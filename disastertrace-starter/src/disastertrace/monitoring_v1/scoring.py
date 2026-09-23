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


def _score_weight(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("Invalid score weight")
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
    total_weight = 0.0
    strata = defaultdict(lambda: {"opportunities": 0, "settled": 0})
    # A target's checkpoints are one trajectory over one binary target event.
    # If target_id is supplied, missing rows must therefore share one hidden Y;
    # legacy rows without target_id retain the old per-opportunity semantics.
    target_groups = defaultdict(list)
    for row in rows:
        base, prediction = _prob(row["base"]), _prob(row["prediction"])
        weight = _score_weight(row.get("score_weight", 1.0))
        total_weight += weight
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
        target_id = row.get("target_id")
        target_groups[str(target_id if target_id else row["opportunity_id"])].append(row)
        if y is None:
            continue
        strata[key]["settled"] += 1
        base_loss, loss = (base - y) ** 2, (prediction - y) ** 2
        gain = base_loss - loss
        base_losses.append((base_loss, weight))
        losses.append((loss, weight))
        gains.append((gain, weight))
        lower_total += weight * gain
        upper_total += weight * gain

    missing_target_groups = 0
    inconsistent_target_groups = 0
    for group in target_groups.values():
        missing = [row for row in group if row["outcome"] is None]
        if not missing:
            continue
        missing_target_groups += 1
        observed = {row["outcome"] for row in group if row["outcome"] is not None}
        if len(observed) > 1:
            # Older rosters may encode checkpoint-local outcomes.  Preserve
            # those rows as an explicit inconsistency and use independent
            # missing bounds until the roster is migrated to target-level Y.
            inconsistent_target_groups += 1
            lower_total += sum(
                _score_weight(row.get("score_weight", 1.0))
                * min(
                    (_prob(row["base"]) - y) ** 2
                    - (_prob(row["prediction"]) - y) ** 2
                    for y in (0, 1)
                )
                for row in missing
            )
            upper_total += sum(
                _score_weight(row.get("score_weight", 1.0))
                * max(
                    (_prob(row["base"]) - y) ** 2
                    - (_prob(row["prediction"]) - y) ** 2
                    for y in (0, 1)
                )
                for row in missing
            )
        elif observed:
            # A settled checkpoint identifies the shared target outcome for
            # every unresolved checkpoint in the same trajectory.
            y = next(iter(observed))
            for row in missing:
                base, prediction = _prob(row["base"]), _prob(row["prediction"])
                gain = (base - y) ** 2 - (prediction - y) ** 2
                weight = _score_weight(row.get("score_weight", 1.0))
                lower_total += weight * gain
                upper_total += weight * gain
        else:
            # Compute the two completions jointly.  Choosing a different Y
            # independently at each checkpoint would describe an impossible
            # target and produce bounds that are too wide.
            endpoints = [
                sum(
                    _score_weight(row.get("score_weight", 1.0))
                    * (
                    (_prob(row["base"]) - y) ** 2
                    - (_prob(row["prediction"]) - y) ** 2
                    )
                    for row in missing
                )
                for y in (0, 1)
            ]
            lower_total += min(endpoints)
            upper_total += max(endpoints)

    if total_weight <= 0:
        raise ValueError("Score weights must have a positive total")

    def mean(values):
        return (
            sum(value * weight for value, weight in values) / sum(weight for _, weight in values)
            if values and sum(weight for _, weight in values) > 0
            else None
        )

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
        "g_plus": mean([(max(gain, 0), weight) for gain, weight in gains]),
        "g_minus": mean([(max(-gain, 0), weight) for gain, weight in gains]),
        "full_population_gain_bounds": [lower_total / total_weight, upper_total / total_weight]
        if n
        else None,
        "score_weight_total": total_weight,
        "missing_target_groups": missing_target_groups,
        "inconsistent_target_groups": inconsistent_target_groups,
        "strata": [
            dict(
                zip(("region", "period", "source", "quality", "maturity", "base_risk_decile"), key),
                **counts,
            )
            for key, counts in sorted(strata.items())
        ],
        "interpretation": "realized losses on common settled mask; bounds do not impute outcomes; no per-action no-harm guarantee",
    }
