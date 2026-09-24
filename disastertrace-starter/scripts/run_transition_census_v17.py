#!/usr/bin/env python3
"""V17-03: Evidence transition census for H15 data qualification.

This script performs a Y-blind (no ASOS/outcome reading) census of verifiable
target-relevant evidence changes in the TAF development material.

CRITICAL Y-ISOLATION BOUNDARIES:
- This script MUST NOT import any outcome_wiring symbols
- This script MUST NOT import compile_asos_csv_to_observations
- This script MUST NOT import load_asos_with_provenance
- This script MUST NOT import resolve_h15_outcomes
- This script MUST NOT import register_h15_outcomes
- This script MUST NOT read any file under asos/ directories
- This script MUST NOT access quarantine_holdout/

The census answers: Before prediction deadlines on fixed weather-risk targets,
do verifiable target-relevant evidence changes genuinely exist, in enough
volume/quality to support state-maintenance-vs-revision evaluation (H15)?

Sampling identity (A2-3): fixed sampling name "四时次日历采样" (four-timepoint
calendar sampling) -- 4 stations x 35 allowed months x daily 00/06/12/18Z
routine issuance hours, 1-hour target validity windows.

Checkpoint semantics (A2-3 / CE3 fix): for each candidate target slot, the
question "was this evidence change actually visible to the scoring process"
is answered by comparing each ledger entry's `available_at` against the three
scoring checkpoints T-60/T-40/T-20 via `visible_at(ledger, cutoff=checkpoint)`
-- NOT by comparing `issued_at` against the target's validity_start. The old
`issued_at < validity_start` filter was checkpoint-blind: a lone AMD issued at
T-10 (after all three checkpoints) would still be counted as an in-episode
change, even though it never became visible at T-60, T-40, or T-20. See CE3
in plan/plan_v17_0921 batch A2 notes.

Exit codes:
  0 - Census completed successfully
  1 - Census found issues but completed (>=1 target UNRESOLVED)
  2 - Hard gate failure (missing/mismatched files, or a station-wide
      ledger compilation failure -- R3)

R1-R4 corrections (census_semantics v2): see compute_slot_signals() (R1
independent arrival/change-like counts; R4 split unresolved flags),
generate_continuous_calendar_slots(allowed_year_months=...) (R2
unallowed_month exclusions), LedgerCompilationError (R3 fail-closed), and
_compute_slot_status() (R3/R4 status precedence and scope rationale).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Resolve project root for imports
_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))

# TAF-side imports only - NO outcome_wiring, NO ASOS
from disastertrace.revision_v1.access_policy import (
    AccessPolicy,
    AccessPolicyViolation,
    ReadVerificationError,
    read_verified_allowed_file,
)
from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream
from disastertrace.revision_v1.ledger import (
    compile_ledger,
    visible_at,
    Provenance,
    ProductLineage,
    _validity_windows_overlap_or_adjacent,
)
from disastertrace.revision_v1.tie_resolution import resolve_receipt_tie_strict
from disastertrace.monitoring_v1.providers.versions import latest_issuance
from disastertrace.monitoring_v1.targets import utc_us


# =============================================================================
# Explicit 140-file allow list (mirroring validate_dl3r_semantics.py)
# =============================================================================

STATIONS = ["KSFO", "KDEN", "KJFK", "KORD"]

# Build YEAR_MONTHS: 2023-01 through 2025-12, excluding 2025-02 (holdout)
YEAR_MONTHS = []
for year in [2023, 2024, 2025]:
    for month in range(1, 13):
        ym = f"{year:04d}{month:02d}"
        # Feb 2025 is holdout - NEVER read it
        if ym == "202502":
            continue
        YEAR_MONTHS.append(ym)

# Explicit expected files: 4 stations x 35 months = 140
EXPECTED_FILES = [(st, ym) for st in STATIONS for ym in YEAR_MONTHS]
assert len(EXPECTED_FILES) == 140, f"Expected 140 files, got {len(EXPECTED_FILES)}"

# Dashed YYYY-MM form of YEAR_MONTHS, for AccessPolicy.allowed_year_months.
# This is the explicit real-census allowlist: it must never be widened beyond
# the 140 files above (no glob, no 2025-02, no other months/stations).
ALLOWED_YEAR_MONTHS = frozenset(f"{ym[:4]}-{ym[4:6]}" for ym in YEAR_MONTHS)


# =============================================================================
# Sampling identity (A2-3)
# =============================================================================

# Registered/fixed sampling name. Any change to the sampling definition
# (stations, months, routine hours, target duration) requires a new name.
SAMPLING_NAME = "四时次日历采样"  # four-timepoint calendar sampling
ROUTINE_HOURS = [0, 6, 12, 18]
TARGET_DURATION_US = 3600 * 1_000_000  # 1-hour H15 target support


# =============================================================================
# Process grouping rule - DEFINED BEFORE RUNNING STATS
# =============================================================================

PROCESS_GROUPING_VERSION = "process_grouping.v1"
PROCESS_GROUPING_RULE = """
Process Grouping Rule (v1):
---------------------------
Evidence changes belong to the SAME weather process group if ALL of:
1. Same station (ICAO code)
2. Same UTC calendar day (defined by day-of-year at 00:00:00Z)

This rule means each station-day pair is ONE independent weather process.

Justification:
- TAF products are issued routinely every 6 hours (00Z, 06Z, 12Z, 18Z)
- A single weather system (front, storm) typically affects a station for 6-24 hours
- Calendar-day grouping is the standard unit for meteorological verification
- Same-day amendments/corrections are typically responses to the same weather evolution
- Cross-day boundaries represent synoptic breaks (new 00Z issuance cycle)
- This rule is simple, unambiguous, and verifiable from UTC timestamps

Count semantics:
- Total process groups = number of distinct (station, calendar_day) pairs
- Not "number of distinct synoptic events" which would require meteorological expertise
- Represents UPPER BOUND on independent weather-driven decisions
- (A2-3) Only computed over IN_EPISODE_CHANGE-eligible entries: strict-overlap,
  change-like (AMD/COR/CNL), visible by T-20 (INTERVAL_1/INTERVAL_2). Baseline,
  mirror-duplicate, and late/AFTER_LAST_SCORE evidence do not open a process group.

This rule is VERSION-LOCKED: the same rule version produces the same grouping.
Any changes to the rule require a new version (v2, v3, etc.).
"""

# Day in microseconds for calendar-day grouping
DAY_US = 24 * 3600 * 1_000_000

# (A2-3) How far before a slot's T-60 checkpoint a station's ledger must have
# at least one entry available for the "no earlier evidence" classification
# to be trusted as genuine absence rather than a coverage gap (e.g. right
# after the excluded 2025-02 month, or at the very start of the allowed
# calendar). 24h matches typical max TAF validity used elsewhere.
PREFIX_LOOKBACK_MARGIN_US = 24 * 3600 * 1_000_000


# =============================================================================
# Availability / relevance / status vocabularies (A2-3)
# =============================================================================

AVAIL_INITIAL_PREFIX = "INITIAL_PREFIX"
AVAIL_INTERVAL_1 = "INTERVAL_1"
AVAIL_INTERVAL_2 = "INTERVAL_2"
AVAIL_AFTER_LAST_SCORE = "AFTER_LAST_SCORE"
AVAIL_UNKNOWN = "UNKNOWN_AVAILABILITY"

AVAILABILITY_CLASSIFICATIONS = (
    AVAIL_INITIAL_PREFIX,
    AVAIL_INTERVAL_1,
    AVAIL_INTERVAL_2,
    AVAIL_AFTER_LAST_SCORE,
    AVAIL_UNKNOWN,
)

# Number of the three checkpoints (T-60, T-40, T-20) at which an entry with
# this checkpoint_classification is visible. Monotonic: INITIAL_PREFIX is
# visible at all three, AFTER_LAST_SCORE/UNKNOWN at none.
_CHECKPOINT_EXPOSURE_WEIGHT = {
    AVAIL_INITIAL_PREFIX: 3,
    AVAIL_INTERVAL_1: 2,
    AVAIL_INTERVAL_2: 1,
    AVAIL_AFTER_LAST_SCORE: 0,
    AVAIL_UNKNOWN: 0,
}

TIER_STRICT_OVERLAP = "strict_overlap"
TIER_ADJACENT_CONTEXT = "adjacent_context"

STATUS_NO_INPUT = "NO_INPUT"
STATUS_NO_APPLICABLE_EVIDENCE = "NO_APPLICABLE_EVIDENCE"
STATUS_INITIAL_ONLY_NO_CHANGE = "INITIAL_ONLY_NO_CHANGE"
STATUS_IN_EPISODE_CHANGE = "IN_EPISODE_CHANGE"
STATUS_UNRESOLVED = "UNRESOLVED"

SLOT_STATUSES = (
    STATUS_NO_INPUT,
    STATUS_NO_APPLICABLE_EVIDENCE,
    STATUS_INITIAL_ONLY_NO_CHANGE,
    STATUS_IN_EPISODE_CHANGE,
    STATUS_UNRESOLVED,
)

# change_type values that represent an actual content revision (as opposed to
# a baseline observation, a duplicate, or a bookkeeping reissue).
CHANGE_LIKE_TYPES = frozenset({"AMD", "COR", "CNL"})

# (R1) change_type values whose whole-report semantics hash is identical to an
# already-visible record: they are genuine new ARRIVALS but carry no new
# whole-report semantics. Used only for the descriptive
# `new_semantic_arrival_in_scoring_window` layer; they still count toward
# `any_new_arrival_in_scoring_window`.
DUPLICATE_LIKE_TYPES = frozenset({"mirror_duplicate", "no_change_reissue"})

# (R3) change_type recorded when a station's ledger could not be compiled.
CHANGE_TYPE_COMPILATION_ERROR = "compilation_error"

# Slot-level flag names (descriptive; never replace `status`).
FLAG_UNRESOLVED_IN_INITIAL_PREFIX = "unresolved_in_initial_prefix"
FLAG_UNRESOLVED_IN_SCORING_WINDOW = "unresolved_in_scoring_window"
FLAG_LEDGER_COMPILATION_ERROR = "ledger_compilation_error"

_SCORING_WINDOW_CLASSIFICATIONS = (AVAIL_INTERVAL_1, AVAIL_INTERVAL_2)

# Version tag for the corrected slot semantics (R1-R4). Bump on any change to
# how statuses/signals are derived.
CENSUS_SEMANTICS_VERSION = "a2_census_semantics.v2_r1_r4"

_CHANGE_TYPE_BY_KIND = {
    "amendment_supersedes": "AMD",
    "correction": "COR",
    "cancellation": "CNL",
    "mirror": "mirror_duplicate",
    "lossless_duplicate": "mirror_duplicate",
    "new_observation": "INITIAL_BASELINE",
    "no_change_reissue": "no_change_reissue",
    "baseline_update": "baseline_update",
    "late_superseded": "late_superseded",
}


# =============================================================================
# Change classification types
# =============================================================================

@dataclass
class EvidenceChange:
    """A single ledger entry classified against one candidate target slot.

    Unlike the pre-A2-3 version, this records EVERY ledger entry relevant (by
    validity overlap/adjacency) to the slot -- not just AMD/COR/CNL -- so that
    INITIAL_PREFIX baseline evidence and late/AFTER_LAST_SCORE evidence remain
    auditable rather than silently dropped. Callers that want only "real,
    in-episode" changes filter on:
        relevance_tier == "strict_overlap"
        and change_type in CHANGE_LIKE_TYPES
        and checkpoint_classification in (INTERVAL_1, INTERVAL_2)
    """
    target_station: str
    target_validity_start_us: int
    target_validity_end_us: int
    change_type: str  # AMD, COR, CNL, INITIAL_BASELINE, mirror_duplicate,
                       # no_change_reissue, baseline_update, late_superseded,
                       # compilation_error, unknown_<kind>
    predecessor_source_ids: list[str]  # full `supersedes` list (A2-2/A2-3:
                                        # never truncate to [0])
    current_source_id: str
    # raw_text_sha256: hash of the verified raw source FILE this change's
    # package was parsed from (from the A2-1 input readset via
    # read_verified_allowed_file). Shared across every package parsed from
    # the same station-month file -- it identifies the input, not the parsed
    # package.
    raw_text_sha256: str
    # native_semantics_sha256: hash of the parsed semantic content of THIS
    # package specifically (as computed by episode_compiler). Distinct from
    # raw_text_sha256: two different raw texts can parse to the same
    # semantics (mirror_duplicate), and one raw file yields many packages
    # that all share one raw_text_sha256 but have different semantics hashes.
    native_semantics_sha256: str
    issued_at_us: int
    dispute_status: str  # resolved, unresolved, none

    # --- A2-3 fields (defaulted so existing direct-construction call sites
    # that predate checkpoint-awareness keep working) ---
    candidate_predecessors: list[str] = field(default_factory=list)
    available_at_us: int | None = None
    availability_basis: str = "unknown"
    checkpoint_classification: str = AVAIL_UNKNOWN
    relevance_tier: str = TIER_STRICT_OVERLAP
    relation_status: str = "not_applicable"  # resolved | unresolved | not_applicable
    relation_reason: str | None = None
    # Fixed per A2-3 scope: this census does not compute/assess weather
    # content deltas, only evidence-change existence/visibility.
    target_content_change: str = "UNASSESSED"
    process_group_id: str | None = None


@dataclass
class CandidateSlot:
    """A continuous-calendar candidate target slot with its A2-3 verdict."""
    station: str
    validity_start_us: int
    validity_end_us: int
    checkpoint_t60_us: int
    checkpoint_t40_us: int
    checkpoint_t20_us: int
    changes: list[EvidenceChange] = field(default_factory=list)
    status: str = STATUS_NO_INPUT  # one of SLOT_STATUSES, mutually exclusive
    flags: list[str] = field(default_factory=list)
    # (R1/R4) Independent, NON-mutually-exclusive per-slot signals, computed
    # by compute_slot_signals() alongside (never instead of) `status`.
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExclusionRecord:
    """One entry in the A2-3 exclusion ledger: a candidate slot or piece of
    evidence that was deliberately left out of the census, and why.

    reason == "protected_window" covers calendar-level exclusions (a slot's
    target validity or one of its checkpoints falls inside
    [holdout_start_us, holdout_end_us)). It is checked first, so a slot that
    is both protected and in an unallowed month is recorded as
    protected_window (with `detail["year_month_allowed"]` = False).

    reason == "unallowed_month" (R2) covers calendar-level exclusions of a
    candidate slot whose target validity month (YYYY-MM) is not in the
    census's allowed_year_months. Previously this reason was never populated
    on the assumption that AccessPolicy's refusal to READ files outside the
    140-file allowlist made it unreachable -- but that conflated "no file can
    be read for this month" with "no slot should exist for this month": such
    slots were still generated and silently counted as NO_APPLICABLE_EVIDENCE.
    generate_continuous_calendar_slots() now excludes them explicitly.
    """
    reason: str  # "protected_window" | "unallowed_month"
    station: str | None
    description: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class CensusResult:
    """Complete census result (A2-3 checkpoint-aware shape)."""
    # File integrity
    files_checked: int
    files_ok: int
    files_missing: list[str]
    files_hash_mismatch: list[dict]

    # Sampling identity
    sampling_name: str

    # Continuous calendar
    total_continuous_calendar_slots: int
    slots_by_status: dict[str, int]  # mutually exclusive, sums to total above

    # A2-3 counts. Each is a raw count; any RATE derived from these must be
    # computed by the caller with an explicit numerator/denominator/filter
    # rather than baked in here.
    n_unique_sources: int
    n_unique_relation_edges: int
    n_target_change_associations: int
    n_targets_with_initial_evidence: int
    n_targets_with_in_episode_change: int
    n_targets_with_unresolved: int
    n_checkpoint_exposures: int
    n_candidate_blocks: int  # distinct (station, target_day), descriptive

    # (R1/R4) Independent per-slot signal counts. NOT mutually exclusive with
    # each other or with slots_by_status; each is "number of slots for which
    # the named signal is true". See compute_slot_signals().
    n_targets_with_any_new_arrival: int
    n_targets_with_new_semantic_arrival: int
    n_targets_with_change_like_arrival: int
    n_targets_with_unresolved_in_initial_prefix: int
    n_targets_with_unresolved_in_scoring_window: int
    n_initial_only_status_with_any_new_arrival: int

    changes_by_type: dict[str, int]

    # Process groups (computed only over IN_EPISODE_CHANGE-eligible changes)
    total_process_groups: int
    process_groups_by_station: dict[str, int]

    # Package stats
    total_packages_compiled: int
    skipped_frames: int

    # Exclusion ledger: protected-window / unallowed-month exclusions, kept
    # as a separate list rather than folded into slot counts.
    exclusions: list[ExclusionRecord]


# =============================================================================
# File integrity verification
# =============================================================================

def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class VerifiedTafFile:
    """A single (body, receipt) pair that has passed AccessPolicy and
    content-integrity verification via read_verified_allowed_file().

    Carries the already-read body text so callers (run_census's package
    compilation step) never need to open the file a second time.
    """
    station: str
    year_month: str  # compact "YYYYMM", matches EXPECTED_FILES
    body_path: Path
    json_path: Path
    raw_text: str
    raw_text_sha256: str
    receipt_sha256: str
    size_bytes: int


def verify_140_files(
    bulk_dir: Path,
    policy: AccessPolicy,
) -> tuple[list[VerifiedTafFile], list[str], list[dict]]:
    """Verify all 140 expected files exist, are allowed by `policy`, and have
    body bytes matching their receipt's declared SHA256.

    Every (body, receipt) pair is checked through read_verified_allowed_file(),
    the shared AccessPolicy-gated entry point (A2-1): no direct open/read of
    real archive content happens here outside of that call. The .exists()
    checks below only stat the caller-controlled EXPECTED_FILES path shape,
    so a missing file and an access-denied file remain distinct outcomes
    (bucketed into `missing` vs `mismatches` respectively) rather than being
    conflated.

    Returns:
        Tuple of (verified_files, missing, hash_mismatches) where:
        - verified_files: list of VerifiedTafFile for valid, allowed files
        - missing: list of missing file descriptions
        - hash_mismatches: list of rejection/mismatch dicts
    """
    verified: list[VerifiedTafFile] = []
    missing: list[str] = []
    mismatches: list[dict] = []

    # Hard boundary check - NEVER access quarantine_holdout
    if "quarantine_holdout" in str(bulk_dir):
        raise RuntimeError(f"BOUNDARY VIOLATION: bulk_dir contains quarantine_holdout: {bulk_dir}")

    for station, year_month in EXPECTED_FILES:
        # Additional boundary check for 202502 (should never be in list, but defense in depth)
        if year_month == "202502":
            raise RuntimeError("BOUNDARY VIOLATION: 202502 should not be in EXPECTED_FILES")

        body_file = bulk_dir / f"{station}_{year_month}.body"
        json_file = bulk_dir / f"{station}_{year_month}.json"

        if not body_file.exists():
            missing.append(f"{station}_{year_month}.body")
            continue
        if not json_file.exists():
            missing.append(f"{station}_{year_month}.json")
            continue

        dashed_year_month = f"{year_month[:4]}-{year_month[4:6]}"
        try:
            verified_input = read_verified_allowed_file(
                policy, body_file, json_file, year_month=dashed_year_month
            )
        except AccessPolicyViolation as e:
            mismatches.append({
                "file": f"{station}_{year_month}.body",
                "reason": f"access_policy_violation: {e}",
            })
            continue
        except ReadVerificationError as e:
            mismatches.append({
                "file": f"{station}_{year_month}.body",
                "reason": f"read_verification_error: {e}",
            })
            continue

        verified.append(VerifiedTafFile(
            station=station,
            year_month=year_month,
            body_path=Path(verified_input.canonical_body_path),
            json_path=Path(verified_input.canonical_receipt_path),
            raw_text=verified_input.body.decode("utf-8", errors="replace"),
            raw_text_sha256=verified_input.raw_text_sha256,
            receipt_sha256=verified_input.receipt_sha256,
            size_bytes=verified_input.size_bytes,
        ))

    return verified, missing, mismatches


# =============================================================================
# Continuous calendar enumeration
# =============================================================================

def generate_continuous_calendar_slots(
    calendar_start_us: int,
    calendar_end_us: int,
    holdout_start_us: int,
    holdout_end_us: int,
    *,
    allowed_year_months: frozenset[str] | None,
) -> tuple[list[CandidateSlot], list[ExclusionRecord]]:
    """Generate all routine-hour slots across the full calendar for all
    stations, and a matching exclusion ledger for any slot skipped because
    its target validity or one of its checkpoints falls inside the protected
    window (hard boundary #3), or (R2) because its target validity month is
    not in `allowed_year_months`.

    Per the H15 contract: every station x day x hour routine slot across the
    35-month calendar, per the stations_calendar config (sampling name:
    SAMPLING_NAME).

    Routine TAF hours are: 00Z, 06Z, 12Z, 18Z (every 6 hours).

    `allowed_year_months` (R2) is keyword-only and REQUIRED so no caller can
    silently forget it: pass the census's dashed "YYYY-MM" allowlist, or an
    explicit None to disable month filtering (unit tests only). The month of
    a slot is the UTC month of its target validity_start (for this sampling,
    identical to the calendar day's month: targets are 1h windows starting
    at 00/06/12/18Z). The protected-window check runs first, so its
    exclusion reason is preserved for holdout slots.
    """
    hour_us = 3600 * 1_000_000
    day_us = 24 * hour_us

    slots: list[CandidateSlot] = []
    exclusions: list[ExclusionRecord] = []

    # Iterate through each day
    current_day_start = calendar_start_us
    while current_day_start < calendar_end_us:
        for station in STATIONS:
            for routine_hour in ROUTINE_HOURS:
                # Target window: the hour starting at routine_hour
                validity_start = current_day_start + routine_hour * hour_us
                validity_end = validity_start + hour_us

                # Skip if outside calendar
                if validity_end > calendar_end_us:
                    continue

                # Checkpoints: T-60, T-40, T-20 before validity_start
                t60 = validity_start - 60 * 60 * 1_000_000  # 60 minutes
                t40 = validity_start - 40 * 60 * 1_000_000  # 40 minutes
                t20 = validity_start - 20 * 60 * 1_000_000  # 20 minutes

                overlaps_holdout = (
                    validity_start < holdout_end_us and validity_end > holdout_start_us
                )
                checkpoint_in_holdout = any(
                    holdout_start_us <= cp < holdout_end_us for cp in (t60, t40, t20)
                )

                slot_dt = datetime.fromtimestamp(validity_start / 1_000_000, tz=timezone.utc)
                slot_year_month = f"{slot_dt.year:04d}-{slot_dt.month:02d}"
                month_allowed = (
                    allowed_year_months is None or slot_year_month in allowed_year_months
                )

                if overlaps_holdout or checkpoint_in_holdout:
                    exclusions.append(ExclusionRecord(
                        reason="protected_window",
                        station=station,
                        description=(
                            f"candidate slot at {station} validity="
                            f"[{validity_start}, {validity_end}) excluded: "
                            f"target validity or a checkpoint falls in the "
                            f"protected window [{holdout_start_us}, {holdout_end_us})"
                        ),
                        detail={
                            "validity_start_us": validity_start,
                            "validity_end_us": validity_end,
                            "checkpoint_t60_us": t60,
                            "checkpoint_t40_us": t40,
                            "checkpoint_t20_us": t20,
                            "overlaps_holdout": overlaps_holdout,
                            "checkpoint_in_holdout": checkpoint_in_holdout,
                            "year_month": slot_year_month,
                            "year_month_allowed": month_allowed,
                        },
                    ))
                    continue

                if not month_allowed:
                    # (R2) The slot's target month is outside the permitted
                    # calendar. AccessPolicy would refuse to read any file
                    # for it, so if it were kept it would masquerade as
                    # NO_APPLICABLE_EVIDENCE. Exclude it explicitly instead.
                    exclusions.append(ExclusionRecord(
                        reason="unallowed_month",
                        station=station,
                        description=(
                            f"candidate slot at {station} validity="
                            f"[{validity_start}, {validity_end}) excluded: "
                            f"target month {slot_year_month} is not in the "
                            f"census's allowed_year_months"
                        ),
                        detail={
                            "validity_start_us": validity_start,
                            "validity_end_us": validity_end,
                            "checkpoint_t60_us": t60,
                            "checkpoint_t40_us": t40,
                            "checkpoint_t20_us": t20,
                            "year_month": slot_year_month,
                        },
                    ))
                    continue

                slot = CandidateSlot(
                    station=station,
                    validity_start_us=validity_start,
                    validity_end_us=validity_end,
                    checkpoint_t60_us=t60,
                    checkpoint_t40_us=t40,
                    checkpoint_t20_us=t20,
                )
                slots.append(slot)

        current_day_start += day_us

    return slots, exclusions


# =============================================================================
# Evidence change classification (A2-3 / CE3 fix)
# =============================================================================

def _classify_relevance_tier(slot: CandidateSlot, pkg: dict) -> str | None:
    """Return TIER_STRICT_OVERLAP, TIER_ADJACENT_CONTEXT, or None (not
    relevant at all) for `pkg` against `slot`'s target validity window.

    `_validity_windows_overlap_or_adjacent` (ledger.py) returns a single
    combined overlap-OR-adjacent boolean and does not itself distinguish the
    two cases, so an additional strict, non-zero-width overlap test is
    layered on top here to implement the plan's two-tier relevance
    requirement.
    """
    slot_window = {"valid_start": slot.validity_start_us, "valid_end": slot.validity_end_us}
    if not _validity_windows_overlap_or_adjacent(slot_window, pkg):
        return None

    p_start = pkg.get("valid_start", 0)
    p_end = pkg.get("valid_end", 0)
    strict_overlap = p_start < slot.validity_end_us and slot.validity_start_us < p_end
    return TIER_STRICT_OVERLAP if strict_overlap else TIER_ADJACENT_CONTEXT


def classify_changes_for_slot(
    slot: CandidateSlot,
    packages_by_station: dict[str, list[dict]],
    *,
    station_ledgers: dict[str, list[dict]] | None = None,
) -> list[EvidenceChange]:
    """Classify every ledger entry relevant to a candidate slot, using
    checkpoint-aware visibility.

    This does NOT filter candidate evidence by `issued_at < validity_start`
    -- that check is checkpoint-blind and is exactly the CE3 defect (a lone
    AMD issued at T-10 would still count as an in-episode change even though
    it never became visible at T-60/T-40/T-20). Instead, every ledger entry
    whose underlying package's validity overlaps or is adjacent to the
    slot's target window is classified by WHEN it became visible
    (`available_at`) relative to the three checkpoints, via
    `visible_at(ledger, cutoff=checkpoint)`. `visible_at` is an inclusive
    `<=` filter, so an entry available exactly at a checkpoint lands in that
    checkpoint's view (the "等于 checkpoint 时先纳入再形成视图" offline
    rule falls out of this for free).

    `station_ledgers[station]`, when given, must be `compile_ledger()` run
    ONCE over the station's full allowed package stream (prefix-stable), not
    a per-slot subset -- passing a pre-filtered subset would corrupt
    resolved/unresolved relation classification for entries whose true
    predecessor set depends on packages outside the slot's own window. When
    not given (direct unit-test callers), a whole-stream ledger is compiled
    here from `packages_by_station[slot.station]` as a fallback -- still
    never a slot-filtered subset.
    """
    station_packages = packages_by_station.get(slot.station, [])
    if not station_packages:
        return []

    if station_ledgers is not None and slot.station in station_ledgers:
        ledger = station_ledgers[slot.station]
    else:
        try:
            ledger = compile_ledger(station_packages)
        except Exception:
            # Whole-station compilation failed: record every package as an
            # unresolved compilation error rather than silently dropping it.
            # (R3) _compute_slot_status() checks for these records FIRST and
            # returns STATUS_UNRESOLVED + FLAG_LEDGER_COMPILATION_ERROR; before
            # that check existed, these AVAIL_UNKNOWN records fell through to
            # NO_APPLICABLE_EVIDENCE + "late_evidence_excluded_from_scoring",
            # i.e. this "safe" fallback was itself silently degraded. Note
            # run_census() never reaches this path: its Step 3.5 raises
            # LedgerCompilationError instead (see there).
            return [
                EvidenceChange(
                    target_station=slot.station,
                    target_validity_start_us=slot.validity_start_us,
                    target_validity_end_us=slot.validity_end_us,
                    change_type=CHANGE_TYPE_COMPILATION_ERROR,
                    predecessor_source_ids=[],
                    current_source_id=pkg.get("source_id", "unknown"),
                    raw_text_sha256=pkg.get("_source_raw_text_sha256", "unknown"),
                    native_semantics_sha256=pkg.get("native_semantics_sha256", "unknown"),
                    issued_at_us=pkg.get("issued_at", 0),
                    dispute_status="unresolved",
                    relation_status="unresolved",
                    checkpoint_classification=AVAIL_UNKNOWN,
                )
                for pkg in station_packages
            ]

    pkg_by_source_id = {pkg["source_id"]: pkg for pkg in station_packages}

    t60_view = {e["source_id"] for e in visible_at(ledger, cutoff=slot.checkpoint_t60_us)}
    t40_view = {e["source_id"] for e in visible_at(ledger, cutoff=slot.checkpoint_t40_us)}
    t20_view = {e["source_id"] for e in visible_at(ledger, cutoff=slot.checkpoint_t20_us)}

    changes: list[EvidenceChange] = []
    for entry in ledger:
        source_id = entry.get("source_id", "unknown")
        orig_pkg = pkg_by_source_id.get(source_id)
        if orig_pkg is None:
            continue

        relevance_tier = _classify_relevance_tier(slot, orig_pkg)
        if relevance_tier is None:
            continue

        available_at_us = entry.get("available_at")
        availability_basis = entry.get("availability_basis", "unknown")

        if source_id in t60_view:
            checkpoint_classification = AVAIL_INITIAL_PREFIX
        elif source_id in t40_view:
            checkpoint_classification = AVAIL_INTERVAL_1
        elif source_id in t20_view:
            checkpoint_classification = AVAIL_INTERVAL_2
        elif available_at_us is None:
            checkpoint_classification = AVAIL_UNKNOWN
        else:
            checkpoint_classification = AVAIL_AFTER_LAST_SCORE

        kind = entry.get("kind", "unknown")
        change_type = _CHANGE_TYPE_BY_KIND.get(kind, f"unknown_{kind}")

        supersedes = list(entry.get("supersedes") or [])
        candidate_predecessors = list(entry.get("candidate_predecessors") or [])
        relation_status = entry.get("relation_status", "not_applicable")
        relation_reason = entry.get("relation_reason")
        dispute_status = "unresolved" if relation_status == "unresolved" else "none"

        changes.append(EvidenceChange(
            target_station=slot.station,
            target_validity_start_us=slot.validity_start_us,
            target_validity_end_us=slot.validity_end_us,
            change_type=change_type,
            predecessor_source_ids=supersedes,
            current_source_id=source_id,
            raw_text_sha256=orig_pkg.get("_source_raw_text_sha256", "unknown"),
            native_semantics_sha256=orig_pkg.get("native_semantics_sha256", "unknown"),
            issued_at_us=orig_pkg.get("issued_at", 0),
            dispute_status=dispute_status,
            candidate_predecessors=candidate_predecessors,
            available_at_us=available_at_us,
            availability_basis=availability_basis,
            checkpoint_classification=checkpoint_classification,
            relevance_tier=relevance_tier,
            relation_status=relation_status,
            relation_reason=relation_reason,
        ))

    return changes


def _compute_slot_status(
    changes: list[EvidenceChange],
    *,
    station_earliest_available_us: int | None,
    checkpoint_t60_us: int,
) -> tuple[str, list[str]]:
    """Derive a slot's mutually-exclusive main status plus descriptive flags
    from its classified EvidenceChange list. Caller handles STATUS_NO_INPUT
    separately (a station with zero packages never reaches here).

    Status precedence (mutually exclusive, first match wins):
      1. (R3) any compilation_error record -> UNRESOLVED
         (+ flag ledger_compilation_error). A failed ledger compile must
         never be reported as "no applicable evidence".
      2. no strict-overlap evidence -> NO_APPLICABLE_EVIDENCE
      3. no strict-overlap evidence visible by T-20 -> NO_APPLICABLE_EVIDENCE
      4. any visible strict-overlap record with relation_status
         "unresolved" -> UNRESOLVED
      5. any change-like (AMD/COR/CNL) record in INTERVAL_1/2 ->
         IN_EPISODE_CHANGE (definition unchanged from A2-3)
      6. otherwise -> INITIAL_ONLY_NO_CHANGE

    (R4) scope decision for rule 4: UNRESOLVED still fires when the
    unresolved relation is ONLY in the initial prefix (not just the scoring
    window). Rationale: this mutually-exclusive status is the slot's
    single "is this slot a clean example" verdict. A prefix-only unresolved
    relation (e.g. two same-instant AMDs with no receipt authority, both
    visible at T-60) means the agent's T-60 starting state itself has no
    determinate authoritative version, so the slot is not a clean
    INITIAL_ONLY_NO_CHANGE control nor a clean IN_EPISODE_CHANGE example.
    Narrowing rule 4 would silently relabel those slots as clean. No
    information is lost by keeping it fail-closed, because (R1/R4) the
    independent signals from compute_slot_signals() report arrivals and
    change-like arrivals regardless of status, and the two flags
    FLAG_UNRESOLVED_IN_INITIAL_PREFIX / FLAG_UNRESOLVED_IN_SCORING_WINDOW
    (added here, and counted separately in the summary) say WHICH kind of
    unresolved it is. This also keeps the historical UNRESOLVED count
    directly comparable.
    """
    flags: list[str] = []

    if any(c.change_type == CHANGE_TYPE_COMPILATION_ERROR for c in changes):
        flags.append(FLAG_LEDGER_COMPILATION_ERROR)
        return STATUS_UNRESOLVED, flags

    strict = [c for c in changes if c.relevance_tier == TIER_STRICT_OVERLAP]
    adjacent = [c for c in changes if c.relevance_tier == TIER_ADJACENT_CONTEXT]

    if not strict:
        if adjacent:
            flags.append("adjacent_only")
        return STATUS_NO_APPLICABLE_EVIDENCE, flags

    visible = [
        c for c in strict
        if c.checkpoint_classification in (AVAIL_INITIAL_PREFIX, AVAIL_INTERVAL_1, AVAIL_INTERVAL_2)
    ]
    if not visible:
        # Relevant evidence exists in the raw archive but none of it was
        # actually visible by T-20 (the CE3 case: e.g. a lone AMD at T-10).
        flags.append("late_evidence_excluded_from_scoring")
        return STATUS_NO_APPLICABLE_EVIDENCE, flags

    if (
        station_earliest_available_us is not None
        and station_earliest_available_us > checkpoint_t60_us - PREFIX_LOOKBACK_MARGIN_US
    ):
        flags.append("prefix_coverage_insufficient")

    unresolved_prefix = any(
        c.relation_status == "unresolved"
        and c.checkpoint_classification == AVAIL_INITIAL_PREFIX
        for c in visible
    )
    unresolved_window = any(
        c.relation_status == "unresolved"
        and c.checkpoint_classification in _SCORING_WINDOW_CLASSIFICATIONS
        for c in visible
    )
    if unresolved_prefix:
        flags.append(FLAG_UNRESOLVED_IN_INITIAL_PREFIX)
    if unresolved_window:
        flags.append(FLAG_UNRESOLVED_IN_SCORING_WINDOW)

    if unresolved_prefix or unresolved_window:
        return STATUS_UNRESOLVED, flags

    if any(
        c.checkpoint_classification in _SCORING_WINDOW_CLASSIFICATIONS
        and c.change_type in CHANGE_LIKE_TYPES
        for c in visible
    ):
        return STATUS_IN_EPISODE_CHANGE, flags

    return STATUS_INITIAL_ONLY_NO_CHANGE, flags


def compute_slot_signals(changes: list[EvidenceChange]) -> dict[str, Any]:
    """(R1/R4) Independent, NON-mutually-exclusive per-slot signals.

    Computed from the same classified EvidenceChange list as
    _compute_slot_status(), but never gated by the status precedence: e.g. a
    slot can be UNRESOLVED and still have `change_like_arrival_in_scoring_window`
    True, or INITIAL_ONLY_NO_CHANGE and still have
    `any_new_arrival_in_scoring_window` True (the R1 case: a routine new
    baseline TAF first becoming visible between T-60 and T-20).

    All signals only consider strict-overlap records. "Scoring window" means
    checkpoint_classification in (INTERVAL_1, INTERVAL_2), i.e. first
    visible after T-60 and at or before T-20.

    Layers (each a superset-or-equal of the next, by construction, except the
    unresolved flags which are orthogonal):
      any_new_arrival_in_scoring_window: any record newly visible in the
          window, regardless of change_type (source-arrival layer).
      new_semantic_arrival_in_scoring_window: same, excluding records whose
          whole-report semantics hash duplicates an already-visible record
          (mirror_duplicate / no_change_reissue). WHOLE-REPORT semantics
          only -- this is NOT evidence that target-window content changed.
      change_like_arrival_in_scoring_window: the original A2-3 definition
          (change_type AMD/COR/CNL), independent of relation status.
      unresolved_in_initial_prefix / unresolved_in_scoring_window: whether a
          visible record with relation_status "unresolved" sits in the T-60
          prefix vs. arrived during the window.
      target_content_change: always "UNASSESSED" -- this census has no
          target-window content projection of the TAF periods (packages only
          carry a whole-report hash). Never interpret absence of a
          projection as "no content change".
    """
    strict = [c for c in changes if c.relevance_tier == TIER_STRICT_OVERLAP]
    window = [c for c in strict if c.checkpoint_classification in _SCORING_WINDOW_CLASSIFICATIONS]
    window_non_error = [c for c in window if c.change_type != CHANGE_TYPE_COMPILATION_ERROR]
    return {
        "any_new_arrival_in_scoring_window": bool(window_non_error),
        "n_new_arrivals_in_scoring_window": len(window_non_error),
        "scoring_window_arrival_change_types": sorted(c.change_type for c in window_non_error),
        "new_semantic_arrival_in_scoring_window": any(
            c.change_type not in DUPLICATE_LIKE_TYPES for c in window_non_error
        ),
        "change_like_arrival_in_scoring_window": any(
            c.change_type in CHANGE_LIKE_TYPES for c in window_non_error
        ),
        "unresolved_in_initial_prefix": any(
            c.relation_status == "unresolved"
            and c.checkpoint_classification == AVAIL_INITIAL_PREFIX
            for c in strict
        ),
        "unresolved_in_scoring_window": any(
            c.relation_status == "unresolved" for c in window
        ),
        "ledger_compilation_error": any(
            c.change_type == CHANGE_TYPE_COMPILATION_ERROR for c in changes
        ),
        "target_content_change": "UNASSESSED",
    }


# =============================================================================
# Process grouping
# =============================================================================

def assign_process_groups(changes: list[EvidenceChange]) -> dict[str, list[EvidenceChange]]:
    """Assign changes to weather process groups per the v1 rule.

    Groups changes by:
    1. Same station
    2. Same UTC calendar day (issued_at timestamp)

    Each (station, calendar_day) pair is one process group. Callers should
    pass only IN_EPISODE_CHANGE-eligible changes (see PROCESS_GROUPING_RULE).
    """
    if not changes:
        return {}

    groups: dict[str, list[EvidenceChange]] = {}

    # Group by (station, calendar_day) where calendar_day = issued_at_us // DAY_US
    for change in changes:
        # Compute calendar day (days since epoch)
        calendar_day = change.issued_at_us // DAY_US
        group_id = f"{change.target_station}_{calendar_day}"

        if group_id not in groups:
            groups[group_id] = []
        groups[group_id].append(change)
        change.process_group_id = group_id

    return groups


# =============================================================================
# Main census logic
# =============================================================================

class LedgerCompilationError(RuntimeError):
    """(R3) A station's whole-stream ledger could not be compiled.

    Raised by run_census() Step 3.5 instead of substituting an empty ledger.
    main() maps it to exit code 2 (hard gate failure), distinct from exit
    code 1 (census completed with UNRESOLVED slots).
    """

    def __init__(self, station: str, cause: BaseException):
        super().__init__(
            f"ledger compilation failed for station {station}: "
            f"{type(cause).__name__}: {cause}"
        )
        self.station = station
        self.cause = cause


def run_census(
    bulk_dir: Path,
    config_path: Path,
    artifacts_dir: Path | None = None,
) -> CensusResult:
    """Run the complete transition census.

    Args:
        bulk_dir: Path to DL-3R bulk archive
        config_path: Path to stations_calendar_v16.json
        artifacts_dir: Optional path for detailed output

    Returns:
        CensusResult with all census statistics
    """
    # Load calendar config
    with open(config_path, "r") as f:
        config = json.load(f)

    calendar_start_us = utc_us(config["calendar_start"])
    calendar_end_us = utc_us(config["calendar_end"])
    holdout_start_us = utc_us(config["holdout_exclusion"]["window_start"])
    holdout_end_us = utc_us(config["holdout_exclusion"]["window_end"])

    # Step 1: Build the access policy scoped to bulk_dir + the 140-file
    # allowlist, and verify all 140 expected files through it (A2-1: no
    # direct glob/open of real archive content outside AccessPolicy).
    print("Step 1: Verifying 140 expected files...")
    policy = AccessPolicy.from_config(
        config,
        allowed_root=Path(bulk_dir),
        allowed_year_months=ALLOWED_YEAR_MONTHS,
    )
    verified, missing, mismatches = verify_140_files(bulk_dir, policy)
    print(f"  Verified: {len(verified)}, Missing: {len(missing)}, Mismatched: {len(mismatches)}")

    if missing or mismatches:
        print("WARNING: File integrity issues found")
        for m in missing[:5]:
            print(f"  Missing: {m}")
        for mm in mismatches[:5]:
            print(f"  Mismatch: {mm['file']}")

    # Step 2: Compile all TAF packages from the already-verified bytes.
    # verify_140_files() already read and hashed every body via
    # read_verified_allowed_file(); this step must not re-open the files.
    print("\nStep 2: Compiling TAF packages from verified files...")
    all_packages: list[dict] = []
    total_skipped = 0
    readset_records: list[dict] = []

    for vf in verified:
        reference_month = f"{vf.year_month[:4]}-{vf.year_month[4:6]}"
        packages, skipped = compile_afos_taf_stream(
            vf.raw_text,
            station=vf.station,
            reference_month=reference_month,
        )
        for pkg in packages:
            # Tag each package with the file-level raw-text identity it was
            # parsed from (distinct from the package's own parsed-semantics
            # hash) so EvidenceChange can report both (A2-1).
            pkg["_source_raw_text_sha256"] = vf.raw_text_sha256
        all_packages.extend(packages)
        total_skipped += len(skipped)

        readset_records.append({
            "station": vf.station,
            "year_month": reference_month,
            "canonical_body_path": str(vf.body_path),
            "canonical_receipt_path": str(vf.json_path),
            "size_bytes": vf.size_bytes,
            "raw_text_sha256": vf.raw_text_sha256,
            "receipt_sha256": vf.receipt_sha256,
        })

    print(f"  Total packages compiled: {len(all_packages)}")
    print(f"  Skipped frames: {total_skipped}")

    # Index packages by station
    packages_by_station: dict[str, list[dict]] = defaultdict(list)
    for pkg in all_packages:
        packages_by_station[pkg["station"]].append(pkg)

    # Step 3: Generate continuous calendar slots
    print("\nStep 3: Generating continuous calendar slots...")
    slots, calendar_exclusions = generate_continuous_calendar_slots(
        calendar_start_us,
        calendar_end_us,
        holdout_start_us,
        holdout_end_us,
        allowed_year_months=ALLOWED_YEAR_MONTHS,
    )
    exclusions_by_reason: dict[str, int] = defaultdict(int)
    for excl in calendar_exclusions:
        exclusions_by_reason[excl.reason] += 1
    print(f"  Total slots: {len(slots)}  (sampling: {SAMPLING_NAME})")
    print(f"  Calendar-level exclusions: {len(calendar_exclusions)} {dict(exclusions_by_reason)}")

    # Step 3.5: Compile one prefix-stable ledger per station across its FULL
    # allowed package stream (A2-3 / CE3 fix: the old code recompiled a
    # filtered, checkpoint-blind ledger separately per slot). Performance
    # note: Step 4 below still does an O(slots x station_ledger_size) scan;
    # this is the approach the plan specifies for A2-3 correctness, and any
    # further optimization for a full real run is deferred to A2-6.
    #
    # (R3) Fail closed on a station-wide compile failure. The previous code
    # printed a warning and cached `ledger = []`; because
    # classify_changes_for_slot() trusts a cached station_ledgers entry
    # first, every slot of that station then silently became
    # NO_APPLICABLE_EVIDENCE (indistinguishable from genuine absence).
    # Omitting the key instead was rejected: the per-slot fallback would
    # recompile the SAME whole-station stream (deterministically failing
    # again) once per slot (~4k slots/station, each an O(n^2) compile), and
    # a station-wide failure invalidates ~1/4 of the census denominator, so
    # a partial result would not be a meaningful census anyway. main() maps
    # this to exit code 2.
    print("\nStep 3.5: Compiling per-station ledgers (whole allowed stream)...")
    station_ledgers: dict[str, list[dict]] = {}
    station_earliest_available: dict[str, int | None] = {}
    for station, pkgs in packages_by_station.items():
        try:
            ledger = compile_ledger(pkgs)
        except Exception as exc:
            print(f"  ERROR: ledger compilation failed for {station}: {exc}")
            raise LedgerCompilationError(station, exc) from exc
        station_ledgers[station] = ledger
        available_values = [
            e["available_at"] for e in ledger if e.get("available_at") is not None
        ]
        station_earliest_available[station] = min(available_values) if available_values else None

    # Step 4: Classify changes for each slot
    print("\nStep 4: Classifying evidence changes for each slot...")
    all_changes: list[EvidenceChange] = []

    for i, slot in enumerate(slots):
        if i % 10000 == 0:
            print(f"  Processing slot {i}/{len(slots)}...")

        if not packages_by_station.get(slot.station):
            slot.status = STATUS_NO_INPUT
            slot.flags = []
            continue

        changes = classify_changes_for_slot(
            slot, packages_by_station, station_ledgers=station_ledgers,
        )
        slot.changes = changes
        status, flags = _compute_slot_status(
            changes,
            station_earliest_available_us=station_earliest_available.get(slot.station),
            checkpoint_t60_us=slot.checkpoint_t60_us,
        )
        slot.status = status
        slot.flags = flags
        slot.signals = compute_slot_signals(changes)
        all_changes.extend(changes)

    slots_by_status: dict[str, int] = {s: 0 for s in SLOT_STATUSES}
    for slot in slots:
        slots_by_status[slot.status] += 1

    print(f"  Slots by status: {slots_by_status}")

    def _n_slots_with(signal: str) -> int:
        return sum(1 for s in slots if s.signals.get(signal) is True)

    n_initial_only_status_with_any_new_arrival = sum(
        1 for s in slots
        if s.status == STATUS_INITIAL_ONLY_NO_CHANGE
        and s.signals.get("any_new_arrival_in_scoring_window") is True
    )

    # Step 5: Assign process groups (only over IN_EPISODE_CHANGE-eligible
    # changes -- see PROCESS_GROUPING_RULE)
    print("\nStep 5: Assigning process groups...")
    episode_changes = [
        c for c in all_changes
        if c.relevance_tier == TIER_STRICT_OVERLAP
        and c.change_type in CHANGE_LIKE_TYPES
        and c.checkpoint_classification in (AVAIL_INTERVAL_1, AVAIL_INTERVAL_2)
    ]
    process_groups = assign_process_groups(episode_changes)
    print(f"  Total process groups: {len(process_groups)}")

    # Count by station
    groups_by_station: dict[str, int] = defaultdict(int)
    for group_id in process_groups:
        station = group_id.split("_")[0]
        groups_by_station[station] += 1

    # Step 6: Compute statistics
    print("\nStep 6: Computing statistics...")

    changes_by_type: dict[str, int] = defaultdict(int)
    for change in all_changes:
        changes_by_type[change.change_type] += 1

    n_unique_sources = len({c.current_source_id for c in all_changes})
    n_unique_relation_edges = len({
        (c.change_type, c.current_source_id, frozenset(c.candidate_predecessors))
        for c in all_changes
    })
    n_target_change_associations = len(episode_changes)
    n_checkpoint_exposures = sum(
        _CHECKPOINT_EXPOSURE_WEIGHT[c.checkpoint_classification]
        for c in all_changes if c.relevance_tier == TIER_STRICT_OVERLAP
    )
    n_candidate_blocks = len({
        (slot.station, slot.validity_start_us // DAY_US)
        for slot in slots
        if slot.status in (STATUS_INITIAL_ONLY_NO_CHANGE, STATUS_IN_EPISODE_CHANGE, STATUS_UNRESOLVED)
    })

    all_exclusions = list(calendar_exclusions)

    result = CensusResult(
        files_checked=len(EXPECTED_FILES),
        files_ok=len(verified),
        files_missing=missing,
        files_hash_mismatch=mismatches,
        sampling_name=SAMPLING_NAME,
        total_continuous_calendar_slots=len(slots),
        slots_by_status=slots_by_status,
        n_unique_sources=n_unique_sources,
        n_unique_relation_edges=n_unique_relation_edges,
        n_target_change_associations=n_target_change_associations,
        n_targets_with_initial_evidence=slots_by_status[STATUS_INITIAL_ONLY_NO_CHANGE],
        n_targets_with_in_episode_change=slots_by_status[STATUS_IN_EPISODE_CHANGE],
        n_targets_with_unresolved=slots_by_status[STATUS_UNRESOLVED],
        n_checkpoint_exposures=n_checkpoint_exposures,
        n_candidate_blocks=n_candidate_blocks,
        n_targets_with_any_new_arrival=_n_slots_with("any_new_arrival_in_scoring_window"),
        n_targets_with_new_semantic_arrival=_n_slots_with("new_semantic_arrival_in_scoring_window"),
        n_targets_with_change_like_arrival=_n_slots_with("change_like_arrival_in_scoring_window"),
        n_targets_with_unresolved_in_initial_prefix=_n_slots_with("unresolved_in_initial_prefix"),
        n_targets_with_unresolved_in_scoring_window=_n_slots_with("unresolved_in_scoring_window"),
        n_initial_only_status_with_any_new_arrival=n_initial_only_status_with_any_new_arrival,
        changes_by_type=dict(changes_by_type),
        total_process_groups=len(process_groups),
        process_groups_by_station=dict(groups_by_station),
        total_packages_compiled=len(all_packages),
        skipped_frames=total_skipped,
        exclusions=all_exclusions,
    )

    # Write detailed output if requested
    if artifacts_dir:
        print(f"\nWriting detailed output to {artifacts_dir}...")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Write the input readset (A2-1): one record per verified source
        # file, in the stable order files were verified in (EXPECTED_FILES
        # order), plus a digest over that exact sequence so the read can be
        # independently reproduced and checked, not just trusted.
        readset_path = artifacts_dir / "input_readset.jsonl"
        with open(readset_path, "w") as f:
            for record in readset_records:
                f.write(json.dumps(record) + "\n")

        fingerprint_path = artifacts_dir / "input_fingerprint.json"
        fingerprint_hasher = hashlib.sha256()
        for record in readset_records:
            fingerprint_hasher.update(
                json.dumps(record, sort_keys=True).encode("utf-8") + b"\n"
            )
        with open(fingerprint_path, "w") as f:
            json.dump({
                "n_files": len(readset_records),
                "readset_digest_sha256": fingerprint_hasher.hexdigest(),
                "digest_method": "sha256 over each readset record json.dumps(sort_keys=True), "
                                 "newline-joined, in EXPECTED_FILES (station, year_month) order",
            }, f, indent=2)

        # Write changes JSONL (every relevant EvidenceChange, all tiers)
        changes_path = artifacts_dir / "all_changes.jsonl"
        with open(changes_path, "w") as f:
            for change in all_changes:
                record = {
                    "target_station": change.target_station,
                    "target_validity_start_us": change.target_validity_start_us,
                    "target_validity_end_us": change.target_validity_end_us,
                    "change_type": change.change_type,
                    "predecessor_source_ids": change.predecessor_source_ids,
                    "candidate_predecessors": change.candidate_predecessors,
                    "current_source_id": change.current_source_id,
                    "raw_text_sha256": change.raw_text_sha256,
                    "native_semantics_sha256": change.native_semantics_sha256,
                    "issued_at_us": change.issued_at_us,
                    "available_at_us": change.available_at_us,
                    "availability_basis": change.availability_basis,
                    "checkpoint_classification": change.checkpoint_classification,
                    "relevance_tier": change.relevance_tier,
                    "relation_status": change.relation_status,
                    "relation_reason": change.relation_reason,
                    "target_content_change": change.target_content_change,
                    "dispute_status": change.dispute_status,
                    "process_group_id": change.process_group_id,
                }
                f.write(json.dumps(record) + "\n")

        # Write process groups summary
        groups_path = artifacts_dir / "process_groups.json"
        with open(groups_path, "w") as f:
            groups_summary = {
                gid: [c.current_source_id for c in changes]
                for gid, changes in process_groups.items()
            }
            json.dump(groups_summary, f, indent=2)

        # Write slot summary (every slot, per plan "输出所有 slot")
        slots_path = artifacts_dir / "slot_summary.jsonl"
        with open(slots_path, "w") as f:
            for slot in slots:
                record = {
                    "station": slot.station,
                    "validity_start_us": slot.validity_start_us,
                    "validity_end_us": slot.validity_end_us,
                    "checkpoint_t60_us": slot.checkpoint_t60_us,
                    "checkpoint_t40_us": slot.checkpoint_t40_us,
                    "checkpoint_t20_us": slot.checkpoint_t20_us,
                    "status": slot.status,
                    "flags": slot.flags,
                    "num_changes": len(slot.changes),
                    "change_types": [c.change_type for c in slot.changes],
                    "signals": slot.signals,
                }
                f.write(json.dumps(record) + "\n")

        # Write exclusion ledger
        exclusions_path = artifacts_dir / "exclusions.jsonl"
        with open(exclusions_path, "w") as f:
            for excl in all_exclusions:
                record = {
                    "reason": excl.reason,
                    "station": excl.station,
                    "description": excl.description,
                    "detail": excl.detail,
                }
                f.write(json.dumps(record) + "\n")

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bulk-dir",
        type=Path,
        default=Path(
            "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/"
            "20260920T134949Z_1bbe63aedc00_dl3rbulk"
        ),
        help="Path to bulk DL-3R directory",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/config/"
            "stations_calendar_v16.json"
        ),
        help="Path to stations calendar config",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Optional path for detailed JSONL output",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for census summary JSON",
    )
    args = parser.parse_args()

    # Run census. (R3) A station-wide ledger compile failure is a hard gate
    # failure (exit 2), never a silently-empty "no evidence" census and
    # never conflated with exit 1 (completed with UNRESOLVED slots).
    try:
        result = run_census(args.bulk_dir, args.config, args.artifacts_dir)
    except LedgerCompilationError as exc:
        print(f"\nHARD FAILURE: {exc}", file=sys.stderr)
        return 2

    # Print summary
    print("\n" + "=" * 70)
    print("TRANSITION CENSUS V17 SUMMARY (A2-3, checkpoint-aware)")
    print("=" * 70)
    print(f"\nSampling: {result.sampling_name}")
    print(f"Process Grouping Rule Version: {PROCESS_GROUPING_VERSION}")
    print(f"\nFile Integrity:")
    print(f"  Expected files: {result.files_checked}")
    print(f"  Verified OK: {result.files_ok}")
    print(f"  Missing: {len(result.files_missing)}")
    print(f"  Hash mismatches: {len(result.files_hash_mismatch)}")

    print(f"\nContinuous Calendar:")
    print(f"  Total slots: {result.total_continuous_calendar_slots}")
    for status in SLOT_STATUSES:
        print(f"    {status}: {result.slots_by_status.get(status, 0)}")
    exclusions_by_reason: dict[str, int] = defaultdict(int)
    for excl in result.exclusions:
        exclusions_by_reason[excl.reason] += 1
    print(f"  Calendar-level exclusions: {len(result.exclusions)} {dict(exclusions_by_reason)}")

    print(f"\nA2-3 Counts:")
    print(f"  n_unique_sources: {result.n_unique_sources}")
    print(f"  n_unique_relation_edges: {result.n_unique_relation_edges}")
    print(f"  n_target_change_associations: {result.n_target_change_associations}")
    print(f"  n_targets_with_initial_evidence: {result.n_targets_with_initial_evidence}")
    print(f"  n_targets_with_in_episode_change: {result.n_targets_with_in_episode_change}")
    print(f"  n_targets_with_unresolved: {result.n_targets_with_unresolved}")
    print(f"  n_checkpoint_exposures: {result.n_checkpoint_exposures}")
    print(f"  n_candidate_blocks: {result.n_candidate_blocks}")

    print(f"\nIndependent slot signals ({CENSUS_SEMANTICS_VERSION}; not mutually exclusive):")
    print(f"  n_targets_with_any_new_arrival: {result.n_targets_with_any_new_arrival}")
    print(f"  n_targets_with_new_semantic_arrival: {result.n_targets_with_new_semantic_arrival}")
    print(f"  n_targets_with_change_like_arrival: {result.n_targets_with_change_like_arrival}")
    print(f"  n_targets_with_unresolved_in_initial_prefix: {result.n_targets_with_unresolved_in_initial_prefix}")
    print(f"  n_targets_with_unresolved_in_scoring_window: {result.n_targets_with_unresolved_in_scoring_window}")
    print(f"  n_initial_only_status_with_any_new_arrival: {result.n_initial_only_status_with_any_new_arrival}")
    print("  target_content_change: UNASSESSED for every slot")

    print(f"\n  Changes by type:")
    for ctype, count in sorted(result.changes_by_type.items()):
        print(f"    {ctype}: {count}")

    print(f"\nProcess Groups (independent weather processes):")
    print(f"  Total groups: {result.total_process_groups}")
    for station, count in sorted(result.process_groups_by_station.items()):
        print(f"    {station}: {count}")

    print(f"\nCompilation Statistics:")
    print(f"  Total packages compiled: {result.total_packages_compiled}")
    print(f"  Skipped frames: {result.skipped_frames}")

    # Write summary JSON if requested
    if args.out:
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "census_semantics_version": CENSUS_SEMANTICS_VERSION,
            "review_status": (
                "AI-reviewed only (R1-R4 corrections); NOT independently "
                "human-reviewed. Does not establish that G1 passes."
            ),
            "sampling_name": result.sampling_name,
            "process_grouping_version": PROCESS_GROUPING_VERSION,
            "process_grouping_rule": "calendar_day",
            "file_integrity": {
                "expected": result.files_checked,
                "verified_ok": result.files_ok,
                "missing": result.files_missing,
                "hash_mismatches": result.files_hash_mismatch,
            },
            "continuous_calendar": {
                "total_slots": result.total_continuous_calendar_slots,
                "slots_by_status": result.slots_by_status,
            },
            "counts": {
                "n_unique_sources": result.n_unique_sources,
                "n_unique_relation_edges": result.n_unique_relation_edges,
                "n_target_change_associations": result.n_target_change_associations,
                "n_targets_with_initial_evidence": result.n_targets_with_initial_evidence,
                "n_targets_with_in_episode_change": result.n_targets_with_in_episode_change,
                "n_targets_with_unresolved": result.n_targets_with_unresolved,
                "n_checkpoint_exposures": result.n_checkpoint_exposures,
                "n_candidate_blocks": result.n_candidate_blocks,
            },
            "independent_slot_signal_counts": {
                "_note": (
                    "Each value = number of slots where the signal is true. "
                    "Not mutually exclusive with each other or with "
                    "slots_by_status. Scoring window = first visible after "
                    "T-60 and at/before T-20, strict-overlap only. "
                    "new_semantic = whole-report semantics hash, NOT target "
                    "content; target_content_change is UNASSESSED."
                ),
                "n_targets_with_any_new_arrival": result.n_targets_with_any_new_arrival,
                "n_targets_with_new_semantic_arrival": result.n_targets_with_new_semantic_arrival,
                "n_targets_with_change_like_arrival": result.n_targets_with_change_like_arrival,
                "n_targets_with_unresolved_in_initial_prefix": result.n_targets_with_unresolved_in_initial_prefix,
                "n_targets_with_unresolved_in_scoring_window": result.n_targets_with_unresolved_in_scoring_window,
                "n_initial_only_status_with_any_new_arrival": result.n_initial_only_status_with_any_new_arrival,
                "target_content_change": "UNASSESSED",
            },
            "changes_by_type": result.changes_by_type,
            "process_groups": {
                "total": result.total_process_groups,
                "by_station": result.process_groups_by_station,
            },
            "compilation": {
                "total_packages": result.total_packages_compiled,
                "skipped_frames": result.skipped_frames,
            },
            "exclusions_count": len(result.exclusions),
            "exclusions_by_reason": dict(exclusions_by_reason),
        }
        with open(args.out, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSummary written to: {args.out}")

    # Determine exit code
    if result.files_missing or result.files_hash_mismatch:
        return 2  # Hard gate failure
    elif result.n_targets_with_unresolved > 0:
        return 1  # Issues found
    else:
        return 0  # Success


if __name__ == "__main__":
    sys.exit(main())
