"""Fork continuation: one NaturalKernel snapshot, independent suffix re-runs.

Only natural_track_v18 is exercised here (no interventions module).  Every
expected trace below was written by hand from the kernel's transition rules
before the tests were run; each is then cross-checked by stepping a freshly
restored kernel with explicitly listed actions.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from disastertrace.monitoring_v1.natural_track_v18 import (
    NaturalAction,
    NaturalKernel,
    NaturalSource,
    replay_suffix,
)


def parent_kernel():
    """q1 published at 10, q2 at 30; the parent waited to 10 and read q1."""

    env = NaturalKernel(
        [NaturalSource("q1", 10, {"visibility_m": 4000}), NaturalSource("q2", 30, {"visibility_m": 9000})],
        start=0,
        deadline=60,
    )
    env.step(NaturalAction("WAIT", 0, wake_at=10))
    env.step(NaturalAction("RETRIEVE", 10, query_id="q1"))
    return env


def stop_now(state):
    return NaturalAction("STOP", state["clock"])


def wait_read_update_stop(state):
    if state["clock"] < 30:
        return NaturalAction("WAIT", state["clock"], wake_at=30)
    if "q2" not in state["read_query_ids"]:
        return NaturalAction("RETRIEVE", state["clock"], query_id="q2")
    if state["action_count"] == 4:
        return NaturalAction("UPDATE", state["clock"], probability=0.7)
    return NaturalAction("STOP", state["clock"])


STOP_AT_10 = [{"action": "STOP", "at": 10, "result": {"status": "stopped", "clock": 10}}]
WAIT_READ_UPDATE_STOP = [
    {"action": "WAIT", "at": 10, "result": {"status": "advanced", "clock": 30}},
    {"action": "RETRIEVE", "at": 30, "result": {"status": "available", "query_id": "q2", "content": {"visibility_m": 9000}}},
    {"action": "UPDATE", "at": 30, "result": {"status": "updated", "probability": 0.7, "read_query_ids": ["q1", "q2"]}},
    {"action": "STOP", "at": 30, "result": {"status": "stopped", "clock": 30}},
]


def test_snapshot_round_trip_preserves_every_state_field():
    env = parent_kernel()
    snapshot = env.snapshot()
    restored = NaturalKernel.from_snapshot(snapshot)
    assert restored.public_state() == env.public_state()
    assert restored.snapshot() == snapshot
    assert (restored.clock, restored.deadline, restored.stopped, restored.expired) == (10, 60, False, False)
    assert restored.read == {"q1": {"visibility_m": 4000}}
    assert restored.actions == env.actions and len(restored.actions) == 2
    assert restored.sources == env.sources


def test_snapshot_is_detached_from_live_kernel_in_both_directions():
    env = parent_kernel()
    snapshot = env.snapshot()
    frozen = deepcopy(snapshot)
    env.read["q1"]["visibility_m"] = -1
    env.actions[0]["result"]["clock"] = -1
    env.step(NaturalAction("WAIT", 10, wake_at=20))
    assert snapshot == frozen
    snapshot["read"]["q1"]["visibility_m"] = -2
    snapshot["sources"][0]["content"]["visibility_m"] = -2
    snapshot["actions"].append({"action": "STOP", "at": 10, "result": {}})
    assert env.sources["q1"].content == {"visibility_m": 4000}
    assert len(env.actions) == 3 and env.read["q1"] == {"visibility_m": -1}


def test_forked_kernels_share_no_state_with_each_other_or_the_parent():
    env = parent_kernel()
    snapshot = env.snapshot()
    left, right = NaturalKernel.from_snapshot(snapshot), NaturalKernel.from_snapshot(snapshot)
    assert left.read is not right.read and left.read["q1"] is not right.read["q1"]
    assert left.actions[0] is not right.actions[0]
    assert left.sources["q1"].content is not right.sources["q1"].content
    left.step(NaturalAction("WAIT", 10, wake_at=30))
    left.step(NaturalAction("RETRIEVE", 30, query_id="q2"))
    left.read["q1"]["visibility_m"] = -1
    right.step(NaturalAction("STOP", 10))
    assert right.public_state() == {
        "clock": 10, "deadline": 60, "read_query_ids": ["q1"], "stopped": True,
        "expired": False, "terminal": True, "action_count": 3,
    }
    assert right.read == {"q1": {"visibility_m": 4000}}
    assert left.public_state()["read_query_ids"] == ["q1", "q2"] and left.clock == 30
    assert env.public_state() == {
        "clock": 10, "deadline": 60, "read_query_ids": ["q1"], "stopped": False,
        "expired": False, "terminal": False, "action_count": 2,
    }


def test_two_policies_from_one_snapshot_yield_distinct_verifiable_traces():
    env = parent_kernel()
    snapshot = env.snapshot()
    frozen = deepcopy(snapshot)
    stop_trace = replay_suffix(snapshot, stop_now, max_actions=4)
    long_trace = replay_suffix(snapshot, wait_read_update_stop, max_actions=4)
    assert stop_trace == STOP_AT_10
    assert long_trace == WAIT_READ_UPDATE_STOP
    assert stop_trace != long_trace
    # Neither continuation touched the shared snapshot or the parent kernel.
    assert snapshot == frozen
    assert env.public_state()["action_count"] == 2 and env.clock == 10
    # Independent check: step a fresh fork with the hand-listed actions.
    for trace, actions in (
        (stop_trace, [NaturalAction("STOP", 10)]),
        (
            long_trace,
            [
                NaturalAction("WAIT", 10, wake_at=30),
                NaturalAction("RETRIEVE", 30, query_id="q2"),
                NaturalAction("UPDATE", 30, probability=0.7),
                NaturalAction("STOP", 30),
            ],
        ),
    ):
        fork = NaturalKernel.from_snapshot(frozen)
        assert [fork.step(action) for action in actions] == [row["result"] for row in trace]
        assert fork.actions == frozen["actions"] + trace


def test_replay_respects_availability_and_never_leaks_future_arrival_time():
    snapshot = parent_kernel().snapshot()

    def grab_q2_then_stop(state):
        if state["action_count"] == 2:
            return NaturalAction("RETRIEVE", state["clock"], query_id="q2")
        return NaturalAction("STOP", state["clock"])

    trace = replay_suffix(snapshot, grab_q2_then_stop, max_actions=3)
    assert trace == [
        {"action": "RETRIEVE", "at": 10, "result": {"status": "unavailable", "query_id": "q2"}},
        STOP_AT_10[0],
    ]


def test_replay_suffix_stops_cleanly_or_raises_explicitly():
    snapshot = parent_kernel().snapshot()
    stuck = lambda state: NaturalAction("RETRIEVE", state["clock"], query_id="q2")  # noqa: E731
    with pytest.raises(ValueError, match="within max_actions"):
        replay_suffix(snapshot, stuck, max_actions=3)
    with pytest.raises(TypeError, match="NaturalAction"):
        replay_suffix(snapshot, lambda state: {"kind": "STOP"}, max_actions=3)
    with pytest.raises(ValueError, match="positive integer"):
        replay_suffix(snapshot, stop_now, max_actions=0)
    with pytest.raises(ValueError, match="clock does not match"):
        replay_suffix(snapshot, lambda state: NaturalAction("STOP", 0), max_actions=3)
    terminal = NaturalKernel.from_snapshot(snapshot)
    terminal.step(NaturalAction("STOP", 10))
    assert replay_suffix(terminal.snapshot(), stop_now, max_actions=1) == []


def test_policy_cannot_mutate_kernel_through_its_state_argument():
    snapshot = parent_kernel().snapshot()

    def vandal(state):
        state["read_query_ids"].append("q2")
        state["clock"] = 999
        return NaturalAction("STOP", 10)

    assert replay_suffix(snapshot, vandal, max_actions=1) == STOP_AT_10


def test_expired_snapshot_round_trips_as_terminal():
    env = parent_kernel()
    env.step(NaturalAction("WAIT", 10, wake_at=90))
    restored = NaturalKernel.from_snapshot(env.snapshot())
    assert restored.public_state()["expired"] is True and restored.clock == 60
    with pytest.raises(ValueError, match="terminal"):
        restored.step(NaturalAction("STOP", 60))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s.pop("read"),
        lambda s: s.update(schema="other"),
        lambda s: s.update(expired=True),
        lambda s: s.update(stopped=True),
        lambda s: s.update(clock=61),
        lambda s: s["sources"].append(deepcopy(s["sources"][0])),
        lambda s: s["actions"].reverse(),
        lambda s: s["actions"][0].update(at=11),
        # clock=50 is within [0, deadline], so only the log-consistency check
        # (not the deadline check) can catch this: the log only supports
        # clock=10 after its 2 actions, so 50 is an inflated, unreachable
        # clock (adversarial-review B2).
        lambda s: s.update(clock=50),
        # The WAIT's own reported result.clock says 10, but is overwritten to
        # claim it woke at 999 -- the running clock must follow the log's
        # actual recorded results, not just the entry ordering.
        lambda s: s["actions"][0]["result"].update(clock=999),
    ],
)
def test_from_snapshot_rejects_inconsistent_state(mutate):
    snapshot = parent_kernel().snapshot()
    mutate(snapshot)
    with pytest.raises(ValueError):
        NaturalKernel.from_snapshot(snapshot)


def test_from_snapshot_rejects_an_action_after_an_expiring_wait():
    env = NaturalKernel([NaturalSource("q1", 10, {"visibility_m": 4000})], start=0, deadline=20)
    env.step(NaturalAction("WAIT", 0, wake_at=20))  # reaches the deadline: expires
    snapshot = env.snapshot()
    # Hand-append an action that could never really follow an expired kernel
    # (step() itself would refuse it) -- from_snapshot must refuse it too.
    snapshot["actions"].append({"action": "STOP", "at": 20, "result": {"status": "stopped", "clock": 20}})
    snapshot["stopped"] = True
    snapshot["expired"] = False  # only one terminal flag may be true; try to sneak the other past
    with pytest.raises(ValueError):
        NaturalKernel.from_snapshot(snapshot)
