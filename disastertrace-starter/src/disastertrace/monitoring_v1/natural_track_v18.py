"""Typed Natural Track kernel for offline active-evidence tests."""

from __future__ import annotations

from dataclasses import dataclass
import math
from copy import deepcopy
from typing import Any, Callable, Mapping


ACTION_KINDS = {"RETRIEVE", "WAIT", "UPDATE", "STOP"}
SNAPSHOT_SCHEMA = "disastertrace.v18.natural_kernel_snapshot.v1"
_SNAPSHOT_KEYS = {"schema", "sources", "clock", "deadline", "read", "stopped", "expired", "actions"}
_SOURCE_KEYS = {"query_id", "available_at", "content", "public_schedule"}
_ACTION_LOG_KEYS = {"action", "at", "result"}


@dataclass(frozen=True)
class NaturalAction:
    kind: str
    at: int
    query_id: str | None = None
    wake_at: int | None = None
    probability: float | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kind, str)
            or self.kind not in ACTION_KINDS
            or isinstance(self.at, bool)
            or not isinstance(self.at, int)
        ):
            raise ValueError("Invalid natural action")
        if self.kind == "RETRIEVE":
            if not isinstance(self.query_id, str) or not self.query_id:
                raise ValueError("RETRIEVE needs query_id")
            if self.wake_at is not None or self.probability is not None:
                raise ValueError("RETRIEVE cannot carry wake_at or probability")
        elif self.kind == "WAIT":
            if self.query_id is not None or self.probability is not None:
                raise ValueError("WAIT cannot carry query_id or probability")
            if (
                isinstance(self.wake_at, bool)
                or not isinstance(self.wake_at, int)
                or self.wake_at <= self.at
            ):
                raise ValueError("WAIT needs a future wake_at")
        elif self.kind == "UPDATE":
            if self.query_id is not None or self.wake_at is not None:
                raise ValueError("UPDATE cannot carry query_id or wake_at")
            if (
                self.probability is None
                or isinstance(self.probability, bool)
                or not isinstance(self.probability, (int, float))
                or not math.isfinite(self.probability)
                or not 0 <= self.probability <= 1
            ):
                raise ValueError("UPDATE needs a probability in [0,1]")
        else:
            fields = [
                name
                for name, value in (
                    ("query_id", self.query_id),
                    ("wake_at", self.wake_at),
                    ("probability", self.probability),
                )
                if value is not None
            ]
            if fields:
                raise ValueError("STOP cannot carry " + ", ".join(fields))


@dataclass(frozen=True)
class NaturalSource:
    query_id: str
    available_at: int
    content: Mapping[str, Any]
    public_schedule: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.query_id, str) or not self.query_id:
            raise ValueError("NaturalSource needs a query_id")
        if (
            isinstance(self.available_at, bool)
            or not isinstance(self.available_at, int)
            or self.available_at < 0
        ):
            raise ValueError("NaturalSource available_at must be a non-negative integer")
        if not isinstance(self.content, Mapping):
            raise ValueError("NaturalSource content must be a mapping")
        if not isinstance(self.public_schedule, bool):
            raise ValueError("NaturalSource public_schedule must be a bool")


class NaturalKernel:
    """A deterministic active-evidence environment without outcome access."""

    def __init__(self, sources: list[NaturalSource], *, start: int, deadline: int):
        if (
            isinstance(start, bool)
            or isinstance(deadline, bool)
            or not isinstance(start, int)
            or not isinstance(deadline, int)
            or start >= deadline
        ):
            raise ValueError("Natural kernel clock and deadline must be increasing integers")
        if len({source.query_id for source in sources}) != len(sources):
            raise ValueError("Invalid natural source roster")
        # Freeze the source payload at environment construction.  A caller
        # mutating its original dict must not rewrite the evidence history.
        self.sources = {
            source.query_id: NaturalSource(
                source.query_id,
                source.available_at,
                deepcopy(dict(source.content)),
                source.public_schedule,
            )
            for source in sources
        }
        self.clock = start
        self.deadline = deadline
        self.read: dict[str, Mapping[str, Any]] = {}
        self.stopped = False
        self.expired = False
        self.actions: list[dict[str, Any]] = []

    def step(self, action: NaturalAction) -> dict[str, Any]:
        if self.stopped:
            raise ValueError("No action is allowed after STOP")
        if self.expired:
            raise ValueError("No action is allowed after deadline; kernel is terminal")
        if action.at != self.clock or action.at > self.deadline:
            raise ValueError("Action clock does not match environment")
        if self.clock >= self.deadline and action.kind != "STOP":
            raise ValueError("Deadline reached; only STOP is allowed")
        if action.kind == "RETRIEVE":
            source = self.sources.get(action.query_id)
            if source is None:
                raise ValueError("Unknown query")
            if source.available_at > self.clock:
                # An undisclosed future arrival time is a hidden oracle.  Only
                # a source explicitly contracted as a public schedule (e.g. a
                # published synoptic issuance time) may reveal when it will
                # next become available; everything else returns "unavailable"
                # with no timing hint at all.
                result = {"status": "unavailable", "query_id": action.query_id}
                if source.public_schedule:
                    result["available_at"] = source.available_at
            else:
                content = deepcopy(dict(source.content))
                self.read[action.query_id] = deepcopy(content)
                result = {"status": "available", "query_id": action.query_id, "content": content}
        elif action.kind == "WAIT":
            self.clock = min(action.wake_at, self.deadline)
            if self.clock >= self.deadline:
                self.expired = True
                result = {"status": "expired", "clock": self.clock, "deadline": self.deadline}
            else:
                result = {"status": "advanced", "clock": self.clock}
        elif action.kind == "UPDATE":
            result = {"status": "updated", "probability": action.probability, "read_query_ids": sorted(self.read)}
        else:
            self.stopped = True
            result = {"status": "stopped", "clock": self.clock}
        self.actions.append(deepcopy({"action": action.kind, "at": action.at, "result": result}))
        return deepcopy(result)

    def public_state(self) -> dict[str, Any]:
        return {
            "clock": self.clock,
            "deadline": self.deadline,
            "read_query_ids": sorted(self.read),
            "stopped": self.stopped,
            "expired": self.expired,
            "terminal": self.stopped or self.expired,
            "action_count": len(self.actions),
        }

    def snapshot(self) -> dict[str, Any]:
        """Return the complete kernel state as an independent deep copy.

        The snapshot carries the frozen source history, the consumed clock
        (the budget proxy), the agent's read cache, the terminal flags and the
        full action log.  Nothing in it aliases the live kernel.
        """

        return deepcopy(
            {
                "schema": SNAPSHOT_SCHEMA,
                "sources": [
                    {
                        "query_id": source.query_id,
                        "available_at": source.available_at,
                        "content": dict(source.content),
                        "public_schedule": source.public_schedule,
                    }
                    for source in self.sources.values()
                ],
                "clock": self.clock,
                "deadline": self.deadline,
                "read": {query_id: dict(content) for query_id, content in self.read.items()},
                "stopped": self.stopped,
                "expired": self.expired,
                "actions": self.actions,
            }
        )

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "NaturalKernel":
        """Rebuild an independent kernel exactly as it was when snapshotted.

        ``__init__`` is bypassed on purpose: it only admits a fresh kernel
        (``start < deadline``), whereas a snapshot may be expired.  The
        structural and clock invariants that ``step`` maintains are checked
        here instead.  The read cache is the agent's own state and is not
        required to agree with the sources; a wrong cache is exactly what a
        repair has to be able to represent and then prove wrong.
        """

        if (
            not isinstance(snapshot, Mapping)
            or set(snapshot) != _SNAPSHOT_KEYS
            or snapshot["schema"] != SNAPSHOT_SCHEMA
        ):
            raise ValueError("Not a natural kernel snapshot")
        data = deepcopy(dict(snapshot))
        clock, deadline = data["clock"], data["deadline"]
        if (
            any(isinstance(value, bool) or not isinstance(value, int) for value in (clock, deadline))
            or clock > deadline
        ):
            raise ValueError("Snapshot clock must be an integer no later than its deadline")
        stopped, expired = data["stopped"], data["expired"]
        if (
            not isinstance(stopped, bool)
            or not isinstance(expired, bool)
            or (stopped and expired)
            or expired != (clock >= deadline)
        ):
            raise ValueError("Snapshot terminal flags are inconsistent with its clock")
        rows = data["sources"]
        if not isinstance(rows, list) or any(
            not isinstance(row, Mapping) or set(row) != _SOURCE_KEYS for row in rows
        ):
            raise ValueError("Snapshot sources are malformed")
        sources = [
            NaturalSource(row["query_id"], row["available_at"], row["content"], row["public_schedule"])
            for row in rows
        ]
        if len({source.query_id for source in sources}) != len(sources):
            raise ValueError("Invalid natural source roster")
        read = data["read"]
        if not isinstance(read, Mapping) or any(
            not isinstance(query_id, str) or not isinstance(content, Mapping)
            for query_id, content in read.items()
        ):
            raise ValueError("Snapshot read cache is malformed")
        actions = data["actions"]
        if not isinstance(actions, list) or any(
            not isinstance(entry, Mapping)
            or set(entry) != _ACTION_LOG_KEYS
            or entry["action"] not in ACTION_KINDS
            or isinstance(entry["at"], bool)
            or not isinstance(entry["at"], int)
            or entry["at"] > clock
            or not isinstance(entry["result"], Mapping)
            for entry in actions
        ):
            raise ValueError("Snapshot action log is malformed")
        # A snapshot's clock must actually be reachable by replaying its own
        # action log, not merely later than every entry's `at`. Without this,
        # a caller could hand-build a snapshot whose clock is inflated past
        # what its logged history supports -- letting a "repaired" replay
        # skip WAIT steps and reach data that should still be in the future
        # relative to the actions actually taken (adversarial-review B2).
        running_clock = actions[0]["at"] if actions else None
        expired_mid_log = False
        for entry in actions:
            if expired_mid_log:
                raise ValueError("Snapshot action log has an action after an expiring WAIT")
            if entry["at"] != running_clock:
                raise ValueError("Snapshot action log's clock is inconsistent with its own history")
            if entry["action"] == "WAIT":
                result = entry["result"]
                result_clock = result.get("clock") if isinstance(result, Mapping) else None
                if (
                    isinstance(result_clock, bool)
                    or not isinstance(result_clock, int)
                    or result_clock < running_clock
                ):
                    raise ValueError("Snapshot action log has a malformed WAIT result")
                running_clock = result_clock
                if isinstance(result, Mapping) and result.get("status") == "expired":
                    expired_mid_log = True
        if actions and running_clock != clock:
            raise ValueError("Snapshot clock does not match its own action log")
        stop_positions = [index for index, entry in enumerate(actions) if entry["action"] == "STOP"]
        if stop_positions != ([len(actions) - 1] if stopped else []):
            raise ValueError("Snapshot STOP history is inconsistent with its stopped flag")
        kernel = cls.__new__(cls)
        kernel.sources = {source.query_id: source for source in sources}
        kernel.clock = clock
        kernel.deadline = deadline
        kernel.read = {query_id: dict(content) for query_id, content in read.items()}
        kernel.stopped = stopped
        kernel.expired = expired
        kernel.actions = [dict(entry) for entry in actions]
        return kernel


NaturalPolicy = Callable[[dict[str, Any]], NaturalAction]


def replay_suffix(
    snapshot: Mapping[str, Any], policy: NaturalPolicy, *, max_actions: int
) -> list[dict[str, Any]]:
    """Genuinely re-run a policy from a snapshot until the kernel is terminal.

    Each iteration asks ``policy`` for one action given only
    ``public_state()``, applies it through ``NaturalKernel.step`` and records
    that step's actual result in the kernel's own action-log shape
    (``{"action", "at", "result"}``).  A policy that has not reached STOP or
    the deadline within ``max_actions`` steps raises ``ValueError``: a
    truncated suffix is not a completed continuation and must not be
    compared as one.  A terminal snapshot has no suffix and yields ``[]``.
    """

    if isinstance(max_actions, bool) or not isinstance(max_actions, int) or max_actions < 1:
        raise ValueError("max_actions must be a positive integer")
    kernel = NaturalKernel.from_snapshot(snapshot)
    trace: list[dict[str, Any]] = []
    while not (kernel.stopped or kernel.expired):
        if len(trace) >= max_actions:
            raise ValueError("Policy did not reach a terminal state within max_actions")
        action = policy(kernel.public_state())
        if not isinstance(action, NaturalAction):
            raise TypeError("A natural policy must return a NaturalAction")
        result = kernel.step(action)
        trace.append({"action": action.kind, "at": action.at, "result": result})
    return trace
