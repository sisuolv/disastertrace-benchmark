"""One-attempt DeepSeek captures with a process-safe conservative fee ledger."""

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from .spool_backend import publish, read

# Peak USD per token in nanodollars, bound to the 2026-09-14 official price capture.
RATES = {"deepseek-flash": (300, 1200), "deepseek-v4-pro": (1320, 3960)}


class ApiBudget:
    def __init__(self, path):
        self.path = Path(path)

    def transact(self, call_id, reserve=None, *, actual=None, outcome=None):
        with self.path.with_suffix(".lock").open("a+") as lock:
            # AFS can return EAGAIN even for LOCK_EX; retry only the local lock.
            deadline = time.monotonic() + 60
            while True:
                try:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("API ledger lock unavailable; no HTTP retry") from None
                    time.sleep(0.01)
            state = read(self.path)
            calls = state["calls"]
            if reserve is not None:
                if type(reserve) is not int or reserve < 0 or call_id in calls:
                    raise ValueError("Invalid or duplicate API reservation")
                charged = sum(
                    r["actual"] if r["status"] == "settled" else r["reserved"]
                    for r in calls.values()
                )
                if (
                    len(calls) >= state["max_calls"]
                    or charged + reserve > state["limit_nanodollars"]
                ):
                    raise ValueError("Registered API budget exhausted")
                calls[call_id] = {"reserved": reserve, "status": "reserved"}
            else:
                row = calls[call_id]
                if row["status"] != "reserved":
                    raise ValueError("API request already has a disposition")
                if outcome == "unknown":
                    row["status"] = "unknown"
                elif type(actual) is int and actual >= 0:
                    row.update(status="settled", actual=actual, overrun=actual > row["reserved"])
                    if row["overrun"]:
                        state["stopped_on_overrun"] = True
                else:
                    raise ValueError("Original measured token usage required")
            if reserve is not None and state.get("stopped_on_overrun"):
                raise ValueError("API fee overrun requires review; no further calls")
            temporary = self.path.with_suffix(".next")
            with temporary.open("w") as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path)
            fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)


def capture(messages, model, call_id, directory, budget, *, max_tokens=512, input_cap=32768):
    """The key is an HTTP header only; original messages and strict outputs persist."""
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    if model not in RATES or type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("Model/settings outside the registered API adapter")
    input_upper = sum(len(m["content"].encode()) for m in messages) + 4096
    if input_upper > input_cap:
        raise ValueError("Conservative UTF-8 input allowance exceeds the frozen cap")
    input_rate, output_rate = RATES[model]
    budget.transact(call_id, input_cap * input_rate + max_tokens * output_rate)
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
    }
    publish(
        directory / "REQUEST.json",
        {
            "call_id": call_id,
            "payload": payload,
            "fee_reservation_nanodollars": input_cap * input_rate + max_tokens * output_rate,
            "input_upper_basis": "UTF-8 bytes plus 4096 framing allowance; validated against returned usage",
            "started_wall_ns": time.time_ns(),
        },
    )
    key_path = Path(
        os.environ.get(
            "DISASTERTRACE_DEEPSEEK_KEY_FILE",
            "/mnt/afs/260010168/.config/disastertrace/deepseek_followup_20260914.key",
        )
    )
    started, response_bytes, status, key = time.perf_counter(), b"", None, ""
    try:
        key = key_path.read_text().strip()
        request = Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload, allow_nan=False).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            method="POST",
        )
        with build_opener(ProxyHandler({})).open(request, timeout=120) as response:
            status = response.status
            response_bytes = response.read(4_000_001)
        if len(response_bytes) > 4_000_000:
            raise ValueError("API response exceeds capture limit")
        safe_bytes = response_bytes.replace(key.encode(), b"[REDACTED]") if key else response_bytes
        wire_path = directory / "RESPONSE.body"
        with wire_path.open("xb") as wire:
            wire.write(safe_bytes)
            wire.flush()
            os.fsync(wire.fileno())
        publish(
            directory / "WIRE_RECEIPT.json",
            {
                "http_status": status,
                "stored_body_sha256": hashlib.sha256(safe_bytes).hexdigest(),
                "original_body_sha256": hashlib.sha256(response_bytes).hexdigest(),
                "redaction_applied": safe_bytes != response_bytes,
                "received_wall_ns": time.time_ns(),
                "elapsed_seconds": time.perf_counter() - started,
            },
        )
        decoded = json.loads(response_bytes)
        usage = decoded["usage"]
        input_tokens, output_tokens = usage["prompt_tokens"], usage["completion_tokens"]
        if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)):
            raise ValueError("Invalid API usage receipt")
        choice = decoded["choices"][0]
        raw = choice["message"]["content"]
        if not isinstance(raw, str):
            raise TypeError("API response has no final text")
        cost = input_tokens * input_rate + output_tokens * output_rate
        seconds = time.perf_counter() - started
        safe_response = response_bytes.decode().replace(key, "[REDACTED]")
        publish(
            directory / "RESPONSE.json",
            {
                "http_status": status,
                "body": json.loads(safe_response),
                "original_body_sha256": hashlib.sha256(response_bytes).hexdigest(),
                "redaction_applied": safe_response != response_bytes.decode(),
                "elapsed_seconds": seconds,
                "peak_tariff_cost_upper_nanodollars": cost,
                "provider_compute_seconds": None,
            },
        )
        # Persist the original answer before a separate billing update can fail.
        budget.transact(call_id, actual=cost)
        return raw, {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "seconds": seconds,
            "elapsed_seconds": seconds,
            "ended_with_eos": choice["finish_reason"] == "stop",
            "timing_basis": "measured HTTP duration; API server compute unknown",
            "model_returned": decoded.get("model"),
            "usage": usage,
            "fee_upper_nanodollars": cost,
            "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
        }
    except Exception as exc:  # noqa: BLE001 - retain every dispatched failure and its reservation.
        body_read_error = None
        if isinstance(exc, HTTPError):
            status = exc.code
            try:
                response_bytes = exc.read(20000)
            except Exception as body_error:  # noqa: BLE001 - a broken error stream is evidence too.
                body_read_error = type(body_error).__name__
            safe = response_bytes.replace(key.encode(), b"[REDACTED]") if key else response_bytes
            with (directory / "ERROR.body").open("xb") as wire:
                wire.write(safe)
                wire.flush()
                os.fsync(wire.fileno())
        # This receipt must not depend on the same ledger that may have failed.
        publish(
            directory / "FAILURE.json",
            {
                "error_type": type(exc).__name__,
                "http_status": status,
                "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
                "elapsed_seconds": time.perf_counter() - started,
                "logical_retry": False,
                "error_body_read_error": body_read_error,
            },
        )
        try:
            state = read(budget.path)
            if state["calls"][call_id]["status"] == "reserved":
                budget.transact(call_id, outcome="unknown")
        except Exception as ledger_error:  # noqa: BLE001 - keep the reservation unresolved.
            publish(directory / "LEDGER_FAILURE.json", {
                "error_type": type(ledger_error).__name__,
                "reservation_disposition": "unresolved",
                "logical_retry": False,
            })
        raise RuntimeError(
            "Original API attempt failed; receipt and reservation retained"
        ) from None
