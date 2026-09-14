"""Reconcile original receipts read-only and distinguish historical/new terminal states."""

import argparse
import json
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1.api_capture import RATES
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def budget_scope(folder):
    budget = read(folder / "BUDGET.json")
    calls = budget["calls"]
    counts = Counter(row["status"] for row in calls.values())
    requests, orphan_dirs, responses = {}, [], []
    captures = (
        list(folder.glob("captures/*/*"))
        if folder.name.startswith("api_evidence")
        else list(folder.glob("*/*/captures/*"))
    )
    for capture in captures:
        if not capture.is_dir():
            continue
        request = capture / "REQUEST.json"
        if not request.exists():
            orphan_dirs.append({"path": str(capture), "request_exists": False})
            continue
        row = read(request)
        cid = row["call_id"]
        if cid in requests:
            raise ValueError("Duplicate original API request identity")
        requests[cid] = capture
        if (capture / "RESPONSE.json").exists():
            responses.append(cid)
    unresolved = []
    for cid, disposition in calls.items():
        if disposition["status"] == "settled":
            continue
        directory = requests.get(cid)
        receipt = {
            "call_id": cid,
            "original_status": disposition["status"],
            "reserved_nanodollars": disposition["reserved"],
            "request_saved": directory is not None,
            "eligible_usage_reconciliation": False,
            "original_ledger_modified": False,
        }
        if directory is not None and (directory / "RESPONSE.json").exists():
            response, request = (
                read(directory / "RESPONSE.json"),
                read(directory / "REQUEST.json"),
            )
            usage, model = (
                response["body"].get("usage", {}),
                request["payload"]["model"],
            )
            pi, po = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if model in RATES and all(type(n) is int and n >= 0 for n in (pi, po)):
                receipt.update(
                    eligible_usage_reconciliation=True,
                    actual_upper_nanodollars=pi * RATES[model][0]
                    + po * RATES[model][1],
                    request_sha256=digest(directory / "REQUEST.json"),
                    response_sha256=digest(directory / "RESPONSE.json"),
                )
        unresolved.append(receipt)
    return {
        "scope": folder.name,
        "registered_budget_calls": len(calls),
        "original_dispositions": dict(counts),
        "persisted_requests": len(requests),
        "persisted_provider_responses": len(responses),
        "capture_directories_without_request": len(orphan_dirs),
        "http_dispatch_count_not_proved_by_legacy_request_file": True,
        "settled_upper_nanodollars": sum(
            r.get("actual", 0) for r in calls.values() if r["status"] == "settled"
        ),
        "unresolved_reservations": len(unresolved),
        "unresolved_nanodollars": sum(r["reserved_nanodollars"] for r in unresolved),
        "unresolved_attempts": unresolved,
        "orphan_capture_directories": orphan_dirs,
        "original_budget_sha256": digest(folder / "BUDGET.json"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run
    old = run.parent / "v9_followup_execution_20260914_01"
    out = run / "reports/original_fee_reconciliation_01"
    out.mkdir(exist_ok=False)
    scopes = [
        budget_scope(old / name)
        for name in [
            "api_evidence_01",
            "api_evidence_02",
            "api_pilot_01",
            "api_rare_pilot_01",
        ]
    ]
    publish(
        out / "RESULT.json",
        {
            "passed": True,
            "scopes": scopes,
            "new_model_calls": 0,
            "scope": "Original usage receipts only; upper cost estimates, not provider invoice",
        },
    )
    audit = read(run / "reports/existing_audit_01/RESULT.json")
    historical = {
        "phase": "COMPLETED_AND_PAUSED",
        "reviewed_commit": "6f71c8799ff69439a18f645e63b8c966ca21eec4",
        "canonical_evidence": "plans/v9_followup_execution_20260914_01/PAUSED_RESULT.json",
        "E02_captured_answers": audit["E"]["captured_answers"],
        "ordinary_F_captured_answers": scopes[2]["persisted_provider_responses"],
        "rare_F_captured_answers": scopes[3]["persisted_provider_responses"],
        "compatibility_calls_reported": 2,
        "temperature": audit["temperature"],
        "F_sessions": audit["forecast_sessions"],
        "unresolved_original_E01_reservations": scopes[0]["unresolved_reservations"],
        "unresolved_original_E01_nanodollars": scopes[0]["unresolved_nanodollars"],
        "all_registered_work_verified": True,
        "consumed_launchers_reopened": False,
    }
    current = {
        "schema": "disastertrace.canonical_status.v1",
        "phase": "RUNNING",
        "historical_v9": historical,
        "current_v10": {
            "run_directory": str(run),
            "active_task": "T04_program_controls_and_model_preparation",
            "completed": [
                "T00_baseline",
                "T01_parser_and_failure_regressions",
                "T02_formal_entry_and_v3_order",
                "T03_exact_coverage_E_composition_calibration_attribution",
            ],
            "new_api_calls": 0,
            "new_gpu_model_calls": 0,
            "confirmation_opened": False,
            "next_allowed_task": "fresh v10 preregistered program and model namespaces",
        },
    }
    (run / "CANONICAL_STATUS.json").write_text(json.dumps(current, indent=2) + "\n")
    print(
        json.dumps(
            {
                "scopes": [
                    {
                        k: r[k]
                        for k in [
                            "scope",
                            "registered_budget_calls",
                            "persisted_requests",
                            "persisted_provider_responses",
                            "unresolved_reservations",
                        ]
                    }
                    for r in scopes
                ]
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
