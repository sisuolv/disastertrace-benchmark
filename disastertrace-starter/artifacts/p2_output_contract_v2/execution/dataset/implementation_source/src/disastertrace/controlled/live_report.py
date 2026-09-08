"""Direct P2 scores from independently audited captures, never relabeled diagnostics."""

import math
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import median

from disastertrace.automated.common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    safe_child,
    write_json,
    write_jsonl,
)
from disastertrace.automated.execution_observations import estimate_captured_cost
from disastertrace.automated.provider import ProviderError

from .execution import read, verify_execution
from .live_audit import _audit_verified
from .provider_capture import parse_capture
from .schema import METHODS
from .scorer import _score_rows


def _observations(plan, audit):
    rows = list(audit["records"])
    if audit["pending"] is not None:
        rows.append(audit["pending"])
    elapsed, details = [], []
    failures, estimates = Counter(), Counter()
    usage_totals = dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens"), 0)
    usage_count = covered = 0
    subtotal = Decimal(0)
    for row in rows:
        capture = row.get("capture")
        completion = row.get("completion")
        if capture is not None:
            elapsed.append(capture["elapsed_seconds"])
            if capture["error_code"]:
                failures[capture["error_code"]] += 1
            if completion is None:
                try:
                    completion = parse_capture(capture, row["prepared"])
                except ProviderError:
                    failures["unparsed_provider_envelope"] += 1
        if completion is not None:
            if completion["raw_response"] == "":
                failures["empty_content"] += 1
            if completion["metadata"]["finish_reason"] == "length":
                failures["length"] += 1
        if row.get("status") == "invalid":
            failures["answer_schema_invalid"] += 1
        settled = row["phase"] in {"settled", "decision"}
        usage = completion["metadata"]["usage"] if completion and settled else None
        if usage is not None:
            usage_count += 1
            for key in usage_totals:
                usage_totals[key] += usage[key]
        estimate = {"usd": None, "status": "unverified_usage", "window": None}
        if audit["mode"] != "model_http":
            estimate["status"] = "diagnostic_simulation"
        elif usage is not None:
            estimate = estimate_captured_cost(
                usage, row["send_intent_at"], row["capture_observed_at"], plan["rates"]
            )
        estimates[estimate["status"]] += 1
        if estimate["usd"] is not None:
            covered += 1
            subtotal += Decimal(estimate["usd"])
        details.append(
            {
                "slot_index": row["slot_index"],
                "phase": row["phase"],
                "send_intent_at": row.get("send_intent_at"),
                "capture_observed_at": row.get("capture_observed_at"),
                "finish_reason": completion["metadata"]["finish_reason"] if completion else None,
                "usage": usage,
                "cost_estimate": estimate,
                "capture_error": capture["error_code"] if capture else None,
            }
        )
    values = sorted(elapsed)
    return {
        "usage": usage_totals,
        "verified_usage_responses": usage_count,
        "failure_counts": dict(failures),
        "failure_categories_overlap": True,
        "latency_seconds": {
            "count": len(values),
            "mean": sum(values) / len(values) if values else None,
            "median": median(values) if values else None,
            "p95": values[math.ceil(0.95 * len(values)) - 1] if values else None,
            "maximum": max(values) if values else None,
        },
        "cost_estimate": {
            "basis": "captured_price_snapshot"
            if audit["mode"] == "model_http"
            else "diagnostic_simulation",
            "usd": str(subtotal) if covered else None,
            "covered_attempts": covered,
            "all_attempts_covered": audit["mode"] == "model_http"
            and covered == audit["attempts"]
            and covered > 0,
            "statuses": dict(estimates),
            "is_invoice": False,
        },
        "conservative_settled_usd": audit["budget"]["settled"],
        "unsettled_reservation_usd": audit["budget"]["pending"],
        "unknown_reservation_usd": str(
            sum(
                (
                    Decimal(row["reservation"])
                    for row in audit["accounting_rows"]
                    if row["status"] == "unknown"
                ),
                Decimal(0),
            )
        ),
        "requested_output_tokens_reserved": sum(r["cap"] for r in audit["accounting_rows"]),
        "attempts": details,
    }


def _materialize(plan, audit):
    traces, methods = [], {}
    live = audit["mode"] == "model_http"
    for row in audit["records"]:
        traces.append(
            {
                "episode_id": row["slot"]["episode_id"],
                "checkpoint_id": row["slot"]["checkpoint_id"],
                "method": row["slot"]["method"],
                "slot_index": row["slot_index"],
                "model_kind": "model_api" if live else audit["mode"],
                "eligible_for_llm_leaderboard": live and audit["complete"],
                "provider_requests": int(live),
                "request": row["request"],
                "request_hash": fingerprint(row["request"]),
                "raw_response": row["raw_response"],
                "status": row["status"],
                "state_after": row["state_after"],
                "provenance": {
                    "execution_id": plan["execution_id"],
                    "audit_id": audit["audit_id"],
                    "prepared_request_sha256": row["prepared"]["request_sha256"],
                    "capture_sha256": fingerprint(row["capture"]),
                    "response_body_sha256": row["capture"]["body_sha256"],
                    "capture_origin": row["capture"]["origin"],
                },
            }
        )
    pending = audit["pending"]
    for method in METHODS:
        selected = [r for r in traces if r["method"] == method]
        missing = {}
        pending_method = None
        if pending is not None:
            slot = plan["schedule"][pending["slot_index"]]
            pending_method = slot["method"]
            if pending_method == method:
                missing[(slot["episode_id"], slot["checkpoint_id"])] = (
                    "reserved_unsent"
                    if pending["phase"] == "reserved"
                    else "attempted_unresolved"
                    if pending["phase"] == "send_intent"
                    else "captured_unfinalized"
                )
        score = _score_rows(plan["episodes"], selected, method, missing_status=missing)
        attempted = len(selected) + int(pending_method == method and pending["phase"] != "reserved")
        methods[method] = {
            **score,
            **({"output_contract": plan["output_contract"]} if "output_contract" in plan else {}),
            "schema_version": "controlled_captured_score_v1",
            "model_kind": "model_api" if live else audit["mode"],
            "eligible_for_llm_leaderboard": live and audit["complete"],
            "model_calls": attempted if live else 0,
            "completed": len(selected),
            "attempted": attempted,
            "unsubmitted": 90 - attempted,
            "audit_id": audit["audit_id"],
        }
    reliability = []
    for method, score in methods.items():
        for family, group in score["by_family"].items():
            count = group["metrics"]["schema_success"]
            length = sum(
                r["completion"]["metadata"]["finish_reason"] == "length"
                for r in audit["records"]
                if r["slot"]["method"] == method and r["slot"]["family"] == family
            )
            reliability.append(
                {
                    "method": method,
                    "family": family,
                    "schema_valid": count["numerator"],
                    "planned": count["denominator"],
                    "length_finishes": length,
                    "passed": count["denominator"] == 30
                    and count["numerator"] >= 29
                    and length <= 1,
                }
            )
    passed = audit["complete"] and all(cell["passed"] for cell in reliability)
    report = {
        **({"output_contract": plan["output_contract"]} if "output_contract" in plan else {}),
        "schema_version": "controlled_captured_report_v1",
        "protocol": plan["protocol"],
        "execution_id": plan["execution_id"],
        "dataset_content_id": plan["dataset_content_id"],
        "audit_id": audit["audit_id"],
        "model": plan["config"]["model"],
        "mode": audit["mode"],
        "model_calls": audit["model_api_calls"],
        "planned": plan["planned_opportunities"],
        "attempted": audit["attempts"],
        "received": audit["received"],
        "completed": audit["completed"],
        "unsubmitted": plan["planned_opportunities"] - audit["attempts"],
        "complete": audit["complete"],
        "stop_reason": audit["stop_reason"],
        "eligible_for_llm_leaderboard": live and audit["complete"],
        "provider_origin_authenticated": False,
        "reliability": {
            "rule": plan["reliability_rule"],
            "cells": reliability,
            "thresholds_passed": passed,
            "measured_model_reliability": live and audit["complete"],
            "model_screen_passed": passed if live else None,
        },
        "methods": methods,
        "operations": _observations(plan, audit),
        "interpretation": (
            "Fixed planned denominators; source-derived controlled records, dependent branches, "
            "one repeat. Diagnostic scores are not LLM results."
        ),
    }
    return report, traces


def report_run(execution, run, output, *, require_model=False):
    output = Path(output)
    if output.exists():
        raise ValueError("report output exists; preserve prior results")
    plan = verify_execution(execution)
    audit = _audit_verified(plan, Path(run))
    if require_model and audit["mode"] != "model_http":
        raise ValueError("captured model origin required; diagnostics cannot be relabeled")
    report, traces = _materialize(plan, audit)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "audit.json", audit)
    write_jsonl(output / "actual_trace.jsonl", traces)
    write_json(output / "report.json", report)
    for method, score in report["methods"].items():
        write_json(output / "scores" / (method + ".json"), score)
    manifest = {
        "schema_version": "controlled_captured_report_manifest_v1",
        "execution_id": plan["execution_id"],
        "audit_id": audit["audit_id"],
        "files": {
            str(p.relative_to(output)): file_hash(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
    }
    write_json(output / "manifest.json", {**manifest, "package_id": fingerprint(manifest)})
    return report


def verify_report(execution, run, output):
    output = Path(output)
    plan = verify_execution(execution)
    audit = _audit_verified(plan, Path(run))
    report, traces = _materialize(plan, audit)
    expected = {
        "audit.json": audit,
        "actual_trace.jsonl": traces,
        "report.json": report,
        **{"scores/" + method + ".json": score for method, score in report["methods"].items()},
    }
    manifest = read(output / "manifest.json")
    inventory = {
        str(p.relative_to(output))
        for p in output.rglob("*")
        if p.is_file() and p != output / "manifest.json"
    }
    if set(expected) != inventory:
        raise ValueError("captured report inventory mismatch")
    for name, value in expected.items():
        path = safe_child(output, name)
        observed = read_jsonl(path) if name.endswith(".jsonl") else read(path)
        if canonical(value) != canonical(observed):
            raise ValueError("captured report differs from audited reconstruction: " + name)
    expected_manifest = {
        "schema_version": "controlled_captured_report_manifest_v1",
        "execution_id": plan["execution_id"],
        "audit_id": audit["audit_id"],
        "files": {name: file_hash(safe_child(output, name)) for name in sorted(expected)},
    }
    expected_manifest["package_id"] = fingerprint(expected_manifest)
    if canonical(manifest) != canonical(expected_manifest):
        raise ValueError("captured report manifest mismatch")
    return {
        "status": "passed",
        "package_id": manifest["package_id"],
        "audit_id": audit["audit_id"],
        "verified_files": len(expected),
        "additional_model_calls": 0,
    }
