"""A declared model-estimate interface to the existing frozen count-based fuser."""

import json

from .audit_contracts import require_exact_ids
from .calibration import feature_key
from .e_composition import aggregate
from .regional_calibration import apply_monotone


def predict_from_slots(bank, target, candidate, query_ids, acquired_ids, slots, *, family=None):
    require_exact_ids(query_ids, slots, "F model slots")
    aggregate(slots.values())
    if len(acquired_ids) != len(set(acquired_ids)) or not set(acquired_ids) <= set(query_ids):
        raise ValueError("Invalid acquired slot identities")
    if any(slots[q] != "unknown" for q in query_ids if q not in acquired_ids):
        raise ValueError("An unread slot cannot be promoted to an observed fact")
    base_key = feature_key(target, candidate)
    keys = []
    if acquired_ids:
        values = json.loads(base_key)
        if values[-1] != "no_taf":
            known = [slots[q] for q in acquired_ids]
            values += [
                len(known),
                known.count("true"),
                known.count("false"),
                known.count("unknown") + known.count("conflict"),
            ]
        keys.append(json.dumps(values, separators=(",", ":")))
    keys += [base_key, json.dumps([target["threshold"], "pooled"], separators=(",", ":"))]
    selected_family = family or ("evidence" if acquired_ids else "base")
    if selected_family not in {"base", "evidence"}:
        raise ValueError("Explicit frozen calibration family required")
    for key in keys:
        cell = bank["cells"].get(key)
        if cell is None or (cell["n"] < bank["minimum_cell_n"] and key != keys[-1]):
            continue
        raw = (cell["positive"] + 1) / (cell["n"] + 2)
        p = (
            apply_monotone(bank["post_calibration"][str(target["threshold"])][selected_family], raw)
            if "post_calibration" in bank
            else raw
        )
        return {
            "schema": "disastertrace.slot_estimate_forecast.v1",
            "probability": p,
            "raw_probability": raw,
            "cell_key": key,
            "calibration_family": selected_family,
            "reference_kind": "model_estimate",
            "aggregate_used_by_F": False,
            "bank_mapping_version": bank["mapping_version"],
            "scope": "existing frozen count mapping; no calibration guarantee for model errors",
        }
    raise ValueError("Frozen slot forecast bank has no pooled fallback")
