"""Freeze serial selector-by-predictor development controls before adaptive calls."""

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import fingerprint
from disastertrace.monitoring_fixed_v1.outcomes import (
    ComparisonContract,
    experiment_spec,
)
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.spool_backend import CommittedSpoolBackend

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "scripts"))
from run_program_calendar import configs, outcomes


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def arm_definitions():
    return [
        ("A00_follow", "round_robin", "program", False, False, None),
        ("A01_base_program", "round_robin", "program", False, True, None),
        ("A02_one_program", "round_robin", "program", True, True, 1),
        ("A03_batch_program", "batch_complete", "program", True, True, None),
        ("A04_risk_program", "risk", "program", True, True, None),
        ("A05_coverage_program", "coverage", "program", True, True, None),
        ("A06_llm_program", "llm", "program", True, True, None),
        ("A07_base_llm", "round_robin", "llm", False, True, None),
        ("A08_one_llm", "round_robin", "llm", True, True, 1),
        ("A09_batch_llm", "batch_complete", "llm", True, True, None),
        ("A10_risk_llm", "risk", "llm", True, True, None),
        ("A11_coverage_llm", "coverage", "llm", True, True, None),
        ("A12_llm_llm", "llm", "llm", True, True, None),
    ]


def main(rehearsal, name=None, selector_roles_only=False):
    if selector_roles_only and not rehearsal:
        raise ValueError("Selector-role subset is only for engineering rehearsal")
    name = name or ("adaptive_rehearsal_01" if rehearsal else "adaptive_large_01")
    assert Path(name).name == name and name.startswith(
        "adaptive_rehearsal_" if rehearsal else "adaptive_large_"
    )
    out = HERE / "gpu" / name
    out.mkdir(exist_ok=False)
    old = read(HERE / "gpu/large_diagnostic_02/PLAN.json")
    model = old["models"]["qwen235b_fp8"]
    hours = 2 if rehearsal else 24
    generation = {
        "seed": 20260913,
        "temperature": 0,
        "max_tokens": 512,
        "thinking": False,
    }
    backend_spec = {
        "model": "engineering_no_model" if rehearsal else model["name"],
        "weights": "none" if rehearsal else model["files"],
        "tokenizer": "none"
        if rehearsal
        else [r for r in model["files"] if "tokenizer" in r["path"]],
        "adapter": "serial_committed_selector_predictor.v1",
        "generation": generation,
        "runtime": {
            "versions": old["runtime_versions"],
            "tensor_parallel_size": 4,
            "engine": old["engine"],
            "batching": "up to4 independent serial controllers",
        },
    }
    save(out / "BACKEND.json", backend_spec)
    bank = read(HERE / "contracts/BANK.json")
    save(out / "BANK.json", bank)
    cases, ceiling = [], 0
    for threshold in (1000, 5000):
        for protocol in ("base_bound_override", "persistent_override"):
            group_id = str(threshold) + "__" + protocol
            group = out / "cases" / group_id
            group.mkdir(parents=True)
            data = load_session(
                HERE / "development_dataset_v2",
                stations=["KSFO", "KOAK", "KSJC"],
                hours=hours,
                threshold=threshold,
            )
            save(group / "DATA.json", data)
            outcomes(HERE / "development_dataset_v2", data, group)
            allowed = defaultdict(list)
            reference = None
            for arm, selector, predictor, acquire, predict, one in arm_definitions():
                if selector_roles_only and selector != "llm":
                    continue
                ident = group_id + "__" + arm
                run = out / "runs" / ident
                (run / "spool").mkdir(parents=True)
                config = configs(hours, protocol)["P04_risk_shared"]
                config.pop("execution_contract")
                config.update(
                    request_budget=hours * 2,
                    model_call_budget=hours * 10,
                    input_token_cap=15360,
                    output_token_cap=512,
                    token_cap=hours * 10 * 15872,
                    compute_ms_cap=hours * 10 * 120000 + hours * 2 * 100 + hours * 9,
                    selector_kind=selector,
                    predictor_kind=predictor,
                    isolation_mode="actual_cost_clock",
                    acquire=acquire,
                    predict=predict,
                    query_limit_per_tick=one,
                )
                uses_model = selector == "llm" or predictor == "llm"
                executor = (
                    CommittedSpoolBackend(run / "spool", backend_spec, run_id=ident)
                    if uses_model
                    else None
                )
                config = bind_execution(config, executor)
                config_path = group / (arm + ".json")
                save(config_path, config)
                spec = experiment_spec(data, bank, config)
                if reference is None:
                    reference = spec["invariants"]
                assert reference == spec["invariants"], (
                    "Compared methods changed a frozen common condition"
                )
                for key, value in spec["interventions"].items():
                    if value not in allowed[key]:
                        allowed[key].append(value)
                calls = hours * (9 * int(predictor == "llm") + int(selector == "llm"))
                ceiling += calls
                cases.append(
                    {
                        "id": ident,
                        "arm": arm,
                        "data_case": group_id,
                        "config": str(config_path.relative_to(out)),
                        "uses_model": uses_model,
                        "max_model_calls": calls,
                        "opportunities": len(data["opportunities"]),
                        "threshold_m": threshold,
                        "protocol": protocol,
                    }
                )
            save(
                group / "COMPARISON.json",
                ComparisonContract(reference, dict(allowed)).export(),
            )
    package = REPO / "disastertrace-starter/src/disastertrace"
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            package / module,
            out / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Frozen adaptive development package."""\n'
    )
    for script in ("adaptive_worker.py", "verify_adaptive.py", "run_adaptive_audit.py"):
        shutil.copyfile(Path(__file__).with_name(script), out / "source" / script)
    files = {str(p.relative_to(out)): sha(p) for p in out.rglob("*") if p.is_file()}
    plan = {
        "schema": "disastertrace.serial_adaptive_development.v1",
        "frozen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "engineering_rehearsal": rehearsal,
        "selector_roles_only": selector_roles_only,
        "model": model,
        "runtime_versions": old["runtime_versions"],
        "generation": generation,
        "engine": old["engine"],
        "parallel_controllers": 2 if rehearsal else 4,
        "maximum_concurrent_gpus": 0 if rehearsal else 4,
        "model_call_ceiling": 0 if rehearsal else ceiling,
        "maximum_processor_callbacks": ceiling,
        "input_token_cap": 15360,
        "last_worker_time": "2026-09-14T02:30:00+00:00",
        "cases": cases,
        "case_order": sorted(
            (c["id"] for c in cases),
            key=lambda key: fingerprint({"case": key, "seed": 20260913}),
        ),
        "files": files,
        "data_scope": "Complete2h engineering subset"
        if rehearsal
        else "Complete24h exposed2025-02-03 development calendar",
        "timing": {
            "model_compute": "Measured tokenization and whole generation batch, per-call charge; unique batches also reported.",
            "model_delivery": "Original staged request through checkpoint and durable response observation.",
            "program_prediction": "Declared1ms original frozen frequency program; not measured hardware latency.",
            "program_selection": "Original metadata ranking, orchestration overhead outside the resource clock.",
            "source_queries": "Original declared100ms processing and native catalog latency scenario.",
            "admission_persistence": "Declared additional1ms; excludes full controller archival overhead.",
        },
        "limits": [
            "Serial controller scope only; cross-session batching does not share evidence or quotas.",
            "Adaptive development diagnostic; no independent weather-process confirmation.",
            "Model and program timing bases are disclosed; no operational speedup or end-to-end cost-efficiency claim.",
            "X09 multi-target joint reasoning and D/MM are not completed by this E/F joint head.",
            "Negative or unchanged F results are retained; no forced probability change, refit or selective retry.",
            "Unfinished sessions retain all registered opportunities as explicit unscored rows; no invented continuation.",
        ],
        "stop_policy": "Stop original controllers at fixed last_worker_time or worker failure; preserve staged/claimed/unknown requests and never reissue.",
    }
    save(out / "PLAN.json", plan)
    print(
        json.dumps(
            {
                "out": str(out),
                "cases": len(cases),
                "max_model_calls": plan["model_call_ceiling"],
                "opportunities_per_case": cases[0]["opportunities"],
                "plan_sha256": sha(out / "PLAN.json"),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearsal", action="store_true")
    parser.add_argument("--name")
    parser.add_argument("--selector-roles-only", action="store_true")
    args = parser.parse_args()
    main(args.rehearsal, args.name, args.selector_roles_only)
