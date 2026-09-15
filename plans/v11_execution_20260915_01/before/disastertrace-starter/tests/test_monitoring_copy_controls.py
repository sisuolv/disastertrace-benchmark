"""Visible-value programs are new overrides, never implicit KEEP actions."""

import copy

import pytest
from test_monitoring_admission import bundle
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.outcomes import experiment_spec
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


@pytest.mark.parametrize(
    "kind,expected", [("copy_current_state", -8), ("copy_latest_baseline", -3.5)]
)
def test_copy_reads_only_selected_visible_forecast_and_keeps_bundle_immutable(kind, expected):
    from disastertrace.monitoring_fixed_v1.copy_controls import VisibleValuePredictor

    row = bundle().policy_view()
    row["state"]["mode"] = "OVERRIDE"
    row["state"]["forecast"]["value"] = -8
    frozen = EvidenceBundle.freeze(row)
    before = copy.deepcopy(frozen.to_dict())
    assert VisibleValuePredictor(kind).predict(frozen).value == expected
    assert frozen.to_dict() == before


@pytest.mark.parametrize("kind", ["copy_current_state", "copy_latest_baseline"])
@pytest.mark.parametrize("protocol", ["base_bound_override", "persistent_override"])
def test_copy_has_distinct_identity_zero_model_fees_and_exact_restore(kind, protocol):
    data, bank, config = typed_fixture(
        program_prediction=kind, predictor_kind="program", protocol=protocol
    )
    session = SessionCoordinator(data, bank, config)
    session.step()
    continued = SessionCoordinator.restore(session.snapshot(), data, bank).finish()
    direct = run_session(data, bank, config)
    assert continued == direct
    assert direct["actual_model_calls"] == 0
    assert direct["actual_program_forecast_calls"] == len(direct["calls"]) > 0
    assert direct["resource_spent"]["tokens"] == 0
    for call in direct["calls"]:
        visible = EvidenceBundle.restore(call["bundle"]).policy_view()
        source = "state" if kind == "copy_current_state" else "baseline"
        assert call["proposed_probability"] == visible[source]["forecast"]["value"]
        assert call["proposed_action"] == "OVERRIDE"
        assert call["receipt"]["executor"] == kind + ".v1"
        assert call["receipt"]["cost"]["compute_ms"] == 1
    identity = bind_execution(config, None)["execution_contract"]
    assert identity["implementation"] == kind + ".v1"
    other = bind_execution(dict(config, program_prediction="frequency_mapping"), None)
    assert identity != other["execution_contract"]


def test_registered_program_kind_is_an_explicit_comparison_factor():
    data, bank, config = typed_fixture(predictor_kind="program")
    specs = [
        experiment_spec(data, bank, dict(config, program_prediction=k))
        for k in ("frequency_mapping", "copy_current_state", "copy_latest_baseline")
    ]
    assert all(s["invariants"] == specs[0]["invariants"] for s in specs)
    assert len({s["interventions"]["program_prediction"] for s in specs}) == 3


def test_copy_kind_requires_typed_explicit_program_role():
    data, bank, config = typed_fixture(program_prediction="copy_current_state")
    with pytest.raises(ValueError, match="program"):
        run_session(data, bank, config)
