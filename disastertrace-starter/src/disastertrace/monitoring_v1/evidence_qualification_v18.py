"""Versioned evidence qualification for the v18 current-v13 port.

The existing monitoring engine keeps source assets and forecast state.  This
module adds the missing semantic witness between those layers: whether an
arrival changes the target-relevant content.  It is deliberately pure and
does not read files, call providers, or infer a missing timestamp as
``no_change``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping


_TIME_KEYS = {
    "issued_at",
    "available_at",
    "observed_at",
    "completed_at",
    "fetched_at",
    "published_at",
}
_IDENTITY_KEYS = {
    "source_id",
    "source_revision",
    "asset_id",
    "record_id",
    "receipt_id",
    "raw_sha256",
}
_NON_TARGET_KEYS = {
    "non_target",
    "formatting",
    "transport",
    "debug",
    "length_sham",
    "raw",
}
# Fields kept in weather_content_only()'s output (the agent-visible
# projection: public_checkpoint/public_prefix send exactly this) but
# excluded from the SEPARATE comparison basis used to decide
# TARGET_CONTENT_CHANGE/DUPLICATE and by build_v18_dev_episodes.py's own
# duplicate-detection hash (Track B-0, v20 plan; corrected after an
# independent review found the first version of this fix wrongly hid these
# fields from the agent too, not just from the comparison -- ftype in
# particular is real TAF group-type information (Observation/Forecast/
# Temporary/Probability), not administrative noise, and must stay visible).
_ADMINISTRATIVE_COMPARISON_ONLY_KEYS = {
    "is_amendment",
    "ftype",
    "source_row_is_tempo",
}
_INTERVAL_KEYS = (
    ("valid_start", "valid_end"),
    ("start", "end"),
    ("from", "to"),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _as_int(value: Any, name: str, *, required: bool = True) -> int | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer timestamp")
    return value


@dataclass(frozen=True)
class EvidenceRecord:
    """A normalized evidence arrival.

    ``issued_at`` describes product time.  ``available_at`` controls when the
    record may enter an agent view and may be unknown; the two are never
    substituted for one another.
    """

    source_id: str
    source_revision: str
    kind: str
    issued_at: int
    available_at: int | None
    content: Mapping[str, Any]
    valid_start: int | None = None
    valid_end: int | None = None
    relation_status: str = "unknown"

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.source_id, self.source_revision, self.kind)
        ):
            raise ValueError("Evidence identity is required")
        _as_int(self.issued_at, "issued_at")
        _as_int(self.available_at, "available_at", required=False)
        if self.available_at is not None and self.available_at < self.issued_at:
            raise ValueError("available_at cannot precede issued_at")
        _as_int(self.valid_start, "valid_start", required=False)
        _as_int(self.valid_end, "valid_end", required=False)
        if self.valid_start is not None and self.valid_end is not None:
            if self.valid_start >= self.valid_end:
                raise ValueError("Evidence validity interval must be increasing")
        if not isinstance(self.content, Mapping):
            raise ValueError("Evidence content must be a mapping")
        if self.relation_status not in {
            "unknown",
            "normal",
            "duplicate",
            "revision",
            "cancellation",
            "conflict",
        }:
            raise ValueError("Unknown relation status")

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "EvidenceRecord":
        """Normalize a dict without treating absent availability as arrival."""

        return cls(
            source_id=row.get("source_id", ""),
            source_revision=row.get("source_revision", row.get("revision", "")),
            kind=row.get("kind", row.get("product_kind", "")),
            issued_at=_as_int(row.get("issued_at"), "issued_at"),  # type: ignore[arg-type]
            available_at=_as_int(row.get("available_at"), "available_at", required=False),
            valid_start=_as_int(row.get("valid_start"), "valid_start", required=False),
            valid_end=_as_int(row.get("valid_end"), "valid_end", required=False),
            content=row.get("content", {}),
            relation_status=str(row.get("relation_status", "unknown")),
        )

    def identity(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "kind": self.kind,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _interval(row: Mapping[str, Any]) -> tuple[int, int] | None:
    for left, right in _INTERVAL_KEYS:
        if left in row and right in row:
            if isinstance(row[left], int) and isinstance(row[right], int):
                return row[left], row[right]
    return None


def _overlaps(start: int, end: int, target_start: int, target_end: int) -> bool:
    return start < target_end and target_start < end


def weather_content_only(value: Any) -> Any:
    """Remove provenance fields while preserving weather semantics.

    This is what an agent actually sees (public_checkpoint/public_prefix
    project exactly this) -- it must never drop information a reader would
    consider part of the weather picture, even if that information is
    redundant with something else kept (e.g. ftype vs operator). Use
    comparison_content_only(), not this function, for change-detection
    hashing, which is allowed to be stricter than what the agent sees.
    """

    if isinstance(value, Mapping):
        return {
            str(key): weather_content_only(item)
            for key, item in value.items()
            if key not in _TIME_KEYS and key not in _IDENTITY_KEYS and key not in _NON_TARGET_KEYS
        }
    if isinstance(value, list):
        return [weather_content_only(item) for item in value]
    return value


def comparison_content_only(value: Any) -> Any:
    """Strictly narrower than weather_content_only(): also drops fields that
    are redundant with something already compared (e.g. ftype duplicates
    operator) or purely administrative (is_amendment, source_row_is_tempo),
    so a same-weather-content re-issue with only these flipped is correctly
    judged unchanged. Only for change-detection hashing -- never for
    anything an agent, or a report, will read as "the evidence".
    """

    stripped = weather_content_only(value)

    def _drop_administrative(inner: Any) -> Any:
        if isinstance(inner, Mapping):
            return {
                str(key): _drop_administrative(item)
                for key, item in inner.items()
                if key not in _ADMINISTRATIVE_COMPARISON_ONLY_KEYS
            }
        if isinstance(inner, list):
            return [_drop_administrative(item) for item in inner]
        return inner

    return _drop_administrative(stripped)


def _project_interval(value: Mapping[str, Any], target_start: int, target_end: int) -> dict[str, Any]:
    """Clip an overlapping interval so outside-target extensions are ignored."""

    interval = _interval(value)
    if interval is None:
        result = weather_content_only(value)
        return result if isinstance(result, dict) else {"content": result}
    start, end = interval
    result = weather_content_only(value)
    if not isinstance(result, dict):
        return {"content": result}
    for left, right in _INTERVAL_KEYS:
        if left in value and right in value:
            result[left] = max(start, target_start)
            result[right] = min(end, target_end)
            break
    return result


def _project(value: Any, target_start: int, target_end: int) -> Any:
    """Project interval-bearing content onto the target window."""

    if isinstance(value, list):
        projected = []
        saw_interval = False
        for item in value:
            if isinstance(item, Mapping):
                interval = _interval(item)
                if interval is not None:
                    saw_interval = True
                    if _overlaps(*interval, target_start, target_end):
                        projected.append(_project_interval(item, target_start, target_end))
                else:
                    projected.append(_project(item, target_start, target_end))
            else:
                projected.append(_project(item, target_start, target_end))
        return projected if saw_interval else [weather_content_only(item) for item in projected]
    if isinstance(value, Mapping):
        interval = _interval(value)
        if interval is not None:
            return _project_interval(value, target_start, target_end) if _overlaps(*interval, target_start, target_end) else None
        return {
            str(key): _project(item, target_start, target_end)
            for key, item in value.items()
            if key not in _TIME_KEYS and key not in _IDENTITY_KEYS and key not in _NON_TARGET_KEYS
        }
    return value


def target_content_projection(
    record: EvidenceRecord | Mapping[str, Any], target_start: int, target_end: int
) -> dict[str, Any]:
    """Return canonical target-relevant content plus an explicit relevance state."""

    if target_start >= target_end:
        raise ValueError("Target interval must be increasing")
    evidence = record if isinstance(record, EvidenceRecord) else EvidenceRecord.from_mapping(record)
    if evidence.valid_start is not None and evidence.valid_end is not None:
        if not _overlaps(evidence.valid_start, evidence.valid_end, target_start, target_end):
            return {"relevance": "outside_target", "content": {}}
    projected = _project(evidence.content, target_start, target_end)
    if projected is None:
        projected = {}
    return {"relevance": "target", "content": projected}


@dataclass(frozen=True)
class EvidenceQualification:
    status: str
    availability: str
    source_change: bool | None
    target_content_change: bool | None
    current_source_hash: str
    previous_source_hash: str | None
    current_projection_hash: str | None
    previous_projection_hash: str | None
    witness: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _availability(record: EvidenceRecord, as_of: int | None) -> str:
    if record.available_at is None:
        return "unknown"
    if as_of is None:
        return "known"
    if record.available_at > as_of:
        return "not_yet_available"
    return "available"


def qualify_evidence(
    current: EvidenceRecord | Mapping[str, Any],
    previous: EvidenceRecord | Mapping[str, Any] | None,
    *,
    target_start: int,
    target_end: int,
    as_of: int | None = None,
) -> EvidenceQualification:
    """Classify an arrival without collapsing unknowns into no-change."""

    now = current if isinstance(current, EvidenceRecord) else EvidenceRecord.from_mapping(current)
    prior = None if previous is None else (
        previous if isinstance(previous, EvidenceRecord) else EvidenceRecord.from_mapping(previous)
    )
    current_projection = target_content_projection(now, target_start, target_end)
    previous_projection = (
        None if prior is None else target_content_projection(prior, target_start, target_end)
    )
    current_source_hash = _hash(now.identity())
    previous_source_hash = None if prior is None else _hash(prior.identity())
    # Hashed for change-detection via comparison_content_only(), stricter than
    # what current_projection["content"] itself holds (the agent-visible
    # projection, unchanged) -- so a same-weather-content re-issue with only
    # is_amendment/ftype/source_row_is_tempo flipped doesn't look changed,
    # without hiding those fields from anything that reads the projection
    # itself (Track B-0, v20 plan, corrected after independent review).
    current_projection_hash = _hash(comparison_content_only(current_projection["content"]))
    previous_projection_hash = (
        None if previous_projection is None
        else _hash(comparison_content_only(previous_projection["content"]))
    )
    availability = _availability(now, as_of)
    source_change = prior is None or now.identity() != prior.identity()
    if availability == "unknown":
        status = "UNKNOWN_AVAILABILITY"
        content_change: bool | None = None
    elif availability == "not_yet_available":
        status = "NOT_YET_AVAILABLE"
        content_change = None
    elif now.relation_status == "conflict":
        status = "CONFLICT"
        content_change = True if prior is not None else None
    elif prior is None:
        status = (
            "NEW_TARGET_CONTENT" if current_projection["relevance"] == "target" else "NEW_IRRELEVANT_SOURCE"
        )
        content_change = True if current_projection["relevance"] == "target" else False
    else:
        content_change = current_projection_hash != previous_projection_hash
        if current_projection["relevance"] == "outside_target":
            # A new product outside the target support is a source event, not
            # a target-content event, even when its raw body differs.
            content_change = False
            status = "TARGET_IRRELEVANT_CHANGE" if source_change else "DUPLICATE"
        elif content_change:
            status = "TARGET_CONTENT_CHANGE"
        elif source_change:
            status = "SOURCE_CHANGE_NO_TARGET_CHANGE"
        else:
            status = "DUPLICATE"
    witness = {
        "source_identity": now.identity(),
        "previous_source_identity": None if prior is None else prior.identity(),
        "relation_status": now.relation_status,
        "issued_at": now.issued_at,
        "available_at": now.available_at,
        "as_of": as_of,
        "target_start": target_start,
        "target_end": target_end,
        "current_relevance": current_projection["relevance"],
        "previous_relevance": None if previous_projection is None else previous_projection["relevance"],
        "current_projection": current_projection["content"],
        "previous_projection": None if previous_projection is None else previous_projection["content"],
    }
    return EvidenceQualification(
        status=status,
        availability=availability,
        source_change=source_change,
        target_content_change=content_change,
        current_source_hash=current_source_hash,
        previous_source_hash=previous_source_hash,
        current_projection_hash=current_projection_hash,
        previous_projection_hash=previous_projection_hash,
        witness=witness,
    )


def qualify_stream(
    records: list[EvidenceRecord | Mapping[str, Any]],
    *,
    target_start: int,
    target_end: int,
    as_of: int | None = None,
) -> list[EvidenceQualification]:
    """Qualify a chronological stream, retaining every row and its witness."""

    previous_target: EvidenceRecord | None = None
    previous_arrival: EvidenceRecord | None = None
    # Unknown availability is a legitimate value, so it cannot be used as a
    # chronology key. Keep the last known key separately: an unknown row in
    # between two known rows must not hide a reordering.
    last_known_available: int | None = None
    last_known_issued_at: int | None = None
    latest_by_available: dict[int, EvidenceRecord] = {}
    out: list[EvidenceQualification] = []
    for row in records:
        current = row if isinstance(row, EvidenceRecord) else EvidenceRecord.from_mapping(row)
        if current.available_at is not None:
            # This API consumes an arrival stream. An old bulletin can arrive
            # after a newer issuance, so issued_at is metadata rather than
            # the chronology key. Equal-time arrivals remain auditable.
            if last_known_available is not None and current.available_at < last_known_available:
                raise ValueError("Evidence stream is not chronological by available_at")
            if (
                last_known_available is not None
                and current.available_at == last_known_available
                and last_known_issued_at is not None
                and current.issued_at < last_known_issued_at
            ):
                raise ValueError("Evidence stream is not chronological by issued_at at equal arrival time")
            same_time = latest_by_available.get(current.available_at)
            if (
                same_time is not None
                and current.source_id == same_time.source_id
                and current.identity() != same_time.identity()
                and current.relation_status not in {"duplicate", "revision", "cancellation"}
            ):
                raise ValueError("Conflicting evidence arrivals share the same chronology key")
            if (
                same_time is not None
                and current.identity() == same_time.identity()
                and _canonical(current.content) != _canonical(same_time.content)
                and current.relation_status != "conflict"
            ):
                raise ValueError("Conflicting content shares the same evidence identity and chronology key")
        result = qualify_evidence(
            current,
            previous_target,
            target_start=target_start,
            target_end=target_end,
            as_of=as_of,
        )
        out.append(result)
        previous_arrival = current
        if current.available_at is not None:
            last_known_available = current.available_at
            last_known_issued_at = current.issued_at
            latest_by_available[current.available_at] = current
        if result.availability in {"available", "known"} and result.witness.get("current_relevance") == "target":
            # An irrelevant arrival advances the source stream but cannot
            # replace the previous target projection.
            previous_target = current
    return out
