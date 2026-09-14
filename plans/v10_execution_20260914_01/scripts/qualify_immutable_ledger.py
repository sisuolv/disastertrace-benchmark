"""Actual AFS multiprocess fixture writes and post-fsync process-crash recovery."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_v1.api_capture_v2 import store_body
from disastertrace.monitoring_v1.api_ledger import ApiLedger, call_spec
from disastertrace.monitoring_v1.spool_backend import publish

MESSAGES = [{"role": "user", "content": "Offline JSON ledger fixture; no HTTP"}]


def work(args):
    path, call_id, crash = args
    import fcntl

    def fail_lock(*args, **kwargs):
        raise BlockingIOError("AFS lock intentionally unavailable")

    fcntl.flock = fail_lock
    ledger = ApiLedger(path)
    spec = ledger.claim(call_id, MESSAGES)
    payload = {
        "model": spec["model"],
        "messages": MESSAGES,
        "stream": False,
        "temperature": 0,
        "max_tokens": spec["max_tokens"],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
    }
    ledger.write(
        call_id,
        "request.json",
        {"payload": payload, "request_sha256": spec["request_sha256"]},
    )
    ledger.write(
        call_id,
        "dispatch.json",
        {
            "call_id": call_id,
            "kind": "durable_pre_http_intent_not_server_ack",
            "synthetic_no_http": True,
            "wall_ns": time.time_ns(),
        },
    )
    body = json.dumps(
        {
            "usage": {"prompt_tokens": 20, "completion_tokens": 5},
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
        }
    ).encode()
    store_body(ledger.attempt(call_id) / "response.raw", body)
    sha = hashlib.sha256(body).hexdigest()
    ledger.write(
        call_id, "wire.json", {"stored_body_sha256": sha, "original_body_sha256": sha}
    )
    if crash:
        os._exit(77)
    ledger.write(call_id, "billing.json", ledger.measured_bill(call_id))
    ledger.write(call_id, "terminal.json", {"state": "BILLED", "synthetic": True})
    return call_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--crash", action="store_true")
    args = parser.parse_args()
    if args.crash:
        work((args.out / "ledger", "crash", True))
        return
    args.out.mkdir(exist_ok=False)
    call_ids = [str(i) for i in range(64)] + ["crash"]
    ledger = ApiLedger.create(
        args.out / "ledger",
        [
            call_spec(cid, MESSAGES, "deepseek-flash", input_cap=8192)
            for cid in call_ids
        ],
        limit_nanodollars=300_000_000,
        max_calls=len(call_ids),
        deadline_wall_ns=time.time_ns() + 3600_000_000_000,
    )
    with ProcessPoolExecutor(max_workers=4) as pool:
        completed = list(
            pool.map(work, [(args.out / "ledger", cid, False) for cid in call_ids[:-1]])
        )
    before = ledger.reduce()
    if before["settled"] != 64 or before["claimed"] != 64:
        raise ValueError("Concurrent fixture count mismatch")
    crash = subprocess.run(
        [sys.executable, __file__, "--out", str(args.out), "--crash"], check=False
    )
    if crash.returncode != 77:
        raise ValueError("Crash fault was not exercised")
    interrupted = ledger.reduce()
    if interrupted["unresolved_reservations"] != 1:
        raise ValueError("Lost crashed reservation")
    ledger.reconcile("crash")
    after = ledger.reduce()
    if after["reconciled"] != 1 or after["unresolved_reservations"] != 0:
        raise ValueError("Recovery mismatch")
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "parallel_fixture_processes": 4,
            "concurrent_completed_calls": len(completed),
            "crash_exit": crash.returncode,
            "before": before,
            "interrupted": interrupted,
            "after": after,
            "http_requests": 0,
            "model_calls": 0,
            "scope": "real AFS process/write behavior, synthetic provider bytes",
        },
    )
    print(
        json.dumps(
            {
                "passed": True,
                "settled": after["settled"],
                "reconciled": after["reconciled"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
