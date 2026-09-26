"""Frozen, source-only contracts used by the v23 DisasterTrace run.

This module contains calendar and availability rules only.  It does not open
weather files and it does not bind an outcome.  Real readers must still pass
through the task-specific AccessPolicy allowlist.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from ..monitoring_v1.measurement_contract_v23 import MeasurementTargetContract
from ..monitoring_v1.targets import utc_us

STATIONS = ("KDEN", "KJFK", "KORD", "KSFO")
MONTHS = ("2025-01", "2025-03")
LEAD_HOURS = (6, 3, 1, 1 / 3)
LEAD_LABELS = ("-6h", "-3h", "-1h", "-20m")
EVENT_VERSION = "h15.visibility.v23"
REPORT_POLICY = "iem_routine_unique_hour.v1"
METAR_AVAILABLE_DELAY_S = 600
VISIBILITY_THRESHOLD_M = 5000.0


def month_hour_starts(*, stations: Iterable[str] = STATIONS, months: Iterable[str] = MONTHS) -> list[dict]:
    """Enumerate the pre-registered hourly target grid in deterministic order."""
    rows: list[dict] = []
    for station in stations:
        if station not in STATIONS:
            raise ValueError(f"station outside v23 calendar: {station}")
        for month in months:
            try:
                year, month_number = (int(part) for part in month.split("-"))
                days = monthrange(year, month_number)[1]
            except Exception as exc:
                raise ValueError(f"invalid v23 month: {month}") from exc
            if month not in MONTHS:
                raise ValueError(f"month outside v23 calendar: {month}")
            for day in range(1, days + 1):
                for hour in range(24):
                    start = datetime(year, month_number, day, hour, tzinfo=timezone.utc)
                    start_us = int(start.timestamp() * 1_000_000)
                    rows.append({
                        "target_id": f"{station}_{start:%Y%m%d_%H}_5000m",
                        "station": station,
                        "month": month,
                        "physical_start_us": start_us,
                        "physical_end_us": start_us + 3_600_000_000,
                        "event_version": EVENT_VERSION,
                    })
    return rows


def checkpoint_rows(target: dict) -> list[dict]:
    """Return the four cutoff rows for one frozen target."""
    result = []
    for label, hours in zip(LEAD_LABELS, LEAD_HOURS, strict=True):
        cutoff = target["physical_start_us"] - int(hours * 3_600_000_000)
        result.append({
            "target_id": target["target_id"],
            "checkpoint_id": label,
            "checkpoint_index": len(result),
            "cutoff_us": cutoff,
            "lead_hours": hours,
        })
    return result


def metar_available_at(valid_us: int, *, delay_s: int = METAR_AVAILABLE_DELAY_S) -> int:
    if type(valid_us) is not int or type(delay_s) is not int or delay_s < 0:
        raise ValueError("METAR valid time and delay must be integer values")
    return valid_us + delay_s * 1_000_000


def visible_metar(valid_us: int, cutoff_us: int, *, delay_s: int = METAR_AVAILABLE_DELAY_S) -> bool:
    return metar_available_at(valid_us, delay_s=delay_s) <= cutoff_us


def routine_window_for_observation(observation_us: int) -> tuple[int, int]:
    """Assign an observation to its UTC hour by its actual timestamp."""
    dt = datetime.fromtimestamp(observation_us / 1_000_000, tz=timezone.utc)
    start = dt.replace(minute=0, second=0, microsecond=0)
    start_us = int(start.timestamp() * 1_000_000)
    return start_us, start_us + 3_600_000_000


def target_contract(target: dict) -> MeasurementTargetContract:
    return MeasurementTargetContract(
        target_id=target["target_id"],
        entity=target["station"],
        variable="visibility",
        units="m",
        event_operator="lt",
        threshold=VISIBILITY_THRESHOLD_M,
        physical_start=target["physical_start_us"],
        physical_end=target["physical_end_us"],
        report_policy=REPORT_POLICY,
        available_at_delay_s=METAR_AVAILABLE_DELAY_S,
        event_version=target["event_version"],
    )


def validate_exact_read_path(path: str | Path, allowlist: Iterable[str]) -> Path:
    """Validate an exact path without opening it.

    This is a pure guard for the J1a synthetic contract tests.  J1b wraps real
    reads with AccessPolicy and an exact allowlist before opening any body.
    """
    candidate = Path(path)
    resolved = candidate.resolve(strict=False)
    allowed = {Path(item).resolve(strict=False) for item in allowlist}
    if candidate.is_symlink():
        raise PermissionError("symlink paths are not allowed")
    if resolved not in allowed:
        raise PermissionError(f"path is outside exact allowlist: {resolved}")
    return resolved
