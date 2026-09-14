"""Recompute seasonal probabilities, denominators and missing-outcome bounds."""

import argparse
import json
import math
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from audit_native_feature_bank import independent_probabilities
from disastertrace.monitoring_v1.native_feature_forecast import feature_vector
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash
from fit_native_feature_bank import native_examples


def audit_unit(pair):
    study, unit = pair
    dataset = Path(unit["dataset"])
    for rel, sha in unit["dataset_files"].items():
        if digest(dataset / rel) != sha:
            raise ValueError("Seasonal data freeze changed")
    original = study / unit["unit"]
    source_audit = read(original / "SOURCE_AUDIT.json")
    for name, sha in source_audit["source_hashes"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Seasonal source receipt or raw bytes changed")
    targets = {r["target_id"]: r for r in read(dataset / "public/TARGETS.json")}
    outcomes = {r["target_id"]: r for r in read(dataset / "private/OUTCOMES.json")}
    pairs = {r["opportunity_id"]: r for r in read(dataset / "public/E_F_PAIRS.json")}
    region = unit["unit"].split("__")[0]
    roster = [
        {
            **r,
            "station": targets[r["target_id"]]["entity"],
            "region": region,
            "role": "seasonal_development",
            "query_ids": pairs[r["opportunity_id"]]["query_ids"],
            "outcome": outcomes[r["target_id"]]["outcome"],
        }
        for r in read(dataset / "public/OPPORTUNITIES.json")
    ]
    banks = {
        mode: read(study / "banks" / (mode + ".json"))
        for mode in ("common", "mask_age", "values")
    }
    expected = {}
    for item in native_examples(dataset, roster):
        for mode, bank in banks.items():
            for condition in ("common_only", "all_registered"):
                features = feature_vector(
                    item["target"],
                    item["candidate"],
                    item["query_ids"],
                    {} if condition == "common_only" else item["views"][-1],
                    at=item["at"],
                    mode=mode,
                )
                sha = canonical_hash(features)
                for calibrated in (False, True):
                    method = (
                        mode
                        + "__"
                        + condition
                        + "__"
                        + ("pav_prior2_cdf" if calibrated else "raw")
                    )
                    ps = independent_probabilities(bank, features, calibrated)
                    for threshold, probability in ps.items():
                        expected[item["opportunity_ids"][threshold], method] = (
                            probability,
                            sha,
                            item["outcomes"][threshold],
                        )
    seen, feature_rows = set(), 0
    rows = [
        json.loads(line) for line in (original / "ROWS.jsonl").read_text().splitlines()
    ]
    roster_ids = {r["opportunity_id"] for r in roster}
    by_id = defaultdict(dict)
    for row in rows:
        key = row["opportunity_id"], row["method"]
        if key in seen or row["opportunity_id"] not in roster_ids:
            raise ValueError("Duplicate or unregistered seasonal row")
        seen.add(key)
        by_id[key[0]][key[1]] = row
        if row["method"] != "FOLLOW":
            p, sha, y = expected[key]
            if (
                not math.isclose(p, row["probability"], abs_tol=1e-12, rel_tol=0)
                or sha != row["feature_sha256"]
                or y != row["outcome"]
            ):
                raise ValueError("Independent seasonal feature probability differs")
            feature_rows += 1
    if (
        set(expected) != {k for k in seen if k[1] != "FOLLOW"}
        or set(by_id) != roster_ids
    ):
        raise ValueError("Incomplete seasonal scored roster")
    for methods in by_id.values():
        if len(methods) != 13:
            raise ValueError("Seasonal opportunity missing a method")
        baseline = methods["FOLLOW"]
        for row in methods.values():
            if (
                row["outcome"] != baseline["outcome"]
                or row["base"] != baseline["probability"]
            ):
                raise ValueError("Methods used different outcomes or baseline")
    return {
        "unit": unit["unit"],
        "rows": len(rows),
        "independent_feature_rows": feature_rows,
        "source_files_verified": len(source_audit["source_hashes"]),
        "source_audit_sha256": digest(original / "SOURCE_AUDIT.json"),
        "rows_sha256": digest(original / "ROWS.jsonl"),
    }


def statistics(rows):
    settled = [r for r in rows if r["outcome"] is not None]
    gains, low, high = [], [], []
    for row in rows:
        p, b, y = row["probability"], row["base"], row["outcome"]
        if not 0 <= p <= 1 or not 0 <= b <= 1:
            raise ValueError("Invalid bounded probability")
        choices = [
            (b - value) ** 2 - (p - value) ** 2
            for value in ([0, 1] if y is None else [y])
        ]
        low.append(min(choices))
        high.append(max(choices))
        if y is not None:
            gains.append(choices[0])
    count = len(settled)
    return {
        "opportunities": len(rows),
        "settled": count,
        "missing": len(rows) - count,
        "positive": sum(r["outcome"] for r in settled),
        "system_brier": math.fsum(
            (r["probability"] - r["outcome"]) ** 2 for r in settled
        )
        / count,
        "base_brier": math.fsum((r["base"] - r["outcome"]) ** 2 for r in settled)
        / count,
        "net_realized_gain": math.fsum(gains) / count,
        "full_population_gain_bounds": [
            math.fsum(low) / len(rows),
            math.fsum(high) / len(rows),
        ],
        "predictions_exactly_zero": sum(r["probability"] == 0 for r in rows),
        "predictions_exactly_one": sum(r["probability"] == 1 for r in rows),
        "posthoc_constant_zero_brier": sum(r["outcome"] for r in settled) / count,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    result, plan = read(args.study / "RESULT.json"), read(args.study / "PLAN.json")
    if not result["passed"] or result["missing_units"]:
        raise ValueError("Complete seasonal evaluation required")
    for rel, sha in plan["files"].items():
        if digest(args.study / rel) != sha:
            raise ValueError("Seasonal source or bank changed")
    units = read(args.study / "DATA_FREEZE.json")["units"]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        units_checked = list(pool.map(audit_unit, [(args.study, u) for u in units]))
    groups, e_groups, drift = defaultdict(list), defaultdict(Counter), Counter()
    for unit in units:
        folder = args.study / unit["unit"]
        for line in (folder / "ROWS.jsonl").read_text().splitlines():
            row = json.loads(line)
            for group in ("ALL", row["region"], row["week"]):
                groups[
                    group + "__" + str(row["threshold"]) + "__" + row["method"]
                ].append(row)
        for line in (folder / "E_ROWS.jsonl").read_text().splitlines():
            row = json.loads(line)
            count = e_groups[str(row["threshold"])]
            count["registered"] += 1
            count["read_slots_" + str(row["read_slots"])] += 1
            count["E_" + row["E"]] += 1
        drift.update(read(folder / "SOURCE_AUDIT.json")["feature_outside5_training_sd"])
    original, metrics = read(args.study / "METRICS.json"), {}
    if set(groups) != set(original):
        raise ValueError("Seasonal metric grouping changed")
    for key, rows in groups.items():
        metrics[key] = value = statistics(rows)
        before = original[key]
        for field in ("opportunities", "settled", "missing"):
            if value[field] != before[field]:
                raise ValueError("Seasonal metric denominator differs")
        for field in ("system_brier", "base_brier", "net_realized_gain"):
            if not math.isclose(value[field], before[field], abs_tol=1e-12, rel_tol=0):
                raise ValueError("Independent seasonal Brier arithmetic differs")
        if any(
            not math.isclose(a, b, abs_tol=1e-12, rel_tol=0)
            for a, b in zip(
                value["full_population_gain_bounds"],
                before["full_population_gain_bounds"],
                strict=True,
            )
        ):
            raise ValueError("Missing-outcome sharp bounds differ")
    publish(args.out / "METRICS.json", metrics)
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "units": units_checked,
            "forecast_rows_verified": sum(r["rows"] for r in units_checked),
            "independent_feature_probability_rows": sum(
                r["independent_feature_rows"] for r in units_checked
            ),
            "metric_groups": len(metrics),
            "E_status_counts": dict(e_groups),
            "feature_outside5_training_sd": dict(drift),
            "new_model_calls_or_fit": 0,
            "confirmation_opened": False,
            "independence_scope": "independent probability and loss arithmetic; frozen source parser and feature extractor reused",
            "constant_zero_control": "posthoc diagnostic on the same denominator; not a newly selected deployable forecast",
            "missingness_bounds": "binary-outcome sharp bounds; not confidence intervals or process-generalization guarantees",
        },
    )
    print(
        json.dumps(
            {
                "passed": True,
                "rows": sum(r["rows"] for r in units_checked),
                "units": len(units_checked),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
