"""Independent synthetic trajectories for fixed-denominator scoring regressions."""

from copy import deepcopy

import pytest

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.automated.dynamic import FIELDS, build_episodes, run_episode, score_dynamic
from disastertrace.automated.scoring_v2 import SCORER_VERSION, score_dynamic_v2


@pytest.fixture
def episodes():
    records = []
    examples = [
        ("2040-08-01T06:00:00Z", 85, 23.5, -83.2, 985),
        ("2040-08-01T12:00:00Z", 105, 24.1, -84.3, 972),
        ("2040-08-01T18:00:00Z", 105, 25.2, -85.1, 963),
    ]
    for number, (issued_at, wind, latitude, longitude, pressure) in enumerate(examples, 1):
        lines = [
            "SYNTHETIC UNIT-TEST REPORT; NOT AN OFFICIAL ADVISORY",
            f"LOCATION...{latitude}N {abs(longitude)}W",
            f"MAXIMUM SUSTAINED WINDS...{wind} MPH",
            f"MINIMUM CENTRAL PRESSURE...{pressure} MB",
            "",
            "DISCUSSION AND OUTLOOK",
            "----------------------",
            f"Maximum sustained winds are near {wind} mph with higher gusts.",
        ]
        locators = (3, 2, 2, 4)
        records.append(
            {
                "record_id": f"synthetic:report:{number}",
                "storm_id": "SYNTHETIC_TEST_STORM",
                "issued_at": issued_at,
                "raw_text": "\n".join(lines),
                "fields": dict(zip(FIELDS[:-1], (wind, latitude, longitude, pressure))),
                "field_evidence": {
                    field: {"line_start": line, "line_end": line, "text": lines[line - 1]}
                    for field, line in zip(FIELDS[:-1], locators)
                },
                "provenance": {"source_origin": "synthetic_record", "historical_claim": False},
            }
        )
    return build_episodes(records)


def traces_for(episodes, backend="rule", method="structured_state", max_queries=5):
    return [
        row
        for episode in episodes
        for row in run_episode(episode, backend, max_queries=max_queries, method=method)
    ]


def submit_decisions(episode, decisions, method="structured_state"):
    predictions = {
        (episode["episode_id"], checkpoint["checkpoint_id"]): {
            "raw_response": canonical(decision) if isinstance(decision, dict) else decision
        }
        for checkpoint, decision in zip(episode["checkpoints"], decisions)
    }
    return run_episode(
        episode, "submissions", max_queries=5, predictions=predictions, method=method
    )


def metric(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def test_equivalent_body_citation_changes_only_grounding_and_keeps_v1(episodes):
    episode = episodes[0]
    decisions = [row["state_after"] for row in traces_for([episode])]
    decisions[-1]["state"]["maximum_wind_mph"]["evidence"][0]["line"] = 8
    traces = submit_decisions(episode, decisions)
    inputs = deepcopy((episodes, traces))
    old = score_dynamic([episode], traces)
    result = score_dynamic_v2([episode], traces)
    assert old["metrics"]["grounded_state"] == metric(24, 25)
    assert result["metrics"]["grounded_state"] == metric(25, 25)
    assert result["metrics"]["known_grounded_accuracy"] == metric(16, 16)
    assert result["metrics"]["known_value_accuracy"] == metric(16, 16)
    assert (episodes, traces) == inputs
    assert score_dynamic([episode], traces) == old
    slot = result["per_checkpoint"][-1]["slots"]["maximum_wind_mph"]
    assert slot["reason"] == "supported"
    assert slot["citation_checks"][0]["reason"] == "supported_body_observation"
    assert result["schema_version"] == "dynamic_score_v2"
    assert result["scorer_version"] == SCORER_VERSION
    assert result["evidence_policy_version"]
    assert len(result["evidence_index_fingerprint"]) == 64
    canonical(result)


@pytest.mark.parametrize("method", ["structured_state", "snapshot", "answer_history"])
def test_fixed_gold_opportunities_have_independent_counts(episodes, method):
    result = score_dynamic_v2(episodes, traces_for(episodes, method=method))
    assert result["metrics"]["gold_transition_success"] == metric(22, 22)
    assert result["metrics"]["gold_transition_value_success"] == metric(22, 22)
    assert result["metrics"]["gold_preservation"] == metric(18, 18)
    assert result["metrics"]["gold_preservation_grounded"] == metric(18, 18)
    assert result["metrics"]["provenance_refresh"] == metric(2, 2)
    assert result["metrics"]["self_error_recovery"] == metric(0, 0)
    assert result["metrics"]["unknown_accuracy"] == metric(18, 18)
    assert result["metrics"]["known_answer_coverage"] == metric(32, 32)
    assert result["metrics"]["all_correct_checkpoints"] == metric(10, 10)
    assert result["per_event"][0]["paired_branches"]["both_correct"][
        "grounded_slots_both_correct"
    ] == metric(25, 25)


@pytest.mark.parametrize("backend", ["no-update", "last-arrival"])
def test_incorrect_prior_answers_never_change_fixed_denominators(episodes, backend):
    result = score_dynamic_v2(episodes, traces_for(episodes, backend=backend))
    assert result["metrics"]["gold_transition_success"]["denominator"] == 22
    assert result["metrics"]["gold_preservation"]["denominator"] == 18
    assert result["metrics"]["provenance_refresh"]["denominator"] == 2
    assert result["metrics"]["known_grounded_accuracy"]["denominator"] == 32
    if backend == "no-update":
        assert result["metrics"]["known_answer_coverage"] == metric(0, 32)
        assert result["metrics"]["gold_transition_success"] == metric(0, 22)


@pytest.mark.parametrize("kind", ["absent", "invalid", "missing", "budget_exhausted"])
def test_unsuccessful_attempts_stay_in_all_fixed_denominators(episodes, kind):
    if kind == "absent":
        traces = []
    elif kind == "invalid":
        traces = [row for ep in episodes for row in submit_decisions(ep, ["bad json"] * 5)]
    elif kind == "missing":
        traces = [row for ep in episodes for row in submit_decisions(ep, [])]
    else:
        traces = traces_for(episodes, max_queries=0)
    result = score_dynamic_v2(episodes, traces)
    assert result["metrics"]["grounded_state"] == metric(0, 50)
    assert result["metrics"]["known_grounded_accuracy"] == metric(0, 32)
    assert result["metrics"]["gold_transition_success"] == metric(0, 22)
    assert result["metrics"]["gold_preservation"] == metric(0, 18)
    assert result["metrics"]["provenance_refresh"] == metric(0, 2)
    assert result["metrics"]["self_error_recovery"] == metric(0, 0)
    assert result["event_macro"]["grounded_state"]["value"] == 0
    assert result["per_checkpoint"][0]["slots"]["maximum_wind_mph"]["reason"] == (
        "missing" if kind == "absent" else kind
    )


@pytest.mark.parametrize("citation_kind", ["missing", "extra_bad", "stale"])
def test_known_support_needs_nonempty_and_every_valid_citation(episodes, citation_kind):
    episode = episodes[0]
    decisions = [row["state_after"] for row in traces_for([episode])]
    evidence = decisions[-1]["state"]["maximum_wind_mph"]["evidence"]
    if citation_kind == "missing":
        evidence.clear()
    elif citation_kind == "extra_bad":
        evidence.append({"record_id": "synthetic:report:3", "line": 9999})
    else:
        evidence[0]["record_id"] = "synthetic:report:2"
    result = score_dynamic_v2([episode], submit_decisions(episode, decisions))
    assert result["metrics"]["state_accuracy"] == metric(25, 25)
    assert result["metrics"]["known_answer_coverage"] == metric(16, 16)
    assert result["metrics"]["known_grounded_accuracy"] == metric(15, 16)
    assert result["metrics"]["gold_preservation"] == metric(9, 9)
    assert result["metrics"]["provenance_refresh"] == metric(0, 1)
    assert not result["per_checkpoint"][-1]["all_correct"]


def test_self_error_recovery_is_separate_from_gold_transitions(episodes):
    episode = episodes[0]
    decisions = [row["state_after"] for row in traces_for([episode])]
    decisions[2]["state"]["maximum_wind_mph"]["value"] = 999
    result = score_dynamic_v2([episode], submit_decisions(episode, decisions))
    assert result["metrics"]["gold_transition_success"] == metric(10, 11)
    assert result["metrics"]["gold_preservation"] == metric(9, 9)
    assert result["metrics"]["self_error_recovery"] == metric(1, 1)
    assert result["metrics"]["self_error_recovery_value"] == metric(1, 1)
    assert result["metrics"]["known_answer_coverage"] == metric(16, 16)
    assert result["metrics"]["known_value_accuracy"] == metric(15, 16)
    slot = result["per_checkpoint"][3]["slots"]["maximum_wind_mph"]
    assert slot["opportunities"]["self_error_recovery"] is True
    assert slot["opportunities"]["gold_transition"] is False


def test_failed_recovery_attempt_is_not_removed(episodes):
    episode = episodes[0]
    decisions = [row["state_after"] for row in traces_for([episode])]
    decisions[2]["state"]["maximum_wind_mph"]["value"] = 999
    decisions[3] = "invalid"
    result = score_dynamic_v2([episode], submit_decisions(episode, decisions))
    # The accepted error persists across c3's invalid answer and the value remains
    # unchanged in Gold at c4, creating a second recovery opportunity.
    assert result["metrics"]["self_error_recovery"] == metric(1, 2)
    assert result["metrics"]["gold_preservation"] == metric(4, 9)
    assert result["metrics"]["gold_transition_success"]["denominator"] == 11


@pytest.mark.parametrize("mutation", ["request", "state", "mixed_method", "duplicate"])
def test_v2_reuses_original_trace_and_history_validation(episodes, mutation):
    traces = traces_for(episodes)
    if mutation == "request":
        traces[-1]["request"]["checkpoint_time"] = "2040-08-01T19:00:00Z"
        traces[-1]["request_hash"] = fingerprint(traces[-1]["request"])
    elif mutation == "state":
        traces[-1]["state_after"]["action"] = "monitor"
    elif mutation == "mixed_method":
        traces[-1]["method"] = "snapshot"
    else:
        traces.append(deepcopy(traces[-1]))
    with pytest.raises(ValueError):
        score_dynamic_v2(episodes, traces)


def test_conditional_v1_metrics_are_preserved_and_labeled(episodes):
    traces = traces_for(episodes, backend="no-update")
    result = score_dynamic_v2(episodes, traces)
    old = score_dynamic(episodes, traces)
    assert result["v1_method_conditional_metrics"] == {
        name: old["metrics"][name] for name in ("required_change_success", "preservation")
    }
    assert "required_change_success" not in result["metrics"]
    assert "preservation" not in result["metrics"]


def test_event_macro_does_not_weight_events_by_checkpoint_count(episodes):
    small = deepcopy(episodes[0])
    small["episode_id"] = "synthetic_second:controlled:base"
    small["group_id"] = "SYNTHETIC_SECOND"
    for record in small["records"]:
        record["storm_id"] = small["group_id"]
    small["checkpoints"] = small["checkpoints"][:1]
    result = score_dynamic_v2([*episodes, small], traces_for(episodes))
    assert result["metrics"]["grounded_state"] == metric(50, 55)
    assert result["event_macro"]["grounded_state"] == {
        "value": 0.5,
        "n_events_defined": 2,
        "n_events_total": 2,
    }
    assert result["event_macro"]["known_grounded_accuracy"]["n_events_defined"] == 1
    assert result["paired_delay_minus_base"]["grounded_state"] == {
        "value": 0.0,
        "n_paired_events_defined": 1,
        "n_paired_events_total": 1,
        "n_events_total": 2,
    }


def test_paired_delay_difference_uses_each_branch_own_gold(episodes):
    base = episodes[0]
    result = score_dynamic_v2(episodes, traces_for([base]))
    event = result["per_event"][0]
    assert event["paired_branches"]["base"]["metrics"]["grounded_state"] == metric(25, 25)
    assert event["paired_branches"]["delay"]["metrics"]["grounded_state"] == metric(0, 25)
    assert event["paired_branches"]["delay_minus_base"]["grounded_state"] == -1
    assert result["paired_delay_minus_base"]["grounded_state"]["value"] == -1
    assert result["independent_event_groups"] == 1
