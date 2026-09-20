"""P1 harness: baselines, method-arm runner, and episode config for DisasterTrace v14.

This module provides the scaffold for running methods (trap policies or LLM agents)
against episodes under controlled experimental conditions.

Components:
1. **Baseline family** (section 4 of NOVELTY_POSITIONING_v16_CN.md):
   - AlwaysZeroBaseline: constant zero-probability floor baseline
   - ClimatologyBaseline: development-period climatology (stub, D05 split rules)
   - PersistenceBaseline: carries forward last known committed value
   - FollowMappingBaseline: interface stub for TAF frozen research mapping
   - ValuesBankBaseline: interface stub for values-bank-based baseline (D05)

2. **Method-arm runner** (three representation arms):
   - STATELESS: method sees only the current evidence package each turn
   - APPEND: method sees the full append-only history of evidence packages
   - STRUCTURED: method sees a structured belief-commit state object

3. **Episode config** (Natural vs Controlled):
   - NaturalConfig: uses episode's evidence stream as-is
   - ControlledConfig: applies safety caps with explicit cap_hit reporting

Reuses:
- canonical_hash from monitoring_v1/targets.py (deterministic state hashing)
- compile_ledger, visible_at from revision_v1/ledger.py
- CommitStore, CommitProcessor from revision_v1/belief_commit.py
- trajectory_score_Q_with_bounds, effective_at_from_commits from revision_v1/metrics.py
- apply_policy, POLICY_NAMES from revision_v1/trap_policies.py

D10 pattern follows multimodal_v1/acquire.py: budget/cap enforcement with explicit
reporting of cap_hit status, never silent truncation.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

from ..monitoring_v1.targets import canonical_hash


# ---------------------------------------------------------------------------
# Claim status for baseline/method results (per NOVELTY_POSITIONING_v16 section 5)
# ---------------------------------------------------------------------------

class ClaimStatus(Enum):
    """Four-value claim status per v15 measurement discipline."""
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    INCONCLUSIVE = "inconclusive"
    NOT_TESTED = "not_tested"


# ---------------------------------------------------------------------------
# Baseline family (NOVELTY_POSITIONING_v16 section 4)
# ---------------------------------------------------------------------------


class Baseline(ABC):
    """Abstract base class for all baselines.

    Each baseline takes an episode's ledger + a target/timepoint and produces
    a scoreable prediction. All baselines must be aligned to the *same* target
    and *same* timepoint (full-denominator: every registered target gets a
    prediction from every baseline, no silent drops).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the baseline's registered name."""
        pass

    @abstractmethod
    def predict(
        self,
        target_id: str,
        timepoint: int,
        *,
        ledger: list[dict] | None = None,
        evidence_values: dict[str, float] | None = None,
    ) -> dict:
        """Generate a prediction for the given target at the given timepoint.

        Args:
            target_id: The target identifier.
            timepoint: The timepoint in microseconds (as-of time).
            ledger: Optional ledger entries visible at timepoint.
            evidence_values: Optional evidence value mapping.

        Returns:
            Dict with:
                probability: float in [0, 1] (or None if not_tested)
                claim_status: ClaimStatus value
                baseline_name: name of this baseline
                target_id: echoed target_id
                timepoint: echoed timepoint
                metadata: any additional baseline-specific info
        """
        pass


class AlwaysZeroBaseline(Baseline):
    """Trivial floor baseline: constant zero-probability.

    Per NOVELTY_POSITIONING_v16 section 4: "必须纳入，作为下界参照，
    排除'稀有事件下弱基线假改善'的误读"
    """

    @property
    def name(self) -> str:
        return "always_zero"

    def predict(
        self,
        target_id: str,
        timepoint: int,
        *,
        ledger: list[dict] | None = None,
        evidence_values: dict[str, float] | None = None,
    ) -> dict:
        return {
            "probability": 0.0,
            "claim_status": ClaimStatus.SUPPORTED,
            "baseline_name": self.name,
            "target_id": target_id,
            "timepoint": timepoint,
            "metadata": {"description": "constant zero floor"},
        }


class ClimatologyBaseline(Baseline):
    """Development-period climatology baseline (stub).

    Per D05 values-bank split: 2023 train / 2024 Jan-Nov calibration /
    2025 development split. The climatology rate is computed ONLY from
    the designated development period, never from the same period being scored.

    This is a stub that stores a pre-computed climatology rate. Real data
    loading is deferred to a future round when actual data is available.
    """

    def __init__(self, climatology_rate: float | None = None):
        """Initialize with an optional pre-computed climatology rate.

        Args:
            climatology_rate: The climatology rate in [0, 1], or None if
                not yet computed (will return not_tested status).
        """
        self._climatology_rate = climatology_rate

    @property
    def name(self) -> str:
        return "climatology"

    def predict(
        self,
        target_id: str,
        timepoint: int,
        *,
        ledger: list[dict] | None = None,
        evidence_values: dict[str, float] | None = None,
    ) -> dict:
        if self._climatology_rate is None:
            return {
                "probability": None,
                "claim_status": ClaimStatus.NOT_TESTED,
                "baseline_name": self.name,
                "target_id": target_id,
                "timepoint": timepoint,
                "metadata": {
                    "description": "development-period climatology (no data loaded)",
                    "reason": "climatology rate not yet computed from real data",
                },
            }

        return {
            "probability": self._climatology_rate,
            "claim_status": ClaimStatus.SUPPORTED,
            "baseline_name": self.name,
            "target_id": target_id,
            "timepoint": timepoint,
            "metadata": {
                "description": "development-period climatology",
                "climatology_rate": self._climatology_rate,
            },
        }


class PersistenceBaseline(Baseline):
    """Persistence baseline: carries forward the last known committed value.

    Per NOVELTY_POSITIONING_v16 section 4: "必须纳入" as one of the
    required baselines alongside climatology and always-zero.
    """

    def __init__(self, fallback: float = 0.5):
        """Initialize with a fallback value for when no prior value exists.

        Args:
            fallback: Probability to use when no prior commits exist.
        """
        self._fallback = fallback
        self._last_values: dict[str, float] = {}

    @property
    def name(self) -> str:
        return "persistence"

    def update(self, target_id: str, probability: float) -> None:
        """Update the last known value for a target.

        Args:
            target_id: The target identifier.
            probability: The new probability value.
        """
        if not 0 <= probability <= 1:
            raise ValueError(f"probability must be in [0, 1], got {probability}")
        self._last_values[target_id] = probability

    def predict(
        self,
        target_id: str,
        timepoint: int,
        *,
        ledger: list[dict] | None = None,
        evidence_values: dict[str, float] | None = None,
    ) -> dict:
        # Get the last known value, or fallback if none exists
        if target_id in self._last_values:
            probability = self._last_values[target_id]
            has_prior = True
        else:
            probability = self._fallback
            has_prior = False

        return {
            "probability": probability,
            "claim_status": ClaimStatus.SUPPORTED,
            "baseline_name": self.name,
            "target_id": target_id,
            "timepoint": timepoint,
            "metadata": {
                "description": "persistence (last known value)",
                "has_prior_value": has_prior,
                "fallback_used": not has_prior,
            },
        }


class FollowMappingBaseline(Baseline):
    """Interface stub for TAF frozen research mapping baseline.

    Per NOVELTY_POSITIONING_v16 section 4: "FOLLOW（TAF 冻结研究映射）"
    with documented H15 Brier 0.0191 vs F_BASE_ONLY 0.0050.

    This is an interface stub that signals not_tested until real FOLLOW
    data is wired in a future round. The call signature is already correct
    so it slots into the runner without changes later.
    """

    @property
    def name(self) -> str:
        return "follow_mapping"

    def predict(
        self,
        target_id: str,
        timepoint: int,
        *,
        ledger: list[dict] | None = None,
        evidence_values: dict[str, float] | None = None,
    ) -> dict:
        return {
            "probability": None,
            "claim_status": ClaimStatus.NOT_TESTED,
            "baseline_name": self.name,
            "target_id": target_id,
            "timepoint": timepoint,
            "metadata": {
                "description": "TAF frozen research mapping (FOLLOW)",
                "reason": "interface stub, real FOLLOW data not yet available",
                "documented_h15_brier": 0.0191,
                "documented_f_base_only_brier": 0.0050,
            },
        }


class ValuesBankBaseline(Baseline):
    """Interface stub for values-bank-based baseline.

    Per D05: 2023 train / 2024 Jan-Nov calibration / 2025 development split.
    This baseline uses a values-bank refit that cannot be exercised without
    real data yet.

    This is an interface stub with the correct call signature reserved for
    a future round.
    """

    @property
    def name(self) -> str:
        return "values_bank"

    def predict(
        self,
        target_id: str,
        timepoint: int,
        *,
        ledger: list[dict] | None = None,
        evidence_values: dict[str, float] | None = None,
    ) -> dict:
        return {
            "probability": None,
            "claim_status": ClaimStatus.NOT_TESTED,
            "baseline_name": self.name,
            "target_id": target_id,
            "timepoint": timepoint,
            "metadata": {
                "description": "values-bank refit baseline (D05 split)",
                "reason": "interface stub, real values-bank data not yet available",
                "d05_split": "2023 train / 2024 Jan-Nov calibration / 2025 development",
            },
        }


# ---------------------------------------------------------------------------
# Method arm types
# ---------------------------------------------------------------------------


class ArmType(Enum):
    """Three representation arms for method execution."""
    STATELESS = "stateless"  # Method sees only current evidence package
    APPEND = "append"        # Method sees full append-only history
    STRUCTURED = "structured"  # Method sees structured belief-commit state


# ---------------------------------------------------------------------------
# Method protocol (trap policy or LLM agent)
# ---------------------------------------------------------------------------


class Method(Protocol):
    """Protocol for methods that can be run through the arm runner.

    Methods can be trap policies from trap_policies.py or LLM agents.
    The protocol defines the interface they must implement.
    """

    def process_evidence(
        self,
        evidence: dict,
        *,
        arm_type: ArmType,
        history: list[dict] | None = None,
        state: dict | None = None,
    ) -> dict:
        """Process a single evidence package and return a commit-shaped response.

        Args:
            evidence: The current evidence package (ledger entry).
            arm_type: Which arm representation is being used.
            history: For APPEND arm, the full history of evidence packages.
            state: For STRUCTURED arm, the current belief-commit state.

        Returns:
            A commit-shaped dict compatible with belief_commit.v14-draft schema.
        """
        ...


# ---------------------------------------------------------------------------
# Arm state: hashable/deterministic at each step
# ---------------------------------------------------------------------------


@dataclass
class ArmState:
    """Immutable snapshot of arm state at a single step.

    The state must be hashable (deterministic, reproducible) at each step.
    This follows the canonical_hash pattern from targets.py.
    """
    arm_type: ArmType
    step_index: int
    evidence_ids_seen: tuple[str, ...]  # Tuple for hashability
    current_probability: float | None
    current_facts: dict[str, Any] = field(default_factory=dict)

    def canonical_repr(self) -> dict:
        """Return a canonical representation for hashing."""
        return {
            "arm_type": self.arm_type.value,
            "step_index": self.step_index,
            "evidence_ids_seen": list(self.evidence_ids_seen),
            "current_probability": self.current_probability,
            "current_facts": self.current_facts,
        }

    def state_hash(self) -> str:
        """Compute deterministic hash of this state."""
        return canonical_hash(self.canonical_repr())


# ---------------------------------------------------------------------------
# Method-arm runner
# ---------------------------------------------------------------------------


@dataclass
class ArmRunResult:
    """Result of running a method under a single arm."""
    arm_type: ArmType
    commits: list[dict]
    final_state: ArmState
    state_hashes: list[str]  # Hash at each step for reproducibility verification
    metadata: dict = field(default_factory=dict)


class MethodArmRunner:
    """Runner that executes a method under the three representation arms.

    All three arms give the method the *same underlying information* (nothing
    hidden in one arm that's available in another) and the *same tool/action
    permissions* -- only the *representation* of state differs.
    """

    def __init__(
        self,
        *,
        episode_id: str,
        target_id: str,
        fallback_probability: float = 0.5,
    ):
        """Initialize the runner.

        Args:
            episode_id: Episode identifier for commits.
            target_id: Target identifier for commits.
            fallback_probability: Probability to use before any evidence.
        """
        self.episode_id = episode_id
        self.target_id = target_id
        self.fallback_probability = fallback_probability

    def run_arm(
        self,
        arm_type: ArmType,
        *,
        ledger: list[dict],
        method: Callable[[dict, ArmType, list[dict] | None, dict | None], dict],
        evidence_values: dict[str, float] | None = None,
    ) -> ArmRunResult:
        """Run a method under a single arm type.

        Args:
            arm_type: Which representation arm to use.
            ledger: The episode's ledger entries (sorted by available_at).
            method: Callable that processes evidence and returns commits.
                Signature: (evidence, arm_type, history, state) -> commit
            evidence_values: Optional mapping of source_id -> probability.

        Returns:
            ArmRunResult with commits, final state, and state hashes.
        """
        evidence_values = evidence_values or {}

        # Sort ledger by available_at for processing order
        sorted_ledger = sorted(ledger, key=lambda e: (e["available_at"], e["source_id"]))

        commits: list[dict] = []
        state_hashes: list[str] = []
        history: list[dict] = []
        evidence_ids_seen: list[str] = []
        current_probability = self.fallback_probability
        current_facts: dict[str, Any] = {}

        for step_index, entry in enumerate(sorted_ledger):
            source_id = entry["source_id"]
            evidence_ids_seen.append(source_id)

            # Build state snapshot before processing
            arm_state = ArmState(
                arm_type=arm_type,
                step_index=step_index,
                evidence_ids_seen=tuple(evidence_ids_seen),
                current_probability=current_probability,
                current_facts=copy.deepcopy(current_facts),
            )
            state_hashes.append(arm_state.state_hash())

            # Prepare arm-specific inputs
            if arm_type == ArmType.STATELESS:
                # Only current evidence, no history or state
                commit = method(entry, arm_type, None, None)
            elif arm_type == ArmType.APPEND:
                # Full history of evidence packages
                history.append(entry)
                commit = method(entry, arm_type, list(history), None)
            elif arm_type == ArmType.STRUCTURED:
                # Structured state object
                state_dict = {
                    "current_probability": current_probability,
                    "facts": copy.deepcopy(current_facts),
                    "evidence_ids_seen": list(evidence_ids_seen),
                    "step_index": step_index,
                }
                commit = method(entry, arm_type, None, state_dict)
            else:
                raise ValueError(f"Unknown arm type: {arm_type}")

            commits.append(commit)

            # Update running state from commit
            if commit.get("operation") != "HOLD":
                for forecast in commit.get("forecast_updates", []):
                    if forecast.get("target_id") == self.target_id:
                        prob = forecast.get("event_probability")
                        if prob is not None:
                            current_probability = prob
                for fact in commit.get("fact_updates", []):
                    slot = fact.get("slot")
                    if slot:
                        current_facts[slot] = {
                            "operation": fact.get("operation"),
                            "value": fact.get("value"),
                        }

        # Final state
        final_state = ArmState(
            arm_type=arm_type,
            step_index=len(sorted_ledger),
            evidence_ids_seen=tuple(evidence_ids_seen),
            current_probability=current_probability,
            current_facts=copy.deepcopy(current_facts),
        )

        return ArmRunResult(
            arm_type=arm_type,
            commits=commits,
            final_state=final_state,
            state_hashes=state_hashes,
            metadata={
                "episode_id": self.episode_id,
                "target_id": self.target_id,
                "evidence_count": len(sorted_ledger),
            },
        )

    def run_all_arms(
        self,
        *,
        ledger: list[dict],
        method: Callable[[dict, ArmType, list[dict] | None, dict | None], dict],
        evidence_values: dict[str, float] | None = None,
    ) -> dict[ArmType, ArmRunResult]:
        """Run a method under all three arms.

        Args:
            ledger: The episode's ledger entries.
            method: Callable that processes evidence and returns commits.
            evidence_values: Optional mapping of source_id -> probability.

        Returns:
            Dict mapping ArmType to ArmRunResult.
        """
        results = {}
        for arm_type in ArmType:
            results[arm_type] = self.run_arm(
                arm_type,
                ledger=ledger,
                method=method,
                evidence_values=evidence_values,
            )
        return results


# ---------------------------------------------------------------------------
# Episode config: Natural vs Controlled
# ---------------------------------------------------------------------------


@dataclass
class EpisodeConfig:
    """Base configuration for episode execution."""
    name: str
    description: str

    def should_stop(
        self,
        *,
        evidence_count: int,
        elapsed_steps: int,
        elapsed_time_us: int | None = None,
    ) -> tuple[bool, str | None]:
        """Check if execution should stop.

        Args:
            evidence_count: Number of evidence packages processed.
            elapsed_steps: Number of steps taken.
            elapsed_time_us: Optional elapsed wall-clock time in microseconds.

        Returns:
            Tuple of (should_stop, cap_name if hit else None).
        """
        return False, None


@dataclass
class NaturalConfig(EpisodeConfig):
    """Natural config: uses the episode's evidence stream as-is.

    No caps applied -- the episode runs to natural completion.
    """

    def __init__(self):
        super().__init__(
            name="natural",
            description="Natural revision frequency, no caps",
        )

    def should_stop(
        self,
        *,
        evidence_count: int,
        elapsed_steps: int,
        elapsed_time_us: int | None = None,
    ) -> tuple[bool, str | None]:
        # Natural config never stops early
        return False, None


@dataclass
class ControlledConfig(EpisodeConfig):
    """Controlled config: applies safety caps with explicit cap_hit reporting.

    Per D10 pattern from multimodal_v1/acquire.py: budget/cap enforcement with
    explicit reporting, never silent truncation. When a cap is hit, that must
    be reported as a separate, explicit flag on the result.
    """
    max_evidence_packages: int | None = None
    max_steps: int | None = None
    max_wall_time_us: int | None = None

    def __init__(
        self,
        *,
        max_evidence_packages: int | None = 100,
        max_steps: int | None = 100,
        max_wall_time_us: int | None = None,
    ):
        super().__init__(
            name="controlled",
            description="Controlled mode with safety caps",
        )
        self.max_evidence_packages = max_evidence_packages
        self.max_steps = max_steps
        self.max_wall_time_us = max_wall_time_us

    def should_stop(
        self,
        *,
        evidence_count: int,
        elapsed_steps: int,
        elapsed_time_us: int | None = None,
    ) -> tuple[bool, str | None]:
        if self.max_evidence_packages is not None and evidence_count >= self.max_evidence_packages:
            return True, "max_evidence_packages"

        if self.max_steps is not None and elapsed_steps >= self.max_steps:
            return True, "max_steps"

        if (
            self.max_wall_time_us is not None
            and elapsed_time_us is not None
            and elapsed_time_us >= self.max_wall_time_us
        ):
            return True, "max_wall_time_us"

        return False, None


# ---------------------------------------------------------------------------
# Episode runner with config
# ---------------------------------------------------------------------------


@dataclass
class EpisodeRunResult:
    """Result of running an episode with a config."""
    config_name: str
    arm_type: ArmType
    commits: list[dict]
    evidence_processed: int
    steps_taken: int
    completed_naturally: bool
    cap_hit: bool
    cap_name: str | None
    final_state: ArmState
    state_hashes: list[str]
    metadata: dict = field(default_factory=dict)


class EpisodeRunner:
    """Runner that executes an episode with a given config.

    Handles both Natural and Controlled configs, with explicit cap_hit
    reporting for Controlled mode per D10 discipline.
    """

    def __init__(
        self,
        *,
        episode_id: str,
        target_id: str,
        config: EpisodeConfig,
        fallback_probability: float = 0.5,
    ):
        """Initialize the episode runner.

        Args:
            episode_id: Episode identifier.
            target_id: Target identifier.
            config: Episode configuration (Natural or Controlled).
            fallback_probability: Probability before any evidence.
        """
        self.episode_id = episode_id
        self.target_id = target_id
        self.config = config
        self.fallback_probability = fallback_probability

    def run(
        self,
        *,
        arm_type: ArmType,
        ledger: list[dict],
        method: Callable[[dict, ArmType, list[dict] | None, dict | None], dict],
        evidence_values: dict[str, float] | None = None,
        start_time_us: int | None = None,
        current_time_provider: Callable[[], int] | None = None,
    ) -> EpisodeRunResult:
        """Run the episode under the given arm type.

        Args:
            arm_type: Which representation arm to use.
            ledger: The episode's ledger entries (sorted by available_at).
            method: Callable that processes evidence and returns commits.
            evidence_values: Optional mapping of source_id -> probability.
            start_time_us: Optional start time for wall-clock cap checking.
            current_time_provider: Optional callable returning current time in us.

        Returns:
            EpisodeRunResult with full execution details.
        """
        evidence_values = evidence_values or {}

        # Sort ledger by available_at
        sorted_ledger = sorted(ledger, key=lambda e: (e["available_at"], e["source_id"]))

        commits: list[dict] = []
        state_hashes: list[str] = []
        history: list[dict] = []
        evidence_ids_seen: list[str] = []
        current_probability = self.fallback_probability
        current_facts: dict[str, Any] = {}

        cap_hit = False
        cap_name: str | None = None
        evidence_processed = 0
        steps_taken = 0

        for step_index, entry in enumerate(sorted_ledger):
            # Check caps before processing
            elapsed_time_us = None
            if start_time_us is not None and current_time_provider is not None:
                elapsed_time_us = current_time_provider() - start_time_us

            should_stop, hit_cap = self.config.should_stop(
                evidence_count=evidence_processed,
                elapsed_steps=steps_taken,
                elapsed_time_us=elapsed_time_us,
            )

            if should_stop:
                cap_hit = True
                cap_name = hit_cap
                break

            source_id = entry["source_id"]
            evidence_ids_seen.append(source_id)

            # Build state snapshot
            arm_state = ArmState(
                arm_type=arm_type,
                step_index=step_index,
                evidence_ids_seen=tuple(evidence_ids_seen),
                current_probability=current_probability,
                current_facts=copy.deepcopy(current_facts),
            )
            state_hashes.append(arm_state.state_hash())

            # Prepare arm-specific inputs and call method
            if arm_type == ArmType.STATELESS:
                commit = method(entry, arm_type, None, None)
            elif arm_type == ArmType.APPEND:
                history.append(entry)
                commit = method(entry, arm_type, list(history), None)
            elif arm_type == ArmType.STRUCTURED:
                state_dict = {
                    "current_probability": current_probability,
                    "facts": copy.deepcopy(current_facts),
                    "evidence_ids_seen": list(evidence_ids_seen),
                    "step_index": step_index,
                }
                commit = method(entry, arm_type, None, state_dict)
            else:
                raise ValueError(f"Unknown arm type: {arm_type}")

            commits.append(commit)
            evidence_processed += 1
            steps_taken += 1

            # Update running state
            if commit.get("operation") != "HOLD":
                for forecast in commit.get("forecast_updates", []):
                    if forecast.get("target_id") == self.target_id:
                        prob = forecast.get("event_probability")
                        if prob is not None:
                            current_probability = prob
                for fact in commit.get("fact_updates", []):
                    slot = fact.get("slot")
                    if slot:
                        current_facts[slot] = {
                            "operation": fact.get("operation"),
                            "value": fact.get("value"),
                        }

        # Final state
        final_state = ArmState(
            arm_type=arm_type,
            step_index=steps_taken,
            evidence_ids_seen=tuple(evidence_ids_seen),
            current_probability=current_probability,
            current_facts=copy.deepcopy(current_facts),
        )

        return EpisodeRunResult(
            config_name=self.config.name,
            arm_type=arm_type,
            commits=commits,
            evidence_processed=evidence_processed,
            steps_taken=steps_taken,
            completed_naturally=not cap_hit,
            cap_hit=cap_hit,
            cap_name=cap_name,
            final_state=final_state,
            state_hashes=state_hashes,
            metadata={
                "episode_id": self.episode_id,
                "target_id": self.target_id,
                "total_evidence_available": len(sorted_ledger),
            },
        )


# ---------------------------------------------------------------------------
# Baseline registry for full-denominator reporting
# ---------------------------------------------------------------------------


class BaselineRegistry:
    """Registry for managing baselines with full-denominator reporting.

    Per NOVELTY_POSITIONING_v16 section 5: "全分母报告：不删除注册目标"
    All registered baselines must participate in scoring; no silent drops.
    """

    def __init__(self):
        self._baselines: dict[str, Baseline] = {}

    def register(self, baseline: Baseline) -> None:
        """Register a baseline.

        Args:
            baseline: The baseline to register.

        Raises:
            ValueError: If a baseline with this name is already registered.
        """
        if baseline.name in self._baselines:
            raise ValueError(f"Baseline '{baseline.name}' already registered")
        self._baselines[baseline.name] = baseline

    def get(self, name: str) -> Baseline | None:
        """Get a registered baseline by name."""
        return self._baselines.get(name)

    def all_baselines(self) -> list[Baseline]:
        """Return all registered baselines."""
        return list(self._baselines.values())

    def predict_all(
        self,
        target_id: str,
        timepoint: int,
        *,
        ledger: list[dict] | None = None,
        evidence_values: dict[str, float] | None = None,
    ) -> dict[str, dict]:
        """Generate predictions from all registered baselines.

        Full-denominator: every registered baseline produces a prediction
        (possibly with claim_status=NOT_TESTED for stubs).

        Args:
            target_id: The target identifier.
            timepoint: The timepoint in microseconds.
            ledger: Optional ledger entries.
            evidence_values: Optional evidence values.

        Returns:
            Dict mapping baseline_name to prediction dict.
        """
        results = {}
        for baseline in self._baselines.values():
            results[baseline.name] = baseline.predict(
                target_id,
                timepoint,
                ledger=ledger,
                evidence_values=evidence_values,
            )
        return results


def create_default_baseline_registry() -> BaselineRegistry:
    """Create a registry with all required baselines pre-registered.

    Per NOVELTY_POSITIONING_v16 section 4:
    - always_zero
    - climatology (stub)
    - persistence
    - follow_mapping (stub)
    - values_bank (stub)
    """
    registry = BaselineRegistry()
    registry.register(AlwaysZeroBaseline())
    registry.register(ClimatologyBaseline())
    registry.register(PersistenceBaseline())
    registry.register(FollowMappingBaseline())
    registry.register(ValuesBankBaseline())
    return registry
