"""Target/episode contracts for DisasterTrace v14 (P0-02).

Provides immutable contract management for targets/episodes:
- Fixed target_id/window/threshold/O-P-R references (immutable once registered)
- Moving window/threshold on the same target_id is REJECTED
- Rolling windows require new target_ids
- Missing report != negative outcome (correct interfacing with OutcomeRegistry)

Builds on top of monitoring_fixed_v1.contracts.Target as the base.

Reuses:
- monitoring_fixed_v1.contracts.Target (base target class)
- monitoring_fixed_v1.outcomes.OutcomeRegistry, OUTCOME_FIELDS
- monitoring_fixed_v1.outcome_policies (validators)
- monitoring_v1.targets.utc_us, canonical_hash (utilities)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..monitoring_fixed_v1.contracts import Target, canonical, fingerprint
from ..monitoring_v1.targets import canonical_hash


@dataclass
class EpisodeState:
    """Tracks the lifecycle state of an episode (target + cutoff).

    Episodes transition through states:
    - pending: awaiting report/resolution
    - missing: no report filed before deadline
    - resolved: report filed with outcome value
    """

    target_id: str
    target: Target
    report_status: str = "pending"  # pending, missing, resolved
    outcome_value: int | float | None = None

    def mark_missing(self) -> None:
        """Mark the episode as missing (no report filed)."""
        if self.report_status != "pending":
            raise ValueError("Can only mark pending episodes as missing")
        self.report_status = "missing"
        self.outcome_value = None

    def resolve(self, value: int | float) -> None:
        """Resolve the episode with an outcome value."""
        if self.report_status not in {"pending", "missing"}:
            raise ValueError("Episode already resolved")
        self.report_status = "resolved"
        self.outcome_value = value


class ContractRegistry:
    """Registry for immutable target contracts.

    Once a target is registered with a target_id, its contract (window, threshold,
    entity, etc.) is fixed. Attempting to re-register the same target_id with
    different contract parameters will raise an error.

    Identical re-registration is idempotent.
    """

    def __init__(self):
        self._contracts: dict[str, Target] = {}
        self._episodes: dict[str, EpisodeState] = {}

    def register(self, target: Target) -> bool:
        """Register a target contract.

        Args:
            target: The Target to register.

        Returns:
            True if newly registered, False if already registered (identical).

        Raises:
            ValueError: If target_id already exists with different contract.
        """
        target_id = target.target_id

        if target_id in self._contracts:
            existing = self._contracts[target_id]
            # Check if contracts are identical (same contract_hash)
            if existing.contract_hash != target.contract_hash:
                raise ValueError(
                    f"Contract mismatch for target_id '{target_id}': "
                    f"cannot modify an immutable contract. "
                    f"Existing hash: {existing.contract_hash[:16]}..., "
                    f"New hash: {target.contract_hash[:16]}..."
                )
            # Identical - idempotent registration
            return False

        self._contracts[target_id] = target
        return True

    def get(self, target_id: str) -> Target | None:
        """Get a registered target by target_id.

        Returns None if not registered.
        """
        return self._contracts.get(target_id)

    def count(self) -> int:
        """Return the number of registered contracts."""
        return len(self._contracts)

    def create_episode(self, target_id: str) -> EpisodeState:
        """Create an episode state for a registered target.

        Args:
            target_id: The target_id of the registered contract.

        Returns:
            A new EpisodeState instance.

        Raises:
            ValueError: If target_id is not registered.
        """
        target = self._contracts.get(target_id)
        if target is None:
            raise ValueError(f"Target '{target_id}' is not registered")

        episode = EpisodeState(target_id=target_id, target=target)
        return episode

    def export(self) -> dict:
        """Export registry state for persistence.

        Returns:
            Dict with schema version and all registered contracts.
        """
        contracts = {}
        for target_id, target in self._contracts.items():
            contracts[target_id] = {
                "target": target.to_dict(),
                "contract_hash": target.contract_hash,
            }

        return {
            "schema": "disastertrace.contract_registry.v1",
            "contracts": contracts,
        }

    @classmethod
    def restore(cls, data: dict) -> "ContractRegistry":
        """Restore a ContractRegistry from exported data.

        Args:
            data: The exported state dict.

        Returns:
            A new ContractRegistry with the restored contracts.
        """
        registry = cls()

        for target_id, contract_data in data.get("contracts", {}).items():
            target = Target(**contract_data["target"])
            # Verify hash matches
            if target.contract_hash != contract_data["contract_hash"]:
                raise ValueError(
                    f"Contract hash mismatch during restore for '{target_id}'"
                )
            registry._contracts[target_id] = target

        return registry


def classify_report_status(
    target: Target,
    *,
    report_value: int | float | None,
    report_filed: bool,
) -> str:
    """Classify the report status for a target.

    Missing reports are NOT negative outcomes - they are a distinct status.

    Args:
        target: The target being evaluated.
        report_value: The outcome value (0 or 1 for events, or None).
        report_filed: Whether a report was actually filed.

    Returns:
        One of: "missing", "settled_negative", "settled_positive"
    """
    if not report_filed or report_value is None:
        return "missing"

    # For event_probability targets, 0 = event did not occur, 1 = event occurred
    if target.output_kind == "event_probability":
        if report_value == 0:
            return "settled_negative"
        elif report_value == 1:
            return "settled_positive"

    # For scalar targets, we don't have a simple positive/negative distinction
    # Return based on value being present
    return "settled_positive" if report_value is not None else "missing"


def build_outcome_record(
    *,
    target: Target,
    resolution_version: str,
    status: str,
    value: int | float | None = None,
    source_revision: str | None = None,
    source_sha256: str | None = None,
    observed_at: int | None = None,
    published_at: int | None = None,
    fetched_at: int | None = None,
    resolved_at: int,
    quality_status: str = "pending",
    availability_basis: str = "observed_first_seen",
    **extra_fields,
) -> dict:
    """Build an outcome record compatible with OutcomeRegistry's OUTCOME_FIELDS.

    This builds the 15-field record required by OutcomeRegistry.register().

    Args:
        target: The target for this outcome.
        resolution_version: Version identifier for the resolution.
        status: One of "mature", "provisional", "missing".
        value: The outcome value (None for missing).
        source_revision: Source identifier.
        source_sha256: Hash of the source data.
        observed_at: When the outcome was observed.
        published_at: When the outcome was published.
        fetched_at: When the outcome was fetched.
        resolved_at: When the outcome was resolved.
        quality_status: Quality indicator string.
        availability_basis: How availability was determined.
        **extra_fields: Additional optional fields (references, etc.)

    Returns:
        Dict with at least the 15 OUTCOME_FIELDS.
    """
    record = {
        # Core identity
        "target_contract_hash": target.contract_hash,
        "resolution_version": resolution_version,
        # Value and status
        "value": value,
        "status": status,
        # Source identity
        "source_revision": source_revision,
        "source_sha256": source_sha256,
        # Physical support (copied from target)
        "physical_start": target.physical_start,
        "physical_end": target.physical_end,
        "units": target.units,
        # Quality
        "quality_status": quality_status,
        # Timestamps
        "observed_at": observed_at,
        "published_at": published_at,
        "fetched_at": fetched_at,
        "resolved_at": resolved_at,
        # Availability
        "availability_basis": availability_basis,
    }

    # Add any extra fields (like references, reference_kind, etc.)
    record.update(extra_fields)

    return record
