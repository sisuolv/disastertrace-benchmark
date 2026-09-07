"""Independently audit the completed, explicitly amended P1 continuation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/p1_deepseek_development"
ORIGINAL = ROOT / "work/p1-deepseek-development-v1"
LIVE = ROOT / "work/p1-deepseek-background-continuation-v1"
DEST = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def dec(value):
    return Decimal(str(value))


def inventory(path):
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(path.rglob("*")) if p.is_file()}


def main():
    target = DEST / "result.json"
    if target.exists():
        raise ValueError("Preserve existing audit evidence")
    status = read(LIVE / "status.json")
    if status["status"] != "completed":
        raise ValueError("This audit requires a completed capture")
    checks = []

    def check(name, actual, expected):
        checks.append(
            {"name": name, "actual": actual, "expected": expected, "passed": actual == expected}
        )

    original_before = inventory(ORIGINAL)
    protected = read(ART / "historical_inventory_before.json")["files"]
    interrupted = read(ART / "interruption_audit/result.json")
    check("historical_count", len(protected), 177)
    check("original_file_count", len(original_before), 83)
    for path, expected in protected.items():
        check("historical:" + path, digest(ROOT / path), expected)
    check("original_capture_unchanged", original_before, interrupted["original_live_inventory"])

    prepared = ART / "background_resume/prepared"
    amendment = read(prepared / "amendment.json")
    check(
        "amendment_fingerprint",
        fingerprint({k: v for k, v in amendment.items() if k != "amendment_id"}),
        amendment["amendment_id"],
    )
    for path, expected in amendment["frozen_files_sha256"].items():
        check("frozen:" + path, digest(path), expected)
    for path, expected in amendment["prepared_files_sha256"].items():
        check("prepared:" + path, digest(prepared / path), expected)
    offline = read(ART / "background_resume/offline_checks.json")
    for path, expected in offline["files_sha256"].items():
        check("offline_check_source:" + path, digest(ROOT / path), expected)
    check("offline_passed_tests", offline["tests"]["passed"], 22)
    check("offline_skipped_tests", offline["tests"]["skipped"], 0)

    auth_path = ART / "background_resume/authorization.json"
    authorization = read(auth_path)
    launch = read(LIVE / "launch.json")
    claim = read(prepared / "launch_claim.json")
    check("authorization_received", authorization["authorized"], True)
    check("authorization_amendment", authorization["amendment_id"], amendment["amendment_id"])
    check("authorization_file_hash", digest(auth_path), launch["authorization_sha256"])
    check("authorization_copy_bytes", digest(LIVE / "authorization.json"), digest(auth_path))
    check(
        "authorization_fingerprint",
        fingerprint(authorization),
        launch["authorization_snapshot_sha256"],
    )
    check(
        "authorization_scope",
        [
            authorization[k]
            for k in (
                "allowance_usd",
                "max_additional_provider_attempts",
                "max_cumulative_provider_attempts",
                "explicit_retry_original_attempt",
            )
        ],
        ["1.5", 12, 91, 79],
    )
    check(
        "amendment_snapshot",
        digest(LIVE / "amendment_snapshot.json"),
        digest(prepared / "amendment.json"),
    )
    check("single_launch_claim", claim["output_path"], str(LIVE))
    check("claim_authorization", claim["authorization_sha256"], digest(auth_path))
    check("automatic_relaunch", launch["automatic_relaunch"], False)
    process = read(DEST / "process_observation.json")
    check(
        "observed_detached_session",
        [process[k] for k in ("pid", "ppid", "pgrp", "session", "tty_nr")],
        [16909, 1, 16909, 16909, 0],
    )
    for name in ("pid.json", "worker_started.json", "status.json", "launch.json"):
        check("pid_binding:" + name, read(LIVE / name)["pid"], 16909)
    check("worker_exit", read(LIVE / "exit.json")["exit_code"], 0)
    check("status_exit", status["exit_code"], 0)
    execution = read(LIVE / "execution.json")
    check(
        "execution_scope",
        [
            execution[k]
            for k in (
                "new_provider_attempts",
                "cumulative_provider_attempts",
                "cumulative_completions_received",
                "full_three_method_scoring_opportunities",
            )
        ],
        [12, 91, 90, 90],
    )
    check("actual_live_transport", execution["injected_offline_transport"], False)
    check("actual_total_cost_unknown", execution["actual_total_cost_usd"], None)

    manifest = read(ART / "experiment.json")
    ledger = read(LIVE / "budget_ledger.json")
    original_ledger = read(ORIGINAL / "budget_ledger.json")
    attempts = ledger["attempts"]
    check("original_79_ledger_rows_unchanged", attempts[:79], original_ledger["attempts"])
    check("ledger_budget", ledger["budget"], amendment["budget"])
    check("attempts", len(attempts), 91)
    check("completions", ledger["provider_completions_received"], 90)
    check("no_denials", ledger["guard_denials_before_provider"], 0)
    check("no_halt", ledger["halted"], False)
    check("assumptions_hold", ledger["conditional_budget_assumptions_satisfied"], True)
    check("no_automatic_retry", ledger["automatic_retry"], False)
    check(
        "first_new_is_explicit_retry",
        attempts[79]["request_sha256"],
        attempts[78]["request_sha256"],
    )
    check(
        "explicit_retry_hash",
        attempts[79]["request_sha256"],
        amendment["explicit_retry_request_sha256"],
    )
    check(
        "new_calls_only_answer_history",
        sorted({a["method"] for a in attempts[79:]}),
        ["answer_history"],
    )
    budget = amendment["budget"]
    prompt_rate, output_rate = (
        dec(budget["peak_input_per_million"]),
        dec(budget["peak_output_per_million"]),
    )
    reserve = (budget["prompt_reservation_tokens"] * prompt_rate + 4096 * output_rate) / 1000000
    check("reservation", reserve, Decimal("0.46678016"))
    spent = pending = Decimal(0)
    for ordinal, attempt in enumerate(attempts, 1):
        label = f"attempt:{ordinal}:"
        check(label + "sequence", attempt["attempt_number"], ordinal)
        check(label + "reserve", dec(attempt["reserved_usd"]), reserve)
        check(label + "output_cap", attempt["requested_output_tokens"], 4096)
        check(label + "request_bytes_cap", attempt["request_bytes"] <= 262144, True)
        if not attempt["reservation_released"]:
            pending += dec(attempt["reserved_usd"])
        if attempt.get("conservative_reported_cost_usd") is not None:
            usage = attempt["usage"]
            charge = (
                usage["prompt_tokens"] * prompt_rate + usage["completion_tokens"] * output_rate
            ) / 1000000
            check(label + "cost", dec(attempt["conservative_reported_cost_usd"]), charge)
            spent += charge
    check(
        "pending_only_original_79",
        [a["attempt_number"] for a in attempts if not a["reservation_released"]],
        [79],
    )
    check("pending_unchanged", pending, Decimal("0.46678016"))
    for name, actual in (
        ("provider_attempts_started", len(attempts)),
        ("requested_output_tokens_reserved_total", len(attempts) * 4096),
        ("conservative_reported_cost_usd", spent),
        ("pending_reservation_usd", pending),
        ("spent_plus_pending_usd", spent + pending),
        ("allowance_remaining_after_reservations_usd", dec("1.5") - spent - pending),
    ):
        check("ledger:" + name, dec(ledger[name]), dec(actual))
    check("output_reservation_limit", len(attempts) * 4096, 372736)
    check("allowance_limit", spent + pending <= dec("1.5"), True)

    rates = read(ART / "docs/rates.json")
    check("price_source", digest(rates["source"]["path"]), rates["source"]["sha256"])
    start, end = [
        datetime.fromisoformat(rates["window"][k]).timestamp() for k in ("start_utc", "end_utc")
    ]
    price = {k: dec(v) for k, v in rates["per_million_tokens"].items()}
    total_usage, total_cost, new_cost, methods = Counter(), Decimal(0), Decimal(0), {}
    for method in manifest["methods"]:
        root = LIVE if method == "answer_history" else ORIGINAL
        directory = root / "runs" / method / "collection"
        requests, outcomes, responses = [
            rows(directory / (name + ".jsonl")) for name in ("requests", "outcomes", "responses")
        ]
        received = [a for a in attempts if a["method"] == method and a["completion_received"]]
        check(
            method + ":counts",
            [len(requests), len(outcomes), len(responses), len(received)],
            [30] * 4,
        )
        keys = [(r["episode_id"], r["checkpoint_id"]) for r in requests]
        check(method + ":checkpoint_identity_unique", len(set(keys)), 30)
        check(
            method + ":only_development_storms",
            sorted({r["episode_id"].split(":")[0] for r in requests}),
            ["al052019", "al062018", "al092021"],
        )
        check(
            method + ":request_order_matches_admitted_received",
            [r["prepared"]["request_sha256"] for r in requests],
            [a["request_sha256"] for a in received],
        )
        if method == "answer_history":
            for name in ("responses", "outcomes", "requests"):
                old_lines = (
                    (ORIGINAL / "runs" / method / "collection" / (name + ".jsonl"))
                    .read_bytes()
                    .splitlines()[:18]
                )
                new_lines = (directory / (name + ".jsonl")).read_bytes().splitlines()[:18]
                check("retained_history_prefix_bytes:" + name, old_lines == new_lines, True)
        method_cost = Decimal(0)
        for ordinal, (request, outcome, response, attempt) in enumerate(
            zip(requests, outcomes, responses, received), 1
        ):
            label = f"{method}:response:{ordinal}:"
            check(label + "collector_ordinal", request["attempt_number"], ordinal)
            check(
                label + "checkpoint_binding",
                [(v["episode_id"], v["checkpoint_id"]) for v in (outcome, response)],
                [keys[ordinal - 1]] * 2,
            )
            check(label + "request_hash", outcome["request_sha256"], attempt["request_sha256"])
            meta = outcome["metadata"]
            usage = meta["usage"]
            check(
                label + "ledger_usage",
                attempt["usage"],
                {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
            )
            check(
                label + "raw_hash",
                fingerprint(response["raw_response"]),
                outcome["raw_response_sha256"],
            )
            check(
                label + "ledger_raw_hash",
                attempt["raw_response_sha256"],
                outcome["raw_response_sha256"],
            )
            check(label + "model", meta["response_model"], "deepseek-v4-flash")
            check(
                label + "no_auto_retry",
                [meta["attempt_count"], meta["automatic_retry"]],
                [1, False],
            )
            check(label + "output_tokens", usage["completion_tokens"] <= 4096, True)
            check(label + "prompt_tokens", usage["prompt_tokens"] <= 1048576, True)
            check(
                label + "total_usage",
                usage["prompt_tokens"] + usage["completion_tokens"],
                usage["total_tokens"],
            )
            check(
                label + "cache_sum",
                usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"],
                usage["prompt_tokens"],
            )
            wire = json.loads(meta["raw_response_body"])
            check(label + "price_window", start <= wire["created"] < end, True)
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
            charge = (
                usage["prompt_cache_hit_tokens"] * price["input_cache_hit"]
                + usage["prompt_cache_miss_tokens"] * price["input_cache_miss"]
                + usage["completion_tokens"] * price["output"]
            ) / 1000000
            method_cost += charge
            if attempt["attempt_number"] > 79:
                new_cost += charge
        total_cost += method_cost
        methods[method] = {
            "opportunities": 30,
            "received": 30,
            "outcome_status_counts": dict(Counter(r["status"] for r in outcomes)),
            "received_cost_estimate_usd": str(method_cost),
        }
    check(
        "original_78_cost_retained",
        total_cost - new_cost,
        dec(interrupted["observed_received_cache_aware_cost_estimate_usd"]),
    )
    check("original_capture_unchanged_during_audit", inventory(ORIGINAL), original_before)
    result = {
        "schema_version": "p1_completed_continuation_independent_audit_v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "script_sha256": digest(__file__),
        "new_model_api_calls": 0,
        "command": [".venv/bin/python", str(Path(__file__).relative_to(ROOT))],
        "new_provider_attempts": 12,
        "cumulative_provider_attempts": 91,
        "benchmark_checkpoint_opportunities": 90,
        "received_answers": 90,
        "original_unresolved_attempt": 79,
        "retained_original_answers": 78,
        "original_invalid_answers_retained": 20,
        "original_capture_files_verified": 83,
        "historical_files_verified": 177,
        "reported_usage": dict(total_usage),
        "methods": methods,
        "new_received_cost_estimate_usd": str(new_cost),
        "all_received_cost_estimate_usd": str(total_cost),
        "actual_total_cost_usd": None,
        "conservative_reported_cost_usd": str(spent),
        "retained_unknown_reservation_usd": str(pending),
        "conservative_spent_plus_pending_usd": str(spent + pending),
        "allowance_remaining_usd": str(dec("1.5") - spent - pending),
        "interpretation": "One explicit retry restores a checkpoint answer; original attempt 79's result and charge remain unknown. Pricing estimates use received usage only, not a provider invoice. No per-item human review or model judge is used.",
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }
    with target.open("x") as stream:
        json.dump(result, stream, indent=2, default=str)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}, default=str))
    print(
        json.dumps(
            {"checks": len(checks), "failed": [c["name"] for c in checks if not c["passed"]]}
        )
    )
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
