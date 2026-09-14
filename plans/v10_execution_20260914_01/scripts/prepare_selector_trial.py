"""Freeze an acquisition-only local-model comparison against existing strong arms."""

import argparse
import datetime as dt
import shutil
from collections import defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import (
    ComparisonContract,
    experiment_spec,
)
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.production import ProductionSpoolBackend
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

CONTROLS = [
    "FOLLOW",
    "F_BASE_ONLY",
    "B11_COVERAGE",
    "B11_RISK",
    "B11_ROUND_ROBIN",
    "B11_BATCH",
]


def backend(batch, case):
    return ProductionSpoolBackend(
        case / "spool",
        read(batch / "BACKEND.json"),
        run_id=case.name,
        bound_files={
            str(batch / name): sha
            for name, sha in read(batch / "FROZEN_FILES.json").items()
        },
    )


def main(out):
    root = Path(__file__).resolve().parents[3]
    run = root / "plans/v10_execution_20260914_01"
    assert read(run / "formal_recovery_01/RESULT.json")["passed"]
    assert read(run / "reports/native_feature_audit_01/RESULT.json")["passed"]
    original = run / "native_feature_sessions_01"
    large = run / "large_feature_trial_01"
    out.mkdir(exist_ok=False)
    shutil.copyfile(large / "MODEL_MANIFEST.json", out / "MODEL_MANIFEST.json")
    model = read(out / "MODEL_MANIFEST.json")
    prior = read(large / "PLAN.json")
    publish(
        out / "BACKEND.json",
        {
            "model": model["name"],
            "weights": digest(out / "MODEL_MANIFEST.json"),
            "tokenizer": "frozen model tokenizer, thinking disabled",
            "adapter": "production_selector_only.v1",
            "generation": {"temperature": 0, "max_tokens": 512, "seed": 20260914},
            "runtime": {
                "versions": prior["gpu_runtime"],
                "engine": prior["gpu_engine"],
                "tp": 4,
            },
            "role": "query order only; all future probabilities come from the same frozen native feature program",
        },
    )
    cards = read(original / "PLAN.json")["cases"]
    for card in cards:
        old, case = original / card["case"], out / card["case"]
        case.mkdir()
        (case / "spool").mkdir()
        for filename in ("DATA.json", "BANK.json", "OUTCOMES.json"):
            shutil.copyfile(old / filename, case / filename)
        config = read(old / "CONFIGS.json")["B11_COVERAGE"]
        config.pop("execution_contract", None)
        config["selector_kind"] = "llm"
        publish(case / "UNBOUND_CONFIG.json", config)
        publish(
            case / "CONTROL_INPUTS.json",
            {
                "parent": str(old),
                "arms": CONTROLS,
                "configs": {k: read(old / "CONFIGS.json")[k] for k in CONTROLS},
                "same_data_sha256": digest(old / "DATA.json"),
                "same_bank_sha256": digest(old / "BANK.json"),
            },
        )
    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(
            root / "disastertrace-starter/src/disastertrace" / module,
            out / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Frozen acquisition-only model experiment."""\n'
    )
    for name in (
        "prepare_selector_trial.py",
        "run_selector_trial.py",
        "audit_selector_trial.py",
    ):
        shutil.copyfile(Path(__file__).parent / name, out / "source" / name)
    frozen = {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()}
    publish(out / "FROZEN_FILES.json", frozen)
    for card in cards:
        case = out / card["case"]
        data, bank = read(case / "DATA.json"), read(case / "BANK.json")
        config = bind_source(
            bind_execution(read(case / "UNBOUND_CONFIG.json"), backend(out, case)), None
        )
        configurations = {
            **read(case / "CONTROL_INPUTS.json")["configs"],
            "B11_LLM": config,
        }
        allowed, invariant = defaultdict(list), None
        for value in configurations.values():
            spec = experiment_spec(data, bank, value)
            invariant = invariant or spec["invariants"]
            if invariant != spec["invariants"]:
                raise ValueError(
                    "LLM and strong controls differ in invariant inputs or resources"
                )
            for k, v in spec["interventions"].items():
                if v not in allowed[k]:
                    allowed[k].append(v)
        publish(case / "CONFIG.json", config)
        publish(
            case / "COMPARISON.json", ComparisonContract(invariant, allowed).export()
        )
    publish(
        out / "PLAN.json",
        {
            "schema": "disastertrace.fixed_forecast_selector.v1",
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "cases": [c["case"] for c in cards],
            "control_batch": str(original),
            "control_arms": CONTROLS,
            "local_model": model["name"],
            "max_model_benchmark_calls": 288,
            "compatibility_calls": 1,
            "gpus": 4,
            "batch_size": 4,
            "last_worker_time": "2026-09-14T23:55:00+00:00",
            "api_calls": 0,
            "frozen_features": "BANK_values raw; all models/controls use identical native parsing and feature map",
            "selection_scope": "query order only; ignored forecast handles; same fixed public forecast slots and48source budget",
            "common_taf": "all full professional products shared without charge",
            "source_timing": "declared archive costs unchanged; measured LLM lifecycle includes checkpoint, batching and queueing",
            "control_reuse": "original frozen trajectories; verify full comparison, denominator and journals independently",
            "experiment_scope": "12 already exposed cases; two calendar blocks, not independent confirmation",
            "confirmation_opened": False,
            "native_program_cpu_timing": "declared1ms plus1ms persistence",
            "files": {
                str(p.relative_to(out)): digest(p)
                for p in out.rglob("*")
                if p.is_file()
            },
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.out.absolute())
