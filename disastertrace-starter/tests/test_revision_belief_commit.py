"""Tests for the belief commit adapter (P0-03).

Acceptance criteria from plan v14 section 7.3:
- Implements `disastertrace.belief_commit.v14-draft` schema
- operation: UPDATE | HOLD | FOLLOW_BASELINE semantics
  - UPDATE: model writes new fact_updates/forecast_updates
  - HOLD: empty update, carries effective state forward from parent (no new facts/forecasts)
  - FOLLOW_BASELINE: defers to baseline forecast source (adoption.validate/decide precedent)
- Verbatim preservation: raw submitted commit stored as-submitted (even if invalid)
- parent_commit_id hash chain: each commit's ID derived via canonical_hash chaining
- Invalid commit handling: retain error, fall back to pre-registered fallback (not crash)
- Two-layer recording: model's raw submission vs system's effective state separately stored

Reuses:
- canonical_hash from monitoring_v1/targets.py (hash chain)
- visible_at from revision_v1/ledger.py (evidence visibility)
- ContractRegistry from revision_v1/contracts.py (target validation)
- adoption.validate/decide from monitoring_fixed_v1/adoption.py (FOLLOW_BASELINE)
"""

import pytest

from disastertrace.monitoring_v1.targets import canonical_hash, utc_us
from disastertrace.monitoring_fixed_v1.contracts import Target


# ---------------------------------------------------------------------------
# Helpers
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


def make_valid_commit(
    *,
    episode_id="ep-001",
    target_id="target-001",
    parent_commit_id=None,
    as_of="2026-09-20T12:00:00Z",
    operation="UPDATE",
    evidence_ids=None,
    fact_updates=None,
    forecast_updates=None,
    next_action=None,
):
    """Create a valid commit payload for testing."""
    return {
        "schema_version": "disastertrace.belief_commit.v14-draft",
        "episode_id": episode_id,
        "target_id": target_id,
        "parent_commit_id": parent_commit_id,
        "as_of": as_of,
        "operation": operation,
        "evidence_ids": evidence_ids or [],
        "fact_updates": fact_updates or [],
        "forecast_updates": forecast_updates or [],
        "next_action": next_action or {"kind": "WAIT", "until_or_args": ""},
    }


# ---------------------------------------------------------------------------
# Test: Schema validation - exact field set
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    """Validate the disastertrace.belief_commit.v14-draft schema."""

    def test_valid_commit_passes_validation(self):
        """A properly formed commit passes validation."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit()
        result = validate_commit_schema(commit)
        assert result["valid"] is True
        assert result["error"] is None

    def test_missing_required_field_fails(self):
        """Missing a required field fails validation."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit()
        del commit["episode_id"]

        result = validate_commit_schema(commit)
        assert result["valid"] is False
        assert "episode_id" in result["error"]

    def test_invalid_operation_fails(self):
        """Invalid operation value fails validation."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit(operation="INVALID_OP")

        result = validate_commit_schema(commit)
        assert result["valid"] is False
        assert "operation" in result["error"].lower()

    def test_all_three_operations_valid(self):
        """UPDATE, HOLD, FOLLOW_BASELINE are all valid operations."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        for op in ["UPDATE", "HOLD", "FOLLOW_BASELINE"]:
            commit = make_valid_commit(operation=op)
            result = validate_commit_schema(commit)
            assert result["valid"] is True, f"Operation {op} should be valid"

    def test_schema_version_must_match(self):
        """Schema version must be exactly disastertrace.belief_commit.v14-draft."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit()
        commit["schema_version"] = "wrong.version"

        result = validate_commit_schema(commit)
        assert result["valid"] is False
        assert "schema_version" in result["error"]

    def test_fact_update_structure(self):
        """fact_updates items must have required fields."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit(
            fact_updates=[{
                "slot": "taf_current_version",
                "operation": "SET",
                "support_status": "supported",
                "value": "TAF-001",
                "source_ids": ["evidence-001"],
            }]
        )
        result = validate_commit_schema(commit)
        assert result["valid"] is True

        # Invalid fact_update missing fields
        bad_commit = make_valid_commit(fact_updates=[{"slot": "taf_current_version"}])
        result = validate_commit_schema(bad_commit)
        assert result["valid"] is False

    def test_forecast_update_structure(self):
        """forecast_updates items must have target_id and event_probability."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit(
            forecast_updates=[{
                "target_id": "target-001",
                "event_probability": 0.25,
            }]
        )
        result = validate_commit_schema(commit)
        assert result["valid"] is True

        # Invalid forecast_update missing probability
        bad_commit = make_valid_commit(forecast_updates=[{"target_id": "target-001"}])
        result = validate_commit_schema(bad_commit)
        assert result["valid"] is False

    def test_next_action_structure(self):
        """next_action must have kind and until_or_args."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        valid_kinds = ["WAIT", "READ", "SEARCH", "TOOL", "STOP_ACTIVE"]
        for kind in valid_kinds:
            commit = make_valid_commit(
                next_action={"kind": kind, "until_or_args": "some_arg"}
            )
            result = validate_commit_schema(commit)
            assert result["valid"] is True, f"next_action kind {kind} should be valid"


# ---------------------------------------------------------------------------
# Test: Operation semantics - UPDATE, HOLD, FOLLOW_BASELINE
# ---------------------------------------------------------------------------


class TestOperationSemantics:
    """Test UPDATE, HOLD, FOLLOW_BASELINE semantics."""

    def test_update_writes_new_fact_and_forecast(self):
        """UPDATE operation applies fact_updates and forecast_updates."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="target-001",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: tid == "target-001")

        commit = make_valid_commit(
            operation="UPDATE",
            fact_updates=[{
                "slot": "taf_current",
                "operation": "SET",
                "support_status": "supported",
                "value": "TAF-v1",
                "source_ids": ["ev-001"],
            }],
            forecast_updates=[{
                "target_id": "target-001",
                "event_probability": 0.30,
            }],
        )

        result = processor.process(commit)
        assert result["accepted"] is True

        # Effective state should reflect the update
        effective = store.get_effective_state("ep-001")
        assert effective["facts"]["taf_current"]["value"] == "TAF-v1"
        assert effective["forecasts"]["target-001"] == 0.30

    def test_hold_carries_forward_parent_state(self):
        """HOLD operation carries effective state from parent, no new updates."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        # First commit with UPDATE
        commit1 = make_valid_commit(
            episode_id="ep-001",
            parent_commit_id=None,
            as_of="2026-09-20T12:00:00Z",
            operation="UPDATE",
            forecast_updates=[{"target_id": "target-001", "event_probability": 0.40}],
        )
        result1 = processor.process(commit1)
        commit1_id = result1["commit_id"]

        # Second commit with HOLD
        commit2 = make_valid_commit(
            episode_id="ep-001",
            parent_commit_id=commit1_id,
            as_of="2026-09-20T13:00:00Z",
            operation="HOLD",
            fact_updates=[],
            forecast_updates=[],
        )
        result2 = processor.process(commit2)
        assert result2["accepted"] is True

        # Effective state should still have the parent's forecast
        effective = store.get_effective_state("ep-001")
        assert effective["forecasts"]["target-001"] == 0.40

    def test_hold_with_non_empty_updates_is_invalid(self):
        """HOLD with non-empty fact_updates or forecast_updates is invalid."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit(
            operation="HOLD",
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.5}],
        )

        result = validate_commit_schema(commit)
        assert result["valid"] is False
        assert "HOLD" in result["error"]

    def test_follow_baseline_defers_to_baseline(self):
        """FOLLOW_BASELINE defers to baseline forecast instead of model's candidate."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        # Provide a baseline lookup function
        baseline_lookup = lambda target_id, as_of: 0.15  # baseline says 0.15

        processor = CommitProcessor(
            store,
            target_validator=lambda tid: True,
            baseline_provider=baseline_lookup,
        )

        commit = make_valid_commit(
            operation="FOLLOW_BASELINE",
            # Model might have written forecasts, but FOLLOW_BASELINE means use baseline
            forecast_updates=[{"target_id": "target-001", "event_probability": 0.90}],
        )

        result = processor.process(commit)
        assert result["accepted"] is True

        # Effective state should have baseline's forecast, not model's
        effective = store.get_effective_state("ep-001")
        assert effective["forecasts"]["target-001"] == 0.15

    def test_three_sequential_holds_carry_initial_state(self):
        """Three sequential HOLD operations carry initial state through."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        # Initial UPDATE
        commit0 = make_valid_commit(
            episode_id="ep-001",
            parent_commit_id=None,
            as_of="2026-09-20T10:00:00Z",
            operation="UPDATE",
            forecast_updates=[{"target_id": "target-001", "event_probability": 0.50}],
        )
        r0 = processor.process(commit0)
        parent_id = r0["commit_id"]

        # Three HOLD operations
        for i in range(3):
            commit = make_valid_commit(
                episode_id="ep-001",
                parent_commit_id=parent_id,
                as_of=f"2026-09-20T1{i+1}:00:00Z",
                operation="HOLD",
            )
            r = processor.process(commit)
            assert r["accepted"] is True
            parent_id = r["commit_id"]

        # State should still be 0.50 after 3 HOLDs
        effective = store.get_effective_state("ep-001")
        assert effective["forecasts"]["target-001"] == 0.50


# ---------------------------------------------------------------------------
# Test: Verbatim preservation - raw submitted stored as-is
# ---------------------------------------------------------------------------


class TestVerbatimPreservation:
    """Raw commit payload stored as-submitted, even if invalid."""

    def test_valid_commit_raw_stored_verbatim(self):
        """Valid commit's raw payload is stored exactly as submitted."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        commit = make_valid_commit(
            episode_id="ep-raw",
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.42}],
        )

        result = processor.process(commit)
        commit_id = result["commit_id"]

        # Retrieve raw record
        raw = store.get_raw_commit(commit_id)
        assert raw["payload"] == commit
        assert raw["payload"]["forecast_updates"][0]["event_probability"] == 0.42

    def test_invalid_commit_raw_stored_verbatim(self):
        """Invalid commit's raw payload is still stored exactly as submitted."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        # Create an invalid commit (bad operation)
        invalid_commit = {
            "schema_version": "disastertrace.belief_commit.v14-draft",
            "episode_id": "ep-invalid",
            "target_id": "target-001",
            "parent_commit_id": None,
            "as_of": "2026-09-20T12:00:00Z",
            "operation": "BOGUS_OPERATION",  # Invalid
            "evidence_ids": [],
            "fact_updates": [],
            "forecast_updates": [],
            "next_action": {"kind": "WAIT", "until_or_args": ""},
        }

        result = processor.process(invalid_commit)

        # Should be rejected but stored
        assert result["accepted"] is False
        assert result["commit_id"] is not None

        raw = store.get_raw_commit(result["commit_id"])
        assert raw["payload"] == invalid_commit
        assert raw["payload"]["operation"] == "BOGUS_OPERATION"

    def test_three_commits_all_preserved_verbatim(self):
        """Three commits (valid and invalid) all preserved verbatim."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        commits = [
            make_valid_commit(episode_id="ep-1", operation="UPDATE"),
            make_valid_commit(episode_id="ep-2", operation="HOLD"),
            {**make_valid_commit(episode_id="ep-3"), "operation": "INVALID"},
        ]

        for commit in commits:
            result = processor.process(commit)
            raw = store.get_raw_commit(result["commit_id"])
            assert raw["payload"] == commit


# ---------------------------------------------------------------------------
# Test: Parent commit ID hash chain
# ---------------------------------------------------------------------------


class TestHashChain:
    """parent_commit_id hash chain integrity via canonical_hash."""

    def test_first_commit_has_null_parent(self):
        """First commit in episode has parent_commit_id = null."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        commit = make_valid_commit(parent_commit_id=None)
        result = processor.process(commit)

        assert result["accepted"] is True
        raw = store.get_raw_commit(result["commit_id"])
        assert raw["payload"]["parent_commit_id"] is None

    def test_commit_id_derived_from_canonical_hash(self):
        """Commit ID is derived via canonical_hash of content + parent."""
        from disastertrace.revision_v1.belief_commit import compute_commit_id

        commit = make_valid_commit(parent_commit_id=None)
        computed_id = compute_commit_id(commit)

        # Should be a hex hash
        assert len(computed_id) == 64
        assert all(c in "0123456789abcdef" for c in computed_id)

        # Same input should produce same hash
        assert compute_commit_id(commit) == computed_id

    def test_chain_integrity_verified(self):
        """Commit with declared parent_commit_id must match actual parent's hash."""
        from disastertrace.revision_v1.belief_commit import (
            CommitProcessor, CommitStore, compute_commit_id
        )

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        # First commit
        commit1 = make_valid_commit(
            episode_id="ep-chain",
            parent_commit_id=None,
            as_of="2026-09-20T10:00:00Z",
        )
        r1 = processor.process(commit1)
        commit1_id = r1["commit_id"]

        # Second commit with correct parent
        commit2 = make_valid_commit(
            episode_id="ep-chain",
            parent_commit_id=commit1_id,
            as_of="2026-09-20T11:00:00Z",
        )
        r2 = processor.process(commit2)
        assert r2["accepted"] is True

    def test_chain_mismatch_detected(self):
        """Commit with wrong parent_commit_id is detected and handled."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        # First commit
        commit1 = make_valid_commit(
            episode_id="ep-bad",
            parent_commit_id=None,
            as_of="2026-09-20T10:00:00Z",
        )
        r1 = processor.process(commit1)

        # Second commit with WRONG parent hash
        commit2 = make_valid_commit(
            episode_id="ep-bad",
            parent_commit_id="0000000000000000000000000000000000000000000000000000000000000000",
            as_of="2026-09-20T11:00:00Z",
        )
        r2 = processor.process(commit2)

        # Should be rejected (chain mismatch) but still stored
        assert r2["accepted"] is False
        assert "parent" in r2["error"].lower() or "chain" in r2["error"].lower()

    def test_three_commit_chain(self):
        """Three commits form a valid chain."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        parent_id = None
        for i in range(3):
            commit = make_valid_commit(
                episode_id="ep-chain3",
                parent_commit_id=parent_id,
                as_of=f"2026-09-20T{10+i}:00:00Z",
                operation="UPDATE",
                forecast_updates=[{"target_id": "t-001", "event_probability": 0.1 * (i + 1)}],
            )
            r = processor.process(commit)
            assert r["accepted"] is True, f"Commit {i} should be accepted"
            parent_id = r["commit_id"]


# ---------------------------------------------------------------------------
# Test: Invalid commit handling - retain error, use fallback
# ---------------------------------------------------------------------------


class TestInvalidCommitHandling:
    """Invalid commits retain error and fall back to pre-registered behavior."""

    def test_invalid_commit_error_retained(self):
        """Invalid commit's error is retained in the record."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        invalid = {
            "schema_version": "disastertrace.belief_commit.v14-draft",
            "episode_id": "ep-err",
            "target_id": "target-001",
            "parent_commit_id": None,
            "as_of": "2026-09-20T12:00:00Z",
            "operation": "INVALID",
            "evidence_ids": [],
            "fact_updates": [],
            "forecast_updates": [],
            "next_action": {"kind": "WAIT", "until_or_args": ""},
        }

        result = processor.process(invalid)

        # Error should be in result
        assert result["accepted"] is False
        assert result["error"] is not None
        assert len(result["error"]) > 0

        # Error also stored with the commit
        raw = store.get_raw_commit(result["commit_id"])
        assert raw["validation_error"] is not None

    def test_invalid_commit_uses_hold_fallback(self):
        """Invalid commit defaults to HOLD-like behavior (keep prior state)."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(
            store,
            target_validator=lambda tid: True,
            fallback_operation="HOLD",  # pre-registered fallback
        )

        # First valid commit
        commit1 = make_valid_commit(
            episode_id="ep-fallback",
            parent_commit_id=None,
            as_of="2026-09-20T10:00:00Z",
            operation="UPDATE",
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.60}],
        )
        r1 = processor.process(commit1)
        parent_id = r1["commit_id"]

        # Invalid second commit
        invalid = make_valid_commit(
            episode_id="ep-fallback",
            parent_commit_id=parent_id,
            as_of="2026-09-20T11:00:00Z",
            operation="BOGUS",  # Invalid operation
        )
        r2 = processor.process(invalid)

        # Rejected but state preserved (HOLD fallback)
        assert r2["accepted"] is False

        # Effective state should still be 0.60 (held from parent)
        effective = store.get_effective_state("ep-fallback")
        assert effective["forecasts"]["t-001"] == 0.60

    def test_invalid_target_id_rejected(self):
        """Commit with unknown target_id is rejected."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        # Only accept target-001
        processor = CommitProcessor(
            store,
            target_validator=lambda tid: tid == "target-001",
        )

        commit = make_valid_commit(target_id="unknown-target")
        result = processor.process(commit)

        assert result["accepted"] is False
        assert "target" in result["error"].lower()

    def test_three_invalid_commits_all_fallback(self):
        """Three invalid commits all use fallback behavior."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(
            store,
            target_validator=lambda tid: True,
            fallback_operation="HOLD",
        )

        # Initial state
        init = make_valid_commit(
            episode_id="ep-3inv",
            parent_commit_id=None,
            operation="UPDATE",
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.25}],
        )
        r0 = processor.process(init)
        parent_id = r0["commit_id"]

        # Three invalid commits
        for i in range(3):
            bad = {
                **make_valid_commit(
                    episode_id="ep-3inv",
                    parent_commit_id=parent_id,
                    as_of=f"2026-09-20T1{i}:00:00Z",
                ),
                "operation": f"BAD_{i}",
            }
            r = processor.process(bad)
            assert r["accepted"] is False
            parent_id = r["commit_id"]

        # State should still be 0.25 after all fallbacks
        effective = store.get_effective_state("ep-3inv")
        assert effective["forecasts"]["t-001"] == 0.25


# ---------------------------------------------------------------------------
# Test: Two-layer recording - raw vs effective
# ---------------------------------------------------------------------------


class TestTwoLayerRecording:
    """Separately record raw submission vs effective state."""

    def test_raw_and_effective_distinguished(self):
        """Raw commit and effective state are stored separately."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        commit = make_valid_commit(
            operation="UPDATE",
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.75}],
        )
        result = processor.process(commit)
        commit_id = result["commit_id"]

        # Raw is what was submitted
        raw = store.get_raw_commit(commit_id)
        assert raw["payload"]["operation"] == "UPDATE"

        # Effective is the resolved state
        effective = store.get_effective_state("ep-001")
        assert "forecasts" in effective
        assert effective["forecasts"]["t-001"] == 0.75

    def test_hold_raw_vs_effective_differ(self):
        """HOLD: raw shows HOLD operation, effective shows carried-forward state."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        # First commit with UPDATE
        commit1 = make_valid_commit(
            episode_id="ep-hold",
            parent_commit_id=None,
            operation="UPDATE",
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.33}],
        )
        r1 = processor.process(commit1)

        # Second commit with HOLD (empty updates)
        commit2 = make_valid_commit(
            episode_id="ep-hold",
            parent_commit_id=r1["commit_id"],
            as_of="2026-09-20T13:00:00Z",
            operation="HOLD",
        )
        r2 = processor.process(commit2)

        # Raw shows HOLD with empty updates
        raw = store.get_raw_commit(r2["commit_id"])
        assert raw["payload"]["operation"] == "HOLD"
        assert raw["payload"]["forecast_updates"] == []

        # Effective shows the carried-forward forecast
        effective = store.get_effective_state("ep-hold")
        assert effective["forecasts"]["t-001"] == 0.33

    def test_invalid_raw_vs_effective_with_fallback(self):
        """Invalid commit: raw has error, effective has fallback state."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(
            store,
            target_validator=lambda tid: True,
            fallback_operation="HOLD",
        )

        # First commit
        commit1 = make_valid_commit(
            episode_id="ep-invraw",
            parent_commit_id=None,
            operation="UPDATE",
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.80}],
        )
        r1 = processor.process(commit1)

        # Invalid second commit
        invalid = {
            **make_valid_commit(
                episode_id="ep-invraw",
                parent_commit_id=r1["commit_id"],
                as_of="2026-09-20T13:00:00Z",
            ),
            "operation": "NONEXISTENT",
        }
        r2 = processor.process(invalid)

        # Raw contains the invalid submission
        raw = store.get_raw_commit(r2["commit_id"])
        assert raw["payload"]["operation"] == "NONEXISTENT"
        assert raw["validation_error"] is not None

        # Effective is the fallback state (held from parent)
        effective = store.get_effective_state("ep-invraw")
        assert effective["forecasts"]["t-001"] == 0.80

    def test_effective_state_per_commit(self):
        """Can retrieve effective state as of any commit in the chain."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        commit_ids = []
        probabilities = [0.10, 0.20, 0.30]
        parent_id = None

        for i, prob in enumerate(probabilities):
            commit = make_valid_commit(
                episode_id="ep-multi",
                parent_commit_id=parent_id,
                as_of=f"2026-09-20T1{i}:00:00Z",
                operation="UPDATE",
                forecast_updates=[{"target_id": "t-001", "event_probability": prob}],
            )
            r = processor.process(commit)
            commit_ids.append(r["commit_id"])
            parent_id = r["commit_id"]

        # Can retrieve effective state as of each commit
        for i, cid in enumerate(commit_ids):
            effective = store.get_effective_state_at(cid)
            assert effective["forecasts"]["t-001"] == probabilities[i]


# ---------------------------------------------------------------------------
# Test: Evidence visibility check (reuses visible_at)
# ---------------------------------------------------------------------------


class TestEvidenceVisibility:
    """Commits reference evidence_ids; verify visibility at as_of time."""

    def test_evidence_ids_checked_against_ledger(self):
        """Evidence IDs in commit must be visible at the commit's as_of time."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        t0 = us("2026-09-20T12:00:00Z")

        store = CommitStore()
        # Visibility checker that makes ev-001 visible at t0, ev-002 not visible
        def evidence_checker(evidence_id, as_of):
            if evidence_id == "ev-001":
                return as_of >= t0
            return False

        processor = CommitProcessor(
            store,
            target_validator=lambda tid: True,
            evidence_visibility_checker=evidence_checker,
        )

        # Commit referencing visible evidence
        commit_ok = make_valid_commit(
            as_of="2026-09-20T12:00:00Z",
            evidence_ids=["ev-001"],
        )
        r_ok = processor.process(commit_ok)
        assert r_ok["accepted"] is True

        # Commit referencing non-visible evidence
        commit_bad = make_valid_commit(
            episode_id="ep-bad-ev",
            as_of="2026-09-20T12:00:00Z",
            evidence_ids=["ev-002"],  # Not visible
        )
        r_bad = processor.process(commit_bad)
        assert r_bad["accepted"] is False
        assert "evidence" in r_bad["error"].lower()


# ---------------------------------------------------------------------------
# Test: Integration with ContractRegistry (target validation)
# ---------------------------------------------------------------------------


class TestContractRegistryIntegration:
    """Integration with ContractRegistry for target_id validation."""

    def test_uses_contract_registry_for_validation(self):
        """Target validation can use ContractRegistry.get()."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore
        from disastertrace.revision_v1.contracts import ContractRegistry

        t0 = us("2026-09-20T00:00:00Z")
        hour = 3_600_000_000

        target = make_target(
            target_id="registered-target",
            physical_start=t0,
            physical_end=t0 + 6 * hour,
        )

        registry = ContractRegistry()
        registry.register(target)

        store = CommitStore()
        processor = CommitProcessor(
            store,
            target_validator=lambda tid: registry.get(tid) is not None,
        )

        # Commit with registered target
        commit_ok = make_valid_commit(target_id="registered-target")
        r_ok = processor.process(commit_ok)
        assert r_ok["accepted"] is True

        # Commit with unregistered target
        commit_bad = make_valid_commit(
            episode_id="ep-unreg",
            target_id="unregistered-target",
        )
        r_bad = processor.process(commit_bad)
        assert r_bad["accepted"] is False


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_evidence_ids_allowed(self):
        """Commit with empty evidence_ids is valid."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        commit = make_valid_commit(evidence_ids=[])
        result = validate_commit_schema(commit)
        assert result["valid"] is True

    def test_multiple_forecast_updates(self):
        """Commit can have multiple forecast_updates for different targets."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        commit = make_valid_commit(
            forecast_updates=[
                {"target_id": "t-001", "event_probability": 0.10},
                {"target_id": "t-002", "event_probability": 0.20},
                {"target_id": "t-003", "event_probability": 0.30},
            ],
        )
        result = processor.process(commit)
        assert result["accepted"] is True

        effective = store.get_effective_state("ep-001")
        assert effective["forecasts"]["t-001"] == 0.10
        assert effective["forecasts"]["t-002"] == 0.20
        assert effective["forecasts"]["t-003"] == 0.30

    def test_multiple_fact_updates(self):
        """Commit can have multiple fact_updates for different slots."""
        from disastertrace.revision_v1.belief_commit import CommitProcessor, CommitStore

        store = CommitStore()
        processor = CommitProcessor(store, target_validator=lambda tid: True)

        commit = make_valid_commit(
            fact_updates=[
                {"slot": "taf_current", "operation": "SET", "support_status": "supported",
                 "value": "TAF-001", "source_ids": ["ev-1"]},
                {"slot": "metar_current", "operation": "SET", "support_status": "supported",
                 "value": "METAR-001", "source_ids": ["ev-2"]},
            ],
        )
        result = processor.process(commit)
        assert result["accepted"] is True

        effective = store.get_effective_state("ep-001")
        assert effective["facts"]["taf_current"]["value"] == "TAF-001"
        assert effective["facts"]["metar_current"]["value"] == "METAR-001"

    def test_probability_bounds_validation(self):
        """event_probability must be in [0, 1]."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        # Valid probability
        ok = make_valid_commit(
            forecast_updates=[{"target_id": "t-001", "event_probability": 0.5}]
        )
        assert validate_commit_schema(ok)["valid"] is True

        # Invalid: negative
        bad_neg = make_valid_commit(
            forecast_updates=[{"target_id": "t-001", "event_probability": -0.1}]
        )
        assert validate_commit_schema(bad_neg)["valid"] is False

        # Invalid: > 1
        bad_high = make_valid_commit(
            forecast_updates=[{"target_id": "t-001", "event_probability": 1.5}]
        )
        assert validate_commit_schema(bad_high)["valid"] is False

    def test_as_of_iso_format_validation(self):
        """as_of must be valid ISO timestamp."""
        from disastertrace.revision_v1.belief_commit import validate_commit_schema

        # Valid ISO
        ok = make_valid_commit(as_of="2026-09-20T12:00:00Z")
        assert validate_commit_schema(ok)["valid"] is True

        # Invalid format
        bad = make_valid_commit(as_of="not-a-timestamp")
        assert validate_commit_schema(bad)["valid"] is False
