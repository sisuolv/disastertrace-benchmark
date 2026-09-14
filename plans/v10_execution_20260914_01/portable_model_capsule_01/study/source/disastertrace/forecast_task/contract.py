"""Public output shape, deliberately separate from semantic correctness."""

import math
import re
from datetime import datetime

from .common import canonical, strict_json

FIELDS = ("latitude", "longitude", "max_sustained_wind")
UNITS = {"latitude": "deg", "longitude": "deg", "max_sustained_wind": "KT"}
STATUSES = ("numeric", "DISSIPATED", "ABSORBED", "not_stated")


def _object(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


SCHEMA = _object(
    {
        "storm_id": {"type": "string"},
        "valid_at": {"type": "string"},
        "measurement_kind": {"type": "string"},
        "status": {"type": "string", "enum": list(STATUSES)},
        **{
            field: _object({"value": {"type": ["number", "null"]}, "unit": {"type": "string"}})
            for field in FIELDS
        },
        "citation": {
            "anyOf": [
                {"type": "null"},
                _object(
                    {
                        "source_id": {"type": "string"},
                        "forecast_line": {"type": "integer", "minimum": 1},
                        "wind_line": {"type": ["integer", "null"], "minimum": 1},
                    }
                ),
            ]
        },
    }
)

SYSTEM = """You read official NHC forecast advisories delivered in a controlled timeline.
Answer only the requested storm and exact absolute UTC valid_at. Select the latest
issued visible advisory explicitly covering that exact valid time. A newer advisory
without that row does not erase an earlier explicit forecast. Never match by relative
lead, interpolate, copy observations/pressure, or substitute gusts for sustained wind.
All numbered source lines are evidence; prior answers in carrier are your own fallible
history, not authority. Issue time does not prove historical public availability.
Return exactly one JSON object with the supplied structure, without markdown or prose.
Use measurement_kind="forecast"; signed latitude/longitude (N/E positive, S/W negative)
in "deg" and maximum sustained wind in "KT". Use the requested absolute UTC valid_at.
status="numeric" has three numeric values. Explicit DISSIPATED or ABSORBED has three
null values and a citation to that forecast line, with wind_line=null. Terminal status
applies only to its exact valid time. If no visible product explicitly covers the key,
use status="not_stated", all values null and citation=null. Retain the required units.
A numeric citation contains source_id, forecast_line and wind_line, using the integer
L0001-style source line labels. Even an unchanged value must cite the latest covering
version. Do not output gusts, qualifiers, pressure, actions or extra fields.
Structure-only output schema: """ + canonical(SCHEMA)


def utc_stamp(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|\+00:00)", value
    ):
        raise ValueError("second-precision absolute UTC timestamp required")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()


def empty_answer(query):
    return {
        "storm_id": query["storm_id"],
        "valid_at": query["valid_at"],
        "measurement_kind": "forecast",
        "status": "not_stated",
        **{field: {"value": None, "unit": UNITS[field]} for field in FIELDS},
        "citation": None,
    }


def parse_answer(text):
    if not isinstance(text, str):
        raise TypeError("missing final text")
    try:
        answer = strict_json(text)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("invalid JSON answer") from exc
    if not isinstance(answer, dict) or set(answer) != set(SCHEMA["properties"]):
        raise ValueError("answer keys differ")
    if any(type(answer[key]) is not str for key in ("storm_id", "valid_at", "measurement_kind")):
        raise ValueError("string key fields required")
    if answer["status"] not in STATUSES:
        raise ValueError("unknown status")
    for field in FIELDS:
        value = answer[field]
        if not isinstance(value, dict) or set(value) != {"value", "unit"}:
            raise ValueError("measurement keys differ")
        number = value["value"]
        if number is not None and (
            type(number) not in (int, float)
            or (type(number) is float and not math.isfinite(number))
        ):
            raise ValueError("finite number or null required")
        if type(value["unit"]) is not str:
            raise ValueError("unit must be a string")
    citation = answer["citation"]
    if citation is not None:
        if not isinstance(citation, dict) or set(citation) != {
            "source_id",
            "forecast_line",
            "wind_line",
        }:
            raise ValueError("citation keys differ")
        if type(citation["source_id"]) is not str:
            raise ValueError("source_id must be a string")
        if type(citation["forecast_line"]) is not int or citation["forecast_line"] < 1:
            raise ValueError("positive forecast line required")
        wind_line = citation["wind_line"]
        if wind_line is not None and (type(wind_line) is not int or wind_line < 1):
            raise ValueError("positive wind line or null required")
    return answer
