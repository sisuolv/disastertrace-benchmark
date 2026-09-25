"""Small deterministic active policy used by the v21 synthetic gate.

This is an experiment fixture, not a weather model.  It deliberately consumes
only the v21 public observation view.  In particular, it has no source roster,
gold outcome, evaluator object, or module-level mutable memory.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .natural_track_v18 import NaturalAction


def _visible_ids(state: Mapping[str, Any]) -> list[str]:
    rows = state.get("catalogue", [])
    if not isinstance(rows, list):
        raise ValueError("active policy requires a public catalogue")
    ids = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) - {"query_id", "available_at"}:
            raise ValueError("malformed public catalogue row")
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("catalogue query_id must be nonempty")
        ids.append(query_id)
    return sorted(set(ids))


class ContentAwareSyntheticPolicy:
    """Select a follow-up source from a retrieved signal.

    The first query is the first public handle solely to obtain an observation.
    The *next* query is chosen from the remaining public handles according to
    the observed visibility value.  Renaming/permuting handles therefore
    changes the emitted query IDs but does not change the decision rule.
    """

    def __init__(self, *, threshold_m: float = 5000.0):
        self.threshold_m = float(threshold_m)

    def __call__(self, state: Mapping[str, Any]) -> NaturalAction:
        state = deepcopy(dict(state))
        clock = state.get("clock")
        if isinstance(clock, bool) or not isinstance(clock, int):
            raise ValueError("active policy requires an integer clock")
        if state.get("terminal"):
            raise ValueError("policy cannot act on a terminal state")
        catalogue = _visible_ids(state)
        read = state.get("read")
        if not isinstance(read, Mapping):
            raise ValueError("active policy requires the v21 read view")
        if not read:
            if not catalogue:
                return NaturalAction("STOP", clock)
            return NaturalAction("RETRIEVE", clock, query_id=catalogue[0])

        observed = list(read.values())[-1]
        if not isinstance(observed, Mapping):
            raise ValueError("retrieved content must be a mapping")
        visibility = observed.get("visibility_m")
        remaining = [query_id for query_id in catalogue if query_id not in read]
        # One follow-up is enough for this diagnostic.  A policy that reads
        # every source would still be valid software, but would make the
        # evidence-dependent allocation question uninformative.
        if remaining and len(read) < 2:
            if isinstance(visibility, (int, float)) and not isinstance(visibility, bool):
                index = 0 if float(visibility) < self.threshold_m else min(1, len(remaining) - 1)
            else:
                index = 0
            return NaturalAction("RETRIEVE", clock, query_id=remaining[index])

        if state.get("action_count", 0) > len(read):
            return NaturalAction("STOP", clock)
        probability = 0.8 if isinstance(visibility, (int, float)) and float(visibility) < self.threshold_m else 0.2
        return NaturalAction("UPDATE", clock, probability=probability)


def run_policy(snapshot: Mapping[str, Any], policy: ContentAwareSyntheticPolicy, *, max_actions: int = 12):
    """Delegate replay to the kernel, keeping this adapter free of hidden state."""
    from .natural_track_v18 import replay_suffix

    return replay_suffix(snapshot, policy, max_actions=max_actions)
