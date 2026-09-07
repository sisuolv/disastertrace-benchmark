"""Offline output-contract checks against the unchanged authoritative parser."""

from __future__ import annotations

import copy
import math

import pytest

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.automated.dynamic import FIELDS, build_episodes, parse_decision, render_request
from disastertrace.automated.methods import METHODS
from disastertrace.automated.output_contract import (
    EXPLICIT_CONTRACT,
    LEGACY_CONTRACT,
    contract_spec,
    render_calibration_request,
)
from disastertrace.automated.provider import ProviderClient, ProviderConfig


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("output-contract tests must not call a provider")

    monkeypatch.setattr("disastertrace.automated.provider.urllib_transport", forbidden)
    monkeypatch.setattr(ProviderClient, "complete", forbidden)


@pytest.fixture
def episode():
    records = []
    for number, hour in enumerate((6, 12, 18), 1):
        text = f"SYNTHETIC TEST REPORT {number}\nPUBLIC_RECORD_{number}_SENTINEL"
        records.append(
            {
                "record_id": f"synthetic:{number}",
                "storm_id": "SYNTHETIC_CONTRACT_TEST",
                "issued_at": f"2040-08-01T{hour:02d}:00:00Z",
                "raw_text": text,
                "fields": {name: 912345.75 + number for name in FIELDS[:-1]},
                "field_evidence": {
                    name: {"line_start": 2, "line_end": 2, "text": text.splitlines()[1]}
                    for name in FIELDS[:-1]
                },
                "provenance": {
                    "source_origin": "synthetic_record",
                    "private_sentinel": "PRIVATE_GOLD_SENTINEL",
                },
            }
        )
    result = build_episodes(records)[0]
    result["private_gold"] = {"sentinel": "PRIVATE_GOLD_SENTINEL"}
    return result


@pytest.fixture
def decision():
    return {
        "state": {name: {"status": "unknown", "value": None, "evidence": []} for name in FIELDS},
        "action": "request_evidence",
    }


def test_legacy_prompt_leaves_action_type_implicit(episode):
    prompt = render_request(episode, "c1", None, method="snapshot")["instruction"]
    assert "exactly state and action" in prompt
    assert "action must be a string" not in prompt
    assert '"type":"string"' not in prompt
    explicit = render_calibration_request(episode, "c1", None, method="snapshot")
    assert (
        '"action":{"enum":["monitor","prepare","request_evidence"],"type":"string"}'
        in explicit["instruction"]
    )


@pytest.mark.parametrize("method", METHODS)
def test_legacy_requests_remain_byte_identical(episode, decision, method):
    legacy = render_request(episode, "c2", decision, method=method, history=[decision])
    calibrated = render_calibration_request(
        episode, "c2", decision, method=method, history=[decision], contract=LEGACY_CONTRACT
    )
    assert canonical(calibrated).encode() == canonical(legacy).encode()


@pytest.mark.parametrize("method", METHODS)
def test_explicit_changes_only_instruction_and_not_any_input(episode, decision, method):
    history = [decision]
    before = copy.deepcopy((episode, decision, history))
    legacy = render_request(episode, "c2", decision, method=method, history=history)
    explicit = render_calibration_request(episode, "c2", decision, method=method, history=history)
    assert set(explicit) == set(legacy)
    assert explicit["protocol"] == "disastertrace_text_v1"
    assert {key for key in legacy if legacy[key] != explicit[key]} == {"instruction"}
    assert explicit["instruction"].startswith(legacy["instruction"] + "\n\n")
    assert (episode, decision, history) == before


def test_contract_instruction_is_identical_across_methods_and_checkpoints(episode, decision):
    instructions = {
        render_calibration_request(
            episode, checkpoint, decision, method=method, history=[decision]
        )["instruction"]
        for method in METHODS
        for checkpoint in ("c0", "c1", "c4")
    }
    assert len(instructions) == 1
    spec = contract_spec()
    assert spec["contract_id"] in next(iter(instructions))
    assert spec["marker"] in next(iter(instructions))


@pytest.mark.parametrize("method", METHODS)
def test_private_fields_and_future_records_are_not_exposed(episode, method):
    request = render_calibration_request(episode, "c1", None, method=method)
    payload = canonical(request)
    assert "PUBLIC_RECORD_1_SENTINEL" in payload
    for private in (
        "PRIVATE_GOLD_SENTINEL",
        "912346.75",
        "PUBLIC_RECORD_2_SENTINEL",
        "PUBLIC_RECORD_3_SENTINEL",
        '"synthetic:2"',
        '"synthetic:3"',
        "field_evidence",
        "checkpoints",
        "arrivals",
    ):
        assert private not in payload
    no_evidence = render_calibration_request(episode, "c0", None, method=method)
    assert no_evidence["evidence"] == []


@pytest.mark.parametrize("method", ("structured_state", "answer_history"))
def test_schema_valid_factual_errors_are_carried_without_repair(episode, decision, method):
    decision["state"]["maximum_wind_mph"] = {"status": "known", "value": -12345, "evidence": []}
    decision["action"] = "prepare"
    parse_decision(canonical(decision))
    rendered = render_calibration_request(
        episode, "c2", decision, method=method, history=[decision]
    )
    assert rendered.get("previous_state", rendered.get("answer_history", [None])[0]) == decision
    carrier = (
        rendered["previous_state"]
        if method == "structured_state"
        else rendered["answer_history"][0]
    )
    carrier["state"]["maximum_wind_mph"]["value"] = 0
    assert decision["state"]["maximum_wind_mph"]["value"] == -12345


def test_schema_and_contract_hashes_are_stable_and_return_values_are_isolated():
    first, second = contract_spec(), contract_spec()
    assert first == second
    assert first["contract"] == EXPLICIT_CONTRACT
    assert first["schema_sha256"] == fingerprint(first["json_schema"])
    assert first["contract_id"] == fingerprint(
        {key: value for key, value in first.items() if key != "contract_id"}
    )
    assert first["contract_id"] != contract_spec(LEGACY_CONTRACT)["contract_id"]
    first["json_schema"]["properties"]["action"]["enum"].append("bad")
    first["lexical_requirements"].append("bad")
    assert contract_spec() == second


def test_full_schema_has_exact_keys_and_consistent_slots():
    schema = contract_spec()["json_schema"]
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"]) == {"state", "action"}
    state = schema["properties"]["state"]
    assert state["additionalProperties"] is False
    assert set(state["required"]) == set(state["properties"]) == set(FIELDS)
    assert all(slot == {"$ref": "#/$defs/slot"} for slot in state["properties"].values())
    variants = schema["$defs"]["slot"]["oneOf"]
    known, unknown = (
        {v["properties"]["status"]["const"]: v for v in variants}[status]
        for status in ("known", "unknown")
    )
    for slot in (known, unknown):
        assert slot["additionalProperties"] is False
        assert set(slot["required"]) == set(slot["properties"]) == {"status", "value", "evidence"}
    assert known["properties"]["value"]["type"] == "number"
    assert known["properties"]["evidence"].get("minItems", 0) == 0
    assert unknown["properties"]["value"]["type"] == "null"
    assert unknown["properties"]["evidence"]["maxItems"] == 0
    citation = schema["$defs"]["citation"]
    assert citation["additionalProperties"] is False
    assert set(citation["required"]) == set(citation["properties"]) == {"record_id", "line"}
    assert citation["properties"]["line"]["type"] == "integer"
    assert citation["properties"]["line"]["minimum"] == 1
    assert citation["properties"]["record_id"] == {"type": "string"}


@pytest.mark.parametrize("action", ["monitor", "prepare", "request_evidence"])
@pytest.mark.parametrize(
    "value,evidence",
    [
        (0, []),
        (-1.25, []),
        (2.5, [{"record_id": "", "line": 1}]),
        (17, [{"record_id": "record", "line": 2}]),
    ],
)
def test_declared_schema_known_slots_match_frozen_parser_acceptance(
    decision, action, value, evidence
):
    schema = contract_spec()["json_schema"]
    decision["action"] = action
    assert action in schema["properties"]["action"]["enum"]
    for name in FIELDS:
        decision["state"][name] = {"status": "known", "value": value, "evidence": evidence}
    assert parse_decision(canonical(decision)) == decision


@pytest.mark.parametrize(
    "mutation",
    [
        "object_action",
        "swapped_action_state",
        "extra_top_key",
        "extra_state_field",
        "extra_slot_key",
        "extra_reference_key",
        "unknown_value",
        "unknown_citation",
        "known_null",
        "known_boolean",
        "line_float",
        "line_boolean",
        "line_zero",
    ],
)
def test_invalid_contract_examples_are_rejected_by_frozen_parser(decision, mutation):
    item = decision["state"]["maximum_wind_mph"]
    ref = {"record_id": "record", "line": 1}
    if mutation == "object_action":
        decision["action"] = {"decision": "monitor"}
    elif mutation == "swapped_action_state":
        decision["action"], decision["state"] = decision["state"], decision["action"]
    elif mutation == "extra_top_key":
        decision["explanation"] = "unsupported key"
    elif mutation == "extra_state_field":
        decision["state"]["extra"] = item
    elif mutation == "extra_slot_key":
        item["confidence"] = 1
    elif mutation == "unknown_value":
        item["value"] = 1
    elif mutation == "unknown_citation":
        item["evidence"] = [ref]
    else:
        item.update(status="known", value=10, evidence=[ref])
        if mutation == "known_null":
            item["value"] = None
        elif mutation == "known_boolean":
            item["value"] = True
        elif mutation == "line_float":
            ref["line"] = 1.0
        elif mutation == "line_boolean":
            ref["line"] = True
        elif mutation == "line_zero":
            ref["line"] = 0
        else:
            ref["extra"] = "unsupported key"
    with pytest.raises((ValueError, TypeError)):
        parse_decision(canonical(decision))


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity", "1e309"])
def test_nonfinite_values_are_rejected_and_lexical_limits_are_declared(decision, raw):
    decision["state"]["maximum_wind_mph"].update(status="known", value=987654321)
    payload = canonical(decision).replace("987654321", raw)
    with pytest.raises(ValueError):
        parse_decision(payload)
    requirements = " ".join(contract_spec()["lexical_requirements"])
    assert "finite" in requirements and "integer" in requirements
    assert not math.isfinite(float(raw))


def test_no_instance_examples_or_port_answer_shortcut_in_contract():
    spec = contract_spec()
    assert "examples" not in canonical(spec["json_schema"])
    assert "always unknown" not in canonical(spec).lower()
    assert "at least one" in spec["grounding_requirement"]
    assert "empty evidence" in spec["grounding_requirement"]
    assert "schema" in spec["grounding_requirement"]


@pytest.mark.parametrize("method", METHODS)
def test_provider_wire_shape_is_valid_and_contract_changes_only_messages(episode, method):
    config = ProviderConfig(
        model="offline-contract-test",
        base_url="http://127.0.0.1:8000",
        key_env=None,
        max_output_tokens=4096,
        token_parameter="max_tokens",
        temperature=None,
        timeout=60,
        max_response_bytes=1048576,
    )
    client = ProviderClient(config)
    legacy = client.prepare(
        render_calibration_request(episode, "c1", None, method=method, contract=LEGACY_CONTRACT)
    )
    explicit = client.prepare(render_calibration_request(episode, "c1", None, method=method))
    assert legacy["request_sha256"] != explicit["request_sha256"]
    from disastertrace.automated.common import strict_json

    before, after = strict_json(legacy["raw_request"]), strict_json(explicit["raw_request"])
    assert {key for key in before if before[key] != after[key]} == {"messages"}
    assert "response_format" not in after
    assert "tools" not in after


@pytest.mark.parametrize("contract", ["explicit_v2", "legacy", None, {}, 1])
def test_unknown_contract_is_rejected_before_rendering(episode, contract):
    with pytest.raises(ValueError, match="contract"):
        contract_spec(contract)
    with pytest.raises(ValueError, match="contract"):
        render_calibration_request(episode, "c1", None, contract=contract)
