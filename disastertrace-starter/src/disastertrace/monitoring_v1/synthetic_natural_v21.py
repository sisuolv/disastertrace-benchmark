"""Fully synthetic Natural/active evidence experiment for v21.

All source text, target identity and evaluator outcomes in this module are
hand-authored fixtures.  The actor only receives the public kernel state and
retrieved content.  The evaluator outcome is attached after the trace.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .active_policy_v21 import ContentAwareSyntheticPolicy
from .natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource


METHODS = ("fixed", "no_extra", "source_rr", "source_hash", "active")


def target_card() -> dict[str, Any]:
    base = {
        "entity": "SYNTHETIC-STATION",
        "variable": "visibility",
        "threshold": 5000.0,
        "unit": "m",
        "comparison": "<",
        "observation_rule": "terminal synthetic observation in target window",
        "target_start": 100,
        "target_end": 200,
        "contract_version": "synthetic.v0",
    }
    base["contract_hash"] = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return base


def _sources(signal: float, *, id_prefix: str = "q") -> list[NaturalSource]:
    return [
        NaturalSource(f"{id_prefix}0", 0, {"visibility_m": signal, "source_role": "initial_signal"}),
        NaturalSource(f"{id_prefix}1", 0, {"visibility_m": 3000.0, "source_role": "followup_a"}),
        NaturalSource(f"{id_prefix}2", 0, {"visibility_m": 9000.0, "source_role": "followup_b"}),
    ]


def _execute(kernel: NaturalKernel, policy: ContentAwareSyntheticPolicy, *, max_actions: int = 12) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    while not kernel.public_state()["terminal"]:
        if len(trace) >= max_actions:
            raise ValueError("synthetic policy did not terminate")
        state = kernel.public_state()
        action = policy(state)
        if not isinstance(action, NaturalAction):
            raise TypeError("synthetic policy returned a non-NaturalAction")
        result = kernel.step(action)
        trace.append({"action": action.kind, "at": action.at, "query_id": action.query_id, "result": result})
    return trace


def run_case(case_id: str, signal: float, *, id_prefix: str = "q", outcome: int) -> dict[str, Any]:
    target = target_card()
    kernel = NaturalKernel(_sources(signal, id_prefix=id_prefix), start=0, deadline=20, target=target)
    policy = ContentAwareSyntheticPolicy(threshold_m=target["threshold"])
    trace = _execute(kernel, policy)
    read = deepcopy(kernel.public_state()["read"])
    # F sees actor-produced extracted features only.  It never receives the
    # evaluator outcome or source roster.
    extracted = {
        query_id: {"visibility_m": content.get("visibility_m")}
        for query_id, content in read.items()
    }
    last = list(extracted.values())[-1]
    probability = 0.8 if float(last["visibility_m"]) < target["threshold"] else 0.2
    retrievals = [row["query_id"] for row in trace if row["action"] == "RETRIEVE"]
    return {
        "case_id": case_id,
        "target": target,
        "source_ids": sorted(read),
        "trace": trace,
        "actor_read": read,
        "actor_extraction": extracted,
        "f_input": deepcopy(extracted),
        "probability": probability,
        "evaluator_y": outcome,
        "brier": (probability - outcome) ** 2,
        "retrieval_sequence": retrievals,
        "outcome_accessed_by_actor": False,
        "model_calls": 0,
    }


def _common_f(extracted: Mapping[str, Mapping[str, Any]], threshold: float) -> float:
    """The one forecast map shared by every synthetic method.

    A method changes which legal evidence it delivers to this map.  The map
    itself never sees the source roster, target outcome, or evaluator state.
    Empty input has the fixed prior probability.
    """

    if not extracted:
        return 0.5
    last = list(extracted.values())[-1]
    visibility = last.get("visibility_m")
    if isinstance(visibility, bool) or not isinstance(visibility, (int, float)):
        return 0.5
    return 0.8 if float(visibility) < threshold else 0.2


def run_method_case(
    case_id: str,
    signal: float,
    *,
    method: str,
    outcome: int,
    id_prefix: str = "q",
) -> dict[str, Any]:
    """Run one method on the same source roster and feed the same F.

    ``active`` delegates to the policy path used by :func:`run_case`.  The
    other methods are evaluator-controlled fixed query schedules that never
    inspect the outcome; they differ only in evidence delivered before F.
    """

    if method not in METHODS:
        raise ValueError(f"unknown synthetic method: {method}")
    if method == "active":
        result = run_case(case_id, signal, id_prefix=id_prefix, outcome=outcome)
        result["method"] = method
        return result
    target = target_card()
    kernel = NaturalKernel(_sources(signal, id_prefix=id_prefix), start=0, deadline=20, target=target)
    schedules = {
        "fixed": (),
        "no_extra": (f"{id_prefix}0",),
        "source_rr": (f"{id_prefix}0", f"{id_prefix}1"),
        # A predeclared source-hash arm chooses the other follow-up without
        # inspecting the first content. It is a deterministic non-adaptive
        # control, not a claim about a production hash function.
        "source_hash": (f"{id_prefix}0", f"{id_prefix}2"),
    }
    trace: list[dict[str, Any]] = []
    for query_id in schedules[method]:
        action = NaturalAction("RETRIEVE", kernel.clock, query_id=query_id)
        result = kernel.step(action)
        trace.append({"action": action.kind, "at": action.at, "query_id": query_id, "result": result})
    extracted = {
        query_id: {"visibility_m": content.get("visibility_m")}
        for query_id, content in kernel.public_state()["read"].items()
    }
    probability = _common_f(extracted, target["threshold"])
    update = NaturalAction("UPDATE", kernel.clock, probability=probability)
    trace.append({"action": update.kind, "at": update.at, "query_id": None, "result": kernel.step(update)})
    stop = NaturalAction("STOP", kernel.clock)
    trace.append({"action": stop.kind, "at": stop.at, "query_id": None, "result": kernel.step(stop)})
    return {
        "case_id": case_id,
        "method": method,
        "target": target,
        "source_ids": sorted(extracted),
        "trace": trace,
        "actor_read": kernel.public_state()["read"],
        "actor_extraction": extracted,
        "f_input": deepcopy(extracted),
        "probability": probability,
        "evaluator_y": outcome,
        "brier": (probability - outcome) ** 2,
        "retrieval_sequence": [row["query_id"] for row in trace if row["action"] == "RETRIEVE"],
        "outcome_accessed_by_actor": False,
        "model_calls": 0,
    }


def run_experiment(out: Path | None = None) -> dict[str, Any]:
    low = run_case("signal_low", 4000.0, outcome=1)
    high = run_case("signal_high", 9000.0, outcome=0)
    renamed = run_case("signal_low_renamed", 4000.0, id_prefix="z", outcome=1)
    artifact = {
        "schema": "disastertrace.v21.synthetic_natural_active.v1",
        "evidence_role": "SYNTHETIC_PROTOCOL_CHECK",
        "synthetic": True,
        "empirical": False,
        "cases": [low, high, renamed],
        "active_gate": {
            "status": "PASS" if low["retrieval_sequence"][1] != high["retrieval_sequence"][1] else "FAIL",
            "content_dependent_second_query": low["retrieval_sequence"][1] != high["retrieval_sequence"][1],
            # The fixture changes only opaque query handles.  The policy must
            # therefore choose the correspondingly renamed follow-up handle.
            "id_renaming_preserves_decision_rule": renamed["retrieval_sequence"][1] == "z1",
        },
        "lineage_contract": "query -> returned content -> actor extraction -> F input -> probability -> evaluator score",
        "claims": {
            "engineering": "The synthetic actor consumes retrieved content and terminates through UPDATE/STOP.",
            "method": "The next query changes when the legal first observation changes.",
            "research": "This is protocol evidence only; it does not establish real-weather value or novelty.",
        },
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact
