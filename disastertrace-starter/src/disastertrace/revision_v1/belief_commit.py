"""Belief commit adapter for DisasterTrace v14 (P0-03).

Implements the disastertrace.belief_commit.v14-draft schema with:
- operation: UPDATE | HOLD | FOLLOW_BASELINE semantics
- Verbatim preservation of raw submitted payloads (even if invalid)
- parent_commit_id hash chain integrity via canonical_hash
- Invalid commit handling with retained errors and fallback behavior
- Two-layer recording: raw submission vs effective state

Reuses:
- canonical_hash from monitoring_v1/targets.py (hash chain)
- visible_at from revision_v1/ledger.py (evidence visibility check)
- ContractRegistry from revision_v1/contracts.py (target validation)
- adoption.validate/decide from monitoring_fixed_v1/adoption.py (FOLLOW_BASELINE precedent)
"""

from __future__ import annotations

import copy
import re
from typing import Any, Callable

from ..monitoring_v1.targets import canonical_hash


# Schema constants
SCHEMA_VERSION = "disastertrace.belief_commit.v14-draft"

VALID_OPERATIONS = {"UPDATE", "HOLD", "FOLLOW_BASELINE"}

VALID_NEXT_ACTION_KINDS = {"WAIT", "READ", "SEARCH", "TOOL", "STOP_ACTIVE"}

VALID_FACT_OPERATIONS = {"SET", "RETRACT", "KEEP_UNKNOWN"}

VALID_SUPPORT_STATUSES = {"supported", "refuted", "undetermined", "inconsistent"}

# Required fields in the commit schema
REQUIRED_FIELDS = {
    "schema_version",
    "episode_id",
    "target_id",
    "parent_commit_id",  # can be null
    "as_of",
    "operation",
    "evidence_ids",
    "fact_updates",
    "forecast_updates",
    "next_action",
}


def _validate_iso_timestamp(value: str) -> bool:
    """Check if value is a valid ISO 8601 timestamp."""
    if not isinstance(value, str):
        return False
    # Basic ISO 8601 pattern with timezone
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([.]\d+)?(Z|[+-]\d{2}:\d{2})$"
    return bool(re.match(pattern, value))


def _validate_fact_update(item: dict) -> tuple[bool, str | None]:
    """Validate a single fact_update item."""
    required = {"slot", "operation", "support_status", "value", "source_ids"}
    if not isinstance(item, dict):
        return False, "fact_update must be a dict"

    missing = required - set(item.keys())
    if missing:
        return False, f"fact_update missing fields: {missing}"

    if item["operation"] not in VALID_FACT_OPERATIONS:
        return False, f"fact_update operation must be one of {VALID_FACT_OPERATIONS}"

    if item["support_status"] not in VALID_SUPPORT_STATUSES:
        return False, f"fact_update support_status must be one of {VALID_SUPPORT_STATUSES}"

    if not isinstance(item["source_ids"], list):
        return False, "fact_update source_ids must be a list"

    return True, None


def _validate_forecast_update(item: dict) -> tuple[bool, str | None]:
    """Validate a single forecast_update item."""
    if not isinstance(item, dict):
        return False, "forecast_update must be a dict"

    if "target_id" not in item:
        return False, "forecast_update missing target_id"

    if "event_probability" not in item:
        return False, "forecast_update missing event_probability"

    prob = item["event_probability"]
    if not isinstance(prob, (int, float)):
        return False, "event_probability must be a number"

    if prob < 0 or prob > 1:
        return False, f"event_probability must be in [0, 1], got {prob}"

    return True, None


def _validate_next_action(action: dict) -> tuple[bool, str | None]:
    """Validate the next_action field."""
    if not isinstance(action, dict):
        return False, "next_action must be a dict"

    if "kind" not in action:
        return False, "next_action missing kind"

    if action["kind"] not in VALID_NEXT_ACTION_KINDS:
        return False, f"next_action kind must be one of {VALID_NEXT_ACTION_KINDS}"

    if "until_or_args" not in action:
        return False, "next_action missing until_or_args"

    return True, None


def validate_commit_schema(commit: dict) -> dict:
    """Validate a commit payload against the v14-draft schema.

    Args:
        commit: The commit payload dict.

    Returns:
        Dict with:
            valid: True if schema is valid, False otherwise.
            error: Error message if invalid, None if valid.
    """
    if not isinstance(commit, dict):
        return {"valid": False, "error": "commit must be a dict"}

    # Check required fields
    missing = REQUIRED_FIELDS - set(commit.keys())
    if missing:
        return {"valid": False, "error": f"missing required fields: {missing}"}

    # Check schema_version
    if commit["schema_version"] != SCHEMA_VERSION:
        return {
            "valid": False,
            "error": f"schema_version must be '{SCHEMA_VERSION}', got '{commit['schema_version']}'",
        }

    # Check operation
    if commit["operation"] not in VALID_OPERATIONS:
        return {
            "valid": False,
            "error": f"operation must be one of {VALID_OPERATIONS}, got '{commit['operation']}'",
        }

    # HOLD operation must have empty fact_updates and forecast_updates
    if commit["operation"] == "HOLD":
        if commit.get("fact_updates") and len(commit["fact_updates"]) > 0:
            return {
                "valid": False,
                "error": "HOLD operation must have empty fact_updates",
            }
        if commit.get("forecast_updates") and len(commit["forecast_updates"]) > 0:
            return {
                "valid": False,
                "error": "HOLD operation must have empty forecast_updates",
            }

    # Check as_of is valid ISO timestamp
    if not _validate_iso_timestamp(commit["as_of"]):
        return {"valid": False, "error": f"as_of must be valid ISO timestamp, got '{commit['as_of']}'"}

    # Check evidence_ids is a list
    if not isinstance(commit.get("evidence_ids"), list):
        return {"valid": False, "error": "evidence_ids must be a list"}

    # Check fact_updates
    if not isinstance(commit.get("fact_updates"), list):
        return {"valid": False, "error": "fact_updates must be a list"}

    for i, item in enumerate(commit.get("fact_updates", [])):
        valid, err = _validate_fact_update(item)
        if not valid:
            return {"valid": False, "error": f"fact_updates[{i}]: {err}"}

    # Check forecast_updates
    if not isinstance(commit.get("forecast_updates"), list):
        return {"valid": False, "error": "forecast_updates must be a list"}

    for i, item in enumerate(commit.get("forecast_updates", [])):
        valid, err = _validate_forecast_update(item)
        if not valid:
            return {"valid": False, "error": f"forecast_updates[{i}]: {err}"}

    # Check next_action
    if "next_action" not in commit or commit["next_action"] is None:
        return {"valid": False, "error": "next_action is required"}

    valid, err = _validate_next_action(commit["next_action"])
    if not valid:
        return {"valid": False, "error": f"next_action: {err}"}

    return {"valid": True, "error": None}


def compute_commit_id(commit: dict) -> str:
    """Compute the commit ID via canonical_hash.

    The commit ID is derived from the canonical hash of the commit content.
    This includes the parent_commit_id to form a hash chain.

    Args:
        commit: The commit payload dict.

    Returns:
        A 64-character hex hash string.
    """
    # Create a canonical representation for hashing
    # Include all semantic fields that define the commit identity
    hashable = {
        "schema_version": commit.get("schema_version"),
        "episode_id": commit.get("episode_id"),
        "target_id": commit.get("target_id"),
        "parent_commit_id": commit.get("parent_commit_id"),
        "as_of": commit.get("as_of"),
        "operation": commit.get("operation"),
        "evidence_ids": commit.get("evidence_ids", []),
        "fact_updates": commit.get("fact_updates", []),
        "forecast_updates": commit.get("forecast_updates", []),
        "next_action": commit.get("next_action"),
    }
    return canonical_hash(hashable)


class CommitStore:
    """Storage for raw commits and effective states.

    Two-layer recording:
    - Raw commits: stored verbatim as submitted (even if invalid)
    - Effective states: resolved state after applying commit semantics

    The store maintains:
    - Per-commit raw records (indexed by commit_id)
    - Per-episode current effective state
    - Per-commit effective state snapshots (for historical queries)
    """

    def __init__(self):
        # Raw commit records indexed by commit_id
        self._raw_commits: dict[str, dict] = {}
        # Current effective state per episode
        self._effective_states: dict[str, dict] = {}
        # Effective state snapshot per commit (for historical queries)
        self._effective_at_commit: dict[str, dict] = {}
        # Chain tracking: episode_id -> latest commit_id
        self._latest_commit: dict[str, str] = {}

    def store_raw_commit(
        self,
        commit_id: str,
        payload: dict,
        *,
        validation_error: str | None = None,
    ) -> None:
        """Store a raw commit record verbatim.

        Args:
            commit_id: The computed commit ID.
            payload: The raw commit payload (stored as-is).
            validation_error: Error message if validation failed, None if valid.
        """
        self._raw_commits[commit_id] = {
            "commit_id": commit_id,
            "payload": copy.deepcopy(payload),  # Store a deep copy
            "validation_error": validation_error,
        }

    def get_raw_commit(self, commit_id: str) -> dict | None:
        """Retrieve a raw commit record by ID."""
        return self._raw_commits.get(commit_id)

    def store_effective_state(
        self,
        episode_id: str,
        commit_id: str,
        state: dict,
    ) -> None:
        """Store the effective state for an episode after a commit.

        Args:
            episode_id: The episode identifier.
            commit_id: The commit that produced this state.
            state: The effective state dict.
        """
        state_copy = copy.deepcopy(state)
        self._effective_states[episode_id] = state_copy
        self._effective_at_commit[commit_id] = state_copy
        self._latest_commit[episode_id] = commit_id

    def get_effective_state(self, episode_id: str) -> dict | None:
        """Get the current effective state for an episode."""
        return self._effective_states.get(episode_id)

    def get_effective_state_at(self, commit_id: str) -> dict | None:
        """Get the effective state as of a specific commit."""
        return self._effective_at_commit.get(commit_id)

    def get_latest_commit_id(self, episode_id: str) -> str | None:
        """Get the latest commit ID for an episode."""
        return self._latest_commit.get(episode_id)


class CommitProcessor:
    """Process belief commits with validation and state management.

    Handles:
    - Schema validation
    - Target validation (via target_validator callback)
    - Evidence visibility checks (via evidence_visibility_checker callback)
    - Hash chain integrity (parent_commit_id verification)
    - Operation semantics (UPDATE, HOLD, FOLLOW_BASELINE)
    - Fallback behavior for invalid commits
    - Two-layer recording (raw vs effective)
    """

    def __init__(
        self,
        store: CommitStore,
        *,
        target_validator: Callable[[str], bool] | None = None,
        baseline_provider: Callable[[str, str], float] | None = None,
        evidence_visibility_checker: Callable[[str, int], bool] | None = None,
        fallback_operation: str = "HOLD",
    ):
        """Initialize the commit processor.

        Args:
            store: The CommitStore for raw and effective state storage.
            target_validator: Callback to validate target_id (returns True if valid).
            baseline_provider: Callback to get baseline forecast (target_id, as_of) -> prob.
            evidence_visibility_checker: Callback to check evidence visibility (id, as_of) -> bool.
            fallback_operation: Operation to use for invalid commits (default HOLD).
        """
        self._store = store
        self._target_validator = target_validator or (lambda tid: True)
        self._baseline_provider = baseline_provider
        self._evidence_checker = evidence_visibility_checker
        self._fallback_operation = fallback_operation

    def process(self, commit: dict) -> dict:
        """Process a belief commit.

        Args:
            commit: The commit payload dict.

        Returns:
            Dict with:
                accepted: True if commit was valid and applied, False otherwise.
                commit_id: The computed commit ID (always returned, even for invalid).
                error: Error message if not accepted, None otherwise.
        """
        # Always compute commit ID first
        commit_id = compute_commit_id(commit)

        # Track validation errors
        validation_error = None
        accepted = True

        # Step 1: Schema validation
        schema_result = validate_commit_schema(commit)
        if not schema_result["valid"]:
            validation_error = schema_result["error"]
            accepted = False

        # Step 2: Target validation (only if schema valid)
        if accepted and not self._target_validator(commit.get("target_id", "")):
            validation_error = f"Invalid or unregistered target_id: {commit.get('target_id')}"
            accepted = False

        # Step 3: Evidence visibility check (only if still valid)
        if accepted and self._evidence_checker:
            as_of_str = commit.get("as_of", "")
            for ev_id in commit.get("evidence_ids", []):
                # Parse as_of to microseconds for the checker
                try:
                    from ..monitoring_v1.targets import utc_us
                    as_of_us = utc_us(as_of_str)
                except Exception:
                    as_of_us = 0

                if not self._evidence_checker(ev_id, as_of_us):
                    validation_error = f"Evidence not visible at as_of time: {ev_id}"
                    accepted = False
                    break

        # Step 4: Hash chain integrity (only if still valid)
        if accepted:
            episode_id = commit.get("episode_id")
            parent_commit_id = commit.get("parent_commit_id")
            latest_id = self._store.get_latest_commit_id(episode_id)

            if parent_commit_id is None:
                # First commit in episode - OK if no prior commits
                if latest_id is not None:
                    validation_error = f"Chain error: parent_commit_id is null but episode already has commits (latest: {latest_id})"
                    accepted = False
            else:
                # Non-first commit - parent must match latest
                if parent_commit_id != latest_id:
                    validation_error = f"Chain mismatch: declared parent {parent_commit_id} != actual latest {latest_id}"
                    accepted = False

        # Store raw commit verbatim (always, even if invalid)
        self._store.store_raw_commit(
            commit_id,
            commit,
            validation_error=validation_error,
        )

        # Compute and store effective state
        episode_id = commit.get("episode_id")
        effective_state = self._compute_effective_state(commit, accepted)
        self._store.store_effective_state(episode_id, commit_id, effective_state)

        return {
            "accepted": accepted,
            "commit_id": commit_id,
            "error": validation_error,
        }

    def _compute_effective_state(self, commit: dict, accepted: bool) -> dict:
        """Compute the effective state after processing a commit.

        For invalid commits, uses fallback behavior (HOLD from parent).
        For HOLD, carries forward parent state.
        For FOLLOW_BASELINE, uses baseline provider.
        For UPDATE, applies the updates.

        Args:
            commit: The commit payload.
            accepted: Whether the commit was accepted.

        Returns:
            The effective state dict.
        """
        episode_id = commit.get("episode_id")

        # Get parent state (if any)
        parent_state = self._store.get_effective_state(episode_id)
        if parent_state is None:
            parent_state = {"facts": {}, "forecasts": {}}

        # Start with copy of parent state
        effective = copy.deepcopy(parent_state)

        # Determine operation (fallback for invalid commits)
        if accepted:
            operation = commit.get("operation", "UPDATE")
        else:
            operation = self._fallback_operation

        # Apply operation semantics
        if operation == "HOLD":
            # HOLD: keep parent state unchanged
            pass
        elif operation == "FOLLOW_BASELINE":
            # FOLLOW_BASELINE: use baseline forecasts instead of model's
            if self._baseline_provider:
                as_of = commit.get("as_of", "")
                # For each forecast target, get baseline
                for update in commit.get("forecast_updates", []):
                    target_id = update.get("target_id")
                    if target_id:
                        baseline_prob = self._baseline_provider(target_id, as_of)
                        effective["forecasts"][target_id] = baseline_prob
            # Facts are still applied normally
            if accepted:
                self._apply_fact_updates(effective, commit.get("fact_updates", []))
        elif operation == "UPDATE":
            # UPDATE: apply all updates
            if accepted:
                self._apply_fact_updates(effective, commit.get("fact_updates", []))
                self._apply_forecast_updates(effective, commit.get("forecast_updates", []))

        return effective

    def _apply_fact_updates(self, state: dict, updates: list[dict]) -> None:
        """Apply fact updates to the state."""
        for update in updates:
            slot = update.get("slot")
            if slot:
                state["facts"][slot] = {
                    "operation": update.get("operation"),
                    "support_status": update.get("support_status"),
                    "value": update.get("value"),
                    "source_ids": update.get("source_ids", []),
                }

    def _apply_forecast_updates(self, state: dict, updates: list[dict]) -> None:
        """Apply forecast updates to the state."""
        for update in updates:
            target_id = update.get("target_id")
            prob = update.get("event_probability")
            if target_id is not None and prob is not None:
                state["forecasts"][target_id] = prob
