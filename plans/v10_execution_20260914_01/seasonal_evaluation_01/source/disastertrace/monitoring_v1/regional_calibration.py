"""Weighted monotone calibration on a separately purged historical period."""

import math


def fit_monotone(rows):
    counts = {}
    for probability, outcome, weight in rows:
        if (
            not math.isfinite(probability)
            or not 0 <= probability <= 1
            or outcome not in (0, 1)
            or not math.isfinite(weight)
            or weight <= 0
        ):
            raise ValueError("Invalid calibration row")
        cell = counts.setdefault(probability, [0.0, 0.0])
        cell[0] += weight * outcome
        cell[1] += weight
    if not counts:
        raise ValueError("Calibration requires observed targets")
    blocks = []
    for probability, (positive, n) in sorted(counts.items()):
        # One Laplace pair per distinct raw probability, before weighted PAV.
        blocks.append(
            {"lower": probability, "upper": probability, "positive": positive + 1, "weight": n + 2}
        )
        while (
            len(blocks) >= 2
            and blocks[-2]["positive"] / blocks[-2]["weight"]
            > blocks[-1]["positive"] / blocks[-1]["weight"]
        ):
            right = blocks.pop()
            left = blocks[-1]
            left.update(
                upper=right["upper"],
                positive=left["positive"] + right["positive"],
                weight=left["weight"] + right["weight"],
            )
    return [
        {"lower": b["lower"], "upper": b["upper"], "value": b["positive"] / b["weight"]}
        for b in blocks
    ]


def apply_monotone(blocks, probability):
    if not blocks or not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Invalid monotone probability mapping")
    for block in blocks:
        if probability <= block["upper"]:
            return block["value"]
    return blocks[-1]["value"]
