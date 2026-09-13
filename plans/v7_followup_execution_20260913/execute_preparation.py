"""Synthetic D scenarios on the typed admission clock; no real-weather claim."""

import argparse
import hashlib
import json
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
)
from disastertrace.monitoring_v1.journal import EventJournal
from disastertrace.monitoring_v1.preparation import one_step_prepare, score_preparation
from execute_admission import save


def main(out):
    out.mkdir(exist_ok=False, parents=True)
    targets = [
        Target(
            t,
            "synthetic:" + t,
            "demand",
            "count",
            "event_probability",
            "point",
            100,
            100,
            "future_physical",
            "synthetic_demand.v1",
            "ge",
            1,
        )
        for t in ("t", "u")
    ]
    opportunities = [
        TypedOpportunity("early", targets[0], 70),
        TypedOpportunity("late", targets[0], 90),
        TypedOpportunity("u", targets[1], 90),
    ]
    fallbacks = {
        t.target_id: Forecast(
            t.contract_hash, "event_probability", "probability", 0.4
        ).to_dict()
        for t in targets
    }
    card = {
        "schema": "disastertrace.preparation_scenario.v1",
        "kind": "research_assumption",
        "capacity": 1,
        "budget": 20,
        "units": "synthetic_cost_units",
        "jobs": [
            {
                "job_id": "j1",
                "target_id": "t",
                "deadline": 95,
                "duration": 10,
                "expires_at": 98,
                "cost": 3,
                "cleanup_duration": 5,
                "cleanup_cost": 1,
            },
            {
                "job_id": "j2",
                "target_id": "u",
                "deadline": 96,
                "duration": 8,
                "expires_at": 97,
                "cost": 2,
                "cleanup_duration": 3,
                "cleanup_cost": 1,
            },
        ],
    }
    b = EvidenceBundle.freeze(
        {
            "schema": "disastertrace.frozen_evidence.v1",
            "opportunity_id": "late",
            "target": targets[0].to_dict(),
            "cutoff": 90,
            "baseline": {
                "forecast": fallbacks["t"],
                "source_revision": "synthetic-1",
                "issued_at": 40,
                "available_at": 50,
                "valid_until": 100,
                "kind": "research",
                "mapping_version": "synthetic.v1",
                "content": {"description": "synthetic protocol fixture"},
            },
            "state": {
                "forecast": fallbacks["t"],
                "mode": "FOLLOW",
                "protocol": "base_bound_override",
            },
            "assets": [],
            "receipts": [],
            "authorization_mode": "target_private",
            "representation": "synthetic",
            "availability_basis": "declared_archive_scenario",
            "provider_version": "synthetic.v1",
        }
    )
    raw = canonical(
        Forecast(
            targets[0].contract_hash, "event_probability", "probability", 0.6
        ).to_dict()
    )
    baseline_events = [
        AdmissionEvent("base", 50, "baseline", {"bundle": b.to_dict()}),
        AdmissionEvent(
            "begin",
            60,
            "begin",
            {
                "call_id": "c",
                "bundle": b.to_dict(),
                "head": "program",
                "executor": "synthetic.v1",
            },
        ),
        AdmissionEvent(
            "complete",
            90,
            "completion",
            {
                "call_id": "c",
                "bundle_hash": b.bundle_hash,
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "started_at": 60,
                "completed_at": 89,
                "persisted_at": 90,
                "expires_at": 92,
                "cost": {
                    "requests": 0,
                    "bytes": len(raw),
                    "tokens": 0,
                    "compute_ms": 1,
                },
                "ended_with_eos": True,
                "head": "program",
                "executor": "synthetic.v1",
            },
        ),
        AdmissionEvent("follow", 91, "follow", {"target_id": "t"}),
    ]
    cases = {
        "deadline_and_inflight": [(85, "prepare", "j1")],
        "cancel_and_cleanup": [
            (60, "prepare", "j1"),
            (65, "cancel_preparation", "j1"),
            (66, "prepare", "j2"),
            (70, "prepare", "j2"),
        ],
        "expired": [(60, "prepare", "j1"), (65, "prepare", "j1")],
        "budget": [(60, "prepare", "j1"), (94, "prepare", "j2")],
    }
    save(
        out / "SCENARIO.json",
        {
            "card": card,
            "cases": cases,
            "outcomes": {"j1": 1, "j2": 1},
            "miss_penalty": 10,
        },
    )
    reports = {}
    for name, actions in cases.items():
        scenario = json.loads(json.dumps(card))
        if name == "expired":
            scenario["jobs"][0]["expires_at"] = 80
        if name == "budget":
            scenario["budget"] = 3
        path = out / (name + ".jsonl")
        with EventJournal(path) as journal:
            engine = AdmissionEngine(
                opportunities,
                fallbacks=fallbacks,
                preparation=scenario,
                journal=journal,
            )
            events = baseline_events + [
                AdmissionEvent("D-" + str(i), at, kind, {"job_id": job})
                for i, (at, kind, job) in enumerate(actions)
            ]
            engine.run(events, until=99)
        replay = AdmissionEngine.from_journal(path)
        if (
            replay.preparation.to_dict() != engine.preparation.to_dict()
            or replay.snapshots != engine.snapshots
        ):
            raise ValueError("D/F same-clock replay mismatch")
        reports[name] = {
            "preparation": replay.preparation.to_dict(),
            "score": score_preparation(
                replay.preparation, {"j1": 1, "j2": 1}, miss_penalty=10
            ),
            "F_opportunities": len(engine.snapshots),
            "unique_D_jobs": len(engine.preparation.snapshots),
        }
    result = {
        "scope": "synthetic_protocol_only",
        "cases": reports,
        "same_clock_replay_verified": True,
        "analytic_boundary": {
            "at_equal": one_step_prepare(0.6, 3, 5),
            "above": one_step_prepare(0.61, 3, 5),
        },
        "actual_model_calls": 0,
        "actual_weather_outcomes": 0,
        "real_decision_benefit_claim": False,
    }
    save(out / "PREPARATION_SYNTHETIC_REPORT.json", result)
    print(
        json.dumps(
            {
                "cases": len(reports),
                "scores": {k: r["score"]["total_cost"] for k, r in reports.items()},
                "same_clock_replay_verified": True,
                "scope": result["scope"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
