"""Frozen development frequencies; no calibration guarantee after acquisition."""

from __future__ import annotations

import json

from .evidence import evidence_features, taf_features


def horizon_bucket(target_start, issue):
    hours = (target_start - issue) / 3_600_000_000
    if hours < 0:
        raise ValueError("Forecast target precedes issuance")
    return "0-3" if hours <= 3 else "3-6" if hours <= 6 else "6-12" if hours <= 12 else "12+"


def feature_key(target, candidate, query_ids=(), disclosed=None):
    threshold = target["threshold"]
    if candidate is None or candidate.get("projection_status") == "unavailable":
        return json.dumps([threshold, "no_taf"], separators=(",", ":"))
    taf = taf_features(candidate["projection"], threshold)
    values = [
        threshold,
        horizon_bucket(target["physical_start"], candidate["issued_at"]),
        taf["prevailing"],
        taf["conditional"],
        taf["has_conditionals"],
    ]
    if disclosed is not None:
        evidence = evidence_features(query_ids, disclosed, threshold)
        values += [evidence["read"], evidence["low"], evidence["not_low"], evidence["unresolved"]]
    return json.dumps(values, separators=(",", ":"))


def predict(bank, target, candidate, query_ids=(), disclosed=None):
    keys = []
    if disclosed:
        keys.append(feature_key(target, candidate, query_ids, disclosed))
    keys.append(feature_key(target, candidate))
    keys.append(json.dumps([target["threshold"], "pooled"], separators=(",", ":")))
    for key in keys:
        row = bank["cells"].get(key)
        if row is not None and (row["n"] >= bank["minimum_cell_n"] or key == keys[-1]):
            probability = (row["positive"] + 1) / (row["n"] + 2)
            if "post_calibration" in bank:
                from .regional_calibration import apply_monotone

                family = "evidence" if disclosed else "base"
                probability = apply_monotone(
                    bank["post_calibration"][str(target["threshold"])][family], probability
                )
            return {
                "probability": probability,
                "cell_key": key,
                "n": row["n"],
                "mapping_version": bank["mapping_version"],
                "kind": "research_calibrated_taf_projection",
            }
    raise ValueError("Frozen bank has no threshold-level fallback")
