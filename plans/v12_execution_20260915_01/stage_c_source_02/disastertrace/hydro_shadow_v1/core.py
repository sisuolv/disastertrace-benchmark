"""Water-level contracts, input-only predictions, and separate exact-time settlement."""

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone

MISSING = {-999.0, -9999.0}
POLICIES = ("initial_professional", "latest_professional", "persistence", "half_blend")


def instant(value):
    result = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if result.tzinfo is None:
        raise ValueError("UTC-aware timestamp required")
    return result.astimezone(timezone.utc)


def utc(value):
    return instant(value).isoformat().replace("+00:00", "Z")


def number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("missing or boolean numeric value")
    result = float(value)
    if not math.isfinite(result) or result in MISSING:
        raise ValueError("nonfinite value or provider missing sentinel")
    return result


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def threshold_contract(metadata):
    if metadata["flood"]["stageUnits"] != "ft":
        raise ValueError("stage threshold must be in feet")
    stage = number(metadata["flood"]["categories"]["minor"]["stage"])
    return {
        "minor_stage_ft": stage,
        "reference_name": metadata["name"],
        "vertical_datums": metadata.get("datums", {}).get("vertical", {}).get("value", []),
    }


def nwps_points(stageflow, role, captured_at, variable="Stage"):
    section = stageflow.get(role, {})
    if section.get("primaryName") != variable or section.get("primaryUnits") != "ft":
        raise ValueError("NWPS primary variable/unit contract mismatch")
    capture = instant(captured_at)
    issued = instant(section["issuedTime"])
    if issued > capture:
        raise ValueError("NWPS issue timestamp is later than receipt")
    points, excluded = {}, Counter()
    for index, row in enumerate(section["data"]):
        try:
            valid = instant(row["validTime"])
            generated = instant(row["generatedTime"])
            value = number(row["primary"])
            if generated > capture or (role == "observed" and valid > capture):
                raise ValueError("future generated record or future observation")
        except (KeyError, TypeError, ValueError) as exc:
            excluded[str(exc)] += 1
            continue
        point = {
            "valid_at": utc(valid),
            "generated_at": utc(generated),
            "value": value,
            "source_row": index,
            "issued_at": utc(issued),
        }
        key = point["valid_at"]
        previous = points.get(key)
        if (
            previous
            and previous["generated_at"] == point["generated_at"]
            and previous["value"] != value
        ):
            raise ValueError("conflicting NWPS values at one version/time")
        if previous is None or point["generated_at"] > previous["generated_at"]:
            points[key] = point
    return sorted(points.values(), key=lambda p: p["valid_at"]), dict(excluded)


def usgs_points(body, site, parameter, captured_at):
    if any(link.get("rel") == "next" for link in body.get("links", [])):
        raise ValueError("USGS response is paginated")
    points, excluded = {}, Counter()
    for feature in body["features"]:
        row = feature["properties"]
        if row["monitoring_location_id"] != "USGS-" + site or row["parameter_code"] != parameter:
            raise ValueError("USGS station/parameter identity mismatch")
        if row["unit_of_measure"] != "ft" or row["statistic_id"] != "00011":
            raise ValueError("USGS unit/statistical support mismatch")
        try:
            at = instant(row["time"])
            value = number(row["value"])
            if at > instant(captured_at):
                raise ValueError("future USGS observation")
            if row.get("qualifier") not in (None, ""):
                raise ValueError("qualified USGS observation")
            if row["approval_status"] not in ("Provisional", "Approved"):
                raise ValueError("unknown USGS approval status")
        except (KeyError, TypeError, ValueError) as exc:
            excluded[str(exc)] += 1
            continue
        point = {
            "valid_at": utc(at),
            "value": value,
            "quality": row["approval_status"],
            "source_identity": row["time_series_id"] + ":" + utc(at),
        }
        key = point["valid_at"]
        if key in points and points[key] != point:
            raise ValueError("ambiguous USGS series or conflicting values at the same time")
        points[key] = point
    return sorted(points.values(), key=lambda p: p["valid_at"]), dict(excluded)


def coops_points(body, station, captured_at):
    if body.get("metadata", {}).get("id") != station or "error" in body:
        raise ValueError("CO-OPS station identity mismatch or provider error")
    points, excluded = {}, Counter()
    for row in body["data"]:
        try:
            at = instant(row["t"].replace(" ", "T") + ":00Z")
            value = number(row["v"])
            if at > instant(captured_at):
                raise ValueError("future CO-OPS observation")
            if row.get("q") not in ("p", "v") or row.get("f") != "0,0,0,0":
                raise ValueError("CO-OPS quality flag requires quarantine")
        except (KeyError, TypeError, ValueError) as exc:
            excluded[str(exc)] += 1
            continue
        point = {
            "valid_at": utc(at),
            "value": value,
            "quality": "Approved" if row["q"] == "v" else "Provisional",
            "source_identity": station + ":MLLW:english:" + utc(at),
        }
        key = point["valid_at"]
        if key in points and points[key] != point:
            raise ValueError("conflicting CO-OPS observations")
        points[key] = point
    return sorted(points.values(), key=lambda p: p["valid_at"]), dict(excluded)


def align_observations(nwps, primary, tolerance=0.02):
    indexed = {p["valid_at"]: p for p in nwps}
    pairs = [(p, indexed[p["valid_at"]]) for p in primary if p["valid_at"] in indexed]
    if not pairs:
        return {"pairs": 0, "compatible": False, "max_difference_ft": None, "mismatches": 0}
    differences = [abs(a["value"] - b["value"]) for a, b in pairs]
    return {
        "pairs": len(pairs),
        "compatible": all(d <= tolerance + 1e-10 for d in differences),
        "max_difference_ft": max(differences),
        "mismatches": sum(d > tolerance + 1e-10 for d in differences),
        "tolerance_ft": tolerance,
    }


def primary_contract(metadata, site, parameter, provider):
    datums = metadata.get("datums", {}).get("vertical", {}).get("value", [])
    offset = 0.0
    if provider == "usgs":
        props = site["properties"]
        if props["id"] != "USGS-" + metadata["usgsId"]:
            raise ValueError("USGS/NWPS station mapping mismatch")
        absolute = "NAVD88" in metadata["name"].upper()
        if parameter == "00065" and absolute:
            offset = number(props["altitude"])
            navd = [d for d in datums if d["abbrev"] == "NAVD88" and number(d["value"]) == 0]
            standard = [
                d
                for d in datums
                if d["abbrev"] == "STND" and abs(number(d["value"]) + offset) <= 0.01
            ]
            if props["vertical_datum"] != "NAVD88" or len(navd) != 1 or len(standard) != 1:
                raise ValueError("absolute datum offset not supported by both source metadata")
            reference = "NAVD88"
        elif parameter == "00065":
            matches = [
                d
                for d in datums
                if d["abbrev"] == props["vertical_datum"]
                and abs(number(d["value"]) - number(props["altitude"])) <= 0.01
            ]
            if len(matches) != 1:
                raise ValueError("gage datum metadata do not match")
            reference = "gage_datum"
        elif parameter == "62614" and absolute:
            reference = "NAVD88"
        else:
            raise ValueError("unsupported parameter/reference pair")
        source_station = metadata["usgsId"]
        spatial_group = props.get("hydrologic_unit_code")
        source_datum = {"datum": props["vertical_datum"], "elevation_ft": props["altitude"]}
    elif provider == "coops":
        station = site["stations"][0]
        source_station = station["id"]
        if "MLLW" not in metadata["name"].upper():
            raise ValueError("NWPS coastal datum is not explicitly MLLW")
        if source_station not in json.dumps(metadata) or station["shefcode"] != metadata["lid"]:
            raise ValueError("NOAA and NWPS station identities do not match")
        if (
            abs(float(station["lat"]) - metadata["latitude"]) > 0.01
            or abs(float(station["lng"]) - metadata["longitude"]) > 0.01
        ):
            raise ValueError("CO-OPS/NWPS coordinates do not align")
        if station["datums"]["units"] != "feet":
            raise ValueError("CO-OPS datum metadata units mismatch")
        source_datum = {
            "epoch": station["datums"]["epoch"],
            "MLLW": [d for d in station["datums"]["datums"] if d["name"] == "MLLW"],
        }
        if len(source_datum["MLLW"]) != 1:
            raise ValueError("CO-OPS MLLW metadata missing")
        reference, spatial_group = "MLLW", "southeast_coastal_tide_context"
    else:
        raise ValueError("unsupported outcome provider")
    return {
        "provider": provider,
        "source_station": source_station,
        "parameter": parameter,
        "reference": reference,
        "offset_ft": offset,
        "source_datum": source_datum,
        "spatial_group": spatial_group,
        "unit": "ft",
        "variable": "Tide Height" if provider == "coops" else "Stage",
    }


def primary_points(primary, contract, captured_at):
    if contract["provider"] == "usgs":
        points, excluded = usgs_points(
            primary, contract["source_station"], contract["parameter"], captured_at
        )
    else:
        points, excluded = coops_points(primary, contract["source_station"], captured_at)
    if contract["offset_ft"]:
        points = [
            {**p, "raw_value_ft": p["value"], "value": p["value"] + contract["offset_ft"]}
            for p in points
        ]
    return points, excluded


def qualify_station(
    metadata, stageflow, primary, site, parameter, captured_at, provider="usgs", receipts=None
):
    receipts = receipts or {"stageflow": captured_at, "primary": captured_at}
    problems = []
    try:
        contract = threshold_contract(metadata)
        source = primary_contract(metadata, site, parameter, provider)
    except (KeyError, TypeError, ValueError) as exc:
        return {"lid": metadata.get("lid"), "admitted": False, "problems": [str(exc)]}
    observed, excluded_obs = nwps_points(
        stageflow, "observed", receipts["stageflow"], source["variable"]
    )
    try:
        forecast, excluded_forecast = nwps_points(
            stageflow, "forecast", receipts["stageflow"], source["variable"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        forecast, excluded_forecast = [], {str(exc): 1}
    points, excluded_primary = primary_points(primary, source, receipts["primary"])
    aligned = align_observations(observed, points)
    if aligned["pairs"] < 8 or not aligned["compatible"]:
        problems.append("insufficient or inconsistent exact-time provider overlap")
    recent = [
        p
        for p in points
        if instant(captured_at) - timedelta(hours=6)
        <= instant(p["valid_at"])
        <= instant(captured_at)
    ]
    if not recent:
        problems.append("no eligible measurement within six hours")
    future = [p for p in forecast if instant(p["valid_at"]) > instant(captured_at)]
    if not future:
        problems.append("no future forecast values")
    if future and instant(captured_at) - instant(future[0]["issued_at"]) > timedelta(hours=36):
        problems.append("forecast older than 36 hours")
    minor = contract["minor_stage_ft"]
    return {
        "lid": metadata["lid"],
        "name": metadata["name"],
        "admitted": not problems,
        "problems": problems,
        **source,
        "primary_contract": source,
        "primary_contract_hash": content_hash(source),
        "threshold": minor,
        "threshold_kind": "minor_flood_stage_snapshot_at_registration",
        "contract_hash": content_hash(contract),
        "rfc": metadata["rfc"]["abbreviation"],
        "family": "coastal_water_level" if provider == "coops" else "river_water_level",
        "provider_alignment": aligned,
        "primary_observations": len(points),
        "quality_counts": dict(Counter(p["quality"] for p in points)),
        "recent_threshold_exceedance_points": sum(p["value"] >= minor for p in points),
        "nwps_30d_threshold_exceedance_points": sum(p["value"] >= minor for p in observed),
        "historical_threshold_vintage_proven": False,
        "source_dependence": "NWPS observed values may retransmit this primary provider; not independent evidence",
        "future_forecast_points": len(future),
        "forecast_issue_time": future[0]["issued_at"] if future else None,
        "excluded": {
            "nwps_observed": excluded_obs,
            "nwps_forecast": excluded_forecast,
            "primary": excluded_primary,
        },
    }


def build_snapshot(station, stageflow, primary, captured_at, receipts=None):
    receipts = receipts or {"stageflow": captured_at, "primary": captured_at}
    forecasts, _ = nwps_points(stageflow, "forecast", receipts["stageflow"], station["variable"])
    observations, _ = primary_points(primary, station["primary_contract"], receipts["primary"])
    return {
        "lid": station["lid"],
        "captured_at": utc(captured_at),
        "source_received_at": receipts,
        "forecast": forecasts,
        "observations": observations,
    }


def predict(snapshot, target, committed_at, initial_value):
    now, deadline = instant(committed_at), instant(target["deadline"])
    if not now <= deadline < instant(target["valid_at"]):
        raise ValueError("late commit or invalid forecast deadline")
    if snapshot["lid"] != target["lid"] or instant(snapshot["captured_at"]) > now:
        raise ValueError("snapshot identity/receipt is not available for this commit")
    forecasts = [
        p
        for p in snapshot["forecast"]
        if instant(p["valid_at"]) == instant(target["valid_at"])
        and instant(p["issued_at"]) <= now
        and instant(p["generated_at"]) <= now
        and now - instant(p["issued_at"]) <= timedelta(hours=36)
    ]
    observations = [
        p
        for p in snapshot["observations"]
        if now - timedelta(hours=6) <= instant(p["valid_at"]) <= now
    ]
    official = max(forecasts, key=lambda p: p["generated_at"])["value"] if forecasts else None
    obs = max(observations, key=lambda p: p["valid_at"])["value"] if observations else None
    values = {
        "initial_professional": initial_value,
        "latest_professional": official,
        "persistence": obs,
        "half_blend": (official + obs) / 2 if official is not None and obs is not None else None,
    }
    return [
        {
            "target_id": target["id"],
            "lid": target["lid"],
            "valid_at": target["valid_at"],
            "committed_at": utc(now),
            "policy": policy,
            "value": number(value),
            "threshold": target["threshold"],
            "point_exceeds_threshold": number(value) >= target["threshold"],
            "snapshot_sha256": content_hash(snapshot),
            "source_first_seen_at": snapshot["captured_at"],
        }
        for policy, value in values.items()
        if value is not None
    ]


def settle(target, commits, observations, checked_at):
    now = instant(checked_at)
    if now < instant(target["valid_at"]):
        return {"target_id": target["id"], "status": "pending_future", "checked_at": utc(now)}
    matches = [p for p in observations if instant(p["valid_at"]) == instant(target["valid_at"])]
    if len(matches) > 1:
        raise ValueError("ambiguous exact-time outcome")
    if not matches:
        return {
            "target_id": target["id"],
            "status": "pending_exact_observation",
            "checked_at": utc(now),
        }
    outcome = matches[0]
    if outcome["quality"] not in ("Approved", "Provisional"):
        raise ValueError("outcome quality is not eligible")
    eligible = [
        c
        for c in commits
        if c["target_id"] == target["id"]
        and instant(c["committed_at"]) <= instant(target["deadline"])
    ]
    by_policy = {}
    for policy in POLICIES:
        candidates = [c for c in eligible if c["policy"] == policy]
        last = max(candidates, key=lambda c: c["committed_at"]) if candidates else None
        by_policy[policy] = {
            "status": "scored" if last else "missing_prediction",
            "prediction": last["value"] if last else None,
            "absolute_error": abs(last["value"] - outcome["value"]) if last else None,
            "point_threshold_error": int(
                (last["value"] >= target["threshold"]) != (outcome["value"] >= target["threshold"])
            )
            if last
            else None,
        }
    return {
        "target_id": target["id"],
        "checked_at": utc(now),
        "status": "settled_approved" if outcome["quality"] == "Approved" else "settled_provisional",
        "outcome": outcome,
        "binary_outcome": int(outcome["value"] >= target["threshold"]),
        "policies": by_policy,
    }
