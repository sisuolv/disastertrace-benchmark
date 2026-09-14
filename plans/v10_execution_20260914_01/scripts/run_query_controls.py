"""Cross allocation/authorization while fixing public forecast invocation slots."""

import argparse
import datetime as dt
import os
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import (
    ComparisonContract,
    experiment_spec,
)
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from run_multicutoff import run_arm


def prepare(out):
    root = Path(__file__).resolve().parents[3]
    old = root / "plans/v9_followup_execution_20260914_01/api_pilot_01"
    out.mkdir(exist_ok=False)
    registration = {
        "registered_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "regions": ["new_york", "chicago", "denver"],
        "dates": ["2025-01-06", "2025-01-10"],
        "thresholds": [1000, 5000],
        "protocols": ["base_bound_override"],
        "request_budget": 48,
        "forecast_schedule": {
            "kind": "public_serial_slots.v1",
            "lead_seconds": 120,
            "spacing_seconds": 30,
        },
        "factorial_selector": "coverage",
        "cell_bits": {
            "first": "fixed_quota=0/global_budget=1",
            "second": "target_private=0/session_shared=1",
        },
        "scope": "exposed development program acquisition controls with identical forecast slots",
        "native_source_costs_unchanged": True,
        "confirmation_opened": False,
        "model_calls": 0,
        "interpretation": "B00..B11 identify allocation/sharing under one fixed selector; B11 policies compare selectors at equal permissions",
    }
    publish(out / "REGISTRATION.json", registration)
    variants = {
        "FOLLOW": {"acquire": False, "predict": False},
        "F_BASE_ONLY": {"acquire": False},
        "B00_COVERAGE": {
            "allocation_mode": "fixed_quota",
            "authorization_mode": "target_private",
            "selector_kind": "coverage",
        },
        "B01_COVERAGE": {
            "allocation_mode": "fixed_quota",
            "authorization_mode": "session_shared",
            "selector_kind": "coverage",
        },
        "B10_COVERAGE": {
            "allocation_mode": "global_budget",
            "authorization_mode": "target_private",
            "selector_kind": "coverage",
        },
        "B11_COVERAGE": {
            "allocation_mode": "global_budget",
            "authorization_mode": "session_shared",
            "selector_kind": "coverage",
        },
        "B11_RISK": {"selector_kind": "risk"},
        "B11_ROUND_ROBIN": {"selector_kind": "round_robin"},
        "B11_BATCH": {"selector_kind": "batch_complete"},
    }
    cases = []
    for region in registration["regions"]:
        for day in registration["dates"]:
            for threshold in registration["thresholds"]:
                name = region + "__" + day + "__" + str(threshold)
                original, case = old / name, out / name
                case.mkdir()
                data, bank = read(original / "DATA.json"), read(original / "BANK.json")
                base = read(original / "CONFIGS.json")["batch_program"]
                base.pop("execution_contract", None)
                base.update(
                    admission_semantics="measurement.v3",
                    formal_resolution_policy="h15_routine_archive.v1",
                    forecast_schedule=registration["forecast_schedule"],
                    predictor_kind="program",
                    adoption_policy={"kind": "always"},
                )
                configs, allowed, invariants = {}, defaultdict(list), None
                for arm, changes in variants.items():
                    config = bind_source(
                        bind_execution({**base, **changes}, None), None
                    )
                    configs[arm] = config
                    spec = experiment_spec(data, bank, config)
                    invariants = invariants or spec["invariants"]
                    assert spec["invariants"] == invariants
                    for key, value in spec["interventions"].items():
                        if value not in allowed[key]:
                            allowed[key].append(value)
                outcomes = [
                    {
                        **r,
                        "provider": "IEM",
                        "provider_version": "native_h15_snapshot.v1",
                    }
                    for r in read(original / "OUTCOMES.json")
                ]
                for key, value in (
                    ("DATA", data),
                    ("BANK", bank),
                    ("CONFIGS", configs),
                    ("OUTCOMES", outcomes),
                ):
                    publish(case / (key + ".json"), value)
                publish(
                    case / "COMPARISON.json",
                    ComparisonContract(invariants, allowed).export(),
                )
                cases.append(
                    {
                        "case": name,
                        "arms": list(configs),
                        "opportunities": len(data["opportunities"]),
                        "targets": len(data["targets"]),
                    }
                )
    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(
            root / "disastertrace-starter/src/disastertrace" / module,
            out / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Frozen fixed-schedule program study."""\n'
    )
    for name in ("run_query_controls.py", "run_multicutoff.py"):
        shutil.copyfile(Path(__file__).parent / name, out / "source" / name)
    publish(
        out / "PLAN.json",
        {
            "cases": cases,
            "model_calls": 0,
            "method_trajectories": sum(len(c["arms"]) for c in cases),
            "opportunities": sum(c["opportunities"] for c in cases),
            "files": {
                str(p.relative_to(out)): digest(p)
                for p in out.rglob("*")
                if p.is_file()
            },
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    out = args.out.absolute()
    if not args.execute:
        prepare(out)
        return
    publish(
        out / "RUN_CLAIM.json",
        {
            "pid": os.getpid(),
            "workers": args.workers,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )
    plan = read(out / "PLAN.json")
    for rel, sha in plan["files"].items():
        if digest(out / rel) != sha:
            raise ValueError("Frozen query-control study changed")
    tasks = [(out / c["case"], arm) for c in plan["cases"] for arm in c["arms"]]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = []
        for result in pool.map(run_arm, tasks):
            results.append(result)
            if len(results) % 9 == 0:
                print({"completed": len(results)}, flush=True)
    publish(
        out / "COMPLETE.json",
        {
            "completed": len(results),
            "results": results,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


if __name__ == "__main__":
    main()
