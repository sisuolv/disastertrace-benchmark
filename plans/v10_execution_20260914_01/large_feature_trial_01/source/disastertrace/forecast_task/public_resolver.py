"""Resolve only model-visible numbered text; no source parser or reference imports."""

import re
from datetime import datetime, timedelta, timezone

from .common import canonical, strict_json
from .contract import SYSTEM, empty_answer, utc_stamp

POLICIES = (
    "latest_explicit",
    "last_displayed_row",
    "same_relative_lead",
    "newest_document",
    "maximum_wind",
    "current_pressure",
    "first_covering",
    "invalid_even",
    "missing_even",
)


def _dated_time(token, reference, *, center=False):
    if not re.fullmatch(r"[0-9]{2}/[0-9]{4}Z", token):
        raise ValueError("unrecognized day-time token")
    day, hour, minute = int(token[:2]), int(token[3:5]), int(token[5:7])
    if not 1 <= day <= 31 or not 0 <= hour < 24 or not 0 <= minute < 60:
        raise ValueError("invalid day-time components")
    low = reference - timedelta(hours=6) if center else reference + timedelta(minutes=1)
    high = reference if center else reference + timedelta(days=7)
    date = low.date()
    possible = []
    while date <= high.date():
        if date.day == day:
            candidate = datetime(date.year, date.month, date.day, hour, minute, tzinfo=timezone.utc)
            if low <= candidate <= high:
                possible.append(candidate)
        date += timedelta(days=1)
    if len(possible) != 1:
        raise ValueError("day-time does not identify a unique in-window date")
    return possible[0]


def parse_document(document):
    numbered = document["numbered_text"].splitlines()
    lines = []
    for expected, item in enumerate(numbered, 1):
        label, separator, value = item.partition("|")
        if separator != "|" or label != f"L{expected:04d}":
            raise ValueError("missing, duplicated or reordered public line labels")
        lines.append(value)
    issue_hits, center_hits, storm_hits, advisory_hits, starts = [], [], [], [], []
    pressure = []
    for index, text in enumerate(lines, 1):
        text = text.strip()
        if re.fullmatch(r"[0-9]{3,4} UTC [A-Z]{3} [A-Z]{3} [0-9]{1,2} [0-9]{4}", text):
            parts = text.split()
            stamp = datetime.strptime(text, "%H%M UTC %a %b %d %Y").replace(tzinfo=timezone.utc)
            if stamp.strftime("%a").upper() != parts[2]:
                raise ValueError("public issue weekday mismatch")
            issue_hits.append(stamp)
        match = re.search(r"\b(AL[0-9]{6})$", text)
        if match:
            storm_hits.append(match[1])
        match = re.search(r"FORECAST/ADVISORY NUMBER\s+([0-9]+)$", text)
        if match:
            advisory_hits.append(int(match[1]))
        if not text.startswith(("REPEAT", "AT ")):
            match = re.search(r"\bCENTER LOCATED NEAR .* AT ([0-9]{2}/[0-9]{4}Z)$", text)
            if match:
                center_hits.append(match[1])
        if text.startswith(("FORECAST VALID", "OUTLOOK VALID")):
            starts.append(index)
        match = re.fullmatch(r"ESTIMATED MINIMUM CENTRAL PRESSURE\s+([0-9]+) MB", text)
        if match:
            pressure.append({"value": int(match[1]), "line": index})
    if any(len(values) != 1 for values in (issue_hits, center_hits, storm_hits, advisory_hits)):
        raise ValueError("unique public identity and time headers required")
    issue = issue_hits[0]
    center = _dated_time(center_hits[0], issue, center=True)
    rows = []
    for number, start in enumerate(starts):
        end = starts[number + 1] - 1 if number + 1 < len(starts) else len(lines)
        heading = re.fullmatch(
            r"(?:FORECAST|OUTLOOK) VALID ([0-9]{2}/[0-9]{4}Z)(.*)", lines[start - 1].strip()
        )
        if heading is None:
            raise ValueError("malformed forecast heading")
        valid = _dated_time(heading[1], center)
        tail = heading[2].strip()
        wind_lines = [i + 1 for i in range(start, end) if lines[i].strip().startswith("MAX WIND")]
        coords = re.fullmatch(
            r"([0-9]+(?:\.[0-9]+)?)([NS])\s+([0-9]+(?:\.[0-9]+)?)([EW])(.*)", tail
        )
        status = tail.lstrip(".").strip()
        if coords:
            if len(wind_lines) != 1:
                raise ValueError("unique forecast sustained wind required")
            wind_line = wind_lines[0]
            match = re.fullmatch(
                r"MAX WIND\s+([0-9]+) KT\.\.\.GUSTS\s+([0-9]+) KT\.",
                lines[wind_line - 1].strip(),
            )
            if match is None:
                raise ValueError("forecast wind and gust units must be KT")
            lat, lon, wind, gust = float(coords[1]), float(coords[3]), int(match[1]), int(match[2])
            if lat > 90 or lon > 180 or not 0 <= wind <= gust <= 250:
                raise ValueError("public coordinate or wind bounds invalid")
            lat *= -1 if coords[2] == "S" else 1
            lon *= -1 if coords[4] == "W" else 1
            status, qualifier = "numeric", coords[5].lstrip(".").strip()
        elif status in ("DISSIPATED", "ABSORBED") and not wind_lines:
            lat = lon = wind = gust = wind_line = None
            qualifier = ""
        else:
            raise ValueError("forecast row must have coordinates or an explicit terminal status")
        rows.append(
            {
                "valid_at": valid.isoformat(),
                "status": status,
                "latitude": lat,
                "longitude": lon,
                "max_sustained_wind": wind,
                "gust_kt": gust,
                "qualifier": qualifier,
                "forecast_line": start,
                "wind_line": wind_line,
                "lead_hours": (valid - center).total_seconds() / 3600,
            }
        )
    if not rows or [r["valid_at"] for r in rows] != sorted({r["valid_at"] for r in rows}):
        raise ValueError("forecast rows must have distinct increasing valid times")
    return {
        "source_id": document["source_id"],
        "storm_id": storm_hits[0],
        "advisory_number": advisory_hits[0],
        "issued_at": issue.isoformat(),
        "center_at": center.isoformat(),
        "rows": rows,
        "current_pressure": pressure[0] if len(pressure) == 1 else None,
    }


def _response(query, chosen):
    result = empty_answer(query)
    if chosen is not None:
        product, row = chosen
        result["status"] = row["status"]
        for field in ("latitude", "longitude", "max_sustained_wind"):
            result[field]["value"] = row[field]
        result["citation"] = {
            "source_id": product["source_id"],
            "forecast_line": row["forecast_line"],
            "wind_line": row["wind_line"],
        }
    return result


def resolve(messages, policy="latest_explicit"):
    if policy not in POLICIES:
        raise ValueError("unknown public policy")
    if (
        len(messages) != 2
        or messages[0] != {"role": "system", "content": SYSTEM}
        or messages[1]["role"] != "user"
    ):
        raise ValueError("expected exact public system/user request")
    payload = strict_json(messages[1]["content"])
    query = payload["query"]
    valid_at = utc_stamp(query["valid_at"])
    reference_at = utc_stamp(payload["checkpoint"]["forecast_reference_at"])
    if query["measurement_kind"] != "forecast" or valid_at <= reference_at:
        raise ValueError("only prospective forecast queries supported")
    products = [parse_document(document) for document in payload["documents"]]
    if len({p["source_id"] for p in products}) != len(products):
        raise ValueError("duplicate public source ID")
    scoped = [p for p in products if p["storm_id"] == query["storm_id"]]
    if len({p["issued_at"] for p in scoped}) != len(scoped):
        raise ValueError("tied product issue times unsupported")
    if any(p["issued_at"] > reference_at for p in products):
        raise ValueError("source issued after the query clock")
    by_issue = sorted(scoped, key=lambda p: p["issued_at"])
    covering = [(p, r) for p in by_issue for r in p["rows"] if r["valid_at"] == valid_at]
    chosen = covering[-1] if covering else None
    if policy == "first_covering":
        chosen = covering[0] if covering else None
    elif policy == "last_displayed_row":
        chosen = (scoped[-1], scoped[-1]["rows"][-1]) if scoped else None
    elif policy == "newest_document":
        chosen = (
            next(
                ((by_issue[-1], r) for r in by_issue[-1]["rows"] if r["valid_at"] == valid_at), None
            )
            if by_issue
            else None
        )
    elif policy == "same_relative_lead":
        chosen = (
            next(
                (
                    (by_issue[-1], r)
                    for r in by_issue[-1]["rows"]
                    if r["lead_hours"] == covering[0][1]["lead_hours"]
                ),
                None,
            )
            if covering
            else None
        )
    elif policy == "maximum_wind":
        all_rows = [
            (p, r) for p in by_issue for r in p["rows"] if r["max_sustained_wind"] is not None
        ]
        chosen = max(all_rows, key=lambda item: item[1]["max_sustained_wind"], default=None)
    result = _response(query, chosen)
    if policy == "current_pressure" and chosen and result["status"] == "numeric":
        pressure = chosen[0]["current_pressure"]
        if pressure is not None:
            result["max_sustained_wind"] = {"value": pressure["value"], "unit": "MB"}
            result["citation"]["wind_line"] = pressure["line"]
    return result


def final_text(messages, policy):
    if (
        policy == "missing_even"
        and strict_json(messages[1]["content"])["checkpoint"]["delivery_step"] % 2 == 0
    ):
        return None
    text = canonical(resolve(messages, policy))
    if (
        policy == "invalid_even"
        and strict_json(messages[1]["content"])["checkpoint"]["delivery_step"] % 2 == 0
    ):
        return "```json\n" + text + "\n```"
    return text
