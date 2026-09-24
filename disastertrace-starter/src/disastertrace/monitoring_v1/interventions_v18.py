"""Paired controlled interventions for the v18 mechanism pilot."""

from __future__ import annotations

import hashlib
import inspect
import json
import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .evidence_qualification_v18 import EvidenceRecord, qualify_stream
from .natural_track_v18 import NaturalKernel, NaturalPolicy, replay_suffix


# A zero-argument factory that builds one new NaturalPolicy per replay.
# Repair runs two replays (control and natural); isolating them is best
# effort only -- see apply_intervention for the full contract and its limits.
RepairPolicyFactory = Callable[[], NaturalPolicy]

REPAIR_APPLIED = "APPLIED"
REPAIR_NOT_APPLICABLE = "NOT_APPLICABLE"
# Kernel snapshot keys a repair may correct (agent-internal state) versus keys
# that are the historical record and must never be rewritten.
_REPAIRABLE_STATE = {"read"}
_HISTORICAL_STATE = {"sources", "actions"}


@dataclass(frozen=True)
class InterventionResult:
    intervention: str
    records: list[dict[str, Any]]
    changed_fields: list[str]
    held_fields: list[str]
    qualification: list[dict[str, Any]]
    # Repair-only fields.  They stay None for every other intervention and
    # to_dict() emits them only for repair, so the other five interventions
    # serialise exactly as before.
    status: str | None = None
    natural_trace: list[dict[str, Any]] | None = None
    control_trace: list[dict[str, Any]] | None = None
    repair_witness: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": "disastertrace.v18.intervention_result.v1",
            "intervention": self.intervention,
            "records": self.records,
            "changed_fields": self.changed_fields,
            "held_fields": self.held_fields,
            "qualification": self.qualification,
        }
        if self.intervention == "repair":
            payload.update(
                status=self.status,
                natural_trace=self.natural_trace,
                control_trace=self.control_trace,
                repair_witness=self.repair_witness,
            )
        return payload


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_error(snapshot: Mapping[str, Any], query_id: str) -> str | None:
    """Say why a cached read is provably wrong at snapshot time, else None.

    The proof uses only the recorded source history as of the snapshot clock:
    either no such source exists, the source had not yet been published when
    the cache claims to hold it, or the cache disagrees with the content that
    was actually published by then.
    """

    source = next((row for row in snapshot["sources"] if row["query_id"] == query_id), None)
    if source is None:
        return "unknown_query"
    if source["available_at"] > snapshot["clock"]:
        return "read_before_available"
    if snapshot["read"][query_id] != source["content"]:
        return "content_differs_from_source"
    return None


_FACTORY_CONTRACT = (
    "repair_policy must be a zero-argument factory that builds a new NaturalPolicy "
    "each time it is called (see apply_intervention), not a policy"
)


def _require_policy_factory(repair_policy: Any) -> None:
    """Reject anything that cannot be called as ``repair_policy()`` up front.

    This is what turns the pre-factory contract (passing the policy itself,
    which takes a ``public_state`` argument) into an immediate, explicit error
    instead of a confusing failure halfway through the first replay.  A
    callable whose signature cannot be introspected is let through; calling
    it in ``_fresh_policy`` is then the check.
    """

    if not callable(repair_policy):
        raise TypeError(_FACTORY_CONTRACT)
    try:
        signature = inspect.signature(repair_policy)
    except (TypeError, ValueError):
        return
    try:
        signature.bind()
    except TypeError as exc:
        raise TypeError(_FACTORY_CONTRACT) from exc


def _fresh_policy(repair_policy: RepairPolicyFactory) -> NaturalPolicy:
    """Build the policy for exactly one replay."""

    policy = repair_policy()
    if not callable(policy):
        raise TypeError(
            "repair_policy factory must return a NaturalPolicy callable, got " + type(policy).__name__
        )
    return policy


def _is_plain_function_without_own_state(policy: Any) -> bool:
    """True for a plain function with no closure, defaults or attributes.

    Such a function carries no state *of its own*, so the factory returning
    the same function object for both replays is tolerated -- that is what
    ``lambda: my_function`` does.  This is NOT a proof of statelessness: the
    function can still read and write module globals, class attributes or
    the ``random`` module, which this check cannot see.
    """

    return (
        inspect.isfunction(policy)
        and not policy.__closure__
        and not policy.__defaults__
        and not policy.__kwdefaults__
        and not getattr(policy, "__dict__", None)
    )


def _same_policy_object(first: Any, second: Any) -> bool:
    """True if both policies are one object, or bound methods of one object."""

    if first is second:
        return True
    owner = getattr(first, "__self__", None)
    return (
        owner is not None
        and not inspect.ismodule(owner)
        and owner is getattr(second, "__self__", None)
    )


def _repair(
    kernel_snapshot: Mapping[str, Any] | None,
    corrected_state_patch: Mapping[str, Any] | None,
    repair_policy: RepairPolicyFactory | None,
    max_actions: int | None,
) -> tuple[str, list[dict[str, Any]] | None, list[dict[str, Any]] | None, dict[str, Any]]:
    """Correct provably wrong agent state, then genuinely re-run the suffix.

    ``corrected_state_patch`` mirrors the snapshot layout and may only name
    read-cache entries to evict: ``{"read": {query_id: None}}``.  A repair
    never writes content into the agent: an evicted entry can only come back
    through a real RETRIEVE in the replayed suffix, under the kernel's own
    availability rules.  The control trace replays the untouched snapshot
    with a second policy built by the same ``repair_policy`` factory, so the
    two runs are meant to differ only by the eviction.

    Both replays legitimately run the clock past the snapshot, so any state
    the two policies share lets one replay's future ticks leak into the
    other.  The mitigations here are best effort, not a guarantee (see
    ``apply_intervention``), and each one holds only WITHIN ONE CALL:

    * both policies are built before either replay runs (natural first),
      so within this call constructing one cannot observe anything this
      call's replays produced;
    * the natural replay runs first, so within this call in-process state
      shared with the control policy cannot carry this call's control
      replay's future into the natural (repaired) trace.  The reverse
      direction stays open: shared state can carry the natural replay's
      future into the control trace of the same call;
    * one object (or bound methods of one object) serving both replays is
      rejected, except a plain function with no closure, defaults or
      attributes;
    * the stdlib ``random`` module state is rewound to the same point
      before each replay, so one replay's draw count cannot shift the
      other's, and is restored to its pre-call state when the call ends
      (also on error), so this call's draws cannot shift a later call.

    ACROSS CALLS NOTHING IS ISOLATED.  Repeated repairs on one episode (for
    example successive checkpoints such as T-60, T-40, T-20) run in the same
    process, and any state that outlives one call -- a class attribute, a
    module-level global, a policy's own persistent store or memory, a cache,
    ``numpy``'s global RNG or any RNG other than stdlib ``random`` -- carries
    what an earlier call's replays saw at their future ticks into a LATER
    call.  That can contaminate the later call's NATURAL trace, not only its
    control trace, even for patterns that are clean within one call (such as
    a store loaded privately at construction and written back while
    running).  Only the stdlib ``random`` module is reset between calls.  Do
    not trust a multi-checkpoint repair sequence to be leak-free unless the
    policy is provably free of any state that survives a call.

    The factory is called exactly twice when a suffix is replayed and never
    otherwise.  ``witness["policy_isolation"]`` records what was done; it
    describes mitigations, it does not certify isolation.
    """

    # Restore the caller's stdlib RNG state however this call ends, so the
    # draws made by this call's replays cannot shift a later call.
    rng_state_before_call = random.getstate()
    try:
        return _repair_body(kernel_snapshot, corrected_state_patch, repair_policy, max_actions)
    finally:
        random.setstate(rng_state_before_call)


def _repair_body(
    kernel_snapshot: Mapping[str, Any] | None,
    corrected_state_patch: Mapping[str, Any] | None,
    repair_policy: RepairPolicyFactory | None,
    max_actions: int | None,
) -> tuple[str, list[dict[str, Any]] | None, list[dict[str, Any]] | None, dict[str, Any]]:
    """The body of ``_repair``; only ever called through it (RNG restore)."""

    if kernel_snapshot is None and corrected_state_patch is None:
        return REPAIR_NOT_APPLICABLE, None, None, {"reason": "no_agent_state_supplied"}
    if kernel_snapshot is None or corrected_state_patch is None:
        raise ValueError("Repair needs both kernel_snapshot and corrected_state_patch")
    if repair_policy is None or max_actions is None:
        raise ValueError("Repair needs repair_policy and max_actions to re-run the suffix")
    _require_policy_factory(repair_policy)
    # Round-trip through a real kernel so both replays start from one
    # validated, independent copy of the parent state.
    parent = NaturalKernel.from_snapshot(kernel_snapshot).snapshot()
    if not isinstance(corrected_state_patch, Mapping) or not corrected_state_patch:
        raise ValueError("corrected_state_patch must be a nonempty mapping")
    historical = sorted(_HISTORICAL_STATE & set(corrected_state_patch))
    if historical:
        raise ValueError("Repair cannot rewrite historical kernel state: " + ", ".join(historical))
    unsupported = sorted(set(corrected_state_patch) - _REPAIRABLE_STATE)
    if unsupported:
        raise ValueError("Repair may only correct the agent read cache, not: " + ", ".join(unsupported))
    evictions = corrected_state_patch["read"]
    if not isinstance(evictions, Mapping) or not evictions:
        raise ValueError("A read correction must name at least one cached query")
    for query_id, value in evictions.items():
        if value is not None:
            raise ValueError(
                "Repair only evicts a provably wrong cache entry (value None); "
                "content must be re-acquired by the replayed agent"
            )
        if query_id not in parent["read"]:
            raise ValueError(f"Repair target {query_id!r} was never consumed by the agent")
    errors = {query_id: _cache_error(parent, query_id) for query_id in sorted(evictions)}
    if all(reason is None for reason in errors.values()):
        return REPAIR_NOT_APPLICABLE, None, None, {
            "reason": "no_provably_wrong_agent_state",
            "checked": sorted(errors),
        }
    unproven = [query_id for query_id, reason in errors.items() if reason is None]
    if unproven:
        raise ValueError("Repair would change agent state that is not provably wrong: " + ", ".join(unproven))
    # A repair must never report APPLIED while some OTHER cache entry is also
    # provably wrong but was left uncorrected -- that would still leave
    # leaked/incorrect content reachable in the "corrected" agent state
    # (adversarial-review B3). Scan every cached entry, not only the ones the
    # caller named, and refuse rather than silently leaving the rest behind.
    other_wrong = sorted(
        query_id
        for query_id in parent["read"]
        if query_id not in evictions and _cache_error(parent, query_id) is not None
    )
    if other_wrong:
        raise ValueError(
            "Other cached entries are also provably wrong and were not named for "
            "eviction, so this repair would still leave incorrect agent state behind: "
            + ", ".join(other_wrong)
        )
    if parent["stopped"] or parent["expired"]:
        return REPAIR_NOT_APPLICABLE, None, None, {"reason": "terminal_snapshot_has_no_suffix"}
    corrected = deepcopy(parent)
    for query_id in errors:
        del corrected["read"][query_id]
    if {key: value for key, value in corrected.items() if key != "read"} != {
        key: value for key, value in parent.items() if key != "read"
    }:
        raise RuntimeError("Repair changed kernel state outside the agent read cache")
    # Best-effort isolation of the two replays (see _repair).  Build both
    # policies before any replay runs, so within this call neither
    # construction can see this call's replay writes (e.g. a memory store
    # loaded at construction).  Writes from an EARLIER call are not excluded.
    natural_policy = _fresh_policy(repair_policy)
    control_policy = _fresh_policy(repair_policy)
    same_object = _same_policy_object(natural_policy, control_policy)
    shared_plain_function = same_object and natural_policy is control_policy and (
        _is_plain_function_without_own_state(natural_policy)
    )
    if same_object and not shared_plain_function:
        raise ValueError(
            "repair_policy factory returned the same policy object for both replays; "
            "it must build a new, independent policy on every call"
        )
    # Natural replay first: within this call, nothing this call's control
    # replay observes can have reached the natural trace through shared
    # in-process state (state left by an earlier call still can).  Rewind the
    # stdlib RNG so each replay starts from the same random state; _repair
    # restores the pre-call state afterwards.
    rng_state = random.getstate()
    natural_trace = replay_suffix(corrected, natural_policy, max_actions=max_actions)
    random.setstate(rng_state)
    control_trace = replay_suffix(parent, control_policy, max_actions=max_actions)
    witness = {
        "evicted": {
            query_id: {"reason": reason, "cached_content_sha256": _digest(parent["read"][query_id])}
            for query_id, reason in errors.items()
        },
        "snapshot_clock": parent["clock"],
        "prefix_action_count": len(parent["actions"]),
        "parent_snapshot_sha256": _digest(parent),
        "corrected_snapshot_sha256": _digest(corrected),
        "sources_sha256": _digest(parent["sources"]),
        "action_prefix_sha256": _digest(parent["actions"]),
        "max_actions": max_actions,
        "traces_differ": natural_trace != control_trace,
        # What was done to keep the replays apart.  Best effort only: this
        # records the mitigations applied, it does not certify isolation.
        "policy_isolation": {
            "guarantee": "best_effort_in_process_not_guaranteed",
            "policies_built_before_any_replay": True,
            "build_order": ["natural", "control"],
            "replay_order": ["natural", "control"],
            "same_policy_object": same_object,
            # False does NOT mean the policies are independent: distinct
            # objects can drive one shared stateful agent underneath (e.g.
            # ``lambda: (lambda s: agent(s))`` or
            # ``functools.partial(agent.__call__)``).
            "same_policy_object_false_rules_out_shared_state": False,
            "same_object_allowed_as_plain_function": shared_plain_function,
            "stdlib_random_rewound_between_replays": True,
            "stdlib_random_restored_after_call": True,
            # Within this call a leak through shared state can only flow from
            # the natural replay into the control trace.  Across calls the
            # direction is unconstrained: state left by an earlier call can
            # reach this call's natural trace.
            "residual_leak_direction": "within_call_natural_to_control_across_calls_unconstrained",
            "cross_call_isolation": False,
        },
    }
    return REPAIR_APPLIED, natural_trace, control_trace, witness


def apply_intervention(
    records: Iterable[EvidenceRecord | Mapping[str, Any]],
    intervention: str,
    *,
    target_start: int,
    target_end: int,
    as_of: int | None = None,
    kernel_snapshot: Mapping[str, Any] | None = None,
    corrected_state_patch: Mapping[str, Any] | None = None,
    repair_policy: RepairPolicyFactory | None = None,
    max_actions: int | None = None,
) -> InterventionResult:
    """Apply one declared intervention without changing the parent in place.

    The four keyword-only agent-state arguments are used by ``repair`` only
    (see ``_repair``); passing any of them to another intervention is an
    error rather than being silently ignored.

    ``repair_policy`` is a *factory*, not a policy: a zero-argument callable
    that builds a new ``NaturalPolicy`` each time it is called.  This
    replaces the earlier contract, which took one policy object and reused
    it for both repair replays (control and natural).  Both replays
    legitimately run the clock past the snapshot, so a policy that keeps
    state (for example an LLM-agent wrapper with conversation history) could
    carry what it saw at one replay's future ticks into the other replay.

    ISOLATION IS BEST EFFORT, NOT A GUARANTEE.  Do not claim
    future-leak-safety for a stateful policy on the strength of this API.
    The replays are separated only if the two policies share NO mutable
    state at all, including process-global state.  What repair does
    (details in ``_repair``; recorded in ``repair_witness["policy_isolation"]``):

    * calls the factory twice, before either replay runs;
    * runs the natural replay first, so within one call state shared with
      the control policy cannot leak that call's control-replay future into
      its natural trace -- but it CAN still leak the natural replay's
      future into the control trace;
    * rejects one object (or bound methods of one object) serving both
      replays, except a plain function with no closure, defaults or
      attributes (what ``lambda: my_function`` returns).  Passing this
      check (``same_policy_object: False``) does NOT show the policies are
      independent: ``lambda: (lambda s: agent(s))`` or
      ``functools.partial(agent.__call__)`` give distinct objects that
      drive one shared stateful ``agent``;
    * rewinds the stdlib ``random`` module to the same state before each
      replay and restores the caller's state when the call ends.  Other
      global RNGs (``numpy.random``, framework seeds) are not touched.

    Every protection above holds within ONE call only.  State that outlives
    a call (class attributes, module globals, a policy's persistent store,
    ``numpy``'s global RNG) can contaminate a LATER repair call's natural
    trace, e.g. on the next checkpoint of the same episode; see ``_repair``.

    What it cannot detect: two distinct policy objects that share mutable
    state underneath.  Each of these still leaks between the replays of one
    call, and across calls:

    * a mutable class attribute (``class P: memory = []``), including when
      the class itself is passed as the factory;
    * a mutable default argument (``def __init__(self, memory=[])``);
    * a container closed over by the factory or by the policy function;
    * a module-level global, a cache, a file or database the policy writes
      to while it runs;
    * any global RNG other than stdlib ``random``.

    Deferred, not implemented: running each replay in a forked process
    would close the in-process patterns (not state held on a remote
    server), and deep-copying each built policy would close some
    instance-held sharing but breaks policies holding locks or network
    clients.

    Safe: a policy class whose ``__init__`` builds all of its state fresh
    and holds no reference to anything that outlives the instance, passed as
    ``lambda: MyPolicy(config)`` where ``config`` is read-only::

        class MyPolicy:
            def __init__(self, config):
                self.config = config      # read-only settings
                self.history = []         # built fresh per instance
                self.rng = random.Random(config.seed)  # private RNG

    UNSAFE (leaks between replays although every call returns a new
    object)::

        shared_history = []
        repair_policy = lambda: MyPolicy(history=shared_history)

    A stateless plain function may be passed as ``lambda: my_function``; it
    is only safe if it reads no mutable global state.

    Passing a policy itself (the old contract) raises ``TypeError``: a
    policy needs its ``public_state`` argument, so it cannot be called as a
    factory.  The check runs as soon as agent state is supplied, before any
    replay, so it fails even where the repair would otherwise be
    ``NOT_APPLICABLE``.  A factory that returns something that is not
    callable raises ``TypeError``; one that returns the same non-function
    object twice raises ``ValueError``.
    """

    parent = [row.to_dict() if isinstance(row, EvidenceRecord) else dict(row) for row in records]
    if not parent:
        raise ValueError("An intervention needs a nonempty parent stream")
    if intervention != "repair" and any(
        value is not None for value in (kernel_snapshot, corrected_state_patch, repair_policy, max_actions)
    ):
        raise ValueError("Agent-state arguments are only meaningful for repair")
    repair_status: str | None = None
    natural_trace: list[dict[str, Any]] | None = None
    control_trace: list[dict[str, Any]] | None = None
    repair_witness: dict[str, Any] | None = None
    changed: list[str] = []
    qualification_records = parent
    held = ["target_start", "target_end", "content", "issued_at"]
    if intervention == "identity_repeat":
        # Identity-repeat is the no-op control: the parent evidence stream is
        # replayed exactly, while the intervention label remains available to
        # the paired analysis.  Appending a row would silently change the
        # information set and invalidate the intended sham.
        child = deepcopy(parent)
        changed = []
        held.remove("content")
        # Preserve the exact parent input while still exposing the duplicate
        # arrival that the qualification audit would observe.  The duplicate
        # is a diagnostic event, not a second source row in the child state.
        qualification_records = child + [deepcopy(parent[-1])]
    elif intervention == "same_origin_duplicate":
        child = deepcopy(parent)
        duplicate = deepcopy(parent[-1])
        duplicate["source_revision"] = duplicate["source_revision"] + "-mirror"
        duplicate["relation_status"] = "duplicate"
        child.append(duplicate)
        changed = ["stream_length", "source_revision", "relation_status"]
        held.remove("content")
    elif intervention == "matched_sham":
        child = deepcopy(parent) + [deepcopy(parent[-1])]
        child[-1].setdefault("content", {})["length_sham"] = "matched"
        child[-1]["source_revision"] = child[-1]["source_revision"] + "-sham"
        child[-1]["relation_status"] = "duplicate"
        changed = ["stream_length", "content.length_sham", "source_revision"]
    elif intervention == "withhold":
        child = deepcopy(parent[:-1])
        changed = ["stream_length", "last_arrival_withheld"]
    elif intervention == "delay":
        child = deepcopy(parent)
        child[-1]["available_at"] = (child[-1].get("available_at") or 0) + 86_400_000_000
        changed = ["available_at"]
    elif intervention == "repair":
        child = deepcopy(parent)
        if len(child) < 2:
            raise ValueError("Repair needs a parent and a later record")
        # Repair is an agent-state operation, not a source rewrite.  The
        # evidence stream and its timestamps remain byte-for-byte unchanged;
        # the state correction and the paired suffix re-runs are carried in
        # the repair-only result fields.
        repair_status, natural_trace, control_trace, repair_witness = _repair(
            kernel_snapshot, corrected_state_patch, repair_policy, max_actions
        )
        if repair_status == REPAIR_APPLIED:
            changed = ["agent_state.read." + query_id for query_id in repair_witness["evicted"]]
            held = held + ["kernel.sources", "kernel.actions_prefix", "kernel.clock"]
    else:
        raise ValueError(f"Unknown intervention: {intervention}")
    if intervention != "identity_repeat":
        qualification_records = child
    qualification = qualify_stream(
        qualification_records, target_start=target_start, target_end=target_end, as_of=as_of
    )
    return InterventionResult(
        intervention,
        child,
        changed,
        held,
        [row.to_dict() for row in qualification],
        status=repair_status,
        natural_trace=natural_trace,
        control_trace=control_trace,
        repair_witness=repair_witness,
    )
