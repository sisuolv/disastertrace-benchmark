"""Continuation is predeclared and never retries an unknown logical request."""

import json

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


class FirstFailure:
    def __init__(self, role):
        self.role = role
        self.invoked = []

    def __call__(self, system, request, call_id):
        assert call_id not in self.invoked
        self.invoked.append(call_id)
        if call_id == self.role + "-0":
            raise RuntimeError("Unknown first call; do not retry")
        if call_id.startswith("select-"):
            value = {"query_order": [], "forecast_handles": list(request["targets"])[:1]}
        else:
            value = {"fact_truth": "unknown", "probability": 0.3}
        return json.dumps(value), {
            "input_tokens": 1,
            "output_tokens": 1,
            "seconds": 0.001,
            "ended_with_eos": True,
        }


@pytest.mark.parametrize("role", ["forecast", "select"])
@pytest.mark.parametrize("policy", ["fail_session_v1", "skip_failed_call_continue_v1"])
@pytest.mark.parametrize("restore", [False, True])
def test_distinct_later_calls_follow_frozen_policy_with_unknown_reserve(role, policy, restore):
    data, bank, config = typed_fixture(
        failure_continuation_policy=policy,
        isolation_mode="actual_cost_clock",
        authorization_mode="session_shared",
        public_call_slot_ms=1000,
        selector_kind="llm" if role == "select" else "round_robin",
        predictor_kind="program" if role == "select" else "llm",
        model_call_budget=4,
    )
    backend = FirstFailure(role)
    if restore:
        session = SessionCoordinator(data, bank, config, backend=backend)
        session.step()
        resumed = SessionCoordinator.restore(session.snapshot(), data, bank, backend=backend)
        report = resumed.finish()
    else:
        report = run_session(data, bank, config, backend=backend)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert (
        report["resource_reserved"]["tokens"]
        == config["input_token_cap"] + config["output_token_cap"]
    )
    assert backend.invoked.count(role + "-0") == 1
    assert (
        len(backend.invoked) > 1
        if policy == "skip_failed_call_continue_v1"
        else len(backend.invoked) == 1
    )
    assert report["failure_continuation"]["policy"] == policy
    assert report["failure_continuation"]["reservation_retained"]


def test_unknown_continuation_policy_is_rejected_before_dispatch():
    data, bank, config = typed_fixture(failure_continuation_policy="retry_until_good")
    with pytest.raises(ValueError, match="continuation"):
        run_session(data, bank, config)
