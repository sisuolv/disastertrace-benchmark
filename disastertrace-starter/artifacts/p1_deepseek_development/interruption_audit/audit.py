"""Audit an interrupted P1 capture without mutating the original experiment."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/p1_deepseek_development"
LIVE = ROOT / "work/p1-deepseek-development-v1"
DEST = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()


def decimal(value):
    return Decimal(str(value))


def inventory(root):
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}


def main():
    target = DEST / "result.json"
    if target.exists():
        raise ValueError("audit output exists; preserve the previous evidence")
    checks = []

    def check(name, actual, expected):
        checks.append(
            {"name": name, "actual": actual, "expected": expected, "passed": actual == expected}
        )

    original_before = inventory(LIVE)
    protected = read(ART / "historical_inventory_before.json")["files"]
    check("protected_file_count", len(protected), 177)
    for path, expected in protected.items():
        check("protected:" + path, digest(ROOT / path), expected)
    manifest = read(ART / "experiment.json")
    check(
        "manifest_fingerprint",
        fingerprint({k: v for k, v in manifest.items() if k != "experiment_id"}),
        manifest["experiment_id"],
    )
    check("live_manifest_copy", digest(LIVE / "experiment.json"), digest(ART / "experiment.json"))
    for name, key in (
        ("run_experiment.py", "runner_sha256"),
        ("report_results.py", "reporter_sha256"),
    ):
        check("frozen:" + name, digest(ART / name), manifest[key])
    for label in ("provider_config", "rates"):
        check("frozen:" + label, digest(manifest[label + "_path"]), manifest[label + "_sha256"])
    check("frozen:protocol", digest(manifest["protocol"]["path"]), manifest["protocol"]["sha256"])
    for path, expected in manifest["offline_checks"].items():
        check("frozen:offline:" + path, digest(ROOT / path), expected)
    check(
        "frozen:dataset_audit",
        digest(ART / "preparation/dataset_audit.json"),
        manifest["dataset_audit_sha256"],
    )
    check(
        "frozen:data_equality",
        digest(ART / "preparation/data_equality.json"),
        manifest["frozen_data_equality_sha256"],
    )
    rates = read(manifest["rates_path"])
    check("official_pricing_source", digest(rates["source"]["path"]), rates["source"]["sha256"])
    initial_path = ART / "final_checks/protocol_audit/initial.json"
    initial = read(initial_path)
    check("initial_audit_passed", initial["passed"], True)
    check(
        "initial_audit_source", digest(initial_path.with_name("audit.py")), initial["script_sha256"]
    )

    build = Path(manifest["build_path"])
    build_manifest = read(build / "manifest.json")
    check("build_identity", build_manifest["build_id"], manifest["build_id"])
    for path, expected in build_manifest["files"].items():
        check("build_artifact:" + path, digest(build / path), expected)
    implementation = read(build / "implementation.json")
    check(
        "implementation_identity",
        implementation["implementation_id"],
        manifest["implementation_id"],
    )
    check(
        "implementation_fingerprint",
        fingerprint({k: v for k, v in implementation.items() if k != "implementation_id"}),
        manifest["implementation_id"],
    )
    for name, expected in implementation["files"].items():
        check(
            "current_implementation:" + name,
            digest(ROOT / "src/disastertrace/automated" / name),
            expected,
        )

    # Read only executable/script tokens; do not persist command lines or environments.
    process_scan_at = datetime.now(timezone.utc).isoformat()
    matches = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            argv = (process / "cmdline").read_bytes().split(b"\0")
        except (OSError, PermissionError):
            continue
        if any(
            Path(token.decode(errors="replace")).name == "run_experiment.py" for token in argv[:3]
        ):
            matches.append({"pid": int(process.name), "script_name": "run_experiment.py"})
    check("runner_process_absent_at_observation", matches, [])

    execution = read(LIVE / "execution.json")
    ledger = read(LIVE / "budget_ledger.json")
    check("execution_binding", execution["experiment_id"], manifest["experiment_id"])
    check(
        "execution_file_binding",
        execution["experiment_file_sha256"],
        digest(ART / "experiment.json"),
    )
    check("execution_runner_binding", execution["runner_sha256"], manifest["runner_sha256"])
    check("ledger_binding", ledger["experiment_id"], manifest["experiment_id"])
    check("ledger_budget_binding", ledger["budget"], manifest["budget"])
    check("planned_opportunities", execution["planned_checkpoints_total"], 90)
    check("original_execution_unfinalized", execution["status"], "running")
    check(
        "original_execution_last_method_boundary_attempts",
        execution["provider_attempts_started"],
        60,
    )

    budget = manifest["budget"]
    input_rate = decimal(budget["peak_input_per_million"])
    output_rate = decimal(budget["peak_output_per_million"])
    reservation = (
        decimal(budget["prompt_reservation_tokens"]) * input_rate + 4096 * output_rate
    ) / 1000000
    check("reservation_formula", reservation, Decimal("0.46678016"))
    attempts = ledger["attempts"]
    spent = pending = Decimal(0)
    for index, attempt in enumerate(attempts, 1):
        label = f"attempt:{index}:"
        check(label + "sequence", attempt["attempt_number"], index)
        check(label + "reservation", decimal(attempt["reserved_usd"]), reservation)
        check(label + "output_cap", attempt["requested_output_tokens"], 4096)
        check(label + "request_size", attempt["request_bytes"] <= budget["max_request_bytes"], True)
        if not attempt["reservation_released"]:
            pending += decimal(attempt["reserved_usd"])
        if attempt.get("conservative_reported_cost_usd") is not None:
            usage = attempt["usage"]
            charge = (
                usage["prompt_tokens"] * input_rate + usage["completion_tokens"] * output_rate
            ) / 1000000
            check(label + "charge", decimal(attempt["conservative_reported_cost_usd"]), charge)
            spent += charge
    check("ledger_attempt_count", ledger["provider_attempts_started"], len(attempts))
    check("ledger_attempts", len(attempts), 79)
    check("ledger_received", ledger["provider_completions_received"], 78)
    check(
        "ledger_reserved_output",
        ledger["requested_output_tokens_reserved_total"],
        len(attempts) * 4096,
    )
    check("ledger_spent", decimal(ledger["conservative_reported_cost_usd"]), spent)
    check("ledger_pending", decimal(ledger["pending_reservation_usd"]), pending)
    check("ledger_total", decimal(ledger["spent_plus_pending_usd"]), spent + pending)
    check(
        "ledger_remaining",
        decimal(ledger["allowance_remaining_after_reservations_usd"]),
        decimal(budget["allowance"]) - spent - pending,
    )
    check("within_allowance", spent + pending <= decimal(budget["allowance"]), True)
    check("attempt_cap", len(attempts) <= budget["max_provider_requests"], True)
    check(
        "output_reservation_cap",
        ledger["requested_output_tokens_reserved_total"] <= budget["max_reserved_output_tokens"],
        True,
    )
    check(
        "pending_attempts",
        [a["attempt_number"] for a in attempts if not a["reservation_released"]],
        [79],
    )
    check("pending_status", attempts[-1]["status"], "pending")
    check("pending_not_received", attempts[-1]["completion_received"], False)
    check("pending_model_cost_unknown", attempts[-1].get("conservative_reported_cost_usd"), None)
    check("no_guard_denial", ledger["guard_denials_before_provider"], 0)
    check("no_automatic_retry", ledger["automatic_retry"], False)

    total_usage = Counter()
    known_cost = Decimal(0)
    method_results = {}
    start = datetime.fromisoformat(rates["window"]["start_utc"]).timestamp()
    end = datetime.fromisoformat(rates["window"]["end_utc"]).timestamp()
    for method in manifest["methods"]:
        location = LIVE / "runs" / method
        requests = rows(location / "collection/requests.jsonl")
        outcomes = rows(location / "collection/outcomes.jsonl")
        responses = rows(location / "collection/responses.jsonl")
        admitted = [a for a in attempts if a["method"] == method]
        received = [a for a in admitted if a["completion_received"]]
        expected_counts = [19, 18, 18] if method == "answer_history" else [30, 30, 30]
        check(
            method + ":journal_counts",
            [len(requests), len(outcomes), len(responses)],
            expected_counts,
        )
        check(
            method + ":request_ledger_multiset",
            Counter(r["prepared"]["request_sha256"] for r in requests),
            Counter(a["request_sha256"] for a in admitted),
        )
        check(
            method + ":request_ledger_order",
            [r["prepared"]["request_sha256"] for r in requests],
            [a["request_sha256"] for a in admitted],
        )
        check(
            method + ":received_ledger_order",
            [r["request_sha256"] for r in outcomes],
            [a["request_sha256"] for a in received],
        )
        check(
            method + ":unique_checkpoint_keys",
            len({(r["episode_id"], r["checkpoint_id"]) for r in requests}),
            len(requests),
        )
        method_cost = Decimal(0)
        for position, (outcome, response, attempt) in enumerate(
            zip(outcomes, responses, received), 1
        ):
            label = method + f":received:{position}:"
            meta = outcome["metadata"]
            usage = meta["usage"]
            check(
                label + "checkpoint_binding",
                (outcome["episode_id"], outcome["checkpoint_id"]),
                (response["episode_id"], response["checkpoint_id"]),
            )
            check(
                label + "ledger_usage",
                attempt["usage"],
                {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
            )
            check(
                label + "ledger_response_hash",
                attempt["raw_response_sha256"],
                outcome["raw_response_sha256"],
            )
            check(
                label + "raw_response_hash",
                fingerprint(response["raw_response"]),
                outcome["raw_response_sha256"],
            )
            check(label + "model", meta["response_model"], "deepseek-v4-flash")
            check(label + "no_retry", meta["automatic_retry"], False)
            check(label + "attempt_count", meta["attempt_count"], 1)
            check(label + "output_limit", usage["completion_tokens"] <= 4096, True)
            check(
                label + "cache_sum",
                usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"],
                usage["prompt_tokens"],
            )
            check(
                label + "total_usage",
                usage["prompt_tokens"] + usage["completion_tokens"],
                usage["total_tokens"],
            )
            wire = json.loads(meta["raw_response_body"])
            check(label + "pricing_window", start <= wire["created"] < end, True)
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
            ):
                total_usage[key] += usage[key]
            total_usage["reasoning_tokens"] += usage["completion_tokens_details"][
                "reasoning_tokens"
            ]
            price = rates["per_million_tokens"]
            method_cost += (
                usage["prompt_cache_hit_tokens"] * decimal(price["input_cache_hit"])
                + usage["prompt_cache_miss_tokens"] * decimal(price["input_cache_miss"])
                + usage["completion_tokens"] * decimal(price["output"])
            ) / 1000000
        known_cost += method_cost
        method_results[method] = {
            "planned": 30,
            "admitted": len(admitted),
            "received": len(received),
            "not_received": 30 - len(received),
            "not_admitted": 30 - len(admitted),
            "outcome_status_counts": dict(Counter(r["status"] for r in outcomes)),
            "observed_received_cost_estimate_usd": str(method_cost),
            "actual_total_cost_usd": None,
        }
    last_request = rows(LIVE / "runs/answer_history/collection/requests.jsonl")[-1]
    check(
        "pending_checkpoint",
        [last_request["episode_id"], last_request["checkpoint_id"]],
        ["al062018:controlled:delay", "c3"],
    )
    original_after = inventory(LIVE)
    check("original_live_files_unchanged_during_audit", original_after, original_before)
    result = {
        "schema_version": "p1_interruption_audit_v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "script_sha256": digest(__file__),
        "command": [".venv/bin/python", str(Path(__file__).relative_to(ROOT))],
        "new_model_api_calls": 0,
        "source_artifact_mutations": 0,
        "experiment_id": manifest["experiment_id"],
        "observed_status": "interrupted_unfinalized_capture",
        "original_execution_status": execution["status"],
        "original_ledger_halted": ledger["halted"],
        "status_interpretation": "Runner is absent at observation; persisted running/pending flags are historical unfinalized state, not evidence that a call remains active. No exit status or interruption timestamp is inferred.",
        "process_observation": {
            "observed_at": process_scan_at,
            "matching_runner_processes": matches,
        },
        "last_ledger_update_at": ledger["updated_at"],
        "planned_checkpoints": 90,
        "provider_calls_admitted": 79,
        "provider_completions_received": 78,
        "pending_outcome_unknown": 1,
        "not_admitted": 11,
        "methods": method_results,
        "reported_usage_from_78_received_completions": dict(total_usage),
        "observed_received_cache_aware_cost_estimate_usd": str(known_cost),
        "full_experiment_cost_estimate_usd": None,
        "cost_interpretation": "Captured off-peak rates estimate only 78 received completions. Attempt 79 may have reached the provider and has no recorded response/usage; total incurred cost is unknown. Retained reservation is an accounting allowance, not an invoice or measured charge.",
        "conservative_reported_subtotal_usd": str(spent),
        "retained_uncertain_reservation_usd": str(pending),
        "conservative_subtotal_plus_reservation_usd": str(spent + pending),
        "allowance_remaining_after_reservations_usd": str(
            decimal(budget["allowance"]) - spent - pending
        ),
        "comparison_interpretation": "All three methods retain 30 planned opportunities each. Answer-history has 18 observed completions, 1 uncertain attempt and 11 unattempted slots; its full-denominator score confounds interruption with model behavior. Completed-prefix-only diagnostics are selected observations, not a completed three-method comparison or evidence of method superiority.",
        "original_live_inventory": original_before,
        "initial_audit_sha256": digest(initial_path),
        "protected_file_count": len(protected),
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }
    target.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "checks": len(checks),
                "failed": [c["name"] for c in checks if not c["passed"]],
                "methods": method_results,
                "known_cost_subtotal_usd": str(known_cost),
                "usage": dict(total_usage),
                "output": str(target),
            }
        )
    )
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
