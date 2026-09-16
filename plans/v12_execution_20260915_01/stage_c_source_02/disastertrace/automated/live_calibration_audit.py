"""Independent reconstruction of persisted calibration exposure and accounting."""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from .common import canonical, fingerprint, write_json
from .dynamic import parse_decision
from .live_calibration import verify_execution
from .output_contract import render_calibration_request
from .provider import ProviderClient, ProviderConfig, ProviderError
from .provider_capture import parse_capture, validate_capture
from .run_store import read_events


def _utc_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() != timedelta(0):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("journal requires an explicit UTC timestamp") from None
    return parsed


def audit_run(execution: Path, output: Path) -> dict:
    plan = verify_execution(execution)
    events = read_events(output)
    if not events or events[0]["kind"] != "binding":
        raise ValueError("missing experiment binding")
    binding = events[0]["data"]
    if (
        set(binding) != {"execution_id", "mode", "authorization"}
        or binding["execution_id"] != plan["execution_id"]
        or binding["mode"] not in {"urllib_http", "injected_transport_unverified"}
    ):
        raise ValueError("invalid execution binding")
    mode = binding["mode"]
    if mode == "injected_transport_unverified" and binding["authorization"] is not None:
        raise ValueError("diagnostics cannot claim live authorization")
    if mode == "urllib_http":
        auth = binding["authorization"]
        if (
            not isinstance(auth, dict)
            or auth.get("authorized") is not True
            or auth.get("execution_id") != plan["execution_id"]
            or auth.get("allowance_usd") != plan["budget"]["allowance"]
            or auth.get("max_attempts") != 270
            or not auth.get("authorization_evidence")
            or auth.get("rates_sha256") != plan["rates_sha256"]
        ):
            raise ValueError("missing matching live authorization evidence")
    policy = plan["budget"]
    histories, records, accounting = {}, [], []
    episodes = {ep["episode_id"]: ep for ep in plan["episodes"]}
    pending, stop = None, None
    settled, reserved = Decimal(0), Decimal(0)
    received, attempts = 0, 0
    price_attested = False
    for event in events[1:]:
        kind, data = event["kind"], event["data"]
        if kind == "price_attestation":
            if (
                mode != "urllib_http"
                or set(data) != {"rates_verified_at", "rates_sha256", "recorded_at"}
                or data["rates_sha256"] != plan["rates_sha256"]
            ):
                raise ValueError("invalid price attestation")
            try:
                age = (
                    datetime.fromisoformat(data["recorded_at"])
                    - datetime.fromisoformat(data["rates_verified_at"])
                ).total_seconds()
                if not 0 <= age <= 86400:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError("invalid price attestation age") from None
            price_attested = True
            continue
        index = len(records)
        if stop or index >= 270 or data.get("slot_index") != index:
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
            request = render_calibration_request(
                episodes[slot["episode_id"]],
                slot["checkpoint_id"],
                previous,
                method=slot["method"],
                history=prefix,
                contract=slot["contract"],
            )
            prepared = ProviderClient(
                ProviderConfig.from_dict(plan["configs"][slot["cell_id"]])
            ).prepare(request)
            if request != data["request"] or prepared != data["prepared"]:
                raise ValueError("actual instruction/evidence/carrier/wire mismatch")
            if len(prepared["raw_request"].encode()) > policy["max_request_bytes"]:
                raise ValueError("request byte guard violated")
            amount = (
                policy["prompt_bound"] * Decimal(policy["input_per_million"])
                + slot["max_output_tokens"] * Decimal(policy["output_per_million"])
            ) / Decimal(1000000)
            expected = {
                "attempt_id": f"{plan['execution_id']}:{index}",
                "cap": slot["max_output_tokens"],
                "reservation": str(amount),
                "cost": "0",
                "status": "reserved",
                "usage": None,
            }
            if (
                data["reservation"] != expected
                or settled + amount > Decimal(policy["allowance"])
                or index >= policy["max_attempts"]
                or sum(r["cap"] for r in accounting) + slot["max_output_tokens"]
                > policy["max_requested_output_tokens"]
            ):
                raise ValueError("reservation or cumulative guard mismatch")
            accounting.append(expected)
            reserved = amount
            pending = {**deepcopy(data), "phase": "reserved"}
        elif kind == "send_intent":
            if (
                pending is None
                or pending["phase"] != "reserved"
                or set(data) != {"slot_index", "send_intent_at"}
            ):
                raise ValueError("send without durable reservation")
            if mode == "urllib_http" and not price_attested:
                raise ValueError("send without fresh price attestation")
            _utc_timestamp(data["send_intent_at"])
            pending.update(phase="send_intent", send_intent_at=data["send_intent_at"])
            attempts += 1
        elif kind == "capture":
            if (
                pending is None
                or pending["phase"] != "send_intent"
                or set(data) != {"slot_index", "capture", "capture_observed_at"}
            ):
                raise ValueError("capture without unique send intent")
            capture = data["capture"]
            _utc_timestamp(data["capture_observed_at"])
            validate_capture(capture, pending["prepared"])
            if (
                capture["origin"] != mode
                or capture["total_deadline_seconds"] != 180
                or (mode == "urllib_http" and capture["total_deadline_enforced"] is not True)
            ):
                raise ValueError("capture execution mode/deadline mismatch")
            received += int(capture["capture_kind"] == "complete" and capture["http_status"] == 200)
            pending.update(
                phase="capture", capture=capture, capture_observed_at=data["capture_observed_at"]
            )
        elif kind == "settled":
            if (
                pending is None
                or pending["phase"] != "capture"
                or set(data) != {"slot_index", "settlement"}
            ):
                raise ValueError("settlement without response")
            try:
                completion = parse_capture(pending["capture"], pending["prepared"])
            except ProviderError:
                raise ValueError("invalid capture cannot settle") from None
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
                or usage["completion_tokens"] > slot["max_output_tokens"]
            ):
                raise ValueError("unverified usage/model cannot settle")
            cost = (
                usage["prompt_tokens"] * Decimal(policy["input_per_million"])
                + usage["completion_tokens"] * Decimal(policy["output_per_million"])
            ) / Decimal(1000000)
            row = {
                **accounting[-1],
                "cost": str(cost),
                "usage": deepcopy(usage),
                "status": "settled",
            }
            if cost > reserved or data["settlement"] != row:
                raise ValueError("usage settlement mismatch")
            accounting[-1] = row
            settled += cost
            reserved = Decimal(0)
            pending.update(phase="settled", completion=completion)
        elif kind == "decision":
            if (
                pending is None
                or pending["phase"] != "settled"
                or set(data) != {"slot_index", "status", "raw_response", "state_after"}
            ):
                raise ValueError("decision without verified settlement")
            completion = pending["completion"]
            raw, status, after = completion["raw_response"], "invalid", previous
            try:
                after = parse_decision(raw)
            except (ValueError, TypeError, KeyError):
                pass
            else:
                status = "ok"
            if (
                data["raw_response"] != raw
                or data["status"] != status
                or data["state_after"] != after
            ):
                raise ValueError("raw answer/acceptance/carrier changed")
            records.append({**deepcopy(pending), **deepcopy(data), "slot": slot})
            if status == "ok":
                histories.setdefault(slot["trajectory_id"], []).append(deepcopy(after))
            pending = None
        elif kind == "halt":
            if set(data) != {"slot_index", "reason"} or data["reason"] not in {
                "budget_guard",
                "request_bytes_guard",
                "capture_or_usage_invalid",
            }:
                raise ValueError("invalid halt")
            stop = data["reason"]
            if pending is not None and accounting[-1]["status"] != "settled":
                accounting[-1]["status"] = "unknown"
        else:
            raise ValueError("unknown journal operation")
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
        "schema_version": "calibration_collection_audit_v1_1",
        "execution_id": plan["execution_id"],
        "mode": mode,
        "journal_tail": events[-1]["hash"],
        "planned": 270,
        "completed": len(records),
        "received": received,
        "attempts": attempts,
        "complete": len(records) == 270,
        "stop_reason": stop,
        "budget": budget,
        "provider_origin_authenticated": False,
        "model_api_calls": attempts if mode == "urllib_http" else 0,
    }
    return {
        **summary,
        "audit_id": fingerprint(summary),
        "records": records,
        "histories": histories,
        "pending": pending,
        "accounting_rows": accounting,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = audit_run(args.execution, args.run)
    summary = {
        k: v
        for k, v in result.items()
        if k not in {"records", "histories", "pending", "accounting_rows"}
    }
    if args.output:
        if args.output.exists():
            raise ValueError("audit output already exists")
        write_json(args.output, summary)
    print(canonical(summary))


if __name__ == "__main__":
    main()
