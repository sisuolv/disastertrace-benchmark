"""Exercise one formal native-source checkpoint through three fresh processes."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, experiment_spec
from disastertrace.monitoring_v1.execution import PendingExecution, bind_execution
from disastertrace.monitoring_v1.formal_session import FormalSession, required_source_files
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.source_spool import ArchiveSpoolSource
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def source(out):
    return ArchiveSpoolSource(out / "spool", read(out / "SOURCE_CONTRACT.json"), run_id="formal-native-restore-v10")


def main(out):
    root = Path(__file__).resolve().parents[3]
    run = root / "plans/v10_execution_20260914_01"
    out.mkdir(exist_ok=False)
    (out / "spool").mkdir()
    for name in ("DATA.json", "BANK.json"):
        shutil.copyfile(run / "native_residual_02" / name, out / name)
    data = read(out / "DATA.json")
    config = read(run / "query_controls_01/new_york__2025-01-06__1000/CONFIGS.json")["B11_COVERAGE"]
    config.pop("execution_contract", None)
    config.pop("source_execution_contract", None)
    config.pop("forecast_schedule", None)
    config.update(predict=False, request_budget=1, selector_kind="round_robin")
    publish(out / "CONFIG.json", config)
    publish(out / "SOURCE_CONTRACT.json", {"provider": "registered_native_archive",
        "products_sha256": canonical_hash(data["query_results"])})
    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(root / "disastertrace-starter/src/disastertrace" / module,
            out / "source/disastertrace" / module, ignore=shutil.ignore_patterns("__pycache__"))
    (out / "source/disastertrace/__init__.py").write_text('"""Frozen formal recovery qualification."""\n')
    for name in ("qualify_formal_recovery.py", "native_source_worker.py"):
        shutil.copyfile(Path(__file__).parent / name, out / "source" / name)
    publish(out / "PLAN.json", {"source": {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()},
        "native_source_queries": 1, "model_calls": 0, "original_directory_only": True,
        "confirmation_opened": False, "no_general_concurrent_recovery_claim": True})
    env = dict(os.environ, PYTHONPATH=str(out / "source"), PYTHONDONTWRITEBYTECODE="1")
    for mode in ("create", "deliver", "restore", "closed_probe"):
        command = [sys.executable, str(out / "source/qualify_formal_recovery.py"), mode, "--out", str(out)]
        publish(out / (mode + ".command.json"), {"command": command})
        with (out / (mode + ".log")).open("x") as stream:
            child = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
        publish(out / (mode + ".exit.json"), {"exit_code": child.returncode})
        if child.returncode:
            raise RuntimeError("Formal recovery stage failed: " + mode)
    report = read(out / "REPORT.json")
    before, after = read(out / "PENDING.json")["payload"], read(out / "FINAL.json")["payload"]
    events = report["resource_events"]
    rid = before["pending_source"]["receipt_id"]
    assert sum(e["event"] == "reserve" and e["receipt_id"] == rid for e in events) == 1
    assert sum(e["event"] == "completed" and e["receipt_id"] == rid for e in events) == 1
    assert not before["store"]["assets"] and len(after["store"]["assets"]) == 1
    assert report["resource_spent"]["requests"] == 1 and report["resource_reserved"]["requests"] == 0
    assert len(list((out / "spool").glob("*.request.json"))) == 1
    pids = [read(out / (mode + ".pid.json"))["pid"] for mode in ("create", "deliver", "restore", "closed_probe")]
    assert len(set(pids)) == 4
    AdmissionEngine.from_journal(out / "admission.jsonl")
    publish(out / "RESULT.json", {"passed": True, "fresh_processes": len(pids), "native_queries": 1,
        "registered_opportunities": len(data["opportunities"]), "settled_original_once": True,
        "no_evidence_before_original_completion": True, "formal_binding_before_worker_release": True,
        "full_event_replay": True, "stopped_session_reopening_blocked": True,
        "model_calls": 0, "scope": "native-data managed serial process recovery, not LLM gain or distributed ownership"})


def stage(mode, out):
    publish(out / (mode + ".pid.json"), {"pid": os.getpid()})
    for name, sha in read(out / "PLAN.json")["source"].items():
        assert digest(out / name) == sha
    data, bank, backend = read(out / "DATA.json"), read(out / "BANK.json"), source(out)
    if mode == "create":
        config = bind_source(bind_execution(read(out / "CONFIG.json"), None), backend)
        spec = experiment_spec(data, bank, config)
        comparison = ComparisonContract(spec["invariants"], {k: [v] for k, v in spec["interventions"].items()})
        files = {str(p): digest(p) for p in required_source_files()}
        files.update({str(out / p): digest(out / p) for p in read(out / "PLAN.json")["source"]})
        session = FormalSession(data, bank, config, comparison=comparison, bound_files=files,
                                directory=out / "formal", source_backend=backend)
        session.step()
        pending = session.snapshot()["payload"]["pending_source"]
        try:
            backend.claim_ready(pending["receipt_id"], worker_id="unreleased-probe")
        except PendingExecution:
            pass
        else:
            raise AssertionError("Native worker released before formal checkpoint")
        session.persist(out / "PENDING.json")
        assert (out / "PENDING.json.formal.json").exists()
        ready = next((out / "spool").glob("*.ready.json"))
        assert read(ready)["checkpoint_file_sha256"] == digest(out / "PENDING.json")
    elif mode == "deliver":
        pending = read(out / "PENDING.json")["payload"]["pending_source"]
        backend.claim_ready(pending["receipt_id"], worker_id="actual-native-disk-worker")
        request = out / "spool" / (pending["ticket"]["remote_id"] + ".request.json")
        command = [sys.executable, str(out / "source/native_source_worker.py"), "--request", str(request), "--data", str(out / "DATA.json")]
        subprocess.run(command, check=True, timeout=60)
    elif mode == "restore":
        session = FormalSession.restore(out / "PENDING.json", data, bank, directory=out / "formal", source_backend=backend)
        report = session.finish(max_steps=30)
        publish(out / "REPORT.json", report)
        publish(out / "FINAL.json", session.snapshot())
        AdmissionEngine.restore(report["event_replay"]).write_journal(out / "admission.jsonl")
    else:
        stop_sha = digest(out / "formal/STOP.json")
        try:
            FormalSession.restore(out / "PENDING.json", data, bank, directory=out / "formal", source_backend=backend)
        except ValueError as exc:
            assert "stopped" in str(exc)
        else:
            raise AssertionError("Stopped formal session reopened")
        assert stop_sha == digest(out / "formal/STOP.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["main", "create", "deliver", "restore", "closed_probe"])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.out.absolute()) if args.mode == "main" else stage(args.mode, args.out.absolute())
