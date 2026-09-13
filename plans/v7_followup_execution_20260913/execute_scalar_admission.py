"""EUPP/DWD scalars under an explicit archive latency scenario, not online proof."""

import argparse
import hashlib
import json
import math
import statistics
import time
from datetime import datetime
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    TypedOpportunity,
    score_admitted,
)
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Forecast,
    Target,
    canonical,
    fingerprint,
)
from disastertrace.monitoring_v1.journal import EventJournal
from execute_admission import ROOT, save


def us(value):
    return round(
        datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1_000_000
    )


def main(out):
    out.mkdir(exist_ok=False, parents=True)
    source = ROOT / "plans/v7_execution_20260913/sources_numerical/paired_records.json"
    records = json.loads(source.read_text())["records"]
    save(
        out / "SCENARIO.json",
        {
            "selection": "all prequalified positive-lead records; no outcome filter",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "publication_assumption": "initialization plus 3h, declared archive scenario only",
            "cutoff_assumption": "initialization plus 4h, invocation 60s before cutoff",
            "fallback": "fixed 273.15 K for engine initialization, no empirical weather fitting",
            "baseline": "ensemble mean of all 51 members",
            "candidate": "ensemble mean or median",
            "historical_publication_proved": False,
            "scope": "native scalar engineering, not heatwave/cold-wave C1/C2",
        },
    )
    opportunities, fallbacks, bundles, outcomes, exclusions = [], {}, {}, [], []
    for r in records:
        if r["lead_hours"] <= 0:
            exclusions.append(r["record_id"])
            continue
        if not r["point_forecast_diagnostic_eligible"]:
            raise ValueError("Source scalar semantics not prequalified")
        origin, valid = us(r["forecast_reference_time"]), us(r["valid_time"])
        available, cutoff = origin + 3 * 3_600_000_000, origin + 4 * 3_600_000_000
        if cutoff >= valid or valid - origin != r["lead_hours"] * 3_600_000_000:
            raise ValueError("Positive lead does not satisfy declared scenario")
        target = Target(
            "dwd-460-" + r["valid_time"],
            "DWD:460:Berus",
            r["variable"],
            "K",
            "scalar",
            "point",
            valid,
            valid,
            "future_physical",
            "DWD_TT_TU_instant_UTC.v1",
        )
        members = r["model_visible"]["forecast_members"]
        if len(members) != 51 or len(set(r["model_visible"]["member_ids"])) != 51:
            raise ValueError("Incomplete ensemble")
        base = Forecast(
            target.contract_hash, "scalar", "K", statistics.mean(members)
        ).to_dict()
        fallbacks[target.target_id] = Forecast(
            target.contract_hash, "scalar", "K", 273.15
        ).to_dict()
        oid = r["record_id"]
        opportunities.append(TypedOpportunity(oid, target, cutoff))
        bundles[oid] = EvidenceBundle.freeze(
            {
                "schema": "disastertrace.frozen_evidence.v1",
                "opportunity_id": oid,
                "target": target.to_dict(),
                "cutoff": cutoff,
                "baseline": {
                    "forecast": base,
                    "source_revision": oid,
                    "issued_at": origin,
                    "available_at": available,
                    "valid_until": valid,
                    "kind": "research",
                    "mapping_version": "51member_mean.v1",
                    "content": {
                        "members_K": members,
                        "member_ids": r["model_visible"]["member_ids"],
                        "native_forecast_initialization": origin,
                    },
                },
                "state": {
                    "forecast": base,
                    "mode": "FOLLOW",
                    "protocol": "base_bound_override",
                },
                "assets": [],
                "receipts": [],
                "authorization_mode": "target_private",
                "representation": "native_ensemble",
                "availability_basis": "declared_archive_scenario",
                "provider_version": "eupp_dwd_scalar_scenario.v1",
            }
        )
        outcomes.append(
            {
                "opportunity_id": oid,
                "target_contract_hash": target.contract_hash,
                "value": r["evaluator_only"]["observation"],
                "status": "mature",
                "source_revision": fingerprint(r["evaluator_only"]),
            }
        )
    paths, observations = {}, {r["opportunity_id"]: r["value"] for r in outcomes}
    direct = {}
    for arm, reducer in [
        ("ensemble_mean", statistics.mean),
        ("ensemble_median", statistics.median),
    ]:
        path = out / (arm + ".jsonl")
        paths[arm] = path
        events, losses = [], []
        for oid, bundle in bundles.items():
            row = bundle.policy_view()
            target = Target(**row["target"])
            events.append(
                AdmissionEvent(
                    oid + "-base",
                    row["baseline"]["available_at"],
                    "baseline",
                    {"bundle": bundle.to_dict()},
                )
            )
            start = row["cutoff"] - 60_000_000
            events.append(
                AdmissionEvent(
                    oid + "-begin",
                    start,
                    "begin",
                    {
                        "call_id": oid,
                        "bundle": bundle.to_dict(),
                        "head": "program",
                        "executor": arm + ".v1",
                    },
                )
            )
            tick = time.monotonic_ns()
            forecast = Forecast(
                target.contract_hash,
                "scalar",
                "K",
                reducer(row["baseline"]["content"]["members_K"]),
            )
            duration = max(1, math.ceil((time.monotonic_ns() - tick) / 1000))
            raw = canonical(forecast.to_dict())
            save(
                out / (arm + "-" + oid + "-response.json"),
                {"raw": raw, "bundle_hash": bundle.bundle_hash},
            )
            persisted = max(duration, math.ceil((time.monotonic_ns() - tick) / 1000))
            events.append(
                AdmissionEvent(
                    oid + "-completion",
                    start + persisted,
                    "completion",
                    {
                        "call_id": oid,
                        "bundle_hash": bundle.bundle_hash,
                        "raw": raw,
                        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                        "started_at": start,
                        "completed_at": start + duration,
                        "persisted_at": start + persisted,
                        "expires_at": row["cutoff"],
                        "cost": {
                            "requests": 0,
                            "bytes": len(raw),
                            "tokens": 0,
                            "compute_ms": math.ceil(duration / 1000),
                        },
                        "ended_with_eos": True,
                        "head": "program",
                        "executor": arm + ".v1",
                    },
                )
            )
            losses.append(abs((forecast.value - 273.15) - (observations[oid] - 273.15)))
        with EventJournal(path) as journal:
            engine = AdmissionEngine(
                opportunities, fallbacks=fallbacks, journal=journal
            )
            engine.run(events, until=max(o.cutoff for o in opportunities))
        if any(r["status"] != "accepted" for r in engine.attempts):
            raise ValueError("Scalar candidate failed admission")
        direct[arm] = sum(losses) / len(losses)
    save(out / "OUTCOME_REFERENCES.json", outcomes)
    report = score_admitted(outcomes, paths)
    for arm, value in direct.items():
        if abs(report["scores"]["arms"][arm]["mean_loss"] - value) > 1e-12:
            raise ValueError(
                "Admitted scalar MAE differs from direct Celsius crosscheck"
            )
    report.update(
        source_records=len(records),
        admitted_opportunities=len(opportunities),
        unique_valid_targets=len(fallbacks),
        excluded_zero_leads=exclusions,
        measured_CPU_predictions=2 * len(opportunities),
        direct_Celsius_MAE=direct,
        actual_model_calls=0,
        historical_publication_proved=False,
        active_shared_evidence_qualified=False,
        heatwave_coldwave_task=False,
    )
    save(out / "SCALAR_ADMISSION_REPORT.json", report)
    print(
        json.dumps(
            {
                "opportunities": len(opportunities),
                "targets": len(fallbacks),
                "MAE": direct,
                "scope": "declared archive scenario, native scalar engineering",
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
