"""Offline regressions for reporting actual usage and preserving score denominators."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from disastertrace.automated.common import file_hash, fingerprint, write_json

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("report_results.py")
SPEC = importlib.util.spec_from_file_location("p1_report_test_target", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
reporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reporter)


def outcome(usage=None, *, seconds=2.0, created=1788703471):
    return {
        "episode_id": "event:base",
        "checkpoint_id": "c0",
        "status": "accepted",
        "metadata": {
            "usage": usage,
            "response_model": "test_model",
            "elapsed_seconds": seconds,
            "raw_response_body": json.dumps({"created": created}),
        },
    }


def valid_usage():
    return {
        "prompt_tokens": 100,
        "completion_tokens": 30,
        "total_tokens": 130,
        "prompt_cache_hit_tokens": 40,
        "prompt_cache_miss_tokens": 60,
        "completion_tokens_details": {"reasoning_tokens": 20},
    }


def rates():
    return {
        "currency": "USD",
        "model": "test_model",
        "per_million_tokens": {"input_cache_hit": 1, "input_cache_miss": 2, "output": 3},
        "source": {"path": "synthetic_test_fixture", "sha256": "not_a_live_rate"},
        "window": {
            "start_utc": "2026-09-06T00:00:00+00:00",
            "end_utc": "2026-09-07T00:00:00+00:00",
        },
    }


def test_reasoning_is_in_completion_and_not_added_to_cost():
    rows = [outcome(valid_usage())]
    summary = reporter.summarize_usage(rows, 1)
    assert summary["totals_where_reported"]["total_tokens"] == 130
    assert summary["totals_where_reported"]["reasoning_tokens"] == 20
    estimate = reporter.cost_estimate(summary, rows, rates())
    assert estimate["estimated_usd"] == pytest.approx(0.00025)
    assert estimate["reasoning_tokens_charged_again"] is False


def test_missing_usage_and_transport_failure_do_not_become_zero_cost():
    rows = [outcome(), {"status": "provider_error"}]
    summary = reporter.summarize_usage(rows, 2)
    assert all(value is None for value in summary["totals_where_reported"].values())
    assert summary["attempts_without_completion_metadata"] == 1
    assert reporter.cost_estimate(summary, rows, rates())["estimated_usd"] is None


def test_inconsistent_cache_has_no_precise_cost_but_keeps_uncached_upper_estimate():
    usage = valid_usage()
    usage["prompt_cache_miss_tokens"] = 61
    rows = [outcome(usage)]
    summary = reporter.summarize_usage(rows, 1)
    assert summary["inconsistencies"][0]["reason"] == "cache_counts_do_not_equal_input"
    result = reporter.cost_estimate(summary, rows, rates())
    assert result["estimated_usd"] is None
    assert result["all_input_as_cache_miss_upper_estimate_at_declared_rates_usd"] == pytest.approx(
        0.00029
    )


def test_unknown_cache_usage_is_not_inferred_from_prompt_count():
    usage = valid_usage()
    del usage["prompt_cache_hit_tokens"]
    rows = [outcome(usage)]
    summary = reporter.summarize_usage(rows, 1)
    assert summary["responses_reporting_field"]["prompt_cache_hit_tokens"] == 0
    assert summary["totals_where_reported"]["prompt_cache_hit_tokens"] is None
    assert reporter.cost_estimate(summary, rows, rates())["estimated_usd"] is None


def test_response_after_pricing_window_not_priced_as_same_window():
    rows = [outcome(valid_usage(), created=1788825600)]
    result = reporter.cost_estimate(reporter.summarize_usage(rows, 1), rows, rates())
    assert result["estimated_usd"] is None
    assert result["response_created_timestamps_outside_pricing_window"] == 1


def test_different_response_model_disables_applicable_cost_estimate():
    rows = [outcome(valid_usage())]
    rows[0]["metadata"]["response_model"] = "different_model"
    result = reporter.cost_estimate(reporter.summarize_usage(rows, 1), rows, rates())
    assert result["estimated_usd"] is None
    assert result["response_models_match_priced_model"] is False
    assert result["cache_aware_subtotal_at_declared_rates_usd"] == pytest.approx(0.00025)


def test_latency_quantiles_and_missing_transport_failures_have_explicit_denominators():
    rows = [outcome(seconds=value) for value in (1.0, 2.0, 3.0, 4.0)]
    rows.append({"status": "provider_error"})
    result = reporter.summarize_latency(rows, 5)
    assert result["mean_seconds"] == 2.5
    assert result["p50_seconds"] == 2.5
    assert result["p95_seconds"] == pytest.approx(3.85)
    assert result["observed_requests"] == 4
    assert result["attempts_without_observed_latency"] == 1
    assert reporter.summarize_latency([], 0)["p95_seconds"] is None


def test_v1_known_metrics_exclude_correct_unknown_slots():
    source = reporter.read_object(ROOT / "work/deepseek-ida-state-v1/score.json")
    metrics = reporter.v1_metrics(source["metrics"])
    assert metrics["known_grounded_accuracy"] == reporter.rate(31, 32)
    assert metrics["known_value_accuracy"] == reporter.rate(32, 32)
    assert metrics["unknown_accuracy"] == reporter.rate(18, 18)


def test_v2_citation_reasons_include_both_summary_and_equivalent_body():
    source = reporter.read_object(ROOT / "work/deepseek-ida-rescore-v2/score_v2.json")
    result = reporter.citation_diagnostics(source)
    assert result["failed_slots"] == []
    assert result["slot_reason_counts"] == {"correct_unknown": 18, "supported": 32}
    assert result["citation_reason_counts"]["supported_body_observation"] == 1


def test_paired_method_opportunities_must_match():
    score = reporter.read_object(ROOT / "work/deepseek-ida-rescore-v2/score_v2.json")
    methods = {"snapshot": {"v2": score}, "structured_state": {"v2": copy.deepcopy(score)}}
    same = reporter.paired_method_differences(methods)
    assert same[0]["event_macro"]["known_grounded_accuracy"]["value"] == 0.0
    methods["structured_state"]["v2"]["per_event"][0]["metrics"]["known_grounded_accuracy"][
        "denominator"
    ] -= 1
    with pytest.raises(ValueError, match="opportunity denominators"):
        reporter.paired_method_differences(methods)


def historical_experiment(tmp_path):
    run = ROOT / "work/deepseek-ida-state-v1"
    derived = ROOT / "work/deepseek-ida-rescore-v2"
    context = reporter.read_object(run / "build_context.json")
    config = ROOT / "configs/provider.deepseek-flash.example.json"
    price_path = ROOT / "artifacts/p1_deepseek_development/docs/rates.json"
    experiment = {
        "test_only": "Historical Ida reporter regression; not the P1 experiment",
        "methods": list(reporter.METHODS),
        "development_event_ids": ["AL092021"],
        "expected_requests_per_method": 10,
        "total_requests": 30,
        "repeats": 1,
        "build_path": str(ROOT / "work/build-deepseek-v1"),
        "build_id": context["build_id"],
        "implementation_id": context["implementation_id"],
        "provider_config_path": str(config),
        "provider_config_sha256": file_hash(config),
        "rates_path": str(price_path),
        "rates_sha256": file_hash(price_path),
    }
    experiment["experiment_id"] = fingerprint(experiment)
    path = tmp_path / "experiment.json"
    write_json(path, experiment)
    for name, target in (("runs", run), ("rescores", derived)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "structured_state").symlink_to(target, target_is_directory=True)
    return path, price_path


def test_historical_report_is_verified_and_clearly_partial(tmp_path):
    experiment, price = historical_experiment(tmp_path)
    result = reporter.create_report(
        experiment,
        tmp_path / "runs",
        tmp_path / "rescores",
        price,
        tmp_path / "report",
        allow_partial=True,
    )
    assert result["matrix_status"] == "incomplete_descriptive_only"
    assert result["missing_methods"] == ["snapshot", "answer_history"]
    assert result["collector_attempts"] == 10
    assert result["provider_calls_admitted"] is None
    assert result["new_provider_requests_by_report"] == 0
    method = result["methods"]["structured_state"]
    assert method["verification"]["verified"] is True
    assert method["v1"]["metrics"]["known_grounded_accuracy"] == reporter.rate(31, 32)
    assert method["v2"]["metrics"]["known_grounded_accuracy"] == reporter.rate(32, 32)
    assert result["cost_estimate"]["estimated_usd"] is not None
    assert (tmp_path / "report/REPORT.md").read_text().isascii()
    with pytest.raises(ValueError, match="output exists"):
        reporter.create_report(
            experiment, tmp_path / "runs", tmp_path / "rescores", price, tmp_path / "report"
        )


def test_missing_method_is_rejected_without_explicit_partial_mode(tmp_path):
    experiment, price = historical_experiment(tmp_path)
    with pytest.raises(ValueError, match="required method collection/rescore is missing"):
        reporter.create_report(
            experiment, tmp_path / "runs", tmp_path / "rescores", price, tmp_path / "report"
        )


def test_modified_frozen_experiment_is_rejected(tmp_path):
    experiment, price = historical_experiment(tmp_path)
    value = reporter.read_object(experiment)
    value["total_requests"] += 1
    write_json(experiment, value)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        reporter.create_report(
            experiment,
            tmp_path / "runs",
            tmp_path / "rescores",
            price,
            tmp_path / "report",
            allow_partial=True,
        )


def test_budget_denial_is_not_counted_as_admitted_provider_call(tmp_path):
    runs = tmp_path / "runs"
    collection = runs / "snapshot/collection"
    collection.mkdir(parents=True)
    (collection / "requests.jsonl").write_text(
        "\n".join(json.dumps({"prepared": {"request_sha256": sha}}) for sha in ("sent", "denied"))
        + "\n"
    )
    ledger = {
        "experiment_id": "test_experiment",
        "budget": {"fixture": True},
        "provider_attempts_started": 1,
        "provider_completions_received": 1,
        "guard_denials_before_provider": 1,
        "attempts": [{"attempt_number": 1, "method": "snapshot", "request_sha256": "sent"}],
        "conservative_reported_cost_usd": 0.1,
        "pending_reservation_usd": 0,
        "halted": True,
        "halt_reason": "external_budget_allowance_exhausted",
        "conditional_budget_assumptions_satisfied": True,
        "monetary_cap_enforced": False,
        "billing_guarantee": False,
        "started_at": "test fixture",
        "updated_at": "test fixture",
        "elapsed_seconds": 1,
        "interpretation": "Synthetic ledger test; zero provider calls.",
    }
    write_json(tmp_path / "budget_ledger.json", ledger)
    methods = {
        "snapshot": {"request_accounting": {"attempts_started": 2, "completions_received": 1}}
    }
    experiment = {"experiment_id": "test_experiment", "budget": {"fixture": True}}
    result = reporter.budget_accounting(runs, experiment, methods)
    assert result["collector_attempts_started"] == 2
    assert result["provider_calls_admitted"] == 1
    ledger["attempts"][0]["request_sha256"] = "not_collected"
    write_json(tmp_path / "budget_ledger.json", ledger)
    with pytest.raises(ValueError, match="absent from collection journals"):
        reporter.budget_accounting(runs, experiment, methods)
