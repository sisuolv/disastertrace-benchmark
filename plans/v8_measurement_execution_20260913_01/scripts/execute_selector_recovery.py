"""Real native query selection and a committed worker across process restoration."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import canonical
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import PendingExecution
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import (
    CommittedSpoolBackend as SpoolBackend,
)
from disastertrace.monitoring_v1.spool_backend import digest, publish

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / "reports/real_committed_selector_01"


def load(path):
    return json.loads(path.read_text())


def save(path, row):
    with path.open("x") as handle:
        json.dump(row, handle, indent=2, allow_nan=False)
        handle.write("\n")


def backend(out):
    return SpoolBackend(
        out / "spool",
        load(out / "BACKEND.json"),
        run_id="real-native-selector-committed.v3",
    )


def worker(out):
    (request_path,) = (out / "spool").glob("*.request.json")
    request = load(request_path)
    backend(out).claim_ready(request["call_id"], worker_id="program-worker-process")
    began = time.perf_counter()
    view = request["request"]
    raw = canonical({"query_order": sorted(view["queries"]), "forecast_handles": []})
    seconds = time.perf_counter() - began
    row = {
        "call_id": request["call_id"],
        "request_sha256": digest(request_path),
        "execution_sha256": request["execution_sha256"],
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": 0,
        "output_tokens": 0,
        "compute_seconds": seconds,
        "ended_with_eos": True,
    }
    key = request_path.name.removesuffix(".request.json")
    receipt_path = out / "spool" / (key + ".worker.json")
    publish(
        receipt_path,
        {
            **row,
            "origin": "real native inputs; deterministic program; zero LLM calls",
            "pid": os.getpid(),
        },
    )
    publish(
        out / "spool" / (key + ".response.json"),
        {
            **row,
            "schema": "disastertrace.spool_response.v1",
            "worker_receipt_sha256": digest(receipt_path),
        },
    )


def restore(out):
    session = SessionCoordinator.restore(
        load(out / "PENDING_CHECKPOINT.json"),
        load(out / "DATA.json"),
        load(out / "BANK.json"),
        backend=backend(out),
    )
    report = session.finish()
    assert session.done
    save(out / "RESTORED_REPORT.json", report)
    save(out / "RESTORED_CHECKPOINT.json", session.snapshot())


def main():
    from run_program_calendar import configs

    OUT.mkdir(exist_ok=False)
    (OUT / "spool").mkdir()
    data = load_session(
        HERE / "development_dataset_v2",
        stations=["KSFO", "KOAK", "KSJC"],
        hours=3,
        threshold=5000,
    )
    bank = load(HERE / "contracts/BANK.json")
    config = configs(3, "base_bound_override")["P04_risk_shared"]
    config.pop("execution_contract")
    config.update(
        selector_kind="llm",
        isolation_mode="actual_cost_clock",
        forecast_call_cap=1,
        model_call_budget=1,
        executor_id="program_transport_engineering.v1",
    )
    save(OUT / "DATA.json", data)
    save(OUT / "BANK.json", bank)
    save(
        OUT / "BACKEND.json",
        {
            "model": "no_model_deterministic_query_order",
            "weights": "none",
            "tokenizer": "none",
            "adapter": "native_program_transport.v1",
            "generation": {},
            "runtime": "CPU stdlib",
        },
    )
    source = REPO / "disastertrace-starter/src/disastertrace"
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            source / module,
            OUT / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (OUT / "source/disastertrace/__init__.py").write_text(
        '"""Frozen pending recovery package."""\n'
    )
    shutil.copyfile(Path(__file__), OUT / "source/execute_selector_recovery.py")
    save(
        OUT / "SOURCE_MANIFEST.json",
        {str(p.relative_to(OUT)): digest(p) for p in (OUT / "source").rglob("*.py")},
    )
    session = SessionCoordinator(data, bank, config, backend=backend(OUT))
    first = session.step()
    checkpoint = session.snapshot()
    assert (
        checkpoint["payload"]["schema"] == "disastertrace.session_inflight_selector.v4"
    )
    publish(OUT / "PENDING_CHECKPOINT.json", checkpoint)
    session.step()
    assert session.snapshot() == checkpoint
    save(OUT / "PREFIX_REPORT.json", first)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(OUT / "source"))
    for stage in ("probe", "worker", "restore"):
        if stage == "worker":
            session.persist(OUT / "PENDING_CHECKPOINT.json")
        command = [
            sys.executable,
            str(OUT / "source/execute_selector_recovery.py"),
            stage,
            "--out",
            str(OUT),
        ]
        save(OUT / (stage + ".command.json"), {"command": command})
        with (OUT / (stage + ".log")).open("x") as handle:
            result = subprocess.run(
                command, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False
            )
        save(OUT / (stage + ".exit.json"), {"exit_code": result.returncode})
        assert result.returncode == 0, stage
    reference = session.finish()
    recovered = load(OUT / "RESTORED_REPORT.json")
    assert reference == recovered
    assert (
        len(recovered["selector_calls"]) == 1
        and not recovered["calls"]
        and recovered["source_receipts"]
        and len(recovered["snapshots"]) == len(data["opportunities"]) == 27
    )
    assert len(list((OUT / "spool").glob("*.request.json"))) == 1
    assert (
        len(
            [
                e
                for e in recovered["resource_events"]
                if e["event"] == "reserve" and e["receipt_id"] == "select-0"
            ]
        )
        == 1
    )
    assert recovered["resource_reserved"]["tokens"] == 0
    save(
        OUT / "VALIDATION.json",
        {
            "passed": True,
            "opportunities": 27,
            "pending_requests": 1,
            "backend_program_invocations": 1,
            "new_model_calls": 0,
            "same_captured_response_cross_process_replay_equal": True,
            "pending_reservation_preserved": True,
            "unresolved_poll_idempotent": True,
            "original_dispatch_only": True,
            "native_source": "2025-02-03 Bay TAF/METAR verified captures",
            "interpretation": "Real data and actual multi-process transport, but deterministic program reply; no LLM effectiveness claim.",
            "worker_requires_durable_checkpoint": True,
            "unreleased_durable_checkpoint_worker_probe": True,
            "pre_dispatch_receipt_committed": True,
            "remaining_CP04b": [
                "pending source request",
                "comprehensive external transport failure reconciliation",
            ],
        },
    )
    print(json.dumps(load(OUT / "VALIDATION.json")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["main", "worker", "restore", "probe"])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "main":
        main()
    elif args.mode == "probe":
        requests = list((args.out / "spool").glob("*.request.json"))
        assert len(requests) == 1
        try:
            backend(args.out).claim_ready(
                load(requests[0])["call_id"], worker_id="must-not-start"
            )
        except PendingExecution:
            save(
                args.out / "UNRELEASED_CHECKPOINT_PROBE.json",
                {
                    "blocked_as_required": True,
                    "checkpoint_exists": (
                        args.out / "PENDING_CHECKPOINT.json"
                    ).exists(),
                    "worker_started": False,
                },
            )
        else:
            raise RuntimeError("Worker consumed a request without a checkpoint release")
    elif args.mode == "worker":
        worker(args.out)
    else:
        restore(args.out)
