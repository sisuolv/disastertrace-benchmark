"""Outcome wiring for H15 visibility targets against real ASOS observations.

Wires real ASOS METAR observations into Target/OutcomeRegistry for H15-style
visibility outcomes ("will visibility be under threshold X at hour-slot Y")
using the routine (top-of-hour) METAR report as the resolving observation.

Design decisions:
- Visibility thresholds in meters: 5000.0m and 1000.0m (frozen project decisions)
- Report selection: "one unique routine report per hour" via modal minute detection
- Modal minute is determined empirically from timestamp data only (weather-blind)
- Published/announced-at timestamps are left None for archived-report scenarios
- resolved_at comes from source data provenance, never wall-clock

Reuses:
- monitoring_fixed_v1.contracts.Target (immutable contract identity)
- monitoring_fixed_v1.outcomes.OutcomeRegistry (canonical result registration)
- monitoring_fixed_v1.outcome_policies (H15 validation requirements)
- revision_v1.contracts.build_outcome_record (record assembly helper)
- revision_v1.episode_compiler.compile_metar_outcomes (outcome logic)
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ..monitoring_fixed_v1.contracts import Target
from ..monitoring_fixed_v1.outcomes import OutcomeRegistry
from ..monitoring_v1.providers.aviation import MetarReport
from ..monitoring_v1.support import Interval, classify
from ..monitoring_v1.targets import utc_us
from .contracts import build_outcome_record

if TYPE_CHECKING:
    from typing import Any

# Frozen project thresholds (in meters)
FROZEN_THRESHOLDS_M = frozenset({5000.0, 1000.0})


def make_h15_visibility_target(
    *,
    station: str,
    slot_start_us: int,
    threshold_m: float,
    target_id: str | None = None,
) -> Target:
    """Build a Target for H15-style visibility outcome.

    Creates a Target for "visibility < threshold_m meters during the routine
    report of the 1-hour slot starting at slot_start_us".

    Args:
        station: ICAO station code (e.g., "KSFO")
        slot_start_us: Start of the 1-hour slot in microseconds since epoch
        threshold_m: Visibility threshold in meters (must be 5000.0 or 1000.0)
        target_id: Optional explicit target_id. If None, generates a
            deterministic, human-legible ID.

    Returns:
        A Target instance configured for H15 visibility evaluation.

    Raises:
        ValueError: If threshold_m is not one of the frozen thresholds.
    """
    if threshold_m not in FROZEN_THRESHOLDS_M:
        raise ValueError(
            f"Invalid threshold {threshold_m}m. "
            f"Allowed thresholds: {sorted(FROZEN_THRESHOLDS_M)}"
        )

    # One hour in microseconds
    hour_us = 3_600_000_000

    # Physical end is one hour after start (interval support)
    slot_end_us = slot_start_us + hour_us

    # Generate deterministic, human-legible target_id if not provided
    if target_id is None:
        # Format: station_YYYYMMDD_HH_thresholdm
        dt = datetime.fromtimestamp(slot_start_us / 1_000_000, tz=timezone.utc)
        target_id = f"{station}_{dt.strftime('%Y%m%d_%H')}_{int(threshold_m)}m"

    return Target(
        target_id=target_id,
        entity=station,
        variable="visibility",
        units="m",
        output_kind="event_probability",
        support_kind="interval",
        physical_start=slot_start_us,
        physical_end=slot_end_us,
        temporal_semantics="future_physical",
        report_policy="iem_routine_unique_hour.v1",
        event_operator="lt",
        threshold=threshold_m,
    )


def select_routine_observations(
    observations: list[MetarReport],
    *,
    station: str,
) -> tuple[list[MetarReport], dict]:
    """Select routine METAR observations using modal-minute heuristic.

    This function is weather-blind: it determines which minute-of-hour is the
    station's "routine" reporting minute purely from timestamp data, never
    looking at visibility or any other weather content.

    The modal minute is the most common minute-of-hour across all observations.
    Tie-break: smallest minute value wins.

    Args:
        observations: List of MetarReport objects to filter.
        station: Station code to filter for.

    Returns:
        Tuple of:
            - filtered: List of observations on the modal minute (routine reports)
            - metadata: Dict containing:
                - modal_minute: The detected routine minute (0-59)
                - modal_count: Number of observations at the modal minute
                - minute_histogram: Counter mapping minute -> count
                - station: The station code used for filtering
                - total_observations: Total input observations for this station

    Note:
        This function's purity is critical for outcome integrity. It must
        never be influenced by the outcome value (visibility).
    """
    # Filter to station (comparison uses station code from MetarReport)
    station_obs = [obs for obs in observations if obs.station == station]

    if not station_obs:
        return [], {
            "modal_minute": None,
            "modal_count": 0,
            "minute_histogram": Counter(),
            "station": station,
            "total_observations": 0,
        }

    # Extract minute-of-hour from each observation timestamp
    minute_histogram = Counter()
    for obs in station_obs:
        # observation_time is in microseconds since epoch
        dt = datetime.fromtimestamp(obs.observation_time / 1_000_000, tz=timezone.utc)
        minute_histogram[dt.minute] += 1

    # Find modal minute (most common, tie-break to smallest)
    if not minute_histogram:
        modal_minute = None
        modal_count = 0
    else:
        # Sort by (-count, minute) to get highest count, then smallest minute
        sorted_minutes = sorted(minute_histogram.items(), key=lambda x: (-x[1], x[0]))
        modal_minute, modal_count = sorted_minutes[0]

    # Filter observations to only those on the modal minute
    filtered = []
    for obs in station_obs:
        dt = datetime.fromtimestamp(obs.observation_time / 1_000_000, tz=timezone.utc)
        if dt.minute == modal_minute:
            filtered.append(obs)

    return filtered, {
        "modal_minute": modal_minute,
        "modal_count": modal_count,
        "minute_histogram": minute_histogram,
        "station": station,
        "total_observations": len(station_obs),
    }


@dataclass(frozen=True)
class AsosProvenance:
    """Provenance for an ASOS body file.

    Captures where an ASOS body file came from, its content hash, and the
    fetch timestamp from its sibling receipt.
    """

    path: str
    sha256: str
    fetch_timestamp_us: int
    run_id: str

    @property
    def source_revision(self) -> str:
        """Return the run_id as the source revision identifier."""
        return self.run_id


def load_asos_with_provenance(
    body_path: str,
    *,
    access_policy: "AccessPolicy | None" = None,
) -> tuple[str, AsosProvenance]:
    """Load an ASOS body file with provenance verification.

    Reads a real ASOS .body file plus its sibling receipt, recomputes the
    body's SHA256 and cross-checks it against the value recorded in the
    receipt.

    V17-01 / F04 fix: Now uses AccessPolicy for canonicalized, segment-based
    quarantine check instead of literal substring matching.

    Args:
        body_path: Path to the .body file.
        access_policy: Optional AccessPolicy for enforcement. If None, falls
            back to legacy segment-based check (still segment-based, not substring).

    Returns:
        Tuple of:
            - content: The body file content as a string
            - provenance: AsosProvenance capturing source identity

    Raises:
        AccessPolicyViolation: If path fails policy check (when access_policy provided).
        ValueError: If path contains 'quarantine_holdout' segment (legacy fallback).
        ValueError: If the SHA256 mismatch between computed and receipt.
        FileNotFoundError: If body or receipt file doesn't exist.
    """
    from .access_policy import AccessPolicy, AccessPolicyViolation

    body_path_obj = Path(body_path)

    # V17-01 / F04 fix: Use AccessPolicy if provided, else fall back to
    # segment-based check (not substring). The key fix is resolving the path
    # BEFORE checking, and checking Path.parts not string substring.
    if access_policy is not None:
        # Full policy check (includes quarantine, root escape, holdout dates)
        access_policy.assert_allowed(body_path)
    else:
        # Legacy fallback: still use segment-based check, not substring
        # This is safer than the old "in" check for backward compatibility
        resolved = body_path_obj.resolve()
        for part in resolved.parts:
            if part == "quarantine_holdout":
                raise ValueError(
                    f"Cannot load from quarantine_holdout: {body_path}"
                )

    body_path_obj = Path(body_path)

    # Find sibling receipt (replace .body with .json)
    receipt_path = body_path_obj.with_suffix(".json")
    if not receipt_path.exists():
        raise FileNotFoundError(f"Receipt file not found: {receipt_path}")

    # Read and hash body
    with open(body_path, "rb") as f:
        body_bytes = f.read()

    computed_sha256 = hashlib.sha256(body_bytes).hexdigest()

    # Read receipt
    with open(receipt_path) as f:
        receipt = json.load(f)

    # Extract expected SHA256 from receipt
    expected_sha256 = receipt.get("sha256")
    if not expected_sha256:
        raise ValueError(f"Receipt missing sha256 field: {receipt_path}")

    # Cross-check
    if computed_sha256 != expected_sha256:
        raise ValueError(
            f"SHA256 mismatch for {body_path}: "
            f"computed {computed_sha256}, receipt says {expected_sha256}"
        )

    # Extract fetch timestamp from receipt (finished_at)
    finished_at_str = receipt.get("finished_at")
    if not finished_at_str:
        raise ValueError(f"Receipt missing finished_at field: {receipt_path}")

    # Parse ISO timestamp to microseconds
    fetch_timestamp_us = utc_us(finished_at_str)

    # Extract run_id from parent directory name
    # Path structure: .../station/YYYY-MM/run_id/filename.body
    run_id = body_path_obj.parent.name

    content = body_bytes.decode("utf-8")

    return content, AsosProvenance(
        path=body_path,
        sha256=computed_sha256,
        fetch_timestamp_us=fetch_timestamp_us,
        run_id=run_id,
    )


# Quality codes for missing outcomes
QUALITY_NO_REPORT_IN_SLOT = "no_routine_report_in_slot"
QUALITY_VISIBILITY_UNDETERMINED = "visibility_undetermined_or_interval"


def _fold_duplicate_observations(
    observations: list[MetarReport],
) -> list[MetarReport]:
    """V17-02 / F11: Fold same-timestamp observations by native_semantics_sha256.

    When multiple observations share the same observation_time and the same
    native_semantics_sha256, they are semantically identical duplicates.
    We keep only one representative from each (timestamp, semantics) group,
    choosing the one with the lexicographically smallest raw text for
    deterministic selection.

    This folding happens BEFORE "last-in-slot" selection, so duplicates
    don't influence which observation is chosen as the resolving one.

    Args:
        observations: List of METAR observations to fold.

    Returns:
        List with duplicates removed (one representative per semantic group).
    """
    if not observations:
        return []

    # Group by (observation_time, native_semantics_sha256)
    from collections import defaultdict

    groups: dict[tuple, list[MetarReport]] = defaultdict(list)
    for obs in observations:
        # MetarReport may not have native_semantics_sha256; use raw as fallback
        semantics_key = getattr(obs, "native_semantics_sha256", None)
        if semantics_key is None:
            # Hash the raw text as a fallback semantic key
            semantics_key = hashlib.sha256(obs.raw.encode()).hexdigest()

        key = (obs.observation_time, semantics_key)
        groups[key].append(obs)

    # Pick one representative per group: lexicographically smallest raw text
    folded = []
    for key in sorted(groups.keys()):  # Sort keys for determinism
        group = groups[key]
        representative = min(group, key=lambda o: o.raw)
        folded.append(representative)

    return folded


def resolve_h15_outcomes(
    observations: list[MetarReport],
    targets: list[Target],
    *,
    provenance: AsosProvenance,
    resolution_version: str,
    resolved_at: int | None = None,
) -> list[dict]:
    """Resolve H15 visibility outcomes for targets against observations.

    V17-02 / F11 fix: Now folds duplicate observations (same timestamp and
    native_semantics_sha256) before picking "last-in-slot", and returns
    records in stable target_id order for deterministic output.

    For each target, determines the outcome via ternary visibility classification
    against the pre-filtered routine observations, then builds one outcome
    record dict per target.

    Note: classify()'s "inconsistent" result is mapped to missing (same as
    "undetermined"), not to a fabricated value=0 refuted outcome.

    Args:
        observations: Pre-filtered routine METAR observations.
        targets: List of Target objects to resolve.
        provenance: Source provenance for the ASOS data.
        resolution_version: Version identifier for this resolution run.
        resolved_at: Resolution timestamp in microseconds. If None, uses
            the provenance's fetch timestamp (never wall-clock).

    Returns:
        List of outcome record dicts, one per target, sorted by target_id
        for stable ordering. Each record is shaped identically regardless
        of registration mode (legacy_compatible or formal_provider_bound).
    """
    if resolved_at is None:
        resolved_at = provenance.fetch_timestamp_us

    # V17-02 / F11: Process targets in sorted order for deterministic output
    sorted_targets = sorted(targets, key=lambda t: t.target_id)

    records = []

    for target in sorted_targets:
        # Find observations in this target's slot
        slot_obs = [
            obs
            for obs in observations
            if obs.station == target.entity
            and target.physical_start <= obs.observation_time < target.physical_end
        ]

        if not slot_obs:
            # No report in slot -> missing
            record = build_outcome_record(
                target=target,
                resolution_version=resolution_version,
                status="missing",
                value=None,
                source_revision=provenance.source_revision,
                source_sha256=None,  # Missing doesn't require sha256
                observed_at=None,
                published_at=None,
                fetched_at=provenance.fetch_timestamp_us,
                resolved_at=resolved_at,
                quality_status=QUALITY_NO_REPORT_IN_SLOT,
                availability_basis="declared_archive_scenario",
                # H15 formal fields (required even for missing in formal mode)
                resolution_policy="h15_routine_archive.v1",
                provider="IEM",
                provider_version="native_h15_snapshot.v1",
                # reference_kind required by validate_resolution even for missing
                reference_kind="final_archived_routine_report_not_continuous_physical_truth",
            )
            # V17-02 / F11: Add target_id for logging/debugging (not in OUTCOME_FIELDS)
            record["target_id"] = target.target_id
            records.append(record)
            continue

        # V17-02 / F11: Fold duplicates BEFORE selecting last-in-slot
        # This prevents duplicates from influencing which observation resolves
        folded_obs = _fold_duplicate_observations(slot_obs)

        # Use last observation in slot (sorted by time, then raw for tie-break)
        folded_obs.sort(key=lambda o: (o.observation_time, o.raw))
        obs = folded_obs[-1]

        # H15 reference kind for all records
        h15_reference_kind = "final_archived_routine_report_not_continuous_physical_truth"

        # Check visibility
        if obs.visibility is None:
            # Report exists but visibility missing/undetermined
            record = build_outcome_record(
                target=target,
                resolution_version=resolution_version,
                status="missing",
                value=None,
                source_revision=provenance.source_revision,
                source_sha256=None,
                observed_at=obs.observation_time,
                published_at=None,
                fetched_at=provenance.fetch_timestamp_us,
                resolved_at=resolved_at,
                quality_status=QUALITY_VISIBILITY_UNDETERMINED,
                availability_basis="declared_archive_scenario",
                resolution_policy="h15_routine_archive.v1",
                provider="IEM",
                provider_version="native_h15_snapshot.v1",
                references=[{"raw": obs.raw}],
                reference_kind=h15_reference_kind,
            )
            # V17-02 / F11: Add target_id for logging/debugging (not in OUTCOME_FIELDS)
            record["target_id"] = target.target_id
            records.append(record)
            continue

        # Classify visibility against threshold
        # classify() returns "supported", "refuted", "undetermined", or
        # "inconsistent" (the latter when its internal support is None).
        classification = classify(obs.visibility, target.event_operator, target.threshold)

        # "inconsistent" is treated the same as "undetermined": both mean the
        # classifier could not determine an outcome, not that it determined a
        # negative (refuted) one. classify() can structurally return
        # "inconsistent" (support is None) even though that branch is not
        # currently reachable from real data paths here; without this check
        # it would silently fall through to the value=0 branch below, which
        # would be a hard "refuted" outcome fabricated from a non-answer.
        if classification in ("undetermined", "inconsistent"):
            # Interval straddles threshold, or support is inconsistent -> ambiguous
            record = build_outcome_record(
                target=target,
                resolution_version=resolution_version,
                status="missing",
                value=None,
                source_revision=provenance.source_revision,
                source_sha256=None,
                observed_at=obs.observation_time,
                published_at=None,
                fetched_at=provenance.fetch_timestamp_us,
                resolved_at=resolved_at,
                quality_status=QUALITY_VISIBILITY_UNDETERMINED,
                availability_basis="declared_archive_scenario",
                resolution_policy="h15_routine_archive.v1",
                provider="IEM",
                provider_version="native_h15_snapshot.v1",
                references=[{"raw": obs.raw}],
                reference_kind=h15_reference_kind,
            )
            # V17-02 / F11: Add target_id for logging/debugging (not in OUTCOME_FIELDS)
            record["target_id"] = target.target_id
            records.append(record)
            continue

        # Mature outcome: value is strictly int (0 or 1)
        value = int(1) if classification == "supported" else int(0)

        record = build_outcome_record(
            target=target,
            resolution_version=resolution_version,
            status="mature",
            value=value,
            source_revision=provenance.source_revision,
            source_sha256=provenance.sha256,
            observed_at=obs.observation_time,
            published_at=None,  # Archives don't have published_at
            fetched_at=provenance.fetch_timestamp_us,
            resolved_at=resolved_at,
            quality_status="settled_final_archived_report",
            availability_basis="declared_archive_scenario",
            resolution_policy="h15_routine_archive.v1",
            provider="IEM",
            provider_version="native_h15_snapshot.v1",
            references=[{"raw": obs.raw}],
            reference_kind="final_archived_routine_report_not_continuous_physical_truth",
        )
        # V17-02 / F11: Add target_id for logging/debugging (not in OUTCOME_FIELDS)
        record["target_id"] = target.target_id
        records.append(record)

    return records


def register_h15_outcomes(
    records: list[dict],
    targets: list[Target],
    *,
    mode: str,
) -> tuple[OutcomeRegistry, list[bool]]:
    """Register H15 outcome records into an OutcomeRegistry.

    Args:
        records: List of outcome record dicts from resolve_h15_outcomes.
        targets: List of Target objects (for registry construction).
        mode: Registry mode - "legacy_compatible" or "formal_provider_bound".

    Returns:
        Tuple of:
            - registry: The OutcomeRegistry with registered records
            - success_flags: List of bools, one per record, indicating
              whether the record was newly registered (True) or was an
              idempotent re-registration (False).
    """
    registry = OutcomeRegistry(targets, mode=mode)

    success_flags = []
    for record in records:
        # V17-02 / F11: Strip target_id before registering (not in OUTCOME_FIELDS)
        # This field is added for logging/debugging but not part of the canonical record
        record_for_registry = {k: v for k, v in record.items() if k != "target_id"}
        result = registry.register(record_for_registry)
        success_flags.append(result)

    return registry, success_flags


def make_resolution_version(
    provenance: AsosProvenance,
    *,
    prefix: str = "h15_asos",
) -> str:
    """Generate a resolution_version string from provenance.

    The version includes the run_id so that if the same station-month's ASOS
    data was fetched under two different download run_ids, the resulting
    outcome sets register as distinct versions rather than colliding.

    Args:
        provenance: The AsosProvenance for this resolution.
        prefix: Optional prefix for the version string.

    Returns:
        A resolution_version string like "h15_asos:20260920T083945Z_5a91ac05a955".
    """
    return f"{prefix}:{provenance.run_id}"
