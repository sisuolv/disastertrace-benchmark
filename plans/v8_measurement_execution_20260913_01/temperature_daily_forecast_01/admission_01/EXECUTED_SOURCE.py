"""Register all candidate outcomes and replay monthly typed admission units."""

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
)
from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
ROOT = HERE / "temperature_daily_forecast_01"
OUT = ROOT / "admission_01"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def us(value):
    return round(dt.datetime.fromisoformat(value).timestamp() * 1_000_000)


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    audit = read(ROOT / "independent_audit_01/VALIDATION.json")
    assert audit["passed"]
    for name, digest in audit["analysis_files"].items():
        assert sha(ROOT / "analysis_01" / name) == digest
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    package = REPO / "disastertrace-starter/src/disastertrace"
    for name in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            package / name,
            OUT / "source/disastertrace" / name,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    save(
        "PROTOCOL.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": {
                str(path.relative_to(OUT)): sha(path)
                for path in (OUT / "source").rglob("*.py")
            },
            "candidate_audit_sha256": sha(
                ROOT / "independent_audit_01/VALIDATION.json"
            ),
            "selection": "First initialization in each month,day1for3daily events andstart-day1for2three-day events;all outcomes retained.",
            "arms": ["follow", "same_value_override"],
            "protocols": ["base_bound_override", "persistent_override"],
            "time_basis": "declared1ms program computation and1ms persistence;init+3havailability/init+4hcutoff",
            "purpose": "Typed daily/duration target,outcome identity,same-value admission and replay;not adaptive acquisition or an efficacy comparison.",
            "baseline": "Derived raw51member fraction from professional-source extrema, research mapping, uncalibrated.",
            "initial_fallback": "0.5engineering-only;common forecast arrives before every cutoff",
            "new_model_calls": 0,
            "new_source_queries": 0,
        },
    )
    daily = read(ROOT / "analysis_01/DAILY_FORECASTS.json")
    durations = read(ROOT / "analysis_01/DURATION_FORECASTS.json")
    first_month = {}
    for row in daily:
        first_month.setdefault(row["initialization"][:7], row["initialization_index"])
    selected_inits = set(first_month.values())
    references = {
        row["date"]: row
        for row in read(
            HERE
            / "temperature_daily_reference_01/qualification_01/DAILY_REFERENCES.json"
        )
    }
    cases = []

    def add(row, event, dates, probability, variable, operator, threshold, visible):
        start, end = (
            us(dates[0] + "T00:00:00+00:00"),
            us(dates[-1] + "T00:00:00+00:00") + 86_400_000_000,
        )
        target = Target(
            "DWD460-" + dates[0] + "-" + event,
            "DWD:460:Berus",
            variable,
            "C",
            "event_probability",
            "interval",
            start,
            end,
            "future_physical",
            "DWD_TXK_TNK_UTC.v1:" + event,
            operator,
            threshold,
        )
        oid = target.target_id + "-init-" + row["initialization"]
        opportunity = TypedOpportunity(oid, target, us(row["cutoff"]))
        refrows = [references.get(date) for date in dates]
        event_key = (
            "hot_day"
            if event == "fixed_threshold_hot_spell_3d"
            else "ice_day"
            if event == "fixed_threshold_ice_spell_3d"
            else event
        )
        value = (
            int(all(r["daily_predicates"][event_key] for r in refrows))
            if all(r is not None for r in refrows)
            else None
        )
        selected = (
            row["initialization_index"] in selected_inits
            and row.get("day_index", row.get("start_day_index")) == 1
        )
        cases.append(
            {
                "opportunity": opportunity,
                "origin": us(row["initialization"]),
                "p": probability,
                "visible": visible,
                "value": value,
                "reference_rows": refrows,
                "event": event,
                "selected": selected,
            }
        )

    for row in daily:
        for event, variable, op, threshold in (
            ("hot_day", "daily_max_2m_temperature", "ge", 30),
            ("frost_day", "daily_min_2m_temperature", "lt", 0),
            ("ice_day", "daily_max_2m_temperature", "lt", 0),
        ):
            add(
                row,
                event,
                [row["target_date"]],
                row["probabilities"][event],
                variable,
                op,
                threshold,
                {
                    "forecast_max_members_C": row["forecast_max_members_C"],
                    "forecast_min_members_C": row["forecast_min_members_C"],
                    "mapping": event,
                },
            )
    indexed = {(row["initialization_index"], row["day_index"]): row for row in daily}
    for row in durations:
        hot = row["event"] == "fixed_threshold_hot_spell_3d"
        add(
            row,
            row["event"],
            row["target_dates"],
            row["probability"],
            "min_of_3_daily_max_2m_temperature"
            if hot
            else "max_of_3_daily_max_2m_temperature",
            "ge" if hot else "lt",
            30 if hot else 0,
            {
                "daily_max_members_C": [
                    indexed[(row["initialization_index"], row["start_day_index"] + j)][
                        "forecast_max_members_C"
                    ]
                    for j in range(3)
                ],
                "mapping": row["event"],
            },
        )
    registry = OutcomeRegistry([case["opportunity"].target for case in cases])
    archive_sha = read(
        HERE / "temperature_daily_reference_01/qualification_01/VALIDATION.json"
    )["archive_sha256"]
    resolved = round(dt.datetime.now(dt.timezone.utc).timestamp() * 1_000_000)
    version = "DWD_daily_20260913.v1"
    for case in cases:
        target = case["opportunity"].target
        registry.register(
            {
                "target_contract_hash": target.contract_hash,
                "resolution_version": version,
                "value": case["value"],
                "status": "mature" if case["value"] is not None else "missing",
                "source_revision": fingerprint(case["reference_rows"]),
                "source_sha256": archive_sha,
                "physical_start": target.physical_start,
                "physical_end": target.physical_end,
                "units": "C",
                "quality_status": "native_QN_4:9"
                if case["value"] is not None
                else "outside_declared_reference_period",
                "observed_at": None,
                "published_at": None,
                "fetched_at": None,
                "resolved_at": resolved,
                "availability_basis": "declared_archive_scenario",
                "reference_kind": "native_DWD_daily_product_predicate",
                "references": case["reference_rows"],
            }
        )
    opportunities = [case["opportunity"] for case in cases]
    outcome_rows = registry.opportunity_rows(
        opportunities, {o.opportunity_id: version for o in opportunities}
    )
    save("OUTCOME_REGISTRY.json", registry.export())
    save("OUTCOME_REFERENCES.json", outcome_rows)
    results, statuses = [], Counter()
    for case in cases:
        if not case["selected"]:
            continue
        opportunity, origin = case["opportunity"], case["origin"]
        oid, target, cutoff = (
            opportunity.opportunity_id,
            opportunity.target,
            opportunity.cutoff,
        )
        forecast = Forecast(
            target.contract_hash, "event_probability", "probability", case["p"]
        )
        for protocol in ("base_bound_override", "persistent_override"):
            bundle = EvidenceBundle.freeze(
                {
                    "schema": "disastertrace.frozen_evidence.v1",
                    "opportunity_id": oid,
                    "target": target.to_dict(),
                    "cutoff": cutoff,
                    "baseline": {
                        "forecast": forecast.to_dict(),
                        "source_revision": oid,
                        "issued_at": origin,
                        "available_at": origin + 3 * 3600_000_000,
                        "valid_until": target.physical_start,
                        "kind": "research",
                        "mapping_version": "raw51_native_extrema_fraction.v1",
                        "content": case["visible"],
                    },
                    "state": {
                        "forecast": forecast.to_dict(),
                        "mode": "FOLLOW",
                        "protocol": protocol,
                    },
                    "assets": [],
                    "receipts": [],
                    "authorization_mode": "target_private",
                    "representation": "native_extrema_member_projection",
                    "availability_basis": "declared_archive_scenario",
                    "provider_version": "eupp_daily_extrema_candidate.v1",
                }
            )
            events = [
                AdmissionEvent(
                    "base",
                    origin + 3 * 3600_000_000,
                    "baseline",
                    {"bundle": bundle.to_dict()},
                )
            ]
            for arm in ("follow", "same_value_override"):
                engine = AdmissionEngine(
                    [opportunity],
                    protocol=protocol,
                    fallbacks={
                        target.target_id: Forecast(
                            target.contract_hash,
                            "event_probability",
                            "probability",
                            0.5,
                        ).to_dict()
                    },
                )
                actual = list(events)
                if arm == "same_value_override":
                    dispatch, raw = cutoff - 60_000_000, canonical(forecast.to_dict())
                    actual += [
                        AdmissionEvent(
                            "begin",
                            dispatch,
                            "begin",
                            {
                                "call_id": "program",
                                "bundle": bundle.to_dict(),
                                "head": "program",
                                "executor": "raw51_fraction",
                            },
                        ),
                        AdmissionEvent(
                            "complete",
                            dispatch + 2000,
                            "completion",
                            {
                                "call_id": "program",
                                "bundle_hash": bundle.bundle_hash,
                                "raw": raw,
                                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                                "started_at": dispatch,
                                "completed_at": dispatch + 1000,
                                "persisted_at": dispatch + 2000,
                                "expires_at": cutoff,
                                "cost": {
                                    "requests": 0,
                                    "bytes": len(raw),
                                    "tokens": 0,
                                    "compute_ms": 1,
                                },
                                "ended_with_eos": True,
                                "head": "program",
                                "executor": "raw51_fraction",
                            },
                        ),
                    ]
                engine.run(actual, until=cutoff)
                snapshot = engine.snapshots[oid]
                assert snapshot["forecast"] == forecast.to_dict()
                assert snapshot["mode"] == ("FOLLOW" if arm == "follow" else "OVERRIDE")
                envelope = engine.export()
                assert (
                    AdmissionEngine.restore(json.loads(canonical(envelope))).export()
                    == envelope
                )
                statuses.update(item["status"] for item in engine.attempts)
                results.append(
                    {
                        "opportunity_id": oid,
                        "event": case["event"],
                        "arm": arm,
                        "protocol": protocol,
                        "mode": snapshot["mode"],
                        "forecast": snapshot["forecast"],
                        "engine_sha256": fingerprint(envelope),
                        "exact_restore": True,
                    }
                )
                if len(results) == 1:
                    save("FIRST_UNIT_ENVELOPE.json", envelope)
    save("REPLAY_RESULTS.json", results)
    save(
        "VALIDATION.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "passed": True,
            "registered_opportunities": len(cases),
            "canonical_unique_targets": len(registry.records),
            "outcome_statuses": dict(Counter(r["status"] for r in outcome_rows)),
            "selected_monthly_opportunities": sum(case["selected"] for case in cases),
            "engine_units": len(results),
            "attempt_statuses": dict(statuses),
            "all_snapshots_restore_exactly": True,
            "same_value_overrides_retain_identity": True,
            "new_model_calls": 0,
            "new_source_queries": 0,
            "new_source_requests": 0,
            "shared_budget_adaptive": False,
            "independent_confirmation": False,
            "full_professional_product_context_comparison": False,
            "scope": "Typed snapshot admission/replay on monthly native-data examples. Target-specific native member projections;not a continuous source/selector/predictor session or C1 evidence-sharing experiment.",
        },
    )
    print(
        json.dumps(
            {
                "registered_opportunities": len(cases),
                "targets": len(registry.records),
                "engine_units": len(results),
                "passed": True,
            }
        )
    )


if __name__ == "__main__":
    main()
