"""Preallocated per-call escrow with immutable receipts and deterministic reduction.

All call ceilings are reserved in the contract before dispatch. Unused allowances
are not recycled into other calls, so workers never contend on a shared balance.
"""

import hashlib
import json
import time
from pathlib import Path

from ..forecast_task.common import strict_json
from .api_capture import RATES
from .spool_backend import digest, publish, read
from .targets import canonical_hash


def call_spec(call_id, messages, model, *, input_cap=32768, max_tokens=512):
    if not isinstance(call_id, str) or not call_id or model not in RATES:
        raise ValueError("Registered call/model required")
    if any(type(v) is not int or v <= 0 for v in (input_cap, max_tokens)):
        raise ValueError("Positive integer token caps required")
    if not isinstance(messages, list) or not messages or any(
        not isinstance(m, dict) or set(m) != {"role", "content"}
        or m["role"] not in {"system", "user", "assistant"} or not isinstance(m["content"], str)
        for m in messages
    ):
        raise ValueError("Text messages with explicit roles required")
    if sum(len(m["content"].encode()) for m in messages) + 4096 > input_cap:
        raise ValueError("Conservative UTF-8 request size exceeds input cap")
    payload = {"model": model, "messages": messages, "stream": False, "temperature": 0,
               "max_tokens": max_tokens, "thinking": {"type": "disabled"},
               "response_format": {"type": "json_object"}}
    ir, outr = RATES[model]
    return {"call_id": call_id, "model": model, "input_cap": input_cap, "max_tokens": max_tokens,
            "request_sha256": canonical_hash(payload), "input_rate": ir, "output_rate": outr,
            "reserved_nanodollars": input_cap * ir + max_tokens * outr}


class ApiLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.contract_sha256 = digest(self.path / "contract.json")
        self.contract = read(self.path / "contract.json")
        self.calls = {r["call_id"]: r for r in self.contract["calls"]}

    @classmethod
    def create(cls, path, calls, *, limit_nanodollars, max_calls, deadline_wall_ns):
        calls = json.loads(json.dumps(list(calls), allow_nan=False))
        if any(type(v) is not int or v <= 0 for v in (limit_nanodollars, max_calls, deadline_wall_ns)):
            raise ValueError("Finite positive API budget and deadline required")
        if not calls or len(calls) > max_calls or len({r["call_id"] for r in calls}) != len(calls):
            raise ValueError("Nonempty unique registered calls within API budget required")
        for r in calls:
            if r["model"] not in RATES or (r["input_rate"], r["output_rate"]) != RATES[r["model"]]:
                raise ValueError("Call rate differs from frozen API contract")
            if any(type(r[k]) is not int or r[k] <= 0 for k in ("input_cap", "max_tokens", "reserved_nanodollars")):
                raise ValueError("Invalid API allowance")
            if r["reserved_nanodollars"] != r["input_cap"]*r["input_rate"]+r["max_tokens"]*r["output_rate"]:
                raise ValueError("Incorrect call escrow")
        if sum(r["reserved_nanodollars"] for r in calls) > limit_nanodollars:
            raise ValueError("Preallocated API budget exceeded")
        path = Path(path)
        path.mkdir(exist_ok=False)
        (path / "attempts").mkdir()
        publish(path / "contract.json", {"schema": "disastertrace.api_escrow.v2", "calls": calls,
            "limit_nanodollars": limit_nanodollars, "max_calls": max_calls, "deadline_wall_ns": deadline_wall_ns,
            "pricing_basis": "2026-09-14 captured peak tariff; upper estimate, not invoice",
            "budget_policy": "sum of all fixed call ceilings; no recycling or network retries"})
        return cls(path)

    def attempt(self, call_id):
        if call_id not in self.calls:
            raise ValueError("Unregistered API call")
        return self.path / "attempts" / hashlib.sha256(call_id.encode()).hexdigest()

    def write(self, call_id, name, value):
        if Path(name).name != name:
            raise ValueError("Receipt basename required")
        publish(self.attempt(call_id) / name, value)

    def claim(self, call_id, messages):
        if digest(self.path / "contract.json") != self.contract_sha256:
            raise ValueError("API contract changed")
        spec = self.calls.get(call_id)
        if spec is None:
            raise ValueError("Unregistered API request")
        actual = call_spec(call_id, messages, spec["model"], input_cap=spec["input_cap"], max_tokens=spec["max_tokens"])
        if actual != spec:
            raise ValueError("API request differs from its frozen escrow")
        if time.time_ns() >= self.contract["deadline_wall_ns"] or (self.path / "STOP.json").exists():
            raise ValueError("API deadline or stop gate reached")
        self.attempt(call_id).mkdir(exist_ok=False)
        self.write(call_id, "reserve.json", {**spec, "claimed_wall_ns": time.time_ns(),
                                           "contract_sha256": self.contract_sha256})
        return spec

    def stop(self, reason):
        try:
            publish(self.path / "STOP.json", {"reason": reason, "at_wall_ns": time.time_ns()})
        except FileExistsError:
            pass

    def measured_bill(self, call_id):
        self._verify_attempt(call_id)
        directory, spec = self.attempt(call_id), self.calls[call_id]
        request = read(directory / "request.json")
        if request["request_sha256"] != spec["request_sha256"] or canonical_hash(request["payload"]) != spec["request_sha256"]:
            raise ValueError("Original request identity mismatch")
        if not (directory / "dispatch.json").exists():
            raise ValueError("No original dispatch receipt")
        wire = read(directory / "wire.json")
        body = (directory / "response.raw").read_bytes()
        if hashlib.sha256(body).hexdigest() != wire["stored_body_sha256"]:
            raise ValueError("Original response bytes changed")
        usage = strict_json(body)["usage"]
        pi, po = usage["prompt_tokens"], usage["completion_tokens"]
        if any(type(n) is not int or n < 0 for n in (pi, po)):
            raise ValueError("Invalid original token usage")
        cost = pi * spec["input_rate"] + po * spec["output_rate"]
        return {"input_tokens": pi, "output_tokens": po, "actual_upper_nanodollars": cost,
                "original_response_sha256": wire["original_body_sha256"],
                "stored_body_sha256": wire["stored_body_sha256"], "request_sha256": spec["request_sha256"],
                "overrun": pi > spec["input_cap"] or po > spec["max_tokens"] or cost > spec["reserved_nanodollars"]}

    def _verify_attempt(self, call_id):
        if digest(self.path / "contract.json") != self.contract_sha256:
            raise ValueError("API contract changed")
        directory, spec = self.attempt(call_id), self.calls[call_id]
        reserve = directory / "reserve.json"
        if reserve.exists():
            saved = read(reserve)
            if (any(saved.get(k) != v for k, v in spec.items())
                    or saved.get("contract_sha256") != self.contract_sha256):
                raise ValueError("Original reservation identity mismatch")
        dispatch = directory / "dispatch.json"
        if dispatch.exists():
            saved = read(dispatch)
            if (not reserve.exists() or saved.get("call_id") != call_id
                    or saved.get("kind") != "durable_pre_http_intent_not_server_ack"):
                raise ValueError("Original dispatch identity mismatch")

    def reconcile(self, call_id):
        directory = self.attempt(call_id)
        if (directory / "billing.json").exists():
            raise ValueError("Already billed; no reconciliation required")
        bill = self.measured_bill(call_id)
        self.write(call_id, "reconciliation.json", {**bill, "basis": "original response usage; no replacement call"})
        if bill["overrun"]:
            self.stop("original usage overrun")
        return bill

    def reduce(self):
        if digest(self.path / "contract.json") != self.contract_sha256:
            raise ValueError("API contract changed")
        counts = {k: 0 for k in ("registered", "claimed", "dispatch_intents", "responses", "settled",
                                 "reconciled", "unresolved_reservations", "unresolved_nanodollars",
                                 "actual_upper_nanodollars", "failed_pre_dispatch")}
        counts["registered"] = len(self.calls)
        known = {self.attempt(cid).name for cid in self.calls}
        if {p.name for p in (self.path / "attempts").iterdir() if p.is_dir()} - known:
            raise ValueError("Unregistered attempt directory")
        for cid, spec in self.calls.items():
            directory = self.attempt(cid)
            if not directory.exists():
                continue
            self._verify_attempt(cid)
            counts["claimed"] += 1
            dispatched = (directory / "dispatch.json").exists()
            counts["dispatch_intents"] += dispatched
            counts["responses"] += (directory / "response.raw").exists()
            terminal = read(directory / "terminal.json") if (directory / "terminal.json").exists() else {}
            billed = next((name for name in ("billing.json", "reconciliation.json") if (directory / name).exists()), None)
            if billed:
                measured, saved = self.measured_bill(cid), read(directory / billed)
                if any(saved.get(k) != v for k, v in measured.items()):
                    raise ValueError("Billing receipt disagrees with original usage")
                counts["settled" if billed == "billing.json" else "reconciled"] += 1
                counts["actual_upper_nanodollars"] += measured["actual_upper_nanodollars"]
            elif terminal.get("state") == "FAILED_PRE_DISPATCH" and not dispatched:
                counts["failed_pre_dispatch"] += 1
            else:
                counts["unresolved_reservations"] += 1
                counts["unresolved_nanodollars"] += spec["reserved_nanodollars"]
        return counts
