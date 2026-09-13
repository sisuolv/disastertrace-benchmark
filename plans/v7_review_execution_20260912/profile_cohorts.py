"""Outcome-side cohort description; never supplied to an acquisition policy."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def main(args):
    args.output.mkdir(exist_ok=False)
    results = []
    for dataset in args.datasets:
        targets = {
            t["target_id"]: t
            for t in json.loads((dataset / "public/TARGETS.json").read_text())
        }
        opportunities = json.loads((dataset / "public/OPPORTUNITIES.json").read_text())
        outcomes = {
            r["target_id"]: r
            for r in json.loads((dataset / "private/OUTCOMES.json").read_text())
        }
        source_rows = {
            (r["source_id"], r["source_line"]): r
            for r in json.loads((dataset / "private/DECODED_REPORTS.json").read_text())
        }
        audit = json.loads((dataset / "REGIONAL_JOIN_AUDIT.json").read_text())
        thresholds = sorted({t["threshold"] for t in targets.values()})
        profiles = {}
        for threshold in thresholds:
            ops = [
                o
                for o in opportunities
                if targets[o["target_id"]]["threshold"] == threshold
            ]
            positive = sorted(
                {
                    o["target_id"]
                    for o in ops
                    if outcomes[o["target_id"]]["outcome"] == 1
                }
            )
            weather, sites, days = Counter(), Counter(), Counter()
            raw_references = []
            for ident in positive:
                target, reference = targets[ident], outcomes[ident]
                sites[target["entity"]] += 1
                days[
                    datetime.fromtimestamp(
                        target["physical_start"] / 1_000_000, timezone.utc
                    ).strftime("%Y-%m-%d")
                ] += 1
                codes = set()
                for ref in reference["references"]:
                    row = source_rows[(ref["source_id"], ref["source_line"])]
                    codes.update(row.get("weather", []))
                    raw_references.append(
                        {
                            "target_id": ident,
                            "source_id": ref["source_id"],
                            "line": ref["source_line"],
                            "weather": row.get("weather", []),
                        }
                    )
                weather[" ".join(sorted(codes)) or "no_significant_weather_code"] += 1
            times = sorted({targets[ident]["physical_start"] for ident in positive})
            episodes = {}
            for gap_hours in (6, 12, 24):
                clusters = []
                for time in times:
                    if (
                        not clusters
                        or time - clusters[-1][-1] > gap_hours * 3_600_000_000
                    ):
                        clusters.append([time])
                    else:
                        clusters[-1].append(time)
                episodes[str(gap_hours)] = [
                    {
                        "start": c[0],
                        "last_positive_hour": c[-1],
                        "unique_regional_positive_hours": len(c),
                    }
                    for c in clusters
                ]
            positive_ops = sum(outcomes[o["target_id"]]["outcome"] == 1 for o in ops)
            if (
                positive_ops
                != audit["by_threshold"][str(threshold)]["positive_opportunities"]
                or len(positive)
                != audit["by_threshold"][str(threshold)]["unique_positive_targets"]
            ):
                raise ValueError("Cohort outcome counts differ from source-bound build")
            masks = defaultdict(Counter)
            for o in ops:
                target = targets[o["target_id"]]
                masks[target["entity"]][outcomes[o["target_id"]]["status"]] += 1
            profiles[str(threshold)] = {
                "opportunities": len(ops),
                "positive_opportunities": positive_ops,
                "unique_positive_targets": len(positive),
                "positive_target_dates": dict(days),
                "positive_targets_by_station": dict(sites),
                "native_weather_codes_on_positive_targets": dict(weather),
                "settlement_by_station": {k: dict(v) for k, v in masks.items()},
                "temporal_cluster_sensitivity": episodes,
                "positive_reference_rows": raw_references,
                "interpretation": "Calendar groups and separated positive runs are descriptive. Multiple leads, sites, hours or code combinations do not establish independent physical processes or newly admitted hazards.",
            }
        results.append(
            {
                "dataset": str(dataset.resolve()),
                "audit_sha256": hashlib.sha256(
                    (dataset / "REGIONAL_JOIN_AUDIT.json").read_bytes()
                ).hexdigest(),
                "by_threshold": profiles,
            }
        )
    report = {
        "profiled_at": datetime.now(timezone.utc).isoformat(),
        "schema": "disastertrace.monitoring.outcome_profile.v1",
        "cohorts": results,
        "scope": "Evaluator-only description after calendars were fixed; no relabeling, row removal, method selection or future target feedback.",
    }
    (args.output / "PROFILES.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                Path(r["dataset"]).name: {
                    t: {
                        "positive_targets": p["unique_positive_targets"],
                        "weather": p["native_weather_codes_on_positive_targets"],
                    }
                    for t, p in r["by_threshold"].items()
                }
                for r in results
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
