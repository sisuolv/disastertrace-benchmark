"""Versioned contracts for exact, finite weather-product evidence tasks."""

# Pydantic v2 wraps ValueError; TypeError would escape malformed-input validation.
# ruff: noqa: TRY004

from datetime import date, datetime, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    PlainValidator,
    WithJsonSchema,
    model_validator,
)


def parse_exact(value) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal, Fraction)):
        raise ValueError("exact number required; decode JSON decimals with Decimal, not float")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("finite exact number with nonzero denominator required") from exc


def parse_instant(value) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(
                value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else "")
            )
        except ValueError as exc:
            raise ValueError("invalid ISO timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def parse_day(value) -> date:
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("ISO calendar day required") from exc
        if value != parsed.isoformat():
            raise ValueError("ISO calendar day must use YYYY-MM-DD")
        return parsed
    if type(value) is not date:
        raise ValueError("calendar date required; do not infer a UTC interval")
    return value


def as_tuple(value):
    if not isinstance(value, (list, tuple)):
        raise ValueError("list or tuple required")
    return tuple(value)


Exact = Annotated[
    Fraction,
    PlainValidator(parse_exact),
    PlainSerializer(lambda v: f"{v.numerator}/{v.denominator}", return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^-?[0-9]+/[1-9][0-9]*$"}),
]
Instant = Annotated[datetime, BeforeValidator(parse_instant)]
Day = Annotated[date, BeforeValidator(parse_day)]
Name = Annotated[str, Field(min_length=1)]
Positive = Annotated[int, Field(gt=0)]
Nonnegative = Annotated[int, Field(ge=0)]
SHA256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Decision = Literal["yes", "no", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        validate_default=True,
        revalidate_instances="always",
    )


class SourceLocator(StrictModel):
    kind: Literal["whole_file", "json_pointer", "byte_range", "uint8_tile"]
    path: Name
    sha256: SHA256
    role: Literal["source_bytes", "derived_product", "episode_snapshot", "availability_proof"]
    pointer: str | None = None
    start: Nonnegative | None = None
    end: Positive | None = None
    array_shape: (
        Annotated[tuple[Positive, Positive, Positive], BeforeValidator(as_tuple)] | None
    ) = None
    frame: Nonnegative | None = None
    box: (
        Annotated[tuple[Nonnegative, Positive, Nonnegative, Positive], BeforeValidator(as_tuple)]
        | None
    ) = None

    @model_validator(mode="after")
    def check_locator(self):
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.path or self.path == ".":
            raise ValueError("locator must be a confined relative POSIX path")
        if self.kind != "uint8_tile" and any(
            v is not None for v in (self.array_shape, self.frame, self.box)
        ):
            raise ValueError("array selectors belong only to uint8_tile")
        if self.kind == "json_pointer":
            if self.pointer is None or (self.pointer and not self.pointer.startswith("/")):
                raise ValueError("RFC 6901 JSON pointer required")
            if self.start is not None or self.end is not None:
                raise ValueError("JSON pointer cannot have byte offsets")
        elif self.kind == "byte_range":
            if (
                self.pointer is not None
                or self.start is None
                or self.end is None
                or self.end <= self.start
            ):
                raise ValueError("nonempty half-open byte range required")
        elif self.kind == "uint8_tile":
            if any(v is not None for v in (self.pointer, self.start, self.end)):
                raise ValueError("array locator cannot have JSON or byte selectors")
            if self.array_shape is None or self.frame is None or self.box is None:
                raise ValueError("array locator requires shape, frame and rectangle")
            height, width, frames = self.array_shape
            y0, y1, x0, x1 = self.box
            if not (0 <= y0 < y1 <= height and 0 <= x0 < x1 <= width and self.frame < frames):
                raise ValueError("array selector outside shape")
        elif any(v is not None for v in (self.pointer, self.start, self.end)):
            raise ValueError("whole-file locator cannot have a selector")
        return self


class Capture(StrictModel):
    id: Name
    url: Name
    captured_at: Instant
    artifact: SourceLocator
    origin_range: (
        Annotated[tuple[Nonnegative, Nonnegative, Positive], BeforeValidator(as_tuple)] | None
    ) = None

    @model_validator(mode="after")
    def check_range(self):
        if self.origin_range is not None:
            start, end, total = self.origin_range
            if not start <= end < total:
                raise ValueError("invalid inclusive HTTP Content-Range")
        return self


class Availability(StrictModel):
    lower: Instant
    upper: Instant
    proof: SourceLocator

    @model_validator(mode="after")
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError("availability interval reversed")
        return self


class Support(StrictModel):
    kind: Literal["instant", "station_day", "product_date", "tile"]
    label: Name
    valid_at: Instant | None = None
    day: Day | None = None
    box: (
        Annotated[tuple[Nonnegative, Positive, Nonnegative, Positive], BeforeValidator(as_tuple)]
        | None
    ) = None

    @model_validator(mode="after")
    def typed_support(self):
        if self.kind in ("instant", "tile"):
            if self.valid_at is None or self.day is not None:
                raise ValueError("instant/tile support needs a timezone-aware valid time")
        elif self.day is None or self.valid_at is not None:
            raise ValueError("calendar support requires a date, not an inferred UTC interval")
        if self.kind == "tile":
            if self.box is None or self.box[0] >= self.box[1] or self.box[2] >= self.box[3]:
                raise ValueError("tile requires a positive half-open rectangle")
        elif self.box is not None:
            raise ValueError("only tile support may carry a rectangle")
        return self

    @property
    def key(self):
        return self.kind, self.valid_at, self.day, self.box

    @property
    def size(self) -> int:
        if self.box is None:
            raise ValueError("support has no pixel size")
        y0, y1, x0, x1 = self.box
        return (y1 - y0) * (x1 - x0)


Supports = Annotated[tuple[Support, ...], BeforeValidator(as_tuple), Field(min_length=1)]
Locators = Annotated[tuple[SourceLocator, ...], BeforeValidator(as_tuple), Field(min_length=1)]


class TargetBase(StrictModel):
    entity: Name
    variable: Name
    unit: Name
    supports: Supports

    @model_validator(mode="after")
    def unique_supports(self):
        if len({s.key for s in self.supports}) != len(self.supports):
            raise ValueError("duplicate normalized target support")
        return self


class RevisionTarget(TargetBase):
    operator: Literal["revision_delta"]
    versions: Annotated[tuple[Name, Name], BeforeValidator(as_tuple)]
    threshold: Exact

    @model_validator(mode="after")
    def exact_pair(self):
        if len(self.supports) != 1 or self.versions[0] == self.versions[1]:
            raise ValueError("revision requires one support and two distinct ordered versions")
        if self.supports[0].kind != "instant":
            raise ValueError("revision v1 requires an exact valid instant")
        return self


class CountTarget(TargetBase):
    operator: Literal["count_threshold"]
    value_threshold: Exact
    count_threshold: Nonnegative

    @model_validator(mode="after")
    def bounded_count(self):
        if self.count_threshold > len(self.supports):
            raise ValueError("count threshold exceeds support count")
        if any(s.kind == "tile" for s in self.supports):
            raise ValueError("tile counts require area_threshold")
        return self


class AreaTarget(TargetBase):
    operator: Literal["area_threshold"]
    height: Positive
    width: Positive
    fraction_threshold: Exact

    @property
    def total_pixels(self) -> int:
        return self.height * self.width

    @model_validator(mode="after")
    def full_partition(self):
        if not 0 <= self.fraction_threshold <= 1:
            raise ValueError("fraction threshold must be in [0, 1]")
        if any(s.kind != "tile" for s in self.supports):
            raise ValueError("area support must be a tile")
        if len({s.valid_at for s in self.supports}) != 1:
            raise ValueError("area partition must have one valid instant")
        for i, support in enumerate(self.supports):
            y0, y1, x0, x1 = support.box
            if y1 > self.height or x1 > self.width:
                raise ValueError("tile outside target domain")
            for other in self.supports[:i]:
                a, b, c, d = other.box
                if max(y0, a) < min(y1, b) and max(x0, c) < min(x1, d):
                    raise ValueError("overlapping spatial supports")
        if sum(s.size for s in self.supports) != self.total_pixels:
            raise ValueError("spatial support is not a complete partition")
        return self


Target = Annotated[RevisionTarget | CountTarget | AreaTarget, Field(discriminator="operator")]


class PixelCounts(StrictModel):
    positive: Nonnegative
    negative: Nonnegative


class Record(StrictModel):
    entity: Name
    variable: Name
    unit: Name
    support: Support
    version: Name
    quality: Literal["valid", "missing", "invalid"]
    value: Exact | PixelCounts | None
    locators: Locators

    @model_validator(mode="after")
    def quality_value(self):
        if self.quality == "valid" and self.value is None:
            raise ValueError("valid record requires a value")
        if self.quality == "missing" and self.value is not None:
            raise ValueError("missing record cannot carry a value")
        if self.support.kind == "tile":
            if self.value is not None:
                if not isinstance(self.value, PixelCounts):
                    raise ValueError("tile record needs positive/negative counts")
                if self.value.positive + self.value.negative > self.support.size:
                    raise ValueError("counts exceed support size")
        elif isinstance(self.value, PixelCounts):
            raise ValueError("scalar record cannot carry pixel counts")
        return self


class Card(StrictModel):
    id: Name
    cost: Positive
    title: Name
    source_id: Name
    issued_at: Instant | None
    issue_label: Name
    issue_missing_reason: Name | None
    availability: Availability | None
    availability_missing_reason: Name | None
    delivery_step: Nonnegative
    captures: Annotated[tuple[Capture, ...], BeforeValidator(as_tuple)]
    records: Annotated[tuple[Record, ...], BeforeValidator(as_tuple), Field(min_length=1)]

    @model_validator(mode="after")
    def missing_clocks(self):
        if (self.issued_at is None) != (self.issue_missing_reason is not None):
            raise ValueError("issue time must have a missing reason exactly when unknown")
        if (self.availability is None) != (self.availability_missing_reason is not None):
            raise ValueError("availability must have a missing reason exactly when unknown")
        if self.availability and self.issued_at and self.availability.upper < self.issued_at:
            raise ValueError("proved public availability cannot precede product issue")
        return self


def eligible(card: Card, policy: str, as_of: datetime | None, delivery_step: int) -> bool:
    if card.delivery_step > delivery_step:
        return False
    if policy == "archive_delivery":
        return True
    return bool(
        card.availability is not None
        and card.availability.upper <= as_of
        and (card.issued_at is None or card.issued_at <= as_of)
    )


def compatible(record: Record, target: TargetBase) -> bool:
    return (
        (record.entity, record.variable, record.unit)
        == (target.entity, target.variable, target.unit)
        and record.support.key in {s.key for s in target.supports}
        and (not isinstance(target, RevisionTarget) or record.version in target.versions)
    )


class Episode(StrictModel):
    schema_version: Literal["active_forecast.v1"]
    id: Name
    family: Name
    group: Name
    variant: Name
    split: Literal["development", "validation", "test"]
    origin: Literal["real", "synthetic"]
    question: Name
    time_policy: Literal["archive_delivery", "historical_asof"]
    as_of: Instant | None
    delivery_step: Nonnegative
    target: Target
    cards: Annotated[tuple[Card, ...], BeforeValidator(as_tuple), Field(min_length=1, max_length=8)]

    @model_validator(mode="after")
    def finite_pool(self):
        if (self.time_policy == "historical_asof") != (self.as_of is not None):
            raise ValueError(
                "as_of belongs only to historical_asof; archive delivery uses logical steps"
            )
        if len({c.id for c in self.cards}) != len(self.cards):
            raise ValueError("duplicate card identity")
        if self.origin == "real" and any(not c.captures for c in self.cards):
            raise ValueError("real product cards require original capture bindings")
        seen = set()
        for card in self.cards:
            if not eligible(card, self.time_policy, self.as_of, self.delivery_step):
                continue
            for record in card.records:
                if not compatible(record, self.target):
                    continue
                key = (
                    (record.support.key, record.version)
                    if isinstance(self.target, RevisionTarget)
                    else record.support.key
                )
                if key in seen:
                    raise ValueError(
                        "overlapping product support requires an explicit fusion policy"
                    )
                seen.add(key)
        return self


class Answer(StrictModel):
    decision: Decision
    citations: Annotated[tuple[Name, ...], BeforeValidator(as_tuple)]

    @model_validator(mode="after")
    def distinct_citations(self):
        if len(set(self.citations)) != len(self.citations):
            raise ValueError("duplicate citation")
        return self
