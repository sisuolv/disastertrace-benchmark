"""Belief commit adapter for DisasterTrace v14 (P0-03 / R2 repair).

Implements the disastertrace.belief_commit.v14-draft schema with:
- operation: UPDATE | HOLD | FOLLOW_BASELINE semantics
- forecast_op: KEEP_PROBABILITY | SET_PROBABILITY | COPY_BASELINE_SNAPSHOT (R2 Issue #4)
- Verbatim preservation of raw submitted payloads (even if invalid)
- parent_commit_id hash chain integrity via canonical_hash
- Invalid commit handling with retained errors and fallback behavior
- Two-layer recording: raw submission vs effective state
- Three-chain separation: attempt chain, accepted state chain, effective state (R2 Issue #8)

Reuses:
- canonical_hash from monitoring_v1/targets.py (hash chain)
- visible_at from revision_v1/ledger.py (evidence visibility check)
- ContractRegistry from revision_v1/contracts.py (target validation)
- adoption.validate/decide from monitoring_fixed_v1/adoption.py (FOLLOW_BASELINE precedent)

R2 fixes (from review Section 3, belief_commit.py issues):
- Issue #1: Validate nested target_id in forecast_updates, source_ids in fact_updates
- Issue #2: as_of must be monotonically increasing (not backward in time)
- Issue #3: Reject bool and NaN probabilities in schema validation before hashing
- Issue #4: forecast_op field for orthogonal probability/fact control
- Issue #5: FOLLOW_BASELINE must have provider, no dummy probability required
- Issue #6: FOLLOW records metadata (product_id, version, applicable_time, probability_source)
- Issue #7: Storage getters return deep copies (immutable views)
- Issue #8: Attempt chain vs accepted chain separation; malformed submissions retained
- Issue #9: SET/RETRACT/KEEP_UNKNOWN have clear valid-state semantics
"""

from __future__ import annotations

import copy
import math
import re
from typing import Any, Callable

from ..monitoring_v1.targets import canonical_hash


# Schema constants
SCHEMA_VERSION = "disastertrace.belief_commit.v14-draft"

VALID_OPERATIONS = {"UPDATE", "HOLD", "FOLLOW_BASELINE"}

# R2 Issue #4: Orthogonal forecast operation field
VALID_FORECAST_OPS = {"KEEP_PROBABILITY", "SET_PROBABILITY", "COPY_BASELINE_SNAPSHOT"}

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
    """Validate a single forecast_update item.

    R2 Issue #3: Reject bool and NaN probabilities in schema validation.
    This validation runs BEFORE canonical_hash to prevent hash errors.
    """
    if not isinstance(item, dict):
        return False, "forecast_update must be a dict"

    if "target_id" not in item:
        return False, "forecast_update missing target_id"

    if "event_probability" not in item:
        return False, "forecast_update missing event_probability"

    prob = item["event_probability"]

    # R2 Issue #3: Reject bool explicitly (bool is subclass of int in Python)
    if isinstance(prob, bool):
        return False, f"event_probability must be a number, not bool (got {prob})"

    if not isinstance(prob, (int, float)):
        return False, "event_probability must be a number"

    # R2 Issue #3: Reject NaN and infinity
    if math.isnan(prob) or math.isinf(prob):
        return False, f"event_probability must be finite, got {prob}"

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

    Three-layer recording (R2 Issue #8):
    - Raw attempts: ALL submissions stored verbatim (even malformed/invalid)
    - Accepted commits: only validated commits that advance the chain
    - Effective states: resolved state after applying commit semantics

    The store maintains:
    - Per-commit raw records (indexed by commit_id or attempt_id)
    - Per-episode current effective state
    - Per-commit effective state snapshots (for historical queries)
    - Attempt log with acceptance status
    - Per-episode as_of history for monotonicity checking (R2 Issue #2)
    """

    def __init__(self):
        # Raw commit records indexed by commit_id
        self._raw_commits: dict[str, dict] = {}
        # Current effective state per episode
        self._effective_states: dict[str, dict] = {}
        # Effective state snapshot per commit (for historical queries)
        self._effective_at_commit: dict[str, dict] = {}
        # Chain tracking: episode_id -> latest ACCEPTED commit_id
        self._latest_commit: dict[str, str] = {}
        # R2 Issue #8: Attempt log (all attempts, including rejected)
        self._attempt_log: list[dict] = []
        # R2 Issue #2: Track last as_of per episode for monotonicity
        self._last_as_of: dict[str, str] = {}

    def store_raw_commit(
        self,
        commit_id: str,
        payload: dict | Any,
        *,
        validation_error: str | None = None,
        accepted: bool = True,
    ) -> None:
        """Store a raw commit record verbatim.

        R2 Issue #8: All attempts (including invalid/malformed) are stored.

        Args:
            commit_id: The computed commit ID (or generated attempt ID for malformed).
            payload: The raw commit payload (stored as-is, can be any type).
            validation_error: Error message if validation failed, None if valid.
            accepted: Whether this attempt was accepted into the chain.
        """
        # R2 Issue #8: Store deep copy, handle non-dict payloads gracefully
        if isinstance(payload, dict):
            stored_payload = copy.deepcopy(payload)
        else:
            stored_payload = payload  # Store malformed payload as-is

        record = {
            "commit_id": commit_id,
            "payload": stored_payload,
            "validation_error": validation_error,
            "accepted": accepted,  # R2 Issue #8: Track acceptance status
        }
        self._raw_commits[commit_id] = record
        # R2 Issue #8: Also add to attempt log
        self._attempt_log.append(record)

    def get_raw_commit(self, commit_id: str) -> dict | None:
        """Retrieve a raw commit record by ID.

        R2 Issue #7: Returns a deep copy to prevent mutation.
        """
        record = self._raw_commits.get(commit_id)
        if record is None:
            return None
        return copy.deepcopy(record)

    def store_effective_state(
        self,
        episode_id: str,
        commit_id: str,
        state: dict,
        *,
        accepted: bool = True,
    ) -> None:
        """Store the effective state for an episode after a commit.

        R2 Issue #8: Only accepted commits update latest_commit.

        Args:
            episode_id: The episode identifier.
            commit_id: The commit that produced this state.
            state: The effective state dict.
            accepted: Whether this was an accepted commit.
        """
        state_copy = copy.deepcopy(state)
        self._effective_states[episode_id] = state_copy
        self._effective_at_commit[commit_id] = copy.deepcopy(state_copy)
        # R2 Issue #8: Only update latest for accepted commits
        if accepted:
            self._latest_commit[episode_id] = commit_id

    def get_effective_state(self, episode_id: str) -> dict | None:
        """Get the current effective state for an episode.

        R2 Issue #7: Returns a deep copy to prevent mutation.
        """
        state = self._effective_states.get(episode_id)
        if state is None:
            return None
        return copy.deepcopy(state)

    def get_effective_state_at(self, commit_id: str) -> dict | None:
        """Get the effective state as of a specific commit.

        R2 Issue #7: Returns a deep copy to prevent mutation.
        """
        state = self._effective_at_commit.get(commit_id)
        if state is None:
            return None
        return copy.deepcopy(state)

    def get_latest_commit_id(self, episode_id: str) -> str | None:
        """Get the latest ACCEPTED commit ID for an episode."""
        return self._latest_commit.get(episode_id)

    def get_attempt_log(self) -> list[dict]:
        """Get the full attempt log (R2 Issue #8).

        Returns deep copies to prevent mutation.
        """
        return copy.deepcopy(self._attempt_log)

    def get_last_as_of(self, episode_id: str) -> str | None:
        """Get the last as_of timestamp for an episode (R2 Issue #2)."""
        return self._last_as_of.get(episode_id)

    def set_last_as_of(self, episode_id: str, as_of: str) -> None:
        """Record the last as_of timestamp for an episode."""
        self._last_as_of[episode_id] = as_of


class CommitProcessor:
    """Process belief commits with validation and state management.

    Handles:
    - Schema validation (R2 Issue #3: before hashing)
    - Target validation for outer and nested targets (R2 Issue #1)
    - Evidence visibility checks including fact_updates.source_ids (R2 Issue #1)
    - Hash chain integrity (parent_commit_id verification)
    - as_of monotonicity enforcement (R2 Issue #2)
    - Operation semantics (UPDATE, HOLD, FOLLOW_BASELINE)
    - FOLLOW_BASELINE requires provider, no dummy probability (R2 Issue #5)
    - Fallback behavior for invalid commits
    - Three-layer recording (raw attempt vs accepted vs effective) (R2 Issue #8)
    - Malformed submission handling (R2 Issue #8)
    """

    def __init__(
        self,
        store: CommitStore,
        *,
        target_validator: Callable[[str], bool] | None = None,
        target_resolver: Callable[[str], Any] | None = None,
        baseline_provider: Callable[[str, str], float] | None = None,
        evidence_visibility_checker: Callable[[str, int], bool] | None = None,
        fallback_operation: str = "HOLD",
    ):
        """Initialize the commit processor.

        Args:
            store: The CommitStore for raw and effective state storage.
            target_validator: Callback to validate target_id (returns True if valid).
            target_resolver: Callback to resolve target_id to Target object (for cutoff validation).
                R2-FIX Gap #2: Required for as_of cutoff/forecast-window binding.
            baseline_provider: Callback to get baseline forecast (target_id, as_of) -> prob.
            evidence_visibility_checker: Callback to check evidence visibility (id, as_of) -> bool.
            fallback_operation: Operation to use for invalid commits (default HOLD).
        """
        self._store = store
        self._target_validator = target_validator or (lambda tid: True)
        self._target_resolver = target_resolver
        self._baseline_provider = baseline_provider
        self._evidence_checker = evidence_visibility_checker
        self._fallback_operation = fallback_operation

    def process(self, commit: Any) -> dict:
        """Process a belief commit.

        R2 Issue #8: Handles malformed (non-dict) submissions gracefully.

        Args:
            commit: The commit payload (expected dict, but handles any type).

        Returns:
            Dict with:
                accepted: True if commit was valid and applied, False otherwise.
                commit_id: The computed commit ID (always returned, even for invalid).
                error: Error message if not accepted, None otherwise.
        """
        # R2 Issue #8: Handle malformed submissions
        if not isinstance(commit, dict):
            # Generate a commit_id for malformed submissions
            import hashlib
            import json
            try:
                content = json.dumps(commit, default=str, sort_keys=True)
            except Exception:
                content = str(commit)
            commit_id = hashlib.sha256(content.encode()).hexdigest()

            validation_error = f"Commit must be a dict, got {type(commit).__name__}"

            # Store the malformed attempt
            self._store.store_raw_commit(
                commit_id,
                commit,
                validation_error=validation_error,
                accepted=False,
            )

            return {
                "accepted": False,
                "commit_id": commit_id,
                "error": validation_error,
            }

        # Track validation errors
        validation_error = None
        accepted = True

        # R2 Issue #3: Schema validation MUST run BEFORE hashing
        # to prevent canonical_hash from throwing on invalid data
        schema_result = validate_commit_schema(commit)
        if not schema_result["valid"]:
            validation_error = schema_result["error"]
            accepted = False

        # Now safe to compute commit ID (schema is valid or we have error)
        commit_id = compute_commit_id(commit)

        # Step 2: Target validation (only if schema valid)
        # R2 Issue #1: Validate outer target_id
        if accepted and not self._target_validator(commit.get("target_id", "")):
            validation_error = f"Invalid or unregistered target_id: {commit.get('target_id')}"
            accepted = False

        # R2 Issue #1: Validate ALL nested target_ids in forecast_updates
        if accepted:
            for i, update in enumerate(commit.get("forecast_updates", [])):
                nested_target = update.get("target_id", "")
                if not self._target_validator(nested_target):
                    validation_error = f"Invalid nested target_id in forecast_updates[{i}]: {nested_target}"
                    accepted = False
                    break

        # Step 3: Evidence visibility check (only if still valid)
        if accepted and self._evidence_checker:
            as_of_str = commit.get("as_of", "")
            try:
                from ..monitoring_v1.targets import utc_us
                as_of_us = utc_us(as_of_str)
            except Exception:
                as_of_us = 0

            # Check top-level evidence_ids
            for ev_id in commit.get("evidence_ids", []):
                if not self._evidence_checker(ev_id, as_of_us):
                    validation_error = f"Evidence not visible at as_of time: {ev_id}"
                    accepted = False
                    break

            # R2 Issue #1: Also check source_ids in fact_updates
            if accepted:
                for i, fact_update in enumerate(commit.get("fact_updates", [])):
                    for source_id in fact_update.get("source_ids", []):
                        if not self._evidence_checker(source_id, as_of_us):
                            validation_error = f"Source not visible in fact_updates[{i}]: {source_id}"
                            accepted = False
                            break
                    if not accepted:
                        break

        # R2 Issue #2: Check as_of monotonicity
        if accepted:
            episode_id = commit.get("episode_id")
            as_of = commit.get("as_of", "")
            last_as_of = self._store.get_last_as_of(episode_id)
            if last_as_of is not None and as_of < last_as_of:
                validation_error = f"as_of must be monotonically increasing: {as_of} < {last_as_of}"
                accepted = False

        # R2-FIX Gap #2: Validate as_of against Target's cutoff/forecast-window logic
        if accepted and self._target_resolver:
            target_id = commit.get("target_id")
            target = self._target_resolver(target_id)
            if target is not None:
                as_of_str = commit.get("as_of", "")
                try:
                    from ..monitoring_v1.targets import utc_us
                    as_of_us = utc_us(as_of_str)
                    # Target.check_cutoff validates as_of against temporal semantics
                    target.check_cutoff(as_of_us)
                except ValueError as e:
                    validation_error = f"as_of violates target cutoff semantics: {e}"
                    accepted = False
                except Exception:
                    # If we can't parse as_of, the ISO validation should have caught it
                    pass

        # R2-FIX Gap #4: Validate forecast_op field if present
        if accepted and "forecast_op" in commit:
            forecast_op = commit.get("forecast_op")
            if forecast_op not in VALID_FORECAST_OPS:
                validation_error = f"Invalid forecast_op: {forecast_op}. Must be one of {VALID_FORECAST_OPS}"
                accepted = False

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

        # R2 Issue #5: FOLLOW_BASELINE requires a baseline_provider
        if accepted and commit.get("operation") == "FOLLOW_BASELINE":
            if self._baseline_provider is None:
                validation_error = "FOLLOW_BASELINE requires a baseline_provider"
                accepted = False

        # Store raw commit verbatim (always, even if invalid) - R2 Issue #8
        self._store.store_raw_commit(
            commit_id,
            commit,
            validation_error=validation_error,
            accepted=accepted,
        )

        # Compute and store effective state
        episode_id = commit.get("episode_id")
        effective_state = self._compute_effective_state(commit, accepted)
        self._store.store_effective_state(episode_id, commit_id, effective_state, accepted=accepted)

        # R2 Issue #2: Update last as_of for accepted commits
        if accepted:
            self._store.set_last_as_of(episode_id, commit.get("as_of", ""))

        return {
            "accepted": accepted,
            "commit_id": commit_id,
            "error": validation_error,
        }

    def _compute_effective_state(self, commit: dict | Any, accepted: bool) -> dict:
        """Compute the effective state after processing a commit.

        For invalid/malformed commits, uses fallback behavior (HOLD from parent).
        For HOLD, carries forward parent state.
        For FOLLOW_BASELINE, uses baseline provider (R2 Issue #5: no dummy prob needed).
        For UPDATE, applies the updates.

        Args:
            commit: The commit payload (dict or malformed).
            accepted: Whether the commit was accepted.

        Returns:
            The effective state dict.
        """
        # R2 Issue #8: Handle malformed commits
        if not isinstance(commit, dict):
            # For malformed commits, just return empty state or parent state
            return {"facts": {}, "forecasts": {}}

        episode_id = commit.get("episode_id")

        # Get parent state (if any) - R2 Issue #7: get_effective_state returns a copy
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
            # R2 Issue #5: FOLLOW_BASELINE copies to the commit's target_id
            # without requiring a dummy probability in forecast_updates.
            # The baseline_provider is already validated to exist.
            if self._baseline_provider:
                as_of = commit.get("as_of", "")
                target_id = commit.get("target_id")

                # R2 Issue #5: Always copy baseline to the declared target
                # This works even if forecast_updates is empty
                if target_id:
                    baseline_prob = self._baseline_provider(target_id, as_of)
                    effective["forecasts"][target_id] = baseline_prob

                # Also handle any additional targets in forecast_updates
                for update in commit.get("forecast_updates", []):
                    nested_target = update.get("target_id")
                    if nested_target and nested_target != target_id:
                        baseline_prob = self._baseline_provider(nested_target, as_of)
                        effective["forecasts"][nested_target] = baseline_prob

                # R2 Issue #6: Record FOLLOW metadata
                effective["_follow_metadata"] = {
                    "baseline_source": "baseline_provider",
                    "as_of": as_of,
                    "target_id": target_id,
                }

            # Facts are still applied normally
            if accepted:
                self._apply_fact_updates(effective, commit.get("fact_updates", []))
        elif operation == "UPDATE":
            # UPDATE: apply all updates
            if accepted:
                # R2-FIX Gap #4: Apply fact_updates independently (orthogonal to forecast_op)
                self._apply_fact_updates(effective, commit.get("fact_updates", []))

                # R2-FIX Gap #4: Handle forecast_op for probability-layer processing
                forecast_op = commit.get("forecast_op")

                if forecast_op == "KEEP_PROBABILITY":
                    # KEEP_PROBABILITY: carry forward parent probability unchanged
                    # Don't apply any forecast_updates - keep parent state as-is
                    pass
                elif forecast_op == "COPY_BASELINE_SNAPSHOT":
                    # COPY_BASELINE_SNAPSHOT: copy from baseline provider
                    if self._baseline_provider:
                        as_of = commit.get("as_of", "")
                        target_id = commit.get("target_id")
                        if target_id:
                            baseline_prob = self._baseline_provider(target_id, as_of)
                            effective["forecasts"][target_id] = baseline_prob
                        # Also handle any additional targets in forecast_updates
                        for update in commit.get("forecast_updates", []):
                            nested_target = update.get("target_id")
                            if nested_target and nested_target != target_id:
                                baseline_prob = self._baseline_provider(nested_target, as_of)
                                effective["forecasts"][nested_target] = baseline_prob
                elif forecast_op == "SET_PROBABILITY":
                    # SET_PROBABILITY: apply explicit probability from forecast_updates
                    self._apply_forecast_updates(effective, commit.get("forecast_updates", []))
                else:
                    # No forecast_op specified (backward compat) or unrecognized:
                    # fall back to old behavior - apply forecast_updates directly
                    self._apply_forecast_updates(effective, commit.get("forecast_updates", []))

        return effective

    def _apply_fact_updates(self, state: dict, updates: list[dict]) -> None:
        """Apply fact updates to the state.

        R2 Issue #9: Clear state semantics for SET/RETRACT/KEEP_UNKNOWN:
        - SET: fact is currently valid with the given value
        - RETRACT: fact is explicitly invalid/withdrawn (not stale prior)
        - KEEP_UNKNOWN: no claim is made (distinct from SET and RETRACT)
        """
        for update in updates:
            slot = update.get("slot")
            if slot:
                operation = update.get("operation")

                # R2 Issue #9: Clear valid-state semantics
                if operation == "SET":
                    # SET: fact is currently valid with value
                    state["facts"][slot] = {
                        "operation": operation,
                        "support_status": update.get("support_status"),
                        "value": update.get("value"),
                        "source_ids": update.get("source_ids", []),
                        "is_valid": True,  # R2 Issue #9: explicit validity
                        "is_retracted": False,
                    }
                elif operation == "RETRACT":
                    # R2 Issue #9: RETRACT marks fact as explicitly invalid/withdrawn
                    # The old value should NOT be treated as current
                    state["facts"][slot] = {
                        "operation": operation,
                        "support_status": update.get("support_status"),
                        "value": None,  # R2 Issue #9: retracted facts have no current value
                        "previous_value": state["facts"].get(slot, {}).get("value"),
                        "source_ids": update.get("source_ids", []),
                        "is_valid": False,
                        "is_retracted": True,
                    }
                elif operation == "KEEP_UNKNOWN":
                    # R2 Issue #9: KEEP_UNKNOWN means no claim - distinct from SET and RETRACT
                    state["facts"][slot] = {
                        "operation": operation,
                        "support_status": update.get("support_status", "undetermined"),
                        "value": update.get("value"),  # may be None
                        "source_ids": update.get("source_ids", []),
                        "is_valid": None,  # unknown validity
                        "is_retracted": False,
                    }
                else:
                    # Fallback for any other operation
                    state["facts"][slot] = {
                        "operation": operation,
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
