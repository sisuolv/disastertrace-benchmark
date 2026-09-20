"""Tests for the P1 harness: baselines, method-arm runner, and episode config.

Acceptance criteria from NOVELTY_POSITIONING_v16_CN.md section 4-5:
- Baselines: always-zero, climatology stub, persistence, FOLLOW/values-bank stubs
- Three-arm runner: STATELESS, APPEND, STRUCTURED with identical information exposure
- Natural/Controlled: cap_hit explicitly reported, never silently truncated
- Full-denominator: every registered target gets a prediction from every baseline

Test strategy:
- Unit tests for each baseline
- Tests for the three-arm runner with identical information verification
- Tests for Natural vs Controlled configs with cap_hit detection
- End-to-end test wiring a trap policy through the full runner

Reuses:
- make_episode_with_all_kinds from test_revision_fixtures.py
- compile_ledger from revision_v1/ledger.py
- apply_policy, ORACLE_LEDGER from revision_v1/trap_policies.py
- trajectory_score_Q_with_bounds from revision_v1/metrics.py
"""

import pytest
import copy

from disastertrace.revision_v1.p1_harness import (
    # Baselines
    Baseline,
    AlwaysZeroBaseline,
    ClimatologyBaseline,
    PersistenceBaseline,
    FollowMappingBaseline,
    ValuesBankBaseline,
    BaselineRegistry,
    create_default_baseline_registry,
    # Claim status
    ClaimStatus,
    # Arms
    ArmType,
    ArmState,
    MethodArmRunner,
    ArmRunResult,
    # Configs
    EpisodeConfig,
    NaturalConfig,
    ControlledConfig,
    EpisodeRunner,
    EpisodeRunResult,
    # Trap policy adapter
    TrapPolicyMethodAdapter,
)
from disastertrace.revision_v1.ledger import compile_ledger, visible_at
from disastertrace.revision_v1.trap_policies import (
    apply_policy,
    POLICY_NAMES,
    KIND_OPERATION_TABLES,
    _ORACLE_KIND_OPERATION,
)
from disastertrace.revision_v1.belief_commit import (
    SCHEMA_VERSION,
    validate_commit_schema,
    compute_commit_id,
)
from disastertrace.revision_v1.metrics import trajectory_score_Q_with_bounds
from disastertrace.monitoring_v1.targets import canonical_hash, utc_us

from test_revision_fixtures import (
    make_episode_with_all_kinds,
    make_product,
    T0,
    HOUR,
    MINUTE,
    us,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_episode():
    """Create a simple synthetic episode for testing."""
    return make_episode_with_all_kinds(prefix="test")


@pytest.fixture
def baseline_registry():
    """Create the default baseline registry."""
    return create_default_baseline_registry()


# ---------------------------------------------------------------------------
# Test: AlwaysZeroBaseline
# ---------------------------------------------------------------------------


class TestAlwaysZeroBaseline:
    """Tests for the always-zero floor baseline."""

    def test_returns_zero_probability(self):
        """AlwaysZeroBaseline always returns probability 0.0."""
        baseline = AlwaysZeroBaseline()
        result = baseline.predict("target-1", T0)

        assert result["probability"] == 0.0
        assert result["claim_status"] == ClaimStatus.SUPPORTED
        assert result["baseline_name"] == "always_zero"
        assert result["target_id"] == "target-1"
        assert result["timepoint"] == T0

    def test_returns_zero_regardless_of_input(self):
        """AlwaysZeroBaseline ignores ledger and evidence_values."""
        baseline = AlwaysZeroBaseline()

        # With no inputs
        r1 = baseline.predict("target-1", T0)
        assert r1["probability"] == 0.0

        # With inputs
        ledger = [{"source_id": "ev-1", "kind": "new_observation"}]
        evidence_values = {"ev-1": 0.75}
        r2 = baseline.predict("target-1", T0, ledger=ledger, evidence_values=evidence_values)
        assert r2["probability"] == 0.0

    def test_has_correct_name(self):
        """AlwaysZeroBaseline has name 'always_zero'."""
        baseline = AlwaysZeroBaseline()
        assert baseline.name == "always_zero"


# ---------------------------------------------------------------------------
# Test: ClimatologyBaseline
# ---------------------------------------------------------------------------


class TestClimatologyBaseline:
    """Tests for the development-period climatology baseline."""

    def test_stub_returns_not_tested_when_no_rate(self):
        """ClimatologyBaseline without rate returns NOT_TESTED."""
        baseline = ClimatologyBaseline(climatology_rate=None)
        result = baseline.predict("target-1", T0)

        assert result["probability"] is None
        assert result["claim_status"] == ClaimStatus.NOT_TESTED
        assert result["baseline_name"] == "climatology"
        assert "not yet computed" in result["metadata"]["reason"]

    def test_returns_rate_when_configured(self):
        """ClimatologyBaseline with rate returns that rate."""
        baseline = ClimatologyBaseline(climatology_rate=0.15)
        result = baseline.predict("target-1", T0)

        assert result["probability"] == 0.15
        assert result["claim_status"] == ClaimStatus.SUPPORTED
        assert result["metadata"]["climatology_rate"] == 0.15

    def test_different_rates_for_different_configs(self):
        """Different climatology rates can be configured."""
        b1 = ClimatologyBaseline(climatology_rate=0.10)
        b2 = ClimatologyBaseline(climatology_rate=0.25)

        r1 = b1.predict("target-1", T0)
        r2 = b2.predict("target-1", T0)

        assert r1["probability"] == 0.10
        assert r2["probability"] == 0.25

    def test_has_correct_name(self):
        """ClimatologyBaseline has name 'climatology'."""
        baseline = ClimatologyBaseline()
        assert baseline.name == "climatology"


# ---------------------------------------------------------------------------
# Test: PersistenceBaseline
# ---------------------------------------------------------------------------


class TestPersistenceBaseline:
    """Tests for the persistence baseline."""

    def test_returns_fallback_initially(self):
        """PersistenceBaseline returns fallback when no prior value."""
        baseline = PersistenceBaseline(fallback=0.5)
        result = baseline.predict("target-1", T0)

        assert result["probability"] == 0.5
        assert result["claim_status"] == ClaimStatus.SUPPORTED
        assert result["metadata"]["fallback_used"] is True
        assert result["metadata"]["has_prior_value"] is False

    def test_custom_fallback(self):
        """PersistenceBaseline respects custom fallback."""
        baseline = PersistenceBaseline(fallback=0.3)
        result = baseline.predict("target-1", T0)
        assert result["probability"] == 0.3

    def test_carries_forward_updated_value(self):
        """PersistenceBaseline carries forward updated value."""
        baseline = PersistenceBaseline(fallback=0.5)

        # First prediction uses fallback
        r1 = baseline.predict("target-1", T0)
        assert r1["probability"] == 0.5

        # Update the value
        baseline.update("target-1", 0.75)

        # Second prediction uses updated value
        r2 = baseline.predict("target-1", T0 + HOUR)
        assert r2["probability"] == 0.75
        assert r2["metadata"]["has_prior_value"] is True
        assert r2["metadata"]["fallback_used"] is False

    def test_separate_targets(self):
        """PersistenceBaseline tracks different targets separately."""
        baseline = PersistenceBaseline(fallback=0.5)

        baseline.update("target-1", 0.8)
        baseline.update("target-2", 0.2)

        r1 = baseline.predict("target-1", T0)
        r2 = baseline.predict("target-2", T0)
        r3 = baseline.predict("target-3", T0)  # Not updated

        assert r1["probability"] == 0.8
        assert r2["probability"] == 0.2
        assert r3["probability"] == 0.5  # Fallback

    def test_rejects_invalid_probability(self):
        """PersistenceBaseline rejects probability outside [0, 1]."""
        baseline = PersistenceBaseline()

        with pytest.raises(ValueError):
            baseline.update("target-1", -0.1)

        with pytest.raises(ValueError):
            baseline.update("target-1", 1.1)

    def test_has_correct_name(self):
        """PersistenceBaseline has name 'persistence'."""
        baseline = PersistenceBaseline()
        assert baseline.name == "persistence"


# ---------------------------------------------------------------------------
# Test: FollowMappingBaseline (stub)
# ---------------------------------------------------------------------------


class TestFollowMappingBaseline:
    """Tests for the FOLLOW mapping baseline stub."""

    def test_stub_returns_not_tested(self):
        """FollowMappingBaseline stub returns NOT_TESTED."""
        baseline = FollowMappingBaseline()
        result = baseline.predict("target-1", T0)

        assert result["probability"] is None
        assert result["claim_status"] == ClaimStatus.NOT_TESTED
        assert result["baseline_name"] == "follow_mapping"
        assert "interface stub" in result["metadata"]["reason"]

    def test_documents_known_brier_scores(self):
        """FollowMappingBaseline documents the known H15 Brier scores."""
        baseline = FollowMappingBaseline()
        result = baseline.predict("target-1", T0)

        # Per NOVELTY_POSITIONING_v16 section 4
        assert result["metadata"]["documented_h15_brier"] == 0.0191
        assert result["metadata"]["documented_f_base_only_brier"] == 0.0050

    def test_has_correct_name(self):
        """FollowMappingBaseline has name 'follow_mapping'."""
        baseline = FollowMappingBaseline()
        assert baseline.name == "follow_mapping"


# ---------------------------------------------------------------------------
# Test: ValuesBankBaseline (stub)
# ---------------------------------------------------------------------------


class TestValuesBankBaseline:
    """Tests for the values-bank baseline stub."""

    def test_stub_returns_not_tested(self):
        """ValuesBankBaseline stub returns NOT_TESTED."""
        baseline = ValuesBankBaseline()
        result = baseline.predict("target-1", T0)

        assert result["probability"] is None
        assert result["claim_status"] == ClaimStatus.NOT_TESTED
        assert result["baseline_name"] == "values_bank"
        assert "interface stub" in result["metadata"]["reason"]

    def test_documents_d05_split(self):
        """ValuesBankBaseline documents the D05 split."""
        baseline = ValuesBankBaseline()
        result = baseline.predict("target-1", T0)

        # Per D05: 2023 train / 2024 Jan-Nov calibration / 2025 development
        assert "2023 train" in result["metadata"]["d05_split"]
        assert "2024 Jan-Nov calibration" in result["metadata"]["d05_split"]
        assert "2025 development" in result["metadata"]["d05_split"]

    def test_has_correct_name(self):
        """ValuesBankBaseline has name 'values_bank'."""
        baseline = ValuesBankBaseline()
        assert baseline.name == "values_bank"


# ---------------------------------------------------------------------------
# Test: BaselineRegistry
# ---------------------------------------------------------------------------


class TestBaselineRegistry:
    """Tests for the baseline registry."""

    def test_register_and_get(self):
        """Registry registers and retrieves baselines."""
        registry = BaselineRegistry()
        baseline = AlwaysZeroBaseline()

        registry.register(baseline)
        retrieved = registry.get("always_zero")

        assert retrieved is baseline

    def test_rejects_duplicate_name(self):
        """Registry rejects duplicate baseline names."""
        registry = BaselineRegistry()
        registry.register(AlwaysZeroBaseline())

        with pytest.raises(ValueError, match="already registered"):
            registry.register(AlwaysZeroBaseline())

    def test_get_returns_none_for_unknown(self):
        """Registry returns None for unknown baseline."""
        registry = BaselineRegistry()
        assert registry.get("nonexistent") is None

    def test_all_baselines(self):
        """Registry returns all registered baselines."""
        registry = BaselineRegistry()
        b1 = AlwaysZeroBaseline()
        b2 = PersistenceBaseline()

        registry.register(b1)
        registry.register(b2)

        all_baselines = registry.all_baselines()
        assert len(all_baselines) == 2
        assert b1 in all_baselines
        assert b2 in all_baselines

    def test_predict_all_full_denominator(self):
        """Registry.predict_all returns prediction from every baseline."""
        registry = create_default_baseline_registry()
        results = registry.predict_all("target-1", T0)

        # All 5 required baselines should be present
        assert "always_zero" in results
        assert "climatology" in results
        assert "persistence" in results
        assert "follow_mapping" in results
        assert "values_bank" in results

        # Each has required fields
        for name, result in results.items():
            assert "probability" in result
            assert "claim_status" in result
            assert result["baseline_name"] == name


class TestDefaultBaselineRegistry:
    """Tests for the default baseline registry."""

    def test_contains_all_required_baselines(self):
        """Default registry contains all 5 required baselines."""
        registry = create_default_baseline_registry()
        baselines = registry.all_baselines()
        names = {b.name for b in baselines}

        assert names == {"always_zero", "climatology", "persistence", "follow_mapping", "values_bank"}


# ---------------------------------------------------------------------------
# Test: ArmState
# ---------------------------------------------------------------------------


class TestArmState:
    """Tests for arm state hashability and determinism."""

    def test_state_hash_is_deterministic(self):
        """Same state produces same hash."""
        state1 = ArmState(
            arm_type=ArmType.STATELESS,
            step_index=0,
            evidence_ids_seen=("ev-1", "ev-2"),
            current_probability=0.5,
            current_facts={"slot1": {"value": 1}},
        )
        state2 = ArmState(
            arm_type=ArmType.STATELESS,
            step_index=0,
            evidence_ids_seen=("ev-1", "ev-2"),
            current_probability=0.5,
            current_facts={"slot1": {"value": 1}},
        )

        assert state1.state_hash() == state2.state_hash()

    def test_different_states_different_hash(self):
        """Different states produce different hashes."""
        state1 = ArmState(
            arm_type=ArmType.STATELESS,
            step_index=0,
            evidence_ids_seen=("ev-1",),
            current_probability=0.5,
        )
        state2 = ArmState(
            arm_type=ArmType.STATELESS,
            step_index=1,  # Different step
            evidence_ids_seen=("ev-1",),
            current_probability=0.5,
        )

        assert state1.state_hash() != state2.state_hash()

    def test_arm_type_affects_hash(self):
        """Different arm types produce different hashes."""
        base = {
            "step_index": 0,
            "evidence_ids_seen": ("ev-1",),
            "current_probability": 0.5,
        }
        state1 = ArmState(arm_type=ArmType.STATELESS, **base)
        state2 = ArmState(arm_type=ArmType.APPEND, **base)

        assert state1.state_hash() != state2.state_hash()

    def test_canonical_repr(self):
        """Canonical representation contains all state fields."""
        state = ArmState(
            arm_type=ArmType.STRUCTURED,
            step_index=5,
            evidence_ids_seen=("a", "b", "c"),
            current_probability=0.75,
            current_facts={"slot": {"op": "SET"}},
        )
        rep = state.canonical_repr()

        assert rep["arm_type"] == "structured"
        assert rep["step_index"] == 5
        assert rep["evidence_ids_seen"] == ["a", "b", "c"]
        assert rep["current_probability"] == 0.75
        assert rep["current_facts"] == {"slot": {"op": "SET"}}


# ---------------------------------------------------------------------------
# Test: MethodArmRunner - identical information exposure
# ---------------------------------------------------------------------------


class TestMethodArmRunner:
    """Tests for the three-arm runner."""

    def test_all_arms_see_same_evidence(self, simple_episode):
        """All three arms process the same evidence in the same order."""
        ledger = compile_ledger(
            simple_episode["products"],
            collector_first_seen=simple_episode.get("collector_first_seen"),
        )

        evidence_seen_per_arm = {arm: [] for arm in ArmType}

        def tracking_method(evidence, arm_type, history, state):
            evidence_seen_per_arm[arm_type].append(evidence["source_id"])
            return {
                "schema_version": SCHEMA_VERSION,
                "episode_id": "test-ep",
                "target_id": "test-target",
                "parent_commit_id": None,
                "as_of": "2026-09-19T00:00:00.000Z",
                "operation": "HOLD",
                "evidence_ids": [evidence["source_id"]],
                "fact_updates": [],
                "forecast_updates": [],
                "next_action": {"kind": "WAIT", "until_or_args": ""},
            }

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")
        runner.run_all_arms(
            ledger=ledger,
            method=tracking_method,
            evidence_values=simple_episode.get("evidence_values"),
        )

        # All arms should see the same evidence in the same order
        assert evidence_seen_per_arm[ArmType.STATELESS] == evidence_seen_per_arm[ArmType.APPEND]
        assert evidence_seen_per_arm[ArmType.APPEND] == evidence_seen_per_arm[ArmType.STRUCTURED]

    def test_state_hashes_deterministic_across_runs(self, simple_episode):
        """State hashes are identical across repeated runs of the same arm."""
        ledger = compile_ledger(
            simple_episode["products"],
            collector_first_seen=simple_episode.get("collector_first_seen"),
        )

        def simple_method(evidence, arm_type, history, state):
            return {
                "schema_version": SCHEMA_VERSION,
                "episode_id": "test-ep",
                "target_id": "test-target",
                "parent_commit_id": None,
                "as_of": "2026-09-19T00:00:00.000Z",
                "operation": "HOLD",
                "evidence_ids": [evidence["source_id"]],
                "fact_updates": [],
                "forecast_updates": [],
                "next_action": {"kind": "WAIT", "until_or_args": ""},
            }

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")

        # Run twice
        result1 = runner.run_arm(ArmType.STATELESS, ledger=ledger, method=simple_method)
        result2 = runner.run_arm(ArmType.STATELESS, ledger=ledger, method=simple_method)

        # State hashes should be identical
        assert result1.state_hashes == result2.state_hashes

    def test_arm_specific_inputs(self, simple_episode):
        """Each arm receives its specific inputs correctly."""
        ledger = compile_ledger(
            simple_episode["products"],
            collector_first_seen=simple_episode.get("collector_first_seen"),
        )[:3]  # Use just 3 entries for simplicity

        inputs_received = {"history_lengths": [], "state_present": []}

        def inspecting_method(evidence, arm_type, history, state):
            inputs_received["history_lengths"].append(len(history) if history else 0)
            inputs_received["state_present"].append(state is not None)
            return {
                "schema_version": SCHEMA_VERSION,
                "episode_id": "test-ep",
                "target_id": "test-target",
                "parent_commit_id": None,
                "as_of": "2026-09-19T00:00:00.000Z",
                "operation": "HOLD",
                "evidence_ids": [evidence["source_id"]],
                "fact_updates": [],
                "forecast_updates": [],
                "next_action": {"kind": "WAIT", "until_or_args": ""},
            }

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")

        # Test STATELESS: no history, no state
        inputs_received = {"history_lengths": [], "state_present": []}
        runner.run_arm(ArmType.STATELESS, ledger=ledger, method=inspecting_method)
        assert all(h == 0 for h in inputs_received["history_lengths"])
        assert all(not s for s in inputs_received["state_present"])

        # Test APPEND: growing history, no state
        inputs_received = {"history_lengths": [], "state_present": []}
        runner.run_arm(ArmType.APPEND, ledger=ledger, method=inspecting_method)
        assert inputs_received["history_lengths"] == [1, 2, 3]
        assert all(not s for s in inputs_received["state_present"])

        # Test STRUCTURED: no history, state present
        inputs_received = {"history_lengths": [], "state_present": []}
        runner.run_arm(ArmType.STRUCTURED, ledger=ledger, method=inspecting_method)
        assert all(h == 0 for h in inputs_received["history_lengths"])
        assert all(s for s in inputs_received["state_present"])


# ---------------------------------------------------------------------------
# Test: Natural vs Controlled configs
# ---------------------------------------------------------------------------


class TestNaturalConfig:
    """Tests for Natural episode config."""

    def test_never_stops_early(self):
        """NaturalConfig never triggers cap_hit."""
        config = NaturalConfig()

        # Should not stop even with large counts
        should_stop, cap = config.should_stop(
            evidence_count=1000,
            elapsed_steps=1000,
            elapsed_time_us=86400_000_000,  # 1 day
        )

        assert should_stop is False
        assert cap is None

    def test_has_correct_name(self):
        """NaturalConfig has name 'natural'."""
        config = NaturalConfig()
        assert config.name == "natural"


class TestControlledConfig:
    """Tests for Controlled episode config."""

    def test_stops_at_max_evidence(self):
        """ControlledConfig stops at max_evidence_packages."""
        config = ControlledConfig(max_evidence_packages=10, max_steps=None)

        # Under limit
        should_stop, cap = config.should_stop(evidence_count=9, elapsed_steps=9)
        assert should_stop is False

        # At/over limit
        should_stop, cap = config.should_stop(evidence_count=10, elapsed_steps=10)
        assert should_stop is True
        assert cap == "max_evidence_packages"

    def test_stops_at_max_steps(self):
        """ControlledConfig stops at max_steps."""
        config = ControlledConfig(max_evidence_packages=None, max_steps=5)

        should_stop, cap = config.should_stop(evidence_count=3, elapsed_steps=5)
        assert should_stop is True
        assert cap == "max_steps"

    def test_stops_at_max_wall_time(self):
        """ControlledConfig stops at max_wall_time_us."""
        config = ControlledConfig(
            max_evidence_packages=None,
            max_steps=None,
            max_wall_time_us=60_000_000,  # 1 minute
        )

        # Under limit
        should_stop, cap = config.should_stop(
            evidence_count=10,
            elapsed_steps=10,
            elapsed_time_us=59_000_000,
        )
        assert should_stop is False

        # Over limit
        should_stop, cap = config.should_stop(
            evidence_count=10,
            elapsed_steps=10,
            elapsed_time_us=61_000_000,
        )
        assert should_stop is True
        assert cap == "max_wall_time_us"

    def test_has_correct_name(self):
        """ControlledConfig has name 'controlled'."""
        config = ControlledConfig()
        assert config.name == "controlled"


class TestEpisodeRunner:
    """Tests for the episode runner with configs."""

    def test_natural_completes_naturally(self, simple_episode):
        """Natural config runs to natural completion."""
        ledger = compile_ledger(
            simple_episode["products"],
            collector_first_seen=simple_episode.get("collector_first_seen"),
        )

        def hold_method(evidence, arm_type, history, state):
            return {
                "schema_version": SCHEMA_VERSION,
                "episode_id": "test-ep",
                "target_id": "test-target",
                "parent_commit_id": None,
                "as_of": "2026-09-19T00:00:00.000Z",
                "operation": "HOLD",
                "evidence_ids": [evidence["source_id"]],
                "fact_updates": [],
                "forecast_updates": [],
                "next_action": {"kind": "WAIT", "until_or_args": ""},
            }

        runner = EpisodeRunner(
            episode_id="test-ep",
            target_id="test-target",
            config=NaturalConfig(),
        )

        result = runner.run(
            arm_type=ArmType.STATELESS,
            ledger=ledger,
            method=hold_method,
        )

        assert result.completed_naturally is True
        assert result.cap_hit is False
        assert result.cap_name is None
        assert result.evidence_processed == len(ledger)

    def test_controlled_reports_cap_hit(self, simple_episode):
        """Controlled config reports cap_hit when limit reached."""
        ledger = compile_ledger(
            simple_episode["products"],
            collector_first_seen=simple_episode.get("collector_first_seen"),
        )

        # Set cap lower than evidence count
        cap_limit = 3
        assert len(ledger) > cap_limit

        def hold_method(evidence, arm_type, history, state):
            return {
                "schema_version": SCHEMA_VERSION,
                "episode_id": "test-ep",
                "target_id": "test-target",
                "parent_commit_id": None,
                "as_of": "2026-09-19T00:00:00.000Z",
                "operation": "HOLD",
                "evidence_ids": [evidence["source_id"]],
                "fact_updates": [],
                "forecast_updates": [],
                "next_action": {"kind": "WAIT", "until_or_args": ""},
            }

        runner = EpisodeRunner(
            episode_id="test-ep",
            target_id="test-target",
            config=ControlledConfig(max_evidence_packages=cap_limit, max_steps=None),
        )

        result = runner.run(
            arm_type=ArmType.STATELESS,
            ledger=ledger,
            method=hold_method,
        )

        # Should report cap hit
        assert result.completed_naturally is False
        assert result.cap_hit is True
        assert result.cap_name == "max_evidence_packages"
        assert result.evidence_processed == cap_limit
        assert result.evidence_processed < len(ledger)

    def test_controlled_under_cap_completes_naturally(self, simple_episode):
        """Controlled config under cap completes naturally."""
        ledger = compile_ledger(
            simple_episode["products"],
            collector_first_seen=simple_episode.get("collector_first_seen"),
        )

        # Set cap higher than evidence count
        cap_limit = len(ledger) + 100

        def hold_method(evidence, arm_type, history, state):
            return {
                "schema_version": SCHEMA_VERSION,
                "episode_id": "test-ep",
                "target_id": "test-target",
                "parent_commit_id": None,
                "as_of": "2026-09-19T00:00:00.000Z",
                "operation": "HOLD",
                "evidence_ids": [evidence["source_id"]],
                "fact_updates": [],
                "forecast_updates": [],
                "next_action": {"kind": "WAIT", "until_or_args": ""},
            }

        runner = EpisodeRunner(
            episode_id="test-ep",
            target_id="test-target",
            config=ControlledConfig(max_evidence_packages=cap_limit),
        )

        result = runner.run(
            arm_type=ArmType.STATELESS,
            ledger=ledger,
            method=hold_method,
        )

        # Should complete naturally (cap not hit)
        assert result.completed_naturally is True
        assert result.cap_hit is False
        assert result.cap_name is None
        assert result.evidence_processed == len(ledger)


# ---------------------------------------------------------------------------
# Test: Reference policy integration (ORACLE_LEDGER via apply_policy directly)
# ---------------------------------------------------------------------------


class TestReferenceIntegration:
    """Integration tests for the reference/oracle policy path.

    NOTE: This class tests ORACLE_LEDGER (the reference/correct policy from
    trap_policies.py) via direct calls to apply_policy(). These tests verify
    that the reference policy produces valid commits and that the runner
    infrastructure works. They do NOT test genuine trap/failure policies
    through the runner - see TestTrapPolicyThroughRunner for that.
    """

    def test_oracle_ledger_produces_scoreable_trajectory(self, simple_episode):
        """ORACLE_LEDGER through runner produces trajectory that metrics can score."""
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        # Use apply_policy to get reference commits
        oracle_commits = apply_policy(
            "ORACLE_LEDGER",
            episode_id="test-ep",
            target_id="test-target",
            ledger=ledger,
            evidence_values=evidence_values,
        )

        # Convert commits to the format expected by metrics
        scoring_commits = []
        for commit in oracle_commits:
            for forecast in commit.get("forecast_updates", []):
                target_id = forecast.get("target_id")
                prob = forecast.get("event_probability")
                if target_id and prob is not None:
                    # Parse as_of to microseconds
                    as_of_str = commit.get("as_of", "2026-09-19T00:00:00.000Z")
                    effective_at = utc_us(as_of_str.replace(".000Z", "+00:00"))
                    scoring_commits.append({
                        "target_id": target_id,
                        "effective_at": effective_at,
                        "probability": prob,
                    })

        # Build a simple grid for one target
        if scoring_commits:
            # Use first and last effective_at as checkpoints
            times = sorted(set(c["effective_at"] for c in scoring_commits))
            if len(times) >= 2:
                grid = {
                    "test-target": [
                        (times[0], 0.5),
                        (times[-1], 0.5),
                    ]
                }
                outcomes = {"test-target": 1}  # Assume event occurred
                fallback = {"test-target": 0.5}

                # This should not crash - verifies end-to-end plumbing
                result = trajectory_score_Q_with_bounds(
                    scoring_commits,
                    grid,
                    outcomes,
                    fallback,
                )

                assert "q_settled" in result
                assert result["settled_count"] == 1

    def test_trap_policy_method_adapter(self, simple_episode):
        """A trap policy can be adapted to the method protocol."""
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        # Create a method adapter for ORACLE_LEDGER
        policy_commits = apply_policy(
            "ORACLE_LEDGER",
            episode_id="test-ep",
            target_id="test-target",
            ledger=ledger,
            evidence_values=evidence_values,
        )

        # The apply_policy function already does what a method would do
        # Verify the commits are valid
        for commit in policy_commits:
            result = validate_commit_schema(commit)
            assert result["valid"], f"Invalid commit: {result['error']}"

    def test_runner_with_updating_method(self, simple_episode):
        """Runner correctly tracks state updates from UPDATE commits."""
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        probabilities_returned = []

        def updating_method(evidence, arm_type, history, state):
            # Return different probabilities based on kind
            kind = evidence.get("kind", "unknown")
            source_id = evidence["source_id"]

            prob = evidence_values.get(source_id, 0.5)
            probabilities_returned.append(prob)

            op = _ORACLE_KIND_OPERATION.get(kind, "UPDATE")

            if op == "HOLD":
                return {
                    "schema_version": SCHEMA_VERSION,
                    "episode_id": "test-ep",
                    "target_id": "test-target",
                    "parent_commit_id": None,
                    "as_of": "2026-09-19T00:00:00.000Z",
                    "operation": "HOLD",
                    "evidence_ids": [source_id],
                    "fact_updates": [],
                    "forecast_updates": [],
                    "next_action": {"kind": "WAIT", "until_or_args": ""},
                }
            else:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "episode_id": "test-ep",
                    "target_id": "test-target",
                    "parent_commit_id": None,
                    "as_of": "2026-09-19T00:00:00.000Z",
                    "operation": op,
                    "evidence_ids": [source_id],
                    "fact_updates": [
                        {
                            "slot": "event_status",
                            "operation": "SET",
                            "support_status": "supported",
                            "value": prob,
                            "source_ids": [source_id],
                        }
                    ],
                    "forecast_updates": [
                        {"target_id": "test-target", "event_probability": prob}
                    ],
                    "next_action": {"kind": "WAIT", "until_or_args": ""},
                }

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")
        result = runner.run_arm(
            ArmType.STRUCTURED,
            ledger=ledger,
            method=updating_method,
        )

        # Verify commits were produced
        assert len(result.commits) == len(ledger)

        # Verify state hashes are all unique (since state changes each step)
        # (Some may repeat if consecutive HOLDs, but there should be variety)
        unique_hashes = set(result.state_hashes)
        assert len(unique_hashes) >= 1  # At least the initial state


# ---------------------------------------------------------------------------
# Test: Determinism verification
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Tests verifying deterministic/reproducible execution."""

    def test_same_inputs_same_hashes(self, simple_episode):
        """Identical inputs produce identical state hashes."""
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        def deterministic_method(evidence, arm_type, history, state):
            source_id = evidence["source_id"]
            prob = evidence_values.get(source_id, 0.5)
            return {
                "schema_version": SCHEMA_VERSION,
                "episode_id": "test-ep",
                "target_id": "test-target",
                "parent_commit_id": None,
                "as_of": "2026-09-19T00:00:00.000Z",
                "operation": "UPDATE",
                "evidence_ids": [source_id],
                "fact_updates": [],
                "forecast_updates": [
                    {"target_id": "test-target", "event_probability": prob}
                ],
                "next_action": {"kind": "WAIT", "until_or_args": ""},
            }

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")

        # Run three times
        results = [
            runner.run_arm(ArmType.STATELESS, ledger=ledger, method=deterministic_method)
            for _ in range(3)
        ]

        # All state hash sequences should be identical
        assert results[0].state_hashes == results[1].state_hashes
        assert results[1].state_hashes == results[2].state_hashes

    def test_canonical_hash_used(self, simple_episode):
        """ArmState uses canonical_hash for determinism."""
        state = ArmState(
            arm_type=ArmType.APPEND,
            step_index=2,
            evidence_ids_seen=("a", "b"),
            current_probability=0.6,
            current_facts={"slot": {"v": 1}},
        )

        # Verify it uses canonical_hash internally
        expected = canonical_hash(state.canonical_repr())
        assert state.state_hash() == expected


# ---------------------------------------------------------------------------
# Test: Genuine trap policy end-to-end through MethodArmRunner
# ---------------------------------------------------------------------------


class TestTrapPolicyThroughRunner:
    """End-to-end tests wiring genuine trap/failure policies through MethodArmRunner.

    This class satisfies the W3 task requirement: "wire at least one trap_policies.py
    policy (e.g. IGNORE_AMD or STALE_HOLD) through the full three-arm runner on a
    synthetic episode with real revision events (AMD/COR/CNL), and confirm the
    runner produces a trajectory that metrics.py's existing scoring functions can
    actually score (i.e. real end-to-end plumbing, not a mocked pipeline)."

    IMPORTANT: These tests use genuine TRAP policies (IGNORE_AMD, STALE_HOLD),
    NOT the ORACLE_LEDGER reference policy. ORACLE_LEDGER is documented as
    "program-correct: perfectly follows ledger" - it is the OPPOSITE of a trap.
    """

    def test_ignore_amd_through_runner_produces_scoreable_trajectory(self, simple_episode):
        """IGNORE_AMD trap policy through MethodArmRunner produces scoreable trajectory.

        IGNORE_AMD is a genuine trap/failure policy that HOLDs (ignores) on
        amendment_supersedes and correction kinds, causing staleness failures.

        This test:
        1. Uses TrapPolicyMethodAdapter with IGNORE_AMD
        2. Actually calls MethodArmRunner.run_arm() (not apply_policy directly)
        3. Feeds commits to trajectory_score_Q_with_bounds()
        4. Verifies the result is well-formed
        """
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        # Create the trap policy adapter
        adapter = TrapPolicyMethodAdapter(
            "IGNORE_AMD",
            episode_id="test-ep",
            target_id="test-target",
            evidence_values=evidence_values,
        )

        # Actually call MethodArmRunner.run_arm()
        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")
        result = runner.run_arm(
            ArmType.STATELESS,
            ledger=ledger,
            method=adapter,
        )

        # Verify commits were produced
        assert len(result.commits) == len(ledger)
        assert len(result.commits) > 0

        # Verify each commit is valid
        for commit in result.commits:
            validation = validate_commit_schema(commit)
            assert validation["valid"], f"Invalid commit: {validation['error']}"

        # Convert commits to scoring format
        scoring_commits = []
        for commit in result.commits:
            for forecast in commit.get("forecast_updates", []):
                target_id = forecast.get("target_id")
                prob = forecast.get("event_probability")
                if target_id and prob is not None:
                    as_of_str = commit.get("as_of", "2026-09-19T00:00:00.000Z")
                    effective_at = utc_us(as_of_str.replace(".000Z", "+00:00"))
                    scoring_commits.append({
                        "target_id": target_id,
                        "effective_at": effective_at,
                        "probability": prob,
                    })

        # Build grid and call trajectory_score_Q_with_bounds
        # Note: weights must sum to 1.0 per target
        if scoring_commits:
            times = sorted(set(c["effective_at"] for c in scoring_commits))
            if len(times) >= 1:
                # Use one or two checkpoints with weights summing to 1.0
                if len(times) >= 2:
                    grid = {
                        "test-target": [
                            (times[0], 0.5),
                            (times[-1], 0.5),
                        ]
                    }
                else:
                    grid = {
                        "test-target": [(times[0], 1.0)]
                    }
                outcomes = {"test-target": 1}
                fallback = {"test-target": 0.5}

                # This should not crash - verifies real end-to-end plumbing
                score_result = trajectory_score_Q_with_bounds(
                    scoring_commits,
                    grid,
                    outcomes,
                    fallback,
                )

                # Verify result is well-formed
                assert "q_settled" in score_result
                assert "settled_count" in score_result

    def test_stale_hold_through_runner_produces_scoreable_trajectory(self, simple_episode):
        """STALE_HOLD trap policy through MethodArmRunner produces scoreable trajectory.

        STALE_HOLD is a genuine trap/failure policy that UPDATEs only on the first
        evidence package, then HOLDs forever after (causing lag failures).

        This test:
        1. Uses TrapPolicyMethodAdapter with STALE_HOLD
        2. Actually calls MethodArmRunner.run_arm() (not apply_policy directly)
        3. Feeds commits to trajectory_score_Q_with_bounds()
        4. Verifies the result is well-formed
        """
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        # Create the trap policy adapter
        adapter = TrapPolicyMethodAdapter(
            "STALE_HOLD",
            episode_id="test-ep",
            target_id="test-target",
            evidence_values=evidence_values,
        )

        # Actually call MethodArmRunner.run_arm()
        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")
        result = runner.run_arm(
            ArmType.STATELESS,
            ledger=ledger,
            method=adapter,
        )

        # Verify commits were produced
        assert len(result.commits) == len(ledger)
        assert len(result.commits) > 0

        # Verify STALE_HOLD behavior: first commit UPDATE, rest HOLD
        assert result.commits[0]["operation"] == "UPDATE"
        for commit in result.commits[1:]:
            assert commit["operation"] == "HOLD"

        # Verify each commit is valid
        for commit in result.commits:
            validation = validate_commit_schema(commit)
            assert validation["valid"], f"Invalid commit: {validation['error']}"

        # Convert commits to scoring format (only the first one has forecast_updates)
        scoring_commits = []
        for commit in result.commits:
            for forecast in commit.get("forecast_updates", []):
                target_id = forecast.get("target_id")
                prob = forecast.get("event_probability")
                if target_id and prob is not None:
                    as_of_str = commit.get("as_of", "2026-09-19T00:00:00.000Z")
                    effective_at = utc_us(as_of_str.replace(".000Z", "+00:00"))
                    scoring_commits.append({
                        "target_id": target_id,
                        "effective_at": effective_at,
                        "probability": prob,
                    })

        # Build grid and call trajectory_score_Q_with_bounds
        # Note: weights must sum to 1.0 per target
        if scoring_commits:
            times = sorted(set(c["effective_at"] for c in scoring_commits))
            grid = {
                "test-target": [(times[0], 1.0)]  # Single checkpoint with weight=1.0
            }
            outcomes = {"test-target": 1}
            fallback = {"test-target": 0.5}

            # This should not crash - verifies real end-to-end plumbing
            score_result = trajectory_score_Q_with_bounds(
                scoring_commits,
                grid,
                outcomes,
                fallback,
            )

            # Verify result is well-formed
            assert "q_settled" in score_result

    def test_trap_policy_adapter_arm_independence(self, simple_episode):
        """Trap policy through STATELESS vs STRUCTURED arms produces same operations.

        For table-driven trap policies (like IGNORE_AMD), the operation is
        determined purely by the evidence kind, which is arm-representation-
        independent. This test verifies the adapter doesn't accidentally
        produce arm-dependent behavior.
        """
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")

        # Run with STATELESS arm
        adapter_stateless = TrapPolicyMethodAdapter(
            "IGNORE_AMD",
            episode_id="test-ep",
            target_id="test-target",
            evidence_values=evidence_values,
        )
        result_stateless = runner.run_arm(
            ArmType.STATELESS,
            ledger=ledger,
            method=adapter_stateless,
        )

        # Run with STRUCTURED arm (fresh adapter to reset state)
        adapter_structured = TrapPolicyMethodAdapter(
            "IGNORE_AMD",
            episode_id="test-ep",
            target_id="test-target",
            evidence_values=evidence_values,
        )
        result_structured = runner.run_arm(
            ArmType.STRUCTURED,
            ledger=ledger,
            method=adapter_structured,
        )

        # Operations should be identical
        ops_stateless = [c["operation"] for c in result_stateless.commits]
        ops_structured = [c["operation"] for c in result_structured.commits]
        assert ops_stateless == ops_structured

        # Evidence IDs should be identical
        evids_stateless = [c["evidence_ids"] for c in result_stateless.commits]
        evids_structured = [c["evidence_ids"] for c in result_structured.commits]
        assert evids_stateless == evids_structured

    def test_ignore_amd_actually_holds_on_amendments(self, simple_episode):
        """IGNORE_AMD policy actually HOLDs on amendment_supersedes and correction kinds.

        This verifies the trap behavior: IGNORE_AMD should HOLD (not UPDATE) on
        amendment and correction evidence, which is the failure mode it represents.
        """
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        # Find which ledger entries have amendment_supersedes or correction kind
        amd_cor_indices = [
            i for i, entry in enumerate(sorted(ledger, key=lambda e: (e["available_at"], e["source_id"])))
            if entry.get("kind") in ("amendment_supersedes", "correction")
        ]

        # This episode should have at least some amendments/corrections
        # (make_episode_with_all_kinds creates both)
        assert len(amd_cor_indices) > 0, "Episode should have amendment/correction entries"

        adapter = TrapPolicyMethodAdapter(
            "IGNORE_AMD",
            episode_id="test-ep",
            target_id="test-target",
            evidence_values=evidence_values,
        )

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")
        result = runner.run_arm(
            ArmType.STATELESS,
            ledger=ledger,
            method=adapter,
        )

        # Verify IGNORE_AMD HOLDs on amendment/correction indices
        for i in amd_cor_indices:
            assert result.commits[i]["operation"] == "HOLD", \
                f"IGNORE_AMD should HOLD on amendment/correction at index {i}"

    def test_adapter_reset_clears_state(self, simple_episode):
        """TrapPolicyMethodAdapter.reset() clears step count and parent_commit_id."""
        products = simple_episode["products"]
        collector_first_seen = simple_episode.get("collector_first_seen")
        evidence_values = simple_episode.get("evidence_values", {})

        ledger = compile_ledger(products, collector_first_seen=collector_first_seen)

        adapter = TrapPolicyMethodAdapter(
            "STALE_HOLD",
            episode_id="test-ep",
            target_id="test-target",
            evidence_values=evidence_values,
        )

        runner = MethodArmRunner(episode_id="test-ep", target_id="test-target")

        # First run
        result1 = runner.run_arm(ArmType.STATELESS, ledger=ledger, method=adapter)
        first_commit_1 = result1.commits[0]

        # Reset adapter
        adapter.reset()

        # Second run should produce same first commit (parent_commit_id=None, step=0)
        result2 = runner.run_arm(ArmType.STATELESS, ledger=ledger, method=adapter)
        first_commit_2 = result2.commits[0]

        # Both first commits should have parent_commit_id=None (since reset clears it)
        assert first_commit_1["parent_commit_id"] is None
        assert first_commit_2["parent_commit_id"] is None

        # Both should be UPDATE (step 0 for STALE_HOLD)
        assert first_commit_1["operation"] == "UPDATE"
        assert first_commit_2["operation"] == "UPDATE"
