"""Read-only raw-cell and post-map attribution for the frozen v1 estimator."""

from .calibration import feature_key, predict
from .regional_calibration import apply_monotone
from .targets import canonical_hash


def trace_prediction(bank, target, candidate, query_ids=(), disclosed=None):
    raw_bank = {k: v for k, v in bank.items() if k != "post_calibration"}
    raw = predict(raw_bank, target, candidate, query_ids, disclosed)
    base = predict(raw_bank, target, candidate)
    actual = predict(bank, target, candidate, query_ids, disclosed)
    family = "evidence" if disclosed else "base"
    maps = bank.get("post_calibration", {}).get(str(target["threshold"]))

    def mapped(p, name):
        return apply_monotone(maps[name], p) if maps else p

    four = {"base_raw_base_map": mapped(base["probability"], "base"),
            "base_raw_evidence_map": mapped(base["probability"], "evidence"),
            "evidence_raw_base_map": mapped(raw["probability"], "base"),
            "evidence_raw_evidence_map": mapped(raw["probability"], "evidence")}
    same = raw["cell_key"] == base["cell_key"]
    relevant = [q for q in query_ids if disclosed and q in disclosed]
    return {"schema": "disastertrace.calibration_attribution.v1", "bank_sha256": canonical_hash(bank),
            "cell_key": raw["cell_key"], "base_cell_key": base["cell_key"],
            "requested_evidence_key": feature_key(target, candidate, query_ids, disclosed) if disclosed else None,
            "n": raw["n"], "positive": bank["cells"][raw["cell_key"]]["positive"],
            "raw_probability": raw["probability"], "base_raw_probability": base["probability"],
            "post_probability": actual["probability"], "calibration_family": family,
            "four_cells": four, "same_raw_cell_as_base": same,
            "mapping_only_numeric_change": same and actual["probability"] != four["base_raw_base_map"],
            "relevant_disclosed_ids": relevant,
            "unrelated_disclosed_ids": sorted(set(disclosed or {}) - set(query_ids)),
            "no_taf": candidate is None or candidate.get("projection_status") == "unavailable",
            "historical_prediction_modified": False}
