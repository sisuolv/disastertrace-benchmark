"""Public-only MFT/INV/DIR examples, with values and locators checked independently."""

from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from disastertrace.automated.common import canonical
from disastertrace.constrained_eval import contract
from disastertrace.controlled.compiler import reference_at
from disastertrace.controlled.generator import micro_episodes
from disastertrace.controlled.public_oracle import answer
from disastertrace.controlled.renderer import render_request
from disastertrace.controlled.schema import FIELDS
from disastertrace.post_p5.citations import classify_field
from disastertrace.post_p5.exposure import compare_evidence
from disastertrace.post_p5.policies import solve


def view():
    return render_request(micro_episodes()[0], "c1", method="snapshot")


def extra_record(req, **changes):
    assertion = deepcopy(micro_episodes()[0]["records"][0]["assertions"][0])
    assertion.update(changes)
    header = {
        "record_id": "extra",
        "issued_at": req["checkpoint_time"],
        "operation": "SET",
        "source_origin": "controlled_generated",
    }
    return {
        "delivery_id": "delivery-extra",
        "record_id": "extra",
        "issued_at": header["issued_at"],
        "text": "1: CONTROLLED_RECORD " + canonical(header) + "\n2: ASSERT " + canonical(assertion),
    }


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"entity_id": "other-storm"}, "wrong_entity"),
        ({"valid_end": "2040-01-01T02:00:00+00:00"}, "wrong_valid_window_or_measurement_kind"),
    ],
)
def test_mft_equal_numeric_value_does_not_rescue_wrong_scope(changes, reason):
    req = view()
    gold = answer(req)["state"][FIELDS[0]]
    req["evidence"].append(extra_record(req, revision_id="extra-revision", **changes))
    predicted = {**gold, "evidence": [{"record_id": "extra", "line": 2}]}
    assert classify_field(req, FIELDS[0], predicted, gold)["primary_error"] == reason
    assert answer(req)["state"][FIELDS[0]] == gold


def transform(value, convert):
    if isinstance(value, dict):
        return {k: transform(v, convert) for k, v in value.items()}
    if isinstance(value, list):
        return [transform(v, convert) for v in value]
    return convert(value)


@pytest.mark.parametrize("kind", ["ids", "time", "assertion_order"])
def test_inv_consistent_transform_preserves_values_and_mapped_support(kind):
    original = micro_episodes()[0]
    ep = deepcopy(original)
    if kind == "ids":

        def convert(value):
            if isinstance(value, str) and value.startswith(
                ("entity-", "record-", "revision-", "delivery-")
            ):
                return "renamed-" + value
            return value

        ep = transform(ep, convert)
    elif kind == "time":

        def convert(value):
            if isinstance(value, str) and value.startswith("2040-"):
                return (datetime.fromisoformat(value) + timedelta(days=366, hours=2)).isoformat()
            return value

        ep = transform(ep, convert)
    else:
        for record in ep["records"]:
            record["assertions"].reverse()
    for cp in ep["checkpoints"]:
        old = reference_at(original, cp["checkpoint_id"])
        expected = reference_at(ep, cp["checkpoint_id"])
        req = render_request(ep, cp["checkpoint_id"], method="snapshot")
        assert solve(req) == answer(req) == expected
        for field in FIELDS:
            assert expected["state"][field]["value"] == old["state"][field]["value"]
    if kind == "assertion_order":
        old = reference_at(original, "c1")["state"][FIELDS[0]]
        req = render_request(ep, "c1", method="snapshot")
        expected = reference_at(ep, "c1")["state"][FIELDS[0]]
        assert not classify_field(req, FIELDS[0], old, expected)["legacy_grounded_correct"]


def test_dir_delayed_support_cannot_make_known_earlier():
    ep = micro_episodes()[0]
    # Remove every first-wave support; later evaluation restores the exact same public bytes.
    early = render_request(ep, "c1", method="snapshot")
    delayed = {**early, "evidence": []}
    assert all(v["status"] == "unknown" for v in solve(delayed)["state"].values())
    assert all(v["status"] == "known" for v in solve(early)["state"].values())


def test_frequency_defines_replay_and_latest_delivery_tie():
    req = render_request(micro_episodes()[0], "c2", method="snapshot")
    current = answer(req)["state"][FIELDS[0]]
    assert solve(req, "most_frequent_value")["state"][FIELDS[0]] == current
    req["evidence"].append({**deepcopy(req["evidence"][0]), "delivery_id": "duplicate-in-count"})
    assert solve(req, "most_frequent_value")["state"][FIELDS[0]]["value"] == 90
    # Unique votes tie; the declared final-delivery tiebreaker selects the replay.
    assert solve(req, "most_frequent_unique_assertion")["state"][FIELDS[0]]["value"] == 90
    assert answer(req)["state"][FIELDS[0]] == current
    relation = compare_evidence({**req, "evidence": req["evidence"][:-1]}, req)
    assert relation["semantic_equal"] and relation["current_target_value_equal"]
    assert relation["effective_strength"]["delivered_assertions"] == 4


def test_public_policy_does_not_import_or_call_private_gold(monkeypatch):
    from disastertrace.controlled import compiler

    req = view()
    expected = answer(req)

    def forbidden(*args, **kwargs):
        raise AssertionError("private compiler read by public solver")

    monkeypatch.setattr(compiler, "reference_at", forbidden)
    assert solve(req) == expected
    req["gold_canary"] = "PRIVATE-EXPECTED-ANSWER"
    with pytest.raises(ValueError):
        solve(req)


def test_structure_grammar_keeps_semantic_errors_reachable():
    req = view()
    correct = answer(req)
    wrong = deepcopy(correct)
    wrong["state"][FIELDS[0]]["value"] = 299
    wrong["state"][FIELDS[0]]["evidence"] = [{"record_id": "invented-record", "line": 99}]
    wrong["action"] = "prepare"
    raw = contract.serialize_fixture(wrong)
    assert contract.inspect(raw)["task_contract_valid"]
    assert not classify_field(
        req, FIELDS[0], wrong["state"][FIELDS[0]], correct["state"][FIELDS[0]]
    )["legacy_grounded_correct"]
