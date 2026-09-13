"""Target identity includes the complete outcome support, not just its end."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def canonical_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def utc_us(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt.astimezone(timezone.utc) - epoch
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


@dataclass(frozen=True)
class TargetSpec:
    target_id: str
    entity: str
    variable: str
    units: str
    event_operator: str
    threshold: float
    spatial_support: str
    physical_start: int
    physical_end: int
    report_policy: str
    outcome_kind: str
    temporal_semantics: str
    release_event_at: int | None = None
    spatial_radius_m: float | None = None

    def __post_init__(self):
        if self.physical_start >= self.physical_end or not math.isfinite(self.threshold):
            raise ValueError("Invalid physical support or threshold")
        if self.event_operator not in {"lt", "le", "gt", "ge"}:
            raise ValueError("Invalid event predicate")
        if self.temporal_semantics not in {
            "future_physical",
            "future_product_release",
            "partial_window_nowcast",
        }:
            raise ValueError("Unknown temporal semantics")
        if self.temporal_semantics == "future_product_release" and self.release_event_at is None:
            raise ValueError("A release target requires its registered release event")
        if self.spatial_radius_m is not None and (
            not math.isfinite(self.spatial_radius_m) or self.spatial_radius_m < 0
        ):
            raise ValueError("Invalid radius")
        if any(
            not getattr(self, f)
            for f in (
                "target_id",
                "entity",
                "variable",
                "units",
                "spatial_support",
                "report_policy",
                "outcome_kind",
            )
        ):
            raise ValueError("Incomplete target identity")

    @property
    def contract_hash(self):
        payload = asdict(self)
        del payload["target_id"]
        return canonical_hash(payload)


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    target: TargetSpec
    cutoff: int

    def __post_init__(self):
        target = self.target
        if target.temporal_semantics == "future_physical":
            valid = self.cutoff < target.physical_start
        elif target.temporal_semantics == "future_product_release":
            valid = self.cutoff < target.release_event_at
        else:
            valid = target.physical_start <= self.cutoff < target.physical_end
        if not valid:
            raise ValueError("Cutoff contradicts target temporal semantics")
