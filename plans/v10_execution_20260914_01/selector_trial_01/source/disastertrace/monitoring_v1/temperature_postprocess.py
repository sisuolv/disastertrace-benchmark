"""Frozen Gaussian EMOS marginals and rank-coupled whole temperature paths."""

import copy
import math
import statistics
from datetime import datetime, timezone

DAY = 86400_000_000


def validate_products(products):
    dates = [p["target_date"] for p in products]
    if len(dates) != len(set(dates)) or not products:
        raise ValueError("Unique daily products are required")
    sizes = set()
    for product in products:
        if type(product["day_index"]) is not int or product["day_index"] < 1:
            raise ValueError("Day0 is excluded from fixed future extrema")
        for field in ("forecast_min_members_C", "forecast_max_members_C"):
            values = product[field]
            sizes.add(len(values))
            if not values or any(type(v) not in (float, int) or not math.isfinite(v) for v in values):
                raise ValueError("Finite complete temperature members required")
    if len(sizes) != 1:
        raise ValueError("Same member dimensions must survive the entire product")


def event_probability(row, *, products=None):
    target = row["target"]
    start, end = target["physical_start"], target["physical_end"]
    if (target["units"] != "C" or type(start) is not int or type(end) is not int
            or start % DAY or end % DAY or end <= start or row["cutoff"] >= start):
        raise ValueError("Absolute future UTC days in Celsius are required")
    products = row["common"]["daily_products"] if products is None else products
    validate_products(products)
    by_date = {p["target_date"]: p for p in products}
    dates = [datetime.fromtimestamp(t/1_000_000, timezone.utc).date().isoformat() for t in range(start, end, DAY)]
    variable = target["variable"]
    field = "forecast_min_members_C" if variable == "daily_min_2m_temperature" else "forecast_max_members_C"
    try:
        values = [by_date[date][field] for date in dates]
    except KeyError as exc:
        raise ValueError("Requested physical target is not fully covered") from exc
    if variable in {"daily_min_2m_temperature", "daily_max_2m_temperature"} and len(values) == 1:
        members = values[0]
    elif variable == "min_of_3_daily_max_2m_temperature" and len(values) == 3:
        members = [min(path) for path in zip(*values, strict=True)]
    elif variable == "max_of_3_daily_max_2m_temperature" and len(values) == 3:
        members = [max(path) for path in zip(*values, strict=True)]
    else:
        raise ValueError("Variable and fixed target duration disagree")
    operator, threshold = target["event_operator"], target["threshold"]
    if operator not in {"ge", "lt"} or type(threshold) not in (float, int) or not math.isfinite(threshold):
        raise ValueError("Unqualified temperature endpoint")
    return sum(v >= threshold if operator == "ge" else v < threshold for v in members)/len(members)


def ecc_products(products, bank):
    """All days share original member identities; min/max repair is explicit."""
    validate_products(products)
    converted = copy.deepcopy(products)
    trace = {"minmax_projections": 0, "member_day_pairs": 0,
             "tie_rule": "stable original member index", "joint_calibration_guarantee": False}
    for product in converted:
        for variable, field in (("min", "forecast_min_members_C"), ("max", "forecast_max_members_C")):
            values = product[field]
            coefficients = bank[variable]
            mean = coefficients["a"]+coefficients["b"]*statistics.fmean(values)
            variance = math.exp(coefficients["log_c"])+math.exp(coefficients["log_d"])*statistics.pvariance(values)
            if not math.isfinite(mean) or not math.isfinite(variance) or variance <= 0:
                raise ValueError("Invalid frozen EMOS distribution")
            distribution = statistics.NormalDist(mean, math.sqrt(variance))
            ranks = sorted(range(len(values)), key=lambda i: (values[i], i))
            calibrated = [0.0]*len(values)
            for rank, member in enumerate(ranks):
                calibrated[member] = distribution.inv_cdf((rank+.5)/len(values))
            product[field] = calibrated
        for i, (lo, hi) in enumerate(zip(product["forecast_min_members_C"], product["forecast_max_members_C"], strict=True)):
            trace["member_day_pairs"] += 1
            if lo > hi:
                trace["minmax_projections"] += 1
                product["forecast_min_members_C"][i] = product["forecast_max_members_C"][i] = (lo+hi)/2
    return converted, trace
