"""Predeclared sensitivity candidates; the historical per-cell PAV is unchanged."""

import math


def fit_fixed_prior(rows, *, prior_mass=2.0, prior_probability=.5):
    if not math.isfinite(prior_mass) or prior_mass < 0 or not 0 <= prior_probability <= 1:
        raise ValueError("Invalid total calibration prior")
    counts = {}
    for p, y, w in rows:
        if (not math.isfinite(p) or not 0 <= p <= 1 or y not in (0, 1)
                or not math.isfinite(w) or w <= 0):
            raise ValueError("Invalid weighted calibration observation")
        bucket = counts.setdefault(p, [[], []])
        bucket[0].append(y*w); bucket[1].append(w)
    if not counts:
        raise ValueError("Calibration observations required")
    total = math.fsum(w for _, ws in counts.values() for w in ws)
    blocks = []
    for p, (positives, weights) in sorted(counts.items()):
        n = math.fsum(weights)
        local_prior = prior_mass*n/total
        blocks.append({"lower": p, "upper": p, "positive": math.fsum(positives)+local_prior*prior_probability,
                       "weight": n+local_prior})
        while len(blocks) > 1 and blocks[-2]["positive"]/blocks[-2]["weight"] > blocks[-1]["positive"]/blocks[-1]["weight"]:
            right = blocks.pop(); left = blocks[-1]
            left.update(upper=right["upper"], positive=left["positive"]+right["positive"],
                        weight=left["weight"]+right["weight"])
    return [{"lower": b["lower"], "upper": b["upper"], "value": b["positive"]/b["weight"]} for b in blocks]


def coherent_cdf(probabilities, information_ids):
    """Equal-weight isotonic projection in increasing threshold order, no labels."""
    values, identities = list(probabilities), list(information_ids)
    if not values or len(values) != len(identities) or len(set(identities)) != 1 or not identities[0]:
        raise ValueError("Nested probabilities require identical information and support identities")
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError("Finite complete probability vector required")
    blocks = []
    for p in values:
        blocks.append([float(p), 1])
        while len(blocks) > 1 and blocks[-2][0]/blocks[-2][1] > blocks[-1][0]/blocks[-1][1]:
            right = blocks.pop(); blocks[-1][0] += right[0]; blocks[-1][1] += right[1]
    return [total/n for total, n in blocks for _ in range(n)]
