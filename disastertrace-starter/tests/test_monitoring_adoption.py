import copy

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_fixed_v1.outcomes import experiment_spec
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def test_keep_gate_preserves_every_computed_proposal_and_its_cost():
    data, bank, config = typed_fixture(
        admission_semantics="measurement.v3", adoption_policy={"kind": "never"}
    )
    kept = run_session(data, bank, config)
    assert kept["calls"]
    assert all(c["admission_status"] == "adoption_kept" for c in kept["calls"])
    assert all(
        c["proposed_probability"] is not None and c["admitted_action"] is None
        for c in kept["calls"]
    )
    assert all(s["mode"] == "FOLLOW" for s in kept["snapshots"])
    assert kept["resource_spent"]["compute_ms"] >= len(kept["calls"])
    assert all(c["receipt"]["cost"]["compute_ms"] == 1 for c in kept["calls"])


def test_equal_copy_is_not_adopted_by_change_gate_and_restores_exactly():
    data, bank, config = typed_fixture(
        admission_semantics="measurement.v3",
        predictor_kind="program",
        program_prediction="copy_current_state",
        adoption_policy={"kind": "change_epsilon", "epsilon": 0.01},
    )
    expected = run_session(data, bank, config)
    session = SessionCoordinator(data, bank, config)
    session.step()
    restored = SessionCoordinator.restore(session.snapshot(), data, bank).finish()
    assert restored == expected
    assert all(c["admission_status"] == "adoption_kept" for c in expected["calls"])


def test_adoption_is_registered_comparison_factor():
    data, bank, config = typed_fixture(admission_semantics="measurement.v3")
    a, b = [
        experiment_spec(data, bank, dict(config, adoption_policy={"kind": k}))
        for k in ("always", "never")
    ]
    assert a["invariants"] == b["invariants"]
    assert a["interventions"]["adoption_policy"] != b["interventions"]["adoption_policy"]


def test_loss_limit_bounds_both_binary_outcomes_but_does_not_claim_calibration():
    from disastertrace.monitoring_fixed_v1.adoption import decide

    for p in (0, 0.01, 0.3, 0.7, 1):
        for q in (0, 0.01, 0.3, 0.7, 1):
            result = decide(
                {"kind": "brier_harm_limit", "max_pointwise_harm": 0.02},
                current=p,
                candidate=q,
                previously_adopted=False,
            )
            harm = max((q - y) ** 2 - (p - y) ** 2 for y in (0, 1))
            assert result["adopt"] == (harm <= 0.02)
            assert result["max_pointwise_harm"] == harm
            assert result["calibration_guarantee"] is False


def test_first_hold_uses_admission_history_not_current_override_presence():
    from disastertrace.monitoring_fixed_v1.adoption import decide

    policy = {"kind": "first_target_only"}
    assert decide(policy, current=0.2, candidate=0.3, previously_adopted=False)["adopt"]
    assert not decide(policy, current=0.8, candidate=0.3, previously_adopted=True)["adopt"]


def test_adoption_requires_new_semantics_and_rejects_bad_thresholds():
    data, bank, config = typed_fixture(adoption_policy={"kind": "never"})
    with pytest.raises(ValueError, match="v3"):
        run_session(data, bank, config)
    config.update(
        admission_semantics="measurement.v3",
        adoption_policy={"kind": "change_epsilon", "epsilon": -1},
    )
    with pytest.raises(ValueError):
        run_session(data, bank, config)


def test_stale_base_failure_precedes_optional_keep_gate():
    from disastertrace.monitoring_fixed_v1.admission import (
        AdmissionEngine,
        AdmissionEvent,
        TypedOpportunity,
    )
    from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, Target

    data, bank, config = typed_fixture()
    call = run_session(data, bank, config)["calls"][0]
    view = call["bundle"]["payload"]
    target = Target(**view["target"])
    engine = AdmissionEngine(
        [TypedOpportunity(view["opportunity_id"], target, view["cutoff"])],
        fallbacks={target.target_id: view["baseline"]["forecast"]},
        semantics_version="measurement.v3",
        experiment={
            "invariants": {"fixture": True},
            "interventions": {"adoption_policy": {"kind": "never"}},
        },
    )
    started = call["started_at"]
    changed = copy.deepcopy(view)
    changed["baseline"].update(
        issued_at=started + 1, available_at=started + 1, source_revision="fixture-new-issuance"
    )
    changed["baseline"]["forecast"]["value"] = 0.9
    changed["state"]["forecast"]["value"] = 0.9
    events = [
        AdmissionEvent(
            "base", view["baseline"]["available_at"], "baseline", {"bundle": call["bundle"]}
        ),
        AdmissionEvent(
            "begin",
            started,
            "begin",
            {
                "call_id": call["call_id"],
                "bundle": call["bundle"],
                "head": call["head"],
                "executor": call["receipt"]["executor"],
            },
        ),
        AdmissionEvent(
            "new-base",
            started + 1,
            "baseline",
            {"bundle": EvidenceBundle.freeze(changed).to_dict()},
        ),
        AdmissionEvent("complete", call["persisted_at"], "completion", call["receipt"]),
    ]
    engine.run(events, until=call["persisted_at"])
    assert engine.attempts[-1]["status"] == "stale_base"
    assert "adoption_decision" not in engine.attempts[-1]
