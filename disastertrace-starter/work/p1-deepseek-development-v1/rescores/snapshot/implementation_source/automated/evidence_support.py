"""Restricted, deterministic citation support for frozen NHC observation tasks."""

from __future__ import annotations

import hashlib
import math
import re

from .common import fingerprint
from .dynamic import aware, validate_episode

EVIDENCE_POLICY_VERSION = "nhc_equivalent_support_v2"
POLICY_SPEC = {
    "version": EVIDENCE_POLICY_VERSION,
    "fields": ["maximum_wind_mph", "latitude_deg", "longitude_deg", "minimum_pressure_mb"],
    "source": "latest_issued_report_actually_delivered_same_entity",
    "value": "exact_canonical_numeric_no_conversion_or_tolerance",
    "summary": "existing_source_field_locator_with_independent_restricted_grammar",
    "body": "first_affirmative_sentence_of_discussion_paragraph_restricted_grammar",
    "max_sentence_lines": 4,
    "max_sentence_chars": 600,
    "max_paragraph_lines": 24,
    "max_paragraph_chars": 1800,
    "citation": "field_phrase_through_canonical_value_unit_lines",
    "context": "declared_forecast_evolution_tails_only_no_attribution_or_observation_qualifiers",
    "unknown_grammar": "evaluator_unverifiable",
}
_NUMBER = r"\d+(?:\.\d+)?"
_WIND = re.compile(
    rf"(?:Satellite imagery indicates that )?(?P<claim>maximum sustained winds "
    rf"(?:are(?: near)?|have increased to(?: near)?) (?P<value>{_NUMBER}) mph)"
    rf"(?: \({_NUMBER} km/h\))?(?: with higher gusts)?\.",
    re.IGNORECASE,
)
_PRESSURE = re.compile(
    rf"The (?P<claim>(?:estimated |latest )?minimum central pressure"
    rf"(?: estimated from Air Force Reserve reconnaissance aircraft data"
    rf"| based on data from the NOAA Hurricane Hunter aircraft)?"
    rf" is (?P<value>{_NUMBER}) mb)(?: \({_NUMBER} inches\))?\.",
    re.IGNORECASE,
)
_POSITION = re.compile(
    rf"At (?P<local>\d{{3,4}}) (?P<ampm>AM|PM) (?P<zone>AST|EDT|EST|CDT|CST) "
    rf"\((?P<utc>\d{{4}}) UTC\), the (?:center|eye) of "
    rf"(?:Hurricane|Tropical Storm|Tropical Depression) (?P<name>[A-Za-z][A-Za-z -]*) "
    rf"was located(?: by satellite and Martinique radar"
    rf"| by an Air Force Reserve Unit Hurricane Hunter aircraft)? near "
    rf"(?P<latitude>latitude (?P<lat>{_NUMBER}) (?P<ns>North|South)), "
    rf"(?P<longitude>longitude (?P<lon>{_NUMBER}) (?P<ew>East|West))\.",
    re.IGNORECASE,
)
_NEGATIVE_CONTEXT = re.compile(
    r"\b(?:not|never|no longer|false|incorrect|previous|yesterday|earlier|hypothetical|"
    r"example|quoted|quotation|disregard|invalid|superseded|retracted|"
    r"this statement|this claim|this value|these values|those winds)\b",
    re.IGNORECASE,
)
_REFERENCE_QUALIFIER = re.compile(
    r"[.!?]\s+(?:this|these|those|that|they|such|the (?:above|preceding|previous|following))\b",
    re.IGNORECASE,
)
_SUMMARY_PATTERNS = {
    "maximum_wind_mph": re.compile(
        rf"MAXIMUM SUSTAINED WINDS\.\.\.(?P<value>{_NUMBER}) MPH"
        rf"(?:\.\.\.{_NUMBER} KM/H)?"
    ),
    "minimum_pressure_mb": re.compile(
        rf"MINIMUM CENTRAL PRESSURE\.\.\.(?P<value>{_NUMBER}) MB"
        rf"(?:\.\.\.{_NUMBER} INCHES)?"
    ),
    "position": re.compile(
        rf"LOCATION\.\.\.(?P<lat>{_NUMBER})(?P<ns>N|S) "
        rf"(?P<lon>{_NUMBER})(?P<ew>E|W)"
    ),
}
_UNITS = {
    "maximum_wind_mph": "mph",
    "latitude_deg": "degrees_north_signed",
    "longitude_deg": "degrees_east_signed",
    "minimum_pressure_mb": "mb",
}


def _span(record, field, value, start, end, citation_lines, kind):
    return {
        "record_id": record["record_id"],
        "field": field,
        "value": value,
        "unit": _UNITS[field],
        "line_start": start,
        "line_end": end,
        "citation_lines": sorted(set(citation_lines)),
        "kind": kind,
        "text": "\n".join(record["raw_text"].splitlines()[start - 1 : end]),
    }


def _summary_spans(record):
    spans = []
    lines = record["raw_text"].splitlines()
    for field in POLICY_SPEC["fields"]:
        locator = record["field_evidence"][field]
        if locator["line_start"] != locator["line_end"]:
            continue
        line = locator["line_start"]
        pattern = _SUMMARY_PATTERNS.get(field, _SUMMARY_PATTERNS["position"])
        match = pattern.fullmatch(lines[line - 1].strip())
        if match is None:
            continue
        if field == "latitude_deg":
            value = float(match["lat"]) * (-1 if match["ns"] == "S" else 1)
        elif field == "longitude_deg":
            value = float(match["lon"]) * (-1 if match["ew"] == "W" else 1)
        else:
            value = float(match["value"])
        if value == record["fields"][field]:
            spans.append(_span(record, field, value, line, line, [line], "summary"))
    return spans


def _paragraphs(record):
    lines = record["raw_text"].splitlines()
    headings = [i for i, line in enumerate(lines) if line.strip() == "DISCUSSION AND OUTLOOK"]
    if len(headings) != 1:
        return
    start = headings[0] + 1
    if start >= len(lines) or re.fullmatch(r"-+", lines[start].strip()) is None:
        return
    paragraph = []
    for number in range(start + 1, len(lines)):
        line = lines[number].strip()
        if re.fullmatch(r"[A-Z][A-Z /-]{5,}", line) or line.startswith("$$"):
            break
        if line:
            paragraph.append((number + 1, line))
        elif paragraph:
            yield paragraph
            paragraph = []
    if paragraph:
        yield paragraph


def _safe_tail(tail, storm_name):
    if not tail.strip():
        return True
    if re.search(
        r"\b(?:observation|observations|estimate|estimates|value|values|statement|claim|"
        r"according|refer|refers|describe|describes|attributed|UTC)\b",
        tail,
        re.IGNORECASE,
    ):
        return False
    storm_prefix = re.escape(storm_name) + r" (?:is|will|could) " if storm_name else r"(?!)"
    allowed = re.compile(
        rf"(?:{storm_prefix}|On the forecast track, "
        r"|A (?:north|south|east|west|northeast|northwest|southeast|southwest)ward turn is forecast "
        r"|(?:(?:Some|Additional|Rapid) )?(?:(?:rapid|slow|slight) )?"
        r"(?:strengthening|weakening) (?:is|are) (?:forecast|expected) )",
        re.IGNORECASE,
    )
    # The only abbreviation needing protection in the admitted development
    # forecast tails is U.S.; no general prose sentence tokenizer is claimed.
    sentences = re.split(r"(?<=[.!?])\s+", tail.strip().replace("U.S.", "US"))
    return all(allowed.match(sentence) is not None for sentence in sentences)


def _first_sentence(paragraph, storm_name):
    if len(paragraph) > POLICY_SPEC["max_paragraph_lines"]:
        return None
    text = " ".join(line for _, line in paragraph)
    if (
        len(text) > POLICY_SPEC["max_paragraph_chars"]
        or _NEGATIVE_CONTEXT.search(text)
        or _REFERENCE_QUALIFIER.search(text)
        or any(
            len(re.findall(r"\b" + variable + r"\b", text, re.IGNORECASE)) > 1
            for variable in (
                "maximum sustained winds",
                "minimum central pressure",
                "latitude",
                "longitude",
            )
        )
    ):
        return None
    end = re.search(r"[.!?](?=\s|$)", text)
    if end is None:
        return None
    sentence = text[: end.end()]
    if not _safe_tail(text[end.end() :], storm_name):
        return None
    if len(sentence) > POLICY_SPEC["max_sentence_chars"]:
        return None
    line_map = []
    for number, line in paragraph:
        line_map.extend([number] * (len(line) + 1))
    line_map = line_map[: len(sentence)]
    if len(set(line_map)) > POLICY_SPEC["max_sentence_lines"]:
        return None
    return sentence, line_map


def _current_position(match, record):
    if match["name"].casefold() != record.get("storm_name", "").casefold():
        return False
    observed = aware(record["issued_at"])
    if match["utc"] != observed.strftime("%H%M"):
        return False
    clock = match["local"]
    hour, minute = int(clock[:-2]), int(clock[-2:])
    if not 1 <= hour <= 12 or not 0 <= minute <= 59:
        return False
    hour = hour % 12 + (12 if match["ampm"].upper() == "PM" else 0)
    offset = {"AST": -4, "EDT": -4, "EST": -5, "CDT": -5, "CST": -6}[match["zone"].upper()]
    return (hour - offset) % 24 == observed.hour and minute == observed.minute


def _body_spans(record):
    spans = []
    for paragraph in _paragraphs(record):
        sentence_parts = _first_sentence(paragraph, record.get("storm_name", ""))
        if sentence_parts is None:
            continue
        sentence, line_map = sentence_parts
        # Unqualified NHC wind/pressure sentences inherit the report entity. A
        # conflicting named storm anywhere in that paragraph makes scope unsafe.
        names = re.findall(
            r"(?:Hurricane|Tropical Storm|Tropical Depression) ([A-Z][a-z]+)"
            r"(?= (?:is|was|will|has|had|could|would|should)\b|[.,])",
            " ".join(line for _, line in paragraph),
            re.IGNORECASE,
        )
        if any(name.casefold() != record.get("storm_name", "").casefold() for name in names):
            continue
        claims = []
        if match := _WIND.fullmatch(sentence):
            claims.append(("maximum_wind_mph", float(match["value"]), "claim"))
        elif match := _PRESSURE.fullmatch(sentence):
            claims.append(("minimum_pressure_mb", float(match["value"]), "claim"))
        elif (match := _POSITION.fullmatch(sentence)) and _current_position(match, record):
            claims.extend(
                [
                    (
                        "latitude_deg",
                        float(match["lat"]) * (-1 if match["ns"].lower() == "south" else 1),
                        "latitude",
                    ),
                    (
                        "longitude_deg",
                        float(match["lon"]) * (-1 if match["ew"].lower() == "west" else 1),
                        "longitude",
                    ),
                ]
            )
        for field, value, group in claims:
            if value != record["fields"][field]:
                continue
            start, end = match.span(group)
            spans.append(
                _span(
                    record,
                    field,
                    value,
                    line_map[0],
                    line_map[-1],
                    line_map[start:end],
                    "body_observation",
                )
            )
    return spans


def _episode_entry(episode):
    validate_episode(episode)
    return {
        "episode_sha256": fingerprint(episode),
        "records": {
            record["record_id"]: {
                "raw_text_sha256": hashlib.sha256(record["raw_text"].encode()).hexdigest(),
                "support_spans": _summary_spans(record) + _body_spans(record),
            }
            for record in episode["records"]
        },
    }


def build_evidence_index(episodes: list[dict]) -> dict:
    """Produce an auditable derived index; never mutate source records or Gold."""
    entries = {}
    for episode in episodes:
        episode_id = episode["episode_id"]
        if episode_id in entries:
            raise ValueError("duplicate episode ID in evidence index")
        entries[episode_id] = _episode_entry(episode)
    return {
        "schema_version": "nhc_evidence_index_v2",
        "policy_version": EVIDENCE_POLICY_VERSION,
        "policy_sha256": fingerprint(POLICY_SPEC),
        "episodes": entries,
    }


def validate_citation(
    episode: dict,
    checkpoint_id: str,
    field: str,
    value: float,
    citation: dict,
    *,
    index: dict | None = None,
) -> dict:
    """Validate one citation, reporting unsupported grammar separately from falsity."""

    def reject(reason):
        return {"valid": False, "reason": reason, "support_spans": []}

    if field not in _UNITS:
        return reject("unsupported_field")
    if type(value) not in (int, float) or not math.isfinite(value):
        return reject("invalid_value")
    if (
        not isinstance(citation, dict)
        or set(citation) != {"record_id", "line"}
        or not isinstance(citation["record_id"], str)
        or type(citation["line"]) is not int
    ):
        return reject("invalid_citation")
    records = {record["record_id"]: record for record in episode["records"]}
    record = records.get(citation["record_id"])
    if record is None:
        return reject("unknown_report")
    if record["storm_id"] != episode["group_id"]:
        return reject("wrong_entity")
    checkpoint = None
    delivered = set()
    for candidate in episode["checkpoints"]:
        delivered.update(candidate["arrivals"])
        if candidate["checkpoint_id"] == checkpoint_id:
            checkpoint = candidate
            break
    if checkpoint is None:
        return reject("unknown_checkpoint")
    if aware(record["issued_at"]) > aware(checkpoint["at"]):
        return reject("future_report")
    if record["record_id"] not in delivered:
        return reject("undelivered_report")
    latest = max((records[item] for item in delivered), key=lambda item: aware(item["issued_at"]))
    if latest["record_id"] != record["record_id"]:
        return reject("stale_report")
    if not 1 <= citation["line"] <= len(record["raw_text"].splitlines()):
        return reject("locator_out_of_bounds")
    if value != record["fields"][field]:
        return reject("value_mismatch")
    try:
        entry = _episode_entry(episode)
    except (ValueError, KeyError, TypeError):
        return reject("invalid_episode")
    if index is not None and (
        not isinstance(index, dict)
        or index.get("schema_version") != "nhc_evidence_index_v2"
        or index.get("policy_version") != EVIDENCE_POLICY_VERSION
        or index.get("policy_sha256") != fingerprint(POLICY_SPEC)
        or not isinstance(index.get("episodes"), dict)
        or index["episodes"].get(episode["episode_id"]) != entry
    ):
        return reject("index_mismatch")
    spans = [
        span
        for span in entry["records"][record["record_id"]]["support_spans"]
        if span["field"] == field and citation["line"] in span["citation_lines"]
    ]
    if not spans:
        return reject("evaluator_unverifiable")
    return {"valid": True, "reason": "supported_" + spans[0]["kind"], "support_spans": spans}
