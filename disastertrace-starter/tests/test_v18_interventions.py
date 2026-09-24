import functools
import random
from copy import deepcopy

import pytest

from disastertrace.monitoring_v1.interventions_v18 import _digest, apply_intervention
from disastertrace.monitoring_v1.natural_track_v18 import (
    NaturalAction,
    NaturalKernel,
    NaturalSource,
    replay_suffix,
)


def parent():
    return [
        {
            "source_id": "s",
            "source_revision": "r1",
            "kind": "taf",
            "issued_at": 1,
            "available_at": 2,
            "valid_start": 100,
            "valid_end": 200,
            "content": {"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 8000}]},
        },
        {
            "source_id": "s",
            "source_revision": "r2",
            "kind": "taf",
            "issued_at": 3,
            "available_at": 4,
            "valid_start": 100,
            "valid_end": 200,
            "content": {"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 4000}]},
        },
    ]


def test_identity_repeat_is_duplicate_and_keeps_content():
    result = apply_intervention(parent(), "identity_repeat", target_start=100, target_end=200, as_of=10)
    assert result.qualification[-1]["status"] == "DUPLICATE"
    assert result.held_fields == ["target_start", "target_end", "issued_at"]


def test_matched_sham_does_not_change_target_projection():
    result = apply_intervention(parent(), "matched_sham", target_start=100, target_end=200, as_of=10)
    assert result.qualification[-1]["status"] == "SOURCE_CHANGE_NO_TARGET_CHANGE"


def test_delay_is_not_natural_no_change():
    result = apply_intervention(parent(), "delay", target_start=100, target_end=200, as_of=10)
    assert result.qualification[-1]["status"] == "NOT_YET_AVAILABLE"


# ---------------------------------------------------------------------------
# Genuine repair: evict provably wrong agent state from a NaturalKernel
# snapshot, then re-run the suffix; the control re-runs the untouched
# snapshot with a second policy built by the same repair_policy factory.
# ---------------------------------------------------------------------------


def retrieve_then_stop(state):
    """Fake policy: RETRIEVE q1 while it is not cached, otherwise STOP."""

    if "q1" not in state["read_query_ids"]:
        return NaturalAction("RETRIEVE", state["clock"], query_id="q1")
    return NaturalAction("STOP", state["clock"])


def corrupted_cache_snapshot():
    """Clock 10; q1 (published at 10 as 4000 m) was read but cached as 9999 m."""

    env = NaturalKernel([NaturalSource("q1", 10, {"visibility_m": 4000})], start=0, deadline=60)
    env.step(NaturalAction("WAIT", 0, wake_at=10))
    env.step(NaturalAction("RETRIEVE", 10, query_id="q1"))
    snapshot = env.snapshot()
    snapshot["read"]["q1"] = {"visibility_m": 9999}
    return snapshot


def repair(snapshot, patch, policy_factory=lambda: retrieve_then_stop):
    # repair_policy is a zero-argument factory (one fresh policy per replay);
    # stateless function policies are wrapped as `lambda: policy`.
    return apply_intervention(
        parent(),
        "repair",
        target_start=100,
        target_end=200,
        as_of=10,
        kernel_snapshot=snapshot,
        corrected_state_patch=patch,
        repair_policy=policy_factory,
        max_actions=5,
    )


def test_repair_without_agent_state_is_not_applicable_and_keeps_stream():
    result = apply_intervention(parent(), "repair", target_start=100, target_end=200, as_of=10)
    assert result.status == "NOT_APPLICABLE"
    assert result.repair_witness == {"reason": "no_agent_state_supplied"}
    assert result.changed_fields == []
    assert result.natural_trace is None and result.control_trace is None
    assert result.records == parent()
    assert result.to_dict()["status"] == "NOT_APPLICABLE"


def test_repair_of_a_correct_cache_entry_is_not_applicable():
    env = NaturalKernel([NaturalSource("q1", 10, {"visibility_m": 4000})], start=0, deadline=60)
    env.step(NaturalAction("WAIT", 0, wake_at=10))
    env.step(NaturalAction("RETRIEVE", 10, query_id="q1"))
    result = repair(env.snapshot(), {"read": {"q1": None}})
    assert result.status == "NOT_APPLICABLE"
    assert result.repair_witness == {"reason": "no_provably_wrong_agent_state", "checked": ["q1"]}
    assert result.natural_trace is None and result.changed_fields == []


def test_repair_evicts_wrong_cache_and_genuinely_reruns_suffix():
    snapshot = corrupted_cache_snapshot()
    before = deepcopy(snapshot)
    result = repair(snapshot, {"read": {"q1": None}})
    stop = {"action": "STOP", "at": 10, "result": {"status": "stopped", "clock": 10}}
    reread = {
        "action": "RETRIEVE",
        "at": 10,
        "result": {"status": "available", "query_id": "q1", "content": {"visibility_m": 4000}},
    }
    assert result.status == "APPLIED"
    # Control keeps the wrong cache, so the policy stops at once.
    assert result.control_trace == [stop]
    # Repaired agent re-acquires q1 from the environment: true content, no 9999.
    assert result.natural_trace == [reread, stop]
    assert result.changed_fields == ["agent_state.read.q1"]
    witness = result.repair_witness
    assert witness["evicted"]["q1"]["reason"] == "content_differs_from_source"
    assert witness["snapshot_clock"] == 10 and witness["prefix_action_count"] == 2
    assert witness["traces_differ"] is True
    # Sources, action prefix and the caller's snapshot are untouched.
    assert snapshot == before
    assert witness["sources_sha256"] == _digest(before["sources"])
    assert witness["action_prefix_sha256"] == _digest(before["actions"])
    assert result.records == parent()
    # The traces are what an independently restored kernel really does.
    for trace, state in ((result.control_trace, before), (result.natural_trace, {**before, "read": {}})):
        env = NaturalKernel.from_snapshot(state)
        replayed = [env.step(retrieve_then_stop(env.public_state())) for _ in trace]
        assert [row["result"] for row in trace] == replayed
        assert env.actions[: len(before["actions"])] == before["actions"]
        assert env.public_state()["terminal"] is True


def test_repair_refuses_to_leave_another_provably_wrong_entry_uncorrected():
    # "now" is cached with the wrong content; "future" is a secret cached
    # before it was ever legitimately available. The caller only names "now"
    # for eviction. Applying the repair anyway would report APPLIED while
    # "future"'s leaked content is still sitting in the "corrected" agent
    # state (adversarial-review B3) -- must be refused instead.
    env = NaturalKernel(
        [NaturalSource("now", 10, {"visibility_m": 4000}), NaturalSource("future", 30, {"visibility_m": 1000})],
        start=0,
        deadline=60,
    )
    env.step(NaturalAction("WAIT", 0, wake_at=10))
    snapshot = env.snapshot()
    snapshot["read"]["now"] = {"visibility_m": 9999}  # content_differs_from_source
    snapshot["read"]["future"] = {"visibility_m": 1000}  # read_before_available: leaked secret
    stop_immediately = lambda state: NaturalAction("STOP", state["clock"])
    with pytest.raises(ValueError, match="Other cached entries are also provably wrong"):
        repair(snapshot, {"read": {"now": None}}, policy_factory=lambda: stop_immediately)
    # Naming both is accepted and evicts the secret too.
    result = repair(snapshot, {"read": {"now": None, "future": None}}, policy_factory=lambda: stop_immediately)
    assert result.status == "APPLIED"
    assert result.repair_witness["evicted"]["future"]["reason"] == "read_before_available"


def test_repair_of_future_read_forces_the_agent_to_wait_for_publication():
    env = NaturalKernel([NaturalSource("q1", 30, {"visibility_m": 9000})], start=0, deadline=60)
    env.step(NaturalAction("WAIT", 0, wake_at=10))
    snapshot = env.snapshot()
    snapshot["read"]["q1"] = {"visibility_m": 9000}  # leaked before publication at 30

    def wait_then_read(state):
        if "q1" in state["read_query_ids"]:
            return NaturalAction("STOP", state["clock"])
        if state["clock"] < 30:
            return NaturalAction("WAIT", state["clock"], wake_at=30)
        return NaturalAction("RETRIEVE", state["clock"], query_id="q1")

    result = repair(snapshot, {"read": {"q1": None}}, policy_factory=lambda: wait_then_read)
    assert result.repair_witness["evicted"]["q1"]["reason"] == "read_before_available"
    assert result.control_trace == [{"action": "STOP", "at": 10, "result": {"status": "stopped", "clock": 10}}]
    assert result.natural_trace == [
        {"action": "WAIT", "at": 10, "result": {"status": "advanced", "clock": 30}},
        {
            "action": "RETRIEVE",
            "at": 30,
            "result": {"status": "available", "query_id": "q1", "content": {"visibility_m": 9000}},
        },
        {"action": "STOP", "at": 30, "result": {"status": "stopped", "clock": 30}},
    ]


class ClockMemoryPolicy:
    """Stateful fake agent whose choices depend on what it has seen before.

    It keeps every public state it was shown, plus the highest clock it has
    ever observed, the way an LLM agent's conversation history persists
    between calls.  While q1 is not cached it RETRIEVEs q1.  After that it
    WAITs in 10-tick steps until it has *ever* seen clock 40, then STOPs.
    """

    def __init__(self):
        self.seen = []
        self.max_clock_seen = 0

    def __call__(self, state):
        self.seen.append(deepcopy(state))
        self.max_clock_seen = max(self.max_clock_seen, state["clock"])
        if "q1" not in state["read_query_ids"]:
            return NaturalAction("RETRIEVE", state["clock"], query_id="q1")
        if self.max_clock_seen < 40:
            return NaturalAction("WAIT", state["clock"], wake_at=state["clock"] + 10)
        return NaturalAction("STOP", state["clock"])


def test_repair_replays_get_separate_policy_instances_so_control_future_cannot_leak():
    # The control replay legitimately runs the clock from the snapshot (10)
    # on to 40.  Before the fix, the SAME policy object then drove the natural
    # replay, so a stateful policy started it already "knowing" clock 40.
    snapshot = corrupted_cache_snapshot()
    before = deepcopy(snapshot)
    corrected = {**before, "read": {}}  # the snapshot with q1 evicted
    built = []

    def factory():
        built.append(ClockMemoryPolicy())
        return built[-1]

    result = apply_intervention(
        parent(),
        "repair",
        target_start=100,
        target_end=200,
        as_of=10,
        kernel_snapshot=snapshot,
        corrected_state_patch={"read": {"q1": None}},
        repair_policy=factory,
        max_actions=10,
    )
    assert result.status == "APPLIED"
    # The factory was called twice (natural first), giving two distinct
    # objects, and the witness records how the replays were separated.
    assert len(built) == 2 and built[0] is not built[1]
    natural_policy, control_policy = built
    assert result.repair_witness["policy_isolation"] == {
        "guarantee": "best_effort_in_process_not_guaranteed",
        "policies_built_before_any_replay": True,
        "build_order": ["natural", "control"],
        "replay_order": ["natural", "control"],
        "same_policy_object": False,
        "same_policy_object_false_rules_out_shared_state": False,
        "same_object_allowed_as_plain_function": False,
        "stdlib_random_rewound_between_replays": True,
        "stdlib_random_restored_after_call": True,
        "residual_leak_direction": "within_call_natural_to_control_across_calls_unconstrained",
        "cross_call_isolation": False,
    }
    # The control replay really observed ticks past the snapshot clock.
    assert result.repair_witness["snapshot_clock"] == 10
    assert control_policy.seen[0]["read_query_ids"] == ["q1"]  # wrong cache kept
    assert [state["clock"] for state in control_policy.seen] == [10, 20, 30, 40]
    assert [row["at"] for row in result.control_trace] == [10, 20, 30, 40]

    # Second control case: the same kind of fresh policy on the corrected
    # snapshot, with NO preceding control replay at all.
    isolated_policy = ClockMemoryPolicy()
    isolated = replay_suffix(corrected, isolated_policy, max_actions=10)
    assert [row["action"] for row in isolated] == ["RETRIEVE", "WAIT", "WAIT", "WAIT", "STOP"]
    assert result.natural_trace == isolated
    assert _digest(result.natural_trace) == _digest(isolated)  # bit-for-bit
    # The natural-replay policy was shown exactly what the isolated one was
    # shown, and nothing from the control replay's future ticks.
    assert natural_policy.seen == isolated_policy.seen
    assert natural_policy.seen[0]["clock"] == 10 and natural_policy.seen[0]["read_query_ids"] == []
    # The control trace is also what a fresh policy produces on its own.
    assert result.control_trace == replay_suffix(before, ClockMemoryPolicy(), max_actions=10)

    # Sensitivity check, so the equalities above are not vacuous: rebuild the
    # pre-fix behaviour (ONE object drives the control replay, then the
    # natural replay).  The policy starts the natural replay with
    # max_clock_seen == 40 and stops right after re-reading q1.
    shared = ClockMemoryPolicy()
    replay_suffix(before, shared, max_actions=10)
    leaked = replay_suffix(corrected, shared, max_actions=10)
    assert [row["action"] for row in leaked] == ["RETRIEVE", "STOP"]
    assert leaked != isolated


def repair_with(factory, snapshot=None):
    return apply_intervention(
        parent(),
        "repair",
        target_start=100,
        target_end=200,
        as_of=10,
        kernel_snapshot=corrupted_cache_snapshot() if snapshot is None else snapshot,
        corrected_state_patch={"read": {"q1": None}},
        repair_policy=factory,
        max_actions=10,
    )


def test_repair_rejects_a_factory_that_serves_one_object_to_both_replays():
    shared_instance = ClockMemoryPolicy()

    @functools.lru_cache(maxsize=None)
    def cached_factory():
        return ClockMemoryPolicy()

    class Singleton(ClockMemoryPolicy):
        _instance = None

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                ClockMemoryPolicy.__init__(cls._instance)
            return cls._instance

        def __init__(self):
            pass

    def closure_policy_factory():
        memory = []

        def policy(state):
            memory.append(state["clock"])
            return retrieve_then_stop(state)

        return policy

    closure_policy = closure_policy_factory()

    def default_arg_policy(state, memory=[]):
        memory.append(state["clock"])
        return retrieve_then_stop(state)

    for factory in (
        lambda: shared_instance,
        cached_factory,
        Singleton,
        lambda: shared_instance.__call__,  # new bound method, same owner
        lambda: closure_policy,
        lambda: default_arg_policy,
    ):
        with pytest.raises(ValueError, match="same policy object for both replays"):
            repair_with(factory)
    # The rejection happens before either replay runs.
    assert shared_instance.seen == []

    # A plain function without closure/defaults/attributes may be returned
    # twice; the witness says so.
    result = repair_with(lambda: retrieve_then_stop)
    assert result.status == "APPLIED"
    isolation = result.repair_witness["policy_isolation"]
    assert isolation["same_policy_object"] is True
    assert isolation["same_object_allowed_as_plain_function"] is True


class LongTermMemoryPolicy:
    """Fake agent with a persistent memory store (reviewer's F2 pattern).

    At construction it loads a PRIVATE deep copy of the store; as it runs it
    writes the highest clock it has seen back to the store.  Two instances
    never share an object, yet one built after the other has run would load
    what that run wrote.
    """

    def __init__(self, store):
        self.store = store
        self.max_clock_seen = deepcopy(store.get("max_clock_seen", 0))

    def __call__(self, state):
        self.max_clock_seen = max(self.max_clock_seen, state["clock"])
        self.store["max_clock_seen"] = self.max_clock_seen
        if "q1" not in state["read_query_ids"]:
            return NaturalAction("RETRIEVE", state["clock"], query_id="q1")
        if self.max_clock_seen < 40:
            return NaturalAction("WAIT", state["clock"], wake_at=state["clock"] + 10)
        return NaturalAction("STOP", state["clock"])


def test_repair_builds_both_policies_before_either_replay_runs():
    before = corrupted_cache_snapshot()
    corrected = {**before, "read": {}}
    store = {}
    result = repair_with(lambda: LongTermMemoryPolicy(store))
    assert result.status == "APPLIED"
    # Each trace is what a policy built from the pristine store produces
    # alone.  Had either policy been built after the other replay ran, it
    # would have loaded max_clock_seen == 40 and stopped early.
    assert result.natural_trace == replay_suffix(corrected, LongTermMemoryPolicy({}), max_actions=10)
    assert result.control_trace == replay_suffix(before, LongTermMemoryPolicy({}), max_actions=10)
    assert [row["action"] for row in result.control_trace] == ["WAIT", "WAIT", "WAIT", "STOP"]
    # Sensitivity: a policy built after a replay wrote to the store stops at once.
    late = replay_suffix(before, LongTermMemoryPolicy(store), max_actions=10)
    assert [row["action"] for row in late] == ["STOP"]


class SharedDictPolicy(ClockMemoryPolicy):
    """Distinct instances that all read and write one closed-over dict."""

    def __init__(self, shared):
        super().__init__()
        self.shared = shared

    def __call__(self, state):
        self.shared["max"] = max(self.shared.get("max", 0), state["clock"])
        self.max_clock_seen = self.shared["max"]
        self.seen.append(deepcopy(state))
        if "q1" not in state["read_query_ids"]:
            return NaturalAction("RETRIEVE", state["clock"], query_id="q1")
        if self.max_clock_seen < 40:
            return NaturalAction("WAIT", state["clock"], wake_at=state["clock"] + 10)
        return NaturalAction("STOP", state["clock"])


def test_repair_runs_the_natural_replay_before_the_control_replay():
    # Shared state underneath distinct objects cannot be detected.  Running
    # the natural replay first keeps the control replay's future out of the
    # natural (repaired) trace.  KNOWN LIMITATION, deliberately not asserted
    # as correct: the control trace here can still be shaped by the natural
    # replay's future.
    before = corrupted_cache_snapshot()
    corrected = {**before, "read": {}}
    shared = {}
    result = repair_with(lambda: SharedDictPolicy(shared))
    assert result.status == "APPLIED"
    assert result.natural_trace == replay_suffix(corrected, SharedDictPolicy({}), max_actions=10)


class RandomWaitPolicy:
    """Holds no state, but draws its WAIT lengths from the global RNG."""

    def __call__(self, state):
        if "q1" not in state["read_query_ids"]:
            return NaturalAction("RETRIEVE", state["clock"], query_id="q1")
        if state["clock"] < 40:
            return NaturalAction("WAIT", state["clock"], wake_at=state["clock"] + random.randint(3, 12))
        return NaturalAction("STOP", state["clock"])


def test_repair_rewinds_the_stdlib_rng_so_one_replay_cannot_shift_the_other():
    saved = random.getstate()
    try:
        before = corrupted_cache_snapshot()
        corrected = {**before, "read": {}}
        random.seed(20260924)
        start = random.getstate()
        result = repair_with(RandomWaitPolicy)
        assert result.status == "APPLIED"
        random.setstate(start)
        isolated_natural = replay_suffix(corrected, RandomWaitPolicy(), max_actions=10)
        random.setstate(start)
        isolated_control = replay_suffix(before, RandomWaitPolicy(), max_actions=10)
        assert result.natural_trace == isolated_natural
        assert result.control_trace == isolated_control
        # Sensitivity: without the rewind, the second replay starts from
        # wherever the first one left the RNG and takes different waits.
        random.setstate(start)
        replay_suffix(corrected, RandomWaitPolicy(), max_actions=10)
        unrewound_control = replay_suffix(before, RandomWaitPolicy(), max_actions=10)
        assert unrewound_control != isolated_control
    finally:
        random.setstate(saved)


def test_repair_restores_the_callers_stdlib_rng_so_a_later_call_is_not_shifted():
    saved = random.getstate()
    try:
        random.seed(7)
        start = random.getstate()
        first = repair_with(RandomWaitPolicy)
        # The replays drew numbers, but the caller's RNG is back where it was.
        assert random.getstate() == start
        # So a second repair call (e.g. the next checkpoint) sees exactly
        # what it would have seen had the first call never happened.
        second = repair_with(RandomWaitPolicy)
        random.setstate(start)
        alone = repair_with(RandomWaitPolicy)
        assert (second.natural_trace, second.control_trace) == (alone.natural_trace, alone.control_trace)
        assert (first.natural_trace, first.control_trace) == (alone.natural_trace, alone.control_trace)

        # Also restored when a replay fails partway through.
        class DrawThenFail:
            def __call__(self, state):
                random.random()
                raise RuntimeError("policy failed mid-replay")

        random.setstate(start)
        with pytest.raises(RuntimeError, match="mid-replay"):
            repair_with(DrawThenFail)
        assert random.getstate() == start
    finally:
        random.setstate(saved)


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"sources": []}, "historical kernel state: sources"),
        ({"actions": []}, "historical kernel state: actions"),
        ({"read": {"q1": None}, "actions": []}, "historical kernel state: actions"),
        ({"read": {"q1": None}, "sources": [], "actions": []}, "historical kernel state: actions, sources"),
        ({"clock": 0}, "only correct the agent read cache"),
        ({"read": {"q1": {"visibility_m": 4000}}}, "only evicts"),
        ({"read": {"q9": None}}, "never consumed"),
        ({"read": {}}, "at least one cached query"),
    ],
)
def test_repair_rejects_corrections_outside_provably_wrong_agent_state(patch, message):
    snapshot = corrupted_cache_snapshot()
    before = deepcopy(snapshot)
    with pytest.raises(ValueError, match=message):
        repair(snapshot, patch)
    assert snapshot == before


def test_repair_rejects_half_an_interface_and_agent_state_on_other_interventions():
    with pytest.raises(ValueError, match="both kernel_snapshot and corrected_state_patch"):
        apply_intervention(parent(), "repair", target_start=100, target_end=200, kernel_snapshot=corrupted_cache_snapshot())
    with pytest.raises(ValueError, match="repair_policy and max_actions"):
        apply_intervention(
            parent(), "repair", target_start=100, target_end=200,
            kernel_snapshot=corrupted_cache_snapshot(), corrected_state_patch={"read": {"q1": None}},
        )
    with pytest.raises(ValueError, match="only meaningful for repair"):
        apply_intervention(parent(), "delay", target_start=100, target_end=200, max_actions=3)


def test_repair_policy_must_be_a_zero_argument_factory():
    patch = {"read": {"q1": None}}
    # Passing a policy itself (the pre-factory contract), whether a function
    # or a stateful instance, is refused up front. Otherwise one object
    # would drive both replays.
    for not_a_factory in (retrieve_then_stop, ClockMemoryPolicy(), "retrieve_then_stop"):
        with pytest.raises(TypeError, match="zero-argument factory"):
            repair(corrupted_cache_snapshot(), patch, policy_factory=not_a_factory)
    with pytest.raises(TypeError, match="must return a NaturalPolicy callable"):
        repair(corrupted_cache_snapshot(), patch, policy_factory=lambda: None)

    env = NaturalKernel.from_snapshot(corrupted_cache_snapshot())
    env.step(NaturalAction("STOP", 10))
    terminal = env.snapshot()
    # The contract is checked even where the repair is NOT_APPLICABLE...
    with pytest.raises(TypeError, match="zero-argument factory"):
        repair(terminal, patch, policy_factory=retrieve_then_stop)

    # ...but the factory itself is only invoked when a suffix is replayed.
    def must_not_be_called():
        raise AssertionError("factory invoked although no suffix is replayed")

    assert repair(terminal, patch, policy_factory=must_not_be_called).status == "NOT_APPLICABLE"


def test_repair_on_terminal_snapshot_is_not_applicable():
    snapshot = corrupted_cache_snapshot()
    env = NaturalKernel.from_snapshot(snapshot)
    env.step(NaturalAction("STOP", 10))
    result = repair(env.snapshot(), {"read": {"q1": None}})
    assert result.status == "NOT_APPLICABLE"
    assert result.repair_witness == {"reason": "terminal_snapshot_has_no_suffix"}


# ---------------------------------------------------------------------------
# Regression guards for the two previously fixed dangerous behaviors, plus
# schema compatibility of the five non-repair interventions.
# ---------------------------------------------------------------------------


def test_identity_repeat_never_grows_the_returned_stream():
    result = apply_intervention(parent(), "identity_repeat", target_start=100, target_end=200, as_of=10)
    assert result.records == parent()
    assert len(result.records) == 2 and len(result.qualification) == 3
    assert result.changed_fields == []


def test_repair_never_copies_later_content_into_earlier_records():
    for result in (
        apply_intervention(parent(), "repair", target_start=100, target_end=200, as_of=10),
        repair(corrupted_cache_snapshot(), {"read": {"q1": None}}),
    ):
        assert result.records == parent()
        assert result.records[0]["content"]["periods"][0]["visibility_m"] == 8000


@pytest.mark.parametrize(
    "name", ["identity_repeat", "same_origin_duplicate", "matched_sham", "withhold", "delay"]
)
def test_non_repair_interventions_keep_their_exact_serialised_schema(name):
    result = apply_intervention(parent(), name, target_start=100, target_end=200, as_of=10)
    assert set(result.to_dict()) == {
        "schema", "intervention", "records", "changed_fields", "held_fields", "qualification"
    }
    assert result.status is None and result.natural_trace is None and result.repair_witness is None
