"""Standard-library-only reconstruction of point errors and group macro means."""

import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from statistics import mean


def read(path):
    return json.loads(path.read_text())


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def number(value):
    return Fraction(str(value))


def close(actual, expected):
    if actual is None or expected is None:
        if actual != expected:
            raise ValueError("missing result changed")
    elif not math.isclose(actual, float(expected), rel_tol=1e-12, abs_tol=1e-10):
        raise ValueError("independent numerical reconstruction differs")


def key(row):
    return tuple(
        row[k]
        for k in ("episode_id", "scenario", "budget", "policy", "fusion", "backend")
    )


def main(dataset, results, summary_file, output):
    episodes = {e["id"]: e for e in read(dataset / "episodes.json")}
    outcomes = {o["episode_id"]: o for o in read(dataset / "outcomes_private.json")}
    traces = {
        key(t): t
        for t in map(json.loads, (results / "traces.jsonl").read_text().splitlines())
    }
    rows = list(map(json.loads, (results / "scores.jsonl").read_text().splitlines()))
    if len(rows) != len(traces) or len({key(r) for r in rows}) != len(rows):
        raise ValueError("score/trace coverage or uniqueness differs")
    groups = defaultdict(list)
    checkpoint_count, unresolved, fallback_count = 0, 0, 0
    for row in rows:
        trace = traces[key(row)]
        episode = episodes[row["episode_id"]]
        outcome = outcomes[row["episode_id"]]
        initial = next(
            a for a in episode["artifacts"] if a["id"] == episode["initial_artifact_id"]
        )
        if row["outcome_status"] != outcome["status"] or row["unit"] != episode["unit"]:
            raise ValueError("outcome status or unit differs")
        if len(row["checkpoints"]) != len(episode["checkpoints"]):
            raise ValueError("checkpoint removed")
        computed = []
        for at, scored in zip(episode["checkpoints"], row["checkpoints"], strict=True):
            checkpoint_count += 1
            time = instant(at)
            if instant(scored["at"]) != time:
                raise ValueError("checkpoint moved")
            commits = [c for c in trace["commits"] if instant(c["at"]) <= time]
            initial_mean = sum(map(number, initial["values"])) / len(initial["values"])
            forecast = number(commits[-1]["value"]) if commits else initial_mean
            fallback_count += not commits
            candidates = [
                a
                for a in episode["artifacts"]
                if a["kind"] == "forecast"
                and instant(a["release_at"]) <= time
                and (row["scenario"] != "delayed" or a["id"] == initial["id"])
            ]
            latest = max(candidates, key=lambda a: instant(a["issued_at"]))
            professional = sum(map(number, latest["values"])) / len(latest["values"])
            close(scored["prediction"], forecast)
            close(scored["latest_professional_prediction"], professional)
            if scored["fallback_to_initial"] != (not commits):
                raise ValueError("fallback count differs")
            if scored["submission_at_this_checkpoint"] != any(
                instant(c["at"]) == time for c in commits
            ):
                raise ValueError("missing submission count differs")
            if outcome["value"] is None:
                unresolved += 1
                close(scored["absolute_error"], None)
                close(scored["professional_absolute_error"], None)
            else:
                target = number(outcome["value"])
                error, reference_error = (
                    abs(forecast - target),
                    abs(professional - target),
                )
                close(scored["absolute_error"], error)
                close(scored["professional_absolute_error"], reference_error)
                computed.append((float(error), float(reference_error)))
        grouping = tuple(
            row[k]
            for k in ("family", "scenario", "budget", "policy", "fusion", "backend")
        )
        groups[grouping].append((row["group"], computed, row))
    summary = read(results / summary_file)
    if len(summary) != len(groups):
        raise ValueError("summary cells removed")
    for cell in summary:
        grouping = tuple(
            cell[k]
            for k in ("family", "scenario", "budget", "policy", "fusion", "backend")
        )
        members = groups[grouping]
        per_group = defaultdict(list)
        for group, values, _ in members:
            per_group[group].extend(values)
        available = [v for v in per_group.values() if v]
        expected = mean(mean(x[0] for x in v) for v in available) if available else None
        reference = (
            mean(mean(x[1] for x in v) for v in available) if available else None
        )
        close(cell["group_macro_mae"], expected)
        close(cell["group_macro_latest_professional_mae"], reference)
        if cell["targets"] != len(members) or cell["settled_targets"] != sum(
            r["outcome_status"] != "unresolved" for _, _, r in members
        ):
            raise ValueError("target denominators changed")
    report = {
        "status": "passed",
        "implementation": "standard library; no project scorer/runtime imported",
        "trajectories": len(rows),
        "checkpoints": checkpoint_count,
        "unresolved_checkpoints": unresolved,
        "initial_fallback_checkpoints": fallback_count,
        "summary_cells": len(summary),
        "checks": [
            "registered checkpoint times",
            "carry-forward/initial fallback",
            "forecast values",
            "latest eligible professional means",
            "absolute errors",
            "group macro MAE",
            "target denominators",
        ],
        "bindings": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                dataset / "episodes.json",
                dataset / "outcomes_private.json",
                results / "traces.jsonl",
                results / "scores.jsonl",
                results / summary_file,
                Path(__file__),
            )
        },
    }
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "bindings"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--summary-file", default="SUMMARY.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.dataset, args.results, args.summary_file, args.output)
