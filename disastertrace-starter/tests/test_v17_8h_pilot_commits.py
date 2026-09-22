import copy
import json

import pytest

from disastertrace.revision_v1.pilot_v17.agent_view import initial_state, messages_for, public_view
from disastertrace.revision_v1.pilot_v17.commits import apply_commit, consume_response, strict_loads, validate
from disastertrace.revision_v1.pilot_v17.provider import digest


@pytest.fixture
def view():
    return {"episode_id": "e1", "target_id": "t1", "station": "KSFO",
            "target_start": "2023-01-10T12:00:00Z", "target_end": "2023-01-10T13:00:00Z",
            "threshold_metres": 5000, "as_of": "2023-01-10T11:20:00Z",
            "history_start": "2023-01-09T00:00:00Z",
            "evidence": [{"source_id": "s1", "station": "KSFO",
                          "native_issue_time": "2023-01-10T11:10:00Z",
                          "available_at": "2023-01-10T11:12:00Z",
                          "availability_basis": "declared_issue_plus_120_seconds", "raw_product": "TAF SYNTHETIC"}]}


@pytest.fixture
def commit(view):
    return {"schema_version": "disastertrace.belief_commit.v14-draft", "episode_id": "e1",
            "target_id": "t1", "parent_commit_id": None, "as_of": view["as_of"],
            "operation": "UPDATE", "forecast_op": "SET_PROBABILITY", "evidence_ids": ["s1"],
            "fact_updates": [{"slot": "target_source_state", "operation": "SET", "support_status": "supported",
                              "value": {"active_source_ids": ["s1"], "valid_start": "2023-01-10T12:00:00Z",
                                        "valid_end": "2023-01-11T12:00:00Z", "relation_status": "RESOLVED"},
                              "source_ids": ["s1"]}],
            "forecast_updates": [{"target_id": "t1", "event_probability": 0.2}],
            "next_action": {"kind": "WAIT", "until_or_args": None}}


def test_valid_commit_and_immutable_application(view, commit):
    before = initial_state()
    result = validate(commit, view, before)
    assert result["valid"]
    after = apply_commit(before, commit, result)
    assert after["probability"] == 0.2 and after["fact_state"]["active_source_ids"] == ["s1"]
    assert before == initial_state()
    commit["fact_updates"][0]["value"]["active_source_ids"].append("changed")
    assert after["fact_state"]["active_source_ids"] == ["s1"]


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -0.1, 1.1, "0.5", None])
def test_invalid_probabilities(view, commit, value):
    commit["forecast_updates"][0]["event_probability"] = value
    result = validate(commit, view, initial_state())
    assert not result["valid"]
    assert apply_commit(initial_state(), commit, result) == initial_state()


@pytest.mark.parametrize("field,value", [
    ("target_id", "other"), ("episode_id", "other"), ("as_of", "2023-01-10T11:21:00Z"),
    ("parent_commit_id", "bad"), ("forecast_op", "OTHER"), ("operation", "FOLLOW_BASELINE"),
])
def test_identity_and_operation_validation(view, commit, field, value):
    commit[field] = value
    assert not validate(commit, view, initial_state())["valid"]


def test_unknown_and_duplicate_source_ids(view, commit):
    commit["evidence_ids"] = ["s1", "not_visible"]
    assert not validate(commit, view, initial_state())["valid"]
    commit["evidence_ids"] = ["s1", "s1"]
    assert not validate(commit, view, initial_state())["valid"]


def test_duplicate_fact_slot_rejected(view, commit):
    commit["fact_updates"].append(copy.deepcopy(commit["fact_updates"][0]))
    assert not validate(commit, view, initial_state())["valid"]


def test_fact_update_can_keep_probability(view, commit):
    commit["forecast_op"] = "KEEP_PROBABILITY"
    commit["forecast_updates"] = []
    result = validate(commit, view, initial_state())
    assert result["valid"]
    after = apply_commit(initial_state(), commit, result)
    assert after["probability"] == 0.5
    assert after["fact_state"]["active_source_ids"] == ["s1"]
    assert after["probability_origin"] == "TECHNICAL_FALLBACK"


def test_hold_carries_valid_state(view, commit):
    before = apply_commit(initial_state(), commit, validate(commit, view, initial_state()))
    hold = {**commit, "operation": "HOLD", "forecast_op": "KEEP_PROBABILITY",
            "parent_commit_id": before["parent_commit_id"], "fact_updates": [], "forecast_updates": []}
    result = validate(hold, view, before)
    assert result["valid"]
    after = apply_commit(before, hold, result)
    assert after["fact_state"] == before["fact_state"] and after["probability"] == before["probability"]


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"p":NaN}', chr(96)*3+'json\n{}\n'+chr(96)*3])
def test_strict_json_keeps_bad_format_bad(text):
    with pytest.raises(ValueError):
        strict_loads(text)


def test_forecast_operation_affects_commit_identity(commit):
    other = copy.deepcopy(commit)
    other["forecast_op"] = "KEEP_PROBABILITY"
    assert digest(commit) != digest(other)


@pytest.mark.parametrize("finish", ["length", "content_filter", None])
def test_truncation_is_not_silently_repaired(view, commit, finish):
    cap = {"http_status": 200, "provider_response": {"choices": [
        {"finish_reason": finish, "message": {"content": json.dumps(commit)}}]}}
    result = consume_response(cap, view, initial_state())
    assert not result["validation"]["valid"] and result["after"] == initial_state()


def test_r_is_exact_input_replication_and_sham_matches_characters(view):
    before = initial_state()
    original, o = messages_for(view, "FRESH", before, "O")
    repeat, r = messages_for(view, "FRESH", before, "R")
    duplicate, d = messages_for(view, "FRESH", before, "D")
    sham, s = messages_for(view, "FRESH", before, "S")
    assert original == repeat and o["messages_sha256"] == r["messages_sha256"]
    assert d["padding_characters"] == s["padding_characters"]
    assert json.loads(duplicate[1]["content"])["task_and_evidence"] == view
    assert json.loads(sham[1]["content"])["task_and_evidence"] == view
    assert duplicate != sham


def test_external_information_equal_across_arms(view):
    before = initial_state()
    before["fact_state"] = {"wrong": "self-written"}
    fresh, f = messages_for(view, "FRESH", before)
    stateful, s = messages_for(view, "STATEFUL", before)
    assert f["external_view_sha256"] == s["external_view_sha256"]
    a, b = json.loads(fresh[1]["content"]), json.loads(stateful[1]["content"])
    assert a["task_and_evidence"] == b["task_and_evidence"]
    assert "previous_self_written_fact_state" not in a
    assert b["previous_self_written_fact_state"] == before["fact_state"]


def test_renderer_never_reads_future_source_or_private_metadata():
    class Reader:
        def text(self, source):
            assert source["source_id"] == "visible"
            return "synthetic visible raw product"
    common = {"station": "KSFO", "issued_at_us": 1_000_000}
    episode = {"episode_id": "e", "target_id": "t", "station": "KSFO",
               "target_start_us": 10_000_000, "target_end_us": 20_000_000,
               "prefix_start_us": 0, "threshold_m": 5000, "checkpoints_us": [5_000_000],
               "category": "PRIVATE_STRATUM", "reference": "PRIVATE_GOLD",
               "sources": [{**common, "source_id": "visible", "available_at_us": 3_000_000},
                           {**common, "source_id": "future", "available_at_us": 6_000_000}]}
    output = public_view(episode, 0, Reader())
    assert len(output["evidence"]) == 1
    assert "PRIVATE" not in json.dumps(output)
