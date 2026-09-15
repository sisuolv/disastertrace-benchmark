"""Shared support validation; probability and postprocessing remain separate."""

import math
from datetime import datetime, timezone

DAY = 86400_000_000


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def event_values(row, products):
    target = row["target"]
    start, end, cutoff = target["physical_start"], target["physical_end"], row["cutoff"]
    if (
        target["units"] != "C"
        or any(type(t) is not int for t in (start, end, cutoff))
        or start % DAY or end % DAY or end <= start or cutoff >= start
    ):
        raise ValueError("Absolute future UTC days in Celsius are required")
    variables = {
        "daily_min_2m_temperature": ("forecast_min_members_C", 1),
        "daily_max_2m_temperature": ("forecast_max_members_C", 1),
        "min_of_3_daily_max_2m_temperature": ("forecast_max_members_C", 3),
        "max_of_3_daily_max_2m_temperature": ("forecast_max_members_C", 3),
    }
    if target["variable"] not in variables:
        raise ValueError("Unqualified temperature variable")
    field, days = variables[target["variable"]]
    if end - start != days * DAY:
        raise ValueError("Variable and fixed target duration disagree")
    if target["event_operator"] not in {"ge", "lt"} or not finite_number(target["threshold"]):
        raise ValueError("Unqualified temperature endpoint")
    dates = [p["target_date"] for p in products]
    if not products or len(dates) != len(set(dates)):
        raise ValueError("Unique daily products are required")
    for product in products:
        if type(product["day_index"]) is not int or product["day_index"] < 1:
            raise ValueError("Day0 is excluded from fixed future extrema")
    by_date = dict(zip(dates, products, strict=True))
    try:
        values = [
            by_date[datetime.fromtimestamp(t / 1_000_000, timezone.utc).date().isoformat()][field]
            for t in range(start, end, DAY)
        ]
    except (KeyError, OverflowError, OSError) as exc:
        raise ValueError("Requested physical target is not fully covered") from exc
    if any(not isinstance(v, list) or not v or not all(map(finite_number, v)) for v in values):
        raise ValueError("Finite complete temperature members required")
    if len({len(v) for v in values}) != 1:
        raise ValueError("Same member dimensions must survive the entire product")
    return values
