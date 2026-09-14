"""Fresh native-text extraction and temperature F-only output contracts."""

import math
from datetime import datetime, timezone

from ..forecast_task.common import strict_json
from .native_feature_forecast import validate_claims

FEATURE_SYSTEM = """Extract native METAR report-label measurements from the lawfully supplied text. This is not physical truth or a future observation. Return exactly one JSON object with a slots object keyed by every supplied read query_id. Each slot has visibility, temperature_c, dewpoint_c. visibility is null or an object with lower, upper, lower_closed, upper_closed in metres. Use the string +inf for an unbounded upper endpoint. Preserve inequalities and censoring: P6SM means lower=9656.064, lower_closed=false, upper=+inf; M1/4SM has an open upper endpoint at 402.336. One statute mile is 1609.344 metres. Temperatures and dewpoints are degrees Celsius, M denotes minus, and missing fields are null. Use only the main routine observation before remarks/trends; TAF is a forecast, not a station observation. A missing or conflicting source slot has null fields. Do not fill unread slots. A bare JSON object or one whole JSON markdown fence is accepted; no other prose, duplicate keys, NaN or extra fields. Future outcomes are unavailable. The supplied professional forecast remains common information; you are only extracting the past report measurements."""

TEMPERATURE_SYSTEM = """Predict the probability of the supplied fixed future temperature event using the complete professional-source ensemble product. Use only the supplied information. The raw same-member ensemble fraction is a research baseline, not guaranteed to be calibrated; you may retain or revise it. Do not report today's state as the future outcome. All daily extrema are Celsius over the exact UTC day; day0 is excluded. A three-day hot spell means all three daily maxima are >=30C for the same member. A three-day ice spell means all three daily maxima are <0C for the same member. Never multiply daily marginal probabilities to obtain a joint member probability. Return exactly one JSON object with probability, a finite number from 0 to 1. Bare JSON or one whole JSON markdown fence is accepted, without other prose or extra fields. No outcome or post-cutoff observation is supplied."""


def output_json(raw):
    text = raw.strip()
    wrapped = False
    for start in ("```json\n", "```\n"):
        if text.startswith(start) and text.endswith("```"):
            text = text[len(start):-3].strip()
            wrapped = True
            break
    return strict_json(text), wrapped


def parse_features(raw, read_ids):
    value, wrapped = output_json(raw)
    if not isinstance(value, dict) or set(value) != {"slots"}:
        raise ValueError("Expected only native feature slots")
    validate_claims(value["slots"], dict.fromkeys(read_ids))
    return value["slots"], {"whole_json_fence": wrapped}


def parse_temperature(raw):
    value, wrapped = output_json(raw)
    if (not isinstance(value, dict) or set(value) != {"probability"}
            or type(value["probability"]) not in (int, float)
            or not math.isfinite(value["probability"]) or not 0 <= value["probability"] <= 1):
        raise ValueError("Expected one bounded future-event probability")
    return float(value["probability"]), {"whole_json_fence": wrapped}


def temperature_ensemble_probability(row):
    target, common = row["target"], row["common"]
    day_us = 86400_000_000
    if (target["units"] != "C" or target["physical_start"] <= row["cutoff"]
            or (target["physical_end"]-target["physical_start"]) % day_us):
        raise ValueError("Temperature requires an absolute future UTC-day support")
    products = {p["target_date"]: p for p in common["daily_products"]}
    dates = [datetime.fromtimestamp(t/1_000_000, timezone.utc).date().isoformat()
             for t in range(target["physical_start"], target["physical_end"], day_us)]
    variable = target["variable"]
    field = "forecast_min_members_C" if variable == "daily_min_2m_temperature" else "forecast_max_members_C"
    if variable not in {"daily_min_2m_temperature", "daily_max_2m_temperature",
                        "min_of_3_daily_max_2m_temperature", "max_of_3_daily_max_2m_temperature"}:
        raise ValueError("Unqualified temperature variable")
    daily = [products[date] for date in dates]
    if any(p["day_index"] < 1 for p in daily) or len({len(p[field]) for p in daily}) != 1:
        raise ValueError("Day0 or inconsistent ensemble member dimensions")
    values = [p[field] for p in daily]
    if not values or not values[0] or any(type(v) not in (int, float) or not math.isfinite(v) for a in values for v in a):
        raise ValueError("Finite complete same-member ensemble required")
    if variable.startswith("min_of_3"):
        if len(values) != 3:
            raise ValueError("Exactly three days required")
        samples = [min(v) for v in zip(*values, strict=True)]
    elif variable.startswith("max_of_3"):
        if len(values) != 3:
            raise ValueError("Exactly three days required")
        samples = [max(v) for v in zip(*values, strict=True)]
    else:
        if len(values) != 1:
            raise ValueError("Exactly one UTC day required")
        samples = values[0]
    operator, threshold = target["event_operator"], target["threshold"]
    if operator not in {"ge", "lt"}:
        raise ValueError("Unqualified temperature event endpoint")
    return sum(v >= threshold if operator == "ge" else v < threshold for v in samples)/len(samples)
