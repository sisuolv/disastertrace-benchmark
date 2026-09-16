"""Regex block parser with adjacent-month candidate time resolution."""

import calendar
import re
from datetime import datetime, timedelta, timezone
from itertools import pairwise

from disastertrace.forecast_source.normalization import normalize


def _time(token, reference, lower, upper):
    match = re.fullmatch(r"(\d{2})/(\d{2})(\d{2})Z", token)
    if not match:
        raise ValueError("unsupported day/UTC time")
    day, hour, minute = map(int, match.groups())
    values = []
    for delta in (-1, 0, 1):
        index = reference.year * 12 + reference.month - 1 + delta
        year, month = index // 12, index % 12 + 1
        if not (
            1 <= day <= calendar.monthrange(year, month)[1] and 0 <= hour < 24 and 0 <= minute < 60
        ):
            continue
        value = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        if reference + lower <= value <= reference + upper:
            values.append(value)
    if len(values) != 1:
        raise ValueError("ambiguous or out-of-window absolute time")
    return values[0]


def _coordinate(value, hemisphere, latitude):
    number = float(value)
    if not 0 <= number <= (90 if latitude else 180):
        raise ValueError("coordinate out of bounds")
    return -number if hemisphere in ("S", "W") else number


def parse(raw):
    lines = normalize(raw)["text"].splitlines()
    issue, center, storm, number = [], [], [], []
    for i, line in enumerate(lines, 1):
        match = re.fullmatch(
            r"(\d{3,4}) UTC ([A-Z]{3}) ([A-Z]{3}) (\d{1,2}) (\d{4})\s*", line.strip()
        )
        if match:
            stamp = datetime.strptime(" ".join(match.groups()), "%H%M %a %b %d %Y").replace(
                tzinfo=timezone.utc
            )
            if stamp.strftime("%a").upper() != match[2]:
                raise ValueError("issue weekday disagrees with date")
            issue.append((stamp, i))
        found = re.search(r"\b(AL\d{6})\s*$", line)
        if found:
            storm.append(found[1])
        found = re.search(r"FORECAST/ADVISORY NUMBER\s+(\d+)\s*$", line)
        if found:
            number.append(int(found[1]))
        found = re.search(
            r"^(?:(?:HURRICANE|TROPICAL STORM|TROPICAL DEPRESSION|POTENTIAL TROP(?:ICAL)? CYCLONE|"
            r"POST-TROPICAL CYCLONE|SUBTROPICAL STORM|SUBTROPICAL DEPRESSION) )?"
            r"CENTER LOCATED NEAR .*\bAT (\d{2}/\d{4}Z)\b",
            line,
        )
        if found:
            center.append((found[1], i))
    if any(len(x) != 1 for x in (issue, center, storm, number)):
        raise ValueError("unique issue, center, storm and advisory headers required")
    issued, issue_line = issue[0]
    reference = _time(center[0][0], issued, timedelta(hours=-6), timedelta())
    heads = [
        (i, re.fullmatch(r"(FORECAST|OUTLOOK) VALID (\d{2}/\d{4}Z)(.*)", line.strip()))
        for i, line in enumerate(lines, 1)
        if line.strip().startswith(("FORECAST VALID", "OUTLOOK VALID"))
    ]
    rows = []
    for pos, (line_number, match) in enumerate(heads):
        if not match:
            raise ValueError("unrecognized forecast block")
        valid = _time(match[2], reference, timedelta(minutes=1), timedelta(days=7))
        tail = match[3].strip()
        location = re.fullmatch(r"(\d+(?:\.\d+)?)([NS])\s+(\d+(?:\.\d+)?)([EW])(.*)", tail)
        terminal = tail.lstrip(".").strip()
        stop = heads[pos + 1][0] - 1 if pos + 1 < len(heads) else len(lines)
        winds = [
            (
                j + 1,
                re.fullmatch(r"MAX WIND\s+(\d+) KT\.\.\.GUSTS\s+(\d+) KT\.(.*)", lines[j].strip()),
            )
            for j in range(line_number, stop)
            if lines[j].strip().startswith("MAX WIND")
        ]
        if location:
            if len(winds) != 1 or winds[0][1] is None:
                raise ValueError("unique sustained forecast wind in KT required")
            wind, gust = int(winds[0][1][1]), int(winds[0][1][2])
            if not 0 <= wind <= gust <= 250:
                raise ValueError("forecast wind bounds or gust relationship invalid")
            row = {
                "latitude": _coordinate(location[1], location[2], True),
                "longitude": _coordinate(location[3], location[4], False),
                "max_sustained_wind_kt": wind,
                "gust_kt": gust,
                "qualifier": location[5].lstrip(".").strip(),
                "wind_line": winds[0][0],
                "terminal_status": None,
            }
        elif terminal in ("DISSIPATED", "ABSORBED") and not winds:
            row = {
                "latitude": None,
                "longitude": None,
                "max_sustained_wind_kt": None,
                "gust_kt": None,
                "qualifier": "",
                "wind_line": None,
                "terminal_status": terminal,
            }
        else:
            raise ValueError("forecast coordinates or terminal status missing")
        rows.append(
            {
                **row,
                "valid_at": valid.isoformat(),
                "forecast_line": line_number,
                "lead_hours_from_center": (valid - reference).total_seconds() / 3600,
            }
        )
    if not rows or any(a["valid_at"] >= b["valid_at"] for a, b in pairwise(rows)):
        raise ValueError("nonempty strictly increasing forecast times required")
    return {
        "storm_id": storm[0],
        "advisory_number": number[0],
        "issued_at": issued.isoformat(),
        "center_at": reference.isoformat(),
        "issue_line": issue_line,
        "center_line": center[0][1],
        "forecasts": rows,
        "initialization_at": None,
        "available_at": None,
        "reference_kind": "explicit_center_time_not_assumed_model_initialization",
    }
