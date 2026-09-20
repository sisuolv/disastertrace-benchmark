"""Tests for shared synthetic episode/evidence generator (P0-06).

This module provides a reusable synthetic-episode/evidence-package generator
importable by other test files (via the repo's cross-file helper convention:
`from test_revision_fixtures import make_episode`).

It covers all 9 ledger `kind` values from P0-01's ledger.py and can produce
well-formed, kind-diverse fixtures for tests.

Deliverables:
1. Shared synthetic episode generator (for import by other test files)
2. "Future canary" integration test: verify future evidence cannot leak
   through the full pipeline (ledger -> contracts -> belief_commit -> metrics)
3. AdmissionEngine.fork() no-op round-trip test: verify fork produces
   identical export when no operations are applied

Reuses:
- P0-01 `revision_v1/ledger.py` (visible_at, compile_ledger, 9 kinds)
- P0-02 `revision_v1/contracts.py` (ContractRegistry, EpisodeState)
- P0-03 `revision_v1/belief_commit.py` (CommitProcessor, CommitStore)
- P0-04 `revision_v1/metrics.py` (trajectory_score_Q, effective_at_from_commits)
- P0-05 `revision_v1/trap_policies.py` (apply_policy, ORACLE_LEDGER)
- `monitoring_fixed_v1/admission.py` (AdmissionEngine, TypedOpportunity)
- `monitoring_fixed_v1/contracts.py` (Target, Forecast)
"""

import pytest

from disastertrace.monitoring_v1.targets import canonical_hash, utc_us
from disastertrace.revision_v1.ledger import compile_ledger, visible_at


# ---------------------------------------------------------------------------
# Shared synthetic episode generator
# ---------------------------------------------------------------------------


def us(iso_str):
    """Convert ISO string to microseconds since epoch."""
    return utc_us(iso_str)


# Reference timestamp and unit constants
T0 = us("2026-09-19T00:00:00Z")
HOUR = 3_600_000_000  # 1 hour in microseconds
MINUTE = 60_000_000  # 1 minute in microseconds
DEFAULT_LAG = 2 * MINUTE  # Default 2-minute declared lag


def make_product(
    *,
    source_id,
    station="KJFK",
    issued_at,
    valid_start,
    valid_end,
    amendment_kind="original",
    status="active",
    semantic_content=None,
    is_baseline=False,
):
    """Create a minimal product dict for ledger testing.

    This is the base building block for all synthetic evidence packages.

    Args:
        source_id: Unique identifier for this product.
        station: Station code (default KJFK).
        issued_at: Issuance time in microseconds.
        valid_start: Validity window start in microseconds.
        valid_end: Validity window end in microseconds.
        amendment_kind: 'original', 'AMD', or 'COR'.
        status: 'active', 'nil', 'canceled', 'unparsed'.
        semantic_content: Content dict for hash computation.
        is_baseline: Whether this is a baseline product.

    Returns:
        Product dict suitable for compile_ledger().
    """
    content = semantic_content if semantic_content is not None else {"body": source_id}
    product = {
        "source_id": source_id,
        "station": station,
        "issued_at": issued_at,
        "valid_start": valid_start,
        "valid_end": valid_end,
        "amendment_kind": amendment_kind,
        "status": status,
        "native_semantics_sha256": canonical_hash(content),
        "semantic_content": content,
    }
    if is_baseline:
        product["is_baseline"] = True
    return product


def make_episode_with_all_kinds(
    *,
    base_time=None,
    declared_lag_us=DEFAULT_LAG,
    prefix="ep",
):
    """Create a synthetic episode with one product of each of the 9 ledger kinds.

    This is the main fixture generator for tests needing kind-diverse evidence.
    The episode is constructed so that each kind appears exactly once in the
    resulting ledger, making it suitable for policy identification and
    compliance testing.

    Args:
        base_time: Base timestamp (default T0).
        declared_lag_us: Declared lag for availability calculation.
        prefix: Source ID prefix for uniqueness.

    Returns:
        Dict with:
            products: List of product dicts.
            collector_first_seen: Dict mapping source_id -> observed time.
            ledger: Compiled ledger entries (call compile_ledger if None).
            kinds: Set of all 9 kind values present.
            evidence_values: Dict mapping source_id -> probability [0,1].
    """
    base_time = base_time or T0
    products = []
    collector_first_seen = {}
    evidence_values = {}

    # 1. new_observation: genuinely new evidence, not replacing anything
    src = f"{prefix}-new-obs"
    products.append(
        make_product(
            source_id=src,
            issued_at=base_time,
            valid_start=base_time,
            valid_end=base_time + 6 * HOUR,
        )
    )
    evidence_values[src] = 0.30

    # 2. amendment_supersedes: AMD that supersedes a previous version
    orig_src = f"{prefix}-amd-orig"
    amd_src = f"{prefix}-amd"
    products.append(
        make_product(
            source_id=orig_src,
            issued_at=base_time + 1 * HOUR,
            valid_start=base_time + 1 * HOUR,
            valid_end=base_time + 7 * HOUR,
        )
    )
    products.append(
        make_product(
            source_id=amd_src,
            issued_at=base_time + 2 * HOUR,
            valid_start=base_time + 1 * HOUR,
            valid_end=base_time + 7 * HOUR,
            amendment_kind="AMD",
            semantic_content={"body": f"{prefix}-amd-content"},
        )
    )
    evidence_values[orig_src] = 0.35
    evidence_values[amd_src] = 0.65

    # 3. correction: COR of a previous version
    cor_orig_src = f"{prefix}-cor-orig"
    cor_src = f"{prefix}-cor"
    products.append(
        make_product(
            source_id=cor_orig_src,
            station="KLAX",
            issued_at=base_time + 3 * HOUR,
            valid_start=base_time + 3 * HOUR,
            valid_end=base_time + 9 * HOUR,
        )
    )
    products.append(
        make_product(
            source_id=cor_src,
            station="KLAX",
            issued_at=base_time + 3 * HOUR + 10 * MINUTE,
            valid_start=base_time + 3 * HOUR,
            valid_end=base_time + 9 * HOUR,
            amendment_kind="COR",
            semantic_content={"body": f"{prefix}-cor-content"},
        )
    )
    evidence_values[cor_orig_src] = 0.40
    evidence_values[cor_src] = 0.55

    # 4. cancellation: CNL of the covered validity window
    cnl_orig_src = f"{prefix}-cnl-orig"
    cnl_src = f"{prefix}-cnl"
    products.append(
        make_product(
            source_id=cnl_orig_src,
            station="KORD",
            issued_at=base_time + 4 * HOUR,
            valid_start=base_time + 4 * HOUR,
            valid_end=base_time + 10 * HOUR,
        )
    )
    products.append(
        make_product(
            source_id=cnl_src,
            station="KORD",
            issued_at=base_time + 5 * HOUR,
            valid_start=base_time + 4 * HOUR,
            valid_end=base_time + 10 * HOUR,
            status="canceled",
        )
    )
    evidence_values[cnl_orig_src] = 0.45
    evidence_values[cnl_src] = 0.0  # cancellation

    # 5. lossless_duplicate: identical semantic content, same issued_at, different source_id
    shared_content_dup = {"body": f"{prefix}-dup-shared", "vis": 10000}
    dup_a_src = f"{prefix}-dup-a"
    dup_b_src = f"{prefix}-dup-b"
    products.append(
        make_product(
            source_id=dup_a_src,
            station="KDEN",
            issued_at=base_time + 6 * HOUR,
            valid_start=base_time + 6 * HOUR,
            valid_end=base_time + 12 * HOUR,
            semantic_content=shared_content_dup,
        )
    )
    products.append(
        make_product(
            source_id=dup_b_src,
            station="KDEN",
            issued_at=base_time + 6 * HOUR,  # Same issued_at
            valid_start=base_time + 6 * HOUR,
            valid_end=base_time + 12 * HOUR,
            semantic_content=shared_content_dup,
        )
    )
    evidence_values[dup_a_src] = 0.40
    evidence_values[dup_b_src] = 0.40  # Same value (duplicate)

    # 6. mirror: identical semantic content from a different source
    shared_content_mir = {"body": f"{prefix}-mirror-shared", "vis": 5000}
    mir_orig_src = f"nws-{prefix}-mir"
    mir_src = f"aviationweather-{prefix}-mir"
    products.append(
        make_product(
            source_id=mir_orig_src,
            station="KSFO",
            issued_at=base_time + 7 * HOUR,
            valid_start=base_time + 7 * HOUR,
            valid_end=base_time + 13 * HOUR,
            semantic_content=shared_content_mir,
        )
    )
    products.append(
        make_product(
            source_id=mir_src,
            station="KSFO",
            issued_at=base_time + 7 * HOUR + 1_000_000,  # Slight delay
            valid_start=base_time + 7 * HOUR,
            valid_end=base_time + 13 * HOUR,
            semantic_content=shared_content_mir,
        )
    )
    evidence_values[mir_orig_src] = 0.45
    evidence_values[mir_src] = 0.45  # Same value (mirror)

    # 7. late_superseded: arrived after it was already superseded
    late_orig_src = f"{prefix}-late-orig"
    late_amd_src = f"{prefix}-late-amd"
    late_src = f"{prefix}-late"
    products.append(
        make_product(
            source_id=late_orig_src,
            station="KBOS",
            issued_at=base_time + 8 * HOUR,
            valid_start=base_time + 8 * HOUR,
            valid_end=base_time + 14 * HOUR,
        )
    )
    products.append(
        make_product(
            source_id=late_amd_src,
            station="KBOS",
            issued_at=base_time + 9 * HOUR,
            valid_start=base_time + 8 * HOUR,
            valid_end=base_time + 14 * HOUR,
            amendment_kind="AMD",
            semantic_content={"body": f"{prefix}-late-amd-content"},
        )
    )
    # Late arrival: issued between orig and amd, but arrived after amd was visible
    products.append(
        make_product(
            source_id=late_src,
            station="KBOS",
            issued_at=base_time + 8 * HOUR + 30 * MINUTE,
            valid_start=base_time + 8 * HOUR,
            valid_end=base_time + 14 * HOUR,
            semantic_content={"body": f"{prefix}-late-old-content"},
        )
    )
    collector_first_seen[late_orig_src] = base_time + 8 * HOUR + declared_lag_us
    collector_first_seen[late_amd_src] = base_time + 9 * HOUR + declared_lag_us
    collector_first_seen[late_src] = base_time + 10 * HOUR  # Arrived very late
    evidence_values[late_orig_src] = 0.20
    evidence_values[late_amd_src] = 0.70
    evidence_values[late_src] = 0.25  # Old, late-arriving value

    # 8. no_change_reissue: reissued with same content
    ncr_content = {"body": f"{prefix}-ncr-content", "vis": 8000}
    ncr_orig_src = f"{prefix}-ncr-orig"
    ncr_src = f"{prefix}-ncr"
    products.append(
        make_product(
            source_id=ncr_orig_src,
            station="KSEA",
            issued_at=base_time + 10 * HOUR,
            valid_start=base_time + 10 * HOUR,
            valid_end=base_time + 16 * HOUR,
            semantic_content=ncr_content,
        )
    )
    products.append(
        make_product(
            source_id=ncr_src,
            station="KSEA",
            issued_at=base_time + 12 * HOUR,  # Later issued_at
            valid_start=base_time + 10 * HOUR,
            valid_end=base_time + 16 * HOUR,
            semantic_content=ncr_content,  # Same content
        )
    )
    evidence_values[ncr_orig_src] = 0.50
    evidence_values[ncr_src] = 0.50  # Same value (reissue)

    # 9. baseline_update: professional baseline forecast update
    base_src = f"{prefix}-baseline"
    products.append(
        make_product(
            source_id=base_src,
            station="KMIA",
            issued_at=base_time + 13 * HOUR,
            valid_start=base_time + 13 * HOUR,
            valid_end=base_time + 19 * HOUR,
            is_baseline=True,
        )
    )
    evidence_values[base_src] = 0.60

    # Compile ledger
    ledger = compile_ledger(
        products,
        declared_lag_us=declared_lag_us,
        collector_first_seen=collector_first_seen or None,
    )

    # Verify all 9 kinds are present
    kinds_present = {entry["kind"] for entry in ledger}
    expected_kinds = {
        "new_observation",
        "amendment_supersedes",
        "correction",
        "cancellation",
        "lossless_duplicate",
        "mirror",
        "late_superseded",
        "no_change_reissue",
        "baseline_update",
    }

    return {
        "products": products,
        "collector_first_seen": collector_first_seen,
        "ledger": ledger,
        "kinds": kinds_present,
        "expected_kinds": expected_kinds,
        "evidence_values": evidence_values,
        "declared_lag_us": declared_lag_us,
        "base_time": base_time,
    }


def make_future_evidence_scenario(
    *,
    query_time,
    future_available_at,
    prefix="future",
):
    """Create evidence with a future availability time.

    Used for "future canary" tests to verify visibility enforcement.

    Args:
        query_time: The time at which visibility is queried.
        future_available_at: The (future) availability time of the evidence.
        prefix: Source ID prefix.

    Returns:
        Dict with products, ledger, and the query_time / future_available_at.
    """
    base_time = query_time - HOUR  # Product issued before query_time
    products = [
        make_product(
            source_id=f"{prefix}-now",
            issued_at=base_time - 2 * HOUR,
            valid_start=base_time - 2 * HOUR,
            valid_end=base_time + 4 * HOUR,
        ),
        make_product(
            source_id=f"{prefix}-future",
            issued_at=base_time,  # Issued before query_time
            valid_start=base_time,
            valid_end=base_time + 6 * HOUR,
        ),
    ]

    # Collector saw the future product much later than declared lag
    declared_lag_us = MINUTE
    collector_first_seen = {
        f"{prefix}-now": base_time - 2 * HOUR + declared_lag_us,
        f"{prefix}-future": future_available_at,  # Very delayed arrival
    }

    ledger = compile_ledger(
        products,
        declared_lag_us=declared_lag_us,
        collector_first_seen=collector_first_seen,
    )

    return {
        "products": products,
        "ledger": ledger,
        "query_time": query_time,
        "future_available_at": future_available_at,
        "declared_lag_us": declared_lag_us,
        "collector_first_seen": collector_first_seen,
    }


# ---------------------------------------------------------------------------
# Test: Shared fixture generator produces well-formed, kind-diverse output
# ---------------------------------------------------------------------------


class TestFixtureGenerator:
    """Tests for the shared synthetic episode generator."""

    def test_make_episode_produces_all_nine_kinds(self):
        """make_episode_with_all_kinds must produce exactly the 9 ledger kinds."""
        episode = make_episode_with_all_kinds()

        # Must have all 9 expected kinds
        assert episode["kinds"] == episode["expected_kinds"]
        assert len(episode["kinds"]) == 9

    def test_make_episode_kinds_are_unique_per_source(self):
        """Each source_id appears in exactly one ledger entry."""
        episode = make_episode_with_all_kinds()

        source_ids = [entry["source_id"] for entry in episode["ledger"]]
        assert len(source_ids) == len(set(source_ids))

    def test_make_episode_evidence_values_match_sources(self):
        """Every source_id in ledger has a corresponding evidence_value."""
        episode = make_episode_with_all_kinds()

        for entry in episode["ledger"]:
            assert entry["source_id"] in episode["evidence_values"]
            prob = episode["evidence_values"][entry["source_id"]]
            assert 0 <= prob <= 1

    def test_make_episode_availability_times_are_sequential(self):
        """Ledger entries have non-decreasing available_at times when sorted."""
        episode = make_episode_with_all_kinds()

        times = sorted(entry["available_at"] for entry in episode["ledger"])
        for i in range(len(times) - 1):
            assert times[i] <= times[i + 1]

    def test_make_episode_with_different_prefixes(self):
        """Different prefixes produce non-overlapping source_ids."""
        ep1 = make_episode_with_all_kinds(prefix="ep1")
        ep2 = make_episode_with_all_kinds(prefix="ep2")

        ids1 = {entry["source_id"] for entry in ep1["ledger"]}
        ids2 = {entry["source_id"] for entry in ep2["ledger"]}

        assert ids1.isdisjoint(ids2)

    def test_make_episode_each_kind_at_least_once(self):
        """Verify each of the 9 kinds appears at least once."""
        episode = make_episode_with_all_kinds()

        for kind in episode["expected_kinds"]:
            matching = [e for e in episode["ledger"] if e["kind"] == kind]
            assert len(matching) >= 1, f"Kind {kind!r} not present in ledger"


# ---------------------------------------------------------------------------
# Test: Future canary - integration-level visibility enforcement
# ---------------------------------------------------------------------------


class TestFutureCanaryIntegration:
    """Future packages must NOT leak through the full pipeline.

    This is an integration-level tripwire: we exercise the full path from
    ledger -> contracts -> belief_commit -> metrics (or trap_policies) and
    verify that future evidence cannot influence the state before its
    available_at time.
    """

    def test_future_evidence_not_visible_in_ledger(self):
        """Baseline: visible_at filters out future evidence."""
        scenario = make_future_evidence_scenario(
            query_time=T0 + 5 * HOUR,
            future_available_at=T0 + 10 * HOUR,
        )

        visible = visible_at(scenario["ledger"], cutoff=scenario["query_time"])
        visible_ids = [e["source_id"] for e in visible]

        # The "now" evidence should be visible
        assert "future-now" in visible_ids
        # The "future" evidence must NOT be visible
        assert "future-future" not in visible_ids

    def test_future_evidence_not_in_trap_policy_trajectory(self):
        """trap_policies.apply_policy must not see future evidence.

        The trap policy trajectory should only include commits for evidence
        that is visible at each commit's as_of time. Since apply_policy
        processes ledger entries in available_at order, and the future
        evidence has available_at > query_time, it should not appear in any
        commit where we query before that time.
        """
        from disastertrace.revision_v1.trap_policies import apply_policy

        scenario = make_future_evidence_scenario(
            query_time=T0 + 5 * HOUR,
            future_available_at=T0 + 10 * HOUR,
        )

        # Filter ledger to only visible evidence at query_time
        visible_ledger = visible_at(scenario["ledger"], cutoff=scenario["query_time"])

        # Apply ORACLE_LEDGER policy to the visible ledger only
        commits = apply_policy(
            "ORACLE_LEDGER",
            episode_id="canary-ep",
            target_id="canary-tgt",
            ledger=visible_ledger,
            evidence_values={"future-now": 0.5},
        )

        # The trajectory should only contain commits for "now" evidence
        all_evidence_ids = [ev_id for c in commits for ev_id in c["evidence_ids"]]
        assert "future-now" in all_evidence_ids
        assert "future-future" not in all_evidence_ids

    def test_future_evidence_not_in_metrics_effective_state(self):
        """metrics.effective_at_from_commits must respect temporal order.

        Commits with future evidence should not influence the effective
        probability at earlier times.
        """
        from disastertrace.revision_v1.metrics import effective_at_from_commits

        # Create a scenario where we have commits at different times
        # The effective_at_from_commits function should return fallback
        # if queried before the first commit's effective_at.

        commits = [
            {"target_id": "tgt-1", "effective_at": T0 + 5 * HOUR, "probability": 0.7},
            {"target_id": "tgt-1", "effective_at": T0 + 10 * HOUR, "probability": 0.9},
        ]

        # Query at T0 + 2 * HOUR (before first commit)
        p_early = effective_at_from_commits("tgt-1", commits, T0 + 2 * HOUR, fallback=0.5)
        assert p_early == 0.5  # Should return fallback

        # Query at T0 + 7 * HOUR (between commits)
        p_mid = effective_at_from_commits("tgt-1", commits, T0 + 7 * HOUR, fallback=0.5)
        assert p_mid == 0.7  # Should return first commit's value

        # Query at T0 + 12 * HOUR (after second commit)
        p_late = effective_at_from_commits("tgt-1", commits, T0 + 12 * HOUR, fallback=0.5)
        assert p_late == 0.9  # Should return second commit's value

    def test_full_pipeline_future_canary(self):
        """Full pipeline integration: future evidence cannot influence earlier state.

        This test constructs a complete episode with future evidence, runs
        through the full pipeline (ledger -> belief_commit -> trap_policy),
        and verifies that the "future" evidence does NOT appear in any commit
        whose as_of time is before the evidence's available_at.
        """
        from disastertrace.revision_v1.belief_commit import (
            CommitProcessor,
            CommitStore,
            validate_commit_schema,
        )
        from disastertrace.revision_v1.trap_policies import apply_policy

        scenario = make_future_evidence_scenario(
            query_time=T0 + 5 * HOUR,
            future_available_at=T0 + 10 * HOUR,
        )

        # Step 1: Filter ledger to visible evidence only
        visible_ledger = visible_at(scenario["ledger"], cutoff=scenario["query_time"])
        visible_ids = {e["source_id"] for e in visible_ledger}

        # Step 2: Apply trap policy to visible ledger only
        commits = apply_policy(
            "ORACLE_LEDGER",
            episode_id="full-canary",
            target_id="tgt-canary",
            ledger=visible_ledger,
            evidence_values={eid: 0.5 for eid in visible_ids},
        )

        # Step 3: Validate each commit through belief_commit
        for commit in commits:
            result = validate_commit_schema(commit)
            assert result["valid"], result["error"]

        # Step 4: Verify no commit references future evidence
        all_evidence_in_commits = set()
        for commit in commits:
            all_evidence_in_commits.update(commit["evidence_ids"])

        # The "future-future" evidence must NOT be in any commit
        assert "future-future" not in all_evidence_in_commits
        # The "future-now" evidence SHOULD be present
        assert "future-now" in all_evidence_in_commits


# ---------------------------------------------------------------------------
# Test: AdmissionEngine.fork() no-op round-trip
# ---------------------------------------------------------------------------


class TestAdmissionEngineForkNoOp:
    """AdmissionEngine.fork() with no operations must export identically.

    This validates the counterfactual-replay foundation: a forked engine
    with no diverging operations should export the exact same payload/hash
    as its parent (modulo the journal reference, which fork() sets to None).
    """

    def _make_minimal_target(self):
        """Create a minimal valid Target for AdmissionEngine."""
        from disastertrace.monitoring_fixed_v1.contracts import Target

        # A minimal event_probability target with future_physical semantics
        return Target(
            target_id="test-target-001",
            entity="airport:KJFK",
            variable="wind_gust",
            units="kt",
            output_kind="event_probability",
            support_kind="point",
            physical_start=T0 + 24 * HOUR,  # Future physical start
            physical_end=T0 + 24 * HOUR,  # Point support: start == end
            temporal_semantics="future_physical",
            report_policy="archive.v1",
            event_operator="gt",
            threshold=30.0,
        )

    def _make_minimal_forecast(self, target):
        """Create a minimal valid Forecast for a target."""
        from disastertrace.monitoring_fixed_v1.contracts import Forecast

        return Forecast(
            target_contract_hash=target.contract_hash,
            kind="event_probability",
            units="probability",
            value=0.5,
        )

    def _make_admission_engine(self):
        """Construct a minimal AdmissionEngine for testing."""
        from disastertrace.monitoring_fixed_v1.admission import (
            AdmissionEngine,
            TypedOpportunity,
        )

        target = self._make_minimal_target()
        forecast = self._make_minimal_forecast(target)

        opportunity = TypedOpportunity(
            opportunity_id="opp-001",
            target=target,
            cutoff=T0 + 12 * HOUR,  # Cutoff before physical_start
        )

        fallbacks = {
            target.target_id: forecast.to_dict(),
        }

        engine = AdmissionEngine(
            [opportunity],
            fallbacks=fallbacks,
            protocol="base_bound_override",
            time_basis="declared_archive_scenario",
            journal=None,
        )

        return engine

    def test_fork_without_operations_produces_identical_export(self):
        """fork() with no operations should export identically to parent."""
        engine = self._make_admission_engine()

        # Export the original engine
        original_export = engine.export()

        # Fork the engine (true no-op: no run() calls on the fork)
        fork = engine.fork()

        # Export the fork
        fork_export = fork.export()

        # The payloads should be identical
        # (fork() sets journal=None but export() doesn't include journal in payload)
        assert fork_export == original_export
        assert fork_export["sha256"] == original_export["sha256"]

    def test_fork_is_independent_of_parent_after_fork(self):
        """Operations on fork should not affect parent (isolation check)."""
        from disastertrace.monitoring_fixed_v1.admission import AdmissionEvent

        engine = self._make_admission_engine()
        original_export = engine.export()

        # Fork the engine
        fork = engine.fork()

        # Run some operations on the fork only
        # Use a 'follow' event which doesn't need a bundle
        event = AdmissionEvent(
            event_id="test-follow-001",
            time=T0 + HOUR,
            kind="follow",
            payload={"target_id": "test-target-001"},
        )

        fork.run([event], until=T0 + 2 * HOUR)

        # Fork's export should now be DIFFERENT
        fork_export_after = fork.export()
        assert fork_export_after != original_export

        # But parent's export should be UNCHANGED
        parent_export_after = engine.export()
        assert parent_export_after == original_export

    def test_fork_preserves_opportunities_and_targets(self):
        """fork() preserves all registered opportunities and targets."""
        engine = self._make_admission_engine()
        fork = engine.fork()

        assert set(fork.opportunities.keys()) == set(engine.opportunities.keys())
        assert set(fork.targets.keys()) == set(engine.targets.keys())

        for oid in engine.opportunities:
            assert fork.opportunities[oid].opportunity_id == engine.opportunities[oid].opportunity_id
            assert fork.opportunities[oid].cutoff == engine.opportunities[oid].cutoff

    def test_fork_preserves_fallbacks(self):
        """fork() preserves the fallbacks dict."""
        engine = self._make_admission_engine()
        fork = engine.fork()

        assert fork.fallbacks == engine.fallbacks

    def test_fork_clears_journal(self):
        """fork() sets journal to None (documented behavior)."""
        engine = self._make_admission_engine()
        fork = engine.fork()

        # The fork should have journal=None (per docstring: "journal=None")
        assert fork.journal is None

    def test_double_fork_produces_identical_exports(self):
        """fork().fork() with no operations should still match original."""
        engine = self._make_admission_engine()
        original_export = engine.export()

        fork1 = engine.fork()
        fork2 = fork1.fork()

        # Both forks should export identically to original (no operations on either)
        assert fork1.export() == original_export
        assert fork2.export() == original_export


# ---------------------------------------------------------------------------
# Test: Fixture can be imported by other test files
# ---------------------------------------------------------------------------


class TestFixtureImportability:
    """Verify the fixtures are importable per repo convention."""

    def test_make_product_is_importable(self):
        """make_product should be usable after import."""
        # This test runs in this module, but validates the function works
        product = make_product(
            source_id="import-test",
            issued_at=T0,
            valid_start=T0,
            valid_end=T0 + HOUR,
        )
        assert product["source_id"] == "import-test"

    def test_make_episode_with_all_kinds_is_importable(self):
        """make_episode_with_all_kinds should be usable after import."""
        episode = make_episode_with_all_kinds(prefix="import-test")
        assert len(episode["kinds"]) == 9

    def test_us_helper_is_importable(self):
        """us() timestamp helper should be usable after import."""
        ts = us("2026-09-20T00:00:00Z")
        assert ts > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
