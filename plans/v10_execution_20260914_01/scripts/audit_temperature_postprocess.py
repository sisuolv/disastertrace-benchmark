"""Independently reconstruct EMOS/ECC probabilities, roles and common masks."""

import argparse
import datetime as dt
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from scipy.special import ndtri


def transform(products, bank):
    calibrated = {}
    projections = 0
    for product in products:
        values = {}
        for variable in ("min", "max"):
            raw = np.asarray(
                product["forecast_" + variable + "_members_C"], dtype=float
            )
            p = bank[variable]
            mean = p["a"] + p["b"] * float(np.mean(raw))
            variance = math.exp(p["log_c"]) + math.exp(p["log_d"]) * float(np.var(raw))
            ranks = np.argsort(raw, kind="stable")
            result = np.empty_like(raw)
            result[ranks] = mean + np.sqrt(variance) * ndtri(
                (np.arange(len(raw)) + 0.5) / len(raw)
            )
            values[variable] = result
        wrong = values["min"] > values["max"]
        projections += int(wrong.sum())
        center = (values["min"] + values["max"]) / 2
        values["min"][wrong] = center[wrong]
        values["max"][wrong] = center[wrong]
        calibrated[product["target_date"]] = values
    return calibrated, projections


def probability(row, daily):
    target = row["target"]
    dates = [
        dt.datetime.fromtimestamp(t / 1e6, dt.timezone.utc).date().isoformat()
        for t in range(target["physical_start"], target["physical_end"], 86400_000_000)
    ]
    variable = target["variable"]
    field = "min" if variable == "daily_min_2m_temperature" else "max"
    matrix = np.asarray([daily[date][field] for date in dates])
    members = (
        matrix[0]
        if len(dates) == 1
        else np.min(matrix, axis=0)
        if variable.startswith("min_of_3")
        else np.max(matrix, axis=0)
    )
    truth = (
        members >= target["threshold"]
        if target["event_operator"] == "ge"
        else members < target["threshold"]
    )
    return float(np.mean(truth))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    frozen = read(args.bank / "FREEZE_BEFORE_EVALUATION.json")
    for path, sha in frozen["input_files"].items():
        if digest(Path(path)) != sha:
            raise ValueError("Original native source projection changed")
    for rel, sha in frozen["source_files"].items():
        if digest(args.bank / rel) != sha:
            raise ValueError("Frozen postprocessor source changed")
    for path, key in (
        ("BANK.json", "bank_sha256"),
        ("SPEC.json", "registration_sha256"),
        ("ROLE_REGISTRY.json", "roles_sha256"),
    ):
        if digest(args.bank / path) != frozen[key]:
            raise ValueError("Bank or pre-evaluation registration changed")
    bank = read(args.bank / "BANK.json")
    objective = {}
    for variable, records in read(args.bank / "TRAINING_RECORDS.json").items():
        repeat = Counter(r["date"] for r in records)
        weights = np.array([1 / repeat[r["date"]] for r in records])
        raw = np.asarray([r["members"] for r in records])
        observed = np.array([r["observed"] for r in records])
        p = bank[variable]
        mean = p["a"] + p["b"] * raw.mean(axis=1)
        variance = np.exp(p["log_c"]) + np.exp(p["log_d"]) * raw.var(axis=1)
        loss = float(
            np.dot(
                weights, 0.5 * (np.log(variance) + (observed - mean) ** 2 / variance)
            )
            / weights.sum()
        )
        if not math.isclose(loss, p["objective"], abs_tol=1e-10, rel_tol=1e-10):
            raise ValueError("Independent Gaussian fitting objective differs")
        if any(not r["date"].startswith("2017-") for r in records):
            raise ValueError("Non-training outcome leaked into the fit")
        objective[variable] = {
            "objective": loss,
            "native_observed_days": len(repeat),
            "forecast_versions": len(records),
        }
    registry = read(args.bank / "ROLE_REGISTRY.json")
    allowed = {r["opportunity_id"] for r in registry if r["role"] == "development_2018"}
    raw_rows = {}
    outcomes = {}
    for name in frozen["input_files"]:
        path = Path(name)
        if path.name == "POLICY.json":
            for row in read(path)["rows"]:
                if row["opportunity_id"] in allowed:
                    raw_rows[row["opportunity_id"]] = row
        else:
            outcomes.update({r["opportunity_id"]: r for r in read(path)})
    scored = [json.loads(line) for line in (args.bank / "EVALUATION_ROWS.jsonl").open()]
    if len(scored) != len(allowed) or {r["opportunity_id"] for r in scored} != allowed:
        raise ValueError("Incomplete chronological evaluation registry")
    cache = {}
    groups = defaultdict(list)
    for record in scored:
        row = raw_rows[record["opportunity_id"]]
        outcome = outcomes[row["opportunity_id"]]
        if row["origin"] not in cache:
            cache[row["origin"]] = transform(row["common"]["daily_products"], bank)
        transformed, projections = cache[row["origin"]]
        raw = {
            p["target_date"]: {
                v: np.asarray(p["forecast_" + v + "_members_C"]) for v in ("min", "max")
            }
            for p in row["common"]["daily_products"]
        }
        expected = {
            "raw51": probability(row, raw),
            "emos_ecc51": probability(row, transformed),
            "past_year_climatology": bank["climatology"][row["event"]]["probability"],
        }
        if (
            record["outcome"] != outcome["value"]
            or record["outcome_status"] != outcome["status"]
            or record["projection_count_in_full_issuance"] != projections
            or any(
                not math.isclose(
                    p, record["probabilities"][method], abs_tol=1e-12, rel_tol=0
                )
                for method, p in expected.items()
            )
        ):
            raise ValueError("Independent event/reference/projection differs")
        for method, p in expected.items():
            groups[row["event"] + "__" + method].append(
                {
                    "opportunity_id": row["opportunity_id"],
                    "base": expected["raw51"],
                    "prediction": p,
                    "outcome": outcome["value"]
                    if outcome["status"] == "mature"
                    else None,
                    "region": "DWD00460",
                    "period": dt.datetime.fromtimestamp(
                        row["target"]["physical_start"] / 1e6, dt.timezone.utc
                    ).strftime("%Y-%m"),
                    "source": "native_DWD_daily",
                    "maturity": outcome["status"],
                    "quality": outcome.get("quality_status", "unknown"),
                }
            )
    reports = {key: brier_report(rows) for key, rows in groups.items()}
    original = read(args.bank / "RESULT.json")
    for key, report in reports.items():
        previous = original["metrics"][key]
        if (
            report["opportunities"] != previous["registered"]
            or report["settled"] != previous["scored"]
            or not math.isclose(
                report["system_brier"], previous["brier"], abs_tol=1e-12, rel_tol=0
            )
        ):
            raise ValueError("Independent common-mask Brier differs")
    publish(args.out / "MISSINGNESS_AND_GAIN.json", reports)
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "original_opportunities": len(registry),
            "evaluation_opportunities": len(scored),
            "independently_transformed_issuances": len(cache),
            "fit_objective": objective,
            "same_member_event_and_minmax_projection_verified": True,
            "source_hashes_verified": True,
            "new_model_or_fitting_calls": 0,
            "confirmation_opened": False,
            "scope": "independent NumPy/SciPy arithmetic, input identity and masked score replay; not new physical-observation collection",
        },
    )
    print({"passed": True, "evaluation": len(scored)}, flush=True)


if __name__ == "__main__":
    main()
