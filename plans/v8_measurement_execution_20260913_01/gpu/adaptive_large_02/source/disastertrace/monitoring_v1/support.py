"""Logical support from disclosed product facts, never from evaluator labels."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float
    lower_closed: bool = True
    upper_closed: bool = True

    def __post_init__(self):
        if math.isnan(self.lower) or math.isnan(self.upper) or self.lower > self.upper:
            raise ValueError("Invalid interval bounds")
        if self.lower == self.upper and (not self.lower_closed or not self.upper_closed):
            raise ValueError("An empty interval must be represented as None")

    def intersect(self, other: Interval) -> Interval | None:
        lo, hi = max(self.lower, other.lower), min(self.upper, other.upper)
        lc = (self.lower < lo or self.lower_closed) and (other.lower < lo or other.lower_closed)
        uc = (self.upper > hi or self.upper_closed) and (other.upper > hi or other.upper_closed)
        if lo > hi or (lo == hi and not (lc and uc)):
            return None
        return Interval(lo, hi, lc, uc)

    def to_dict(self):
        # JSON cannot portably encode infinity as a number.
        def bound(x):
            return x if math.isfinite(x) else ("+inf" if x > 0 else "-inf")

        return {
            "lower": bound(self.lower),
            "upper": bound(self.upper),
            "lower_closed": self.lower_closed,
            "upper_closed": self.upper_closed,
        }


def classify(support: Interval | None, operator: str, threshold: float) -> str:
    if not math.isfinite(threshold) or operator not in {"lt", "le", "ge", "gt"}:
        raise ValueError("Unsupported predicate")
    if support is None:
        return "inconsistent"
    if operator == "lt":
        yes = support.upper < threshold or (support.upper == threshold and not support.upper_closed)
        no = support.lower >= threshold
    elif operator == "le":
        yes = support.upper <= threshold
        no = support.lower > threshold or (support.lower == threshold and not support.lower_closed)
    elif operator == "ge":
        yes = support.lower >= threshold
        no = support.upper < threshold or (support.upper == threshold and not support.upper_closed)
    else:
        yes = support.lower > threshold or (support.lower == threshold and not support.lower_closed)
        no = support.upper <= threshold
    return "supported" if yes else "refuted" if no else "undetermined"


def sum_intervals(intervals: Iterable[Interval | None]) -> Interval | None:
    values = list(intervals)
    if any(v is None for v in values):
        return None
    return Interval(
        sum(v.lower for v in values),
        sum(v.upper for v in values),
        all(v.lower_closed for v in values),
        all(v.upper_closed for v in values),
    )


@dataclass(frozen=True)
class EvidenceFact:
    series_id: str
    version: int
    released_at: int
    field: str
    units: str
    interval: Interval | None
    reference_kind: str
    support_assumption: str
    visible_information_scope: str
    support_rule_version: str
    valid_until: int | None = None

    def __post_init__(self):
        if (
            self.version < 0
            or not self.series_id
            or not self.units
            or not self.support_rule_version
        ):
            raise ValueError("Incomplete evidence identity")
        if self.reference_kind not in {
            "product_label",
            "measurement",
            "model_estimate",
            "evaluator_label",
            "raw_image",
        }:
            raise ValueError("Unknown reference kind")
        if self.visible_information_scope not in {"policy", "evaluator", "oracle_diagnostic"}:
            raise ValueError("Unknown information scope")
        if self.support_assumption not in {
            "product_exact",
            "bounded_measurement",
            "model_estimate",
            "annotation_reference",
            "coverage_only",
        }:
            raise ValueError("Unknown support assumption")

    @property
    def certified(self):
        return self.visible_information_scope == "policy" and (
            (self.reference_kind == "product_label" and self.support_assumption == "product_exact")
            or (
                self.reference_kind == "measurement"
                and self.support_assumption == "bounded_measurement"
            )
        )


def public_support(
    facts: Iterable[EvidenceFact], field: str, units: str, domain: Interval, at: int
) -> Interval | None:
    relevant = [f for f in facts if f.field == field and f.released_at <= at and f.certified]
    if any(f.units != units for f in relevant):
        raise ValueError("Units must be normalized by a declared provider rule")
    # Choose the current disclosed version before checking expiry; an expired
    # correction must not silently resurrect an earlier contradicted product.
    versions = {}
    for fact in relevant:
        versions[fact.series_id] = max(versions.get(fact.series_id, -1), fact.version)
    support = domain
    for fact in relevant:
        if fact.version != versions[fact.series_id] or (
            fact.valid_until is not None and at > fact.valid_until
        ):
            continue
        if fact.interval is None or support is None:
            return None
        support = support.intersect(fact.interval)
    return support


def area_support(
    weights: Mapping[str, float], products: Iterable[Mapping[str, Interval]]
) -> Interval | None:
    if any(not math.isfinite(w) or w <= 0 for w in weights.values()):
        raise ValueError("Cells require positive finite area weights")
    cells = {key: Interval(0, 1) for key in weights}
    for product in products:
        for key, value in product.items():
            if key not in cells or value.lower < 0 or value.upper > 1:
                raise ValueError("Unsupported spatial cell or fraction")
            cells[key] = cells[key].intersect(value) if cells[key] is not None else None
    return sum_intervals(
        None
        if cells[key] is None
        else Interval(
            weights[key] * cells[key].lower,
            weights[key] * cells[key].upper,
            cells[key].lower_closed,
            cells[key].upper_closed,
        )
        for key in cells
    )
