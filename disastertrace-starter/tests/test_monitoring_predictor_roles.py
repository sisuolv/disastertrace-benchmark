"""Separately controlled selectors and predictors share actual model budgets."""

import json

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_fixed_v1.outcomes import experiment_spec
from disastertrace.monitoring_v1.policies import run_session


def test_llm_selector_can_use_the_original_program_predictor_without_extra_model_calls():
    data, bank, config = typed_fixture(
        selector_kind="llm",
        predictor_kind="program",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        model_call_budget=1,
    )
    invoked = []

    def backend(system, request, call_id):
        invoked.append(call_id)
        assert call_id.startswith("select-")
        assert request["forecast_executor_kind"] == "program"
        assert request["forecast_model_call_cost"] == 0
        assert request["forecast_call_upper"]["tokens"] == 0
        raw = json.dumps(
            {
                "query_order": list(request["queries"]),
                "forecast_handles": list(request["targets"])[:2],
            }
        )
        return raw, {
            "input_tokens": 11,
            "output_tokens": 9,
            "seconds": 0.01,
            "ended_with_eos": True,
        }

    report = run_session(data, bank, config, backend=backend)
    assert invoked == ["select-0"]
    assert len(report["calls"]) == 2 and all(r["head"] == "program" for r in report["calls"])
    assert report["actual_model_calls"] == 1
    assert report["actual_program_forecast_calls"] == 2
    assert report["resource_spent"]["tokens"] == 20
    assert report["resource_spent"]["compute_ms"] >= 12
    assert all(
        e["upper"]["tokens"] == 0
        for e in report["resource_events"]
        if e["event"] == "reserve" and e["receipt_id"].startswith("forecast-")
    )


def test_explicit_model_predictor_still_pays_for_both_model_roles():
    data, bank, config = typed_fixture(
        selector_kind="llm",
        predictor_kind="llm",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        model_call_budget=2,
    )
    invoked = []

    def backend(system, request, call_id):
        invoked.append(call_id)
        if call_id.startswith("select-"):
            assert request["forecast_executor_kind"] == "llm"
            assert request["forecast_model_call_cost"] == 1
        value = (
            {"query_order": [], "forecast_handles": list(request["targets"])[:2]}
            if call_id.startswith("select-")
            else {"fact_truth": "unknown", "probability": 0.3}
        )
        return json.dumps(value), {
            "input_tokens": 11,
            "output_tokens": 9,
            "seconds": 0.01,
            "ended_with_eos": True,
        }

    report = run_session(data, bank, config, backend=backend)
    assert invoked == ["select-0", "forecast-0"]
    assert len(report["calls"]) == 1 and report["actual_model_calls"] == 2
    assert report["actual_program_forecast_calls"] == 0
    assert report["resource_spent"]["tokens"] == 40


def test_predictor_kind_is_a_declared_comparison_factor_with_unchanged_invariants():
    data, bank, config = typed_fixture()
    program = experiment_spec(data, bank, dict(config, predictor_kind="program"))
    model = experiment_spec(data, bank, dict(config, predictor_kind="llm"))
    assert program["invariants"] == model["invariants"]
    assert program["interventions"]["predictor_kind"] == "program"
    assert model["interventions"]["predictor_kind"] == "llm"


def test_model_role_cannot_silently_fall_back_to_a_program():
    data, bank, config = typed_fixture(predictor_kind="llm")
    with pytest.raises(ValueError, match="predictor"):
        run_session(data, bank, config)
