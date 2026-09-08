"""Reconstruct captured P2 exposure and accounting independently of the collector."""

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.automated.provider import ProviderConfig, ProviderError
from disastertrace.automated.run_store import read_events

from .execution import (
    read,
    utc_timestamp,
    validate_attestation,
    validate_authorization,
    verify_execution,
)
from .provider_adapter import prepare
from .provider_capture import parse_capture, validate_capture
from .renderer import render_request
from .schema import parse_decision


def _amount(policy, cap):
    return (
        policy["prompt_bound"] * Decimal(policy["input_per_million"])
        + cap * Decimal(policy["output_per_million"])
    ) / Decimal(1000000)


def _settlement(pending, policy, row):
    completion = parse_capture(pending["capture"], pending["prepared"])
    usage = completion["metadata"]["usage"]
    if (
        completion["metadata"]["response_model"] != pending["prepared"]["config"]["model"]
        or not isinstance(usage, dict)
        or any(
            type(usage.get(k)) is not int or usage[k] < 0
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        or usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]
        or usage["prompt_tokens"] > policy["prompt_bound"]
        or usage["completion_tokens"] > row["cap"]
    ):
        raise ValueError("unverified response model or usage")
    cost = (
        usage["prompt_tokens"] * Decimal(policy["input_per_million"])
        + usage["completion_tokens"] * Decimal(policy["output_per_million"])
    ) / Decimal(1000000)
    if cost > Decimal(row["reservation"]):
        raise ValueError("settlement exceeds reservation")
    return completion, {**row, "status": "settled", "usage": deepcopy(usage), "cost": str(cost)}


def audit_run(execution, output):
    return _audit_verified(verify_execution(execution), Path(output))


def _audit_verified(plan, output):
    """Internal entry for a collector that already verified the frozen execution."""
    events = read_events(output)
    if not events or events[0]["kind"] != "binding":
        raise ValueError("missing P2 execution binding")
    binding = events[0]["data"]
    if (
        not isinstance(binding, dict)
        or set(binding) != {"execution_id", "mode", "authorization", "registry_path"}
        or binding["execution_id"] != plan["execution_id"]
        or binding["mode"]
        not in {"model_http", "loopback_http_fixture", "injected_transport_unverified"}
    ):
        raise ValueError("invalid P2 execution binding")
    mode = binding["mode"]
    registry = Path(binding["registry_path"])
    if str(registry.resolve()) != binding["registry_path"]:
        raise ValueError("registry path is not canonical")
    injected = mode == "injected_transport_unverified"
    if injected == (str(registry) == plan["registry_path"]):
        raise ValueError("diagnostic and live registry scopes must be separate")
    claim = read(registry / (plan["execution_id"] + ".json"))
    if claim != {"execution_id": plan["execution_id"], "output": str(Path(output).resolve())}:
        raise ValueError("execution claim/run path mismatch")
    if mode == "model_http":
        if plan["execution_kind"] != "development_model":
            raise ValueError("fixture execution cannot claim model origin")
        validate_authorization(plan, binding["authorization"])
    elif binding["authorization"] is not None:
        raise ValueError("diagnostics cannot claim model authorization")
    if mode == "loopback_http_fixture" and plan["execution_kind"] != "loopback_fixture":
        raise ValueError("model execution cannot use a loopback origin")
    policy, cap = plan["budget"], plan["config"]["max_output_tokens"]
    histories, records, accounting = {}, [], []
    episodes = {ep["episode_id"]: ep for ep in plan["episodes"]}
    config = ProviderConfig.from_dict(plan["config"])
    pending = stop = attestation = last_time = None
    settled, reserved = Decimal(0), Decimal(0)
    received = attempts = 0

    def timestamp(value):
        nonlocal last_time
        moment = utc_timestamp(value)
        if last_time is not None and moment < last_time:
            raise ValueError("journal UTC time moved backwards")
        last_time = moment

    def budget_blocked():
        return (
            settled + _amount(policy, cap) > Decimal(policy["allowance"])
            or len(accounting) >= policy["max_attempts"]
            or sum(row["cap"] for row in accounting) + cap > policy["max_requested_output_tokens"]
        )

    for event in events[1:]:
        kind, data = event["kind"], event["data"]
        if stop or not isinstance(data, dict):
            raise ValueError("event after halt or malformed journal data")
        if kind == "price_attestation":
            if (
                mode != "model_http"
                or set(data) != {"attestation", "recorded_at"}
                or pending is not None
                and pending["phase"] != "reserved"
            ):
                raise ValueError("unexpected price attestation")
            validate_attestation(plan, data["attestation"], at=data["recorded_at"])
            timestamp(data["recorded_at"])
            attestation = data["attestation"]
            continue
        index = len(records)
        if (
            index >= plan["planned_opportunities"]
            or type(data.get("slot_index")) is not int
            or data["slot_index"] != index
        ):
            raise ValueError("out-of-order event or removed/duplicated slot")
        slot = plan["schedule"][index]
        prefix = histories.get(slot["trajectory_id"], [])
        previous = prefix[-1] if prefix else None
        if kind == "reserved":
            if pending is not None or set(data) != {
                "slot_index",
                "request",
                "prepared",
                "reservation",
            }:
                raise ValueError("overlapping reservation")
            request = render_request(
                episodes[slot["episode_id"]],
                slot["checkpoint_id"],
                method=slot["method"],
                previous=previous,
                history=prefix,
            )
            prepared = prepare(request, config)
            if canonical(request) != canonical(data["request"]) or canonical(prepared) != canonical(
                data["prepared"]
            ):
                raise ValueError("actual instruction/evidence/carrier/wire mismatch")
            if len(prepared["raw_request"].encode()) > policy["max_request_bytes"]:
                raise ValueError("request byte guard violated")
            amount = _amount(policy, cap)
            row = {
                "attempt_id": f"{plan['execution_id']}:{index}",
                "cap": cap,
                "reservation": str(amount),
                "cost": "0",
                "status": "reserved",
                "usage": None,
            }
            if canonical(data["reservation"]) != canonical(row) or budget_blocked():
                raise ValueError("reservation or cumulative guard mismatch")
            accounting.append(row)
            reserved = amount
            pending = {**deepcopy(data), "phase": "reserved"}
        elif kind == "send_intent":
            if (
                pending is None
                or pending["phase"] != "reserved"
                or set(data) != {"slot_index", "send_intent_at"}
            ):
                raise ValueError("send without durable reservation")
            if mode == "model_http":
                validate_attestation(plan, attestation, at=data["send_intent_at"])
            timestamp(data["send_intent_at"])
            pending.update(phase="send_intent", send_intent_at=data["send_intent_at"])
            attempts += 1
        elif kind == "capture":
            if (
                pending is None
                or pending["phase"] != "send_intent"
                or set(data) != {"slot_index", "capture", "capture_observed_at"}
            ):
                raise ValueError("capture without unique send intent")
            timestamp(data["capture_observed_at"])
            capture = data["capture"]
            validate_capture(capture, pending["prepared"])
            if (
                capture["origin"]
                != ("injected_transport_unverified" if injected else "urllib_http")
                or capture["total_deadline_seconds"] != plan["total_deadline_seconds"]
            ):
                raise ValueError("capture origin or deadline mismatch")
            received += int(capture["capture_kind"] == "complete" and capture["http_status"] == 200)
            pending.update(
                phase="capture",
                capture=deepcopy(capture),
                capture_observed_at=data["capture_observed_at"],
            )
        elif kind == "settled":
            if (
                pending is None
                or pending["phase"] != "capture"
                or set(data) != {"slot_index", "settlement"}
            ):
                raise ValueError("settlement without response")
            try:
                completion, row = _settlement(pending, policy, accounting[-1])
            except ProviderError:
                raise ValueError("invalid capture cannot settle") from None
            if canonical(data["settlement"]) != canonical(row):
                raise ValueError("usage settlement mismatch")
            accounting[-1] = row
            settled += Decimal(row["cost"])
            reserved = Decimal(0)
            pending.update(phase="settled", completion=completion)
        elif kind == "decision":
            if (
                pending is None
                or pending["phase"] != "settled"
                or set(data) != {"slot_index", "status", "raw_response", "state_after"}
            ):
                raise ValueError("decision without verified captured settlement")
            raw, status, after = pending["completion"]["raw_response"], "invalid", previous
            try:
                after = parse_decision(raw)
            except (ValueError, TypeError, KeyError, RecursionError):
                pass
            else:
                status = "ok"
            if (
                data["raw_response"] != raw
                or data["status"] != status
                or canonical(data["state_after"]) != canonical(after)
            ):
                raise ValueError("raw answer/acceptance/carrier changed")
            records.append(
                {**deepcopy(pending), **deepcopy(data), "slot": slot, "phase": "decision"}
            )
            if status == "ok":
                histories.setdefault(slot["trajectory_id"], []).append(deepcopy(after))
            pending = None
        elif kind == "halt":
            if set(data) != {"slot_index", "reason"}:
                raise ValueError("invalid halt")
            reason = data["reason"]
            if reason == "capture_or_usage_invalid":
                if pending is None or pending["phase"] != "capture":
                    raise ValueError("capture halt without captured response")
                try:
                    _settlement(pending, policy, accounting[-1])
                except (ValueError, ProviderError):
                    pass
                else:
                    raise ValueError("halt hides a valid response")
                accounting[-1]["status"] = "unknown"
            elif reason == "budget_guard":
                if pending is not None or not budget_blocked():
                    raise ValueError("unjustified budget halt")
            elif reason == "request_bytes_guard":
                request = render_request(
                    episodes[slot["episode_id"]],
                    slot["checkpoint_id"],
                    method=slot["method"],
                    previous=previous,
                    history=prefix,
                )
                if (
                    pending is not None
                    or len(prepare(request, config)["raw_request"].encode())
                    <= policy["max_request_bytes"]
                ):
                    raise ValueError("unjustified request byte halt")
            else:
                raise ValueError("unknown halt reason")
            stop = reason
        else:
            raise ValueError("unknown P2 journal operation")
    if pending is not None and pending["phase"] == "send_intent":
        stop = "unknown_in_flight"
        accounting[-1]["status"] = "unknown"
    budget = {
        "attempts": len(accounting),
        "settled": str(settled),
        "pending": str(reserved),
        "rows": deepcopy(accounting),
    }
    summary = {
        "schema_version": "controlled_collection_audit_v1",
        "execution_id": plan["execution_id"],
        "dataset_content_id": plan["dataset_content_id"],
        "mode": mode,
        "journal_tail": events[-1]["hash"],
        "planned": plan["planned_opportunities"],
        "completed": len(records),
        "received": received,
        "attempts": attempts,
        "complete": len(records) == plan["planned_opportunities"],
        "stop_reason": stop,
        "budget": budget,
        "provider_origin_authenticated": False,
        "model_api_calls": attempts if mode == "model_http" else 0,
    }
    return {
        **summary,
        "audit_id": fingerprint(summary),
        "records": records,
        "histories": histories,
        "pending": pending,
        "accounting_rows": accounting,
    }
