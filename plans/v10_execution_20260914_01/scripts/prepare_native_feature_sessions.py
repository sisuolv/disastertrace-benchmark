"""Freeze the qualified native feature backend under identical real query limits."""

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
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    run = root / "plans/v10_execution_20260914_01"
    original = run / "query_controls_01"
    if not read(run / "reports/native_feature_audit_01/RESULT.json")["passed"]:
        raise ValueError("Native bank audit required before session execution")
    feature_bank = read(run / "native_feature_bank_01/BANK_values.json")
    registration = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "parent_study": str(original),
        "same_opportunities_baselines_queries_budgets_slots": True,
        "model_calls": 0,
        "confirmation_opened": False,
        "primary": "native_feature_raw",
        "secondary": "native_feature_calibrated",
        "calibration_selection": "original frozen prior2 PAV/CDF; no bank refit or test-score selection",
        "scope": "same exposed12 cases; changes numerical backend and preserves original study",
        "program_latency": "declared1ms compute plus1ms persistence, not measured application runtime",
        "feature_bank_sha256": digest(run / "native_feature_bank_01/BANK_values.json"),
    }
    publish(out / "REGISTRATION.json", registration)
    cases = []
    for card in read(original / "PLAN.json")["cases"]:
        case = out / card["case"]
        case.mkdir()
        origin = original / card["case"]
        data, bank = read(origin / "DATA.json"), read(origin / "BANK.json")
        configs = read(origin / "CONFIGS.json")
        for name in list(configs):
            configs[name] = {
                **configs[name],
                "program_prediction": "native_feature_raw",
                "native_feature_bank": feature_bank,
            }
        for name, base in (
            ("CAL_BASE_ONLY", "F_BASE_ONLY"),
            ("CAL_COVERAGE", "B11_COVERAGE"),
            ("CAL_BATCH", "B11_BATCH"),
        ):
            configs[name] = {
                **configs[base],
                "program_prediction": "native_feature_calibrated",
            }
        allowed = defaultdict(list)
        invariant = None
        for name, config in configs.items():
            config.pop("execution_contract", None)
            config = bind_source(bind_execution(config, None), None)
            configs[name] = config
            spec = experiment_spec(data, bank, config)
            invariant = invariant or spec["invariants"]
            if invariant != spec["invariants"]:
                raise ValueError(
                    "Program arms changed invariant resource/information contract"
                )
            for key, value in spec["interventions"].items():
                if value not in allowed[key]:
                    allowed[key].append(value)
        for filename in ("DATA.json", "BANK.json", "OUTCOMES.json"):
            shutil.copyfile(origin / filename, case / filename)
        publish(case / "CONFIGS.json", configs)
        publish(
            case / "COMPARISON.json", ComparisonContract(invariant, allowed).export()
        )
        cases.append({**card, "arms": list(configs)})
    for package in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(
            root / "disastertrace-starter/src/disastertrace" / package,
            out / "source/disastertrace" / package,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Frozen native feature shared-resource sessions."""\n'
    )
    for name in (
        "run_query_controls.py",
        "run_multicutoff.py",
        "analyze_query_controls.py",
        "prepare_native_feature_sessions.py",
    ):
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
    print(
        {"cases": len(cases), "trajectories": sum(len(c["arms"]) for c in cases)},
        flush=True,
    )


if __name__ == "__main__":
    main()
