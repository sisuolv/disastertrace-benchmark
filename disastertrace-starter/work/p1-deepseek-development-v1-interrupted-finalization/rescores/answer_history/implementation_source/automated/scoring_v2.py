"""Versioned support scoring; fixed Gold transitions never depend on model errors."""

from __future__ import annotations

from collections import Counter

from .common import fingerprint
from .dynamic import FIELDS, parse_decision, reference_at, score_dynamic
from .evidence_support import (
    EVIDENCE_POLICY_VERSION,
    build_evidence_index,
    validate_citation,
)

SCORER_VERSION = "dynamic_score_v2.0"

_METRICS = {
    "schema_success": ("valid", "attempts"),
    "state_accuracy": ("value_correct", "slots"),
    "grounded_state": ("grounded_correct", "slots"),
    "known_value_accuracy": ("known_value_correct", "known_required"),
    "known_grounded_accuracy": ("known_grounded_correct", "known_required"),
    "action_accuracy": ("action_correct", "attempts"),
    "unknown_accuracy": ("unknown_correct", "unknown_required"),
    "known_answer_coverage": ("known_answered", "known_required"),
    "gold_transition_success": ("gold_transition_grounded", "gold_transitions"),
    "gold_transition_value_success": ("gold_transition_value", "gold_transitions"),
    "gold_preservation": ("gold_preserved_value", "gold_preservations"),
    "gold_preservation_grounded": ("gold_preserved_grounded", "gold_preservations"),
    "self_error_recovery": ("self_error_recovered_grounded", "self_error_opportunities"),
    "self_error_recovery_value": ("self_error_recovered_value", "self_error_opportunities"),
    "provenance_refresh": ("provenance_refreshed", "provenance_refresh_opportunities"),
    "all_correct_checkpoints": ("all_correct", "attempts"),
}
_COUNT_NAMES = sorted({name for pair in _METRICS.values() for name in pair})


def _rate(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _metrics(counts: dict) -> dict:
    return {name: _rate(counts[n], counts[d]) for name, (n, d) in _METRICS.items()}


def _summarize(rows: list[dict]) -> dict:
    counts = {name: sum(row["counts"][name] for row in rows) for name in _COUNT_NAMES}
    return {"counts": counts, "metrics": _metrics(counts)}


def _semantic(slot: dict) -> tuple:
    return slot["status"], slot["value"]


def _sources(slot: dict) -> set[str]:
    return {citation["record_id"] for citation in slot["evidence"]}


def _slot_score(
    episode: dict,
    checkpoint_id: str,
    field: str,
    gold: dict,
    submitted: dict | None,
    status: str,
    index: dict,
) -> dict:
    value_ok = submitted is not None and _semantic(submitted) == _semantic(gold)
    checks = []
    if submitted is not None and submitted["status"] == "known":
        checks = [
            {
                "citation": dict(citation),
                **validate_citation(
                    episode, checkpoint_id, field, submitted["value"], citation, index=index
                ),
            }
            for citation in submitted["evidence"]
        ]
    if submitted is None:
        reason = status
    elif submitted["status"] != gold["status"]:
        reason = "status_mismatch"
    elif not value_ok:
        reason = "value_mismatch"
    elif gold["status"] == "unknown":
        reason = "correct_unknown"
    elif not checks:
        reason = "missing_citation"
    elif not all(check["valid"] for check in checks):
        reason = "unverified_citation"
    else:
        reason = "supported"
    return {
        "value_correct": value_ok,
        "grounded_correct": value_ok and reason in {"correct_unknown", "supported"},
        "reason": reason,
        "citation_checks": checks,
    }


def _paired_correctness(base: list[dict], delay: list[dict]) -> dict:
    indexed_base = {row["checkpoint_id"]: row for row in base}
    indexed_delay = {row["checkpoint_id"]: row for row in delay}
    shared = sorted(indexed_base.keys() & indexed_delay.keys())
    both_slots = sum(
        indexed_base[checkpoint]["slots"][field]["grounded_correct"]
        and indexed_delay[checkpoint]["slots"][field]["grounded_correct"]
        for checkpoint in shared
        for field in FIELDS
    )
    both_checkpoints = sum(
        indexed_base[checkpoint]["all_correct"] and indexed_delay[checkpoint]["all_correct"]
        for checkpoint in shared
    )
    return {
        "matched_checkpoints": len(shared),
        "base_checkpoints": len(base),
        "delay_checkpoints": len(delay),
        "grounded_slots_both_correct": _rate(both_slots, len(shared) * len(FIELDS)),
        "checkpoints_both_correct": _rate(both_checkpoints, len(shared)),
    }


def _event_results(episodes: list[dict], rows: list[dict]) -> dict:
    events = []
    for group_id in sorted({episode["group_id"] for episode in episodes}):
        members = [episode for episode in episodes if episode["group_id"] == group_id]
        episode_ids = sorted(episode["episode_id"] for episode in members)
        event_rows = [row for row in rows if row["episode_id"] in episode_ids]
        event = {"group_id": group_id, "episode_ids": episode_ids, **_summarize(event_rows)}
        branches = {
            branch: [episode for episode in members if episode["episode_id"].endswith(f":{branch}")]
            for branch in ("base", "delay")
        }
        paired = len(members) == 2 and all(len(value) == 1 for value in branches.values())
        event["paired_branches"] = None
        if paired:
            branch_rows = {
                branch: [row for row in event_rows if row["episode_id"] == members[0]["episode_id"]]
                for branch, members in branches.items()
            }
            summaries = {branch: _summarize(items) for branch, items in branch_rows.items()}
            summaries["delay_minus_base"] = {
                name: (
                    summaries["delay"]["metrics"][name]["value"]
                    - summaries["base"]["metrics"][name]["value"]
                    if all(
                        summaries[arm]["metrics"][name]["value"] is not None
                        for arm in ("base", "delay")
                    )
                    else None
                )
                for name in _METRICS
            }
            summaries["both_correct"] = _paired_correctness(
                branch_rows["base"], branch_rows["delay"]
            )
            event["paired_branches"] = summaries
        events.append(event)
    macro, differences = {}, {}
    paired_events = [event for event in events if event["paired_branches"] is not None]
    for name in _METRICS:
        values = [event["metrics"][name]["value"] for event in events]
        defined = [value for value in values if value is not None]
        macro[name] = {
            "value": sum(defined) / len(defined) if defined else None,
            "n_events_defined": len(defined),
            "n_events_total": len(events),
        }
        values = [event["paired_branches"]["delay_minus_base"][name] for event in paired_events]
        defined = [value for value in values if value is not None]
        differences[name] = {
            "value": sum(defined) / len(defined) if defined else None,
            "n_paired_events_defined": len(defined),
            "n_paired_events_total": len(paired_events),
            "n_events_total": len(events),
        }
    return {"per_event": events, "event_macro": macro, "paired_delay_minus_base": differences}


def score_dynamic_v2(episodes: list[dict], traces: list[dict]) -> dict:
    """Rescore verified offline traces without changing their requests or accepted state."""
    # V1 remains the authority for request/history and failure accounting checks.
    original = score_dynamic(episodes, traces)
    index = build_evidence_index(episodes)
    trace_index = {(row["episode_id"], row["checkpoint_id"]): row for row in traces}
    checked = {(row["episode_id"], row["checkpoint_id"]): row for row in original["per_checkpoint"]}
    per_checkpoint = []
    for episode in episodes:
        previous_gold, previous_accepted = None, None
        for checkpoint in episode["checkpoints"]:
            checkpoint_id = checkpoint["checkpoint_id"]
            key = episode["episode_id"], checkpoint_id
            validated = checked[key]
            decision = (
                parse_decision(trace_index[key]["raw_response"])
                if validated["status"] == "ok"
                else None
            )
            reference = reference_at(episode, checkpoint_id)
            counts = dict.fromkeys(_COUNT_NAMES, 0)
            counts["attempts"], counts["valid"] = 1, int(decision is not None)
            row = {
                "episode_id": key[0],
                "checkpoint_id": key[1],
                "status": validated["status"],
                "method": original["method"],
                "slots": {},
                "action_correct": validated["action_correct"],
                "counts": counts,
            }
            for field in FIELDS:
                gold = reference["state"][field]
                submitted = decision["state"][field] if decision is not None else None
                slot = _slot_score(
                    episode, checkpoint_id, field, gold, submitted, validated["status"], index
                )
                value_ok, grounded_ok = slot["value_correct"], slot["grounded_correct"]
                counts["slots"] += 1
                counts["value_correct"] += int(value_ok)
                counts["grounded_correct"] += int(grounded_ok)
                known = gold["status"] == "known"
                counts["known_required"] += int(known)
                counts["known_answered"] += int(
                    known and submitted is not None and submitted["status"] == "known"
                )
                counts["known_value_correct"] += int(known and value_ok)
                counts["known_grounded_correct"] += int(known and grounded_ok)
                counts["unknown_required"] += int(not known)
                counts["unknown_correct"] += int(not known and value_ok)
                transition = preservation = recovery = refresh = False
                if previous_gold is not None:
                    before = previous_gold["state"][field]
                    transition = _semantic(before) != _semantic(gold)
                    preservation = not transition
                    refresh = preservation and known and _sources(before) != _sources(gold)
                    recovery = (
                        preservation
                        and previous_accepted is not None
                        and _semantic(previous_accepted["state"][field]) != _semantic(before)
                    )
                counts["gold_transitions"] += int(transition)
                counts["gold_transition_value"] += int(transition and value_ok)
                counts["gold_transition_grounded"] += int(transition and grounded_ok)
                counts["gold_preservations"] += int(preservation)
                counts["gold_preserved_value"] += int(preservation and value_ok)
                counts["gold_preserved_grounded"] += int(preservation and grounded_ok)
                counts["provenance_refresh_opportunities"] += int(refresh)
                counts["provenance_refreshed"] += int(refresh and grounded_ok)
                counts["self_error_opportunities"] += int(recovery)
                counts["self_error_recovered_value"] += int(recovery and value_ok)
                counts["self_error_recovered_grounded"] += int(recovery and grounded_ok)
                slot["opportunities"] = {
                    "gold_transition": transition,
                    "gold_preservation": preservation,
                    "self_error_recovery": recovery,
                    "provenance_refresh": refresh,
                }
                row["slots"][field] = slot
            row["all_correct"] = row["action_correct"] and all(
                slot["grounded_correct"] for slot in row["slots"].values()
            )
            counts["action_correct"] = int(row["action_correct"])
            counts["all_correct"] = int(row["all_correct"])
            if decision is not None:
                previous_accepted = decision
            previous_gold = reference
            per_checkpoint.append(row)
    result = {
        key: value
        for key, value in original.items()
        if key not in {"schema_version", "metrics", "per_checkpoint", "status_counts"}
    }
    result.update(
        {
            "schema_version": "dynamic_score_v2",
            "scorer_version": SCORER_VERSION,
            "evidence_policy_version": EVIDENCE_POLICY_VERSION,
            "evidence_index_fingerprint": fingerprint(index),
            **_summarize(per_checkpoint),
            "per_checkpoint": per_checkpoint,
            "status_counts": dict(sorted(Counter(row["status"] for row in per_checkpoint).items())),
            "v1_method_conditional_metrics": {
                name: original["metrics"][name]
                for name in ("required_change_success", "preservation")
            },
            "metric_spec": "docs/METRICS_V2.md",
            "paired_interpretation": (
                "Dependent branches of each storm; correctness is against each branch's own Gold. "
                "Event macro uses equal event weights and excludes undefined rates with counts."
            ),
            **_event_results(episodes, per_checkpoint),
        }
    )
    return result
