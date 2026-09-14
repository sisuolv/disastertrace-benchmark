"""Canonical scalar results for the full calendar and monthly native replay units."""

import datetime as dt
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    TypedOpportunity,
)
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Forecast,
    Target,
    canonical,
    fingerprint,
    paired_scores,
)
from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
ROOT = HERE / "temperature_extension_01"
DATA = ROOT / "decoded_01"
OUT = ROOT / "admission_01"


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def us(value):
    return round(dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1_000_000)


def target_of(row):
    at = us(row["valid_time"])
    return Target(
        "DWD460-" + row["valid_time"],
        "DWD:460:Berus",
        "2m_temperature",
        "K",
        "scalar",
        "point",
        at,
        at,
        "future_physical",
        "DWD_TT_TU_instant_UTC.v1",
    )


def main():
    validation = load(DATA / "VALIDATION.json")
    if not validation["passed"]:
        raise ValueError("Native coordinate and unit verification failed")
    for name, sha in validation["output_files"].items():
        if digest(DATA / name) != sha:
            raise ValueError("Decoded artifact changed")
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(__file__, OUT / "scorer.py")
    package = REPO / "disastertrace-starter/src/disastertrace"
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            package / module,
            OUT / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    save(
        OUT / "PROTOCOL.json",
        {
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "decoded_validation_sha256": digest(DATA / "VALIDATION.json"),
            "replay_selection_sha256": digest(DATA / "REPLAY_SELECTION.json"),
            "source": {str(p.relative_to(OUT)): digest(p) for p in (OUT / "source").rglob("*.py")},
            "processing": "declared 1ms computation plus 1ms persistence; program scalar controls only",
            "baseline": "full 51-member arithmetic mean; missing ensembles explicitly unqualified",
            "initial_fallback": "273.15K engineering initialization; never reported as a professional baseline",
            "admission_unit": "independent snapshot per opportunity, not adaptive acquisition",
            "replay_selection": "first source initialization each calendar month, all positive leads",
            "canonical_registry_scope": "all 14600 future opportunities, shared target labels across all initialization/lead pairs",
        },
    )
    records = [json.loads(line) for line in (DATA / "RECORDS.jsonl").read_text().splitlines()]
    rows = [r for r in records if r["future_eligible"]]
    typed = [
        TypedOpportunity(
            r["record_id"], target_of(r), us(r["forecast_reference_time"]) + 4 * 3600_000_000
        )
        for r in rows
    ]
    registry = OutcomeRegistry([o.target for o in typed])
    refs = [
        json.loads(line)
        for line in (REPO / "plans/v7_execution_20260913/sources_numerical/REQUESTS.jsonl")
        .read_text()
        .splitlines()
    ]
    acquired = next(
        r
        for r in refs
        if r.get("name") == "dwd_berus_hourly_temperature.zip" and r.get("status") == 200
    )
    fetched = us(acquired["finished_utc"])
    resolved = round(dt.datetime.now(dt.timezone.utc).timestamp() * 1_000_000)
    for r, opportunity in zip(rows, typed):
        target, native = opportunity.target, r["evaluator_only"]
        registry.register(
            {
                "target_contract_hash": target.contract_hash,
                "resolution_version": "DWD_native_20260913.v1",
                "value": native["dwd_K"],
                "status": "mature" if native["dwd_K"] is not None else "missing",
                "source_revision": fingerprint(native["native_row"]),
                "source_sha256": acquired["sha256"],
                "physical_start": target.physical_start,
                "physical_end": target.physical_end,
                "units": "K",
                "quality_status": "native_QN_9:" + str(native["QN_9"]),
                "observed_at": target.physical_start,
                "published_at": None,
                "fetched_at": fetched,
                "resolved_at": resolved,
                "availability_basis": "declared_archive_scenario",
                "reference_kind": "native_DWD_hourly_report",
                "references": [{"source": "DWD", "record": native["native_row"]}],
            }
        )
    outcomes = registry.opportunity_rows(
        typed, {o.opportunity_id: "DWD_native_20260913.v1" for o in typed}
    )
    save(OUT / "OUTCOME_REGISTRY.json", registry.export())
    save(OUT / "OUTCOME_REFERENCES.json", outcomes)
    by_id = {r["opportunity_id"]: r for r in outcomes}
    selection = set(load(DATA / "REPLAY_SELECTION.json")["opportunity_ids"])
    summary = {
        "selected_opportunities": len(selection),
        "replayed_units": 0,
        "skipped_missing_forecast": [],
        "status_counts": Counter(),
    }
    selected_rows, predictions = [], {"follow": {}, "mean": {}, "median": {}}
    with (OUT / "UNIT_REPLAYS.jsonl").open("x") as handle:
        for r, opportunity in zip(rows, typed):
            oid, target = r["record_id"], opportunity.target
            if oid not in selection:
                continue
            if not r["forecast_complete"]:
                summary["skipped_missing_forecast"].append(oid)
                continue
            base = Forecast(target.contract_hash, "scalar", "K", r["predictions"]["mean"])
            fallback = Forecast(target.contract_hash, "scalar", "K", 273.15)
            origin, cutoff = us(r["forecast_reference_time"]), opportunity.cutoff
            bundle = EvidenceBundle.freeze(
                {
                    "schema": "disastertrace.frozen_evidence.v1",
                    "opportunity_id": oid,
                    "target": target.to_dict(),
                    "cutoff": cutoff,
                    "baseline": {
                        "forecast": base.to_dict(),
                        "source_revision": oid,
                        "issued_at": origin,
                        "available_at": origin + 3 * 3600_000_000,
                        "valid_until": target.physical_start,
                        "kind": "research",
                        "mapping_version": "51member_mean.v1",
                        "content": r["model_visible"],
                    },
                    "state": {
                        "forecast": base.to_dict(),
                        "mode": "FOLLOW",
                        "protocol": "base_bound_override",
                    },
                    "assets": [],
                    "receipts": [],
                    "authorization_mode": "target_private",
                    "representation": "native_ensemble",
                    "availability_basis": "declared_archive_scenario",
                    "provider_version": "eupp_dwd_full_calendar.v1",
                }
            )
            events = [
                AdmissionEvent(
                    "base", origin + 3 * 3600_000_000, "baseline", {"bundle": bundle.to_dict()}
                )
            ]
            predictions["follow"][oid] = base.to_dict()
            selected_rows.append(
                {
                    "opportunity_id": oid,
                    "target": target.to_dict(),
                    "outcome": by_id[oid]["value"] if by_id[oid]["status"] == "mature" else None,
                }
            )
            for arm in ("mean", "median"):
                candidate = Forecast(target.contract_hash, "scalar", "K", r["predictions"][arm])
                raw = canonical(candidate.to_dict())
                dispatch = cutoff - 60_000_000
                complete = {
                    "call_id": "program",
                    "bundle_hash": bundle.bundle_hash,
                    "raw": raw,
                    "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "started_at": dispatch,
                    "completed_at": dispatch + 1000,
                    "persisted_at": dispatch + 2000,
                    "expires_at": cutoff,
                    "cost": {"requests": 0, "bytes": len(raw), "tokens": 0, "compute_ms": 1},
                    "ended_with_eos": True,
                    "head": "program",
                    "executor": "51member_" + arm,
                }
                all_events = [
                    *events,
                    AdmissionEvent(
                        "begin",
                        dispatch,
                        "begin",
                        {
                            "call_id": "program",
                            "bundle": bundle.to_dict(),
                            "head": "program",
                            "executor": "51member_" + arm,
                        },
                    ),
                    AdmissionEvent("complete", dispatch + 2000, "completion", complete),
                ]
                engine = AdmissionEngine(
                    [opportunity], fallbacks={target.target_id: fallback.to_dict()}
                )
                engine.run(all_events, until=cutoff)
                snapshot = engine.snapshots[oid]
                if snapshot["mode"] != "OVERRIDE" or snapshot["forecast"] != candidate.to_dict():
                    raise ValueError(
                        "Scalar candidate failed admission or equal-value mean lost OVERRIDE identity"
                    )
                envelope = engine.export()
                if AdmissionEngine.restore(json.loads(canonical(envelope))).export() != envelope:
                    raise ValueError("Scalar native unit does not replay exactly")
                summary["replayed_units"] += 1
                summary["status_counts"].update(a["status"] for a in engine.attempts)
                predictions[arm][oid] = snapshot["forecast"]
                handle.write(
                    canonical({"opportunity_id": oid, "arm": arm, "engine": envelope}) + "\n"
                )
    scores = paired_scores(selected_rows, predictions)
    native_report = load(DATA / "REPORT.json")
    report = {
        "schema": "disastertrace.temperature_scalar_admission.v1",
        "canonical_opportunities": len(rows),
        "canonical_unique_targets": len(registry.records),
        "replay": summary,
        "replay_scores": scores,
        "full_calendar_direct_scores": native_report["all_future"],
        "model_calls": 0,
        "historical_publication_proved": False,
        "shared_budget_adaptive": False,
        "heatwave_coldwave_qualified": False,
        "independent_confirmation": False,
    }
    save(OUT / "REPORT.json", report)
    save(
        OUT / "VALIDATION.json",
        {
            "passed": True,
            "canonical_targets": len(registry.records),
            "opportunity_outcomes": len(outcomes),
            "full_universe_registry_verified": True,
            "selected_replay_units": summary["replayed_units"],
            "all_selected_snapshots_replay_exactly": True,
            "equal_probability_or_scalar_not_follow": True,
            "model_calls": 0,
            "files": {p.name: digest(p) for p in OUT.iterdir() if p.is_file()},
        },
    )
    print(
        json.dumps(
            {
                "canonical_opportunities": len(rows),
                "targets": len(registry.records),
                "replay": summary,
                "replay_scores": scores,
            }
        )
    )


if __name__ == "__main__":
    main()
