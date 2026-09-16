"""Small explicit public contract, distinct from private source geometry."""

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("explicit UTC time required")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class FactKey:
    event_id: str
    product: str
    variable: str
    threshold_kt: int
    valid_at: str
    spatial_scope: str = "seed_map_extent"

    def __post_init__(self):
        utc(self.valid_at)
        if type(self.threshold_kt) is not int or self.threshold_kt <= 0:
            raise ValueError("positive integer threshold required")


@dataclass(frozen=True)
class ArtifactMeta:
    artifact_id: str
    issued_at: str
    version: int
    modality: str
    origin: str
    target: FactKey
    observation_at: str | None = None
    historical_available_at: str | None = None

    def __post_init__(self):
        utc(self.issued_at)
        if (
            type(self.version) is not int
            or self.version < 0
            or self.modality not in {"image", "text"}
        ):
            raise ValueError("invalid artifact version/modality")
        for stamp in (self.observation_at, self.historical_available_at):
            if stamp is not None:
                utc(stamp)

    def public(self):
        return asdict(self)


@dataclass(frozen=True)
class DeliveryEvent:
    delivery_id: str
    artifact_id: str
    delivered_at: str
    checkpoint: int
    schedule_origin: str = "controlled_replay"

    def __post_init__(self):
        utc(self.delivered_at)
        if type(self.checkpoint) is not int or self.checkpoint < 0:
            raise ValueError("nonnegative checkpoint required")


@dataclass(frozen=True)
class QuerySpec:
    site_id: str
    lon: float
    lat: float
    pixel: tuple[float, float]
    grid: str
    revealed_at: int

    def __post_init__(self):
        if (
            not all(math.isfinite(x) for x in (self.lon, self.lat, *self.pixel))
            or not -180 <= self.lon <= 180
            or not -90 <= self.lat <= 90
        ):
            raise ValueError("invalid site coordinates")


@dataclass(frozen=True)
class RuleSpec:
    name: str = "inspection_required"
    expression: str = "watched AND forecast_inside"
    origin: str = "benchmark_rule"


@dataclass(frozen=True)
class PublicEvidenceView:
    checkpoint: str
    target: dict
    queries: list
    evidence: list
    deliveries: list
    rule: dict
    access_track: str = "full_evidence"

    def as_dict(self):
        return asdict(self)


STATE_FIELDS = {
    "relation",
    "watched",
    "inspection_required",
    "map_source",
    "map_locator",
    "rule_source",
    "rule_locator",
}
RELATIONS = {"inside", "outside", "boundary_ambiguous", "unknown"}


@dataclass(frozen=True)
class ModelCommit:
    state: dict

    @classmethod
    def parse(cls, text):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result

        if not isinstance(text, str) or len(text.encode("utf-8")) > 65536:
            raise ValueError("invalid final text")
        data = json.loads(
            text,
            object_pairs_hook=unique,
            parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)),
        )
        if (
            not isinstance(data, dict)
            or set(data) != {"state"}
            or not isinstance(data["state"], dict)
        ):
            raise ValueError("full state object required")
        if len(data["state"]) > 64:
            raise ValueError("state exceeds common site cap")
        for key, row in data["state"].items():
            if (
                not isinstance(key, str)
                or not 1 <= len(key) <= 32
                or not isinstance(row, dict)
                or set(row) != STATE_FIELDS
            ):
                raise ValueError("invalid state fields")
            if not isinstance(row["relation"], str) or row["relation"] not in RELATIONS:
                raise ValueError("invalid spatial relation")
            for name in ("watched", "inspection_required"):
                if row[name] is not None and type(row[name]) is not bool:
                    raise ValueError("boolean or null required")
            for name in ("map_source", "map_locator", "rule_source", "rule_locator"):
                if row[name] is not None and (
                    not isinstance(row[name], str) or not 1 <= len(row[name]) <= 80
                ):
                    raise ValueError("bounded reference or null required")
        return cls(data["state"])


@dataclass(frozen=True)
class TransitionObligation:
    site_id: str
    aspect: str
    obligation: str


def tri_and(a, b):
    if any(x is not None and type(x) is not bool for x in (a, b)):
        raise ValueError("three-valued operands required")
    if a is False or b is False:
        return False
    if a is None or b is None:
        return None
    return True


def select_version(artifacts, delivered_ids, target, modality):
    matches = [
        a
        for a in artifacts
        if a["artifact_id"] in delivered_ids and a["modality"] == modality and a["target"] == target
    ]
    if not matches:
        return None
    ranks = [(utc(a["issued_at"]), a["version"]) for a in matches]
    top = max(ranks)
    winners = [a for a, rank in zip(matches, ranks) if rank == top]
    if len({a["artifact_id"] for a in winners}) != 1:
        raise ValueError("ambiguous applicable version")
    return winners[0]
