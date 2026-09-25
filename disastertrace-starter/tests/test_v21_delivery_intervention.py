from copy import deepcopy

import pytest

from disastertrace.monitoring_v1.delivery_intervention_v21 import run_delivery_probe
from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.synthetic_natural_v21 import target_card


def parent_snapshot():
    env = NaturalKernel(
        [
            NaturalSource("q0", 0, {"visibility_m": 4000}),
            NaturalSource("q1", 0, {"visibility_m": 3000}),
        ],
        start=0,
        deadline=20,
        target=target_card(),
    )
    env.step(NaturalAction("RETRIEVE", 0, query_id="q0"))
    return env.snapshot()


def test_delivery_probe_keeps_parent_and_catalogue_fixed():
    parent = parent_snapshot()
    frozen = deepcopy(parent)
    artifact = run_delivery_probe(parent)
    assert parent == frozen
    assert artifact["parent_untouched"] is True
    assert artifact["catalogue_equal"] is True
    assert artifact["withhold_changes_delivery_only"] is True
    assert artifact["arms"]["withhold"]["trace"][0]["result"]["status"] == "unavailable"
    assert artifact["arms"]["noop"]["trace"][0]["result"]["status"] == "available"


def test_blocked_delivery_branch_keeps_kernel_clock_contract():
    from disastertrace.monitoring_v1.delivery_intervention_v21 import DeliveryKernel

    parent = parent_snapshot()
    child = DeliveryKernel(parent, blocked_until={"q1": 10})
    with pytest.raises(ValueError, match="clock"):
        child.step(NaturalAction("RETRIEVE", 1, query_id="q1"))
    assert child.snapshot() == parent
