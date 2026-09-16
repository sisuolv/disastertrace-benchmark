"""Independent HTML/token parser with day enumeration, not adjacent-month regex logic."""

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser


class Product(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside, self.blocks, self.chunks = False, 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            if self.inside:
                raise ValueError("nested PRE block")
            self.inside = True
            self.blocks += 1
        elif self.inside:
            raise ValueError("markup inside PRE")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.inside = False

    def handle_data(self, value):
        if self.inside:
            self.chunks.append(value)


def _day_time(token, base, center=False):
    date, separator, clock = token.partition("/")
    if separator != "/" or len(date) != 2 or len(clock) != 5 or clock[-1] != "Z":
        raise ValueError("unsupported UTC time token")
    if not date.isdecimal() or not clock[:-1].isdecimal():
        raise ValueError("non-numeric UTC time")
    day, hour, minute = int(date), int(clock[:2]), int(clock[2:4])
    if not 1 <= day <= 31 or not 0 <= hour < 24 or not 0 <= minute < 60:
        raise ValueError("UTC components outside bounds")
    candidates = []
    for offset in range(-1, 9):
        candidate = (base + timedelta(days=offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        hours = (candidate - base).total_seconds() / 3600
        accepted = -6 <= hours <= 0 if center else 0 < hours <= 168
        if candidate.day == day and accepted:
            candidates.append(candidate)
    if len(candidates) != 1:
        raise ValueError("absolute day resolution is ambiguous or outside bounds")
    return candidates[0]


def _location(token, latitude):
    expected = "NS" if latitude else "EW"
    index = next((i for i, character in enumerate(token) if character in expected), None)
    if index is None or index != len(token) - 1:
        raise ValueError("coordinate hemisphere missing or malformed")
    digits = token[:index]
    if digits.count(".") > 1 or not digits.replace(".", "").isdecimal():
        raise ValueError("coordinate numeric part malformed")
    value = float(digits)
    if value > (90 if latitude else 180):
        raise ValueError("coordinate outside bounds")
    return value * (-1 if token[index] in "SW" else 1)


def parse(raw):
    document = Product()
    document.feed(raw.decode("utf-8"))
    document.close()
    if document.blocks != 1 or document.inside:
        raise ValueError("one complete forecast product PRE block required")
    lines = (
        "".join(document.chunks)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\xa0", " ")
        .splitlines()
    )
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    issues, centers, storms, advisory_numbers = [], [], [], []
    headers = []
    for number, text in enumerate(lines, 1):
        words = text.split()
        if len(words) == 6 and words[1] == "UTC" and words[0].isdecimal():
            if len(words[0]) not in (3, 4) or words[3] not in months:
                raise ValueError("issue date format unsupported")
            clock = words[0].zfill(4)
            issued = datetime(
                int(words[5]),
                months.index(words[3]) + 1,
                int(words[4]),
                int(clock[:2]),
                int(clock[2:]),
                tzinfo=timezone.utc,
            )
            if weekdays[issued.weekday()] != words[2]:
                raise ValueError("issue weekday mismatch")
            issues.append((issued, number))
        if (
            words
            and len(words[-1]) == 8
            and words[-1].startswith("AL")
            and words[-1][2:].isdecimal()
        ):
            storms.append(words[-1])
        if "FORECAST/ADVISORY" in words:
            position = words.index("FORECAST/ADVISORY")
            if words[position + 1 : position + 2] != ["NUMBER"] or len(words[position + 2 :]) != 1:
                raise ValueError("advisory identifier format unsupported")
            advisory_numbers.append(int(words[-1]))
        if "CENTER" in words and not text.lstrip().startswith("REPEAT"):
            position = words.index("CENTER")
            if words[position : position + 3] == ["CENTER", "LOCATED", "NEAR"]:
                at = words.index("AT", position)
                centers.append((words[at + 1], number))
        if words[:2] in (["FORECAST", "VALID"], ["OUTLOOK", "VALID"]):
            headers.append((number, words[2:]))
    if [len(x) for x in (issues, centers, storms, advisory_numbers)] != [1, 1, 1, 1]:
        raise ValueError("missing or duplicate product identity/time headers")
    issued, issue_line = issues[0]
    center = _day_time(centers[0][0], issued, center=True)
    rows = []
    for index, (line_number, words) in enumerate(headers):
        token, *joined = " ".join(words).split("...", 1)
        fields = token.split()
        if not fields:
            raise ValueError("forecast valid time absent")
        valid = _day_time(fields[0], center)
        qualifier = joined[0].strip() if joined else ""
        end = headers[index + 1][0] - 1 if index + 1 < len(headers) else len(lines)
        wind_lines = [
            (n + 1, lines[n].strip())
            for n in range(line_number, end)
            if lines[n].strip().split()[:2] == ["MAX", "WIND"]
        ]
        if len(fields) == 3:
            latitude, longitude = _location(fields[1], True), _location(fields[2], False)
            if len(wind_lines) != 1:
                raise ValueError("one sustained wind row required")
            wind_line, wind_text = wind_lines[0]
            sustained, separator, gusts = wind_text.partition("...")
            sustained_words, gust_words = sustained.split(), gusts.rstrip(".").split()
            if (
                separator != "..."
                or len(sustained_words) != 4
                or sustained_words[:2] != ["MAX", "WIND"]
                or sustained_words[3] != "KT"
                or len(gust_words) != 3
                or gust_words[0] != "GUSTS"
                or gust_words[2] != "KT"
            ):
                raise ValueError("forecast sustained/gust units or structure differ")
            wind, gust = int(sustained_words[2]), int(gust_words[1])
            if wind < 0 or gust < wind or gust > 250:
                raise ValueError("invalid wind/gust relationship")
            terminal = None
        elif len(fields) == 1 and qualifier in ("DISSIPATED", "ABSORBED") and not wind_lines:
            latitude = longitude = wind = gust = wind_line = None
            terminal, qualifier = qualifier, ""
        else:
            raise ValueError("forecast row lacks coordinates or terminal status")
        rows.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "max_sustained_wind_kt": wind,
                "gust_kt": gust,
                "qualifier": qualifier,
                "wind_line": wind_line,
                "terminal_status": terminal,
                "valid_at": valid.isoformat(),
                "forecast_line": line_number,
                "lead_hours_from_center": (valid - center).total_seconds() / 3600,
            }
        )
    if not rows or sorted({r["valid_at"] for r in rows}) != [r["valid_at"] for r in rows]:
        raise ValueError("duplicate, reordered or empty forecast rows")
    return {
        "storm_id": storms[0],
        "advisory_number": advisory_numbers[0],
        "issued_at": issued.isoformat(),
        "center_at": center.isoformat(),
        "issue_line": issue_line,
        "center_line": centers[0][1],
        "forecasts": rows,
        "initialization_at": None,
        "available_at": None,
        "reference_kind": "explicit_center_time_not_assumed_model_initialization",
    }
