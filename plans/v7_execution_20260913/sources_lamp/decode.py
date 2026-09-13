"""Decode native LAMP text without treating guidance as observed weather."""

import datetime as dt
import re

UTC = dt.timezone.utc
MILE_METERS = 1609.344
FLT_HEADER = re.compile(
    r"^([A-Z][A-Z0-9]{3})\s+.*?GFS LAMP (\d{4}) UTC\s+(\d+)/(\d+)/(\d{4})$"
)
LAV_HEADER = re.compile(
    r"^\s*([A-Z][A-Z0-9]{3})\s+GFS LAMP GUIDANCE\s+(\d+)/(\d+)/(\d{4})\s+(\d{4}) UTC\s*$",
    re.MULTILINE,
)
VISIBILITY_THRESHOLDS = {
    "VPVL": {"operator": "lt", "miles": 0.5, "meters": 0.5 * MILE_METERS},
    "VPL": {"operator": "lt", "miles": 1.0, "meters": MILE_METERS},
    "VPI": {"operator": "lt", "miles": 3.0, "meters": 3.0 * MILE_METERS},
    "VPM": {"operator": "le", "miles": 5.0, "meters": 5.0 * MILE_METERS},
    "VPVFR": {"operator": "gt", "miles": 5.0, "meters": 5.0 * MILE_METERS},
}


def timestamp(month, day, year, hhmm):
    return dt.datetime(int(year), int(month), int(day), int(hhmm[:2]), int(hhmm[2:]), tzinfo=UTC)


def advance_hour(anchor, hour, minute=0):
    candidate = anchor.replace(hour=int(hour), minute=int(minute))
    while candidate <= anchor:
        candidate += dt.timedelta(days=1)
    return candidate


def fixed_cells(line, start, count):
    cells = [line[start + 3 * index : start + 3 * (index + 1)].strip() for index in range(count)]
    if any(not cell for cell in cells):
        raise ValueError("empty or truncated fixed-width cell")
    return cells


def parse_fltcat(text):
    records = []
    blocks = text.strip().split("\n\n")
    seen = set()
    for block in blocks:
        lines = block.splitlines()
        match = FLT_HEADER.fullmatch(lines[0].strip())
        if match is None:
            raise ValueError("unrecognized flight-category header")
        station, hhmm, month, day, year = match.groups()
        initialized = timestamp(month, day, year, hhmm)
        key = (station, initialized)
        if key in seen:
            raise ValueError("duplicate station/cycle")
        seen.add(key)
        fields = {line[:5].strip(): line for line in lines[1:] if line[:5].strip()}
        hours = fields["UTC"][5:].split()
        minutes = fields["MIN"][5:].split()
        if len(hours) != 24 or len(minutes) != 24:
            raise ValueError("this decoder requires a complete 24-slot 15-minute bulletin")
        parsed = {name: fixed_cells(fields[name], 5, 24) for name in ("VIS", "CIG", *VISIBILITY_THRESHOLDS)}
        previous_end = initialized
        for index, (hour, minute) in enumerate(zip(hours, minutes, strict=True)):
            end = advance_hour(previous_end, hour, minute)
            if end - previous_end != dt.timedelta(minutes=15):
                raise ValueError("non-contiguous 15-minute forecast grid")
            probabilities = {name: int(parsed[name][index]) for name in VISIBILITY_THRESHOLDS}
            if any(not 0 <= value <= 100 for value in probabilities.values()):
                raise ValueError("probability outside percent range; missing must be handled explicitly")
            cumulative = [probabilities[name] for name in ("VPVL", "VPL", "VPI", "VPM")]
            if cumulative != sorted(cumulative):
                raise ValueError("non-monotone cumulative visibility probabilities")
            records.append({
                "station": station,
                "native_cycle_at": initialized.isoformat(),
                "physical_start": (end - dt.timedelta(minutes=15)).isoformat(),
                "physical_end": end.isoformat(),
                "statistic": "lowest_visibility_during_15_minute_period",
                "vis_category": int(parsed["VIS"][index]),
                "cig_category": int(parsed["CIG"][index]),
                "probability_percent": probabilities,
            })
            previous_end = end
    return records


def parse_lav(text, stations=None):
    """Retain native bulletin minute, actual columns and product values."""
    matches = list(LAV_HEADER.finditer(text))
    if not matches:
        raise ValueError("no native LAV bulletin headers")
    records = []
    for index, match in enumerate(matches):
        station, month, day, year, hhmm = match.groups()
        if stations is not None and station not in stations:
            continue
        initialized = timestamp(month, day, year, hhmm)
        block = text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        lines = {line[1:4].strip(): line for line in block.splitlines() if len(line) >= 5}
        hours = lines["UTC"][5:].split()
        values = {field: fixed_cells(lines[field], 5, len(hours)) for field in ("VIS", "CIG")}
        for field in ("TMP", "DPT", "P01", "WDR", "WSP"):
            if field in lines:
                values[field] = fixed_cells(lines[field], 5, len(hours))
        previous_time = initialized
        for offset, hour in enumerate(hours):
            valid = advance_hour(previous_time, hour)
            guidance = {name: int(items[offset]) for name, items in values.items()}
            records.append({
                "station": station,
                "native_cycle_at": initialized.isoformat(),
                "valid_at": valid.isoformat(),
                "statistic": "categorical_visibility_at_hour",
                "guidance_values": guidance,
                "missing_or_invalid_categorical_fields": [
                    name for name, maximum in (("VIS", 7), ("CIG", 8))
                    if not 1 <= guidance[name] <= maximum
                ],
                "guidance_values_are_raw_encodings": True,
                "reference_kind": "operational_model_guidance",
                "support_assumption": "exact_product_encoding_not_physical_truth",
                "visible_information_scope": "native_bulletin_fields_only",
                "support_rule_version": "lamp_native_text_v1",
            })
            previous_time = valid
    return records
