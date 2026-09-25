from copy import deepcopy

import pytest

from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.synthetic_natural_v21 import run_case, run_experiment, target_card


def test_v21_target_hash_and_snapshot_contract_are_strict():
    target = target_card()
    env = NaturalKernel(
        [NaturalSource("q0", 0, {"visibility_m": 4000})],
        start=0,
        deadline=20,
        target=target,
    )
    snapshot = env.snapshot()
    assert snapshot["schema"] == "disastertrace.v21.natural_kernel_snapshot.v2"
    assert snapshot["target"] == target
    assert NaturalKernel.from_snapshot(snapshot).snapshot() == snapshot
    broken = deepcopy(snapshot)
    broken["target"]["entity"] = "OTHER"
    with pytest.raises(ValueError, match="contract_hash"):
        NaturalKernel.from_snapshot(broken)


def test_v21_public_state_contains_only_read_content_and_is_detached():
    env = NaturalKernel(
        [
            NaturalSource("visible", 0, {"nested": {"value": 1}}),
            NaturalSource("future-private", 50, {"secret": 99}),
            NaturalSource("future-public", 50, {"public": 1}, public_schedule=True),
        ],
        start=0,
        deadline=100,
        target=target_card(),
    )
    state = env.public_state()
    assert [row["query_id"] for row in state["catalogue"]] == ["future-public", "visible"]
    assert state["catalogue"][0]["available_at"] == 50
    assert "future-private" not in {row["query_id"] for row in state["catalogue"]}
    env.step(NaturalAction("RETRIEVE", 0, query_id="visible"))
    state = env.public_state()
    state["read"]["visible"]["nested"]["value"] = 999
    assert env.read["visible"]["nested"]["value"] == 1
    with pytest.raises(ValueError, match="not currently visible"):
        env.step(NaturalAction("RETRIEVE", 0, query_id="future-private"))


def test_v21_active_policy_changes_followup_query_from_actual_content():
    low = run_case("low", 4000, outcome=1)
    high = run_case("high", 9000, outcome=0)
    assert low["retrieval_sequence"][0] == high["retrieval_sequence"][0] == "q0"
    assert low["retrieval_sequence"][1] == "q1"
    assert high["retrieval_sequence"][1] == "q2"
    assert low["actor_extraction"] != high["actor_extraction"]
    assert low["outcome_accessed_by_actor"] is False


def test_v21_id_renaming_preserves_policy_semantics():
    original = run_case("original", 4000, outcome=1)
    renamed = run_case("renamed", 4000, id_prefix="z", outcome=1)
    assert original["retrieval_sequence"] == ["q0", "q1"]
    assert renamed["retrieval_sequence"] == ["z0", "z1"]
    assert original["probability"] == renamed["probability"]


def test_v21_experiment_artifact_has_protocol_only_claims(tmp_path):
    artifact = run_experiment(tmp_path / "active.json")
    assert artifact["active_gate"]["status"] == "PASS"
    assert artifact["cases"][0]["model_calls"] == 0
    assert artifact["claims"]["research"].startswith("This is protocol evidence")
