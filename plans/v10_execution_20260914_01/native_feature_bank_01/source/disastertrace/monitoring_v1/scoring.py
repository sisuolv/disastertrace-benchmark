"""All-opportunity outcome-side scoring; no feedback to policy state."""

from __future__ import annotations

import math
from collections import defaultdict


def _prob(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("Invalid probability")
    return float(value)


def generic_missing_gain_bounds(settlement_fraction, settled_mean_gain):
    if not 0 <= settlement_fraction <= 1 or not -1 <= settled_mean_gain <= 1:
        raise ValueError("Invalid Brier coverage or gain")
    center = settlement_fraction * settled_mean_gain
    missing = 1 - settlement_fraction
    return center - missing, center + missing


def brier_report(rows):
    rows = list(rows)
    if len({r["opportunity_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate opportunity")
    gains, base_losses, losses = [], [], []
    lower_total = upper_total = 0.0
    strata = defaultdict(lambda: {"opportunities": 0, "settled": 0})
    for row in rows:
        base, prediction = _prob(row["base"]), _prob(row["prediction"])
        y = row["outcome"]
        if y is not None and (type(y) is not int or y not in (0, 1)):
            raise ValueError("Missing outcomes must be None; binary outcomes must be 0 or 1")
        key = (
            row.get("region", "unspecified"),
            row.get("period", "unspecified"),
            row.get("source", "unspecified"),
            row.get("quality", "unspecified"),
            row.get("maturity", "unspecified"),
            min(9, int(base * 10)),
        )
        strata[key]["opportunities"] += 1
        if y is None:
            endpoints = [(base - value) ** 2 - (prediction - value) ** 2 for value in (0, 1)]
            lower_total += min(endpoints)
            upper_total += max(endpoints)
            continue
        strata[key]["settled"] += 1
        base_loss, loss = (base - y) ** 2, (prediction - y) ** 2
        gain = base_loss - loss
        base_losses.append(base_loss)
        losses.append(loss)
        gains.append(gain)
        lower_total += gain
        upper_total += gain

    def mean(values):
        return sum(values) / len(values) if values else None

    n = len(rows)
    return {
        "opportunities": n,
        "settled": len(gains),
        "missing": n - len(gains),
        "professional_baseline_opportunities": sum(
            r.get("baseline_kind") == "professional" for r in rows
        ),
        "base_brier": mean(base_losses),
        "system_brier": mean(losses),
        "net_realized_gain": mean(gains),
        "g_plus": mean([max(g, 0) for g in gains]),
        "g_minus": mean([max(-g, 0) for g in gains]),
        "full_population_gain_bounds": [lower_total / n, upper_total / n] if n else None,
        "strata": [
            dict(
                zip(("region", "period", "source", "quality", "maturity", "base_risk_decile"), key),
                **counts,
            )
            for key, counts in sorted(strata.items())
        ],
        "interpretation": "realized losses on common settled mask; bounds do not impute outcomes; no per-action no-harm guarantee",
    }
