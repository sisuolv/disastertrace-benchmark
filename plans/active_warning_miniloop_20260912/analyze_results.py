"""Descriptive paired analysis; does not fit policies or select favorable targets."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from gpu_worker import save

BASE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def macro(rows, checkpoint=None):
    groups = defaultdict(list)
    for row in rows:
        points = (
            row["checkpoints"]
            if checkpoint is None
            else [row["checkpoints"][checkpoint]]
        )
        groups[row["group"]].extend(
            p["absolute_error"] for p in points if p["absolute_error"] is not None
        )
    values = [mean(points) for points in groups.values() if points]
    return mean(values) if values else None


def main(batch, results, destination):
    rows = [
        json.loads(line) for line in (results / "scores.jsonl").read_text().splitlines()
    ]
    traces = [
        json.loads(line) for line in (results / "traces.jsonl").read_text().splitlines()
    ]
    grouped = defaultdict(list)
    per_group = defaultdict(list)
    for row in rows:
        grouped[row["family"], row["scenario"], row["policy"]].append(row)
        per_group[row["group"], row["scenario"], row["policy"]].append(row)
    paths = {
        path.parent.name: path.parent
        for path in (batch / "runs").glob("*/*/TRACE.json")
    }
    index = {(t["episode_id"], t["scenario"], t["policy"]): t for t in traces}
    e1, e2 = [], []
    for trace in traces:
        if trace["policy"] == "active_raw":
            fixed = index[trace["episode_id"], trace["scenario"], "fixed_forecast"]
            comparisons = []
            for checkpoint in range(2):
                prefix = f"forecast-{checkpoint}"
                first, second = paths[trace["run_id"]], paths[fixed["run_id"]]
                comparisons.append(
                    {
                        "checkpoint": checkpoint,
                        "identical_messages": read(first / (prefix + "-request.json"))[
                            "messages"
                        ]
                        == read(second / (prefix + "-request.json"))["messages"],
                        "identical_raw_output": (
                            first / (prefix + "-raw.txt")
                        ).read_bytes()
                        == (second / (prefix + "-raw.txt")).read_bytes(),
                    }
                )
            e1.append(
                {
                    "episode_id": trace["episode_id"],
                    "scenario": trace["scenario"],
                    "same_queries": [q["tool_id"] for q in trace["receipts"]]
                    == [q["tool_id"] for q in fixed["receipts"]],
                    "forecast_pairs": comparisons,
                }
            )
        if trace["policy"] == "active_canonical" and trace["scenario"] == "clean":
            stale = index[trace["episode_id"], "stale", "active_canonical"]
            comparisons = []
            for stage in ("acquire", "forecast"):
                for checkpoint in range(2):
                    prefix = f"{stage}-{checkpoint}"
                    first, second = paths[trace["run_id"]], paths[stale["run_id"]]
                    comparisons.append(
                        {
                            "stage": stage,
                            "checkpoint": checkpoint,
                            "identical_messages": read(
                                first / (prefix + "-request.json")
                            )["messages"]
                            == read(second / (prefix + "-request.json"))["messages"],
                            "identical_raw_output": (
                                first / (prefix + "-raw.txt")
                            ).read_bytes()
                            == (second / (prefix + "-raw.txt")).read_bytes(),
                        }
                    )
            e2.append({"episode_id": trace["episode_id"], "pairs": comparisons})
    active_tools = Counter(
        q["tool_id"]
        for t in traces
        if t["policy"].startswith("active_")
        for q in t["receipts"]
    )
    report = {
        "interpretation": "descriptive development analysis; no confidence intervals or significance claim",
        "active_acquisition_tool_counts": dict(active_tools),
        "e1_active_raw_vs_fixed": {
            "trajectory_pairs": len(e1),
            "same_query_sequences": sum(r["same_queries"] for r in e1),
            "forecast_message_pairs": sum(len(r["forecast_pairs"]) for r in e1),
            "identical_forecast_messages": sum(
                p["identical_messages"] for r in e1 for p in r["forecast_pairs"]
            ),
            "identical_raw_forecasts": sum(
                p["identical_raw_output"] for r in e1 for p in r["forecast_pairs"]
            ),
            "details": e1,
        },
        "e2_canonical_clean_stale": {
            "trajectory_pairs": len(e2),
            "model_message_pairs": sum(len(r["pairs"]) for r in e2),
            "identical_messages": sum(
                p["identical_messages"] for r in e2 for p in r["pairs"]
            ),
            "identical_raw_outputs": sum(
                p["identical_raw_output"] for r in e2 for p in r["pairs"]
            ),
            "details": e2,
        },
        "per_checkpoint": [
            {
                "family": k[0],
                "scenario": k[1],
                "policy": k[2],
                "first_checkpoint_mae": macro(v, 0),
                "deadline_mae": macro(v, 1),
            }
            for k, v in sorted(grouped.items())
        ],
        "per_group": [
            {
                "group": k[0],
                "scenario": k[1],
                "policy": k[2],
                "targets": len(v),
                "settled_targets": sum(r["outcome_status"] != "unresolved" for r in v),
                "mae": macro(v),
            }
            for k, v in sorted(per_group.items())
        ],
    }
    save(destination, report)
    print(
        json.dumps(
            {
                k: (
                    {a: b for a, b in v.items() if a != "details"}
                    if isinstance(v, dict)
                    else v
                )
                for k, v in report.items()
                if k not in ("per_group", "per_checkpoint")
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.batch, args.results, args.output)
