import json
from pathlib import Path

import pytest

from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.policies import parse_answer, run_session

ROOT = Path(__file__).resolve().parents[2] / "plans/v7_review_execution_20260912/regional_01"


def fixture():
    if not ROOT.exists():
        pytest.skip("Downloaded regional fixture not installed")
    data = load_session(ROOT, stations=["KSFO", "KOAK"], hours=2, threshold=1000)
    bank = {
        "minimum_cell_n": 20,
        "mapping_version": "synthetic_protocol_test_only",
        "cells": {'[1000,"pooled"]': {"n": 100, "positive": 20}},
    }
    config = {
        "seed": 20260912,
        "request_budget": 4,
        "forecast_call_cap": 4,
        "per_tick_forecast_cap": 2,
        "input_token_cap": 8192,
        "output_token_cap": 384,
        "call_compute_cap_ms": 120000,
        "wakeup_seconds": 600,
        "token_cap": 4 * (8192 + 384),
        "compute_ms_cap": 4 * 120100,
        "selector_kind": "round_robin",
        "isolation_mode": "public_schedule",
        "public_call_slot_ms": 120000,
        "allocation_mode": "global_budget",
        "authorization_mode": "target_private",
        "protocol": "base_bound_override",
    }
    return data, bank, config


def test_policy_entry_does_not_read_private_outcomes(monkeypatch):
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        if "OUTCOMES" in path.name:
            raise AssertionError("Policy opened evaluator outcomes")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    data, bank, config = fixture()
    trace = run_session(data, bank, config)
    assert len(trace["snapshots"]) == len(data["opportunities"])
    assert trace["resource_spent"]["requests"] <= config["request_budget"]
    assert all(value == 0 for value in trace["resource_reserved"].values())


def test_private_model_result_latency_and_token_count_do_not_change_other_target_inputs():
    data, bank, config = fixture()
    captures = []
    for bit in (0, 1):
        other_inputs = []

        def backend(system, request, call_id, bit=bit, other_inputs=other_inputs):
            private_target = request["target"]["entity"] == "KSFO"
            if not private_target:
                other_inputs.append(request)
            probability = 0.2 + 0.6 * bit if private_target else 0.3
            raw = json.dumps(
                {
                    "probability": probability,
                    "e_status": "undetermined",
                    "decision": "override",
                    "citations": [],
                }
            )
            details = {
                "seconds": 1 + bit * 8 if private_target else 1,
                "input_tokens": 10,
                "output_tokens": 10 + bit * 20 if private_target else 10,
                "ended_with_eos": True,
            }
            return raw, details

        run_session(data, bank, config, backend=backend)
        captures.append(other_inputs)
    assert captures[0]
    assert captures[0] == captures[1]


def test_invalid_model_answers_keep_the_complete_opportunity_ledger():
    data, bank, config = fixture()
    trace = run_session(
        data,
        bank,
        config,
        backend=lambda *args: (
            "not json",
            {"seconds": 1, "input_tokens": 10, "output_tokens": 2, "ended_with_eos": True},
        ),
    )
    assert len(trace["snapshots"]) == len(data["opportunities"])
    assert all(c["response_error"] for c in trace["calls"])
    assert all(s["mode"] == "follow" for s in trace["snapshots"])


def test_exact_answer_contract_does_not_accept_boolean_probability_or_extra_prose():
    with pytest.raises(ValueError):
        parse_answer(
            '{"probability":true,"e_status":"undetermined","decision":"follow","citations":[]}'
        )
    with pytest.raises(ValueError):
        parse_answer(
            'Answer: {"probability":0.2,"e_status":"undetermined","decision":"follow","citations":[]}'
        )


def test_complete_batch_control_accumulates_budget_without_reading_missing_payloads():
    _, bank, config = fixture()
    data = load_session(ROOT, stations=["KSFO", "KOAK", "KSJC"], hours=6, threshold=1000)
    config.update(
        authorization_mode="session_shared",
        request_budget=12,
        forecast_call_cap=54,
        per_tick_forecast_cap=9,
        isolation_mode="actual_cost_clock",
    )
    paced = run_session(data, bank, config)
    batched = run_session(data, bank, dict(config, selector_kind="batch_complete"))
    assert batched["frames"][0]["source_steps"] == []
    assert len(batched["frames"][1]["source_steps"]) == 3
    assert batched["resource_spent"]["requests"] <= 12
    assert batched["e_counts"].get("refuted", 0) > paced["e_counts"].get("refuted", 0)
    assert len(batched["snapshots"]) == len(paced["snapshots"]) == 54


def test_predictor_receives_its_current_explicit_state_and_action_semantics():
    data, bank, config = fixture()
    requests = []

    def backend(system, request, call_id):
        assert "no_change" in system and "retains" in system and "clears" in system
        requests.append(request)
        return json.dumps(
            {
                "probability": 0.3,
                "e_status": "undetermined",
                "decision": "override",
                "citations": [],
            }
        ), {"input_tokens": 20, "output_tokens": 10, "seconds": 1, "ended_with_eos": True}

    run_session(data, bank, config, backend=backend)
    assert requests and all("current_state" in r for r in requests)
    for request in requests:
        assert request["current_state"]["target_id"] == request["target"]["target_id"]
        assert request["current_state"]["mode"] in {"follow", "override"}


def test_new_unparsed_taf_replaces_old_mapping_and_remains_visible_to_model():
    data, bank, config = fixture()
    target_id = data["opportunities"][0]["target_id"]
    cutoff = data["opportunities"][0]["cutoff"]
    target = next(t for t in data["targets"] if t["target_id"] == target_id)
    data["baseline_candidates"].append(
        {
            "target_id": target_id,
            "source_id": "strict-parser-unavailable",
            "available_at": cutoff - 1000 * 1000000,
            "issued_at": cutoff - 1120 * 1000000,
            "valid_until": target["physical_start"],
            "raw": "UNPARSED NATIVE TAF KEPT",
            "projection_status": "unavailable",
            "projection": {"status": "unparsed", "reason": "scope"},
        }
    )
    config.update(
        forecast_call_cap=12,
        per_tick_forecast_cap=6,
        token_cap=12 * (8192 + 384),
        compute_ms_cap=12 * 120100,
    )
    seen = []

    def backend(system, request, call_id):
        if request["target"]["target_id"] == target_id:
            seen.append(request)
        return json.dumps(
            {"probability": 0.2, "e_status": "undetermined", "decision": "follow", "citations": []}
        ), {"input_tokens": 10, "output_tokens": 10, "seconds": 1, "ended_with_eos": True}

    trace = run_session(data, bank, config, backend=backend)
    assert seen and seen[0]["common_baseline"]["baseline_kind"] == "fallback"
    assert seen[0]["full_native_taf"] == "UNPARSED NATIVE TAF KEPT"
    assert len(trace["snapshots"]) == len(data["opportunities"])


def test_neighbor_persistence_is_a_charged_program_not_model_inference():
    data, bank, config = fixture()
    config.update(authorization_mode="session_shared", program_prediction="neighbor_persistence")
    trace = run_session(data, bank, config)
    assert trace["calls"] and trace["actual_model_calls"] == 0
    assert trace["resource_spent"]["tokens"] == 0
    for call in trace["calls"]:
        if call["reported_e"] == "refuted":
            assert call["proposed_probability"] == 0.0
        elif call["reported_e"] == "supported":
            assert call["proposed_probability"] == 1.0
    assert trace["resource_spent"]["requests"] > 0
