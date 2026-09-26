"""Frozen target identity and measurement-contract helpers for v23.

The contract is deliberately small: it records the physical event, the
report-selection rule, the source availability delay, and an explicit version.
It is used by offline scoring/roster builders so a changed event definition
cannot silently share a target identity with an older definition.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .targets import canonical_hash


@dataclass(frozen=True)
class MeasurementTargetContract:
    target_id: str
    entity: str
    variable: str
    units: str
    event_operator: str
    threshold: float
    physical_start: int
    physical_end: int
    report_policy: str
    available_at_delay_s: int
    event_version: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
            self.target_id, self.entity, self.variable, self.units,
            self.report_policy, self.event_version,
        )):
            raise ValueError("measurement contract identity fields are required")
        if self.event_operator not in {"lt", "le", "gt", "ge"}:
            raise ValueError("invalid measurement event operator")
        if not math.isfinite(self.threshold):
            raise ValueError("measurement threshold must be finite")
        if type(self.physical_start) is not int or type(self.physical_end) is not int:
            raise ValueError("measurement physical bounds must be integers")
        if self.physical_start >= self.physical_end:
            raise ValueError("measurement physical window must be nonempty")
        if type(self.available_at_delay_s) is not int or self.available_at_delay_s < 0:
            raise ValueError("measurement availability delay must be a nonnegative integer")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def contract_hash(self) -> str:
        return canonical_hash(self.to_dict())


def validate_measurement_contract(row: dict) -> str:
    """Validate and return a row's explicit contract hash.

    Rows may carry the expanded fields or only ``event_contract_hash`` after a
    roster has been sealed.  The latter must be a nonempty 64-character hash.
    """
    value = row.get("event_contract_hash")
    if value is None:
        raise ValueError("event contract hash is required for measurement rows")
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("event contract hash must be a 64-character string")
    return value
