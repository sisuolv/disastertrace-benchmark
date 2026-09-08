from copy import deepcopy

import pytest

from disastertrace.automated.common import canonical
from disastertrace.controlled import generator, runtime, scorer


def test_correct_program_and_missing_rows_keep_all_denominators():
    episodes = generator.micro_episodes()
    rows = runtime.rehearse(episodes, "structured_state", "correct")
    report = scorer.score(episodes, rows, "structured_state")
    assert report["metrics"]["schema_success"] == {"numerator": 60, "denominator": 60, "value": 1.0}
    assert report["metrics"]["known_grounded_accuracy"]["value"] == 1
    assert report["metrics"]["unknown_accuracy"]["value"] == 1
    missing = scorer.score(episodes, rows[:-1], "structured_state")
    assert missing["metrics"]["schema_success"]["denominator"] == 60
    assert missing["metrics"]["schema_success"]["numerator"] == 59
    assert (
        missing["metrics"]["known_grounded_accuracy"]["denominator"]
        == report["metrics"]["known_grounded_accuracy"]["denominator"]
    )
    assert missing["status_counts"]["unsubmitted"] == 1


def test_grounding_rejects_missing_and_mixed_wrong_citations():
    episodes = generator.micro_episodes()[:1]
    rows = runtime.rehearse(episodes, "snapshot", "correct")
    answer = __import__("json").loads(rows[-1]["raw_response"])
    answer["state"]["maximum_wind_mph"]["evidence"].append(
        {"record_id": "not-delivered", "line": 2}
    )
    rows[-1]["raw_response"] = canonical(answer)
    rows[-1]["state_after"] = answer
    score = scorer.score(episodes, rows, "snapshot")
    assert score["metrics"]["known_value_accuracy"]["value"] == 1
    assert score["metrics"]["known_grounded_accuracy"]["value"] < 1


def test_invalid_response_is_not_repaired_or_carried():
    episodes = generator.micro_episodes()[:1]
    rows = runtime.rehearse(episodes, "answer_history", "invalid-control")
    assert rows[2]["status"] == "invalid"
    assert rows[2]["raw_response"] == ""
    assert rows[2]["state_after"] == rows[1]["state_after"]
    assert len(rows[3]["request"]["answer_history"]) == 2
    assert (
        scorer.score(episodes, rows, "answer_history")["metrics"]["schema_success"]["numerator"]
        == 4
    )


def test_tampered_exposure_or_cross_trajectory_state_is_rejected():
    episodes = generator.micro_episodes()[:2]
    rows = runtime.rehearse(episodes, "structured_state", "correct")
    changed = deepcopy(rows)
    changed[2]["request"]["instruction"] += " revised"
    with pytest.raises(ValueError):
        scorer.score(episodes, changed, "structured_state")
    changed = deepcopy(rows)
    changed[5]["request"]["previous_state"] = rows[4]["state_after"]
    with pytest.raises(ValueError):
        scorer.score(episodes, changed, "structured_state")


def test_declared_mutants_fail_targeted_metrics_latest_issued_is_allowed():
    episodes = generator.micro_episodes()
    for backend, family, metric in [
        ("clear-omitted", "U1", "preservation"),
        ("latest-arrival", "U2", "known_grounded_accuracy"),
        ("always-unknown", "U3", "known_grounded_accuracy"),
        ("always-known", "U3", "unknown_accuracy"),
        ("always-copy-previous", "U1", "update_success"),
        ("correct-value-wrong-source", "U2", "provenance_refresh"),
    ]:
        report = scorer.score(
            episodes, runtime.rehearse(episodes, "structured_state", backend), "structured_state"
        )
        assert report["by_family"][family]["metrics"][metric]["value"] < 1
    report = scorer.score(
        episodes, runtime.rehearse(episodes, "snapshot", "per-key-latest-issued"), "snapshot"
    )
    assert report["metrics"]["known_grounded_accuracy"]["value"] == 1
