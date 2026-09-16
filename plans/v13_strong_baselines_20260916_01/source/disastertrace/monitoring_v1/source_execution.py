"""Observed transport for one immutable, registered native archive query."""

import json
import math
import time

from .execution import PendingExecution, execution_identity
from .resources import Cost
from .targets import canonical_hash


def source_identity(backend):
    if backend is None:
        return None
    contract = getattr(backend, "source_contract", None)
    if not isinstance(contract, dict) or not contract:
        raise ValueError("Source transport needs an explicit source execution contract")
    return {
        **execution_identity(backend),
        "kind": "registered_source_transport",
        "source_contract": json.loads(json.dumps(contract, allow_nan=False)),
    }


def bind_source(config, backend):
    identity = source_identity(backend)
    if "source_execution_contract" in config and config["source_execution_contract"] != identity:
        raise ValueError("Backend source execution contract differs from frozen identity")
    if identity is None:
        return config
    if (
        config.get("session_runtime") != "typed_admission_v1"
        or config.get("isolation_mode") != "actual_cost_clock"
    ):
        raise ValueError("Observed source transport requires typed admission and actual cost clock")
    return {**config, "source_execution_contract": identity}


def observe_source(
    backend,
    request,
    receipt_id,
    ledger,
    registered,
    *,
    ticket=None,
    timing_policy="backend_receipt_v1",
):
    """A response pays its observed cost before it can grant a native asset."""
    started = time.perf_counter()
    minimum_us = request["catalog"]["latency_ms"] * 1000
    details, product, size = {}, None, None
    ledger.bind_request(
        receipt_id,
        {
            "request_sha256": canonical_hash(request),
            "execution_sha256": canonical_hash(source_identity(backend)),
        },
    )
    try:
        from .lifecycle import invoke

        product, details = invoke(
            backend, (request, receipt_id), receipt_id, ledger, ticket=ticket, policy=timing_policy
        )
        if (
            not isinstance(details, dict)
            or any(
                type(details.get(k)) not in (int, float)
                or not math.isfinite(details[k])
                or details[k] < 0
                for k in ("seconds", "elapsed_seconds")
            )
            or details["elapsed_seconds"] < details["seconds"]
        ):
            raise ValueError("Untrusted source timing receipt")
        size = len(json.dumps(product, separators=(",", ":"), allow_nan=False).encode())
        duration = max(minimum_us, math.ceil(details["elapsed_seconds"] * 1_000_000))
        actual = Cost(requests=1, bytes=size, compute_ms=math.ceil(details["seconds"] * 1000))
    except PendingExecution as exc:
        if callable(getattr(backend, "resolve", None)):
            if ticket is not None and ticket != exc.ticket:
                raise ValueError("Source resolver changed the original ticket") from exc
            raise
        details = {"error_type": "MissingOriginalTicketResolver"}
        ledger.mark_unknown(receipt_id, details)
        return None, details, minimum_us, "unknown_execution", None
    except Exception as exc:  # noqa: BLE001 - dispatched source may still incur a charge.
        details = {
            "error_type": type(exc).__name__,
            "observed_wall_seconds": time.perf_counter() - started,
        }
        from .lifecycle import elapsed_us

        details["observed_wall_seconds"] = max(
            details["observed_wall_seconds"], elapsed_us(ledger, receipt_id) / 1_000_000
        )
        try:
            json.dumps(product, allow_nan=False)
        except (TypeError, ValueError):
            details["unserializable_product_type"] = type(product).__name__
            product = None
        ledger.mark_unknown(receipt_id, details)
        duration = max(minimum_us, math.ceil(details["observed_wall_seconds"] * 1_000_000))
        return product, details, duration, "unknown_execution", size
    upper = ledger.entries[receipt_id]["upper"]
    overrun = any(
        getattr(actual, k) > getattr(upper, k)
        for k in ("requests", "bytes", "tokens", "compute_ms")
    )
    matched = (
        isinstance(product, dict)
        and "status" in product
        and canonical_hash(product) == canonical_hash(registered)
    )
    status = "resource_overrun" if overrun else "source_identity_mismatch" if not matched else None
    ledger.settle_observed(receipt_id, actual, outcome=status or "completed")
    return product, details, duration, status, size
