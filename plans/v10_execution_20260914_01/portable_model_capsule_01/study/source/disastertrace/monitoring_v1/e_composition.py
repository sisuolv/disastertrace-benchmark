"""Composition of model estimates; never a repair of historical model answers."""

from ..forecast_task.common import strict_json
from .audit_contracts import require_exact_ids

TRUTHS = {"true", "false", "unknown", "conflict"}


def aggregate(values):
    values = list(values)
    if not values or any(type(v) is not str or v not in TRUTHS for v in values):
        raise ValueError("A nonempty registered set of truth strings is required")
    return ("conflict" if "conflict" in values else "true" if "true" in values
            else "false" if all(v == "false" for v in values) else "unknown")


def compose(raw, query_ids):
    answer = strict_json(raw)
    if not isinstance(answer, dict) or set(answer) != {"slots", "fact_truth"}:
        raise ValueError("Invalid slotwise response fields")
    if not isinstance(answer["slots"], dict):
        raise ValueError("Slot mapping required")  # noqa: TRY004 - uniform invalid-response contract.
    require_exact_ids(query_ids, answer["slots"], "model slots")
    reported = answer["fact_truth"]
    if type(reported) is not str or reported not in TRUTHS:
        raise ValueError("Invalid reported aggregate")
    return {"schema": "disastertrace.model_slot_composition.v1", "slots": answer["slots"],
            "reported_aggregate": reported, "composed_aggregate": aggregate(answer["slots"].values()),
            "reference_kind": "model_estimate", "support_assumption": "model_estimate",
            "support_rule_version": "finite_registered_exists_conflict_first.v1"}
