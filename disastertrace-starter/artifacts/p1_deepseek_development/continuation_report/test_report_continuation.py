"""Offline regression and integration tests; real saved data are immutable fixtures."""

from __future__ import annotations

import copy
import importlib.util
import urllib.request
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = importlib.util.spec_from_file_location(
    "_continuation_report_test", HERE / "report_continuation.py"
)
assert SPEC is not None and SPEC.loader is not None
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)
AMENDMENT = HERE.parent / "background_resume/prepared/amendment.json"
CONTINUATION = ROOT / "work/p1-deepseek-background-continuation-v1"


@pytest.fixture
def saved_accounting():
    amendment = REPORT.FROZEN.read_object(AMENDMENT)
    source = Path(amendment["original_source_root"])
    original = REPORT.FROZEN.read_object(source / "budget_ledger.json")
    ledger = REPORT.FROZEN.read_object(CONTINUATION / "budget_ledger.json")
    original_requests, requests, outcomes = {}, {}, {}
    for method in REPORT.FROZEN.METHODS:
        original_requests[method] = REPORT.read_jsonl(
            source / "runs" / method / "collection/requests.jsonl"
        )
        requests[method] = REPORT.read_jsonl(
            CONTINUATION / "runs" / method / "collection/requests.jsonl"
        )
        outcomes[method] = REPORT.read_jsonl(
            CONTINUATION / "runs" / method / "collection/outcomes.jsonl"
        )
    return amendment, original, ledger, original_requests, requests, outcomes


def test_reconciliation_keeps_unresolved_original_outside_ninety_answers(saved_accounting):
    result = REPORT.reconcile_ledger(*saved_accounting)
    assert result["cumulative_provider_calls_admitted"] == 91
    assert result["benchmark_response_count"] == result["benchmark_scoring_opportunities"] == 90
    assert result["new_provider_calls_admitted"] == 12
    assert result["actual_total_cost_usd"] is None
    assert result["pending_reservation_usd"] == 0.46678016
    assert result["conservative_observed_peak_cost_usd"] == 0.354178


@pytest.mark.parametrize(
    "defect",
    [
        "old_row_changed",
        "retry_changed",
        "reordered_suffix",
        "usage_changed",
        "release_old_reserve",
        "over_cap",
        "request_bytes",
        "reservation",
    ],
)
def test_reconciliation_rejects_tampered_history_accounting_and_limits(saved_accounting, defect):
    args = copy.deepcopy(saved_accounting)
    _, _, ledger, _, _, outcomes = args
    if defect == "old_row_changed":
        ledger["attempts"][0]["started_at"] = "changed"
    elif defect == "retry_changed":
        ledger["attempts"][79]["request_sha256"] = "different"
    elif defect == "reordered_suffix":
        ledger["attempts"][80]["request_sha256"], ledger["attempts"][81]["request_sha256"] = (
            ledger["attempts"][81]["request_sha256"],
            ledger["attempts"][80]["request_sha256"],
        )
    elif defect == "usage_changed":
        outcomes["answer_history"][18]["metadata"]["usage"]["prompt_tokens"] += 1
    elif defect == "release_old_reserve":
        ledger["pending_reservation_usd"] = 0
    elif defect == "over_cap":
        ledger["attempts"].append(copy.deepcopy(ledger["attempts"][-1]))
    elif defect == "request_bytes":
        ledger["attempts"][-1]["request_bytes"] = 262145
    elif defect == "reservation":
        ledger["attempts"][-1]["reserved_usd"] = 0.4
    with pytest.raises(ValueError):
        REPORT.reconcile_ledger(*args)


def test_equal_payload_hashes_at_distinct_positions_are_not_deduplicated(saved_accounting):
    args = copy.deepcopy(saved_accounting)
    _, _, ledger, _, requests, outcomes = args
    duplicate_hash = ledger["attempts"][79]["request_sha256"]
    ledger["attempts"][80]["request_sha256"] = duplicate_hash
    requests["answer_history"][19]["prepared"]["request_sha256"] = duplicate_hash
    outcomes["answer_history"][19]["request_sha256"] = duplicate_hash
    assert REPORT.reconcile_ledger(*args)["new_provider_calls_admitted"] == 12


def test_partial_continuation_keeps_ninety_scoring_opportunities(saved_accounting):
    args = copy.deepcopy(saved_accounting)
    _, _, ledger, _, requests, outcomes = args
    ledger["attempts"] = ledger["attempts"][:80]
    ledger["provider_attempts_started"] = 80
    ledger["provider_completions_received"] = 79
    ledger["requested_output_tokens_reserved_total"] = 80 * 4096
    spent = sum(
        (
            Decimal(str(row["conservative_reported_cost_usd"]))
            for row in ledger["attempts"]
            if row.get("conservative_reported_cost_usd") is not None
        ),
        Decimal(0),
    )
    pending = Decimal("0.46678016")
    ledger["conservative_reported_cost_usd"] = float(spent)
    ledger["spent_plus_pending_usd"] = float(spent + pending)
    ledger["allowance_remaining_after_reservations_usd"] = float(Decimal("1.5") - spent - pending)
    requests["answer_history"] = requests["answer_history"][:19]
    outcomes["answer_history"] = outcomes["answer_history"][:19]
    result = REPORT.reconcile_ledger(*args)
    assert result["benchmark_response_count"] == 79
    assert result["benchmark_scoring_opportunities"] == 90


def test_retained_prefix_is_checked_as_bytes(tmp_path):
    old, new = tmp_path / "old.jsonl", tmp_path / "new.jsonl"
    old.write_bytes(b'{"a":1}\n')
    new.write_bytes(b'{"a":1}\r\n')
    with pytest.raises(ValueError, match="prefix bytes"):
        REPORT.require_prefix(old, new, 1)


@pytest.mark.parametrize(
    "raw,finish,expected",
    [
        ("", "length", "empty_final_at_output_limit"),
        ('{"state":', "length", "partial_or_invalid_json_at_output_limit"),
        ('{"state":{},"action":{}}', "stop", "wrong_action_json_type"),
        ('{"state":"monitor","action":{}}', "stop", "state_action_structure_swapped"),
        ("[]", "stop", "wrong_json_root_type"),
    ],
)
def test_failure_taxonomy_does_not_repair_outputs(raw, finish, expected):
    outcome = {
        "episode_id": "storm",
        "checkpoint_id": "c0",
        "status": "invalid",
        "metadata": {"finish_reason": finish},
    }
    response = {"episode_id": "storm", "checkpoint_id": "c0", "raw_response": raw}
    score = {
        "per_checkpoint": [
            {"episode_id": "storm", "checkpoint_id": "c0", "status": "invalid"},
            {"episode_id": "storm", "checkpoint_id": "c1", "status": "missing"},
        ]
    }
    result = REPORT.failure_diagnostics([outcome], [response], score)
    assert result["received_or_attempted_failure_counts"] == {expected: 1}
    assert result["unsubmitted_checkpoints"] == 1
    assert result["secondary_valid_only_diagnostic"]["grounded_state"]["value"] is None


def test_total_unknown_even_when_every_benchmark_answer_has_usage(saved_accounting):
    outcomes = [row for group in saved_accounting[-1].values() for row in group]
    usage = REPORT.FROZEN.summarize_usage(outcomes, 91)
    rates = REPORT.FROZEN.validate_rates(HERE.parent / "docs/rates.json")
    cost = REPORT.FROZEN.cost_estimate(usage, outcomes, rates)
    assert usage["completions_received"] == 90
    assert usage["attempts_without_completion_metadata"] == 1
    assert cost["estimated_usd"] is None
    assert cost["cache_aware_subtotal_at_declared_rates_usd"] == 0.146989544
    assert cost["pricing_window_verified_from_provider_timestamp"]


@pytest.mark.parametrize("defect", ["authorized", "scope", "launch_hash", "launch_fingerprint"])
def test_report_rejects_unbound_or_mismatched_authorization(tmp_path, monkeypatch, defect):
    original_reader = REPORT.FROZEN.read_object

    def altered_reader(path):
        value = original_reader(path)
        if Path(path) == CONTINUATION / "authorization.json":
            if defect == "authorized":
                value["authorized"] = False
            elif defect == "scope":
                value["max_additional_provider_attempts"] = 13
        if Path(path) == CONTINUATION / "launch.json":
            if defect == "launch_hash":
                value["authorization_sha256"] = "0" * 64
            elif defect == "launch_fingerprint":
                value["authorization_snapshot_sha256"] = "0" * 64
        return value

    monkeypatch.setattr(REPORT.FROZEN, "read_object", altered_reader)
    with pytest.raises(ValueError, match="authorization"):
        REPORT.create_report(AMENDMENT, CONTINUATION, tmp_path / "report")


def test_integrated_offline_report_and_immutable_source_bindings(tmp_path, monkeypatch):
    def reject_network(*args, **kwargs):
        raise AssertionError("the reporter must not call a model API")

    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    output = tmp_path / "report"
    result = REPORT.create_report(AMENDMENT, CONTINUATION, output)
    assert result["matrix_status"] == "completed_amended_continuation"
    assert result["cost_estimate"]["estimated_usd"] is None
    assert result["new_provider_requests_by_report"] == 0
    assert result["methods"]["answer_history"]["v2"]["metrics"]["known_grounded_accuracy"] == {
        "numerator": 76,
        "denominator": 96,
        "value": 76 / 96,
    }
    assert result["methods"]["snapshot"]["failure_diagnostics"][
        "received_or_attempted_failure_counts"
    ] == {
        "empty_final_at_output_limit": 12,
        "partial_or_invalid_json_at_output_limit": 2,
        "wrong_action_json_type": 1,
        "state_action_structure_swapped": 1,
    }
    manifest = REPORT.FROZEN.read_object(output / "manifest.json")
    REPORT.verified_files(manifest["input_sha256"])
    REPORT.verified_files(manifest["files"], output)
    with pytest.raises(ValueError, match="output exists"):
        REPORT.create_report(AMENDMENT, CONTINUATION, output)
