"""Natural delivery-layer intervention for the v21 synthetic probe.

The base roster and public catalogue stay fixed.  An arm may only change the
result of retrieving a declared query until a delivery release time.  This is
separate from records-only ``withhold`` because both arms execute a kernel
suffix from the same parent state.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .natural_track_v18 import NaturalAction, NaturalKernel


class DeliveryKernel:
    def __init__(self, parent_snapshot: Mapping[str, Any], *, blocked_until: Mapping[str, int] | None = None):
        self.kernel = NaturalKernel.from_snapshot(parent_snapshot)
        self.blocked_until = {str(k): int(v) for k, v in (blocked_until or {}).items()}
        if any(v < self.kernel.clock for v in self.blocked_until.values()):
            raise ValueError("delivery release cannot precede the common prefix clock")

    def public_state(self) -> dict[str, Any]:
        # Delivery rules are evaluator-side and never appear in the actor view.
        return self.kernel.public_state()

    def step(self, action: NaturalAction) -> dict[str, Any]:
        # The blocked branch records an evaluator-side unavailable result
        # without delegating to NaturalKernel.step(). Enforce the same clock
        # and terminal contract before appending to the action log.
        if self.kernel.stopped:
            raise ValueError("No action is allowed after STOP")
        if self.kernel.expired:
            raise ValueError("No action is allowed after deadline; kernel is terminal")
        if action.at != self.kernel.clock or action.at > self.kernel.deadline:
            raise ValueError("Action clock does not match environment")
        if self.kernel.clock >= self.kernel.deadline and action.kind != "STOP":
            raise ValueError("Deadline reached; only STOP is allowed")
        if action.kind == "RETRIEVE" and action.query_id in self.blocked_until:
            release = self.blocked_until[action.query_id]
            if self.kernel.clock < release:
                if action.query_id not in self.kernel._visible_query_ids():
                    raise ValueError("Query is not currently visible")
                result = {"status": "unavailable", "query_id": action.query_id}
                self.kernel.actions.append(
                    deepcopy({"action": action.kind, "at": action.at, "result": result})
                )
                return deepcopy(result)
        return self.kernel.step(action)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.kernel.snapshot())


def run_delivery_probe(parent_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Run no-op, expose, withhold and delay suffixes from one parent."""
    actions = [
        NaturalAction("RETRIEVE", parent_snapshot["clock"], query_id="q1"),
        NaturalAction("UPDATE", parent_snapshot["clock"], probability=0.8),
        NaturalAction("STOP", parent_snapshot["clock"]),
    ]
    arms = {}
    for arm, blocked in (
        ("noop", {}),
        ("expose", {}),
        ("withhold", {"q1": parent_snapshot["clock"] + 10}),
    ):
        child = DeliveryKernel(parent_snapshot, blocked_until=blocked)
        trace = []
        for action in actions:
            result = child.step(action)
            trace.append({"action": action.kind, "at": action.at, "query_id": action.query_id, "result": result})
        arms[arm] = {
            "trace": trace,
            "catalogue": parent_snapshot.get("target") and NaturalKernel.from_snapshot(parent_snapshot).public_state()["catalogue"],
            "post_snapshot": child.snapshot(),
        }
    return {
        "schema": "disastertrace.v21.delivery_intervention.v1",
        "parent_snapshot": deepcopy(parent_snapshot),
        "arms": arms,
        "parent_untouched": NaturalKernel.from_snapshot(parent_snapshot).snapshot() == parent_snapshot,
        "catalogue_equal": arms["noop"]["catalogue"] == arms["withhold"]["catalogue"],
        "withhold_changes_delivery_only": arms["noop"]["trace"][0]["result"] != arms["withhold"]["trace"][0]["result"],
    }
