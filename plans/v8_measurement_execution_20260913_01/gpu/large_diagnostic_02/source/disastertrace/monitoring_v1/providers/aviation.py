"""Native report-value semantics and full applicable TAF change groups.

Intervals describe encoded product values, not error-free physical weather.
TAF conditional groups remain conditional; TEMPO never creates a probability.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from itertools import pairwise

from ..support import Interval
from ..targets import utc_us

MILE_METERS = Fraction(201168, 125)
SM = re.compile(r"(?<!\S)([PM]?)(?:(\d+)\s+)?(\d+(?:/\d+)?)SM(?!\S)")
METRIC = re.compile(r"(?<!\S)(\d{4})(?:NDV)?(?!\S)")
WIND = re.compile(r"(?:\d{3}|VRB)\d{2,3}(?:G\d{2,3})?(?:KT|MPS|KMH)")
SKY = re.compile(r"(?:(?:FEW|SCT|BKN|OVC)(?:\d{3}|///)(?:CB|TCU)?|VV(?:\d{3}|///)|SKC|CLR|NSC|NCD)")
WEATHER = re.compile(
    r"[+-]?(?:VC)?(?:(?:MI|PR|BC|DR|BL|SH|TS|FZ|DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS))+"
)
CHANGE = re.compile(r"\b(FM\d{6}|(?:BECMG|TEMPO|PROB(?:30|40)(?:\s+TEMPO)?)\s+\d{4}/\d{4})\b")


def _dt(value):
    result = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if result.tzinfo is None:
        raise ValueError("Timezone required")
    return result.astimezone(timezone.utc)


def day_time(token: str, reference: datetime) -> datetime:
    if not re.fullmatch(r"\d{4}(?:\d{2})?", token):
        raise ValueError("Invalid day/time token")
    reference = _dt(reference)
    day, hour, minute = int(token[:2]), int(token[2:4]), int(token[4:] or 0)
    if hour > 24 or minute > 59 or (hour == 24 and minute):
        raise ValueError("Invalid UTC hour/minute")
    candidates = []
    for delta in (-1, 0, 1):
        month_index = reference.year * 12 + reference.month - 1 + delta
        year, month = divmod(month_index, 12)
        try:
            value = datetime(year, month + 1, day, min(hour, 23), minute, tzinfo=timezone.utc)
        except ValueError:
            continue
        if hour == 24:
            value = value.replace(hour=0) + timedelta(days=1)
        candidates.append(value)
    if not candidates:
        raise ValueError("Invalid calendar day")
    return min(candidates, key=lambda x: abs(x - reference))


def _visibility_match(body):
    sm = SM.search(body)
    if sm:
        modifier, whole, remainder = sm.groups()
        value = (Fraction(int(whole or 0)) + Fraction(remainder)) * MILE_METERS
        meters = float(value)
        interval = (
            Interval(0, meters, upper_closed=False)
            if modifier == "M"
            else Interval(meters, math.inf, lower_closed=False)
            if modifier == "P"
            else Interval(meters, meters)
        )
        return interval, sm.span()
    cavok = re.search(r"\bCAVOK\b", body)
    if cavok:
        return Interval(10000, math.inf), cavok.span()
    metric = METRIC.search(body)
    if metric:
        value = int(metric.group(1))
        interval = (
            Interval(10000, math.inf)
            if value == 9999
            else Interval(0, 50, upper_closed=False)
            if value == 0
            else Interval(value, value)
        )
        return interval, metric.span()
    return None, None


def visibility(body: str) -> Interval | None:
    return _visibility_match(body)[0]


@dataclass(frozen=True)
class MetarReport:
    station: str
    observation_time: int
    report_type: str
    visibility: Interval | None
    temperature_c: float | None
    dewpoint_c: float | None
    weather: tuple[str, ...]
    quality_flags: tuple[str, ...]
    raw: str


def parse_metar(raw: str, *, observation_time: str, report_type: str) -> MetarReport:
    text = " ".join(raw.strip().rstrip("=").split())
    observed = _dt(observation_time)
    if report_type not in {"routine", "special"}:
        raise ValueError("Report type must come from the source contract")
    if text.startswith("SPECI ") and report_type != "special":
        raise ValueError("Native special disagrees with archive routine selection")
    header = re.search(r"\b([A-Z][A-Z0-9]{3})\s+(\d{6})Z\b", text)
    if not header or day_time(header.group(2), observed) != observed:
        raise ValueError("Native observation timestamp disagrees with source slot")
    body = re.split(r"\b(?:RMK|TEMPO|BECMG|NOSIG|FM\d{6})\b", text[header.end() :], maxsplit=1)[0]
    vis = visibility(body)
    temperature = re.search(r"(?<!\S)(M?\d{2})/(M?\d{2}|//)(?!\S)", body)

    def signed(token):
        return -int(token[1:]) if token.startswith("M") else int(token)

    temp = signed(temperature.group(1)) if temperature else None
    dew = signed(temperature.group(2)) if temperature and temperature.group(2) != "//" else None
    flags = []
    if vis is None:
        flags.append("visibility_missing")
    if "COR" in text.split():
        flags.append("correction_chronology_unproven")
    if "NIL" in text.split():
        flags.append("nil_report")
    return MetarReport(
        header.group(1),
        utc_us(observed.isoformat()),
        report_type,
        vis,
        temp,
        dew,
        tuple(t for t in body.split() if WEATHER.fullmatch(t)),
        tuple(flags),
        text,
    )


def _fields(raw, *, complete):
    body = " ".join(raw.strip().split())
    if complete and "NSW" in body.split():
        raise ValueError("NSW is not legal in a complete BASE/FM group")
    vis, span = _visibility_match(body)
    remaining = (
        body if span is None else body[: span[0]] + " " * (span[1] - span[0]) + body[span[1] :]
    )
    fields = {}
    if vis is not None:
        fields["visibility"] = vis.to_dict()
    if "CAVOK" in body.split():
        fields.update(sky=["CAVOK"], weather=[])
    weather, sky, auxiliary, unknown = [], [], [], []
    explicit_weather = False
    for token in remaining.split():
        if WIND.fullmatch(token):
            if "wind" in fields:
                raise ValueError("Conflicting winds in one TAF group")
            fields["wind"] = token
        elif SKY.fullmatch(token):
            sky.append(token)
        elif token == "NSW":
            explicit_weather = True
        elif WEATHER.fullmatch(token):
            explicit_weather = True
            weather.append(token)
        elif re.fullmatch(r"WS\d{3}/\d{3}\d{2,3}KT", token):
            fields["wind_shear"] = token
        elif re.fullmatch(r"T[XN]M?\d{2}/\d{4}Z|QNH\d{4}INS", token):
            auxiliary.append(token)
        else:
            unknown.append(token)
    if unknown:
        raise ValueError("Unsupported native TAF tokens: " + " ".join(unknown))
    if sky:
        fields["sky"] = sky
    if explicit_weather:
        fields["weather"] = weather
    if auxiliary:
        fields["auxiliary"] = auxiliary
    if complete:
        if not {"visibility", "sky", "wind"} <= fields.keys():
            raise ValueError("BASE/FM must be a complete wind/visibility/sky replacement")
        fields.setdefault("weather", [])
        fields.setdefault("wind_shear", None)
        fields.setdefault("auxiliary", [])
    return fields


@dataclass(frozen=True)
class TafClause:
    operator: str
    start: int
    end: int
    fields: dict
    raw: str
    native_probability: float | None = None


@dataclass(frozen=True)
class TafProduct:
    station: str
    issued_at: int
    valid_start: int | None
    valid_end: int | None
    amendment_kind: str
    status: str
    clauses: tuple[TafClause, ...]
    raw: str
    amendment_scheduling: str | None = None

    def project(self, start: int, end: int):
        if (
            self.status != "active"
            or start >= end
            or start < self.valid_start
            or end > self.valid_end
        ):
            raise ValueError("TAF does not cover the complete fixed target window")
        boundaries = {start, end}
        for clause in self.clauses:
            for boundary in (clause.start, clause.end):
                if start < boundary < end:
                    boundaries.add(boundary)
        boundaries = sorted(boundaries)
        segments = []
        for left, right in pairwise(boundaries):
            states = [deepcopy(self.clauses[0].fields)]
            for clause in self.clauses[1:]:
                if clause.start > left:
                    continue
                if clause.operator == "FM":
                    states = [deepcopy(clause.fields)]
                elif clause.operator == "BECMG":
                    changed = [dict(deepcopy(state), **deepcopy(clause.fields)) for state in states]
                    states = changed if left >= clause.end else states + changed
            conditional = []
            for index, clause in enumerate(self.clauses):
                scope_end = min(
                    [clause.end]
                    + [later.start for later in self.clauses[index + 1 :] if later.operator == "FM"]
                )
                if (
                    clause.operator not in {"BASE", "FM", "BECMG"}
                    and clause.start <= left < scope_end
                ):
                    conditional.append(
                        {
                            "operator": clause.operator,
                            "native_probability": clause.native_probability,
                            "states": [
                                dict(deepcopy(state), **deepcopy(clause.fields)) for state in states
                            ],
                        }
                    )
            if (
                segments
                and segments[-1]["prevailing"] == states
                and segments[-1]["conditional"] == conditional
            ):
                segments[-1]["end"] = right
            else:
                segments.append(
                    {"start": left, "end": right, "prevailing": states, "conditional": conditional}
                )
        result = {
            "station": self.station,
            "target_start": start,
            "target_end": end,
            "segments": segments,
            "rule_version": "taf_applicable_groups.v1",
        }
        if self.amendment_scheduling is not None:
            result["amendment_scheduling"] = self.amendment_scheduling
        return result


def parse_taf(raw: str, *, station: str, archive_issue: str) -> TafProduct:
    text = " ".join(raw.strip().split())
    reference = _dt(archive_issue)
    header = re.search(r"\b" + re.escape(station) + r"\s+(\d{6})Z\b", text)
    if header is None:
        raise ValueError("Native TAF station/issuance header missing")
    issued = day_time(header.group(1), reference)
    if issued != reference:
        raise ValueError("Native TAF issue disagrees with archive metadata")
    prefix = text[: header.start()].split()
    amendment = "COR" if "COR" in prefix else "AMD" if "AMD" in prefix else "original"
    body = text[header.end() :].strip().split("=", 1)[0].strip()
    window = re.match(r"(\d{4})/(\d{4})\b", body)
    if window:
        begin = day_time(window.group(1), issued)
        end = day_time(window.group(2), begin)
        if not begin < end <= begin + timedelta(hours=36):
            raise ValueError("Invalid TAF validity interval")
        body = body[window.end() :].strip()
        begin_us, end_us = utc_us(begin.isoformat()), utc_us(end.isoformat())
    else:
        begin_us = end_us = None
    if body in {"NIL", "CNL"}:
        return TafProduct(
            station,
            utc_us(issued.isoformat()),
            begin_us,
            end_us,
            amendment,
            "nil" if body == "NIL" else "canceled",
            (),
            text,
        )
    if window is None:
        raise ValueError("Active TAF requires full validity window")
    body = re.split(r"\bRMK\b", body, maxsplit=1)[0].strip()
    amendment_scheduling = None
    if body.endswith("AMD NOT SKED"):
        amendment_scheduling = "AMD NOT SKED"
        body = body[: -len("AMD NOT SKED")].strip()
    changes = list(CHANGE.finditer(body))
    first_end = changes[0].start() if changes else len(body)
    clauses = [
        TafClause(
            "BASE",
            begin_us,
            end_us,
            _fields(body[:first_end], complete=True),
            body[:first_end].strip(),
        )
    ]
    previous_prevailing_start = begin_us
    for index, match in enumerate(changes):
        marker = match.group(1)
        next_start = changes[index + 1].start() if index + 1 < len(changes) else len(body)
        content = body[match.end() : next_start].strip()
        if marker.startswith("FM"):
            operator, probability = "FM", None
            start_dt = day_time(marker[2:], issued)
            clause_start, clause_end = utc_us(start_dt.isoformat()), end_us
        else:
            operator, validity = marker.rsplit(" ", 1)
            left, right = validity.split("/")
            start_dt = day_time(left, issued)
            end_dt = day_time(right, start_dt)
            clause_start, clause_end = utc_us(start_dt.isoformat()), utc_us(end_dt.isoformat())
            probability = int(operator[4:6]) / 100 if operator.startswith("PROB") else None
        if not begin_us <= clause_start < clause_end <= end_us:
            raise ValueError("Change group outside native validity")
        if operator in {"FM", "BECMG"}:
            if clause_start < previous_prevailing_start:
                raise ValueError("Out-of-order prevailing change group")
            previous_prevailing_start = clause_start
        clauses.append(
            TafClause(
                operator,
                clause_start,
                clause_end,
                _fields(content, complete=operator == "FM"),
                content,
                probability,
            )
        )
    return TafProduct(
        station,
        utc_us(issued.isoformat()),
        begin_us,
        end_us,
        amendment,
        "active",
        tuple(clauses),
        text,
        amendment_scheduling,
    )
