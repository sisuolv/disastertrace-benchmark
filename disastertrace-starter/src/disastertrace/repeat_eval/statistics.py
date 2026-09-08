"""Full-denominator checkpoint scores, episode pass^k and both directions of paired change."""

import math
from collections import Counter, defaultdict

from disastertrace.controlled import scorer
from disastertrace.controlled.renderer import render_request
from disastertrace.controlled.schema import METHODS
from disastertrace.post_p5.exposure import carrier, exposure_series
from disastertrace.post_p5.report import trajectory_summary


def pass_power(successes, repeats, k):
    if (
        any(type(v) is not int for v in (successes, repeats, k))
        or not 0 <= successes <= repeats
        or k < 1
    ):
        raise ValueError("invalid reliability counts")
    if repeats < k:
        return None
    return math.comb(successes, k) / math.comb(repeats, k) if successes >= k else 0.0


def summarize(result):
    plan, datasets, slots, traces = (result[k] for k in ("plan", "datasets", "slots", "traces"))
    cells, screens, scored_index, successes, trajectories, source_rows = (
        [],
        [],
        {},
        defaultdict(list),
        [],
        [],
    )
    trace_index = {
        (t["condition"], t["repeat"], t["method"], t["base_episode_id"], t["checkpoint_id"]): t
        for t in traces
    }
    source_by_base = {m["base_episode_id"]: m["group_id"] for m in plan["mapping"]}
    exposures = {}
    by_id = {(condition, e["episode_id"]): e for condition, eps in datasets.items() for e in eps}
    for mapping in plan["mapping"]:
        views = [
            [
                render_request(by_id[c, mapping["episodes"][c]], f"c{i}", method="snapshot")
                for i in range(5)
            ]
            for c in ("base", "irrelevant_scope")
        ]
        exposures[mapping["base_episode_id"]] = exposure_series(*views)
    for condition, episodes in datasets.items():
        order = {
            (ep["episode_id"], cp["checkpoint_id"]): i
            for i, (ep, cp) in enumerate((ep, cp) for ep in episodes for cp in ep["checkpoints"])
        }
        base_ids = {m["episodes"][condition]: m["base_episode_id"] for m in plan["mapping"]}
        for repeat in range(plan["repeats"]):
            for method in METHODS:
                rows = sorted(
                    (
                        t
                        for t in traces
                        if (t["condition"], t["repeat"], t["method"]) == (condition, repeat, method)
                    ),
                    key=lambda t: order[t["episode_id"], t["checkpoint_id"]],
                )
                missing = {
                    (s["episode_id"], s["checkpoint_id"]): "attempted_unresolved"
                    for s in slots
                    if s["slot_id"] in result["unresolved_slot_ids"]
                    and (s["condition"], s["repeat"], s["method"]) == (condition, repeat, method)
                }
                score = scorer._score_rows(episodes, rows, method, missing_status=missing)
                identity = {"condition": condition, "repeat": repeat, "method": method}
                cells.append({**identity, **score})
                source_rows.extend(
                    {
                        **identity,
                        "source_group": group,
                        "counts": part["counts"],
                        "metrics": part["metrics"],
                    }
                    for group, part in score["by_group"].items()
                )
                for family, group in score["by_family"].items():
                    valid = group["counts"]["schema_valid"]
                    planned = group["counts"]["checkpoints"]
                    length = sum(
                        r["finish_reason"] == "length" for r in rows if r["family"] == family
                    )
                    screens.append(
                        {
                            **identity,
                            "family": family,
                            "planned": planned,
                            "valid": valid,
                            "length": length,
                            "passed": planned == 60 and valid >= 58 and length <= 2,
                        }
                    )
                for row in score["per_checkpoint"]:
                    scored_index[
                        (
                            condition,
                            repeat,
                            method,
                            base_ids[row["episode_id"]],
                            row["checkpoint_id"],
                        )
                    ] = row
                for ep in episodes:
                    episode_rows = [
                        r for r in score["per_checkpoint"] if r["episode_id"] == ep["episode_id"]
                    ]
                    successes[(condition, method, base_ids[ep["episode_id"]])].append(
                        all(r["counts"]["all_correct"] for r in episode_rows)
                    )
                    trajectories.append(
                        {
                            **identity,
                            "base_episode_id": base_ids[ep["episode_id"]],
                            "source_group": ep["group_id"],
                            "all_responses_received": all(
                                r["status"] in ("ok", "invalid") for r in episode_rows
                            ),
                            **trajectory_summary(
                                [
                                    {
                                        "checkpoint_id": r["checkpoint_id"],
                                        "all_correct": bool(r["counts"]["all_correct"]),
                                    }
                                    for r in episode_rows
                                ]
                            ),
                        }
                    )
    reliability = [
        {
            "condition": key[0],
            "method": key[1],
            "base_episode_id": key[2],
            "source_group": source_by_base[key[2]],
            "incomplete": any(
                not t["all_responses_received"]
                for t in trajectories
                if (t["condition"], t["method"], t["base_episode_id"]) == key
            ),
            "successes": sum(values),
            "repeats": len(values),
            "pass_power_1": pass_power(sum(values), len(values), 1),
            "pass_power_2": pass_power(sum(values), len(values), 2),
        }
        for key, values in successes.items()
    ]
    pairs = []
    for key, base in scored_index.items():
        if key[0] != "base":
            continue
        other = scored_index[("irrelevant_scope",) + key[1:]]
        x, y = base["counts"]["all_correct"], other["counts"]["all_correct"]
        visible = exposures[key[3]][int(key[4][1:])]
        left, right = trace_index.get(key), trace_index.get(("irrelevant_scope",) + key[1:])
        pairs.append(
            {
                "repeat": key[1],
                "method": key[2],
                "base_episode_id": key[3],
                "checkpoint_id": key[4],
                "source_group": base["group_id"],
                "exposure_status": visible["exposure_status"],
                "first_exposed_checkpoint": visible["first_exposed_checkpoint"],
                "evidence_byte_equal": visible["evidence_byte_equal"],
                "both_received": left is not None and right is not None,
                "actual_carrier_equal": None
                if left is None or right is None
                else carrier(left["request"]) == carrier(right["request"]),
                "base_correct": bool(x),
                "condition_correct": bool(y),
                "outcome": "both_correct"
                if x and y
                else "base_only"
                if x
                else "condition_only"
                if y
                else "both_wrong",
            }
        )
    totals = Counter()
    for row in cells:
        totals.update(row["counts"])
    slices = []
    for repeat in range(plan["repeats"]):
        for method in METHODS:
            for exposure in ("before_first_exposure", "exposed", "never_exposed"):
                selected = [
                    p
                    for p in pairs
                    if (p["repeat"], p["method"], p["exposure_status"])
                    == (repeat, method, exposure)
                ]
                slices.append(
                    {
                        "repeat": repeat,
                        "method": method,
                        "exposure_status": exposure,
                        "planned_pairs": len(selected),
                        "outcomes": dict(Counter(p["outcome"] for p in selected)),
                        "paired_accuracy_difference": sum(
                            p["condition_correct"] - p["base_correct"] for p in selected
                        )
                        / len(selected)
                        if selected
                        else None,
                    }
                )
    source_ranges = []
    for condition in datasets:
        for method in METHODS:
            selected = [
                s for s in source_rows if (s["condition"], s["method"]) == (condition, method)
            ]
            rates = [s["counts"]["all_correct"] / s["counts"]["checkpoints"] for s in selected]
            source_ranges.append(
                {
                    "condition": condition,
                    "method": method,
                    "source_repeat_cells": len(rates),
                    "mean": sum(rates) / len(rates),
                    "minimum": min(rates),
                    "maximum": max(rates),
                    "independent_sources": len({s["source_group"] for s in selected}),
                }
            )
    return {
        "schema_version": "p6_repeat_report_v1",
        "execution_id": plan["execution_id"],
        "experiment_id": plan["experiment_id"],
        "data_sha256": plan["data_sha256"],
        "model_identity": plan["model_identity"],
        "declared_runtime_profile": plan["runtime_profile"],
        "output_track": plan["settings"]["output_track"],
        "scorer_sha256": plan["implementation_files"]["src/disastertrace/controlled/scorer.py"],
        "origin": result["summary"]["origin"],
        "complete": result["summary"]["complete"],
        "incomplete_infrastructure": result["summary"]["incomplete_infrastructure"],
        "counts": dict(totals),
        "cells": cells,
        "format_screens": screens,
        "episode_reliability": reliability,
        "trajectory_errors": trajectories,
        "source_repeat_table": source_rows,
        "source_repeat_mean_range": source_ranges,
        "exposure_slices": slices,
        "paired_changes": pairs,
        "paired_totals": dict(Counter(p["outcome"] for p in pairs)),
        "usage": {
            k: sum(t[k] for t in traces)
            for k in (
                "prompt_tokens",
                "completion_tokens",
                "reasoning_tokens",
                "content_tokens",
                "delimiter_tokens",
                "terminal_tokens",
            )
        },
        "additional_model_calls": 0,
        "eligible_for_model_leaderboard": False,
        "interpretation": "Program diagnostics; three dependent sources in the full candidate, no model reliability estimate or population significance.",
    }
