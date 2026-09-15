"""One original HTTP attempt, independent terminal receipt, no shared JSON lock."""

import hashlib
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from ..forecast_task.common import strict_json


def store_body(path, body):
    temporary = path.with_suffix(path.suffix + ".writing")
    with temporary.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, path)
    temporary.unlink()
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def capture(ledger, call_id, messages):
    spec = ledger.claim(call_id, messages)
    directory = ledger.attempt(call_id)
    payload = {
        "model": spec["model"],
        "messages": messages,
        "stream": False,
        "temperature": 0,
        "max_tokens": spec["max_tokens"],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
    }
    started, dispatched, key = time.perf_counter(), False, ""
    try:
        ledger.write(
            call_id,
            "request.json",
            {"call_id": call_id, "payload": payload, "request_sha256": spec["request_sha256"]},
        )
        key_path = Path(
            os.environ.get(
                "DISASTERTRACE_DEEPSEEK_KEY_FILE",
                "/mnt/afs/260010168/.config/disastertrace/deepseek_followup_20260914.key",
            )
        )
        key = key_path.read_text().strip()
        if not key:
            raise ValueError("Empty API credential")
        request = Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload, allow_nan=False).encode(),
            method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        )
        ledger.permit_dispatch(call_id)
        dispatched = True
        with build_opener(ProxyHandler({})).open(request, timeout=120) as response:
            status, body = response.status, response.read(4_000_001)
        safe = body.replace(key.encode(), b"[REDACTED]")
        store_body(directory / "response.raw", safe)
        ledger.write(
            call_id,
            "wire.json",
            {
                "http_status": status,
                "original_body_sha256": hashlib.sha256(body).hexdigest(),
                "stored_body_sha256": hashlib.sha256(safe).hexdigest(),
                "redaction_applied": safe != body,
                "body_hash_scope": "captured_prefix" if len(body) > 4_000_000 else "complete_body",
                "complete_body_sha256": None if len(body) > 4_000_000 else hashlib.sha256(body).hexdigest(),
                "captured_bytes": len(body),
                "truncated": len(body) > 4_000_000,
                "received_wall_ns": time.time_ns(),
                "elapsed_seconds": time.perf_counter() - started,
            },
        )
        if len(body) > 4_000_000:
            raise ValueError("Provider response exceeds bounded capture")
        decoded = strict_json(safe)
        ledger.write(call_id, "response.json", decoded)
        bill = ledger.measured_bill(call_id)
        ledger.write(call_id, "billing.json", bill)
        if bill["overrun"]:
            ledger.stop("provider token/fee allowance overrun")
            raise ValueError("Provider usage exceeded registered allowance")
        choice = decoded["choices"][0]
        raw = choice["message"]["content"]
        if not isinstance(raw, str):
            raise TypeError("No final provider text")
        seconds = time.perf_counter() - started
        details = {
            "input_tokens": bill["input_tokens"],
            "output_tokens": bill["output_tokens"],
            "seconds": seconds,
            "elapsed_seconds": seconds,
            "ended_with_eos": choice["finish_reason"] == "stop",
            "model_returned": decoded.get("model"),
            "provider_compute_seconds": None,
            "timing_basis": "client HTTP and durable capture elapsed; provider compute unknown",
            "fee_upper_nanodollars": bill["actual_upper_nanodollars"],
        }
        ledger.write(
            call_id, "terminal.json", {"state": "BILLED", "logical_retry": False, **details}
        )
        return raw, details
    except Exception as exc:  # noqa: BLE001 - preserve transport, parse and billing failures independently.
        observation = {
            "state": "FAILED_POST_DISPATCH" if dispatched else "FAILED_PRE_DISPATCH",
            "error_type": type(exc).__name__,
            "logical_retry": False,
            "elapsed_seconds": time.perf_counter() - started,
        }
        if isinstance(exc, HTTPError):
            observation["http_status"] = exc.code
            try:
                body = exc.read(20000)
                store_body(
                    directory / "error.raw",
                    body.replace(key.encode(), b"[REDACTED]") if key else body,
                )
                observation["original_error_body_sha256"] = hashlib.sha256(body).hexdigest()
            except Exception as secondary:  # noqa: BLE001 - no nested failure can erase the terminal observation.
                observation["error_body_read_error"] = type(secondary).__name__
        ledger.write(call_id, "terminal.json", observation)
        raise RuntimeError("Original API v2 attempt failed; inspect immutable receipts") from None
