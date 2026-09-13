"""CPU interface checks on actual frozen bundles, with synthetic parser responses.

No response in this test module is a new model prediction or research result.
"""

import json
from collections import Counter
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from disastertrace.monitoring_fixed_v1.aviation import (
    TRUTH_TO_SUPPORT,
    visible_e_status,
)
from disastertrace.monitoring_fixed_v1.aviation import (
    parse_response as parse_joint,
)
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Target,
    canonical,
)
from disastertrace.monitoring_fixed_v1.heads import (
    HeadResponse,
    model_messages,
    parse_response,
)

MATRIX = Path(__file__).resolve().parents[1] / "evidence_bundle/matrix_01"
HEADS = ("e_only", "f_only", "joint")


@pytest.fixture(scope="module")
def bundles():
    manifest = json.loads((MATRIX / "MANIFEST.json").read_text())
    result = []
    for item in manifest:
        bundle = EvidenceBundle.restore(
            json.loads((MATRIX / "policy" / (item["call_id"] + ".json")).read_text())
        )
        assert bundle.bundle_hash == item["bundle_hash"]
        assert bundle.base_hash == item["base_hash"]
        result.append(bundle)
    assert len(result) == 144
    return result


def test_all_heads_receive_identical_visible_inputs_and_fresh_messages(bundles):
    for bundle in bundles:
        before = bundle.to_dict()
        messages = [model_messages(bundle, head) for head in HEADS]
        assert len({m[0]["content"] for m in messages}) == 3
        assert {m[1]["content"] for m in messages} == {canonical(bundle.policy_view())}
        for message in messages:
            assert [m["role"] for m in message] == ["system", "user"]
            message[1]["content"] = "local mutation"
            message[0]["content"] = "local mutation"
            message.append({"role": "assistant", "content": "private memory"})
        for head in HEADS:
            fresh = model_messages(bundle, head)
            assert len(fresh) == 2
            assert fresh[1]["content"] == canonical(bundle.policy_view())
            assert "local mutation" not in fresh[0]["content"]
        assert bundle.to_dict() == before


def test_head_instructions_do_not_request_the_other_answer_or_give_filled_examples(
    bundles,
):
    systems = {head: model_messages(bundles[0], head)[0]["content"] for head in HEADS}
    assert "fact_truth" not in systems["f_only"]
    assert "Return true" not in systems["f_only"]
    assert "probability" not in systems["e_only"]
    assert "exactly probability" in systems["f_only"]
    assert "exactly fact_truth." in systems["e_only"]
    assert "exactly fact_truth and probability" in systems["joint"]
    for system in systems.values():
        assert "{" not in system and "}" not in system
        assert '"fact_truth":' not in system and '"probability":' not in system


def test_real_visible_support_and_baseline_values_round_trip_without_head_imputation(
    bundles,
):
    inverse = {value: key for key, value in TRUTH_TO_SUPPORT.items()}
    support_counts = Counter()
    for bundle in bundles:
        support = visible_e_status(bundle)
        support_counts[support] += 1
        truth = inverse[support]
        probability = bundle.policy_view()["baseline"]["forecast"]["value"]
        e = parse_response(json.dumps({"fact_truth": truth}), bundle, "e_only")
        f = parse_response(json.dumps({"probability": probability}), bundle, "f_only")
        raw = json.dumps({"fact_truth": truth, "probability": probability})
        joint = parse_response(raw, bundle, "joint")
        old_forecast, old_status = parse_joint(raw, bundle)
        assert e.fact_truth == joint.fact_truth == truth
        assert e.e_status == joint.e_status == old_status == support
        assert e.forecast is None
        assert f.fact_truth is None and f.e_status is None
        assert f.forecast == joint.forecast == old_forecast
        Target(**bundle.policy_view()["target"]).check_forecast(f.forecast)
    assert support_counts == {"undetermined": 93, "supported": 9, "refuted": 42}


@pytest.mark.parametrize("truth,status", TRUTH_TO_SUPPORT.items())
@pytest.mark.parametrize("head", ["e_only", "joint"])
def test_all_explicit_truth_values_including_conflict(bundles, head, truth, status):
    row = {"fact_truth": truth}
    if head == "joint":
        row["probability"] = 0.25
    result = parse_response(json.dumps(row), bundles[0], head)
    assert result.e_status == status
    with pytest.raises(FrozenInstanceError):
        result.fact_truth = "unknown"


@pytest.mark.parametrize("head", ["f_only", "joint"])
@pytest.mark.parametrize("probability", [0, 1, 0.0, 1.0, 0.25])
def test_probability_inclusive_bounds(bundles, head, probability):
    row = {"probability": probability}
    if head == "joint":
        row["fact_truth"] = "unknown"
    assert (
        parse_response(json.dumps(row), bundles[0], head).forecast.value == probability
    )


@pytest.mark.parametrize("head", ["f_only", "joint"])
@pytest.mark.parametrize(
    "value",
    [
        "true",
        "false",
        "null",
        '"0.5"',
        "NaN",
        "Infinity",
        "-Infinity",
        "1e999",
        "-0.01",
        "1.01",
        "[]",
        "{}",
        "1" + "0" * 400,
    ],
)
def test_invalid_probabilities_are_rejected(bundles, head, value):
    fields = '"probability":' + value
    if head == "joint":
        fields += ',"fact_truth":"unknown"'
    with pytest.raises(ValueError):
        parse_response("{" + fields + "}", bundles[0], head)


@pytest.mark.parametrize("head", ["e_only", "joint"])
@pytest.mark.parametrize("value", [True, False, None, 1, "supported", "TRUE", [], {}])
def test_invalid_truth_types_and_aliases_are_rejected(bundles, head, value):
    row = {"fact_truth": value}
    if head == "joint":
        row["probability"] = 0.25
    with pytest.raises(ValueError):
        parse_response(json.dumps(row), bundles[0], head)


@pytest.mark.parametrize(
    "head,raw",
    [
        ("e_only", '{"fact_truth":"unknown","probability":0.25}'),
        ("f_only", '{"fact_truth":"unknown","probability":0.25}'),
        ("joint", '{"fact_truth":"unknown"}'),
        ("joint", '{"probability":0.25}'),
        ("e_only", '{"fact_truth":"true","fact_truth":"false"}'),
        ("f_only", '{"probability":0.25,"probability":0.5}'),
        ("joint", '{"fact_truth":"true","probability":0.25,"probability":0.5}'),
    ],
)
def test_cross_head_fields_missing_fields_and_duplicate_keys_are_rejected(
    bundles, head, raw
):
    with pytest.raises(ValueError):
        parse_response(raw, bundles[0], head)


@pytest.mark.parametrize("head", HEADS)
@pytest.mark.parametrize(
    "raw", ["[]", "null", "true", "{}", "not JSON", "{} {}", b"{}"]
)
def test_non_objects_empty_objects_and_malformed_responses_fail(bundles, head, raw):
    with pytest.raises(ValueError):
        parse_response(raw, bundles[0], head)


@pytest.mark.parametrize("head", HEADS)
def test_arbitrary_extra_fields_are_rejected(bundles, head):
    row = {}
    if head != "f_only":
        row["fact_truth"] = "unknown"
    if head != "e_only":
        row["probability"] = 0.25
    row["explanation"] = "extra"
    with pytest.raises(ValueError):
        parse_response(json.dumps(row), bundles[0], head)


@pytest.mark.parametrize("head", [None, True, 1, [], "E-only", "", "scalar"])
def test_unknown_heads_are_rejected_before_dispatch_and_parse(bundles, head):
    with pytest.raises(ValueError):
        model_messages(bundles[0], head)
    with pytest.raises(ValueError):
        parse_response("{}", bundles[0], head)


@pytest.mark.parametrize("head", HEADS)
def test_different_target_contract_is_not_silently_routed_to_aviation(bundles, head):
    row = bundles[0].policy_view()
    row["target"].update(variable="temperature", units="K")
    target_hash = Target(**row["target"]).contract_hash
    row["baseline"]["forecast"]["target_contract_hash"] = target_hash
    row["state"]["forecast"]["target_contract_hash"] = target_hash
    other = EvidenceBundle.freeze(row)
    with pytest.raises(ValueError, match="aviation visibility"):
        model_messages(other, head)
    with pytest.raises(ValueError, match="aviation visibility"):
        parse_response("{}", other, head)


def test_absent_head_cannot_be_added_through_response_constructor(bundles):
    forecast = parse_response('{"probability":0.25}', bundles[0], "f_only").forecast
    with pytest.raises(ValueError):
        HeadResponse("e_only", "unknown", forecast)
    with pytest.raises(ValueError):
        HeadResponse("f_only", "unknown", forecast)
    with pytest.raises(ValueError):
        HeadResponse("joint", "unknown", None)
