"""Durable elapsed delivery time, separate from provider compute charges."""

import math
import time


def elapsed_us(ledger, call_id):
    return ledger.entries[call_id].get("timing", {}).get("elapsed_us", 0)


def invoke(backend, args, call_id, ledger, *, ticket=None, policy="backend_receipt_v1"):
    if policy not in {"backend_receipt_v1", "lifecycle_wall_v1"}:
        raise ValueError("Unknown pending timing policy")
    measured = policy == "lifecycle_wall_v1"
    if measured:
        ledger.record_execution_timing(
            call_id, time.time_ns(), "dispatch" if ticket is None else "poll"
        )
    try:
        result = backend(*args) if ticket is None else backend.resolve(ticket, call_id)
    except BaseException:
        if measured:
            ledger.record_execution_timing(call_id, time.time_ns(), "interrupted")
        raise
    if measured:
        ledger.record_execution_timing(call_id, time.time_ns(), "returned")
        raw, details = result
        if isinstance(details, dict):
            details = dict(details)
            stated = details.get("elapsed_seconds", details.get("seconds"))
            compute = details.get("seconds")
            if (
                type(stated) in (int, float)
                and math.isfinite(stated)
                and type(compute) in (int, float)
                and math.isfinite(compute)
                and stated >= compute >= 0
            ):
                details["provider_elapsed_seconds"] = stated
                details["elapsed_seconds"] = max(stated, elapsed_us(ledger, call_id) / 1_000_000)
                details["delivery_timing_policy"] = policy
        return raw, details
    return result
