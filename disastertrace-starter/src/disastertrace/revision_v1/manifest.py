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
# V17-02 / F02: Bumped to v2 for filtered revision counts and outcome_contract
SELECTION_RULE_VERSION = "manifest_selection.v2"

# V17-02 / F02: Outcome contract constants (import from outcome_wiring for consistency)
# These define the H15 visibility target scoring parameters
DEFAULT_OUTCOME_CONTRACT = {
    "thresholds_m": [5000.0, 1000.0],
    "report_policy": "iem_routine_unique_hour.v1",
    "support_window_hours": 1.0,
    "checkpoint_weights": [1.0, 1.0, 1.0],  # Equal weights, sum = 3.0, normalized per target
    "checkpoint_offsets_minutes": [-60, -40, -20],
}

# Checkpoint offsets from validity_start (in minutes, negative = before)
CHECKPOINT_OFFSETS_MINUTES = [-60, -40, -20]

# Maximum targets in the manifest
MAX_TARGETS = 12

# A2-4: This batch supports exactly one outcome/scoring profile. H15_DEFAULT_PROFILE
# is the single source of truth for it (same value as DEFAULT_OUTCOME_CONTRACT --
# named separately so `validate_outcome_profile` has an unambiguous target to check
# against, independent of any future change to what a *default* means).
H15_DEFAULT_PROFILE = DEFAULT_OUTCOME_CONTRACT

# Fields a profile dict must carry, in full, to be accepted by validate_outcome_profile.
_OUTCOME_PROFILE_REQUIRED_FIELDS = (
    "thresholds_m",
    "report_policy",
    "support_window_hours",
    "checkpoint_weights",
    "checkpoint_offsets_minutes",
)


class UnsupportedOutcomeProfile(ValueError):
    """Raised when an outcome_contract does not match the single supported H15 profile.

    A2-4: prior behavior silently accepted and partially honored any custom
    outcome_contract dict (see the withdrawn `test_custom_outcome_contract_preserved`
    claim). This batch supports exactly one profile end-to-end (checkpoints,
    thresholds, support window); anything else must be rejected explicitly rather
    than partially applied.
    """


def validate_outcome_profile(contract: dict) -> None:
    """Validate that `contract` is exactly the single supported H15 profile.

    Args:
        contract: An outcome_contract-shaped dict to check.

    Raises:
        UnsupportedOutcomeProfile: if any required field is missing, or any
            field's value differs from H15_DEFAULT_PROFILE.
    """
    missing = [f for f in _OUTCOME_PROFILE_REQUIRED_FIELDS if f not in contract]
    if missing:
        raise UnsupportedOutcomeProfile(
            f"outcome_contract missing required field(s): {missing}"
        )

    mismatches = [
        f"{field}: got {contract[field]!r}, only {H15_DEFAULT_PROFILE[field]!r} is supported"
        for field in _OUTCOME_PROFILE_REQUIRED_FIELDS
        if contract[field] != H15_DEFAULT_PROFILE[field]
    ]
    if mismatches:
        raise UnsupportedOutcomeProfile(
            "This batch supports exactly one outcome profile (H15_DEFAULT_PROFILE); "
            "rejecting unsupported profile:\n" + "\n".join(mismatches)
        )


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

    # V17-02 / F02: TAF-side scoring signals - FILTERED to pre-deadline only
    # These count only packages with issued_at < validity_start_us
    revision_count: int  # AMD/COR packages issued before target deadline
    tie_event_count: int  # Same-minute ties issued before deadline
    evidence_change_count: int  # Distinct semantic hashes issued before deadline
    lead_time_coverage_hours: float  # Hours of TAF coverage before target

    # V17-02 / F02: UNFILTERED counts for comparison/debugging
    # These count ALL packages in the validity window regardless of issued_at
    revision_count_whole_window: int  # AMD/COR packages in full validity window
    tie_event_count_whole_window: int  # Same-minute ties in full window
    evidence_change_count_whole_window: int  # Distinct hashes in full window

    # Source tracking
    source_packages: list[dict]  # Raw TAF packages for this window

    @property
    def target_id(self) -> str:
        """Generate deterministic, human-legible target_id."""
        dt = datetime.fromtimestamp(self.validity_start_us / 1_000_000, tz=timezone.utc)
        return f"{self.station}_{dt.strftime('%Y%m%d_%H')}"

    @property
    def has_revisions(self) -> bool:
        """True if target saw AMD/COR before deadline (pre-deadline revisions)."""
        return self.revision_count > 0

    @property
    def selection_score(self) -> tuple:
        """Score tuple for selection ranking (higher = more interesting).

        V17-02 / F02: Uses pre-deadline revision_count, not whole-window count.

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


def compute_checkpoints(
    validity_start_us: int,
    *,
    profile: dict | None = None,
) -> list[Checkpoint]:
    """Compute checkpoints for a target from a profile's offsets/weights.

    All checkpoints are strictly earlier than validity_start.

    Args:
        validity_start_us: Target validity window start in microseconds.
        profile: Outcome profile supplying `checkpoint_offsets_minutes` and
            `checkpoint_weights`. Defaults to H15_DEFAULT_PROFILE, whose values
            equal the historical hardcoded CHECKPOINT_OFFSETS_MINUTES with
            weight 1.0 -- so callers that don't pass a profile see unchanged
            behavior.

    Returns:
        List of Checkpoint objects, one per offset.
    """
    if profile is None:
        profile = H15_DEFAULT_PROFILE

    offsets_minutes = profile["checkpoint_offsets_minutes"]
    weights = profile["checkpoint_weights"]

    checkpoints = []
    for offset_min, weight in zip(offsets_minutes, weights):
        offset_us = offset_min * 60 * 1_000_000
        checkpoint_time = validity_start_us + offset_us
        checkpoints.append(Checkpoint(time_us=checkpoint_time, weight=weight))

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

    V17-02 / F02 fix: Computes BOTH filtered counts (issued_at < validity_start)
    and unfiltered whole-window counts. The filtered counts are what matters
    for scoring (only revisions visible before the deadline), while unfiltered
    counts are kept for comparison/debugging.

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

        # V17-02 / F02: Split packages into pre-deadline and whole-window sets
        pre_deadline_packages = [
            pkg for pkg in window_packages
            if pkg["issued_at"] < valid_start
        ]

        # FILTERED counts (pre-deadline only) - used for scoring
        revision_count = sum(
            1 for pkg in pre_deadline_packages
            if pkg.get("amendment_kind") in ("AMD", "COR")
        )
        tie_count = detect_same_minute_ties(pre_deadline_packages)
        evidence_change_count = count_distinct_semantics(pre_deadline_packages)

        # UNFILTERED counts (whole window) - kept for comparison/debugging
        revision_count_whole = sum(
            1 for pkg in window_packages
            if pkg.get("amendment_kind") in ("AMD", "COR")
        )
        tie_count_whole = detect_same_minute_ties(window_packages)
        evidence_change_count_whole = count_distinct_semantics(window_packages)

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
            revision_count_whole_window=revision_count_whole,
            tie_event_count_whole_window=tie_count_whole,
            evidence_change_count_whole_window=evidence_change_count_whole,
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


def _validate_checkpoint_weights(weights: list[float]) -> None:
    """V17-02 / F02: Validate that checkpoint weights sum to 1.0 per target.

    The DEFAULT_OUTCOME_CONTRACT uses equal weights [1.0, 1.0, 1.0] which sum to 3.0.
    When normalized per target (divided by number of checkpoints), each checkpoint
    contributes 1/3 to the target score.

    Raises:
        ValueError: If weights are empty or any weight is negative.
    """
    if not weights:
        raise ValueError("Checkpoint weights cannot be empty")
    if any(w < 0 for w in weights):
        raise ValueError("Checkpoint weights cannot be negative")
    # Note: We validate non-negativity and non-emptiness, but the sum need not
    # be exactly 1.0 - the scorer normalizes by dividing by sum(weights).


def build_manifest(
    changed_queue: list[CandidateTarget],
    unchanged_queue: list[CandidateTarget],
    *,
    config_sha256: str,
    taf_archive_summary: str,
    outcome_contract: dict | None = None,
) -> dict:
    """Build the episode manifest JSON structure.

    V17-02 / F02 fix: Now includes outcome_contract in the manifest schema,
    and reports both pre-deadline (filtered) and whole-window counts.

    Args:
        changed_queue: Selected targets with AMD/COR revisions.
        unchanged_queue: Selected targets without revisions.
        config_sha256: Verified SHA256 of stations_calendar config.
        taf_archive_summary: Identifying hash/summary of TAF archive state.
        outcome_contract: Optional outcome contract. If None, uses DEFAULT_OUTCOME_CONTRACT.

    Returns:
        Manifest dict ready for JSON serialization.
    """
    # Use default outcome contract if not provided
    if outcome_contract is None:
        outcome_contract = DEFAULT_OUTCOME_CONTRACT.copy()

    # Validate checkpoint weights first: this preserves the exact "cannot be
    # empty" / "cannot be negative" messages for contracts that are missing
    # fields entirely (e.g. a fixture with no checkpoint_offsets_minutes),
    # before the broader profile-support check below would otherwise fire.
    _validate_checkpoint_weights(outcome_contract.get("checkpoint_weights", []))

    # A2-4: this batch supports exactly one outcome profile end-to-end. Reject
    # anything else explicitly rather than partially honoring it (see
    # UnsupportedOutcomeProfile and the withdrawn "custom contract preserved"
    # claim in tests/test_revision_manifest.py).
    validate_outcome_profile(outcome_contract)

    # support_window_hours defines the H15 target_support window from
    # validity_start; kept here as an explicit, profile-derived field
    # alongside (not replacing) the TAF-side source_validity window.
    support_window_us = int(outcome_contract["support_window_hours"] * 3600 * 1_000_000)

    targets = []

    for queue_name, queue in [("changed", changed_queue), ("unchanged", unchanged_queue)]:
        for candidate in queue:
            checkpoints = compute_checkpoints(candidate.validity_start_us, profile=outcome_contract)

            target_entry = {
                "target_id": candidate.target_id,
                "station": candidate.station,
                "validity_start": _us_to_iso(candidate.validity_start_us),
                "validity_start_us": candidate.validity_start_us,
                "validity_end": _us_to_iso(candidate.validity_end_us),
                "validity_end_us": candidate.validity_end_us,
                # A2-4: source_validity is the TAF forecast's own validity
                # window (identical to validity_start_us/validity_end_us
                # above, kept for backward compatibility). target_support is
                # the H15 scoring support window derived from this profile's
                # support_window_hours, distinct in principle even though it
                # currently starts at the same instant.
                "source_validity_start_us": candidate.validity_start_us,
                "source_validity_end_us": candidate.validity_end_us,
                "target_support_start_us": candidate.validity_start_us,
                "target_support_end_us": candidate.validity_start_us + support_window_us,
                "queue": queue_name,
                "checkpoints": [
                    {
                        "time": _us_to_iso(cp.time_us),
                        "time_us": cp.time_us,
                        "weight": cp.weight,
                    }
                    for cp in checkpoints
                ],
                # V17-02 / F02: Include both pre-deadline and whole-window counts
                "selection_signals": {
                    # Pre-deadline counts (used for scoring)
                    "revision_count": candidate.revision_count,
                    "tie_event_count": candidate.tie_event_count,
                    "evidence_change_count": candidate.evidence_change_count,
                    "lead_time_coverage_hours": round(candidate.lead_time_coverage_hours, 2),
                    # Whole-window counts (for comparison/debugging)
                    "revision_count_whole_window": candidate.revision_count_whole_window,
                    "tie_event_count_whole_window": candidate.tie_event_count_whole_window,
                    "evidence_change_count_whole_window": candidate.evidence_change_count_whole_window,
                },
            }
            targets.append(target_entry)

    frozen_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # V17-02 / F02: Determine schema version based on whether outcome_contract is included
    schema_version = "disastertrace.episode_manifest.v2" if outcome_contract else "disastertrace.episode_manifest.v1"

    manifest = {
        "schema": schema_version,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "input_fingerprints": {
            "stations_calendar_sha256": config_sha256,
            "taf_archive_summary": taf_archive_summary,
        },
        # V17-02 / F02: Include outcome contract in manifest (hashed into self_sha256)
        "outcome_contract": outcome_contract,
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

    V17-02 / F02: Now accepts both v1 and v2 schemas. v2 schema includes:
    - outcome_contract with thresholds, report_policy, weights
    - whole-window count fields in selection_signals

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Check schema - accept both v1 and v2
    schema = manifest.get("schema")
    valid_schemas = {
        "disastertrace.episode_manifest.v1",
        "disastertrace.episode_manifest.v2",
    }
    if schema not in valid_schemas:
        errors.append(f"Invalid schema: {schema}")

    is_v2 = schema == "disastertrace.episode_manifest.v2"

    # V17-02 / F02: Validate outcome_contract for v2 schema
    if is_v2:
        outcome_contract = manifest.get("outcome_contract")
        if outcome_contract is None:
            errors.append("v2 schema requires outcome_contract")
        else:
            # Validate required fields
            required_fields = {
                "thresholds_m",
                "report_policy",
                "support_window_hours",
                "checkpoint_weights",
            }
            missing = required_fields - set(outcome_contract.keys())
            if missing:
                errors.append(f"outcome_contract missing required fields: {missing}")

            # Validate checkpoint_weights
            weights = outcome_contract.get("checkpoint_weights", [])
            if not weights:
                errors.append("outcome_contract.checkpoint_weights cannot be empty")
            elif any(w < 0 for w in weights):
                errors.append("outcome_contract.checkpoint_weights cannot contain negative values")

            # Validate thresholds_m
            thresholds = outcome_contract.get("thresholds_m", [])
            if not thresholds:
                errors.append("outcome_contract.thresholds_m cannot be empty")

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

        # V17-02 / F02: For v2 schema, validate whole-window count fields exist
        if is_v2:
            signals = target.get("selection_signals", {})
            whole_window_fields = [
                "revision_count_whole_window",
                "tie_event_count_whole_window",
                "evidence_change_count_whole_window",
            ]
            for field in whole_window_fields:
                if field not in signals:
                    errors.append(f"Target {target_id}: v2 schema requires {field} in selection_signals")

    # Check self_sha256 integrity
    try:
        verify_manifest_integrity(manifest)
    except ValueError as e:
        errors.append(str(e))

    return errors
