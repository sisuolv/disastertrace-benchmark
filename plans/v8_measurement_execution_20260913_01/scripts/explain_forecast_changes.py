"""Separate numeric proposals from later baseline changes in audited snapshots."""

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validation = read(args.analysis / "VALIDATION.json")
    if not validation["all_metrics_match_independent_scores"]:
        raise ValueError("A qualified independent analysis is required")
    arms = read(args.analysis / "ARMS.json")
    scored = {
        (r["case"], r["opportunity_id"]): r
        for r in read(args.analysis / "OPPORTUNITIES.json")
    }
    summaries, positions = [], []
    for arm in arms:
        if arm["status"] != "qualified":
            summaries.append(
                {"case": arm["case"], "status": arm["status"], "counts": None}
            )
            continue
        path = args.batch / "runs" / arm["case"] / "REPORT.json"
        if sha(path) != arm["source_report_sha256"]:
            raise ValueError("Changed original report")
        report = read(path)
        calls = {r["call_id"]: r for r in report["calls"]}
        if len(calls) != len(report["calls"]):
            raise ValueError("Duplicate model/program call identity")
        counts, gains, strata = Counter(), [], defaultdict(list)
        for snapshot in report["snapshots"]:
            key = (arm["case"], snapshot["opportunity_id"])
            item = scored[key]
            p, base = snapshot["forecast"]["value"], snapshot["base_forecast"]["value"]
            if p != item["prediction"] or base != item["base"]:
                raise ValueError("Scored effective forecast differs")
            old_base = proposal = call_head = None
            if snapshot["mode"] == "FOLLOW":
                if p != base or snapshot["override_call_id"] is not None:
                    raise ValueError(
                        "A follow snapshot cannot retain an effective override"
                    )
                category = "follow_common_baseline"
            else:
                if snapshot["mode"] != "OVERRIDE":
                    raise ValueError("Unknown effective forecast mode")
                call = calls[snapshot["override_call_id"]]
                bundle = call["bundle"]["payload"]
                if (
                    call["admission_status"] != "accepted"
                    or bundle["target"] != snapshot["target"]
                ):
                    raise ValueError(
                        "Effective override lacks an accepted same-target call"
                    )
                proposal = call["proposed_probability"]
                old_base = bundle["baseline"]["forecast"]["value"]
                call_head = call["head"]
                if proposal != p:
                    raise ValueError(
                        "Effective override value differs from admitted proposal"
                    )
                category = (
                    "override_equal_current_baseline"
                    if p == base
                    else "copied_dispatch_baseline_current_baseline_differs"
                    if proposal == old_base
                    else "proposal_differs_from_dispatch_and_current_baseline"
                )
            counts[category] += 1
            gain = item["gain_vs_common_base"]
            if gain is not None:
                gains.append(gain)
                strata[category].append(gain)
            positions.append(
                {
                    "case": arm["case"],
                    "opportunity_id": snapshot["opportunity_id"],
                    "mode": snapshot["mode"],
                    "category": category,
                    "override_call_id": snapshot["override_call_id"],
                    "call_head": call_head,
                    "dispatch_baseline": old_base,
                    "proposal": proposal,
                    "current_baseline": base,
                    "effective_prediction": p,
                    "proposal_equals_dispatch_baseline": None
                    if proposal is None
                    else proposal == old_base,
                    "dispatch_baseline_value_changed_by_cutoff": None
                    if old_base is None
                    else old_base != base,
                    "gain_vs_current_common_baseline": gain,
                }
            )
        if sum(counts.values()) != arm["registered_opportunities"]:
            raise ValueError("Lost cutoff denominator")
        net = sum(gains) / len(gains) if gains else None
        expected = arm["F_metrics"]["net_realized_gain"]
        if (net is None) != (expected is None) or (
            net is not None
            and not math.isclose(net, expected, rel_tol=0, abs_tol=1e-14)
        ):
            raise ValueError(
                "Attribution does not sum to the independent full-denominator gain"
            )
        summaries.append(
            {
                "case": arm["case"],
                "status": arm["status"],
                "counts": dict(counts),
                "mean_gain_vs_baseline": net,
                "strata": {
                    k: {
                        "mature_positions": len(v),
                        "loss_gain_sum": sum(v),
                        "contribution_to_full_mature_mean": sum(v) / len(gains),
                        "help": sum(g > 1e-15 for g in v),
                        "harm": sum(g < -1e-15 for g in v),
                    }
                    for k, v in sorted(strata.items())
                },
                "original_report_sha256": sha(path),
            }
        )
    if len(positions) != len(scored):
        raise ValueError("Incomplete independent-score coverage")
    result = {
        "passed": True,
        "registered_sessions": len(arms),
        "qualified_sessions": sum(a["status"] == "qualified" for a in arms),
        "qualified_cutoff_positions": len(positions),
        "all_gains_sum_to_independent_scores": True,
        "engineering_rehearsal": validation["engineering_rehearsal"],
        "new_model_calls": 0,
        "source_hashes": {
            n: sha(args.analysis / n)
            for n in ("VALIDATION.json", "ARMS.json", "OPPORTUNITIES.json")
        },
        "interpretation": [
            "Descriptions use the admitted proposal and the baseline visible at dispatch versus cutoff; this is not causal source-version attribution.",
            "An unchanged numeric proposal may later differ from the current common baseline under a persistent override. It is not evidence that the model generated a new probability.",
            "Numeric differences may be rounding or another behavior; no deliberateness or extra information use is inferred.",
            "Same-value accepted overrides remain overrides. Failed or incomplete sessions are never filled in as model results.",
        ],
    }
    args.output.mkdir(exist_ok=False)
    for name, value in (
        ("ARMS.json", summaries),
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
