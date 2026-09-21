"""Episode manifest builder for pre-registration (P0-08).

This module builds a FROZEN, PRE-REGISTERED set of episode targets for later
measurement, using ONLY metadata that is available BEFORE looking at outcomes
(Y = the actual METAR/ASOS observed outcome). This is standard pre-registration
discipline: if you let the selection process see Y even implicitly, the resulting
"measurement" is contaminated.

CRITICAL Y-ISOLATION CONSTRAINT:
This module MUST NOT import anything from outcome_wiring.py or any ASOS/outcome
reading functions. The import isolation is enforced by a test that parses this
module's AST.

Selection logic (deterministic, pre-declared):
- Score candidate targets using ONLY TAF-side signals:
  - Revision density within the target's validity window (AMD/COR count)
  - Presence of same-minute ties / receipt-order events
  - Lead-time coverage
  - Readable-evidence change frequency
- Deterministic tie-breaking (lexicographic by station+timestamp)
- Version string recorded in output manifest

Constraints:
- At most 12 targets total
- Exactly 3 checkpoints per target (T-60, T-40, T-20 minutes before validity start)
- Every checkpoint must be strictly earlier than target's validity start
- Split into "changed" (AMD/COR) and "unchanged" queues
- Exclude holdout window overlaps
- Label maturity: only targets within archive covered period
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# IMPORTANT: Only import TAF-side functions. NEVER import from outcome_wiring.py
from .episode_compiler import compile_afos_taf_stream

# Selection rule version - increment when selection logic changes
SELECTION_RULE_VERSION = "manifest_selection.v1"

# Checkpoint offsets from validity_start (in minutes, negative = before)
CHECKPOINT_OFFSETS_MINUTES = [-60, -40, -20]

# Maximum targets in the manifest
MAX_TARGETS = 12


@dataclass(frozen=True)
class Checkpoint:
    """A single checkpoint for evaluation."""

    time_us: int  # Microseconds since epoch
    weight: float = 1.0  # Equal weights per D03


@dataclass
class CandidateTarget:
    """A candidate target for episode selection."""

    station: str
    validity_start_us: int
    validity_end_us: int

    # TAF-side scoring signals
    revision_count: int  # AMD/COR packages in validity window
    tie_event_count: int  # Same-minute issuance ties
    evidence_change_count: int  # Distinct semantic hashes in window
    lead_time_coverage_hours: float  # Hours of TAF coverage before target

    # Source tracking
    source_packages: list[dict]  # Raw TAF packages for this window

    @property
    def target_id(self) -> str:
        """Generate deterministic, human-legible target_id."""
        dt = datetime.fromtimestamp(self.validity_start_us / 1_000_000, tz=timezone.utc)
        return f"{self.station}_{dt.strftime('%Y%m%d_%H')}"

    @property
    def has_revisions(self) -> bool:
        """True if target saw AMD/COR during validity window."""
        return self.revision_count > 0

    @property
    def selection_score(self) -> tuple:
        """Score tuple for selection ranking (higher = more interesting).

        Returns tuple for comparison: (revision_count, tie_event_count,
        evidence_change_count, lead_time_coverage_hours, -station, -validity_start)

        The negative values ensure deterministic tie-breaking (lexicographic).
        """
        return (
            self.revision_count,
            self.tie_event_count,
            self.evidence_change_count,
            self.lead_time_coverage_hours,
            # Deterministic tie-breakers (negative for ascending order)
            self.station,  # Lexicographic by station
            self.validity_start_us,  # Then by time
        )


def _us_to_iso(timestamp_us: int) -> str:
    """Convert microseconds timestamp to ISO 8601 string."""
    dt = datetime.fromtimestamp(timestamp_us / 1_000_000, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _iso_to_us(iso_str: str) -> int:
    """Convert ISO 8601 string to microseconds timestamp."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1_000_000)


def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_config_sha256(config_path: Path) -> str:
    """Verify stations_calendar config against its sidecar SHA256.

    Returns:
        The verified SHA256 hash.

    Raises:
        ValueError: If SHA256 mismatch.
    """
    sidecar_path = config_path.with_suffix(config_path.suffix + ".sha256")
    if not sidecar_path.exists():
        raise FileNotFoundError(f"SHA256 sidecar not found: {sidecar_path}")

    # Read expected hash
    with open(sidecar_path, "r") as f:
        expected_line = f.read().strip()
    # Format: "hash  filename" or just "hash"
    expected_sha = expected_line.split()[0]

    # Compute actual
    actual_sha = sha256_file(config_path)

    if actual_sha != expected_sha:
        raise ValueError(
            f"SHA256 mismatch for {config_path}: "
            f"computed {actual_sha}, sidecar says {expected_sha}"
        )

    return actual_sha


def load_stations_calendar(config_path: Path) -> tuple[dict, str]:
    """Load and verify stations_calendar config.

    Returns:
        Tuple of (config_dict, verified_sha256).
    """
    verified_sha = verify_config_sha256(config_path)

    with open(config_path, "r") as f:
        config = json.load(f)

    return config, verified_sha


def get_holdout_window(config: dict) -> tuple[int, int]:
    """Extract holdout exclusion window from config.

    Returns:
        Tuple of (start_us, end_us) for the holdout window.
    """
    holdout = config.get("holdout_exclusion", {})
    start_str = holdout.get("window_start")
    end_str = holdout.get("window_end")

    if not start_str or not end_str:
        raise ValueError("Holdout exclusion window not defined in config")

    return _iso_to_us(start_str), _iso_to_us(end_str)


def get_calendar_bounds(config: dict) -> tuple[int, int]:
    """Extract calendar start/end from config.

    Returns:
        Tuple of (start_us, end_us) for the calendar period.
    """
    start_str = config.get("calendar_start")
    end_str = config.get("calendar_end")

    if not start_str or not end_str:
        raise ValueError("Calendar bounds not defined in config")

    return _iso_to_us(start_str), _iso_to_us(end_str)


def windows_overlap(
    start1_us: int, end1_us: int,
    start2_us: int, end2_us: int,
) -> bool:
    """Check if two time windows overlap."""
    return start1_us < end2_us and start2_us < end1_us


def compute_checkpoints(validity_start_us: int) -> list[Checkpoint]:
    """Compute 3 checkpoints for a target at T-60, T-40, T-20 minutes.

    All checkpoints are strictly earlier than validity_start.

    Args:
        validity_start_us: Target validity window start in microseconds.

    Returns:
        List of 3 Checkpoint objects.
    """
    checkpoints = []
    for offset_min in CHECKPOINT_OFFSETS_MINUTES:
        offset_us = offset_min * 60 * 1_000_000
        checkpoint_time = validity_start_us + offset_us
        checkpoints.append(Checkpoint(time_us=checkpoint_time, weight=1.0))

    # Verify all checkpoints are strictly before validity_start
    for cp in checkpoints:
        if cp.time_us >= validity_start_us:
            raise ValueError(
                f"Checkpoint {cp.time_us} not strictly before validity_start {validity_start_us}"
            )

    return checkpoints


def detect_same_minute_ties(packages: list[dict]) -> int:
    """Count same-minute issuance ties in a set of packages.

    Ties indicate receipt-order events that may be interesting for evaluation.
    """
    # Group by issued_at minute
    by_minute = defaultdict(list)
    for pkg in packages:
        issued_at = pkg["issued_at"]
        # Round down to minute
        minute_us = (issued_at // 60_000_000) * 60_000_000
        by_minute[minute_us].append(pkg)

    # Count groups with >1 package
    tie_count = sum(1 for group in by_minute.values() if len(group) > 1)
    return tie_count


def count_distinct_semantics(packages: list[dict]) -> int:
    """Count distinct semantic hashes in a set of packages."""
    hashes = {pkg.get("native_semantics_sha256") for pkg in packages}
    return len(hashes)


def build_candidates_from_taf_packages(
    packages: list[dict],
    *,
    calendar_start_us: int,
    calendar_end_us: int,
    holdout_start_us: int,
    holdout_end_us: int,
) -> list[CandidateTarget]:
    """Build candidate targets from compiled TAF packages.

    Groups packages by (station, validity_start, validity_end) to identify
    unique target windows, then computes TAF-side scoring signals for each.

    Excludes:
    - Targets overlapping holdout window
    - Targets outside calendar bounds
    """
    # Group packages by target window
    by_window: dict[tuple, list[dict]] = defaultdict(list)
    for pkg in packages:
        station = pkg["station"]
        valid_start = pkg["valid_start"]
        valid_end = pkg["valid_end"]
        key = (station, valid_start, valid_end)
        by_window[key].append(pkg)

    candidates = []

    for (station, valid_start, valid_end), window_packages in by_window.items():
        # Skip if outside calendar bounds
        if valid_start < calendar_start_us or valid_end > calendar_end_us:
            continue

        # Skip if overlaps holdout window
        if windows_overlap(valid_start, valid_end, holdout_start_us, holdout_end_us):
            continue

        # Also check that checkpoints don't overlap holdout
        checkpoints = compute_checkpoints(valid_start)
        checkpoint_window_start = min(cp.time_us for cp in checkpoints)
        checkpoint_window_end = valid_start  # Checkpoints are before validity

        if windows_overlap(
            checkpoint_window_start, checkpoint_window_end,
            holdout_start_us, holdout_end_us
        ):
            continue

        # Count revisions (AMD/COR)
        revision_count = sum(
            1 for pkg in window_packages
            if pkg.get("amendment_kind") in ("AMD", "COR")
        )

        # Detect same-minute ties
        tie_count = detect_same_minute_ties(window_packages)

        # Count distinct semantic changes
        evidence_change_count = count_distinct_semantics(window_packages)

        # Compute lead-time coverage (hours of TAF packages before target)
        # This is simplified: we count hours between earliest package and target
        earliest_issued = min(pkg["issued_at"] for pkg in window_packages)
        lead_time_hours = (valid_start - earliest_issued) / (3600 * 1_000_000)

        candidate = CandidateTarget(
            station=station,
            validity_start_us=valid_start,
            validity_end_us=valid_end,
            revision_count=revision_count,
            tie_event_count=tie_count,
            evidence_change_count=evidence_change_count,
            lead_time_coverage_hours=lead_time_hours,
            source_packages=window_packages,
        )
        candidates.append(candidate)

    return candidates


def select_episodes(
    candidates: list[CandidateTarget],
    *,
    max_targets: int = MAX_TARGETS,
) -> tuple[list[CandidateTarget], list[CandidateTarget]]:
    """Select episodes from candidates, split into changed/unchanged queues.

    Selection strategy:
    1. Separate candidates into "changed" (has AMD/COR) and "unchanged" buckets
    2. Sort each bucket by selection_score (descending)
    3. Take top candidates from each bucket to fill quota
    4. Deterministic tie-breaking via selection_score's tuple comparison

    Args:
        candidates: List of all candidate targets.
        max_targets: Maximum total targets to select.

    Returns:
        Tuple of (changed_queue, unchanged_queue) with selected targets.
    """
    changed = [c for c in candidates if c.has_revisions]
    unchanged = [c for c in candidates if not c.has_revisions]

    # Sort by selection_score (reversed for descending by interesting-ness,
    # but selection_score includes deterministic tie-breakers)
    # We want higher revision count first, so reverse=True for the primary components
    def sort_key(c: CandidateTarget) -> tuple:
        score = c.selection_score
        # Negate numeric components for descending, keep strings for lexicographic
        return (
            -score[0],  # revision_count (higher first)
            -score[1],  # tie_event_count (higher first)
            -score[2],  # evidence_change_count (higher first)
            -score[3],  # lead_time_coverage (higher first)
            score[4],   # station (lexicographic ascending)
            score[5],   # validity_start (ascending)
        )

    changed.sort(key=sort_key)
    unchanged.sort(key=sort_key)

    # Allocate slots between queues
    # Aim for balanced split, but don't force empty queues
    half_max = max_targets // 2

    selected_changed = []
    selected_unchanged = []

    if changed and unchanged:
        # Both queues have candidates - split evenly
        selected_changed = changed[:half_max]
        selected_unchanged = unchanged[:max_targets - len(selected_changed)]
    elif changed:
        # Only changed queue has candidates
        selected_changed = changed[:max_targets]
    else:
        # Only unchanged queue has candidates
        selected_unchanged = unchanged[:max_targets]

    return selected_changed, selected_unchanged


def build_manifest(
    changed_queue: list[CandidateTarget],
    unchanged_queue: list[CandidateTarget],
    *,
    config_sha256: str,
    taf_archive_summary: str,
) -> dict:
    """Build the episode manifest JSON structure.

    Args:
        changed_queue: Selected targets with AMD/COR revisions.
        unchanged_queue: Selected targets without revisions.
        config_sha256: Verified SHA256 of stations_calendar config.
        taf_archive_summary: Identifying hash/summary of TAF archive state.

    Returns:
        Manifest dict ready for JSON serialization.
    """
    targets = []

    for queue_name, queue in [("changed", changed_queue), ("unchanged", unchanged_queue)]:
        for candidate in queue:
            checkpoints = compute_checkpoints(candidate.validity_start_us)

            target_entry = {
                "target_id": candidate.target_id,
                "station": candidate.station,
                "validity_start": _us_to_iso(candidate.validity_start_us),
                "validity_start_us": candidate.validity_start_us,
                "validity_end": _us_to_iso(candidate.validity_end_us),
                "validity_end_us": candidate.validity_end_us,
                "queue": queue_name,
                "checkpoints": [
                    {
                        "time": _us_to_iso(cp.time_us),
                        "time_us": cp.time_us,
                        "weight": cp.weight,
                    }
                    for cp in checkpoints
                ],
                "selection_signals": {
                    "revision_count": candidate.revision_count,
                    "tie_event_count": candidate.tie_event_count,
                    "evidence_change_count": candidate.evidence_change_count,
                    "lead_time_coverage_hours": round(candidate.lead_time_coverage_hours, 2),
                },
            }
            targets.append(target_entry)

    frozen_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    manifest = {
        "schema": "disastertrace.episode_manifest.v1",
        "selection_rule_version": SELECTION_RULE_VERSION,
        "input_fingerprints": {
            "stations_calendar_sha256": config_sha256,
            "taf_archive_summary": taf_archive_summary,
        },
        "targets": targets,
        "queue_summary": {
            "changed_count": len(changed_queue),
            "unchanged_count": len(unchanged_queue),
            "total_count": len(changed_queue) + len(unchanged_queue),
        },
        "frozen_at": frozen_at,
        "self_sha256": "",  # Placeholder, computed after serialization
    }

    return manifest


def compute_self_sha256(manifest: dict) -> str:
    """Compute self_sha256 for manifest integrity.

    Method: serialize with self_sha256="" placeholder, compute SHA256,
    then fill in the actual hash.
    """
    # Create copy with placeholder
    manifest_copy = json.loads(json.dumps(manifest))
    manifest_copy["self_sha256"] = ""

    # Serialize deterministically
    serialized = json.dumps(manifest_copy, sort_keys=True, indent=2)

    # Compute hash
    return hashlib.sha256(serialized.encode()).hexdigest()


def verify_manifest_integrity(manifest: dict) -> bool:
    """Verify manifest's self_sha256 matches computed value.

    Returns:
        True if integrity check passes.

    Raises:
        ValueError: If self_sha256 doesn't match.
    """
    recorded_sha = manifest.get("self_sha256", "")
    computed_sha = compute_self_sha256(manifest)

    if recorded_sha != computed_sha:
        raise ValueError(
            f"Manifest integrity check failed: "
            f"recorded {recorded_sha}, computed {computed_sha}"
        )

    return True


def freeze_manifest(
    taf_packages: list[dict],
    config_path: Path,
    *,
    taf_archive_summary: str | None = None,
) -> dict:
    """Phase 1: Freeze episode selection from TAF-only data.

    This is the main entry point for manifest generation. It:
    1. Loads and verifies stations_calendar config
    2. Builds candidates from TAF packages
    3. Selects episodes via deterministic scoring
    4. Computes integrity hash

    Args:
        taf_packages: Compiled TAF packages from compile_afos_taf_stream.
        config_path: Path to stations_calendar_v16.json.
        taf_archive_summary: Optional archive identifier. If None, computed
            from packages hash.

    Returns:
        Complete manifest dict ready for serialization.
    """
    # Load and verify config
    config, config_sha256 = load_stations_calendar(config_path)

    # Extract bounds
    calendar_start, calendar_end = get_calendar_bounds(config)
    holdout_start, holdout_end = get_holdout_window(config)

    # Build candidates
    candidates = build_candidates_from_taf_packages(
        taf_packages,
        calendar_start_us=calendar_start,
        calendar_end_us=calendar_end,
        holdout_start_us=holdout_start,
        holdout_end_us=holdout_end,
    )

    # Select episodes
    changed_queue, unchanged_queue = select_episodes(candidates)

    # Compute TAF archive summary if not provided
    if taf_archive_summary is None:
        # Hash first 10 package source_ids as summary
        package_ids = sorted(set(pkg.get("source_id", "") for pkg in taf_packages[:100]))
        taf_archive_summary = hashlib.sha256(
            json.dumps(package_ids).encode()
        ).hexdigest()[:16]

    # Build manifest
    manifest = build_manifest(
        changed_queue,
        unchanged_queue,
        config_sha256=config_sha256,
        taf_archive_summary=taf_archive_summary,
    )

    # Compute and fill in self_sha256
    manifest["self_sha256"] = compute_self_sha256(manifest)

    return manifest


def validate_manifest(manifest: dict) -> list[str]:
    """Validate manifest structure and constraints.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Check schema
    if manifest.get("schema") != "disastertrace.episode_manifest.v1":
        errors.append(f"Invalid schema: {manifest.get('schema')}")

    targets = manifest.get("targets", [])

    # Check target count
    if len(targets) > MAX_TARGETS:
        errors.append(f"Too many targets: {len(targets)} > {MAX_TARGETS}")

    # Check each target
    for target in targets:
        target_id = target.get("target_id", "unknown")
        validity_start_us = target.get("validity_start_us")
        checkpoints = target.get("checkpoints", [])

        # Check checkpoint count
        if len(checkpoints) != 3:
            errors.append(f"Target {target_id}: expected 3 checkpoints, got {len(checkpoints)}")

        # Check checkpoints are before validity_start
        for i, cp in enumerate(checkpoints):
            cp_time = cp.get("time_us")
            if cp_time is not None and validity_start_us is not None:
                if cp_time >= validity_start_us:
                    errors.append(
                        f"Target {target_id}: checkpoint {i} at {cp_time} "
                        f"not before validity_start {validity_start_us}"
                    )

    # Check self_sha256 integrity
    try:
        verify_manifest_integrity(manifest)
    except ValueError as e:
        errors.append(str(e))

    return errors
