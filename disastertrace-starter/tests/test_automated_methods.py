"""Carrier comparisons use actual accepted answers and identical visible evidence."""

from copy import deepcopy

import pytest

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.automated.dynamic import (
    FIELDS,
    build_episodes,
    diagnostic_response,
    parse_decision,
    render_request,
    run_episode,
    score_dynamic,
)
from disastertrace.automated.methods import METHODS, method_contract
from disastertrace.automated.provider import ProviderClient, ProviderConfig, validate_public_request


@pytest.fixture
def episode():
    records = []
    for index, (wind, pressure) in enumerate(((85, 985), (105, 972), (115, 963)), 1):
        lines = [
            "SYNTHETIC METHOD TEST; NO HISTORICAL CLAIM",
            "LOCATION...23.5N 83.2W",
            f"MAXIMUM SUSTAINED WINDS...{wind} MPH",
            f"MINIMUM CENTRAL PRESSURE...{pressure} MB",
        ]
        records.append(
            {
                "record_id": f"synthetic:methods:{index}",
                "storm_id": "SYNTHETIC_METHODS",
                "issued_at": f"2040-08-01T{index * 6:02d}:00:00Z",
                "raw_text": "\n".join(lines),
                "fields": {
                    "maximum_wind_mph": wind,
                    "latitude_deg": 23.5,
                    "longitude_deg": -83.2,
                    "minimum_pressure_mb": pressure,
                },
                "field_evidence": {
                    field: {"line_start": line, "line_end": line, "text": lines[line - 1]}
                    for field, line in zip(FIELDS[:-1], (3, 2, 2, 4))
                },
                "provenance": {"source_origin": "synthetic_record"},
            }
        )
    return build_episodes(records)[0]


def unknown_decision():
    return {
        "state": {field: {"status": "unknown", "value": None, "evidence": []} for field in FIELDS},
        "action": "request_evidence",
    }


def wrong_decision():
    value = unknown_decision()
    value["state"]["maximum_wind_mph"] = {
        "status": "known",
        "value": 999,
        "evidence": [{"record_id": "synthetic:methods:1", "line": 3}],
    }
    value["action"] = "prepare"
    return value


def submissions(episode):
    return {
        (episode["episode_id"], key): {"raw_response": raw}
        for key, raw in (
            ("c0", canonical(unknown_decision())),
            ("c1", canonical(wrong_decision())),
            ("c2", "not a JSON answer"),
            ("c4", canonical(unknown_decision())),
        )
    }


def test_default_preserves_original_public_shape(episode):
    old_keys = {
        "protocol",
        "instruction",
        "checkpoint_time",
        "required_fields",
        "policy",
        "evidence",
        "previous_state",
    }
    legacy = render_request(episode, "c1", unknown_decision())
    explicit = render_request(episode, "c1", unknown_decision(), method="structured_state")
    assert set(legacy) == old_keys
    assert legacy == explicit


@pytest.mark.parametrize("checkpoint", ["c0", "c1", "c2", "c3", "c4"])
def test_methods_receive_identical_evidence_and_task(episode, checkpoint):
    original = deepcopy(episode)
    requests = [
        render_request(
            episode,
            checkpoint,
            wrong_decision(),
            method=method,
            history=[unknown_decision(), wrong_decision()],
        )
        for method in METHODS
    ]
    for request in requests:
        validate_public_request(request)
        for key in (
            "protocol",
            "instruction",
            "checkpoint_time",
            "required_fields",
            "policy",
            "evidence",
        ):
            assert request[key] == requests[0][key]
        assert "field_evidence" not in canonical(request)
        assert "gold_origin" not in canonical(request)
        assert "checkpoints" not in canonical(request)
    assert episode == original


def test_history_contains_actual_accepted_wrong_answer_and_excludes_invalid_missing_future(episode):
    traces = run_episode(
        episode,
        "submissions",
        max_queries=5,
        predictions=submissions(episode),
        method="answer_history",
    )
    assert [row["status"] for row in traces] == ["ok", "ok", "invalid", "missing", "ok"]
    assert traces[0]["request"]["answer_history"] == []
    assert traces[1]["request"]["answer_history"] == [unknown_decision()]
    for index in (2, 3, 4):
        request = traces[index]["request"]
        assert request["answer_history"] == [unknown_decision(), wrong_decision()]
        assert "previous_state" not in request
        assert "not a JSON answer" not in canonical(request)
    assert score_dynamic([episode], traces)["method"] == "answer_history"


def test_snapshot_hides_accepted_previous_answers_without_erasing_recorded_state(episode):
    traces = run_episode(
        episode, "submissions", max_queries=5, predictions=submissions(episode), method="snapshot"
    )
    for row in traces:
        assert "previous_state" not in row["request"]
        assert "answer_history" not in row["request"]
        assert row["request"]["method"] == "snapshot"
    assert traces[2]["state_after"] == traces[3]["state_after"] == wrong_decision()
    assert score_dynamic([episode], traces)["method"] == "snapshot"


def test_history_requests_are_deep_copies(episode):
    history = [wrong_decision()]
    request = render_request(
        episode, "c2", wrong_decision(), method="answer_history", history=history
    )
    request["answer_history"][0]["state"]["maximum_wind_mph"]["value"] = 42
    assert history == [wrong_decision()]


@pytest.mark.parametrize("method", METHODS)
def test_no_update_uses_only_declared_carrier(episode, method):
    request = render_request(
        episode,
        "c2",
        wrong_decision(),
        method=method,
        history=[unknown_decision(), wrong_decision()],
    )
    expected = unknown_decision() if method == "snapshot" else wrong_decision()
    assert parse_decision(diagnostic_response(request, "no-update")) == expected


@pytest.mark.parametrize("method", METHODS)
def test_rule_accuracy_is_unchanged_and_method_is_reported(episode, method):
    traces = run_episode(episode, "rule", max_queries=5, method=method)
    score = score_dynamic([episode], traces)
    assert all(row["method"] == method for row in traces)
    assert all(row["method"] == method for row in score["per_checkpoint"])
    assert score["method"] == method
    assert score["method_contract"] == method_contract(method)
    assert score["metrics"]["grounded_state"] == {"numerator": 25, "denominator": 25, "value": 1.0}


@pytest.mark.parametrize("mutation", ["replace_wrong_history", "remove_entry", "future_entry"])
def test_scorer_reconstructs_history_even_when_tampered_request_hash_is_recomputed(
    episode, mutation
):
    traces = run_episode(
        episode,
        "submissions",
        max_queries=5,
        predictions=submissions(episode),
        method="answer_history",
    )
    history = traces[2]["request"]["answer_history"]
    if mutation == "replace_wrong_history":
        history[-1] = unknown_decision()
    elif mutation == "remove_entry":
        history.pop()
    else:
        history.append(unknown_decision())
    traces[2]["request_hash"] = fingerprint(traces[2]["request"])
    with pytest.raises(ValueError, match="history"):
        score_dynamic([episode], traces)


@pytest.mark.parametrize("mutation", ["single_row", "all_rows", "remove", "unknown"])
def test_scorer_rejects_method_metadata_tampering(episode, mutation):
    traces = run_episode(episode, "rule", max_queries=5, method="snapshot")
    if mutation == "single_row":
        traces[2]["method"] = "answer_history"
    elif mutation == "all_rows":
        for row in traces:
            row["method"] = "structured_state"
    elif mutation == "remove":
        for row in traces:
            del row["method"]
    else:
        traces[0]["method"] = "private_gold"
    with pytest.raises(ValueError):
        score_dynamic([episode], traces)


def test_legacy_traces_without_method_remain_scoreable(episode):
    traces = run_episode(episode, "rule", max_queries=5)
    for row in traces:
        del row["method"]
    assert score_dynamic([episode], traces)["method"] == "structured_state"


@pytest.mark.parametrize("method", METHODS)
def test_provider_uses_fresh_messages_for_each_declared_method(episode, method):
    config = ProviderConfig(
        model="offline-test",
        base_url="http://localhost:8000/v1",
        key_env=None,
        max_output_tokens=128,
        token_parameter="max_tokens",
        temperature=0,
        timeout=5,
        max_response_bytes=65536,
    )
    client = ProviderClient(config)
    request = render_request(
        episode,
        "c2",
        wrong_decision(),
        method=method,
        history=[unknown_decision(), wrong_decision()],
    )
    prepared = client.prepare(request)
    assert [message["role"] for message in prepared["payload"]["messages"]] == ["system", "user"]
    assert prepared["payload"]["messages"][1]["content"] == canonical(request)
    assert client.prepare(request) == prepared


@pytest.mark.parametrize(
    "method,extra",
    [
        ("snapshot", "previous_state"),
        ("snapshot", "answer_history"),
        ("answer_history", "previous_state"),
        ("structured_state", "answer_history"),
    ],
)
def test_provider_rejects_undeclared_carrier(episode, method, extra):
    request = render_request(episode, "c1", None, method=method)
    request[extra] = [] if extra == "answer_history" else None
    with pytest.raises(ValueError):
        validate_public_request(request)


@pytest.mark.parametrize("history", [{}, "raw chat", ["raw answer"], [{"private_gold": 105}]])
def test_answer_history_accepts_only_valid_decision_objects(episode, history):
    with pytest.raises(ValueError):
        render_request(episode, "c1", None, method="answer_history", history=history)


@pytest.mark.parametrize("method", ["undeclared", "", None, [], True])
def test_unknown_method_rejected_before_any_diagnostic_attempt(episode, method):
    with pytest.raises(ValueError):
        run_episode(episode, "rule", max_queries=0, method=method)
