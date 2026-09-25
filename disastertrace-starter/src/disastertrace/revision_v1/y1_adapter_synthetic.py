"""SYNTHETIC-ONLY Y1 outcome-settlement adapter (Track D, v20 plan).

Maps a v18 dev-episode target contract onto ``revision_v1.outcome_wiring``'s
Target/AsosProvenance/resolve_h15_outcomes structures, reusing its pure
resolution logic rather than treating it as an opaque black box or
rewriting settlement from scratch.

NO REAL-DATA ADAPTER EXISTS YET. Everything in this module operates on
synthetic (hand-constructed or randomly generated, never archive-sourced)
observations only. ``resolve_h15_outcomes`` is a pure function -- it never
reads a file or makes a network call itself -- but this module goes further
and refuses, at call time, to be pointed at anything that does not match
the exact shape synthetic_provenance() itself produces (independent review
found an earlier version of this docstring wrongly claimed an import-time
check that does not exist -- there is none; nothing runs until a function
in this module is actually called). Real Y1 settlement remains
BLOCKED_EXPLICIT_AUTHORIZATION; building this module does not change that.

Known real gap this module does not attempt to close (see ADR note in
docs/PLAN_V20_NEXT_STEPS.md Track D): ``resolve_h15_outcomes`` currently
classifies every resolvable record as ``mature`` -- there is no real
``provisional`` state. A real settlement round needs an outer state machine
or a final-archive-freeze policy layered on top of this adapter; that is
explicitly out of scope here.

Second known gap, found by independent review and not yet fixed: a record
returned by ``settle_synthetic_outcomes`` cannot currently be passed
directly to ``register_h15_outcomes`` -- that function's own schema does
not have a slot for the extra ``provenance`` key this module attaches, and
its ``availability_basis`` allowlist does not include
``"synthetic_fixture"``. Wiring settled synthetic records into the real
outcome registry therefore needs either a small adapter on the
``register_h15_outcomes`` side or an explicit allowlist addition there --
neither exists yet. Nothing in this module or its tests currently depends
on that path working.
"""

from __future__ import annotations

from typing import Any, Mapping

from disastertrace.monitoring_fixed_v1.contracts import Target
from disastertrace.monitoring_v1.providers.aviation import MetarReport
from disastertrace.revision_v1.outcome_wiring import (
    AsosProvenance,
    make_h15_visibility_target,
    resolve_h15_outcomes,
)

SYNTHETIC_SOURCE_REVISION = "SYNTHETIC"
SYNTHETIC_AVAILABILITY_BASIS = "synthetic_fixture"


class RealReceiptRejected(ValueError):
    """Raised when this synthetic-only adapter is pointed at anything that
    looks like a real, tracked ASOS receipt sha256 rather than a synthetic
    fixture. This is a hard refusal, not a warning."""


def v18_target_to_h15_target(
    *,
    episode_id: str,
    station: str,
    target_start_us: int,
    target_end_us: int,
    threshold_m: float,
) -> Target:
    """Adapt one v18 dev-episode's target window into an H15 visibility
    Target, at the episode's own exact microsecond precision.

    make_h15_visibility_target's own target_id default only reaches hour
    granularity (station_YYYYMMDD_HH_thresholdm) -- the v18 line's targets
    can be sub-hour, so this always passes an explicit target_id derived
    from the episode_id instead of relying on that default.

    Independent review found make_h15_visibility_target's own
    support_window_hours -> support_window_us conversion
    (int(support_window_hours * 3_600_000_000)) round-trips through a float
    and silently loses up to 1 microsecond for windows that aren't an exact
    multiple of an hour (confirmed: a 65-minute window loses exactly 1us).
    Latent for v18 today (every real target is exactly 1 hour), but the
    "exact microsecond precision" claim above would be false for a genuine
    sub-hour target without this correction, so the result is corrected
    back to the exact requested target_end_us and asserted, rather than
    modifying outcome_wiring.py's own arithmetic (which stays untouched --
    Track D reuses it, it is not this adapter's to change).
    """

    if target_end_us <= target_start_us:
        raise ValueError("target_end_us must be after target_start_us")
    support_window_hours = (target_end_us - target_start_us) / 3_600_000_000
    target = make_h15_visibility_target(
        station=station,
        slot_start_us=target_start_us,
        threshold_m=threshold_m,
        target_id=f"v18-y1-synthetic-{episode_id}-{int(threshold_m)}m",
        support_window_hours=support_window_hours,
    )
    if target.physical_end != target_end_us:
        from dataclasses import replace
        target = replace(target, physical_end=target_end_us)
    assert target.physical_start == target_start_us and target.physical_end == target_end_us
    return target


def synthetic_provenance(*, fixture_label: str, fetch_timestamp_us: int) -> AsosProvenance:
    """Build a provenance record that can never be confused with a real
    tracked receipt: path and sha256 are both derived from the fixture
    label itself, never a real file, and run_id is always SYNTHETIC_SOURCE_REVISION."""

    return AsosProvenance(
        path=f"SYNTHETIC_FIXTURE::{fixture_label}",
        sha256="0" * 64,  # never a real content hash; see _reject_if_real_receipt
        fetch_timestamp_us=fetch_timestamp_us,
        run_id=SYNTHETIC_SOURCE_REVISION,
    )


def synthetic_metar(*, station: str, observation_time_us: int, visibility_m: float, raw: str | None = None) -> MetarReport:
    """A hand-constructed, never-archive-sourced METAR observation."""

    from disastertrace.monitoring_v1.support import Interval

    return MetarReport(
        station=station,
        observation_time=observation_time_us,
        report_type="routine",
        visibility=Interval(float(visibility_m), float(visibility_m)),
        temperature_c=None,
        dewpoint_c=None,
        weather=(),
        quality_flags=(),
        raw=raw or f"SYNTHETIC {station} vis={visibility_m}m",
    )


_SYNTHETIC_PATH_PREFIX = "SYNTHETIC_FIXTURE::"
_SYNTHETIC_SHA256 = "0" * 64


def _reject_if_real_receipt(provenance: AsosProvenance, tracked_receipt_sha256: frozenset[str]) -> None:
    """Independent review found the original version of this guard was
    mostly cosmetic: ``tracked_receipt_sha256`` defaults to an empty set, so
    a provenance with realistic-looking real path/sha256 values and just
    ``run_id="SYNTHETIC"`` sailed straight through. Fixed to an ALLOWLIST on
    the provenance's own shape -- it must match exactly what
    synthetic_provenance() itself produces (the fixed path prefix and fixed
    all-zero sha256) -- rather than a caller-supplied denylist the caller
    could simply forget to populate. tracked_receipt_sha256 is now only a
    belt-and-suspenders extra, not the primary defense.
    """

    if not provenance.path.startswith(_SYNTHETIC_PATH_PREFIX):
        raise RealReceiptRejected(
            f"provenance.path {provenance.path!r} does not start with {_SYNTHETIC_PATH_PREFIX!r} -- "
            "this adapter only accepts provenance built by synthetic_provenance()"
        )
    if provenance.sha256 != _SYNTHETIC_SHA256:
        raise RealReceiptRejected(
            f"provenance.sha256 must be the fixed synthetic value {_SYNTHETIC_SHA256!r}, "
            f"got {provenance.sha256!r} -- a real-looking hash is refused regardless of "
            "whether it happens to be in tracked_receipt_sha256"
        )
    if provenance.sha256 in tracked_receipt_sha256:
        raise RealReceiptRejected(
            f"provenance.sha256 {provenance.sha256!r} matches a tracked receipt -- "
            "this adapter is synthetic-only and refuses to settle against real data"
        )
    if provenance.run_id != SYNTHETIC_SOURCE_REVISION:
        raise RealReceiptRejected(
            f"provenance.run_id must be {SYNTHETIC_SOURCE_REVISION!r}, got {provenance.run_id!r}"
        )


def settle_synthetic_outcomes(
    *,
    targets: list[Target],
    observations: list[MetarReport],
    provenance: AsosProvenance,
    resolution_version: str,
    resolved_at: int | None = None,
    tracked_receipt_sha256: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Resolve outcomes for synthetic targets/observations only.

    tracked_receipt_sha256 lets a caller (e.g. a future test) pass in the
    real archive's known receipt hashes as a belt-and-suspenders check,
    without this module importing anything that could read them itself.

    Rejects a fixture that would resolve a target before its own observation
    window has even closed (independent review found the original test
    fixtures did exactly this -- resolved_at/fetched_at earlier than
    observed_at and earlier than physical_end -- which is harmless for a
    throwaway synthetic test but would be a real correctness bug if this
    adapter's shape is ever used as the template for real Y1 settlement).
    """

    _reject_if_real_receipt(provenance, tracked_receipt_sha256)
    effective_resolved_at = resolved_at if resolved_at is not None else provenance.fetch_timestamp_us
    too_early = [t.target_id for t in targets if effective_resolved_at < t.physical_end]
    if too_early:
        raise ValueError(
            f"resolved_at/fetch_timestamp_us ({effective_resolved_at}) is before "
            f"physical_end for target(s) {too_early} -- an outcome cannot be settled "
            "before its own observation window has closed"
        )
    records = resolve_h15_outcomes(
        observations,
        targets,
        provenance=provenance,
        resolution_version=resolution_version,
        resolved_at=resolved_at,
    )
    for record in records:
        record["availability_basis"] = SYNTHETIC_AVAILABILITY_BASIS
        record["provenance"] = {"source_revision": provenance.source_revision}
    return records
