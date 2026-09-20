"""Tests for target/episode contracts (P0-02).

Acceptance criteria from plan v14:
- Fixed target_id/window/threshold/O-P-R references (immutable contract identity).
- Moving window/threshold on the same target_id -> REJECTED (must raise error).
- A rolling window requires a new target_id (can't reuse existing).
- Missing report != negative outcome (interface with OutcomeRegistry fields).

Reuses:
- monitoring_fixed_v1.contracts.Target (base class for contracts)
- monitoring_fixed_v1.outcomes.OutcomeRegistry, OUTCOME_FIELDS
- monitoring_fixed_v1.outcome_policies.validate_formal_resolution, validate_resolution, POLICIES
- monitoring_v1.targets.utc_us, canonical_hash (utility functions)
"""

import pytest

from disastertrace.monitoring_v1.targets import canonical_hash, utc_us
from disastertrace.monitoring_fixed_v1.contracts import Target, Forecast, fingerprint
from disastertrace.monitoring_fixed_v1.outcomes import OUTCOME_FIELDS


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def us(iso_str):
    """Convert ISO string to microseconds since epoch."""
    return utc_us(iso_str)


def make_target(
    *,
    target_id,
    entity="KJFK",
    variable="visibility",
    units="m",
    output_kind="event_probability",
    support_kind="interval",
    physical_start,
    physical_end,
    temporal_semantics="future_physical",
    report_policy="iem_routine_unique_hour.v1",
    event_operator="lt",
    threshold=1600.0,
    release_event_at=None,
):
    """Create a Target instance for testing."""
    return Target(
        target_id=target_id,
        entity=entity,
        variable=variable,
        units=units,
        output_kind=output_kind,
        support_kind=support_kind,
        physical_start=physical_start,
        physical_end=physical_end,
        temporal_semantics=temporal_semantics,
        report_policy=report_policy,
        event_operator=event_operator,
        threshold=threshold,
        release_event_at=release_event_at,
    )


# ---------------------------------------------------------------------------
# Test: Fixed identity - target_id/window/threshold/O-P-R immutable
# ---------------------------------------------------------------------------


class TestFixedIdentity:
    """Target contract identity must be immutable once registered."""

    def test_target_is_frozen_dataclass(self):
        """Target from monitoring_fixed_v1 is a frozen dataclass (immutable)."""
        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        # Frozen dataclass - cannot modify attributes
        with pytest.raises(AttributeError, match="cannot assign"):
            target.physical_start = t0 + hour

        with pytest.raises(AttributeError, match="cannot assign"):
            target.threshold = 2000.0

        with pytest.raises(AttributeError, match="cannot assign"):
            target.target_id = "test-002"

    def test_contract_registry_preserves_identity(self):
        """ContractRegistry preserves the original contract for a target_id."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
            threshold=1600.0,
        )

        registry = ContractRegistry()
        registry.register(target)

        # Retrieve should return identical contract
        retrieved = registry.get("test-001")
        assert retrieved is target
        assert retrieved.physical_start == t0
        assert retrieved.physical_end == t0 + 6 * hour
        assert retrieved.threshold == 1600.0

    def test_contract_hash_fixed_after_registration(self):
        """The contract_hash is deterministic and fixed for a target."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        # contract_hash is deterministic
        hash1 = target.contract_hash
        hash2 = registry.get("test-001").contract_hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_three_targets_independent_identities(self):
        """Three targets with different IDs maintain independent identities."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        targets = [
            make_target(
                target_id=f"test-{i:03d}",
                physical_start=t0 + i * hour,
                physical_end=t0 + (i + 6) * hour,
                threshold=1000.0 + i * 100,
            )
            for i in range(3)
        ]

        registry = ContractRegistry()
        for t in targets:
            registry.register(t)

        # Each target maintains its own identity
        for i, t in enumerate(targets):
            retrieved = registry.get(f"test-{i:03d}")
            assert retrieved is t
            assert retrieved.threshold == 1000.0 + i * 100


# ---------------------------------------------------------------------------
# Test: Moving window/threshold on same target_id is REJECTED
# ---------------------------------------------------------------------------


class TestRejectMutation:
    """Moving window or threshold on an existing target_id must be rejected."""

    def test_changing_window_rejected(self):
        """Attempting to re-register with different window raises error."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        original = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        modified = make_target(
            target_id="test-001",  # Same target_id
            physical_start=t0 + hour,  # Different window
            physical_end=t0 + 7 * hour,
        )

        registry = ContractRegistry()
        registry.register(original)

        # Re-registering with different window should be rejected
        with pytest.raises(ValueError, match="contract.*mismatch|immutable|cannot.*modify"):
            registry.register(modified)

    def test_changing_threshold_rejected(self):
        """Attempting to re-register with different threshold raises error."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        original = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
            threshold=1600.0,
        )

        modified = make_target(
            target_id="test-001",  # Same target_id
            physical_start=t0,
            physical_end=t0 + 6 * hour,
            threshold=800.0,  # Different threshold
        )

        registry = ContractRegistry()
        registry.register(original)

        with pytest.raises(ValueError, match="contract.*mismatch|immutable|cannot.*modify"):
            registry.register(modified)

    def test_changing_entity_rejected(self):
        """Attempting to re-register with different entity raises error."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        original = make_target(
            target_id="test-001",
            entity="KJFK",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        modified = make_target(
            target_id="test-001",
            entity="KLAX",  # Different entity
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(original)

        with pytest.raises(ValueError, match="contract.*mismatch|immutable|cannot.*modify"):
            registry.register(modified)

    def test_three_mutation_attempts_all_rejected(self):
        """Three different mutation attempts on the same target_id are all rejected."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        original = make_target(
            target_id="test-001",
            entity="KJFK",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
            threshold=1600.0,
        )

        registry = ContractRegistry()
        registry.register(original)

        # Attempt 1: change start
        with pytest.raises(ValueError):
            registry.register(make_target(
                target_id="test-001",
                entity="KJFK",
                physical_start=t0 + 30 * 60_000_000,  # shifted 30 min
                physical_end=t0 + 6 * hour,
                threshold=1600.0,
            ))

        # Attempt 2: change end
        with pytest.raises(ValueError):
            registry.register(make_target(
                target_id="test-001",
                entity="KJFK",
                physical_start=t0,
                physical_end=t0 + 12 * hour,  # extended
                threshold=1600.0,
            ))

        # Attempt 3: change operator
        with pytest.raises(ValueError):
            registry.register(make_target(
                target_id="test-001",
                entity="KJFK",
                physical_start=t0,
                physical_end=t0 + 6 * hour,
                threshold=1600.0,
                event_operator="gt",  # changed from lt
            ))

    def test_identical_re_registration_accepted(self):
        """Re-registering the exact same contract should be idempotent."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        # Same contract again - should not raise
        # Create identical target
        same = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )
        registry.register(same)  # Should be idempotent

        # Still returns original
        assert registry.get("test-001").contract_hash == target.contract_hash


# ---------------------------------------------------------------------------
# Test: Rolling window requires NEW target_id
# ---------------------------------------------------------------------------


class TestRollingWindowNewId:
    """A rolling window scenario requires a new target_id, not reuse."""

    def test_sequential_windows_different_ids(self):
        """Sequential time windows must use different target_ids."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        # Hour 1 window
        window1 = make_target(
            target_id="kjfk-2026092000",
            physical_start=t0,
            physical_end=t0 + hour,
        )

        # Hour 2 window
        window2 = make_target(
            target_id="kjfk-2026092001",  # Different ID for different window
            physical_start=t0 + hour,
            physical_end=t0 + 2 * hour,
        )

        registry = ContractRegistry()
        registry.register(window1)
        registry.register(window2)

        assert registry.get("kjfk-2026092000").physical_start == t0
        assert registry.get("kjfk-2026092001").physical_start == t0 + hour

    def test_rolling_window_reuse_id_rejected(self):
        """Attempting to roll a window with the same target_id is rejected."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        # Original window
        original = make_target(
            target_id="rolling-target",
            physical_start=t0,
            physical_end=t0 + hour,
        )

        # "Rolled" window - same ID, different time
        rolled = make_target(
            target_id="rolling-target",  # SAME ID
            physical_start=t0 + hour,  # Rolled forward
            physical_end=t0 + 2 * hour,
        )

        registry = ContractRegistry()
        registry.register(original)

        # Should be rejected - can't roll a window on an existing ID
        with pytest.raises(ValueError, match="contract.*mismatch|immutable|cannot.*modify"):
            registry.register(rolled)

    def test_three_rolling_windows_three_ids(self):
        """Three rolling windows must use three distinct target_ids."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        registry = ContractRegistry()

        for i in range(3):
            target = make_target(
                target_id=f"rolling-{i}",  # Unique ID per window
                physical_start=t0 + i * hour,
                physical_end=t0 + (i + 1) * hour,
            )
            registry.register(target)

        # All three should be independently registered
        for i in range(3):
            retrieved = registry.get(f"rolling-{i}")
            assert retrieved.physical_start == t0 + i * hour
            assert retrieved.physical_end == t0 + (i + 1) * hour


# ---------------------------------------------------------------------------
# Test: Missing report != negative outcome
# ---------------------------------------------------------------------------


class TestMissingReportNotNegative:
    """Missing reports must be distinguished from negative outcomes."""

    def test_outcome_fields_includes_availability_basis(self):
        """OUTCOME_FIELDS from OutcomeRegistry includes availability_basis for tracking."""
        # Verify the field exists in the canonical outcome schema
        assert "availability_basis" in OUTCOME_FIELDS

    def test_outcome_status_distinguishes_missing(self):
        """Outcome status values distinguish 'missing' from actual results."""
        # The status field has three values: mature, provisional, missing
        # 'missing' means no report was filed, NOT a negative outcome
        # This is verified by examining OutcomeRegistry's validation
        from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = OutcomeRegistry([target], mode="legacy_compatible")

        # Missing outcome with value=None (NOT a negative outcome)
        missing_record = {
            "target_contract_hash": target.contract_hash,
            "resolution_version": "v1",
            "value": None,  # No value - this is MISSING, not negative
            "status": "missing",  # Explicitly marked as missing
            "source_revision": None,
            "source_sha256": None,
            "physical_start": t0,
            "physical_end": t0 + 6 * hour,
            "units": "m",
            "quality_status": "no_report",
            "observed_at": None,
            "published_at": None,
            "fetched_at": None,
            "resolved_at": t0 + 7 * hour,
            "availability_basis": "observed_first_seen",
        }

        # Should register successfully as missing
        registry.register(missing_record)

    def test_missing_vs_negative_semantically_different(self):
        """Missing report (no report filed) vs negative outcome (event did not occur)."""
        from disastertrace.revision_v1.contracts import classify_report_status

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        # Case 1: No report filed at all
        missing_status = classify_report_status(
            target,
            report_value=None,
            report_filed=False,
        )
        assert missing_status == "missing"

        # Case 2: Report filed, event did NOT occur (negative outcome = 0)
        negative_status = classify_report_status(
            target,
            report_value=0,  # Event did not occur
            report_filed=True,
        )
        assert negative_status == "settled_negative"

        # Case 3: Report filed, event DID occur (positive outcome = 1)
        positive_status = classify_report_status(
            target,
            report_value=1,  # Event occurred
            report_filed=True,
        )
        assert positive_status == "settled_positive"

    def test_three_missing_reports_all_classified_correctly(self):
        """Three missing reports should all be classified as missing, not negative."""
        from disastertrace.revision_v1.contracts import classify_report_status

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        targets = [
            make_target(
                target_id=f"test-{i:03d}",
                physical_start=t0 + i * hour,
                physical_end=t0 + (i + 1) * hour,
            )
            for i in range(3)
        ]

        for target in targets:
            status = classify_report_status(
                target,
                report_value=None,
                report_filed=False,
            )
            assert status == "missing"
            assert status != "settled_negative"

    def test_contract_tracks_report_status(self):
        """ContractRegistry can track report status separately from outcome value."""
        from disastertrace.revision_v1.contracts import ContractRegistry, EpisodeState

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        # Create episode state to track reporting status
        episode = registry.create_episode("test-001")

        # Initially no report
        assert episode.report_status == "pending"

        # Mark as missing (no report filed before deadline)
        episode.mark_missing()
        assert episode.report_status == "missing"
        assert episode.outcome_value is None


# ---------------------------------------------------------------------------
# Test: Integration with OutcomeRegistry OUTCOME_FIELDS
# ---------------------------------------------------------------------------


class TestOutcomeRegistryIntegration:
    """Verify correct interfacing with OutcomeRegistry and its 15 fields."""

    def test_outcome_fields_count(self):
        """OUTCOME_FIELDS should have exactly 15 fields as specified."""
        fields = OUTCOME_FIELDS.split()
        assert len(fields) == 15

    def test_all_outcome_fields_present(self):
        """Verify all expected fields are in OUTCOME_FIELDS."""
        fields = set(OUTCOME_FIELDS.split())
        expected = {
            "target_contract_hash",
            "resolution_version",
            "value",
            "status",
            "source_revision",
            "source_sha256",
            "physical_start",
            "physical_end",
            "units",
            "quality_status",
            "observed_at",
            "published_at",
            "fetched_at",
            "resolved_at",
            "availability_basis",
        }
        assert fields == expected

    def test_build_outcome_record_for_missing(self):
        """Build a valid outcome record for a missing report."""
        from disastertrace.revision_v1.contracts import build_outcome_record

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        record = build_outcome_record(
            target=target,
            resolution_version="v1",
            status="missing",
            resolved_at=t0 + 7 * hour,
            availability_basis="observed_first_seen",
        )

        # Should have all 15 fields
        assert set(record.keys()) >= set(OUTCOME_FIELDS.split())
        assert record["status"] == "missing"
        assert record["value"] is None
        assert record["target_contract_hash"] == target.contract_hash

    def test_build_outcome_record_for_mature(self):
        """Build a valid outcome record for a mature (resolved) outcome."""
        from disastertrace.revision_v1.contracts import build_outcome_record

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        record = build_outcome_record(
            target=target,
            resolution_version="v1",
            status="mature",
            value=1,  # Event occurred
            source_revision="iem-2026092006",
            source_sha256="a" * 64,
            observed_at=t0 + 3 * hour,
            published_at=t0 + 4 * hour,
            fetched_at=t0 + 5 * hour,
            resolved_at=t0 + 6 * hour,
            quality_status="settled_final_archived_report",
            availability_basis="observed_first_seen",
        )

        assert record["status"] == "mature"
        assert record["value"] == 1
        assert record["source_revision"] == "iem-2026092006"

    def test_three_outcomes_different_statuses(self):
        """Build outcome records with different statuses."""
        from disastertrace.revision_v1.contracts import build_outcome_record

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        # Missing
        missing = build_outcome_record(
            target=target,
            resolution_version="v1",
            status="missing",
            resolved_at=t0 + 7 * hour,
            availability_basis="observed_first_seen",
        )
        assert missing["status"] == "missing"
        assert missing["value"] is None

        # Provisional
        provisional = build_outcome_record(
            target=target,
            resolution_version="v1",
            status="provisional",
            value=1,
            source_revision="pending-iem",
            source_sha256="b" * 64,
            resolved_at=t0 + 7 * hour,
            quality_status="provisional_early_report",
            availability_basis="observed_first_seen",
        )
        assert provisional["status"] == "provisional"
        assert provisional["value"] == 1

        # Mature
        mature = build_outcome_record(
            target=target,
            resolution_version="v1",
            status="mature",
            value=0,  # Event did NOT occur
            source_revision="iem-final",
            source_sha256="c" * 64,
            observed_at=t0 + 6 * hour,
            published_at=t0 + 6 * hour + 60_000_000,
            fetched_at=t0 + 6 * hour + 120_000_000,
            resolved_at=t0 + 7 * hour,
            quality_status="settled_final_archived_report",
            availability_basis="observed_first_seen",
        )
        assert mature["status"] == "mature"
        assert mature["value"] == 0


# ---------------------------------------------------------------------------
# Test: Episode lifecycle
# ---------------------------------------------------------------------------


class TestEpisodeLifecycle:
    """Test episode state tracking through its lifecycle."""

    def test_episode_creation(self):
        """Episode is created from a registered contract."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        episode = registry.create_episode("test-001")
        assert episode.target_id == "test-001"
        assert episode.target.contract_hash == target.contract_hash

    def test_episode_requires_registered_contract(self):
        """Cannot create episode for unregistered target_id."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        registry = ContractRegistry()

        with pytest.raises(ValueError, match="not registered|unknown"):
            registry.create_episode("nonexistent-target")

    def test_episode_lifecycle_pending_to_resolved(self):
        """Episode transitions from pending to resolved."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        episode = registry.create_episode("test-001")
        assert episode.report_status == "pending"

        # Resolve with a positive outcome
        episode.resolve(value=1)
        assert episode.report_status == "resolved"
        assert episode.outcome_value == 1


# ---------------------------------------------------------------------------
# Test: Contract export/serialization
# ---------------------------------------------------------------------------


class TestContractSerialization:
    """Test contract export and serialization."""

    def test_contract_registry_export(self):
        """ContractRegistry can export its state."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        export = registry.export()
        assert "contracts" in export
        assert "test-001" in export["contracts"]
        assert export["contracts"]["test-001"]["contract_hash"] == target.contract_hash

    def test_contract_registry_restore(self):
        """ContractRegistry can be restored from export."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="test-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        export = registry.export()

        # Restore from export
        restored = ContractRegistry.restore(export)
        assert restored.get("test-001").contract_hash == target.contract_hash


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_registry(self):
        """Empty registry has no contracts."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        registry = ContractRegistry()
        assert registry.count() == 0

        export = registry.export()
        assert export["contracts"] == {}

    def test_get_unregistered_target(self):
        """Getting unregistered target returns None or raises."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        registry = ContractRegistry()
        assert registry.get("nonexistent") is None

    def test_point_support_target(self):
        """Point support target (physical_start == physical_end) is valid."""
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")

        target = Target(
            target_id="point-001",
            entity="KJFK",
            variable="temperature",
            units="K",
            output_kind="scalar",
            support_kind="point",
            physical_start=t0,
            physical_end=t0,  # Same as start for point support
            temporal_semantics="future_physical",
            report_policy="instant.v1",
        )

        registry = ContractRegistry()
        registry.register(target)

        assert registry.get("point-001").support_kind == "point"
