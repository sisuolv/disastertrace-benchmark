"""Require independent agreement and pair only the same absolute valid time."""

from collections import defaultdict
from itertools import pairwise

from . import parser_a, parser_b


def agree(raw):
    first, second = parser_a.parse(raw), parser_b.parse(raw)
    if first != second:
        raise ValueError("independent parser disagreement")
    return first


def revision_pairs(products):
    groups = defaultdict(list)
    for product in products:
        for row in product["forecasts"]:
            groups[product["storm_id"], row["valid_at"]].append((product, row))
    pairs = []
    for (storm, valid), versions in sorted(groups.items()):
        versions.sort(key=lambda value: value[0]["issued_at"])
        for (older, a), (newer, b) in pairwise(versions):
            if older["issued_at"] >= newer["issued_at"]:
                raise ValueError("same-valid-time versions need distinct ordered issue times")
            pairs.append(
                {
                    "storm_id": storm,
                    "valid_at": valid,
                    "older_advisory": older["advisory_number"],
                    "newer_advisory": newer["advisory_number"],
                    "older_issued_at": older["issued_at"],
                    "newer_issued_at": newer["issued_at"],
                    "older": a,
                    "newer": b,
                    "wind_change_kt": b["max_sustained_wind_kt"] - a["max_sustained_wind_kt"]
                    if a["max_sustained_wind_kt"] is not None
                    and b["max_sustained_wind_kt"] is not None
                    else None,
                }
            )
    return pairs


def latest_covering(products, storm_id, valid_at, issue_cutoff):
    matches = [
        {"advisory_number": p["advisory_number"], "issued_at": p["issued_at"], "row": row}
        for p in products
        if p["storm_id"] == storm_id and p["issued_at"] <= issue_cutoff
        for row in p["forecasts"]
        if row["valid_at"] == valid_at
    ]
    return max(matches, key=lambda value: value["issued_at"]) if matches else None
