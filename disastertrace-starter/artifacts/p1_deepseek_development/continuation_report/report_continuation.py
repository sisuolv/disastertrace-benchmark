"""Offline report for the explicitly amended P1 continuation, retaining uncertainty."""

from __future__ import annotations

import argparse
import importlib.util
from collections import Counter
from decimal import Decimal
from pathlib import Path

from disastertrace.automated.common import file_hash, fingerprint, read_jsonl, write_json

HERE = Path(__file__).resolve().parent
FROZEN_PATH = HERE.parent / "report_results.py"
FROZEN_SHA256 = "d364ec543a03f972b2433c54b051eb1e1b56a0fb54f95fca5e81bfe004075669"
if file_hash(FROZEN_PATH) != FROZEN_SHA256:
    raise ValueError("frozen reporting dependency changed")
SPEC = importlib.util.spec_from_file_location("_original_p1_report", FROZEN_PATH)
assert SPEC is not None and SPEC.loader is not None
FROZEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FROZEN)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def decimal(value: object) -> Decimal:
    return Decimal(str(value))


def verified_files(hashes: dict, root: Path | None = None) -> dict:
    result = {}
    for name, expected in hashes.items():
        path = root / name if root is not None else Path(name)
        require(path.is_file() and file_hash(path) == expected, "input hash mismatch: " + str(path))
        result[str(path.resolve())] = expected
    return result


def require_prefix(original: Path, resumed: Path, count: int) -> None:
    old = original.read_bytes().splitlines(keepends=True)
    new = resumed.read_bytes().splitlines(keepends=True)
    require(len(old) >= count and len(new) >= count, "missing retained journal prefix")
    require(old[:count] == new[:count], "retained journal prefix bytes changed")


def reconcile_ledger(
    amendment: dict,
    original: dict,
    ledger: dict,
    original_requests: dict,
    requests: dict,
    outcomes: dict,
) -> dict:
    """Bind admitted calls to ordered journals, allowing repeated payload hashes."""
    rows = ledger["attempts"]
    old = original["attempts"]
    require(len(old) == 79 and rows[:79] == old, "original 79 ledger rows changed")
    require(79 <= len(rows) <= 91, "cumulative provider cap exceeded")
    require(ledger["budget"] == amendment["budget"], "amended budget mismatch")
    require(ledger["experiment_id"] == amendment["original_experiment_id"], "experiment mismatch")
    require(
        ledger["continuation"]["amendment_id"] == amendment["amendment_id"],
        "ledger amendment mismatch",
    )
    require(
        [row["attempt_number"] for row in rows] == list(range(1, len(rows) + 1)),
        "attempt order mismatch",
    )
    require(ledger["provider_attempts_started"] == len(rows), "provider attempt count mismatch")
    require(
        old[-1]["status"] == "pending"
        and not old[-1]["completion_received"]
        and not old[-1]["reservation_released"]
        and decimal(old[-1]["reserved_usd"]) == Decimal("0.46678016"),
        "original uncertain attempt was resolved or reserve changed",
    )
    original_sequence = [
        (method, row["prepared"]["request_sha256"])
        for method in FROZEN.METHODS
        for row in original_requests[method]
    ]
    require(
        original_sequence == [(row["method"], row["request_sha256"]) for row in old],
        "original request/ledger order mismatch",
    )
    suffix = requests["answer_history"][18:]
    new_rows = rows[79:]
    denials = ledger["guard_denials_before_provider"]
    require(type(denials) is int and 0 <= denials <= 1, "invalid guard denial count")
    require(len(suffix) == len(new_rows) + denials, "new collector/provider count mismatch")
    admitted = [(row["method"], row["request_sha256"]) for row in new_rows]
    observed = [("answer_history", row["prepared"]["request_sha256"]) for row in suffix]
    require(admitted == observed[: len(new_rows)], "new ledger/journal order mismatch")
    require(Counter(admitted) <= Counter(observed), "new ledger/journal multiplicity mismatch")
    if new_rows:
        require(
            new_rows[0]["attempt_number"] == 80
            and new_rows[0]["request_sha256"]
            == old[-1]["request_sha256"]
            == amendment["explicit_retry_request_sha256"],
            "first continuation attempt does not bind explicit retry",
        )
    for method in FROZEN.METHODS:
        retained = 18 if method == "answer_history" else 30
        require(
            requests[method][:retained] == original_requests[method][:retained], "prefix changed"
        )
        require(len(requests[method]) == len(outcomes[method]), "finalized outcome count mismatch")
    paired = list(zip(old[:30], outcomes["snapshot"]))
    paired += list(zip(old[30:60], outcomes["structured_state"]))
    paired += list(zip(old[60:78], outcomes["answer_history"][:18]))
    paired += list(zip(new_rows, outcomes["answer_history"][18:]))
    for row, outcome in paired:
        require(
            row["request_sha256"] == outcome["request_sha256"], "outcome request binding mismatch"
        )
        require(row["completion_received"] == ("metadata" in outcome), "completion count mismatch")
        if row["completion_received"]:
            require(
                row["raw_response_sha256"] == outcome["raw_response_sha256"],
                "response hash differs from ledger",
            )
            require(
                row["response_model"] == outcome["metadata"]["response_model"],
                "returned model differs from ledger",
            )
            if row.get("usage_verified"):
                require(
                    row["usage"]
                    == {key: outcome["metadata"]["usage"][key] for key in row["usage"]},
                    "usage differs from ledger",
                )
            charge = row.get("conservative_reported_cost_usd")
            if charge is not None:
                expected = (
                    row["usage"]["prompt_tokens"] * Decimal("0.44")
                    + row["usage"]["completion_tokens"] * Decimal("1.32")
                ) / 1_000_000
                require(decimal(charge) == expected, "conservative cost arithmetic mismatch")
    received = sum("metadata" in row for group in outcomes.values() for row in group)
    require(
        ledger["provider_completions_received"]
        == received
        == sum(row["completion_received"] for row in rows),
        "cumulative received count mismatch",
    )
    spent = sum(
        (
            decimal(row["conservative_reported_cost_usd"])
            for row in rows
            if row.get("conservative_reported_cost_usd") is not None
        ),
        Decimal(0),
    )
    pending = sum(
        (decimal(row["reserved_usd"]) for row in rows if not row["reservation_released"]),
        Decimal(0),
    )
    require(pending >= Decimal("0.46678016"), "original reserve released")
    require(decimal(ledger["conservative_reported_cost_usd"]) == spent, "settled cost mismatch")
    require(decimal(ledger["pending_reservation_usd"]) == pending, "pending reserve mismatch")
    require(decimal(ledger["spent_plus_pending_usd"]) == spent + pending, "budget balance mismatch")
    require(spent + pending <= Decimal("1.5"), "conditional allowance exceeded")
    require(
        all(decimal(row["reserved_usd"]) == Decimal("0.46678016") for row in rows),
        "per-call reserve mismatch",
    )
    require(
        all(
            type(row["request_bytes"]) is int and 0 < row["request_bytes"] <= 262144 for row in rows
        ),
        "request bytes cap exceeded",
    )
    require(
        decimal(ledger["allowance_remaining_after_reservations_usd"])
        == Decimal("1.5") - spent - pending,
        "remaining allowance mismatch",
    )
    require(all(row["requested_output_tokens"] == 4096 for row in rows), "output cap mismatch")
    require(
        ledger["requested_output_tokens_reserved_total"] == len(rows) * 4096 <= 372736,
        "cumulative requested output mismatch",
    )
    collector_count = sum(len(group) for group in requests.values())
    require(collector_count == len(rows) - 1 + denials, "collector/admitted reconciliation failed")
    return {
        "cumulative_provider_calls_admitted": len(rows),
        "new_provider_calls_admitted": len(new_rows),
        "benchmark_collection_attempts": collector_count,
        "benchmark_response_count": received,
        "benchmark_scoring_opportunities": 90,
        "guard_denials_before_provider": denials,
        "cumulative_calls_per_method": dict(Counter(row["method"] for row in rows)),
        "historical_ledger_rows_unchanged": 79,
        "retained_answer_history_prefix_responses": 18,
        "explicit_retry": {
            "original_attempt": 79,
            "new_attempt": 80 if new_rows else None,
            "request_sha256": amendment["explicit_retry_request_sha256"],
        },
        "unresolved_original_attempt_outside_benchmark_collection": old[-1],
        "conservative_observed_peak_cost_usd": float(spent),
        "pending_reservation_usd": float(pending),
        "original_pending_reservation_usd": 0.46678016,
        "spent_plus_pending_usd": float(spent + pending),
        "allowance_remaining_usd": float(Decimal("1.5") - spent - pending),
        "allowance_usd": 1.5,
        "requested_output_tokens_reserved_total": len(rows) * 4096,
        "active_attempt": ledger["active_attempt"],
        "halted": ledger["halted"],
        "halt_reason": ledger["halt_reason"],
        "conditional_budget_assumptions_satisfied": ledger[
            "conditional_budget_assumptions_satisfied"
        ],
        "actual_total_cost_usd": None,
        "billing_guarantee": False,
        "note": "Original attempt 79 is unresolved, not erased or settled by retry 80. "
        "Reservations are admission accounting, not measured provider charges.",
    }


def failure_diagnostics(outcomes: list[dict], responses: list[dict], score: dict) -> dict:
    by_key = {(r["episode_id"], r["checkpoint_id"]): r["raw_response"] for r in responses}
    categories = Counter()
    rows = []
    for outcome in outcomes:
        if outcome["status"] == "accepted":
            continue
        key = (outcome["episode_id"], outcome["checkpoint_id"])
        raw = by_key.get(key)
        finish = outcome.get("metadata", {}).get("finish_reason")
        if raw is None:
            category = "no_received_final_answer"
        elif not raw.strip():
            category = "empty_final_at_output_limit" if finish == "length" else "empty_final"
        else:
            try:
                parsed = FROZEN.strict_json(raw)
            except (ValueError, TypeError):
                category = (
                    "partial_or_invalid_json_at_output_limit"
                    if finish == "length"
                    else "invalid_json"
                )
            else:
                if not isinstance(parsed, dict):
                    category = "wrong_json_root_type"
                elif isinstance(parsed.get("state"), str) and isinstance(
                    parsed.get("action"), dict
                ):
                    category = "state_action_structure_swapped"
                elif not isinstance(parsed.get("action"), str):
                    category = "wrong_action_json_type"
                elif not isinstance(parsed.get("state"), dict):
                    category = "wrong_state_json_type"
                else:
                    category = "other_schema_failure"
        categories[category] += 1
        rows.append(
            {
                "episode_id": key[0],
                "checkpoint_id": key[1],
                "status": outcome["status"],
                "finish_reason": finish,
                "category": category,
                "raw_response_sha256": outcome.get("raw_response_sha256"),
            }
        )
    valid = [row for row in score["per_checkpoint"] if row["status"] == "ok"]
    counts = Counter()
    for row in valid:
        counts.update(row["counts"])
    return {
        "received_or_attempted_failure_counts": dict(sorted(categories.items())),
        "failures": rows,
        "unsubmitted_checkpoints": sum(
            (row["episode_id"], row["checkpoint_id"])
            not in {(outcome["episode_id"], outcome["checkpoint_id"]) for outcome in outcomes}
            for row in score["per_checkpoint"]
        ),
        "secondary_valid_only_diagnostic": {
            "valid_checkpoint_count": len(valid),
            "state_accuracy": FROZEN.rate(counts["value_correct"], counts["slots"]),
            "grounded_state": FROZEN.rate(counts["grounded_correct"], counts["slots"]),
            "known_grounded_accuracy": FROZEN.rate(
                counts["known_grounded_correct"], counts["known_required"]
            ),
            "selection_warning": "Conditioned on valid model answers; not a replacement for fixed-denominator primary scores.",
        },
    }


def markdown(report: dict) -> str:
    budget = report["provider_call_accounting"]
    lines = [
        "# P1 explicitly amended DeepSeek continuation",
        "",
        "Status: "
        + report["matrix_status"]
        + ". Original interrupted no-retry experiment is retained separately.",
        "",
        "The primary score is V2 known-value grounding on all 96 known-field opportunities per method. "
        "Correct values must have citations accepted by the frozen policy. Schema failures and missing checkpoints remain in denominators.",
        "",
        "| Method | Received / planned | Schema | V2 known grounding (primary) | V2 all fields | V1 all fields |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for method, result in report["methods"].items():
        metric = result["v2"]["metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    method,
                    str(result["request_accounting"]["completions_received"]) + "/30",
                    FROZEN.format_rate(metric["schema_success"]),
                    FROZEN.format_rate(metric["known_grounded_accuracy"]),
                    FROZEN.format_rate(metric["grounded_state"]),
                    FROZEN.format_rate(result["v1"]["metrics"]["grounded_state"]),
                ]
            )
            + " |"
        )
    lines += [
        "",
        "## Per-event V2 results",
        "",
        "| Method | Storm | Schema | Known grounding | All-field grounding |",
        "| --- | --- | --- | --- | --- |",
    ]
    for method, result in report["methods"].items():
        for row in result["v2"]["per_event"]:
            lines.append(
                "| "
                + " | ".join(
                    [method, row["group_id"]]
                    + [
                        FROZEN.format_rate(row["metrics"][name])
                        for name in ("schema_success", "known_grounded_accuracy", "grounded_state")
                    ]
                )
                + " |"
            )
    lines += [
        "",
        "Full V1/V2 per-event, event-macro, branch and descriptive paired differences are in report.json. "
        "No significance inference is made from three storms and one repeat.",
        "",
        "## Failures and conditional diagnostics",
        "",
    ]
    for method, result in report["methods"].items():
        diag = result["failure_diagnostics"]
        valid = diag["secondary_valid_only_diagnostic"]
        lines += [
            "- " + method + ": " + str(diag["received_or_attempted_failure_counts"]) + ". "
            "Secondary valid-only: " + str(valid["valid_checkpoint_count"]) + " checkpoints, "
            "grounded fields " + FROZEN.format_rate(valid["grounded_state"]) + "."
        ]
    lines += [
        "",
        "Valid-only diagnostics select on successful formatting and must not replace the fixed-denominator scores. "
        "evaluator_unverifiable is a restricted-grammar support result, not automatically a hallucination.",
        "",
        "## Calls, usage, costs and timing",
        "",
        f"Cumulative admitted calls: {budget['cumulative_provider_calls_admitted']}; new continuation calls: {budget['new_provider_calls_admitted']}; "
        f"received benchmark responses: {budget['benchmark_response_count']}; planned scoring opportunities: 90.",
        "",
        "Original attempt 79 remains unresolved outside the benchmark collection; attempt 80 explicitly reissues its exact payload. "
        "The received 78 original answers, including invalid answers, are retained without retry.",
        "",
        "Actual total expense remains unknown. Cache-aware received-response subtotal at declared rates: USD "
        + str(report["cost_estimate"]["cache_aware_subtotal_at_declared_rates_usd"])
        + ". "
        "This subtotal is not the total bill and excludes unreported usage from original attempt 79.",
        "",
        "Conservative reported peak-rate accounting: USD "
        + str(budget["conservative_observed_peak_cost_usd"])
        + "; "
        "pending reservation: USD " + str(budget["pending_reservation_usd"]) + "; "
        "remaining conditional allowance: USD " + str(budget["allowance_remaining_usd"]) + ". "
        "The original USD 0.46678016 reservation is retained; reservations are not measured charges.",
        "",
        "Reported token totals: " + str(report["reported_usage"]["totals_where_reported"]) + ". "
        "Reasoning tokens are already included in completion tokens.",
        "",
        "| Method | Transport mean seconds | p50 | p95 | Observed cache-aware subtotal USD |",
        "| --- | --- | --- | --- | --- |",
    ]
    for method, result in report["methods"].items():
        latency = result["transport_latency"]
        lines.append(
            "| "
            + " | ".join(
                [method]
                + [
                    f"{latency[key]:.3f}" if latency[key] is not None else "unknown"
                    for key in ("mean_seconds", "p50_seconds", "p95_seconds")
                ]
                + [str(result["cost_estimate"]["cache_aware_subtotal_at_declared_rates_usd"])]
            )
            + " |"
        )
    lines += [
        "",
        FROZEN.LATENCY_DEFINITION,
        "",
        "## Interpretation and provenance",
        "",
        report["interpretation"],
        "",
        "The continuation is a separately authorized amendment with USD 1.5 cumulative conditional allowance, "
        "at most 12 additional and 91 cumulative attempts, one explicit uncertain-request retry, no automatic retries and no heldout calls. "
        "It is not the original uninterrupted 90-request experiment. The restart adds a time/cache confound.",
        "",
        "The output prompt does not explicitly state that action is a string; prior valid carrier answers also supply format examples. "
        "These are candidate explanations to test in a later controlled output-contract and output-budget study, not proven causes. "
        "All methods see cumulative delivered evidence; this experiment does not isolate memory dependence.",
        "",
        "Original source files, raw answers, frozen code/data/scorers, journals and prior partial results are preserved. "
        "This report makes zero API calls and uses deterministic scoring without new item-level human annotation or an LLM judge.",
        "",
    ]
    return "\n".join(lines)


def create_report(amendment_path: Path, continuation: Path, output: Path) -> dict:
    require(not output.exists() and not output.is_symlink(), "report output exists")
    amendment = FROZEN.read_object(amendment_path)
    require(
        amendment["amendment_id"]
        == fingerprint({k: v for k, v in amendment.items() if k != "amendment_id"}),
        "amendment fingerprint mismatch",
    )
    source = Path(amendment["original_source_root"])
    prefix = Path(amendment["prepared_prefix_path"])
    for protected in (source, prefix, continuation / "runs", continuation / "rescores"):
        require(
            not output.resolve().is_relative_to(protected.resolve()),
            "report overlaps protected inputs",
        )
    inputs = verified_files(amendment["original_source_files_sha256"], source)
    require(
        len(amendment["original_source_files_sha256"]) == 83, "original capture inventory mismatch"
    )
    inputs.update(verified_files(amendment["prepared_files_sha256"], prefix.parent))
    inputs.update(verified_files(amendment["frozen_files_sha256"]))
    experiment_path = Path(amendment["experiment_path"])
    experiment = FROZEN.read_object(experiment_path)
    require(
        experiment["experiment_id"]
        == amendment["original_experiment_id"]
        == fingerprint({k: v for k, v in experiment.items() if k != "experiment_id"}),
        "experiment fingerprint mismatch",
    )
    rates = FROZEN.validate_rates(Path(experiment["rates_path"]))
    require(
        FROZEN.read_object(continuation / "amendment_snapshot.json") == amendment,
        "amendment snapshot mismatch",
    )
    authorization = FROZEN.read_object(continuation / "authorization.json")
    launch = FROZEN.read_object(continuation / "launch.json")
    expected_authorization = {
        "authorized": True,
        "original_experiment_id": amendment["original_experiment_id"],
        "amendment_id": amendment["amendment_id"],
        "allowance_usd": "1.5",
        "max_additional_provider_attempts": 12,
        "max_cumulative_provider_attempts": 91,
        "explicit_retry_original_attempt": 79,
    }
    require(
        all(
            type(authorization.get(key)) is type(value) and authorization[key] == value
            for key, value in expected_authorization.items()
        ),
        "authorization scope mismatch",
    )
    require(
        isinstance(authorization.get("user_message"), str)
        and bool(authorization["user_message"].strip()),
        "missing actual authorization text",
    )
    require(
        launch["authorization_sha256"] == file_hash(continuation / "authorization.json")
        and launch["authorization_snapshot_sha256"] == fingerprint(authorization)
        and launch["amendment_id"] == amendment["amendment_id"],
        "launch authorization binding mismatch",
    )
    status = FROZEN.read_object(continuation / "status.json")
    execution = FROZEN.read_object(continuation / "execution.json")
    exit_record = FROZEN.read_object(continuation / "exit.json")
    require(
        status["status"] in {"completed", "stopped"}
        and status["exit_code"] == exit_record["exit_code"],
        "worker not finalized",
    )
    require(
        execution["status"] == status["status"] and not execution["injected_offline_transport"],
        "worker execution mismatch",
    )
    require(execution["amendment_id"] == amendment["amendment_id"], "execution amendment mismatch")
    for name in ("requests.jsonl", "responses.jsonl", "outcomes.jsonl"):
        require_prefix(
            source / "runs/answer_history/collection" / name,
            continuation / "runs/answer_history/collection" / name,
            18,
        )
    methods, outcomes, requests, original_requests = {}, {}, {}, {}
    for method in FROZEN.METHODS:
        if method != "answer_history":
            for dirname in ("runs", "rescores"):
                require(
                    (continuation / dirname / method).resolve()
                    == (source / dirname / method).resolve(),
                    "completed method alias changed",
                )
        result, rows, bindings = FROZEN.read_method(
            method, continuation / "runs", continuation / "rescores", experiment, rates
        )
        methods[method], outcomes[method] = result, rows
        inputs.update(bindings)
        collection = continuation / "runs" / method / "collection"
        requests[method] = read_jsonl(collection / "requests.jsonl")
        original_requests[method] = read_jsonl(
            source / "runs" / method / "collection/requests.jsonl"
        )
        result["failure_diagnostics"] = failure_diagnostics(
            rows,
            read_jsonl(collection / "responses.jsonl"),
            FROZEN.read_object(continuation / "rescores" / method / "score_v2.json"),
        )
        for name in ("requests.jsonl", "responses.jsonl", "plan.json"):
            path = collection / name
            inputs[str(path.resolve())] = file_hash(path)
    ledger = FROZEN.read_object(continuation / "budget_ledger.json")
    accounting = reconcile_ledger(
        amendment,
        FROZEN.read_object(source / "budget_ledger.json"),
        ledger,
        original_requests,
        requests,
        outcomes,
    )
    require(
        execution["cumulative_provider_attempts"]
        == accounting["cumulative_provider_calls_admitted"]
        and execution["new_provider_attempts"] == accounting["new_provider_calls_admitted"]
        and execution["cumulative_completions_received"] == accounting["benchmark_response_count"],
        "execution accounting mismatch",
    )
    for method, result in methods.items():
        admitted = accounting["cumulative_calls_per_method"][method]
        result["request_accounting"]["cumulative_provider_calls_admitted"] = admitted
        result["reported_usage"] = FROZEN.summarize_usage(outcomes[method], admitted)
        result["transport_latency"] = FROZEN.summarize_latency(outcomes[method], admitted)
        result["cost_estimate"] = FROZEN.cost_estimate(
            result["reported_usage"], outcomes[method], rates
        )
    all_outcomes = [row for group in outcomes.values() for row in group]
    usage = FROZEN.summarize_usage(all_outcomes, accounting["cumulative_provider_calls_admitted"])
    cost = FROZEN.cost_estimate(usage, all_outcomes, rates)
    require(cost["estimated_usd"] is None, "unresolved original charge must leave total unknown")
    for name in (
        "budget_ledger.json",
        "authorization.json",
        "amendment_snapshot.json",
        "launch.json",
        "execution.json",
        "status.json",
        "exit.json",
    ):
        path = continuation / name
        inputs[str(path.resolve())] = file_hash(path)
    inputs[str(amendment_path.resolve())] = file_hash(amendment_path)
    report = {
        "schema_version": "deepseek_amended_continuation_report_v1",
        "amendment_id": amendment["amendment_id"],
        "original_experiment_id": experiment["experiment_id"],
        "build_id": experiment["build_id"],
        "implementation_id": experiment["implementation_id"],
        "matrix_status": "completed_amended_continuation"
        if status["status"] == "completed"
        else "partial_amended_continuation",
        "primary_metric": "v2.known_grounded_accuracy; all fixed known-field opportunities",
        "methods": methods,
        "independent_event_count": 3,
        "repeats": 1,
        "paired_method_differences": FROZEN.paired_method_differences(methods),
        "provider_call_accounting": accounting,
        "reported_usage": usage,
        "transport_latency": FROZEN.summarize_latency(
            all_outcomes, accounting["cumulative_provider_calls_admitted"]
        ),
        "cost_estimate": cost,
        "input_sha256": inputs,
        "original_no_retry_partial_report": str(
            source.with_name(source.name + "-interrupted-finalization") / "report/report.json"
        ),
        "new_provider_requests_by_report": 0,
        "eligible_for_llm_leaderboard": False,
        "interpretation": FROZEN.INTERPRETATION
        + " This is an explicitly amended continuation with a machine restart and one authorized uncertain-request retry. Total cost remains unknown.",
    }
    verified_files(inputs)
    output.mkdir(parents=True)
    write_json(output / "report.json", report)
    (output / "REPORT.md").write_text(markdown(report), encoding="ascii")
    manifest = {
        "schema_version": "offline_amended_continuation_report_manifest_v1",
        "amendment_id": amendment["amendment_id"],
        "report_script_sha256": file_hash(Path(__file__)),
        "frozen_reporting_dependency_sha256": FROZEN_SHA256,
        "input_sha256": inputs,
        "new_provider_requests": 0,
        "files": {name: file_hash(output / name) for name in ("report.json", "REPORT.md")},
    }
    manifest["report_id"] = fingerprint(manifest)
    write_json(output / "manifest.json", manifest)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--continuation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = create_report(args.amendment, args.continuation, args.output)
    print(
        "Offline continuation report: "
        + report["matrix_status"]
        + "; total expense remains unknown; new API requests=0"
    )


if __name__ == "__main__":
    main()
