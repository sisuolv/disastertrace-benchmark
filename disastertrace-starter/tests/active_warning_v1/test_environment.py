"""Adversarial protocol checks; fixture values are synthetic and never model results."""

import json
from datetime import timedelta

import pytest

from disastertrace.active_forecast.provenance import decode_json
from disastertrace.active_forecast.schema import SourceLocator, parse_instant
from disastertrace.active_warning_v1 import Artifact, Environment, Episode, Outcome, Tool
from disastertrace.active_warning_v1.policies import (
    audit_trace,
    fixed_forecast,
    run_episode,
    scenario_episode,
)
from disastertrace.active_warning_v1.scoring import score


def time(hour, minute=0):
    return parse_instant(f"2024-01-01T{hour:02d}:{minute:02d}:00Z")


@pytest.fixture
def episode():
    locator = SourceLocator(
        kind="whole_file", path="test-only.json", sha256="0" * 64, role="source_bytes"
    )
    common = {
        "provider": "fixture",
        "entity": "station",
        "variable": "wind",
        "unit": "kt",
        "source": locator,
        "captured_at": "2026-09-12T00:00:00Z",
        "quality": "synthetic unit-test fixture",
    }
    artifacts = (
        Artifact(
            id="initial-f",
            product_id="p0",
            kind="forecast",
            issued_at=time(0),
            valid_at=time(4),
            release_at=time(0),
            values=(50,),
            **common,
        ),
        Artifact(
            id="new-f",
            product_id="p1",
            kind="forecast",
            issued_at=time(1),
            valid_at=time(4),
            release_at=time(1),
            values=(80,),
            **common,
        ),
        Artifact(
            id="o1",
            product_id="o1",
            kind="observation",
            issued_at=None,
            valid_at=time(1),
            release_at=time(1, 30),
            values=(60,),
            **common,
        ),
    )
    return Episode(
        id="target",
        group="fixture-group",
        family="tropical_cyclone",
        entity="station",
        variable="wind",
        unit="kt",
        start_at=time(0),
        target_at=time(4),
        deadline=time(3),
        checkpoints=(time(2), time(3)),
        threshold=64,
        threshold_meaning="unit test",
        initial_artifact_id="initial-f",
        artifacts=artifacts,
        tools=tuple(
            Tool(id=kind, kind=kind, description=kind)
            for kind in ("forecast", "observation", "mirror", "archive")
        ),
    )


def outcome(episode, value=70):
    return Outcome(
        episode_id=episode.id,
        entity=episode.entity,
        variable=episode.variable,
        unit=episode.unit,
        valid_at=episode.target_at,
        value=value,
        status="unresolved" if value is None else "retrospective_analysis",
        source=None if value is None else episode.artifacts[0].source,
        captured_at="2026-09-12T00:00:00Z",
        reason="unit-test fixture",
    )


def test_hidden_evidence_and_private_metadata_never_in_public_view(episode):
    view = json.dumps(Environment(episode, 2).view())
    for secret in ("new-f", "80.0", "fixture-group", "test-only.json", "sha256", "source", "o1"):
        assert secret not in view


def test_request_time_snapshot_survives_revision_during_transfer(episode):
    env = Environment(episode, 2)
    env.wait_until(time(0, 59) + timedelta(seconds=30))
    receipt = env.query("forecast")
    with pytest.raises(ValueError):
        env.read(receipt)
    env.wait_until(time(1, 1))
    assert env.read(receipt)[0]["values"] == [50.0]


def test_future_version_read_requires_new_paid_query(episode):
    env = Environment(episode, 2)
    first = env.query("forecast")
    env.wait_until(time(1, 1))
    env.read(first)
    second = env.query("forecast")
    env.wait_until(time(1, 2))
    assert env.read(second)[0]["values"] == [80.0]
    assert env.spent == 2


def test_pending_state_does_not_reveal_future_result_metadata(episode):
    env = Environment(episode, 1)
    env.query("observation")
    pending = env.view()["pending"][0]
    assert set(pending) == {"id", "tool_id", "requested_at", "status"}
    env.wait_until(time(0, 1))
    assert env.read("q0000") == []
    answer = fixed_forecast(env.view())
    answer["citations"] = ["q0000"]
    with pytest.raises(ValueError):
        env.forecast(answer)


def test_budget_and_concurrency_fail_without_extra_charge(episode):
    env = Environment(episode, 4, max_pending=1)
    env.query("forecast")
    with pytest.raises(ValueError):
        env.query("observation")
    assert env.spent == 1
    limited = Environment(episode, 0)
    with pytest.raises(ValueError):
        limited.query("forecast")
    assert limited.spent == 0


def test_backward_and_post_deadline_clock_rejected(episode):
    env = Environment(episode, 1)
    env.wait_until(time(2))
    with pytest.raises(ValueError):
        env.wait_until(time(1))
    with pytest.raises(ValueError):
        env.wait_until(time(3, 1))


def test_inflight_at_deadline_cannot_be_cited(episode):
    env = Environment(episode, 1)
    env.wait_until(time(3) - timedelta(seconds=30))
    receipt = env.query("forecast")
    env.wait_until(time(3))
    with pytest.raises(ValueError):
        env.read(receipt)
    assert env.spent == 1
    assert env.receipts[0]["status"] == "pending"


@pytest.mark.parametrize("bad", [True, "NaN", "Infinity", "-1"])
def test_invalid_numeric_forecasts_rejected(episode, bad):
    env = Environment(episode, 1)
    answer = fixed_forecast(env.view())
    answer["value"] = bad
    with pytest.raises(ValueError):
        env.forecast(answer)


def test_no_unread_receipt_or_wrong_target_citation(episode):
    env = Environment(episode, 1)
    answer = fixed_forecast(env.view())
    answer["citations"] = ["q0000"]
    with pytest.raises(ValueError):
        env.forecast(answer)
    answer["citations"] = ["initial"]
    answer["target_id"] = "other-target"
    with pytest.raises(ValueError):
        env.forecast(answer)
    assert env.commits == []


def test_same_timestamp_forecasts_append_without_rewriting(episode):
    env = Environment(episode, 1)
    answer = fixed_forecast(env.view())
    env.forecast(answer)
    answer["value"] = 90
    env.forecast(answer)
    assert len(env.commits) == 2
    assert env.commits[0]["value"] == 50


@pytest.mark.parametrize("scenario", ["clean", "duplicate", "stale", "delayed"])
def test_replay_reconstructs_every_receipt_and_commit(episode, scenario):
    transformed = scenario_episode(episode, scenario)
    trace = run_episode(transformed, 4, "all_read", "blend")
    assert audit_trace(transformed, trace)


def test_duplicate_or_stale_rendering_does_not_change_canonical_forecast(episode):
    values = []
    for scenario in ("clean", "duplicate", "stale"):
        env = Environment(scenario_episode(episode, scenario), 1)
        env.wait_until(time(2))
        q = env.query("forecast")
        env.wait_until(time(2, 1))
        env.read(q)
        values.append(fixed_forecast(env.view(canonical=True))["value"])
    assert values == ["80", "80", "80"]


def test_delayed_version_is_not_returned_before_deadline(episode):
    transformed = scenario_episode(episode, "delayed")
    trace = run_episode(transformed, 2, "latest")
    assert {commit["value"] for commit in trace["commits"]} == {50.0}


def test_changed_event_detected(episode):
    trace = run_episode(episode, 2, "latest")
    trace["events"][-1]["at"] = time(2).isoformat()
    with pytest.raises(ValueError):
        audit_trace(episode, trace)


def test_missing_answers_keep_all_checkpoints_and_common_fallback(episode):
    def invalid_backend(*args):
        return "not JSON", {"output_tokens": 2}

    trace = run_episode(episode, 2, "latest", backend=invalid_backend)
    result = score(episode, outcome(episode), trace)
    assert len(result["checkpoints"]) == 2
    assert all(c["fallback_to_initial"] for c in result["checkpoints"])
    assert all(c["absolute_error"] == 20 for c in result["checkpoints"])
    assert result["invalid_events"] == 2


def test_outcome_missing_is_unresolved_not_negative(episode):
    trace = run_episode(episode, 2, "latest")
    result = score(episode, outcome(episode, None), trace)
    assert result["outcome_status"] == "unresolved"
    assert all(
        c["absolute_error"] is None and "binary_outcome" not in c for c in result["checkpoints"]
    )


def test_different_outcomes_cannot_change_model_requests(episode):
    seen = []

    def backend(system, prompt, *args):
        seen.append(prompt)
        view = json.loads(prompt)
        answer = fixed_forecast(view)
        return json.dumps(answer), {}

    trace = run_episode(episode, 2, "latest", backend=backend)
    before = list(seen)
    assert score(episode, outcome(episode, 70), trace) != score(
        episode, outcome(episode, 20), trace
    )
    assert seen == before


def test_duplicate_json_keys_and_nonfinite_tokens_fail_closed():
    for raw in ('{"value":1,"value":2}', '{"value":NaN}'):
        with pytest.raises(ValueError):
            decode_json(raw)


def test_future_outcome_observation_cannot_enter_episode(episode):
    data = episode.model_dump()
    item = episode.artifacts[-1].model_dump()
    item.update(valid_at=episode.target_at, release_at=episode.target_at)
    data["artifacts"] = [*episode.artifacts[:-1], item]
    with pytest.raises(ValueError):
        Episode.model_validate(data)


def test_stop_retains_forecast_clock_and_commit_opportunities(episode):
    env = Environment(episode, 1)
    env.stop()
    with pytest.raises(ValueError):
        env.query("forecast")
    env.wait_until(episode.deadline)
    env.forecast(fixed_forecast(env.view()))
    assert len(env.commits) == 1
