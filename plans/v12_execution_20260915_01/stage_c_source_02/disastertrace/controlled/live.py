"""Durable P2 collection, explicit diagnostics and credential-free offline recovery."""

import argparse
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.budget_ledger import BudgetLedger
from disastertrace.automated.common import canonical, strict_json, write_json
from disastertrace.automated.provider import ProviderConfig, ProviderError
from disastertrace.automated.run_store import RunStore, durable_json, read_events

from . import public_oracle
from .execution import (
    contract_version,
    prepare_execution,
    read,
    validate_attestation,
    validate_authorization,
    verify_execution,
)
from .live_audit import _audit_verified, audit_run
from .output_contract import V1, VERSIONS
from .provider_adapter import prepare
from .provider_capture import parse_capture, send_prepared
from .renderer import render_request
from .schema import parse_decision


def collect(
    execution,
    output,
    *,
    transport=None,
    registry=None,
    resume=False,
    authorization=None,
    price_attestation=None,
    offline_only=False,
    fault=None,
):
    plan = verify_execution(execution)
    output = Path(output)
    credential = None
    if offline_only:
        if not resume or transport is not None:
            raise ValueError("offline recovery requires an existing run and no transport")
        events = read_events(output)
        if not events or events[0]["kind"] != "binding":
            raise ValueError("missing existing execution binding")
        binding = events[0]["data"]
        mode = binding["mode"]
        registry = Path(binding["registry_path"]) if registry is None else Path(registry).resolve()
        if str(registry) != binding["registry_path"]:
            raise ValueError("offline recovery registry changed")
    else:
        mode = (
            "injected_transport_unverified"
            if transport is not None
            else "loopback_http_fixture"
            if plan["execution_kind"] == "loopback_fixture"
            else "model_http"
        )
        default_registry = (
            output.resolve().parent / "diagnostic_registry"
            if transport is not None
            else Path(plan["registry_path"])
        )
        registry = Path(registry).resolve() if registry is not None else default_registry
        if (mode == "injected_transport_unverified") == (str(registry) == plan["registry_path"]):
            raise ValueError("diagnostic/live registry override is not allowed")
        if mode == "model_http":
            validate_authorization(plan, authorization)
            validate_attestation(plan, price_attestation)
            credential = os.environ.get(plan["config"]["key_env"])
            if (
                not isinstance(credential, str)
                or not credential
                or any(ord(c) < 33 or ord(c) > 126 for c in credential)
            ):
                raise ValueError("valid provider credential required; no attempt started")
        elif transport is not None:
            credential = "diagnostic-fixture-credential"
        binding = {
            "execution_id": plan["execution_id"],
            "mode": mode,
            "authorization": authorization if mode == "model_http" else None,
            "registry_path": str(registry),
        }
    with RunStore(output, plan["execution_id"], registry, resume=resume) as store:
        if not store.events:
            store.append("binding", binding)
        elif canonical(store.events[0]["data"]) != canonical(binding):
            raise ValueError("resume mode, registry or authorization changed")
        audit = _audit_verified(plan, output)
        if audit["stop_reason"] or audit["complete"]:
            return _summary(plan, audit)
        if mode == "model_http" and not offline_only:
            store.append(
                "price_attestation",
                {
                    "attestation": price_attestation,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        ledger = BudgetLedger(plan["budget"])
        for row in audit["accounting_rows"]:
            ledger.reserve(row["attempt_id"], row["cap"])
            if row["status"] == "settled":
                ledger.settle(row["attempt_id"], row["usage"])
        history, pending = audit["histories"], audit["pending"]
        episodes = {ep["episode_id"]: ep for ep in plan["episodes"]}
        config = ProviderConfig.from_dict(plan["config"])
        version = contract_version(plan)

        def boundary(kind, index):
            if fault is not None:
                fault(kind, index)

        for index in range(audit["completed"], plan["planned_opportunities"]):
            if offline_only and (pending is None or pending["phase"] == "reserved"):
                break
            slot = plan["schedule"][index]
            prefix = history.get(slot["trajectory_id"], [])
            previous = prefix[-1] if prefix else None
            request = render_request(
                episodes[slot["episode_id"]],
                slot["checkpoint_id"],
                method=slot["method"],
                previous=previous,
                history=prefix,
            )
            prepared = prepare(request, config, output_contract=version)
            attempt = f"{plan['execution_id']}:{index}"
            if pending is None:
                if len(prepared["raw_request"].encode()) > plan["budget"]["max_request_bytes"]:
                    store.append("halt", {"slot_index": index, "reason": "request_bytes_guard"})
                    break
                try:
                    reservation = ledger.reserve(attempt, config.max_output_tokens)
                except ValueError:
                    store.append("halt", {"slot_index": index, "reason": "budget_guard"})
                    break
                store.append(
                    "reserved",
                    {
                        "slot_index": index,
                        "request": request,
                        "prepared": prepared,
                        "reservation": reservation,
                    },
                )
                boundary("reserved", index)
                pending = {"phase": "reserved"}
            if pending["phase"] == "reserved":
                if mode == "model_http":
                    validate_attestation(plan, price_attestation)
                store.append(
                    "send_intent",
                    {"slot_index": index, "send_intent_at": datetime.now(timezone.utc).isoformat()},
                )
                boundary("send_intent", index)
                captured = send_prepared(
                    prepared,
                    total_deadline=plan["total_deadline_seconds"],
                    transport=transport,
                    credential=credential,
                )
                store.append(
                    "capture",
                    {
                        "slot_index": index,
                        "capture": captured,
                        "capture_observed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                boundary("capture", index)
            else:
                captured = pending["capture"]
            try:
                completion = parse_capture(captured, prepared)
                if completion["metadata"]["response_model"] != config.model:
                    raise ValueError("model_mismatch")
                settlement = ledger.settle(attempt, completion["metadata"]["usage"])
            except (ValueError, ProviderError):
                store.append("halt", {"slot_index": index, "reason": "capture_or_usage_invalid"})
                break
            if pending["phase"] != "settled":
                store.append("settled", {"slot_index": index, "settlement": settlement})
                boundary("settled", index)
            raw, status, after = completion["raw_response"], "invalid", previous
            try:
                after = parse_decision(raw)
            except (ValueError, TypeError, KeyError, RecursionError):
                pass
            else:
                status = "ok"
                history.setdefault(slot["trajectory_id"], []).append(deepcopy(after))
            store.append(
                "decision",
                {"slot_index": index, "status": status, "raw_response": raw, "state_after": after},
            )
            boundary("decision", index)
            pending = None
        result = _summary(plan, _audit_verified(plan, output))
        durable_json(output / "summary.json", result)
        return result


def _summary(plan, audit):
    return {
        **({"output_contract": plan["output_contract"]} if "output_contract" in plan else {}),
        "execution_id": plan["execution_id"],
        "planned": plan["planned_opportunities"],
        "completed": audit["completed"],
        "received": audit["received"],
        "status": audit["stop_reason"] or ("complete" if audit["complete"] else "incomplete"),
        "mode": audit["mode"],
        "model_api_calls": audit["model_api_calls"],
        "budget": audit["budget"],
        "audit_id": audit["audit_id"],
    }


def diagnostic_transport(endpoint, body, headers, timeout, maximum):
    wire = strict_json(body.decode())
    request = strict_json(wire["messages"][1]["content"])
    return 200, canonical(
        {
            "model": wire["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": canonical(public_oracle.answer(request)),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
        }
    ).encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--dataset", type=Path, required=True)
    prep.add_argument("--rates", type=Path, required=True)
    prep.add_argument("--price-document", type=Path)
    prep.add_argument("--registry", type=Path, required=True)
    prep.add_argument("--allowance-usd", default="3.00")
    prep.add_argument("--output-contract", choices=VERSIONS, default=V1)
    prep.add_argument("--output", type=Path, required=True)
    for name in (
        "verify",
        "rehearse",
        "run",
        "resume",
        "recover",
        "audit",
        "report",
        "verify-report",
    ):
        cmd = commands.add_parser(name)
        cmd.add_argument("--execution", type=Path, required=True)
        if name != "verify":
            cmd.add_argument("--output", type=Path, required=name not in {"audit"})
        if name in {"audit", "report", "verify-report"}:
            cmd.add_argument("--run", type=Path, required=True)
        if name in {"run", "resume"}:
            cmd.add_argument("--authorization", type=Path, required=True)
            cmd.add_argument("--price-attestation", type=Path, required=True)
        if name == "rehearse":
            cmd.add_argument("--registry", type=Path)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_execution(
            args.dataset,
            args.output,
            rates=args.rates,
            registry=args.registry,
            allowance_usd=args.allowance_usd,
            price_document=args.price_document,
            output_contract=args.output_contract,
        )
    elif args.command == "verify":
        result = verify_execution(args.execution)
    elif args.command == "audit":
        result = audit_run(args.execution, args.run)
        if args.output:
            if args.output.exists():
                raise ValueError("audit output exists")
            write_json(args.output, result)
    elif args.command == "report":
        from .live_report import report_run

        result = report_run(args.execution, args.run, args.output)
    elif args.command == "verify-report":
        from .live_report import verify_report

        result = verify_report(args.execution, args.run, args.output)
    else:
        result = collect(
            args.execution,
            args.output,
            transport=diagnostic_transport if args.command == "rehearse" else None,
            registry=args.registry if args.command == "rehearse" else None,
            resume=args.command in {"resume", "recover"},
            offline_only=args.command == "recover",
            authorization=read(args.authorization) if args.command in {"run", "resume"} else None,
            price_attestation=read(args.price_attestation)
            if args.command in {"run", "resume"}
            else None,
        )
    print(
        canonical(
            {
                k: v
                for k, v in result.items()
                if k
                not in {
                    "episodes",
                    "schedule",
                    "source_identity",
                    "environment_identity",
                    "dataset_manifest",
                    "records",
                    "histories",
                    "pending",
                    "accounting_rows",
                    "methods",
                    "operations",
                    "budget",
                }
            }
        )
    )


if __name__ == "__main__":
    main()
