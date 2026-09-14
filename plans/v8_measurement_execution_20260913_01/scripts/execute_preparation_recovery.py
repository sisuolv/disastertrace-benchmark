"""Replay native E/F plus synthetic D through separately committed transports."""

import argparse
import importlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
HELPERS = {
    "predictor": "execute_committed_recovery",
    "selector": "execute_selector_recovery",
    "source": "execute_source_recovery",
}


def schedule(data, config):
    first = min(o["cutoff"] for o in data["opportunities"])
    start = first - config["wakeup_seconds"] * 1_000_000
    return {
        "schema": "disastertrace.session_preparation_schedule.v1",
        "decision_basis": "frozen_exogenous_schedule",
        "scenario": {
            "schema": "disastertrace.preparation_scenario.v1",
            "kind": "research_assumption",
            "units": "synthetic_cost_units",
            "capacity": 1,
            "budget": 10,
            "jobs": [
                {
                    "job_id": "research-preparation",
                    "target_id": data["opportunities"][0]["target_id"],
                    "deadline": first,
                    "duration": 10_000_000,
                    "expires_at": first + 30_000_000,
                    "cost": 3,
                    "cleanup_duration": 500_000,
                    "cleanup_cost": 1,
                }
            ],
        },
        "events": [
            {
                "event_id": "D-start",
                "time": start - 2,
                "kind": "prepare",
                "payload": {"job_id": "research-preparation"},
            },
            {
                "event_id": "D-cancel",
                "time": start + 1_000_000,
                "kind": "cancel_preparation",
                "payload": {"job_id": "research-preparation"},
            },
        ],
    }


def command(out, name, argv, source):
    publish(out / (name + ".command.json"), {"command": argv})
    with (out / (name + ".log")).open("x") as handle:
        result = subprocess.run(
            argv,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(source)),
        )
    publish(out / (name + ".exit.json"), {"exit_code": result.returncode})
    assert result.returncode == 0, name


def run_case(root, source, role, data, bank):
    from run_program_calendar import configs

    out = root / "cases" / role
    out.mkdir(parents=True)
    (out / "spool").mkdir()
    helper = importlib.import_module(HELPERS[role])
    config = configs(3, "base_bound_override")["P04_risk_shared"]
    config.pop("execution_contract")
    config.update(
        isolation_mode="actual_cost_clock", forecast_call_cap=1, model_call_budget=1
    )
    config["preparation_schedule"] = schedule(data, config)
    publish(out / "DATA.json", data)
    publish(out / "BANK.json", bank)
    if role == "source":
        config.update(predict=False, request_budget=3)
        publish(
            out / "SOURCE_CONTRACT.json",
            {
                "provider": "registered_native_METAR_archive",
                "products_sha256": canonical_hash(data["query_results"]),
                "timing": "measured local transport with declared archive floor",
                "worker_extra_delivery_delay_seconds": 2,
            },
        )
        session = SessionCoordinator(
            data, bank, config, source_backend=helper.source(out)
        )
    else:
        config.update(executor_id="program_transport_engineering.v1")
        if role == "selector":
            config.update(selector_kind="llm", predict=False)
        else:
            config.update(acquire=False)
        publish(
            out / "BACKEND.json",
            {
                "model": "no_model_deterministic_program",
                "weights": "none",
                "tokenizer": "none",
                "adapter": "preparation_native_transport.v1",
                "generation": {},
                "runtime": {
                    "kind": "CPU stdlib",
                    "worker_extra_delivery_delay_seconds": 2,
                },
            },
        )
        session = SessionCoordinator(data, bank, config, backend=helper.backend(out))
    publish(out / "CONFIG.json", session.config)
    session.finish()
    index = 0
    while not session.done:
        checkpoint = session.snapshot()
        assert "pending_" + role in checkpoint["payload"]
        reducer = AdmissionEngine.restore(checkpoint["payload"]["runtime"]).preparation
        assert reducer is not None
        if index == 0:
            assert reducer.states["research-preparation"]["status"] == "running"
            assert reducer.spent == 3 and reducer.reserved == 1
        path = out / (
            f"PENDING_{index}.json" if role == "source" else "PENDING_CHECKPOINT.json"
        )
        publish(path, checkpoint)
        session.step()
        assert session.snapshot() == checkpoint
        helper_path = source / (HELPERS[role] + ".py")
        suffix = ["--out", str(out)] + (
            ["--index", str(index)] if role == "source" else []
        )
        command(
            out,
            f"probe_{index}",
            [sys.executable, str(helper_path), "probe", *suffix],
            source,
        )
        session.persist(path)
        command(
            out,
            f"worker_{index}",
            [
                sys.executable,
                str(source / Path(__file__).name),
                "worker",
                "--case",
                str(out),
                "--role",
                role,
                "--index",
                str(index),
            ],
            source,
        )
        command(
            out,
            f"restore_{index}",
            [sys.executable, str(helper_path), "restore", *suffix],
            source,
        )
        session.finish()
        recovered_path = out / (
            f"RESTORED_CHECKPOINT_{index}.json"
            if role == "source"
            else "RESTORED_CHECKPOINT.json"
        )
        assert read(recovered_path) == session.snapshot()
        index += 1
    report = session.report
    engine = AdmissionEngine.restore(session.snapshot()["payload"]["runtime"])
    engine.write_journal(out / "ADMISSION.jsonl")
    replay = AdmissionEngine.from_journal(out / "ADMISSION.jsonl")
    assert replay.export() == engine.export()
    assert replay.preparation.to_dict() == engine.preparation.to_dict()
    reducer = engine.preparation
    assert reducer.states["research-preparation"]["status"] == "canceled"
    assert reducer.spent == 4 and reducer.reserved == 0
    assert sum(r["status"] == "started" for r in reducer.history) == 1
    assert sum(r["status"] == "cleanup_complete" for r in reducer.history) == 1
    assert len(report["snapshots"]) == len(data["opportunities"]) == 27
    assert len(list((out / "spool").glob("*.request.json"))) == index
    assert not any(report["resource_reserved"].values())
    publish(out / "REPORT.json", report)
    publish(out / "PREPARATION.json", reducer.to_dict())
    result = {
        "role": role,
        "passed": True,
        "opportunities": 27,
        "committed_native_transport_invocations": index,
        "separate_process_recoveries": index,
        "new_model_calls": 0,
        "D_initial_running_spent": 3,
        "D_initial_reserved_cleanup": 1,
        "D_final_spent": 4,
        "D_final_reserved_cleanup": 0,
        "D_starts": 1,
        "D_cleanup_completions": 1,
        "snapshot_and_journal_replay_equal": True,
        "source_queries": len(report["source_receipts"]),
        "source_report_sha256": digest(out / "REPORT.json"),
    }
    publish(out / "VALIDATION.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["main", "worker"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--role", choices=list(HELPERS))
    parser.add_argument("--roles", choices=list(HELPERS), nargs="+", default=list(HELPERS))
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args()
    if args.mode == "worker":
        # This is an actual delivery wait, never a fabricated compute duration.
        time.sleep(2)
        helper = importlib.import_module(HELPERS[args.role])
        if args.role == "source":
            helper.worker(args.case, args.index)
        else:
            helper.worker(args.case)
        return
    root = args.output.resolve()
    assert len(set(args.roles)) == len(args.roles)
    root.mkdir(parents=True, exist_ok=False)
    source = root / "source"
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            REPO / "disastertrace-starter/src/disastertrace" / module,
            source / "disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (source / "disastertrace/__init__.py").write_text(
        '"""Frozen mixed native and synthetic recovery qualification."""\n'
    )
    for name in [*HELPERS.values(), "run_program_calendar", Path(__file__).stem]:
        shutil.copyfile(Path(__file__).with_name(name + ".py"), source / (name + ".py"))
    publish(
        root / "PLAN.json",
        {
            "roles": args.roles,
            "native_data": "Bay 2025-02-03 exposed development",
            "D": "synthetic frozen exogenous start/cancel schedule, separate declared research-cost units",
            "worker_delay_seconds": 2,
            "maximum_original_transport_calls": 5,
            "model_calls": 0,
            "does_not_train": True,
            "does_not_establish": [
                "model-selected decisions",
                "real mitigation benefit",
                "arbitrary simultaneous pending requests",
                "external exactly-once",
                "independent confirmation",
            ],
            "source_files": {
                str(p.relative_to(root)): digest(p) for p in source.rglob("*.py")
            },
        },
    )
    data = load_session(
        HERE / "development_dataset_v2",
        stations=["KSFO", "KOAK", "KSJC"],
        hours=3,
        threshold=5000,
    )
    bank = read(HERE / "contracts/BANK.json")
    rows = [run_case(root, source, role, data, bank) for role in args.roles]
    assert sum(r["committed_native_transport_invocations"] for r in rows) <= 5
    result = {
        "passed": True,
        "roles": rows,
        "new_model_calls": 0,
        "scope": "Native weather records with synthetic exogenous D actions and separate real local worker/controller processes; one event clock and original source/model resource reservations survive. No live GPU batch was changed.",
    }
    publish(root / "VALIDATION.json", result)
    print(__import__("json").dumps(result))


if __name__ == "__main__":
    main()
