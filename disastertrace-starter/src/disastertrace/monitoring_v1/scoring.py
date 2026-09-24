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


def _missing_increments(group, missing):
    """Legacy missing-outcome bound increments for one target group.

    Returns ``(lower, upper)`` increments in the exact order the historical
    implementation added them, so re-summing them is bit-identical.
    """

    observed = {row["outcome"] for row in group if row["outcome"] is not None}
    if len(observed) > 1:
        # Legacy only: a conflicting target was bounded with an independent
        # Y per missing row.  Such groups never reach the qualified score.
        return [
            (
                sum(
                    _score_weight(row.get("score_weight", 1.0))
                    * min(
                        (_prob(row["base"]) - y) ** 2
                        - (_prob(row["prediction"]) - y) ** 2
                        for y in (0, 1)
                    )
                    for row in missing
                ),
                sum(
                    _score_weight(row.get("score_weight", 1.0))
                    * max(
                        (_prob(row["base"]) - y) ** 2
                        - (_prob(row["prediction"]) - y) ** 2
                        for y in (0, 1)
                    )
                    for row in missing
                ),
            )
        ]
    if observed:
        # A settled checkpoint identifies the shared target outcome for
        # every unresolved checkpoint in the same trajectory.
        y = next(iter(observed))
        increments = []
        for row in missing:
            base, prediction = _prob(row["base"]), _prob(row["prediction"])
            gain = (base - y) ** 2 - (prediction - y) ** 2
            weight = _score_weight(row.get("score_weight", 1.0))
            increments.append((weight * gain, weight * gain))
        return increments
    # Compute the two completions jointly.  Choosing a different Y
    # independently at each checkpoint would describe an impossible
    # target and produce bounds that are too wide.
    endpoints = [
        sum(
            _score_weight(row.get("score_weight", 1.0))
            * ((_prob(row["base"]) - y) ** 2 - (_prob(row["prediction"]) - y) ** 2)
            for row in missing
        )
        for y in (0, 1)
    ]
    return [(min(endpoints), max(endpoints))]


def _mean(values):
    return (
        sum(value * weight for value, weight in values) / sum(weight for _, weight in values)
        if values and sum(weight for _, weight in values) > 0
        else None
    )


def _score_block(view):
    gains = view["gains"]
    return {
        "base_brier": _mean(view["base_losses"]),
        "system_brier": _mean(view["losses"]),
        "net_realized_gain": _mean(gains),
        "g_plus": _mean([(max(gain, 0), weight) for gain, weight in gains]),
        "g_minus": _mean([(max(-gain, 0), weight) for gain, weight in gains]),
        "full_population_gain_bounds": [
            view["lower"] / view["weight"],
            view["upper"] / view["weight"],
        ]
        if view["weight"] > 0
        else None,
    }


def brier_report(rows):
    """Brier report whose top-level score excludes settled-Y conflicts.

    A target's checkpoints (across every method) are one trajectory over one
    binary target event.  A target group whose settled rows disagree about Y
    is unidentifiable, so all of its rows -- settled and missing -- are
    excluded from every top-level score field.  The historical all-row numbers
    remain available only under ``legacy_all_rows_including_conflicts``, which
    is audit-only and must not feed a primary experiment.
    """

    rows = list(rows)
    if len({r["opportunity_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate opportunity")
    total_weight = 0.0
    strata = defaultdict(lambda: {"opportunities": 0, "settled": 0})
    # If target_id is supplied, missing rows must share one hidden Y; legacy
    # rows without target_id retain the old per-opportunity semantics.
    target_groups = defaultdict(list)
    parsed = []
    explicit_target_ids = set()
    fallback_opportunity_ids = set()
    # Pass 1: validate every row (same checks and order as before) and group
    # rows by target before any score is accumulated.
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
        # Strata describe roster coverage of recorded outcomes, not the score.
        strata[key]["opportunities"] += 1
        if y is not None:
            strata[key]["settled"] += 1
        target_id = row.get("target_id")
        if target_id is not None and not target_id:
            # A present-but-falsy target_id (0 or "") is an intentional label that
            # `if target_id` would silently discard, collapsing it into the
            # opportunity_id fallback as if it were never grouped at all -- reject
            # explicitly instead of silently ignoring a group membership signal.
            raise ValueError(
                "target_id must not be an empty/zero placeholder; omit the key "
                "entirely (or use None) for a single-opportunity group"
            )
        if target_id:
            group_key = str(target_id)
            explicit_target_ids.add(group_key)
        else:
            group_key = str(row["opportunity_id"])
            fallback_opportunity_ids.add(group_key)
        target_groups[group_key].append(row)
        parsed.append((group_key, base, prediction, weight, y))
    colliding = explicit_target_ids & fallback_opportunity_ids
    if colliding:
        raise ValueError(
            f"target_id collides with another row's opportunity_id, which would "
            f"silently merge two unrelated groups: {sorted(colliding)!r}"
        )
    inconsistent = {
        group_key
        for group_key, group in target_groups.items()
        if len({row["outcome"] for row in group if row["outcome"] is not None}) > 1
    }

    def new_view():
        return {"gains": [], "base_losses": [], "losses": [], "lower": 0.0, "upper": 0.0,
                "weight": 0.0, "rows": 0, "missing_target_groups": 0}

    legacy, qualified = new_view(), new_view()
    # Pass 2: settled rows in row order.  Rows of an inconsistent group enter
    # only the legacy view.
    for group_key, base, prediction, weight, y in parsed:
        views = (legacy,) if group_key in inconsistent else (legacy, qualified)
        for view in views:
            view["weight"] += weight
            view["rows"] += 1
        if y is None:
            continue
        base_loss, loss = (base - y) ** 2, (prediction - y) ** 2
        gain = base_loss - loss
        for view in views:
            view["base_losses"].append((base_loss, weight))
            view["losses"].append((loss, weight))
            view["gains"].append((gain, weight))
            view["lower"] += weight * gain
            view["upper"] += weight * gain

    # Pass 3: missing-outcome bounds per target group, in first-seen order.
    # A group that has missing rows AND conflicting settled rows has no
    # single identifiable Y to broadcast or jointly complete, so its missing
    # contribution is excluded from the qualified bounds as well.
    for group_key, group in target_groups.items():
        missing = [row for row in group if row["outcome"] is None]
        if not missing:
            continue
        views = (legacy,) if group_key in inconsistent else (legacy, qualified)
        for view in views:
            view["missing_target_groups"] += 1
        for lower, upper in _missing_increments(group, missing):
            for view in views:
                view["lower"] += lower
                view["upper"] += upper

    if total_weight <= 0:
        raise ValueError("Score weights must have a positive total")

    n = len(rows)
    legacy_settled = len(legacy["gains"])
    qualified_settled = len(qualified["gains"])
    return {
        "opportunities": n,
        # Qualified counts: rows of inconsistent target groups are excluded,
        # so opportunities == settled + missing + inconsistent rows excluded.
        "settled": qualified_settled,
        "missing": qualified["rows"] - qualified_settled,
        "professional_baseline_opportunities": sum(
            r.get("baseline_kind") == "professional" for r in rows
        ),
        **_score_block(qualified),
        "score_weight_total": total_weight,
        "qualified_score_weight_total": qualified["weight"],
        "missing_target_groups": qualified["missing_target_groups"],
        "inconsistent_target_groups": len(inconsistent),
        "inconsistent_target_group_rows_excluded": n - qualified["rows"],
        "legacy_all_rows_including_conflicts": {
            "audit_only": True,
            "qualified": False,
            "note": "historical all-row numbers including unresolved settled-Y conflicts; "
            "never a primary or qualified score",
            "opportunities": n,
            "settled": legacy_settled,
            "missing": n - legacy_settled,
            **_score_block(legacy),
            "score_weight_total": legacy["weight"],
            "missing_target_groups": legacy["missing_target_groups"],
        },
        "strata": [
            dict(
                zip(("region", "period", "source", "quality", "maturity", "base_risk_decile"), key),
                **counts,
            )
            for key, counts in sorted(strata.items())
        ],
        "interpretation": "realized losses on common settled mask; bounds do not impute outcomes; no per-action no-harm guarantee",
    }
