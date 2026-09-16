"""Versioned calibration execution. Preparation/rehearsal never read API credentials."""

import argparse
import hashlib
import importlib.metadata
import os
import platform
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from . import calibration
from .budget_ledger import BudgetLedger, default_policy
from .common import canonical, file_hash, fingerprint, read_jsonl, strict_json, write_json
from .dynamic import diagnostic_response, parse_decision
from .output_contract import render_calibration_request
from .provider import ProviderClient, ProviderConfig, ProviderError
from .provider_capture import parse_capture, send_prepared
from .run_store import RunStore, durable_json, read_events

ROOT = Path(__file__).resolve().parents[3]
EXECUTION_PROTOCOL = ROOT / "docs/CALIBRATION_EXECUTION_V1_1.md"


def read(path):
    return strict_json(Path(path).read_text(encoding="utf-8"))


def source_identity():
    paths = sorted((ROOT / "src/disastertrace").rglob("*.py"))
    files = {str(p.relative_to(ROOT)): file_hash(p) for p in paths}
    files["docs/CALIBRATION_EXECUTION_V1_1.md"] = file_hash(EXECUTION_PROTOCOL)
    return {"files": files, "identity": fingerprint(files)}


def environment_identity():
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "packages": sorted(
            (dist.metadata["Name"].lower(), dist.version)
            for dist in importlib.metadata.distributions()
        ),
    }


def prepare_execution(preparation: Path, output: Path, *, registry: Path | None = None) -> dict:
    verified = calibration.verify(preparation)
    preparation, output = Path(preparation), Path(output)
    episodes = read_jsonl(preparation / "development_episodes.jsonl")
    configs = calibration.provider_configs(
        ProviderConfig.from_dict(read(preparation / "provider_input.json"))
    )
    configs = {
        k: asdict(replace(ProviderConfig.from_dict(v), timeout=180)) for k, v in configs.items()
    }
    source = source_identity()
    plan = {
        "schema_version": "calibration_execution_v1_1",
        "parent_preparation_id": verified["package_id"],
        "parent_protocol_sha256": file_hash(preparation / "protocol.md"),
        "execution_protocol_sha256": file_hash(EXECUTION_PROTOCOL),
        "source_identity": source,
        "environment_identity": environment_identity(),
        "episodes": episodes,
        "schedule": calibration.make_schedule(episodes),
        "configs": configs,
        "budget": default_policy(),
        "socket_timeout_seconds": 180,
        "total_deadline_seconds": 180,
        "registry_path": str(
            (
                Path(registry) if registry is not None else ROOT.parent / ".execution_claims"
            ).resolve()
        ),
        "rates": read(preparation / "rates.json"),
        "rates_raw": (preparation / "rates.json").read_text(encoding="utf-8"),
        "rates_sha256": file_hash(preparation / "rates.json"),
        "parent_manifest": read(preparation / "manifest.json"),
        "authorized": False,
        "pricing_requires_fresh_attestation": True,
        "automatic_retry": False,
        "planned_opportunities": 270,
        "state": "CALIBRATION_EXECUTION_PREPARED",
    }
    plan["execution_id"] = fingerprint(plan)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "execution.json", plan)
    (output / "execution_protocol.md").write_bytes(EXECUTION_PROTOCOL.read_bytes())
    write_json(
        output / "authorization.template.json",
        {
            "authorized": False,
            "execution_id": plan["execution_id"],
            "allowance_usd": "3.00",
            "max_attempts": 270,
            "rates_sha256": plan["rates_sha256"],
            "rates_verified_at": None,
            "authorization_evidence": None,
        },
    )
    return plan


def verify_execution(path: Path) -> dict:
    plan = read(Path(path) / "execution.json")
    if plan["execution_id"] != fingerprint({k: v for k, v in plan.items() if k != "execution_id"}):
        raise ValueError("execution identity mismatch")
    if (
        plan["schema_version"] != "calibration_execution_v1_1"
        or plan["socket_timeout_seconds"] != 180
        or plan["total_deadline_seconds"] != 180
        or plan["authorized"] is not False
        or plan["automatic_retry"] is not False
        or plan["budget"] != default_policy()
        or plan["planned_opportunities"] != 270
        or plan["source_identity"] != source_identity()
        or canonical(plan["environment_identity"]) != canonical(environment_identity())
        or file_hash(Path(path) / "execution_protocol.md") != plan["execution_protocol_sha256"]
        or plan["execution_protocol_sha256"] != file_hash(EXECUTION_PROTOCOL)
        or calibration.make_schedule(plan["episodes"]) != plan["schedule"]
    ):
        raise ValueError("execution scope or implementation drift")
    if (
        not isinstance(plan["registry_path"], str)
        or str(Path(plan["registry_path"]).resolve()) != plan["registry_path"]
    ):
        raise ValueError("registry must be a frozen canonical absolute path")
    calibration.proposed_budget(plan["rates"])
    if (
        strict_json(plan["rates_raw"]) != plan["rates"]
        or hashlib.sha256(plan["rates_raw"].encode()).hexdigest() != plan["rates_sha256"]
    ):
        raise ValueError("captured pricing bytes changed")
    parent = plan["parent_manifest"]
    if (
        parent["package_id"] != plan["parent_preparation_id"]
        or parent["package_id"]
        != fingerprint({k: v for k, v in parent.items() if k != "package_id"})
        or parent["files"]["rates.json"] != plan["rates_sha256"]
        or parent["files"]["protocol.md"] != plan["parent_protocol_sha256"]
        or parent["files"]["development_episodes.jsonl"]
        != hashlib.sha256(
            "".join(canonical(ep) + "\n" for ep in plan["episodes"]).encode()
        ).hexdigest()
    ):
        raise ValueError("parent preparation binding changed")
    base = ProviderConfig.from_dict(read(ROOT / "artifacts/p1_deepseek_development/provider.json"))
    expected = {
        k: asdict(replace(ProviderConfig.from_dict(v), timeout=180))
        for k, v in calibration.provider_configs(base).items()
    }
    if plan["configs"] != expected:
        raise ValueError("provider configuration drift")
    return plan


def _authorize(plan, authorization):
    if not isinstance(authorization, dict) or set(authorization) != {
        "authorized",
        "execution_id",
        "allowance_usd",
        "max_attempts",
        "rates_sha256",
        "rates_verified_at",
        "authorization_evidence",
    }:
        raise ValueError("explicit authorization and fresh pricing attestation required")
    if (
        authorization["authorized"] is not True
        or authorization["execution_id"] != plan["execution_id"]
        or authorization["allowance_usd"] != plan["budget"]["allowance"]
        or type(authorization["max_attempts"]) is not int
        or authorization["max_attempts"] != 270
        or authorization["rates_sha256"] != plan["rates_sha256"]
        or not isinstance(authorization["authorization_evidence"], str)
        or not authorization["authorization_evidence"].strip()
    ):
        raise ValueError("authorization scope mismatch")
    try:
        verified = datetime.fromisoformat(authorization["rates_verified_at"])
        age = (datetime.now(timezone.utc) - verified).total_seconds()
        if not 0 <= age <= 86400:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("fresh explicit price attestation required") from None


def collect(
    execution: Path,
    output: Path,
    *,
    transport=None,
    registry=None,
    resume=False,
    authorization=None,
    fault=None,
    offline_only=False,
) -> dict:
    plan = verify_execution(execution)
    mode = "injected_transport_unverified" if transport is not None else "urllib_http"
    credential = "diagnostic-fixture-credential"
    if offline_only:
        if not resume or transport is not None:
            raise ValueError("offline recovery requires an existing run and no transport")
        original_binding = read_events(output)[0]["data"]
        mode = original_binding["mode"]
        authorization = original_binding["authorization"]
    elif transport is None:
        _authorize(plan, authorization)
        if registry is not None and str(Path(registry).resolve()) != plan["registry_path"]:
            raise ValueError("live registry override requires a new execution identity")
        credential = os.environ.get("DEEPSEEK_API_KEY")
        if not credential:
            raise ValueError("credential missing; no attempt started")
    output = Path(output)
    registry = Path(registry) if registry is not None else Path(plan["registry_path"])
    if mode == "urllib_http" and str(registry.resolve()) != plan["registry_path"]:
        raise ValueError("live registry override requires a new execution identity")

    def boundary(kind, i):
        if fault is not None:
            fault(kind, i)

    with RunStore(output, plan["execution_id"], registry, resume=resume) as store:
        binding = {
            "execution_id": plan["execution_id"],
            "mode": mode,
            "authorization": (
                {k: v for k, v in authorization.items() if k != "rates_verified_at"}
                if mode == "urllib_http"
                else None
            ),
        }
        if offline_only:
            binding = original_binding
        if not store.events:
            store.append("binding", binding)
        elif store.events[0]["data"] != binding:
            raise ValueError("resume mode or authorization changed")
        if mode == "urllib_http" and not offline_only:
            store.append(
                "price_attestation",
                {
                    "rates_verified_at": authorization["rates_verified_at"],
                    "rates_sha256": authorization["rates_sha256"],
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        from .live_calibration_audit import audit_run

        audit = audit_run(execution, output)
        if audit["stop_reason"]:
            return _summary(plan, audit)
        ledger = BudgetLedger(plan["budget"])
        for row in audit["accounting_rows"]:
            ledger.reserve(row["attempt_id"], row["cap"])
            if row["status"] == "settled":
                ledger.settle(row["attempt_id"], row["usage"])
        history = audit["histories"]
        episodes = {ep["episode_id"]: ep for ep in plan["episodes"]}
        pending = audit["pending"]
        for index in range(audit["completed"], 270):
            if offline_only and (pending is None or pending["phase"] == "reserved"):
                break
            slot = plan["schedule"][index]
            prefix = history.get(slot["trajectory_id"], [])
            previous = prefix[-1] if prefix else None
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
            attempt = f"{plan['execution_id']}:{index}"
            if pending is None:
                if len(prepared["raw_request"].encode()) > plan["budget"]["max_request_bytes"]:
                    store.append("halt", {"slot_index": index, "reason": "request_bytes_guard"})
                    break
                try:
                    reservation = ledger.reserve(attempt, slot["max_output_tokens"])
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
                store.append(
                    "send_intent",
                    {"slot_index": index, "send_intent_at": datetime.now(timezone.utc).isoformat()},
                )
                boundary("send_intent", index)
                captured = send_prepared(
                    prepared, total_deadline=180, transport=transport, credential=credential
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
                if completion["metadata"]["response_model"] != prepared["config"]["model"]:
                    raise ValueError("model_mismatch")
                settlement = ledger.settle(attempt, completion["metadata"]["usage"])
            except (ValueError, ProviderError):
                store.append("halt", {"slot_index": index, "reason": "capture_or_usage_invalid"})
                break
            if pending["phase"] != "settled":
                store.append("settled", {"slot_index": index, "settlement": settlement})
                boundary("settled", index)
            raw = completion["raw_response"]
            status, after = "invalid", previous
            try:
                after = parse_decision(raw)
            except (ValueError, KeyError, TypeError):
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
        audit = audit_run(execution, output)
        summary = _summary(plan, audit)
        durable_json(output / "summary.json", summary)
        return summary


def _summary(plan, audit):
    return {
        "execution_id": plan["execution_id"],
        "completed": audit["completed"],
        "received": audit["received"],
        "planned": 270,
        "status": audit["stop_reason"] or ("complete" if audit["complete"] else "incomplete"),
        "model_api_calls": audit["attempts"] if audit["mode"] == "urllib_http" else 0,
        "budget": audit["budget"],
        "audit_id": audit["audit_id"],
        "live_collection_verified": audit["mode"] == "urllib_http" and audit["complete"],
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
                        "content": diagnostic_response(request, "rule"),
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
    prep.add_argument("--preparation", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--registry", type=Path)
    for name in ("verify", "rehearse", "run", "resume", "recover"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--execution", type=Path, required=True)
        if name != "verify":
            cmd.add_argument("--output", type=Path, required=True)
            cmd.add_argument("--registry", type=Path)
        if name in ("run", "resume"):
            cmd.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_execution(args.preparation, args.output, registry=args.registry)
    elif args.command == "verify":
        result = verify_execution(args.execution)
    else:
        result = collect(
            args.execution,
            args.output,
            registry=args.registry,
            resume=args.command in ("resume", "recover"),
            offline_only=args.command == "recover",
            transport=diagnostic_transport if args.command == "rehearse" else None,
            authorization=read(args.authorization) if args.command in ("run", "resume") else None,
        )
    print(
        canonical(
            {
                k: v
                for k, v in result.items()
                if k
                not in {"episodes", "schedule", "configs", "source_identity", "parent_manifest"}
            }
        )
    )


if __name__ == "__main__":
    main()
