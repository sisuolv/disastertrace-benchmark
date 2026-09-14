"""Formal same-target multi-cutoff program/adoption experiment on exposed H15."""

import argparse
import datetime as dt
import json
import os
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.outcomes import (
    ComparisonContract,
    experiment_spec,
)
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.formal_session import (
    FormalSession,
    required_source_files,
    score_formal,
)
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import utc_us


def run_arm(pair):
    case, name = pair
    data, bank, config = (
        read(case / "DATA.json"),
        read(case / "BANK.json"),
        read(case / "CONFIGS.json")[name],
    )
    c = read(case / "COMPARISON.json")["payload"]
    comparison = ComparisonContract(c["invariants"], c["allowed_interventions"])
    files = {str(p): digest(p) for p in required_source_files()}
    files.update(
        {
            str(case / n): digest(case / n)
            for n in ("DATA.json", "BANK.json", "CONFIGS.json", "COMPARISON.json")
        }
    )
    session = FormalSession(
        data,
        bank,
        config,
        comparison=comparison,
        bound_files=files,
        directory=case / name,
    )
    report = session.finish(max_steps=100)
    publish(case / name / "REPORT.json", report)
    journal = case / name / "admission.jsonl"
    AdmissionEngine.restore(report["event_replay"]).write_journal(journal)
    scores = score_formal(
        read(case / "OUTCOMES.json"), {name: journal}, comparison=comparison
    )
    publish(case / name / "SCORES.json", scores)
    result = {
        "arm": name,
        "opportunities": len(report["snapshots"]),
        "calls": len(report["calls"]),
        "adopted": sum(c["admission_status"] == "accepted" for c in report["calls"]),
        "kept": sum(c["admission_status"] == "adoption_kept" for c in report["calls"]),
        "resource_spent": report["resource_spent"],
        "formal_full_replay": True,
        "model_calls": report["actual_model_calls"],
    }
    publish(case / name / "COMPLETE.json", result)
    return {"case": case.name, **result}


def prepare(out):
    root = Path(__file__).resolve().parents[3]
    old = root / "plans/v9_followup_execution_20260914_01"
    v8 = (
        root
        / "plans/v8_measurement_execution_20260913_01/regional_calendar_extension_01"
    )
    out.mkdir(exist_ok=False)
    registration = {
        "regions": ["new_york", "chicago", "denver"],
        "target_start_dates": ["2025-01-06", "2025-01-10"],
        "target_start_hours_UTC": [6, 12, 18],
        "lead_hours": [6, 3, 1],
        "thresholds": [1000, 5000],
        "protocols": ["base_bound_override", "persistent_override"],
        "request_budget": 48,
        "forecast_calls": 27,
        "query_policy": "batch_complete",
        "selection_uses_future_outcomes": False,
        "calibration": "unchanged regional December bank; multi-lead transfer is diagnostic",
        "scope": "exposed same-target protocol and adoption mechanism; not new synoptic independence",
        "adoption_comparator": "current effective probability at completion; all computed proposals remain charged",
        "registered_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "confirmation_opened": False,
    }
    publish(out / "REGISTRATION.json", registration)
    cases = []
    for region in registration["regions"]:
        for day in registration["target_start_dates"]:
            for threshold in registration["thresholds"]:
                case = out / (region + "__" + day + "__" + str(threshold))
                case.mkdir()
                original = old / "api_pilot_01" / case.name
                original_data = read(original / "DATA.json")
                data = load_session(
                    v8 / region / "dataset_v2",
                    stations=original_data["stations"],
                    threshold=threshold,
                )
                start = utc_us(day + "T00:00:00Z")
                selected_tids = {
                    r["target_id"]
                    for r in data["targets"]
                    if r["physical_start"]
                    in {
                        start + h * 3600_000_000
                        for h in registration["target_start_hours_UTC"]
                    }
                }
                data["opportunities"] = [
                    r
                    for r in data["opportunities"]
                    if r["target_id"] in selected_tids
                    and r["lead_hours"] in registration["lead_hours"]
                ]
                oids = {r["opportunity_id"] for r in data["opportunities"]}
                for n in ("targets", "baseline_candidates", "baseline_withdrawals"):
                    data[n] = [r for r in data[n] if r["target_id"] in selected_tids]
                data["e_f_pairs"] = [
                    r for r in data["e_f_pairs"] if r["opportunity_id"] in oids
                ]
                qids = {q for r in data["e_f_pairs"] for q in r["query_ids"]}
                for n in ("query_catalog", "query_results"):
                    data[n] = [r for r in data[n] if r["query_id"] in qids]
                assert len(data["opportunities"]) == 27 and len(data["targets"]) == 9
                bank = read(original / "BANK.json")
                base = read(original / "CONFIGS.json")["batch_program"]
                base.update(
                    admission_semantics="measurement.v3",
                    formal_resolution_policy="h15_routine_archive.v1",
                    forecast_call_cap=27,
                    model_call_budget=27,
                    per_tick_forecast_cap=3,
                    token_cap=27 * 33280,
                    compute_ms_cap=27 * 120000 + 4800,
                    request_budget=48,
                )
                base.pop("execution_contract", None)
                variants = {
                    "FOLLOW": {
                        "acquire": False,
                        "predict": False,
                        "adoption_policy": {"kind": "always"},
                    },
                    "COPY_CURRENT": {
                        "program_prediction": "copy_current_state",
                        "adoption_policy": {"kind": "always"},
                    },
                    "COPY_BASELINE": {
                        "program_prediction": "copy_latest_baseline",
                        "adoption_policy": {"kind": "always"},
                    },
                    "BASELINE_FIRST_HOLD": {
                        "program_prediction": "copy_latest_baseline",
                        "adoption_policy": {"kind": "first_target_only"},
                    },
                    "FREQUENCY_ALWAYS": {"adoption_policy": {"kind": "always"}},
                    "FREQUENCY_KEEP": {"adoption_policy": {"kind": "never"}},
                    "FREQUENCY_FIRST": {
                        "adoption_policy": {"kind": "first_target_only"}
                    },
                    "FREQUENCY_EPS001": {
                        "adoption_policy": {"kind": "change_epsilon", "epsilon": 0.01}
                    },
                    "FREQUENCY_HARM001": {
                        "adoption_policy": {
                            "kind": "brier_harm_limit",
                            "max_pointwise_harm": 0.01,
                        }
                    },
                }
                configs, allowed, invariants = {}, defaultdict(list), None
                for protocol in registration["protocols"]:
                    for name, changes in variants.items():
                        config = bind_source(
                            bind_execution(
                                dict(base, protocol=protocol, **changes), None
                            ),
                            None,
                        )
                        configs[protocol + "__" + name] = config
                        spec = experiment_spec(data, bank, config)
                        invariants = invariants or spec["invariants"]
                        assert spec["invariants"] == invariants
                        for k, v in spec["interventions"].items():
                            if v not in allowed[k]:
                                allowed[k].append(v)
                target_by_oid = {
                    r["opportunity_id"]: r["target_id"]
                    for r in original_data["opportunities"]
                }
                results = {
                    target_by_oid[r["opportunity_id"]]: r
                    for r in read(original / "OUTCOMES.json")
                }
                outcomes = [
                    {
                        **results[r["target_id"]],
                        "opportunity_id": r["opportunity_id"],
                        "provider": "IEM",
                        "provider_version": "native_h15_snapshot.v1",
                    }
                    for r in data["opportunities"]
                ]
                for n, value in (
                    ("DATA", data),
                    ("BANK", bank),
                    ("CONFIGS", configs),
                    ("OUTCOMES", outcomes),
                ):
                    publish(case / (n + ".json"), value)
                publish(
                    case / "COMPARISON.json",
                    ComparisonContract(invariants, allowed).export(),
                )
                cases.append(
                    {
                        "case": case.name,
                        "arms": list(configs),
                        "opportunities": 27,
                        "targets": 9,
                    }
                )
    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(
            root / "disastertrace-starter/src/disastertrace" / module,
            out / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Frozen v10 multi-cutoff experiment."""\n'
    )
    shutil.copyfile(__file__, out / "source/worker.py")
    publish(
        out / "PLAN.json",
        {
            "cases": cases,
            "method_trajectories": 216,
            "unique_targets": 108,
            "opportunities": 324,
            "model_calls": 0,
            "files": {
                str(p.relative_to(out)): digest(p)
                for p in out.rglob("*")
                if p.is_file()
            },
        },
    )
    print(json.dumps({"cases": len(cases), "trajectories": 216, "opportunities": 324}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workers", type=int, default=24)
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
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )
    plan = read(out / "PLAN.json")
    for rel, sha in plan["files"].items():
        if digest(out / rel) != sha:
            raise ValueError("Frozen multi-cutoff inputs changed")
    tasks = [
        (out / case["case"], arm) for case in plan["cases"] for arm in case["arms"]
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = []
        for row in pool.map(run_arm, tasks):
            results.append(row)
            if len(results) % 18 == 0:
                print(json.dumps({"completed_trajectories": len(results)}), flush=True)
    publish(
        out / "COMPLETE.json",
        {
            "completed": len(results),
            "results": results,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


if __name__ == "__main__":
    main()
