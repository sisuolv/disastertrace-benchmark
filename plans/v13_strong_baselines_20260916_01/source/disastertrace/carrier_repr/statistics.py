"""Descriptive paired outcomes; no independence or population-significance claim."""

from collections import Counter, defaultdict
from statistics import mean, median


def paired(slots, scores, public, private, captures):
    by_slot = {r["slot_id"]: r["score"] for r in scores["records"]}
    if len(by_slot) != len(slots) or set(by_slot) != {s["slot_id"] for s in slots}:
        raise ValueError("paired scores must retain the exact planned denominator")
    captured = {c["slot_id"]: c for c in captures}
    groups = defaultdict(dict)
    for s in slots:
        if s["encoding"] in groups[s["pair_id"]]:
            raise ValueError("duplicate representation arm")
        groups[s["pair_id"]][s["encoding"]] = s
    counts, storms, records = Counter(), defaultdict(Counter), []
    transitions, repeats, availability, deltas = (
        defaultdict(Counter),
        defaultdict(Counter),
        Counter(),
        [],
    )
    for pair, arms in sorted(groups.items()):
        if set(arms) != {"json", "text"}:
            raise ValueError("paired report lacks a planned arm")
        first, second = arms["json"], arms["text"]
        if any(
            first[k] != second[k]
            for k in ("source_slot_id", "seed", "opportunity_id", "eligible", "repeat")
        ):
            raise ValueError("representations did not share source prefix and seed")
        a, b = by_slot[first["slot_id"]], by_slot[second["slot_id"]]
        state = (
            ("json_correct" if a["all_correct"] else "json_wrong")
            + "_"
            + ("text_correct" if b["all_correct"] else "text_wrong")
        )
        storm = public["opportunities"][first["opportunity_id"]]["query"]["storm_id"]
        transition = private["references"][first["opportunity_id"]]["transition"]
        arm_captures = [captured.get(arm["slot_id"]) for arm in (first, second)]
        available = (
            "ineligible_prefix"
            if not first["eligible"]
            else "both_captured"
            if all(arm_captures)
            else "one_captured"
            if any(arm_captures)
            else "neither_captured"
        )
        availability[available] += 1
        tokens = {
            arm["encoding"]: captured[arm["slot_id"]]["prompt_tokens"]
            if arm["slot_id"] in captured
            else None
            for arm in (first, second)
        }
        delta = tokens["text"] - tokens["json"] if all(arm_captures) else None
        if delta is not None:
            deltas.append(delta)
        counts[state] += 1
        storms[storm][state] += 1
        transitions[transition][state] += 1
        repeats[str(first["repeat"])][state] += 1
        records.append(
            {
                "pair_id": pair,
                "source_slot_id": first["source_slot_id"],
                "outcome": state,
                "eligible": first["eligible"],
                "storm_id": storm,
                "transition": transition,
                "repeat": first["repeat"],
                "capture_availability": available,
                "prompt_tokens": tokens,
                "prompt_tokens_text_minus_json": delta,
            }
        )
    discordant = counts["json_wrong_text_correct"] - counts["json_correct_text_wrong"]
    return {
        "planned_pairs": len(groups),
        "counts": dict(counts),
        "text_minus_json_correct_count": discordant,
        "text_minus_json_accuracy": discordant / len(groups) if groups else None,
        "by_storm": {k: dict(v) for k, v in storms.items()},
        "by_transition": {k: dict(v) for k, v in transitions.items()},
        "by_repeat": {k: dict(v) for k, v in repeats.items()},
        "capture_availability": dict(availability),
        "captured_pair_prompt_token_difference": {
            "pairs_with_both_captures": len(deltas),
            "equal_length_pairs": deltas.count(0),
            "minimum": min(deltas) if deltas else None,
            "maximum": max(deltas) if deltas else None,
            "mean": mean(deltas) if deltas else None,
            "median": median(deltas) if deltas else None,
            "direction": "text_minus_json",
            "equal_information_is_not_equal_token_length": True,
        },
        "records": records,
        "estimand": "one-step representation difference conditional on saved structured-state prefixes",
        "independent_storms": len(storms),
        "population_inference": False,
        "native_scorer_trajectory_ids_here_are_single_step_branches": True,
    }
