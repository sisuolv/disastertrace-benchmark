"""Native source workers and restored controllers share one paid acquisition history."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import PendingExecution
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.source_spool import ArchiveSpoolSource
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / "reports/real_committed_source_01"


def source(out):
    return ArchiveSpoolSource(
        out / "spool",
        read(out / "SOURCE_CONTRACT.json"),
        run_id="real-native-source-recovery.v1",
    )


def worker(out, index, *, probe=False):
    state = read(out / f"PENDING_{index}.json")
    pending = state["payload"]["pending_source"]
    backend = source(out)
    try:
        request = backend.claim_ready(
            pending["receipt_id"], worker_id=f"native-process-{index}"
        )
    except PendingExecution:
        if not probe:
            raise
        publish(
            out / f"UNRELEASED_PROBE_{index}.json",
            {
                "blocked_as_required": True,
                "durable_checkpoint_exists": True,
                "worker_started": False,
            },
        )
        return
    if probe:
        raise RuntimeError("Native worker claimed an unreleased checkpoint")
    start = time.perf_counter()
    data = read(out / "DATA.json")
    product = next(
        r
        for r in data["query_results"]
        if r["query_id"] == request["request"]["query_id"]
    )
    raw = json.dumps(product, sort_keys=True, separators=(",", ":"), allow_nan=False)
    seconds = time.perf_counter() - start
    key = pending["ticket"]["remote_id"]
    row = {
        "call_id": pending["receipt_id"],
        "request_sha256": pending["ticket"]["request_sha256"],
        "execution_sha256": request["execution_sha256"],
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": 0,
        "output_tokens": 0,
        "compute_seconds": seconds,
        "ended_with_eos": True,
    }
    receipt = out / "spool" / (key + ".worker.json")
    publish(
        receipt,
        {
            **row,
            "origin": "registered native METAR archive, no model",
            "pid": os.getpid(),
        },
    )
    publish(
        out / "spool" / (key + ".response.json"),
        {
            **row,
            "schema": "disastertrace.spool_response.v1",
            "worker_receipt_sha256": digest(receipt),
        },
    )


def restore(out, index):
    session = SessionCoordinator.restore(
        read(out / f"PENDING_{index}.json"),
        read(out / "DATA.json"),
        read(out / "BANK.json"),
        source_backend=source(out),
    )
    report = session.finish()
    publish(out / f"RESTORED_REPORT_{index}.json", report)
    publish(out / f"RESTORED_CHECKPOINT_{index}.json", session.snapshot())


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
    bank = read(HERE / "contracts/BANK.json")
    config = configs(3, "base_bound_override")["P04_risk_shared"]
    config.update(predict=False, isolation_mode="actual_cost_clock", request_budget=3)
    publish(OUT / "DATA.json", data)
    publish(OUT / "BANK.json", bank)
    publish(
        OUT / "SOURCE_CONTRACT.json",
        {
            "provider": "registered_native_METAR_archive",
            "products_sha256": canonical_hash(data["query_results"]),
            "acquisition": "paid supplemental records",
            "timing": "observed local transport with declared archive latency floor",
        },
    )
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            REPO / "disastertrace-starter/src/disastertrace" / module,
            OUT / "source/disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (OUT / "source/disastertrace/__init__.py").write_text(
        '"""Frozen source recovery package."""\n'
    )
    shutil.copyfile(Path(__file__), OUT / "source/execute_source_recovery.py")
    publish(
        OUT / "SOURCE_MANIFEST.json",
        {str(p.relative_to(OUT)): digest(p) for p in (OUT / "source").rglob("*.py")},
    )
    session = SessionCoordinator(data, bank, config, source_backend=source(OUT))
    session.finish()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(OUT / "source"))
    index = 0
    while not session.done:
        checkpoint = session.snapshot()
        assert (
            checkpoint["payload"]["schema"]
            == "disastertrace.session_inflight_source.v5"
        )
        path = OUT / f"PENDING_{index}.json"
        publish(path, checkpoint)
        session.step()
        assert session.snapshot() == checkpoint
        for mode in ("probe", "worker", "restore"):
            if mode == "worker":
                session.persist(path)
            command = [
                sys.executable,
                str(OUT / "source/execute_source_recovery.py"),
                mode,
                "--out",
                str(OUT),
                "--index",
                str(index),
            ]
            publish(OUT / f"{mode}_{index}.command.json", {"command": command})
            with (OUT / f"{mode}_{index}.log").open("x") as handle:
                result = subprocess.run(
                    command,
                    env=env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            publish(OUT / f"{mode}_{index}.exit.json", {"exit_code": result.returncode})
            assert result.returncode == 0, (mode, index)
        reference = session.finish()
        assert reference == read(OUT / f"RESTORED_REPORT_{index}.json")
        assert session.snapshot() == read(OUT / f"RESTORED_CHECKPOINT_{index}.json")
        index += 1
    report = session.report
    assert index == len(report["source_receipts"]) == 3
    assert report["resource_spent"]["requests"] == 3
    assert report["resource_reserved"]["requests"] == 0
    assert report["actual_model_calls"] == 0
    assert len(report["snapshots"]) == len(data["opportunities"]) == 27
    assert len(list((OUT / "spool").glob("*.claim.json"))) == 3
    publish(OUT / "REPORT.json", report)
    publish(
        OUT / "VALIDATION.json",
        {
            "passed": True,
            "opportunities": 27,
            "native_query_responses": 3,
            "separate_native_workers": 3,
            "fresh_controller_processes": 3,
            "repeated_original_acquisitions": 0,
            "new_model_calls": 0,
            "all_unreleased_worker_probes_blocked": True,
            "all_cross_process_reports_exact": True,
            "original_data": "2025-02-03 Bay native TAF/METAR",
            "actual_external_downloads": 0,
            "scope": "Serial archive queries via real local processes; physical provider execution deduplication is not proved.",
            "remaining": [
                "general parallel inflight calls",
                "physical external transport reconciliation",
                "D recovery",
            ],
        },
    )
    print(json.dumps(read(OUT / "VALIDATION.json")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["main", "probe", "worker", "restore"])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--index", type=int)
    args = parser.parse_args()
    if args.mode == "main":
        main()
    elif args.mode == "restore":
        restore(args.out, args.index)
    else:
        worker(args.out, args.index, probe=args.mode == "probe")
