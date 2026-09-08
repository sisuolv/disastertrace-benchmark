"""Bounded source profiling and fail-closed NHC public-advisory admission.

The parser verifies a small, declared text contract. It does not certify the
scientific accuracy of an advisory or prove when it first became public.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

PARSER_VERSION = "nhc_public_summary_v1"
_MONTHS = {
    name: i for i, name in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)
}
_WEEKDAYS = "MON TUE WED THU FRI SAT SUN".split()
_OFFSETS = {
    "UTC": 0,
    "AST": -4,
    "EDT": -4,
    "EST": -5,
    "CDT": -5,
    "CST": -6,
    "MDT": -6,
    "MST": -7,
    "PDT": -7,
    "PST": -8,
    "HST": -10,
}
_CLOCK = r"(?P<clock>\d{3,4})(?:\s+(?P<meridiem>AM|PM))?\s+(?P<zone>[A-Z]{3})"
_HEADER_TIME = re.compile(
    _CLOCK + r"\s+(?P<weekday>MON|TUE|WED|THU|FRI|SAT|SUN)\s+"
    r"(?P<month>[A-Z]{3})\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})",
    re.IGNORECASE,
)
_SUMMARY = re.compile(
    r"SUMMARY OF " + _CLOCK + r"(?:\.\.\.(?P<utc>\d{4}) UTC)?\.\.\.INFORMATION",
    re.IGNORECASE,
)
_ADVISORY = re.compile(
    r"(?P<class>Hurricane|Tropical Storm|Tropical Depression|Subtropical Storm|"
    r"Subtropical Depression|Post-Tropical Cyclone|Potential Tropical Cyclone) "
    r"(?P<name>[A-Za-z0-9-]+) (?:(?:Intermediate|Special) )?"
    r"Advisory Number\s+(?P<number>[0-9]+[A-Za-z]?)",
    re.IGNORECASE,
)
_LOCATION = re.compile(r"LOCATION\.\.\.(\d+(?:\.\d+)?)([NS]) (\d+(?:\.\d+)?)([EW])")
_WIND = re.compile(r"MAXIMUM SUSTAINED WINDS\.\.\.(\d+) MPH\.\.\.(\d+) KM/H")
_MOVEMENT = re.compile(
    r"PRESENT MOVEMENT\.\.\.([A-Z]+) OR (\d+) DEGREES AT (\d+) MPH\.\.\.(\d+) KM/H"
)
_PRESSURE = re.compile(r"MINIMUM CENTRAL PRESSURE\.\.\.(\d+) MB\.\.\.(\d+\.\d+) INCHES")
_COMPASS = "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split()
_EXCLUSIONS = {
    "Q16": (
        "CONTEXT_ANSWER_SHORTCUT",
        "Answer names the port already supplied in context; control only.",
    ),
    "Q17": (
        "LANDFALL_IMPACT_SEMANTICS",
        "Landfall location and impacted coast are distinct variables.",
    ),
    "Q18": (
        "LABEL_OPTION_MISMATCH",
        "Question limits choices to A-D while the template supplies seven.",
    ),
    "Q28": (
        "ONSET_LANDFALL_SEMANTICS",
        "Tropical-storm condition onset is not time until landfall.",
    ),
}


def _unique_json_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def profile_cyportqa(template_path: Path) -> dict:
    """Inventory template declarations, never instantiated QA labels or model results."""
    raw = Path(template_path).read_bytes()
    templates = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_json_object)
    if not isinstance(templates, list):
        raise ValueError("CyPortQA template file must contain a list")
    modality_counts: Counter = Counter()
    answer_counts: Counter = Counter()
    role_counts: Counter = Counter()
    rows = []
    seen = set()
    for index, template in enumerate(templates):
        if not isinstance(template, dict):
            raise ValueError(f"template {index} must be an object")
        tags = template.get("question_type")
        modalities = template.get("modalities")
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError(f"template {index} has invalid question_type")
        ids = [tag for tag in tags if re.fullmatch(r"Q[1-9]\d*", tag)]
        if len(ids) != 1 or ids[0] in seen:
            raise ValueError(f"template {index} must have one unique template ID")
        if (
            not isinstance(modalities, list)
            or not modalities
            or not all(isinstance(m, str) and m for m in modalities)
            or len(set(modalities)) != len(modalities)
        ):
            raise ValueError(f"template {ids[0]} has invalid modalities")
        if "answer" not in template:
            raise ValueError(f"template {ids[0]} is missing its declared answer")
        template_id = ids[0]
        seen.add(template_id)
        kinds = [tag for tag in tags if tag in {"MC", "TF", "NU", "DE"}]
        kind = kinds[0] if len(kinds) == 1 else "UNRESOLVED"
        reasons = []
        if template_id in _EXCLUSIONS:
            code, detail = _EXCLUSIONS[template_id]
            reasons.append({"code": code, "detail": detail})
            role = "excluded_from_new_core"
        elif any(m.startswith("Graphic_") for m in modalities):
            role = "visual_evidence_required"
        elif modalities == ["text_advisory"]:
            role = "text_candidate_requires_source_validation"
        else:
            role = "source_format_verification_required"
        modality_counts.update(modalities)
        answer_counts.update([kind])
        role_counts.update([role])
        rows.append(
            {
                "template_id": template_id,
                "modalities": modalities,
                "answer_kind": kind,
                "role": role,
                "reason_codes": reasons,
            }
        )
    return {
        "schema_version": "cyportqa_template_profile_v1",
        "scope": "template_declarations_only",
        "selection_basis": "frozen_source_and_task_contract_before_model_results",
        "source_path": str(template_path),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "template_count": len(rows),
        "template_ids": [row["template_id"] for row in rows],
        "modality_counts": dict(sorted(modality_counts.items())),
        "answer_kind_counts": dict(sorted(answer_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
        "templates": rows,
        "limitations": [
            "Not a complete CyPortQA dataset or instantiated-label audit.",
            "Modality declarations do not prove that an original text table is available.",
            "No template is admitted as independently verified gold by this profile.",
            "Known exclusions apply to the new core; upstream labels remain inherited in any original-task comparison.",
        ],
    }


class _Reject(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _reject(code: str, detail: str) -> None:
    raise _Reject(code, detail)


def _one(candidates: list, label: str):
    if len(candidates) != 1:
        _reject(
            "MISSING_FIELD" if not candidates else "AMBIGUOUS_FIELD",
            f"Expected exactly one {label}; found {len(candidates)}",
        )
    return candidates[0]


def _clock_parts(match: re.Match) -> tuple[int, int, timezone]:
    value = match["clock"]
    hour, minute = int(value[:-2]), int(value[-2:])
    meridiem = match["meridiem"]
    zone = match["zone"].upper()
    if zone not in _OFFSETS:
        _reject("TIMEZONE_UNSUPPORTED", f"Timezone {zone} is outside the parser contract")
    if minute > 59:
        _reject("TIME_INVALID", "Clock minute must be in 00-59")
    if meridiem:
        if not 1 <= hour <= 12 or zone == "UTC":
            _reject("TIME_INVALID", "Invalid 12-hour clock or meridiem on UTC time")
        hour = hour % 12 + (12 if meridiem.upper() == "PM" else 0)
    elif zone != "UTC" or hour > 23 or len(value) != 4:
        _reject("TIME_INVALID", "Only four-digit UTC supports the 24-hour clock")
    return hour, minute, timezone(timedelta(hours=_OFFSETS[zone]))


def _locator(lines: list[str], index: int) -> dict:
    return {"line_start": index + 1, "line_end": index + 1, "text": lines[index]}


def _admit_nhc(text: str, source_id: str, source_url: str, source_sha256: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        _reject("SOURCE_MISSING", "A nonempty decoded source text is required")
    if not isinstance(source_id, str) or not source_id.strip():
        _reject("SOURCE_ID_MISSING", "A nonempty source ID is required")
    if (
        not isinstance(source_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
        or hashlib.sha256(text.encode("utf-8")).hexdigest() != source_sha256
    ):
        _reject("SOURCE_HASH_MISMATCH", "SHA256 must match exact UTF-8 text bytes")
    if not isinstance(source_url, str):
        _reject("SOURCE_URL_UNSUPPORTED", "An official NHC archive URL is required")
    try:
        parsed_url = urlparse(source_url)
    except ValueError:
        _reject("SOURCE_URL_UNSUPPORTED", "The source URL is malformed")
    path_match = re.fullmatch(
        r"/archive/(\d{4})/([a-z]{2}\d{2})/([a-z]{2}\d{6})\.public\.(\d{3}[a-z]?)\.shtml",
        parsed_url.path,
    )
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc not in {"www.nhc.noaa.gov", "nhc.noaa.gov"}
        or not path_match
        or parsed_url.query
        or parsed_url.fragment
    ):
        _reject("SOURCE_URL_UNSUPPORTED", "Expected an official NHC archive public-advisory URL")
    lines = text.splitlines()
    summary_index = _one(
        [
            i
            for i, line in enumerate(lines)
            if re.match(r"SUMMARY OF\b", line.strip(), re.I)
            and line.strip().upper() != "SUMMARY OF WATCHES AND WARNINGS IN EFFECT:"
        ],
        "summary header",
    )
    summary_match = _SUMMARY.fullmatch(lines[summary_index].strip())
    if not summary_match:
        _reject(
            "SUMMARY_FORMAT_UNSUPPORTED", "Summary must declare an unambiguous current UTC time"
        )
    header = lines[:summary_index]
    advisory_index = _one(
        [i for i, line in enumerate(lines) if re.search(r"\bAdvisory Number\b", line, re.I)],
        "advisory identity",
    )
    if advisory_index >= summary_index:
        _reject("IDENTITY_MISMATCH", "Advisory identity must precede the summary")
    advisory = _ADVISORY.fullmatch(lines[advisory_index].strip())
    if not advisory:
        _reject("IDENTITY_UNSUPPORTED", "Unsupported advisory identity format")
    publisher_index = _one(
        [
            i
            for i, line in enumerate(header)
            if line.strip().startswith("NWS National Hurricane Center")
        ],
        "NHC publisher header",
    )
    storm_ids = re.findall(r"\b[A-Z]{2}\d{6}\b", lines[publisher_index])
    storm_id = _one(storm_ids, "storm ID")
    advisory_number = advisory["number"].upper()
    url_number = (
        str(int(re.match(r"\d+", path_match[4])[0])) + re.sub(r"\d", "", path_match[4]).upper()
    )
    if (
        storm_id.lower() != path_match[3]
        or storm_id[:4].lower() != path_match[2]
        or storm_id[4:] != path_match[1]
        or advisory_number != url_number
    ):
        _reject("IDENTITY_MISMATCH", "URL and source storm/year/advisory identities disagree")
    date_index = _one(
        [i for i, line in enumerate(header) if re.match(r"^\s*\d{3,4}\s+", line)],
        "dated issue header",
    )
    date_match = _HEADER_TIME.fullmatch(lines[date_index].strip())
    if not date_match:
        _reject("TIME_FORMAT_UNSUPPORTED", "Dated issue header is outside the supported format")
    hour, minute, zone = _clock_parts(date_match)
    try:
        issued_local = datetime(
            int(date_match["year"]),
            _MONTHS[date_match["month"].upper()],
            int(date_match["day"]),
            hour,
            minute,
            tzinfo=zone,
        )
    except (ValueError, KeyError):
        _reject("DATE_INVALID", "Issue date is not a valid calendar date")
    if _WEEKDAYS[issued_local.weekday()] != date_match["weekday"].upper():
        _reject("DATE_WEEKDAY_MISMATCH", "Header weekday does not agree with its calendar date")
    if issued_local.year != int(storm_id[4:]):
        _reject("IDENTITY_MISMATCH", "Storm year and local issue year disagree")
    issued_utc = issued_local.astimezone(timezone.utc)
    summary_hour, summary_minute, summary_zone = _clock_parts(summary_match)
    if (summary_hour, summary_minute, summary_zone) != (hour, minute, zone):
        _reject("ISSUED_SUMMARY_MISMATCH", "Dated header and summary local clocks disagree")
    summary_utc = summary_match["utc"]
    if summary_match["zone"].upper() == "UTC":
        if summary_utc is not None:
            _reject("AMBIGUOUS_UTC", "Summary contains duplicate UTC fields")
        summary_utc = summary_match["clock"]
    if summary_utc is None:
        _reject("UTC_MISSING", "Local summary requires its explicit UTC equivalent")
    if int(summary_utc[:2]) > 23 or int(summary_utc[2:]) > 59:
        _reject("TIME_INVALID", "Summary UTC clock is invalid")
    if summary_utc != issued_utc.strftime("%H%M"):
        _reject("ISSUED_SUMMARY_MISMATCH", "Summary UTC does not match the dated issue header")

    # Only the first summary block is eligible: outlook prose can contain other values.
    start = summary_index + 1
    if start >= len(lines) or not re.fullmatch(r"-+", lines[start].strip()):
        _reject("SUMMARY_FORMAT_UNSUPPORTED", "Summary separator is missing")
    start += 1
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    field_evidence = {
        "issued_at": [_locator(lines, date_index), _locator(lines, summary_index)],
        "storm_id": _locator(lines, publisher_index),
        "advisory_id": _locator(lines, advisory_index),
    }

    def current_field(prefix: str, pattern: re.Pattern) -> tuple[re.Match, dict]:
        index = _one([i for i in range(start, end) if lines[i].strip().startswith(prefix)], prefix)
        match = pattern.fullmatch(lines[index].strip())
        if not match:
            _reject("FIELD_FORMAT_OR_UNIT_UNSUPPORTED", f"Unsupported format or units for {prefix}")
        return match, _locator(lines, index)

    position, position_locator = current_field("LOCATION", _LOCATION)
    latitude, longitude = float(position[1]), float(position[3])
    if latitude > 90 or longitude > 180:
        _reject("VALUE_OUT_OF_RANGE", "Latitude or longitude is outside geographic bounds")
    latitude *= -1 if position[2] == "S" else 1
    longitude *= -1 if position[4] == "W" else 1
    wind, wind_locator = current_field("MAXIMUM SUSTAINED WINDS", _WIND)
    wind_mph, wind_kmh = int(wind[1]), int(wind[2])
    if not 0 <= wind_mph <= 400:
        _reject("VALUE_OUT_OF_RANGE", "Wind is outside the declared 0-400 MPH parsing range")
    # NHC wind products round MPH and KM/H independently in five-unit increments.
    if abs(wind_kmh - wind_mph * 1.609344) > 6.53:
        _reject("UNIT_VALUE_MISMATCH", "Wind MPH and KM/H disagree beyond rounding bounds")
    movement, movement_locator = current_field("PRESENT MOVEMENT", _MOVEMENT)
    direction, degrees, speed_mph, speed_kmh = (
        movement[1],
        int(movement[2]),
        int(movement[3]),
        int(movement[4]),
    )
    if direction not in _COMPASS or not 0 <= degrees <= 360 or not 0 <= speed_mph <= 200:
        _reject("VALUE_OUT_OF_RANGE", "Unsupported movement direction, bearing or speed")
    compass_degrees = _COMPASS.index(direction) * 22.5
    if abs((degrees - compass_degrees + 180) % 360 - 180) > 11.25:
        _reject("DIRECTION_MISMATCH", "Compass direction and numeric bearing disagree")
    if abs(speed_kmh - speed_mph * 1.609344) > 1.31:
        _reject("UNIT_VALUE_MISMATCH", "Movement MPH and KM/H disagree beyond rounding bounds")
    pressure, pressure_locator = current_field("MINIMUM CENTRAL PRESSURE", _PRESSURE)
    pressure_mb, pressure_inches = int(pressure[1]), float(pressure[2])
    if not 800 <= pressure_mb <= 1100:
        _reject("VALUE_OUT_OF_RANGE", "Pressure is outside the declared 800-1100 MB parsing range")
    if abs(pressure_inches - pressure_mb * 0.0295299830714) > 0.020:
        _reject("UNIT_VALUE_MISMATCH", "Pressure MB and INCHES disagree beyond rounding bounds")
    fields = {
        "maximum_wind_mph": wind_mph,
        "latitude_deg": latitude,
        "longitude_deg": longitude,
        "movement_direction": direction,
        "movement_degrees": degrees,
        "movement_speed_mph": speed_mph,
        "minimum_pressure_mb": pressure_mb,
    }
    for key, locator in (
        ("maximum_wind_mph", wind_locator),
        ("latitude_deg", position_locator),
        ("longitude_deg", position_locator),
        ("movement_direction", movement_locator),
        ("movement_degrees", movement_locator),
        ("movement_speed_mph", movement_locator),
        ("minimum_pressure_mb", pressure_locator),
    ):
        field_evidence[key] = locator
    return {
        "record_id": source_id,
        "source_id": source_id,
        "storm_id": storm_id,
        "storm_name": advisory["name"],
        "advisory_number": advisory_number,
        "advisory_id": f"{storm_id}:public:{advisory_number}",
        "issued_at": issued_utc.isoformat(),
        "fields": fields,
        "field_evidence": field_evidence,
        "raw_text": text,
        "provenance": {
            "source_origin": "official_record",
            "gold_origin": "derived_from_source",
            "schedule_origin": "issued_time",
            "source_url": source_url,
            "source_sha256": source_sha256,
            "availability_proven": False,
            "parser_version": PARSER_VERSION,
            "field_semantics": "current_summary_reported_at_issue_time",
            "limitations": [
                "URL and text checks assume the caller supplies authentic source bytes; this parser does not fetch or authenticate a server.",
                "Issue time is not proof of historical first public availability.",
                "Only current summary fields are parsed; future forecast cycles, warnings and port actions are outside this contract.",
                "Special/corrected formats, stationary movement, missing units and ambiguous records are quarantined rather than inferred.",
                "Parser checks do not constitute universal scientific or semantic review.",
            ],
        },
    }


def parse_nhc(text: str, *, source_id: str, source_url: str, source_sha256: str) -> dict:
    """Admit one strict NHC summary or return a machine-readable quarantine reason.

    Supply the exact UTF-8 text (not newline-normalized data), its SHA256, and its
    official archive URL. Retrieval and HTML-to-text lineage belong in the source
    manifest. The returned record contains private derived facts and is not itself
    a model request. Rejections are first-failure diagnostics, not exhaustive audits.
    """
    try:
        record = _admit_nhc(text, source_id, source_url, source_sha256)
    except _Reject as exc:
        return {
            "schema_version": "nhc_admission_v1",
            "parser_version": PARSER_VERSION,
            "source_id": source_id,
            "admitted": False,
            "record": None,
            "rejection_reasons": [{"code": exc.code, "detail": exc.detail}],
        }
    return {
        "schema_version": "nhc_admission_v1",
        "parser_version": PARSER_VERSION,
        "source_id": source_id,
        "admitted": True,
        "record": record,
        "rejection_reasons": [],
    }
