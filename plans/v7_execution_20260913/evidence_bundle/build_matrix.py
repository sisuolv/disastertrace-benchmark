"""Register public calendar selections before reading evaluator outcomes."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import (
    AviationProvider,
    FrozenFrequencyPredictor,
    model_messages,
    visible_e_status,
)
from disastertrace.monitoring_fixed_v1.contracts import fingerprint

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "plans/v7_review_execution_20260912"


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / "matrix_01"
    out.mkdir(exist_ok=False)
    rule = {
        "date_days": [3, 10, 17, 24],
        "cutoff_hours_utc": [0, 12],
        "lead_hours": 3,
        "year_month": "2024-01",
        "regions": {"bay": 5000, "front": 1000},
        "conditions": ["common_only", "fixed_one", "all_registered"],
        "selection": "All registered stations, dates and cutoff hours in the public calendar; no outcome selection",
        "expected_opportunities": 48,
        "expected_model_calls": 144,
        "estimand": "fixed_snapshot_information_response; no acquisition delay or adaptive-session gain claim",
        "exposure": "Previously exposed development calendars; no independent process confirmation",
        "candidate_adoption": "Every valid direct probability is scored; invalid/length uses common baseline with failures retained",
        "E_F": "E computed only from lawful disclosed product intervals; future F reference remains evaluator-only",
        "cost": "Archive logical receipts are descriptive, not measured live network expense; inference measured separately",
    }
    save(out / "DESIGN.json", rule)
    (out / "policy").mkdir()
    (out / "evaluator").mkdir()
    bank_path = OLD / "calibration_bank_01/BANK.json"
    bank = json.loads(bank_path.read_text())
    program = FrozenFrequencyPredictor(bank)
    manifest, deferred_labels, program_rows, rejected, bindings = (
        [],
        [],
        [],
        [],
        {str(bank_path.relative_to(ROOT)): sha(bank_path)},
    )
    for region, name in [
        ("bay", "extension_bay_area_01"),
        ("front", "extension_front_range_03"),
    ]:
        dataset = OLD / name
        provider = AviationProvider(dataset, bank)
        for rel in [
            "public/TARGETS.json",
            "public/OPPORTUNITIES.json",
            "public/E_F_PAIRS.json",
            "public/QUERY_CATALOG.json",
            "environment/QUERY_RESULTS.json",
            "environment/LATEST_BASELINES.json",
        ]:
            bindings[str((dataset / rel).relative_to(ROOT))] = sha(dataset / rel)
        selected = []
        for opportunity in provider.opportunities.values():
            dt = datetime.fromtimestamp(opportunity["cutoff"] / 1_000_000, timezone.utc)
            if (
                dt.strftime("%Y-%m") == rule["year_month"]
                and dt.day in rule["date_days"]
                and dt.hour in rule["cutoff_hours_utc"]
                and opportunity["lead_hours"] == rule["lead_hours"]
                and opportunity["threshold_m"] == rule["regions"][region]
            ):
                selected.append(opportunity)
        for opportunity in sorted(selected, key=lambda r: r["opportunity_id"]):
            deferred_labels.append((region, dataset, opportunity))
            for condition in rule["conditions"]:
                identity = (
                    region + ":" + opportunity["opportunity_id"] + ":" + condition
                )
                call_id = fingerprint(identity)[:20]
                try:
                    bundle = provider.freeze(opportunity["opportunity_id"], condition)
                except ValueError as exc:
                    rejected.append({"identity": identity, "error": str(exc)})
                    continue
                save(out / "policy" / (call_id + ".json"), bundle.to_dict())
                forecast, details = program.predict_with_details(bundle)
                manifest.append(
                    {
                        "call_id": call_id,
                        "region": region,
                        "condition": condition,
                        "opportunity_id": opportunity["opportunity_id"],
                        "target_id": opportunity["target_id"],
                        "bundle_hash": bundle.bundle_hash,
                        "base_hash": bundle.base_hash,
                        "messages_sha256": fingerprint(model_messages(bundle)),
                        "cost": bundle.cost(),
                    }
                )
                program_rows.append(
                    {
                        "call_id": call_id,
                        "forecast": forecast.to_dict(),
                        "mapping_details": details,
                        "e_status": visible_e_status(bundle),
                    }
                )
    # Freeze all policy-side inputs before loading any hidden future references.
    save(out / "MANIFEST.json", manifest)
    save(out / "INPUT_BINDINGS.json", bindings)
    save(out / "REJECTIONS.json", rejected)
    save(out / "PROGRAM.json", program_rows)
    save(out / "BANK.json", bank)
    labels, cache = [], {}
    for region, dataset, opportunity in deferred_labels:
        if dataset not in cache:
            path = dataset / "private/OUTCOMES.json"
            cache[dataset] = {r["target_id"]: r for r in json.loads(path.read_text())}
        record = cache[dataset][opportunity["target_id"]]
        labels.append(
            {
                "region": region,
                "opportunity_id": opportunity["opportunity_id"],
                **record,
            }
        )
    save(out / "evaluator/OUTCOMES.json", labels)
    report = {
        "opportunities": len(deferred_labels),
        "frozen_inputs": len(manifest),
        "rejected": len(rejected),
        "conditions": dict(Counter(r["condition"] for r in manifest)),
        "regions": dict(Counter(r["region"] for r in manifest)),
        "E_by_condition": {
            c: dict(
                Counter(
                    program_rows[i]["e_status"]
                    for i, m in enumerate(manifest)
                    if m["condition"] == c
                )
            )
            for c in rule["conditions"]
        },
        "settled": sum(r["outcome"] is not None for r in labels),
        "positive": sum(r["outcome"] == 1 for r in labels),
        "no_hidden_outcomes_in_policy": True,
        "new_model_calls": 0,
        "limitations": "fixed snapshots, exposed small diagnostic, assumed historical release; not adaptive policy/cross-process confirmation",
    }
    report["accepted_for_bounded_fixed_snapshot_inference"] = (
        not rejected and len(deferred_labels) == 48 and len(manifest) == 144
    )
    save(out / "CPU_ACCEPTANCE.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
