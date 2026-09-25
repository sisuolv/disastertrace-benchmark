from copy import deepcopy

import pytest

from disastertrace.monitoring_v1.natural_selector_policy_v21 import CatalogueSelectorPolicy
from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.synthetic_natural_v21 import target_card


def _kernel(order=None):
    rows = {
        "opaque-a": NaturalSource("opaque-a", 0, {"visibility_m": 4000}),
        "opaque-b": NaturalSource("opaque-b", 0, {"visibility_m": 9000}),
        "opaque-c": NaturalSource("opaque-c", 0, {"visibility_m": 7000}),
    }
    order = order or list(rows)
    return NaturalKernel([rows[key] for key in order], start=0, deadline=30, target=target_card())


def _run(kernel, policy):
    trace = []
    while not kernel.public_state()["terminal"]:
        action = policy(kernel.public_state())
        assert isinstance(action, NaturalAction)
        trace.append(action)
        kernel.step(action)
    return trace


def test_selector_adapter_uses_public_catalogue_and_budget():
    kernel = _kernel()
    trace = _run(kernel, CatalogueSelectorPolicy(max_queries=2, seed=17))
    assert [action.kind for action in trace] == ["RETRIEVE", "RETRIEVE", "UPDATE", "STOP"]
    assert len([action for action in trace if action.kind == "RETRIEVE"]) == 2
    assert len(kernel.public_state()["read_query_ids"]) == 2


def test_selector_result_does_not_depend_on_source_serialization_order():
    left = _kernel(["opaque-a", "opaque-b", "opaque-c"])
    right = _kernel(["opaque-c", "opaque-a", "opaque-b"])
    policy_left = CatalogueSelectorPolicy(max_queries=2, seed=17)
    policy_right = CatalogueSelectorPolicy(max_queries=2, seed=17)
    left_trace = _run(left, policy_left)
    right_trace = _run(right, policy_right)
    assert [a.query_id for a in left_trace if a.kind == "RETRIEVE"] == [
        a.query_id for a in right_trace if a.kind == "RETRIEVE"
    ]


def test_selector_rejects_malformed_or_hidden_public_state():
    policy = CatalogueSelectorPolicy()
    state = _kernel().public_state()
    state["catalogue"][0]["content"] = {"secret": 1}
    with pytest.raises(ValueError, match="Malformed public catalogue"):
        policy(state)
    broken = deepcopy(_kernel().public_state())
    broken["catalogue"][0]["query_id"] = ""
    with pytest.raises(ValueError, match="Catalogue query IDs"):
        policy(broken)
