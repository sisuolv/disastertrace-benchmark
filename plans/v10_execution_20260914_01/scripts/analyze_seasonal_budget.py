"""Describe audited budget controls without opening data or making new calls."""

import argparse
import datetime as dt
import hashlib
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

from disastertrace.monitoring_v1.scoring import brier_report


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(rows, reference, method):
    by_arm = defaultdict(dict)
    for row in rows:
        key = row["case"] + "/" + row["opportunity_id"]
        if key in by_arm[row["arm"]]:
            raise ValueError("Duplicate method opportunity")
        by_arm[row["arm"]][key] = row
    if set(by_arm[method]) != set(by_arm[reference]):
        raise ValueError("Unmatched comparison roster")
    records = []
    for key, row in sorted(by_arm[method].items()):
        base = by_arm[reference][key]
        if row["outcome"] != base["outcome"]:
            raise ValueError("Unmatched outcome masks")
        region, day, _ = row["case"].split("__")
        records.append(
            {
                "opportunity_id": key,
                "prediction": row["probability"],
                "base": base["probability"],
                "outcome": row["outcome"],
                "region": region,
                "period": day,
                "source": "IEM routine METAR",
                "maturity": "archived_report",
                "quality": "missing" if row["outcome"] is None else "settled",
                "baseline_kind": "research",
            }
        )
    report = brier_report(records)
    missing = [row for row in records if row["outcome"] is None]
    if len(missing) > 12:
        raise ValueError(
            "This small-scope exhaustive check supports at most12 missing outcomes"
        )
    settled_gain = math.fsum(
        (row["base"] - row["outcome"]) ** 2 - (row["prediction"] - row["outcome"]) ** 2
        for row in records
        if row["outcome"] is not None
    )
    # Enumerate binary completions only to check bounds, never to impute scores.
    worlds = [
        (
            settled_gain
            + math.fsum(
                (row["base"] - y) ** 2 - (row["prediction"] - y) ** 2
                for row, y in zip(missing, values, strict=True)
            )
        )
        / len(records)
        for values in itertools.product((0, 1), repeat=len(missing))
    ]
    if not all(
        math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12)
        for actual, expected in zip(
            (min(worlds), max(worlds)),
            report["full_population_gain_bounds"],
            strict=True,
        )
    ):
        raise ValueError("Analytic and enumerated missing-outcome bounds differ")
    report["positive"] = sum(row["outcome"] == 1 for row in records)
    report["binary_completions_checked"] = len(worlds)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run, out = args.run.absolute(), args.out.absolute()
    source = run / "reports/seasonal_controls_audit_01"
    audit = read(source / "RESULT.json")
    if not audit["passed"] or audit["trajectories"] != 216:
        raise ValueError("Complete216trajectory journal audit required")
    rows = [
        json.loads(line) for line in (source / "ROWS.jsonl").read_text().splitlines()
    ]
    if len(rows) != 15552:
        raise ValueError("Unexpected registered method-row count")
    groups = defaultdict(list)
    for row in rows:
        groups["ALL", row["threshold_m"]].append(row)
        groups[row["case"].split("__")[1], row["threshold_m"]].append(row)
    comparisons = [
        ("FOLLOW", "B11_COVERAGE"),
        ("F_BASE_ONLY", "B11_COVERAGE"),
        ("B11_BATCH", "B11_COVERAGE"),
        ("B00_COVERAGE", "B01_COVERAGE"),
        ("B10_COVERAGE", "B11_COVERAGE"),
        ("B00_COVERAGE", "B10_COVERAGE"),
        ("B01_COVERAGE", "B11_COVERAGE"),
    ]
    reports = {
        f"{period}__{threshold}__{method}_vs_{reference}": paired(
            values, reference, method
        )
        for (period, threshold), values in sorted(groups.items())
        for reference, method in comparisons
    }
    result = {
        "passed": True,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_audit_sha256": digest(source / "RESULT.json"),
        "source_rows_sha256": digest(source / "ROWS.jsonl"),
        "executed_source_sha256": digest(Path(__file__)),
        "registered_method_rows": len(rows),
        "paired_groups": len(reports),
        "metrics": reports,
        "new_model_calls": 0,
        "new_source_downloads": 0,
        "confirmation_opened": False,
        "interpretation": "posthoc arithmetic on audited captured program controls; no independent confirmation",
        "bounds_scope": "binary missing-outcome sensitivity on registered opportunities, not confidence intervals",
        "independent_process_count_established": False,
    }
    out.mkdir(exist_ok=False)
    (out / "EXECUTED_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    with (out / "RESULT.json").open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "metrics"}))


if __name__ == "__main__":
    main()
