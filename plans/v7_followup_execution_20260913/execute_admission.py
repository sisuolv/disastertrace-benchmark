"""Real archived H15 fixtures through durable typed admission (no model calls)."""

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    TypedOpportunity,
    score_admitted,
)
from disastertrace.monitoring_fixed_v1.aviation import FrozenFrequencyPredictor
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Target,
    canonical,
    fingerprint,
)
from disastertrace.monitoring_v1.calibration import predict
from disastertrace.monitoring_v1.journal import EventJournal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MATRIX = ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01"


def save(path, row):
    with path.open("x") as f:
        f.write(json.dumps(row, indent=2, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def mission_inputs():
    rows = json.loads((HERE / "EXPOSURE_LEDGER.json").read_text())["rows"]
    bundles = {
        r["call_id"]: EvidenceBundle.restore(
            json.loads((MATRIX / "policy" / (r["call_id"] + ".json")).read_text())
        )
        for r in rows
    }
    common = [
        bundles[r["call_id"]].policy_view()
        for r in rows
        if r["condition"] == "common_only"
    ]
    opportunities = [
        TypedOpportunity(r["opportunity_id"], Target(**r["target"]), r["cutoff"])
        for r in common
    ]
    bank = json.loads((MATRIX / "BANK.json").read_text())
    fallbacks = {}
    for row in common:
        target = Target(**row["target"])
        legacy = row["baseline"]["content"]["legacy_target_contract"]
        probability = predict(bank, legacy, None)["probability"]
        fallbacks[target.target_id] = {
            "target_contract_hash": target.contract_hash,
            "kind": "event_probability",
            "units": "probability",
            "value": probability,
        }
    return rows, bundles, opportunities, fallbacks


def evaluator_outcomes(opportunities):
    raw = json.loads((MATRIX / "evaluator/OUTCOMES.json").read_text())
    records = {r["opportunity_id"]: r for r in raw}
    return [
        {
            "opportunity_id": o.opportunity_id,
            "target_contract_hash": o.target.contract_hash,
            "value": records[o.opportunity_id]["outcome"],
            "status": "mature"
            if records[o.opportunity_id]["status"] == "settled_final_archived_report"
            else "missing",
            "source_revision": fingerprint(records[o.opportunity_id]),
        }
        for o in opportunities
    ]


def main(out):
    out.mkdir(exist_ok=False, parents=True)
    rows, bundles, opportunities, fallbacks = mission_inputs()
    predictor = FrozenFrequencyPredictor(json.loads((MATRIX / "BANK.json").read_text()))
    arms, committed, receipts = {}, [], []
    for condition in ("follow", "common_only", "fixed_one", "all_registered"):
        path = out / (condition + ".jsonl")
        arms[condition] = path
        selected = [
            r
            for r in rows
            if r["condition"] == ("common_only" if condition == "follow" else condition)
        ]
        events = []
        for item in selected:
            bundle = bundles[item["call_id"]]
            p = bundle.policy_view()
            call_id = item["call_id"]
            events.append(
                AdmissionEvent(
                    call_id + "-base",
                    p["baseline"]["available_at"],
                    "baseline",
                    {"bundle": bundle.to_dict()},
                )
            )
            if condition == "follow":
                continue
            started = p["cutoff"] - 60_000_000
            if (
                max(
                    [p["baseline"]["available_at"]]
                    + [a["completed_at"] for a in p["assets"]]
                )
                > started
            ):
                raise ValueError("Selected input not available at frozen logical start")
            events.append(
                AdmissionEvent(
                    call_id + "-begin",
                    started,
                    "begin",
                    {
                        "call_id": call_id,
                        "bundle": bundle.to_dict(),
                        "head": "program",
                        "executor": "frozen_frequency.v1",
                    },
                )
            )
            wall_start, start = time.time_ns(), time.monotonic_ns()
            forecast = predictor.predict(bundle)
            completed = max(1, math.ceil((time.monotonic_ns() - start) / 1000))
            raw = canonical(forecast.to_dict())
            response_file = out / (condition + "-" + call_id + "-response.json")
            save(
                response_file,
                {
                    "raw": raw,
                    "wall_started_ns": wall_start,
                    "bundle_hash": bundle.bundle_hash,
                },
            )
            persisted = max(completed, math.ceil((time.monotonic_ns() - start) / 1000))
            receipt = {
                "call_id": call_id,
                "bundle_hash": bundle.bundle_hash,
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "started_at": started,
                "completed_at": started + completed,
                "persisted_at": started + persisted,
                "expires_at": p["cutoff"],
                "cost": {
                    "requests": 0,
                    "bytes": len(raw.encode()),
                    "tokens": 0,
                    "compute_ms": math.ceil(completed / 1000),
                },
                "ended_with_eos": True,
                "head": "program",
                "executor": "frozen_frequency.v1",
            }
            receipts.append(
                {
                    "condition": condition,
                    "receipt": receipt,
                    "wall_started_ns": wall_start,
                    "measured_through_fsync_us": persisted,
                }
            )
            events.append(
                AdmissionEvent(
                    call_id + "-completion",
                    receipt["persisted_at"],
                    "completion",
                    receipt,
                )
            )
        with EventJournal(path) as journal:
            engine = AdmissionEngine(
                opportunities, fallbacks=fallbacks, journal=journal
            )
            engine.run(events, until=max(o.cutoff for o in opportunities))
        reconstructed = AdmissionEngine.from_journal(path)
        if (
            reconstructed.snapshots != engine.snapshots
            or reconstructed.attempts != engine.attempts
        ):
            raise ValueError("Independent durable replay mismatch")
        committed.extend({"arm": condition, **r} for r in engine.snapshots.values())
    outcomes = evaluator_outcomes(opportunities)
    save(out / "OUTCOME_REFERENCES.json", outcomes)
    report = score_admitted(outcomes, arms)
    report.update(
        {
            "purpose": "real archived native reports, measured CPU inference; archive timing scenario",
            "real_model_calls": 0,
            "base_opportunities": len(opportunities),
            "program_calls": len(receipts),
            "all_journals_reconstructed": True,
            "new_independent_weather_processes": 0,
            "online_qualification": False,
        }
    )
    save(out / "ADMISSION_REPORT.json", report)
    save(out / "PROGRAM_RECEIPTS.json", receipts)
    with (out / "COMMITTED_FORECASTS.jsonl").open("x") as f:
        for r in committed:
            f.write(canonical(r) + "\n")
    print(
        json.dumps(
            {
                "output": str(out),
                "opportunities": len(opportunities),
                "program_calls": len(receipts),
                "scores": report["scores"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
