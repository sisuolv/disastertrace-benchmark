"""Build source-bound development examples, preserving failed outcome admission."""

import argparse
import calendar
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics

import eccodes


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
UTC = timezone.utc
SOURCES = {}
DECODED = []
CHECKPOINTS = []
OUTCOMES = []
BASELINES = []
DIAGNOSTICS = []


def instant(text):
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def stamp(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def source(path):
    path = path.resolve()
    raw = path.read_bytes()
    receipt_path = path.with_suffix(".json")
    receipt = json.loads(receipt_path.read_text())
    if receipt["sha256"] != digest(raw) or receipt["bytes"] != len(raw):
        raise ValueError("Source byte binding failed: " + str(path))
    if receipt["http_status"] not in (200, 206):
        raise ValueError("Source HTTP status failed")
    if receipt.get("curl_exit", 0) != 0 or receipt.get("complete", True) is False:
        raise ValueError("Incomplete source cannot enter this builder")
    key = "src-" + digest(raw)[:16]
    SOURCES[key] = dict(id=key, path=str(path.relative_to(REPO)), sha256=digest(raw),
                        bytes=len(raw), receipt=str(receipt_path.relative_to(REPO)),
                        receipt_sha256=digest(receipt_path.read_bytes()))
    return raw, key


def captured(round_id, ident):
    return ROOT / f"captures_{round_id:02d}" / (ident + ".body")


def csv_records(path):
    raw, sid = source(path)
    reader = csv.reader(io.StringIO(raw.decode()), strict=True)
    header = next(reader)
    rows = []
    for line in reader:
        if len(line) != len(header):
            raise ValueError("CSV field count mismatch")
        row = {}
        for key, value in zip(header, line):
            if key in row and row[key] != value:
                raise ValueError("Duplicate CSV column contains conflicting values")
            row[key] = value
        row["_line"] = reader.line_num
        row["_source"] = sid
        rows.append(row)
    return rows


def scalar(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Non-finite source value")
    return value


def ncei_temperature(row):
    value, quality = row["TMP"].split(",")
    if quality not in {"1", "5"} or abs(int(value)) == 9999:
        raise ValueError("temperature_quality_" + quality)
    return int(value) / 10


def accepted_temperatures(rows):
    result = []
    for row in rows:
        try:
            value = ncei_temperature(row)
        except ValueError:
            continue
        result.append(dict(time=stamp(instant(row["DATE"])), value=value, unit="degC",
                           source=row["_source"], line=row["_line"], quality=row["TMP"].split(",")[1]))
    return result


def latest_observation(rows, clock):
    # Five minutes is a declared replay rule, not a measured historical latency.
    eligible = [row for row in rows if instant(row["time"]) + timedelta(minutes=5) <= clock]
    return max(eligible, key=lambda row: row["time"]) if eligible else None


def grib(path, latitude, longitude, expected):
    raw, sid = source(path)
    if raw[:4] != b"GRIB" or raw[-4:] != b"7777" or len(raw) != int.from_bytes(raw[8:16], "big"):
        raise ValueError("Not a complete single GRIB2 message")
    receipt = json.loads(path.with_suffix(".json").read_text())
    content_range = receipt["response_headers"].get("content-range", "")
    if not content_range.startswith("bytes " + receipt["range"] + "/"):
        raise ValueError("GRIB HTTP Range mismatch")
    handle = eccodes.codes_new_from_message(raw)
    try:
        keys = ["shortName", "units", "dataDate", "dataTime", "validityDate", "validityTime",
                "typeOfLevel", "level", "stepType", "startStep", "endStep", "Ni", "Nj"]
        metadata = {key: eccodes.codes_get(handle, key) for key in keys}
        for key, value in expected.items():
            if metadata[key] != value:
                raise ValueError("Unexpected GRIB field " + key + ": " + str(metadata[key]))
        nearest = dict(eccodes.codes_grib_find_nearest(handle, latitude, longitude)[0])
        metadata["issue"] = stamp(datetime.strptime(
            str(metadata["dataDate"]) + f'{metadata["dataTime"]:04d}', "%Y%m%d%H%M").replace(tzinfo=UTC))
        metadata["valid"] = stamp(datetime.strptime(
            str(metadata["validityDate"]) + f'{metadata["validityTime"]:04d}', "%Y%m%d%H%M").replace(tzinfo=UTC))
        metadata.update(source=sid, nearest=nearest, station_lat=latitude, station_lon=longitude)
        DECODED.append(metadata)
        return metadata
    finally:
        eccodes.codes_release(handle)


def outcome(target, family, time, unit, value=None, status="unresolved", **extra):
    result = dict(target_id=target, family=family, target_time=stamp(time), unit=unit,
                  value=value, status=status, **extra)
    OUTCOMES.append(result)
    return result


def checkpoint(target, clock, forecast, observation, target_time, kind, **extra):
    if clock >= target_time:
        raise ValueError("Checkpoint must precede the fixed target")
    if instant(forecast["available_at"]) > clock:
        raise ValueError("Future forecast exposed at checkpoint")
    if observation and instant(observation["time"]) + timedelta(minutes=5) > clock:
        raise ValueError("Future observation exposed at checkpoint")
    item = dict(checkpoint_id=f"{target}-c{len([x for x in CHECKPOINTS if x['target_id'] == target])}",
                target_id=target, target_time=stamp(target_time), clock=stamp(clock),
                origin="development_archive_controlled", task_kind=kind,
                professional_forecast=forecast, prior_observation=observation, **extra)
    CHECKPOINTS.append(item)
    return item


def score_scalar(point, reference, forecast_value, prior):
    for name, value in [("professional", forecast_value), ("persistence", None if prior is None else prior["value"])]:
        BASELINES.append(dict(checkpoint_id=point["checkpoint_id"], target_id=point["target_id"],
                              method=name, value=value, unit=reference["unit"],
                              absolute_error=None if value is None or reference["value"] is None
                              else abs(value - reference["value"])))


def temperatures():
    cases = [
        ("temp-phx-original", "2023-07-19T00:00:00Z", captured(3, "ncei-phx-days"),
         [captured(2, "gfs-t2m-phx-" + tag) for tag in ["early", "mid", "late"]], "phoenix-202307-heat"),
        ("temp-phx-daytime", "2023-07-18T18:00:00Z", captured(3, "ncei-phx-days"),
         [captured(8, "gfs-phx-daytime-t2m-" + tag) for tag in ["early", "mid", "late"]], "phoenix-202307-heat"),
        ("temp-den", "2024-01-13T18:00:00Z", captured(4, "ncei-days-den-cold"),
         [captured(2, "gfs-t2m-den-" + tag) for tag in ["early", "mid", "late"]], "denver-202401-cold-snow"),
    ]
    for ident, target_text, path, forecasts, group in cases:
        rows = csv_records(path)
        target = instant(target_text)
        matches = [row for row in rows if instant(row["DATE"]) == target]
        if len(matches) != 1:
            raise ValueError("Expected exactly one fixed-time NCEI reference record")
        record = matches[0]
        try:
            value = ncei_temperature(record)
            status, reason = "quality_controlled_observation", None
        except ValueError as exc:
            value, status, reason = None, "unresolved_quality", str(exc)
        ref = outcome(ident, "temperature", target, "degC", value, status,
                      event_group=group, source=record["_source"], source_line=record["_line"],
                      raw_temperature=record["TMP"], reason=reason)
        observations = accepted_temperatures(rows)
        for path in forecasts:
            model = grib(path, scalar(record["LATITUDE"]), scalar(record["LONGITUDE"]),
                         dict(shortName="2t", units="K", typeOfLevel="heightAboveGround", level=2))
            if instant(model["valid"]) != target:
                raise ValueError("Temperature forecast and target valid times differ")
            clock = instant(model["issue"]) + timedelta(hours=5)
            value = model["nearest"]["value"] - 273.15
            prior = latest_observation(observations, clock)
            forecast = dict(value=value, unit="degC", issue=model["issue"], valid=model["valid"],
                            available_at=stamp(clock), source=model["source"], provider="NOAA GFS",
                            grid_point=model["nearest"], lineage="single_GFS_product")
            point = checkpoint(ident, clock, forecast, prior, target, "point_temperature",
                               station=record["STATION"], event_group=group)
            score_scalar(point, ref, value, prior)


def hydro():
    for lid, station in [("NRWI4", "05486000"), ("CRHA2", "15493400"), ("SCOC1", "11477000")]:
        raw, sid = source(captured(2, "usgs-flow-" + lid.lower()))
        data = json.loads(raw)
        if any(link["rel"] == "next" for link in data.get("links", [])):
            raise ValueError("Unconsumed USGS pagination")
        observations = []
        for feature in data["features"]:
            row = feature["properties"]
            if (row["monitoring_location_id"] != "USGS-" + station or row["parameter_code"] != "00060"
                    or row["statistic_id"] != "00011" or row["unit_of_measure"] != "ft^3/s"):
                raise ValueError("USGS variable/support mismatch")
            if row["approval_status"] not in {"Provisional", "Approved"} or row.get("qualifier") not in (None, ""):
                continue
            value = scalar(row["value"])
            if value < 0:
                continue
            observations.append(dict(time=stamp(instant(row["time"])), value=value, unit="ft^3/s",
                                     source=sid, quality=row["approval_status"], series=row["time_series_id"]))
        if len({row["time"] for row in observations}) != len(observations):
            raise ValueError("Ambiguous duplicate USGS observations")
        models = []
        for day in [10, 11]:
            path = captured(2, f"hefs-{lid.lower()}-202609{day}")
            if lid == "SCOC1" and day == 10:
                path = REPO / "plans/v6_data_decision_20260911/captures_03/hefs-scoc1-ensemble.raw"
            raw, model_sid = source(path)
            products = json.loads(raw)
            if len(products) != 1 or not products[0]:
                raise ValueError("Expected one complete ensemble product")
            members = products[0]
            base = members[0]
            ids = {member["ensemble_member_index"] for member in members}
            if len(ids) != len(members):
                raise ValueError("Duplicate ensemble member")
            identity = ["forecast_datetime", "creation_datetime", "start_datetime", "end_datetime"]
            for member in members:
                if (member["location_id"] != lid or member["parameter_id"] != "QINE"
                        or member["units"] != "CFS" or member["type"] != "instantaneous"
                        or any(member[key] != base[key] for key in identity)):
                    raise ValueError("Mixed HEFS product identity")
                if any(e["flag"] != "0" or scalar(e["value"]) < 0 for e in member["events"]):
                    raise ValueError("HEFS event quality failure")
            clock = instant(f"2026-09-{day}T22:00:00Z")
            if instant(base["creation_datetime"]) > clock:
                raise ValueError("HEFS created after checkpoint")
            models.append((clock, members, model_sid))
            DECODED.append(dict(kind="HEFS", lid=lid, source=model_sid, members=len(members),
                                issue=base["forecast_datetime"], created=base["creation_datetime"],
                                start=base["start_datetime"], points_per_member=len(base["events"])))
        for hour in [0, 6]:
            target = instant(f"2026-09-12T{hour:02d}:00:00Z")
            matches = [row for row in observations if instant(row["time"]) == target]
            if len(matches) != 1:
                raise ValueError("Missing exact-time USGS target")
            actual = matches[0]
            ident = f"flow-{lid.lower()}-{hour:02d}"
            ref = outcome(ident, "river_discharge", target, "ft^3/s", actual["value"],
                          "provisional_observation" if actual["quality"] == "Provisional" else "approved_observation",
                          event_group=lid + "-202609", source=sid, station=station,
                          official_flow_threshold=None)
            for clock, members, model_sid in models:
                values = []
                for member in members:
                    matches = [e for e in member["events"] if instant(e["valid_datetime"]) == target]
                    if len(matches) != 1:
                        raise ValueError("Ensemble member misses exact target")
                    values.append(scalar(matches[0]["value"]))
                value = statistics.fmean(values)
                prior = latest_observation(observations, clock)
                forecast = dict(value=value, unit="ft^3/s", issue=members[0]["forecast_datetime"],
                                created=members[0]["creation_datetime"], available_at=stamp(clock),
                                source=model_sid, provider="NOAA HEFS", member_count=len(values),
                                ensemble_values=values, member_ids=[m["ensemble_member_index"] for m in members])
                point = checkpoint(ident, clock, forecast, prior, target, "point_discharge",
                                   station=station, lid=lid, event_group=lid + "-202609")
                score_scalar(point, ref, value, prior)


def visibility(text):
    text = text.split(" RMK ")[0].split(" TEMPO ")[0].split(" NOSIG")[0]
    match = re.search(r"(?<!\S)([PM]?)(\d+(?:\s+\d+/\d+|/\d+)?)SM(?=\s|$)", text)
    if match:
        value = sum(Fraction(token) for token in match[2].split()) * Fraction("1609.344")
        bound = float(value)
        if match[1] == "P":
            return dict(lower_m=bound, upper_m=None, upper_inclusive=False, raw=match[0])
        if match[1] == "M":
            return dict(lower_m=0.0, upper_m=bound, upper_inclusive=False, raw=match[0])
        return dict(lower_m=bound, upper_m=bound, upper_inclusive=True, raw=match[0])
    if re.search(r"\bCAVOK\b", text):
        return dict(lower_m=10000.0, upper_m=None, upper_inclusive=False, raw="CAVOK")
    wind = re.search(r"(?:\d{3}|VRB)\d{2,3}(?:G\d{2,3})?(?:KT|MPS)\s+", text)
    tail = text[wind.end():] if wind else text
    match = re.search(r"(?<!\S)(\d{4})(?:NDV)?(?=\s|$)", tail)
    if match:
        value = int(match[1])
        if value == 9999:
            return dict(lower_m=10000.0, upper_m=None, upper_inclusive=False, raw=match[0])
        if value == 0:
            return dict(lower_m=0.0, upper_m=50.0, upper_inclusive=False, raw=match[0])
        return dict(lower_m=float(value), upper_m=float(value), upper_inclusive=True, raw=match[0])
    raise ValueError("No unambiguous native visibility token")


def below(interval, threshold=1000):
    if interval["lower_m"] >= threshold:
        return False
    upper = interval["upper_m"]
    if upper is not None and (upper < threshold or (upper == threshold and not interval["upper_inclusive"])):
        return True
    return None


def day_time(token, reference, with_minutes=False):
    day, hour = int(token[:2]), int(token[2:4])
    minute = int(token[4:6]) if with_minutes else 0
    if hour > 24 or minute > 59 or (hour == 24 and minute):
        raise ValueError("Invalid TAF clock token")
    possibilities = []
    for delta in [-1, 0, 1]:
        index = reference.year * 12 + reference.month - 1 + delta
        year, month0 = divmod(index, 12)
        if 1 <= day <= calendar.monthrange(year, month0 + 1)[1]:
            possibilities.append(datetime(year, month0 + 1, day, tzinfo=UTC)
                                 + timedelta(hours=hour, minutes=minute))
    return min(possibilities, key=lambda value: abs((value - reference).total_seconds()))


def taf(path, station, expected_issue):
    raw, sid = source(path)
    text = " ".join(raw.decode().split())
    header = re.search(r"\b" + station + r"\s+(\d{6})Z\s+(\d{4})/(\d{4})\s+", text)
    if not header:
        raise ValueError("Native TAF header missing")
    issue = day_time(header[1], expected_issue, True)
    if issue != expected_issue:
        raise ValueError("Native TAF issue disagrees with archive metadata")
    start = day_time(header[2], issue)
    end = day_time(header[3], start)
    if end <= start or end - start > timedelta(hours=36):
        raise ValueError("Invalid TAF validity interval")
    body = text[header.end():].split("=")[0]
    pattern = r"\b(?:FM\d{6}|(?:TEMPO|BECMG|PROB\d{2}(?: TEMPO)?)\s+\d{4}/\d{4})\b"
    controls = list(re.finditer(pattern, body))
    pieces = [("INITIAL", body[:controls[0].start()] if controls else body)]
    for i, match in enumerate(controls):
        pieces.append((match[0], body[match.end():controls[i + 1].start() if i + 1 < len(controls) else len(body)]))
    segments, conditional = [], []
    for mode, content in pieces:
        parsed = visibility(content.strip())
        if mode == "INITIAL" or mode.startswith("FM"):
            valid = start if mode == "INITIAL" else day_time(mode[2:], start, True)
            segments.append(dict(start=stamp(valid), end=stamp(end), visibility=parsed, raw=content.strip(), mode=mode))
        elif mode.startswith("TEMPO"):
            times = mode.split()[-1].split("/")
            cstart = day_time(times[0], start)
            cend = day_time(times[1], cstart)
            conditional.append(dict(start=stamp(cstart), end=stamp(cend), visibility=parsed, mode=mode, raw=content.strip()))
        else:
            raise ValueError("Operator retained as unsupported in this bounded TAF parser: " + mode)
    segments.sort(key=lambda row: row["start"])
    for first, second in zip(segments, segments[1:]):
        first["end"] = second["start"]
    if any(instant(row["start"]) >= instant(row["end"]) for row in segments + conditional):
        raise ValueError("Nonpositive TAF segment duration")
    result = dict(source=sid, station=station, issue=stamp(issue), start=stamp(start), end=stamp(end),
                  segments=segments, conditional=conditional, native_text=text)
    DECODED.append(dict(kind="TAF", **result))
    return result


def metars(path):
    rows = csv_records(path)
    parsed = []
    for row in rows:
        try:
            interval = visibility(row["metar"])
        except ValueError:
            continue
        parsed.append(dict(time=stamp(instant(row["valid"])), visibility=interval,
                           source=row["_source"], line=row["_line"], raw=row["metar"],
                           weather=row["wxcodes"], quality="archived_report_not_final_sensor_QC"))
    return parsed


def airports():
    selections = json.loads((ROOT / "TAF_SELECTION_01.json").read_text())
    for station, date, first_hour, minute, path in [
        ("KSFO", "2024-01-06", 12, 56, captured(1, "metar-sfo-vis")),
        ("KDEN", "2024-01-13", 6, 53, captured(3, "metar-serial-den")),
    ]:
        observations = metars(path)
        models = []
        for select in selections:
            if select["station"] != station:
                continue
            model = taf(captured(4, select["capture_id"]), station, instant(select["issue"]))
            models.append((instant(select["cutoff"]), model))
        for hour in range(first_hour, first_hour + 12):
            target = instant(f"{date}T{hour:02d}:{minute:02d}:00Z")
            ident = f"visibility-{station.lower()}-{hour:02d}"
            matches = [row for row in observations if instant(row["time"]) == target]
            if len(matches) > 1:
                raise ValueError("Ambiguous METAR target")
            actual = matches[0] if matches else None
            actual_class = below(actual["visibility"]) if actual else None
            ref = outcome(ident, "airport_visibility", target, "m", status="archived_report" if actual else "unresolved_missing_report",
                          interval=None if actual is None else actual["visibility"], below_1000m=actual_class,
                          source=None if actual is None else actual["source"],
                          source_line=None if actual is None else actual["line"],
                          raw_metar=None if actual is None else actual["raw"],
                          weather=None if actual is None else actual["weather"], station=station,
                          event_group="denver-202401-cold-snow" if station == "KDEN" else "sfo-202401-rain")
            for clock, model in models:
                matches = [s for s in model["segments"] if instant(s["start"]) <= target < instant(s["end"])]
                if len(matches) != 1:
                    raise ValueError("TAF does not uniquely cover the fixed target")
                segment = matches[0]
                prior = latest_observation(observations, clock)
                conditions = [s for s in model["conditional"] if instant(s["start"]) <= target < instant(s["end"])]
                forecast = dict(visibility=segment["visibility"], raw_segment=segment["raw"],
                                segment_start=segment["start"], segment_end=segment["end"],
                                conditional_segments=conditions, issue=model["issue"],
                                available_at=stamp(instant(model["issue"]) + timedelta(minutes=15)),
                                provider="NWS TAF via IEM", source=model["source"], projection="prevailing_only")
                point = checkpoint(ident, clock, forecast, prior, target, "point_visibility", station=station)
                for method, interval in [("taf_prevailing_projection", segment["visibility"]),
                                         ("persistence", None if prior is None else prior["visibility"])]:
                    value = below(interval) if interval else None
                    BASELINES.append(dict(checkpoint_id=point["checkpoint_id"], target_id=ident, method=method,
                                          predicted_below_1000m=value, actual_below_1000m=actual_class,
                                          correct=None if value is None or actual_class is None else value == actual_class,
                                          conditional_overlay_present=bool(conditions)))


def supplementary():
    rows = csv_records(captured(4, "ncei-days-msy-rain"))
    exact = [r for r in rows if r["DATE"] == "2024-09-12T00:00:00"][0]
    target = instant(exact["DATE"])
    period, depth, condition, quality = exact["AA1"].split(",")
    if period != "06" or condition != "3":
        raise ValueError("Expected the recorded accumulation-condition ambiguity")
    ref = outcome("rain-msy-strict", "precipitation", target, "mm", status="unresolved_accumulation_condition",
                  source=exact["_source"], source_line=exact["_line"], raw_precipitation=exact["AA1"],
                  reason="condition_3_begin_accumulated_period", window_start="2024-09-11T18:00:00Z")
    near = [r for r in rows if r["DATE"] == "2024-09-11T23:53:00"][0]
    fields = near["AA2"].split(",")
    if fields[0] != "06" or fields[2] != "9" or fields[3] not in {"1", "5"}:
        raise ValueError("Unexpected nearby six-hour precipitation metadata")
    native_group = re.search(r"\b6(\d{4})\b", near["REM"])
    if not native_group:
        raise ValueError("Native six-hour METAR group missing")
    native_mm = int(native_group[1]) / 100 * 25.4
    reported_mm = int(fields[1]) / 10
    if abs(native_mm - reported_mm) > 0.051:
        raise ValueError("METAR precipitation and decoded AA2 disagree")
    forecasts = []
    for tag in ["early", "mid", "late"]:
        model = grib(captured(5, "gfs-rain-apcp-" + tag), scalar(exact["LATITUDE"]), scalar(exact["LONGITUDE"]),
                     dict(shortName="tp", units="kg m**-2", stepType="accum", typeOfLevel="surface"))
        begin = instant(model["issue"]) + timedelta(hours=model["startStep"])
        if instant(model["valid"]) != target or begin != target - timedelta(hours=6):
            raise ValueError("Wrong GFS accumulation window")
        clock = instant(model["issue"]) + timedelta(hours=5)
        forecast = dict(value=model["nearest"]["value"], unit="mm", source=model["source"], issue=model["issue"],
                        available_at=stamp(clock), accumulation_start=stamp(begin), accumulation_end=stamp(target),
                        provider="NOAA GFS", grid_point=model["nearest"])
        point = checkpoint("rain-msy-strict", clock, forecast, None, target, "six_hour_precipitation")
        score_scalar(point, ref, forecast["value"], None)
        forecasts.append(forecast)
    DIAGNOSTICS.append(dict(kind="rain_near_time_only", target_station=exact["STATION"],
                            forecast_window_end=stamp(target), observation_window_end=near["DATE"],
                            end_difference_seconds=420, source=near["_source"], source_line=near["_line"],
                            reported_mm=reported_mm, raw_six_hour_group=native_group[0], native_group_mm=native_mm,
                            condition_note="condition 9 not supplied; quality 1/5 required", forecasts=forecasts,
                            strict_target_settled=False))
    observations = metars(captured(3, "metar-serial-egkk"))
    wanted = instant("2024-12-27T11:50:00Z")
    actual = [row for row in observations if instant(row["time"]) == wanted]
    if len(actual) != 1:
        raise ValueError("Expected fixed EGKK near-time report")
    fog_models = []
    for tag in ["early", "mid", "late"]:
        model = grib(captured(6, "gfs-fog-vis-" + tag), 51.1481, -0.1903,
                     dict(shortName="vis", units="m", typeOfLevel="surface"))
        if instant(model["valid"]) != instant("2024-12-27T12:00:00Z"):
            raise ValueError("Wrong EGKK GFS valid time")
        fog_models.append(model)
    DIAGNOSTICS.append(dict(kind="uk_visibility_near_time_only", observation=actual[0], forecast_models=fog_models,
                            difference_seconds=600, exact_time_match=False,
                            downloaded_reports=len(observations),
                            below_1000m_reports=sum(below(r["visibility"]) is True for r in observations),
                            taf_archive_rows={tag: len(csv_records(captured(3, "taf-csv-" + tag))) for tag in ["egll", "egkk"]}))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new output directory")
    temperatures()
    hydro()
    airports()
    supplementary()
    args.output.mkdir(parents=True)
    for name in ["public", "private"]:
        (args.output / name).mkdir()
    for path, records in [("public/checkpoints.jsonl", CHECKPOINTS), ("private/outcomes.jsonl", OUTCOMES),
                          ("baselines.jsonl", BASELINES)]:
        (args.output / path).write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in records))
    write_json(args.output / "SOURCE_BINDINGS.json", list(SOURCES.values()))
    write_json(args.output / "DECODED_PRODUCTS.json", DECODED)
    write_json(args.output / "SUPPLEMENTARY.json", DIAGNOSTICS)
    report = dict(schema="disastertrace.task_chain_feasibility.v1", targets=len(OUTCOMES),
                  checkpoints=len(CHECKPOINTS), baseline_records=len(BASELINES),
                  families=dict(Counter(row["family"] for row in OUTCOMES)),
                  outcome_status=dict(Counter(row["status"] for row in OUTCOMES)),
                  quality_temperature_targets=[r for r in OUTCOMES if r["family"] == "temperature"],
                  visibility_positive_targets=sum(r.get("below_1000m") is True for r in OUTCOMES),
                  distinct_bound_sources=len(SOURCES), numeric_products=len(DECODED),
                  new_model_calls=0, new_gpu_jobs=0, confirmed_novelty=False,
                  limits=["Development cases, not independent-event confirmation.",
                          "Historical availability is controlled, not proved by issue time.",
                          "Raw archived METAR is not a final independent sensor-QC certificate.",
                          "No calibrated probability or complete TAF conditional-probability baseline.",
                          "Public checkpoint rows exclude future values; a live filesystem sandbox is not tested here."])
    write_json(args.output / "REPORT.json", report)
    print(json.dumps({k: report[k] for k in ["targets", "checkpoints", "baseline_records", "families", "outcome_status", "visibility_positive_targets"]}))


if __name__ == "__main__":
    main()
