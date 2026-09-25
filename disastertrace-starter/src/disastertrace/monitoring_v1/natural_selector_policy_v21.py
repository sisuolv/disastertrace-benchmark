"""Public-catalogue selector adapter for the v21 Natural Track.

The adapter connects the already versioned selector priority and query-only
output contract to ``NaturalKernel``.  It has no source roster, outcome,
evaluator, or mutable cross-replay state.  The kernel remains responsible for
availability, entitlement, clock, and terminal checks.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping

from .natural_track_v18 import NaturalAction
from .public_query_selectors import query_priority
from .selector_contract_v2 import parse_query_only


SUPPORTED_SELECTORS = frozenset({"fixed_hash.v1", "round_robin_cycle.v1", "public_risk_age.v1"})


def _catalogue(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = state.get("catalogue")
    if not isinstance(rows, list):
        raise ValueError("Natural public state must contain a catalogue")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) - {"query_id", "available_at"}:
            raise ValueError("Malformed public catalogue row")
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or not query_id or query_id in seen:
            raise ValueError("Catalogue query IDs must be unique nonempty strings")
        if "available_at" in row and (isinstance(row["available_at"], bool) or not isinstance(row["available_at"], int)):
            raise ValueError("Catalogue available_at must be an integer")
        seen.add(query_id)
        result.append(dict(row))
    return result


class CatalogueSelectorPolicy:
    """Select public query handles under a fixed query budget.

    ``baseline_probability`` is a registered public prior supplied by the
    episode protocol.  It is not inferred from hidden source content.  The
    policy uses the selector module only on catalogue metadata and validates
    its ordered handles through ``selector_contract_v2`` before emitting the
    first query.  Forecasting is deliberately a small deterministic map used
    for protocol tests; it is not a weather model.
    """

    def __init__(
        self,
        *,
        selector_kind: str = "fixed_hash.v1",
        seed: int = 0,
        max_queries: int = 1,
        baseline_probability: float = 0.5,
        threshold_m: float = 5000.0,
    ) -> None:
        if selector_kind not in SUPPORTED_SELECTORS:
            raise ValueError("unsupported selector kind")
        if isinstance(max_queries, bool) or not isinstance(max_queries, int) or max_queries < 0:
            raise ValueError("max_queries must be a nonnegative integer")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed must be an integer")
        if isinstance(baseline_probability, bool) or not 0 <= float(baseline_probability) <= 1:
            raise ValueError("baseline_probability must be in [0,1]")
        self.selector_kind = selector_kind
        self.seed = seed
        self.max_queries = max_queries
        self.baseline_probability = float(baseline_probability)
        self.threshold_m = float(threshold_m)

    def _ordered_handles(self, state: Mapping[str, Any], rows: list[dict[str, Any]]) -> list[str]:
        target = state.get("target")
        if not isinstance(target, Mapping) or not isinstance(target.get("entity"), str):
            raise ValueError("v21 selector policy requires a public target entity")
        acquired = set(state.get("read_query_ids", []))
        common = {
            target["entity"]: {
                "entity": target["entity"],
                "baseline_probability": self.baseline_probability,
                "public_query_ids": [row["query_id"] for row in rows],
            }
        }
        tick = int(state.get("action_count", 0))
        ranked = sorted(
            rows,
            key=lambda row: query_priority(
                self.selector_kind,
                seed=self.seed,
                tick=tick,
                acquired=len(acquired),
                target_id=target["entity"],
                query_id=row["query_id"],
                common=common,
                available_at=int(row.get("available_at", state["clock"])),
            ),
        )
        ordered = [row["query_id"] for row in ranked if row["query_id"] not in acquired]
        parsed = parse_query_only(json.dumps({"query_order": ordered}), ordered)
        return parsed["query_order"]

    def _forecast(self, state: Mapping[str, Any]) -> float:
        read = state.get("read")
        if not isinstance(read, Mapping) or not read:
            return self.baseline_probability
        latest = list(read.values())[-1]
        if not isinstance(latest, Mapping):
            return self.baseline_probability
        visibility = latest.get("visibility_m")
        if isinstance(visibility, bool) or not isinstance(visibility, (int, float)):
            return self.baseline_probability
        return 0.8 if float(visibility) < self.threshold_m else 0.2

    def __call__(self, public_state: Mapping[str, Any]) -> NaturalAction:
        state = deepcopy(dict(public_state))
        clock = state.get("clock")
        if isinstance(clock, bool) or not isinstance(clock, int):
            raise ValueError("selector policy requires an integer clock")
        if state.get("terminal"):
            raise ValueError("selector policy cannot act on a terminal state")
        rows = _catalogue(state)
        read = state.get("read")
        if not isinstance(read, Mapping):
            raise ValueError("selector policy requires the v21 read view")
        if len(read) < self.max_queries:
            handles = self._ordered_handles(state, rows)
            if handles:
                return NaturalAction("RETRIEVE", clock, query_id=handles[0])
        if state.get("action_count", 0) == len(read):
            return NaturalAction("UPDATE", clock, probability=self._forecast(state))
        return NaturalAction("STOP", clock)
