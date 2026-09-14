"""Register first-calendar-day controls and execute two disjoint CPU shards."""

import argparse
import datetime as dt
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import (
    ComparisonContract,
    experiment_spec,
)
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import utc_us
from run_multicutoff import run_arm

STATIONS = {
    "new_york": ["KJFK", "KLGA", "KEWR"],
    "chicago": ["KORD", "KMDW", "KRFD"],
    "denver": ["KDEN", "KBJC", "KAPA"],
}
ARMS = [
    "FOLLOW",
    "F_BASE_ONLY",
    "B00_COVERAGE",
    "B01_COVERAGE",
    "B10_COVERAGE",
    "B11_COVERAGE",
    "B11_RISK",
    "B11_ROUND_ROBIN",
    "B11_BATCH",
]


def prepare(out):
    run = Path(__file__).resolve().parents[1]
    repo = run.parents[1]
    ablation = run / "calendar_feature_ablation_01"
    if (
        not read(ablation / "RESULT.json")["passed"]
        or not read(run / "reports/native_feature_sessions_audit_01/RESULT.json")[
            "passed"
        ]
    ):
        raise ValueError(
            "Both the ablation arithmetic and original session audits are required"
        )
    units = read(run / "seasonal_completion_02/COMPLETE.json")["units"]
    if len(units) != 12 or not all(u["complete"] for u in units):
        raise ValueError("All original twelve region-weeks are required")
    out.mkdir(exist_ok=False)
    publish(
        out / "REGISTRATION.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "calendar_rule": "first UTC cutoff day of every previously fixed region-week; all24 single-threshold cases",
            "thresholds": [1000, 5000],
            "regions": list(STATIONS),
            "arms": ARMS,
            "scope": "error-informed developmental backend extension; no independent confirmation",
            "bank": "Dec2024 values bank without year_sin/year_cos; raw primary only",
            "request_budget": 48,
            "forecast_slots_and_allocation_factors": "unchanged from the original program factorial",
            "program_latency": "declared1ms plus1ms persistence; not measured runtime",
            "shards": 2,
            "model_calls": 0,
            "confirmation_opened": False,
            "day_selection_uses_individual_outcomes": False,
            "ablation_result_sha256": digest(ablation / "RESULT.json"),
            "feature_bank_sha256": digest(ablation / "banks/values.json"),
        },
    )
    helper_path = (
        repo
        / "plans/v9_followup_execution_20260914_01/api_pilot_01/source/program_reference.py"
    )
    spec = importlib.util.spec_from_file_location(
        "native_outcome_reference", helper_path
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    feature_bank = read(ablation / "banks/values.json")
    cases = []
    for index, unit in enumerate(units):
        dataset = Path(unit["dataset"])
        for name, sha in unit["dataset_files"].items():
            if digest(dataset / name) != sha:
                raise ValueError("Seasonal input changed")
        region, day = unit["unit"].split("__")
        for threshold in (1000, 5000):
            name = unit["unit"] + "__" + str(threshold)
            case = out / name
            case.mkdir()
            data = load_session(dataset, stations=STATIONS[region], threshold=threshold)
            start = utc_us(day + "T00:00:00Z")
            data["opportunities"] = [
                r
                for r in data["opportunities"]
                if start <= r["cutoff"] < start + 86_400_000_000
                and r["lead_hours"] == 1
            ]
            tids = {r["target_id"] for r in data["opportunities"]}
            oids = {r["opportunity_id"] for r in data["opportunities"]}
            if len(oids) != 72 or len(data["opportunities"]) != 72:
                raise ValueError("The complete first-day roster has changed")
            for field in ("targets", "baseline_candidates", "baseline_withdrawals"):
                data[field] = [r for r in data[field] if r["target_id"] in tids]
            data["e_f_pairs"] = [
                r for r in data["e_f_pairs"] if r["opportunity_id"] in oids
            ]
            bank = read(run / "seasonal_evaluation_01/banks" / (region + ".json"))
            publish(case / "DATA.json", data)
            publish(case / "BANK.json", bank)
            (case / "outcome_preparation").mkdir()
            outcomes = helper.outcomes(dataset, data, case / "outcome_preparation")
            publish(
                case / "OUTCOMES.json",
                [
                    {
                        **r,
                        "resolution_policy": "h15_routine_archive.v1",
                        "provider": "IEM",
                        "provider_version": "native_h15_snapshot.v1",
                    }
                    for r in outcomes
                ],
            )
            original = read(
                run
                / "native_feature_sessions_01"
                / (region + "__2025-01-06__" + str(threshold))
                / "CONFIGS.json"
            )
            configs, allowed, invariant = {}, defaultdict(list), None
            for arm in ARMS:
                config = {
                    **original[arm],
                    "native_feature_bank": feature_bank,
                    "program_prediction": "native_feature_raw",
                }
                config.pop("execution_contract", None)
                config = bind_source(bind_execution(config, None), None)
                configs[arm] = config
                current = experiment_spec(data, bank, config)
                invariant = invariant or current["invariants"]
                if current["invariants"] != invariant:
                    raise ValueError(
                        "Seasonal arms differ in invariant information or resources"
                    )
                for key, value in current["interventions"].items():
                    if value not in allowed[key]:
                        allowed[key].append(value)
            publish(case / "CONFIGS.json", configs)
            publish(
                case / "COMPARISON.json",
                ComparisonContract(invariant, allowed).export(),
            )
            publish(
                case / "SOURCE_BINDINGS.json",
                {
                    "dataset": str(dataset),
                    "dataset_files": unit["dataset_files"],
                    "parent_unit": unit["unit"],
                },
            )
            cases.append(
                {
                    "case": name,
                    "arms": ARMS,
                    "opportunities": 72,
                    "targets": len(tids),
                    "shard": index % 2,
                }
            )
    for package in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(
            repo / "disastertrace-starter/src/disastertrace" / package,
            out / "source/disastertrace" / package,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Frozen seasonal query controls."""\n'
    )
    shutil.copyfile(__file__, out / "source/run_seasonal_controls.py")
    shutil.copyfile(helper_path, out / "source/program_reference.py")
    for name in ("analyze_query_controls.py", "run_multicutoff.py"):
        shutil.copyfile(Path(__file__).with_name(name), out / "source" / name)
    publish(
        out / "PLAN.json",
        {
            "cases": cases,
            "model_calls": 0,
            "method_trajectories": 216,
            "opportunities": 1728,
            "shards": 2,
            "files": {
                str(p.relative_to(out)): digest(p)
                for p in out.rglob("*")
                if p.is_file()
            },
        },
    )
    print(
        json.dumps({"prepared": True, "cases": len(cases), "trajectories": 216}),
        flush=True,
    )


def execute(args):
    out = args.out.absolute()
    if args.shard not in (0, 1):
        raise ValueError("Use an original registered shard")
    plan = read(out / "PLAN.json")
    publish(
        out / ("RUN_CLAIM_" + str(args.shard) + ".json"),
        {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "shard": args.shard},
    )
    for name, sha in plan["files"].items():
        if digest(out / name) != sha:
            raise ValueError("Frozen seasonal session input changed")
    tasks = [
        (out / c["case"], arm)
        for c in plan["cases"]
        if c["shard"] == args.shard
        for arm in c["arms"]
    ]
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for item in pool.map(run_arm, tasks):
            results.append(item)
            if len(results) % 9 == 0:
                print(
                    json.dumps(
                        {
                            "shard": args.shard,
                            "completed": len(results),
                            "registered": len(tasks),
                        }
                    ),
                    flush=True,
                )
    publish(
        out / ("COMPLETE_" + str(args.shard) + ".json"),
        {"completed": len(results), "results": results},
    )


def combine_and_audit(args):
    out = args.out.absolute()
    plan = read(out / "PLAN.json")
    wanted = {(c["case"], arm) for c in plan["cases"] for arm in c["arms"]}
    results = [
        r
        for shard in (0, 1)
        for r in read(out / ("COMPLETE_" + str(shard) + ".json"))["results"]
    ]
    if (
        len(results) != len(wanted)
        or {(r["case"], r["arm"]) for r in results} != wanted
    ):
        raise ValueError("Missing or duplicate seasonal trajectory")
    publish(
        out / "COMPLETE.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "completed": len(results),
            "results": results,
        },
    )
    command = [
        sys.executable,
        str(out / "source/analyze_query_controls.py"),
        "--batch",
        str(out),
        "--out",
        str(args.audit_out.absolute()),
        "--workers",
        str(args.workers),
    ]
    publish(out / "AUDIT_COMMAND.json", {"command": command})
    response = subprocess.run(command, check=False, timeout=7200)
    publish(out / "AUDIT_EXIT.json", {"exit_code": response.returncode})
    raise SystemExit(response.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shard", type=int)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--audit-out", type=Path)
    parser.add_argument("action", choices=["prepare", "execute", "combine-and-audit"])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.out.absolute())
    elif args.action == "execute":
        execute(args)
    else:
        combine_and_audit(args)
