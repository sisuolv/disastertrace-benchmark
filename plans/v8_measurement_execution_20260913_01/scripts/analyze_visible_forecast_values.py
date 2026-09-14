"""Compare proposals with both probabilities actually visible at dispatch."""

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probability(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("Expected a finite probability")
    return value


def value_match(proposal, base, state):
    probability(base)
    probability(state)
    if proposal is None:
        return "no_parsed_probability"
    probability(proposal)
    if proposal == base and proposal == state:
        return "matches_both"
    if proposal == base:
        return "matches_dispatch_baseline_only"
    if proposal == state:
        return "matches_visible_state_only"
    return "differs_from_both"


def describe(report, scored_rows, expected_mean_gain):
    calls, call_rows = {}, []
    counts = {kind: Counter() for kind in ("model", "program")}
    for call in report["calls"]:
        ident = call["call_id"]
        if ident in calls:
            raise ValueError("Duplicate call identity")
        bundle = call["bundle"]["payload"]
        base = bundle["baseline"]["forecast"]["value"]
        state = bundle["state"]["forecast"]["value"]
        proposal = call["proposed_probability"]
        category = value_match(proposal, base, state)
        kind = "program" if call["head"] == "program" else "model"
        item = {
            "call_id": ident,
            "opportunity_id": call["opportunity_id"],
            "kind": kind,
            "admission_status": call["admission_status"],
            "proposal": proposal,
            "dispatch_baseline": base,
            "dispatch_visible_state": state,
            "visible_state_mode": bundle["state"]["mode"],
            "value_match": category,
            "equals_visible_state": proposal == state,
            "differs_from_dispatch_baseline": proposal is not None and proposal != base,
        }
        calls[ident] = item
        call_rows.append(item)
        counts[kind][category] += 1

    scored = {row["opportunity_id"]: row for row in scored_rows}
    if len(scored) != len(scored_rows):
        raise ValueError("Duplicate scored opportunity")
    positions, category_gains, all_gains, seen = [], defaultdict(list), [], set()
    for snapshot in report["snapshots"]:
        ident = snapshot["opportunity_id"]
        if ident in seen or ident not in scored:
            raise ValueError("Unexpected cutoff denominator")
        seen.add(ident)
        score = scored[ident]
        proposal = snapshot["forecast"]["value"]
        base = snapshot["base_forecast"]["value"]
        if proposal != score["prediction"] or base != score["base"]:
            raise ValueError("Independent scored forecast mismatch")
        gain = score["gain_vs_common_base"]
        category = "follow_current_baseline"
        call_id = snapshot["override_call_id"]
        if snapshot["mode"] == "FOLLOW":
            if call_id is not None or proposal != base:
                raise ValueError("Invalid FOLLOW snapshot")
        elif snapshot["mode"] == "OVERRIDE":
            item = calls[call_id]
            if item["admission_status"] != "accepted" or proposal != item["proposal"]:
                raise ValueError("Override lacks its accepted proposal")
            category = item["kind"] + "_" + item["value_match"]
        else:
            raise ValueError("Unknown forecast mode")
        if gain is not None:
            all_gains.append(gain)
            category_gains[category].append(gain)
        positions.append(
            {
                "opportunity_id": ident,
                "override_call_id": call_id,
                "category": category,
                "effective_probability": proposal,
                "current_baseline": base,
                "gain_vs_current_common_baseline": gain,
            }
        )
    if seen != set(scored):
        raise ValueError("Lost cutoff denominator")
    mean_gain = sum(all_gains) / len(all_gains) if all_gains else None
    if (mean_gain is None) != (expected_mean_gain is None) or (
        mean_gain is not None
        and not math.isclose(mean_gain, expected_mean_gain, rel_tol=0, abs_tol=1e-14)
    ):
        raise ValueError("Attribution differs from independent full-denominator score")
    model = [item for item in call_rows if item["kind"] == "model"]
    summary = {
        "call_value_matches": {kind: dict(values) for kind, values in counts.items()},
        "model_forecast_calls": len(model),
        "model_proposals_equal_visible_state": sum(r["equals_visible_state"] for r in model),
        "model_proposals_differ_from_dispatch_baseline": sum(
            r["differs_from_dispatch_baseline"] for r in model
        ),
        "model_proposals_differ_from_both_visible_probabilities": sum(
            r["value_match"] == "differs_from_both" for r in model
        ),
        "cutoff_positions": len(positions),
        "mean_gain_vs_baseline": mean_gain,
        "cutoff_category_counts": dict(Counter(r["category"] for r in positions)),
        "gain_contributions_to_full_mature_mean": {
            kind: sum(values) / len(all_gains)
            for kind, values in sorted(category_gains.items())
        },
    }
    return summary, call_rows, positions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    validation = read(args.analysis / "VALIDATION.json")
    if not validation["all_metrics_match_independent_scores"]:
        raise ValueError("Qualified independent analysis required")
    if validation["engineering_rehearsal"]:
        raise ValueError("This report requires actual model results")
    arms = read(args.analysis / "ARMS.json")
    scored = defaultdict(list)
    for row in read(args.analysis / "OPPORTUNITIES.json"):
        scored[row["case"]].append(row)
    summaries, calls, positions = [], [], []
    for arm in arms:
        ident = arm["case"]
        if arm["status"] != "qualified":
            summaries.append({"case": ident, "status": arm["status"], "metrics": None})
            continue
        path = args.batch / "runs" / ident / "REPORT.json"
        if sha(path) != arm["source_report_sha256"]:
            raise ValueError("Changed source report")
        summary, call_rows, snapshot_rows = describe(
            read(path), scored[ident], arm["F_metrics"]["net_realized_gain"]
        )
        if summary["model_forecast_calls"] != arm["E_model_calls"]:
            raise ValueError("Model forecast-call denominator changed")
        summaries.append({"case": ident, "status": arm["status"], "metrics": summary})
        calls.extend(dict(case=ident, **row) for row in call_rows)
        positions.extend(dict(case=ident, **row) for row in snapshot_rows)
    model = [row for row in calls if row["kind"] == "model"]
    result = {
        "passed": True,
        "registered_sessions": len(arms),
        "qualified_sessions": sum(row["status"] == "qualified" for row in arms),
        "model_predictor_calls": len(model),
        "model_proposals_equal_visible_state": sum(row["equals_visible_state"] for row in model),
        "model_proposals_differ_from_dispatch_baseline": sum(
            row["differs_from_dispatch_baseline"] for row in model
        ),
        "model_proposals_differ_from_both_visible_probabilities": sum(
            row["value_match"] == "differs_from_both" for row in model
        ),
        "qualified_cutoff_positions": len(positions),
        "all_gain_contributions_match_independent_scores": True,
        "new_model_calls": 0,
        "source_hashes": {
            name: sha(args.analysis / name)
            for name in ("VALIDATION.json", "ARMS.json", "OPPORTUNITIES.json")
        },
        "interpretation": [
            "Exact numeric equality to two visible fields, not causal evidence of copying or of evidence use.",
            "Matching the current state may differ from the latest common baseline under persistent overrides.",
            "Reading state.forecast.value reproduces matching numeric F proposals on these captured inputs; it does not reproduce E, selector choices or a new closed-loop experiment.",
            "A value different from both fields may be rounding or other behavior; it does not establish useful forecasting.",
            "Dispatch calls and cutoff positions have separate denominators; selector-only calls are not forecast answers.",
            "No source, response, model, scorer or frozen execution was changed by this posthoc report.",
        ],
    }
    args.output.mkdir(exist_ok=False)
    for name, value in (
        ("ARMS.json", summaries),
        ("CALLS.json", calls),
        ("OPPORTUNITIES.json", positions),
        ("VALIDATION.json", result),
    ):
        with (args.output / name).open("x") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
    (args.output / "EXECUTED_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
