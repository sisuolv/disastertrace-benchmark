"""Execution identity and observed-cost accounting for controlled backends."""

import inspect
import json
import math
import time
import types

from .targets import canonical_hash


class PendingExecution(Exception):
    """A durable dispatch exists; resolution must poll its original remote ticket."""

    def __init__(self, ticket):
        if not isinstance(ticket, dict) or not ticket.get("remote_id"):
            raise ValueError("Pending execution requires a durable remote identity")
        self.ticket = json.loads(json.dumps(ticket, sort_keys=True, allow_nan=False))
        super().__init__("Original remote execution remains pending")


def _constant_identity(value):
    if isinstance(value, types.CodeType):
        return _code_identity(value)
    if isinstance(value, (tuple, frozenset)):
        items = [_constant_identity(v) for v in value]
        if isinstance(value, frozenset):
            items.sort(key=canonical_hash)
        return {"kind": type(value).__name__, "items": items}
    return {"kind": type(value).__name__, "value": repr(value)}


def _code_identity(code):
    constants = [_constant_identity(value) for value in code.co_consts]
    return {
        "bytecode": code.co_code.hex(),
        "constants": constants,
        "names": code.co_names,
        "arguments": code.co_argcount,
    }


def _callback_configuration(value):
    if value is None or type(value) in (str, bytes, int, float, bool, complex):
        return _constant_identity(value)
    if isinstance(value, (tuple, frozenset)):
        items = [_callback_configuration(v) for v in value]
        if isinstance(value, frozenset):
            items.sort(key=canonical_hash)
        return {"kind": type(value).__name__, "items": items}
    if inspect.isfunction(value):
        return {"function": _code_identity(value.__code__)}
    # Mutable runtime state is not a model specification; real adapters declare one.
    return {"runtime_type": type(value).__module__ + "." + type(value).__qualname__}


def execution_identity(backend):
    if backend is None:
        return {"kind": "program", "implementation": "frozen_frequency.v1"}
    declared = getattr(backend, "execution_contract", None)
    if not callable(backend):
        raise TypeError("Backend must be callable")
    function = backend if inspect.isfunction(backend) else backend.__call__
    code = getattr(function, "__code__", None)
    if code is None:
        raise ValueError("Backend requires a bindable implementation")
    identity = {
        "kind": "declared_model" if declared is not None else "python_callback",
        "implementation_sha256": canonical_hash(_code_identity(code)),
    }
    resolver = getattr(backend, "resolve", None)
    if resolver is not None:
        resolver_code = getattr(resolver, "__code__", None)
        if not callable(resolver) or resolver_code is None:
            raise ValueError("Pending resolver requires a bindable implementation")
        identity["resolver_implementation_sha256"] = canonical_hash(_code_identity(resolver_code))
    committer = getattr(backend, "commit_checkpoint", None)
    if committer is not None:
        code = getattr(committer, "__code__", None)
        if not callable(committer) or code is None:
            raise ValueError("Checkpoint committer requires a bindable implementation")
        identity["committer_implementation_sha256"] = canonical_hash(_code_identity(code))
    if declared is not None:
        required = {"model", "weights", "tokenizer", "adapter", "generation", "runtime"}
        if not isinstance(declared, dict) or not required <= set(declared):
            raise ValueError("Incomplete model execution contract")
        identity["declared"] = declared
    else:
        closure = getattr(function, "__closure__", None) or ()
        configuration = {
            "defaults": _callback_configuration(getattr(function, "__defaults__", None)),
            "keyword_defaults": {
                k: _callback_configuration(v)
                for k, v in (getattr(function, "__kwdefaults__", None) or {}).items()
            },
            "immutable_closure": [_callback_configuration(cell.cell_contents) for cell in closure],
        }
        identity["configuration_sha256"] = canonical_hash(configuration)
    return identity


def bind_execution(config, backend):
    identity = execution_identity(backend)
    existing = config.get("execution_contract")
    if existing is not None and existing != identity:
        raise ValueError("Backend execution contract differs from frozen identity")
    return {**config, "execution_contract": identity}


def observe_reserved_backend(backend, system, request, call_id, ledger, *, ticket=None):
    """Keep an unknown reserve when a dispatched call has no trustworthy receipt."""
    from .resources import Cost

    start = time.perf_counter()
    raw = None
    ledger.bind_request(
        call_id,
        {
            "request_sha256": canonical_hash({"system": system, "request": request}),
            "execution_sha256": canonical_hash(execution_identity(backend)),
        },
    )
    try:
        if ticket is None:
            raw, details = backend(system, request, call_id)
        else:
            raw, details = backend.resolve(ticket, call_id)
        if (
            not isinstance(raw, str)
            or not isinstance(details, dict)
            or type(details.get("seconds")) not in (int, float)
            or not math.isfinite(details["seconds"])
            or details["seconds"] < 0
            or type(details.get("elapsed_seconds", details["seconds"])) not in (int, float)
            or not math.isfinite(details.get("elapsed_seconds", details["seconds"]))
            or details.get("elapsed_seconds", details["seconds"]) < details["seconds"]
            or any(
                type(details.get(k)) is not int or details[k] < 0
                for k in ("input_tokens", "output_tokens")
            )
        ):
            raise ValueError("Invalid observed backend receipt")
    except PendingExecution as exc:
        if callable(getattr(backend, "resolve", None)):
            if ticket is not None and exc.ticket != ticket:
                raise ValueError("Resolver changed the original pending ticket") from exc
            raise
        diagnostic = {
            "error_type": "MissingOriginalTicketResolver",
            "observed_wall_seconds": time.perf_counter() - start,
        }
        ledger.mark_unknown(call_id, diagnostic)
        return (
            None,
            diagnostic,
            max(1, math.ceil(diagnostic["observed_wall_seconds"] * 1_000_000)),
            "unknown_execution",
        )
    except Exception as exc:  # noqa: BLE001 - dispatched calls retain an unknown reservation.
        diagnostic = {
            "error_type": type(exc).__name__,
            "observed_wall_seconds": time.perf_counter() - start,
        }
        ledger.mark_unknown(call_id, diagnostic)
        duration = max(1, math.ceil(diagnostic["observed_wall_seconds"] * 1_000_000))
        return raw if isinstance(raw, str) else None, diagnostic, duration, "unknown_execution"
    duration = max(1, math.ceil(details.get("elapsed_seconds", details["seconds"]) * 1_000_000))
    actual = Cost(
        tokens=details["input_tokens"] + details["output_tokens"],
        compute_ms=math.ceil(details["seconds"] * 1000),
    )
    upper = ledger.entries[call_id]["upper"]
    overrun = any(
        getattr(actual, k) > getattr(upper, k)
        for k in ("requests", "bytes", "tokens", "compute_ms")
    )
    if overrun:
        ledger.settle_observed(call_id, actual, outcome="resource_overrun")
    return raw, details, duration, "resource_overrun" if overrun else None
