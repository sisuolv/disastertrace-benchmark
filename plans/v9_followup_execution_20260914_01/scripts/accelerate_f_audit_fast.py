"""Replay existing journals in processes, then run the unchanged audit/scoring code."""

from __future__ import annotations

import ast
import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
import multiprocessing
import os
import socket
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime/audit_acceleration_02"
OUTPUT = ROOT / "reports/api_forecast_audit_parallel_02"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    with pending.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, path)
    pending.unlink()


def progress(phase, **details):
    row = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": phase, **details}
    with (RUNTIME / "EVENTS.jsonl").open("a") as stream:
        stream.write(json.dumps(row) + "\n")
    pending = RUNTIME / "STATUS.next"
    pending.write_text(json.dumps(row, indent=2) + "\n")
    pending.replace(RUNTIME / "STATUS.json")
    print(json.dumps(row), flush=True)


def replay_journal(path):
    from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine

    started = time.monotonic()
    before = digest(path)
    engine = AdmissionEngine.from_journal(path)
    if digest(path) != before:
        raise ValueError("Journal changed while replaying: " + str(path))
    return str(path), engine, {"path": str(path), "sha256": before,
                               "elapsed_seconds": time.monotonic() - started, "pid": os.getpid()}


def scorer_with_replayed_engines(original, engines):
    """Use identical scoring bytecode after all original replay checks have run."""
    remaining = dict(engines)

    class AlreadyReplayed:
        @staticmethod
        def from_journal(path):
            key = str(path)
            if key not in remaining:
                raise ValueError("Unverified or reused journal: " + key)
            return remaining.pop(key)

    scope = dict(original.__globals__, AdmissionEngine=AlreadyReplayed)
    copied = types.FunctionType(original.__code__, scope, original.__name__,
                                original.__defaults__, original.__closure__)
    copied.__kwdefaults__ = original.__kwdefaults__
    return copied, remaining


def redirected_audit(module, scorer, output):
    """Only redirect the audit output assignment; preserve its full scientific body."""
    tree = ast.parse(Path(module.__file__).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "audit_f")
    assignments = [n for n in node.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "out" for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError("Reference audit output assignment changed")
    assignments[0].value = ast.Name(id="parallel_output", ctx=ast.Load())
    modified = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    scope = dict(vars(module), score_admitted=scorer, parallel_output=Path(output))
    # The local reference source is hash-bound before worker dispatch.
    exec(compile(modified, str(module.__file__), "exec"), scope)  # noqa: S102
    return scope["audit_f"]


def load_auditor(path):
    spec = importlib.util.spec_from_file_location("reference_followup_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    registration = read(RUNTIME / "REGISTRATION.json")
    if socket.gethostname() == registration["cci_host"]:
        raise ValueError("This worker must run on the registered ACP CPU node")
    if sys.version_info[:2] != (3, 10):
        raise ValueError("Preserve Python 3.10 replay semantics")
    write(RUNTIME / "WORKER_CLAIM.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "host": socket.gethostname(),
        "pid": os.getpid(), "python": sys.version,
        "cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "memory_max": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
    })
    for path, expected in registration["bound_files"].items():
        if digest(path) != expected:
            raise ValueError("Registered input changed: " + path)
    journal_paths = registration["journals"]
    if len(set(journal_paths)) != len(journal_paths):
        raise ValueError("Duplicate journal work item")
    started = time.monotonic()
    progress("PARALLEL_JOURNAL_REPLAY", total=len(journal_paths), workers=registration["workers"])
    engines, receipts = {}, []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=registration["workers"], mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [pool.submit(replay_journal, path) for path in journal_paths]
        for future in concurrent.futures.as_completed(futures):
            path, engine, receipt = future.result()
            engines[path] = engine
            receipts.append(receipt)
            if len(receipts) % 8 == 0 or len(receipts) == len(journal_paths):
                progress("PARALLEL_JOURNAL_REPLAY", completed=len(receipts), total=len(journal_paths))
    write(RUNTIME / "REPLAY_RECEIPTS.json", sorted(receipts, key=lambda r: r["path"]))
    module = load_auditor(ROOT / "scripts/analyze_api_followup.py")
    scorer, remaining = scorer_with_replayed_engines(module.score_admitted, engines)
    progress("ORIGINAL_AUDIT_CHECKS", replay_seconds=time.monotonic() - started)
    redirected_audit(module, scorer, OUTPUT)("api_pilot_01")
    if remaining:
        raise ValueError("Some verified journals were not consumed by the audit")
    for path, expected in registration["bound_files"].items():
        if digest(path) != expected:
            raise ValueError("Registered input changed during audit: " + path)
    result = read(OUTPUT / "VALIDATION.json")
    if not result["passed"] or not result["all_registered_arms_finished"] or result["unfinished_arms"]:
        raise ValueError("Original audit did not verify the full registered matrix")
    write(RUNTIME / "COMPLETE.json", {"passed": True, "journals": len(receipts),
        "records": len(result["records"]), "elapsed_seconds": time.monotonic() - started,
        "workers": registration["workers"], "new_model_calls": 0, "gpu_cards": 0,
        "validation_sha256": digest(OUTPUT / "VALIDATION.json"),
        "scoring_bytecode_unchanged": True, "original_audit_only_output_path_redirected": True})
    progress("PARALLEL_AUDIT_COMPLETE", elapsed_seconds=time.monotonic() - started)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        progress("PARALLEL_AUDIT_FAILED", error_type=type(exc).__name__, reason=str(exc))
        raise
