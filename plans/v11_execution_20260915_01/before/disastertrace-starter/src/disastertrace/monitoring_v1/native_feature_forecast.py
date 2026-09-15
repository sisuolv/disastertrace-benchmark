"""Threshold-coherent, auditable feature backend for native H15 products.

All exact quantities describe native report/product labels. Feature clipping is
a numerical transform, never an asserted bound on unknown physical weather.
"""

import math
import re
from datetime import datetime, timezone

from .evidence import interval_from_dict, taf_features
from .providers.aviation import parse_metar, parse_taf

HOUR = 3_600_000_000
FEATURE_VERSION = "native_h15_features.v1"


def _iso(at):
    return datetime.fromtimestamp(at / 1_000_000, timezone.utc).isoformat()


def native_claims(query_ids, disclosed, *, at):
    if not set(disclosed) <= set(query_ids):
        raise ValueError("Unregistered native evidence")
    claims = {}
    for qid, product in disclosed.items():
        if (
            product["query_id"] != qid
            or product.get("reference_kind") != "product_label"
            or product.get("support_assumption") != "product_exact"
        ):
            raise ValueError("Native feature source must have a bound product-label contract")
        value = {"visibility": None, "temperature_c": None, "dewpoint_c": None}
        if product["status"] == "disclosed_product_fact" and len(product.get("reports", [])) == 1:
            report = product["reports"][0]
            if report["observation_time"] > at:
                raise ValueError("Future native observation cannot enter forecast features")
            parsed = parse_metar(
                report["raw"],
                observation_time=_iso(report["observation_time"]),
                report_type="routine",
            )
            visibility = None if parsed.visibility is None else parsed.visibility.to_dict()
            if parsed.station != report["station"] or visibility != report["visibility"]:
                raise ValueError("Native report and supplied decoded values disagree")
            value = {
                "visibility": visibility,
                "temperature_c": parsed.temperature_c,
                "dewpoint_c": parsed.dewpoint_c,
            }
        claims[qid] = value
    return claims


def validate_claims(claims, disclosed):
    if not isinstance(claims, dict) or set(claims) != set(disclosed):
        raise ValueError("Claims must match the actually disclosed slots")
    for value in claims.values():
        if not isinstance(value, dict) or set(value) != {
            "visibility",
            "temperature_c",
            "dewpoint_c",
        }:
            raise ValueError("Invalid native feature claim schema")
        for key in ("temperature_c", "dewpoint_c"):
            if value[key] is not None and (
                type(value[key]) not in (float, int) or not math.isfinite(value[key])
            ):
                raise ValueError("A claimed temperature must be finite or missing")
        if value["visibility"] is not None:
            raw = value["visibility"]
            if (
                not isinstance(raw, dict)
                or set(raw) != {"lower", "upper", "lower_closed", "upper_closed"}
                or any(type(raw[k]) is not bool for k in ("lower_closed", "upper_closed"))
                or any(
                    v != "+inf" and (type(v) not in (float, int) or not math.isfinite(v))
                    for v in (raw["lower"], raw["upper"])
                )
            ):
                raise ValueError("A claimed visibility requires an exact typed native interval")
            interval = interval_from_dict(value["visibility"])
            if interval.lower < 0:
                raise ValueError("Native visibility cannot have a negative lower bound")


def feature_vector(target, candidate, query_ids, disclosed, *, at, mode="values", claims=None):
    if (
        mode not in {"common", "mask_age", "values"}
        or len(set(query_ids)) != len(query_ids)
        or len(query_ids) > 2
        or not set(disclosed) <= set(query_ids)
        or type(at) is not int
        or target["physical_start"] <= at
    ):
        raise ValueError("Invalid native feature information/time contract")
    stamp = datetime.fromtimestamp(target["physical_start"] / 1_000_000, timezone.utc)
    station = target["entity"].removeprefix("station:")
    features = {
        "station:" + station: 1.0,
        "hour_sin": math.sin(2 * math.pi * stamp.hour / 24),
        "hour_cos": math.cos(2 * math.pi * stamp.hour / 24),
        "year_sin": math.sin(2 * math.pi * stamp.timetuple().tm_yday / 365.25),
        "year_cos": math.cos(2 * math.pi * stamp.timetuple().tm_yday / 365.25),
        "lead_hours": (target["physical_start"] - at) / HOUR,
        "window_hours": (target["physical_end"] - target["physical_start"]) / HOUR,
        "taf_present": float(candidate is not None),
        "taf_parsed": 0.0,
        "taf_age_hours": 0.0,
    }
    if candidate is not None:
        if candidate["available_at"] > at or candidate["issued_at"] > at:
            raise ValueError("Undisclosed future TAF cannot enter features")
        features["taf_age_hours"] = min(48.0, (at - candidate["issued_at"]) / HOUR)
        if candidate.get("projection_status") != "unavailable":
            native = parse_taf(
                candidate["raw"], station=station, archive_issue=_iso(candidate["issued_at"])
            )
            projection = native.project(target["physical_start"], target["physical_end"])
            if projection != candidate["projection"]:
                raise ValueError("Full native TAF projection differs from registered target")
            features["taf_parsed"] = 1.0
            for threshold in (1000, 5000):
                groups = taf_features(projection, threshold)
                for group in ("prevailing", "conditional"):
                    for category in ("any_low", "uncertain", "no_low"):
                        features[f"taf_{threshold}_{group}_{category}"] = float(
                            groups[group] == category
                        )
                for operator in groups["conditional_operators"]:
                    features["taf_operator:" + operator] = 1.0
            features["taf_segments"] = float(len(projection["segments"]))
            winds = [
                state.get("wind", "")
                for segment in projection["segments"]
                for state in segment["prevailing"]
            ]
            speeds = [
                float(m[1])
                for wind in winds
                if (m := re.fullmatch(r"(?:\d{3}|VRB)(\d{2,3})(?:G\d{2,3})?KT", wind))
            ]
            features["taf_wind_kt"] = sum(speeds) / len(speeds) if speeds else 0.0
            features["taf_wind_missing"] = float(not speeds)
    if mode == "common":
        return features
    values = native_claims(query_ids, disclosed, at=at) if claims is None else claims
    validate_claims(values, disclosed)
    for index, qid in enumerate(sorted(query_ids)):
        prefix = f"slot{index}_"
        product = disclosed.get(qid)
        read = product is not None
        reports = product.get("reports", []) if read else []
        valid = read and product["status"] == "disclosed_product_fact" and len(reports) == 1
        features[prefix + "read"] = float(read)
        features[prefix + "valid_report"] = float(valid)
        age = 0.0
        if valid:
            if reports[0]["observation_time"] > at:
                raise ValueError("Future native observation cannot enter age features")
            age = min(48.0, (at - reports[0]["observation_time"]) / HOUR)
        features[prefix + "age_hours"] = age
        value = values.get(qid, {"visibility": None, "temperature_c": None, "dewpoint_c": None})
        for field in value:
            features[prefix + field + "_missing"] = float(value[field] is None)
        if mode == "mask_age":
            continue
        interval = None if value["visibility"] is None else interval_from_dict(value["visibility"])
        for bound in ("lower", "upper"):
            number = None if interval is None else getattr(interval, bound)
            features[prefix + "visibility_" + bound + "_log"] = (
                0.0 if number is None else math.log1p(min(20000.0, number))
            )
            features[prefix + "visibility_" + bound + "_infinite"] = float(
                number is not None and math.isinf(number)
            )
        for field in ("temperature_c", "dewpoint_c"):
            number = value[field]
            features[prefix + field] = 0.0 if number is None else min(100.0, max(-100.0, number))
        temp, dew = value["temperature_c"], value["dewpoint_c"]
        features[prefix + "dewpoint_depression_c"] = (
            0.0 if temp is None or dew is None else min(100.0, max(-100.0, temp - dew))
        )
    return features


def predict_features(bank, features):
    if bank["feature_version"] != FEATURE_VERSION:
        raise ValueError("Feature-bank version mismatch")
    vector = [
        (features.get(k, 0.0) - mean) / scale
        for k, mean, scale in zip(bank["feature_names"], bank["mean"], bank["scale"], strict=True)
    ]
    scores = [
        intercept + math.fsum(c * x for c, x in zip(coef, vector, strict=True))
        for coef, intercept in zip(bank["coefficients"], bank["intercepts"], strict=True)
    ]
    peak = max(scores)
    weights = [math.exp(score - peak) for score in scores]
    probabilities = [weight / math.fsum(weights) for weight in weights]
    return {
        "1000": probabilities[0],
        "5000": min(1.0, probabilities[0] + probabilities[1]),
        "classes": probabilities,
        "mapping_version": bank["mapping_version"],
    }
