"""Typed Natural Track kernel for offline active-evidence tests."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping


ACTION_KINDS = {"RETRIEVE", "WAIT", "UPDATE", "STOP"}


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
        self.sources = {source.query_id: source for source in sources}
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
                result = {"status": "unavailable", "query_id": action.query_id, "available_at": source.available_at}
            else:
                self.read[action.query_id] = source.content
                result = {"status": "available", "query_id": action.query_id, "content": source.content}
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
        self.actions.append({"action": action.kind, "at": action.at, "result": result})
        return result

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
