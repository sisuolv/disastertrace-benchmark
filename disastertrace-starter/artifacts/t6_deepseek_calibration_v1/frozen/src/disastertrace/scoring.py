from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import BeliefUpdate, CheckpointCommit, ObligationSheet, StateLedger


@dataclass(frozen=True)
class AuditVector:
    evidence_legal: float
    grounding_correct: float
    revision_correct: float
    preservation_correct: float
    unknown_preservation: float
    action_admissible: float
    action_timing_correct: float
    model_owned_commit: float
    commit_used: float | None = None

    def strict_score(self) -> float | None:
        values = [
            self.evidence_legal,
            self.grounding_correct,
            self.revision_correct,
            self.preservation_correct,
            self.unknown_preservation,
            self.action_admissible,
            self.action_timing_correct,
            self.model_owned_commit,
        ]
        if self.commit_used is not None:
            values.append(self.commit_used)
        return float(all(value >= 1.0 for value in values))


@dataclass(frozen=True)
class TransitionScore:
    transition_id: str
    audit: AuditVector
    strict_pass: float | None
    diagnostics: dict[str, Any]


def _find_update(commit: CheckpointCommit, slot: str) -> BeliefUpdate | None:
    matches = [update for update in commit.belief_updates if update.slot == slot]
    if len(matches) > 1:
        raise ValueError(f"model emitted multiple updates for slot {slot!r}")
    return matches[0] if matches else None


def score_transition(
    *,
    obligation: ObligationSheet,
    commit: CheckpointCommit,
    previous_state: StateLedger,
    current_state: StateLedger,
    delivered_ids: set[str],
    checkpoint_time: datetime,
    model_owned_commit: bool = True,
    commit_used: float | None = None,
) -> TransitionScore:
    used_ids = {ref.artifact_id for ref in commit.evidence_used}
    for update in commit.belief_updates:
        used_ids.update(ref.artifact_id for ref in update.evidence)
    used_ids.update(ref.artifact_id for ref in commit.action.rationale_evidence)
    illegal = used_ids - delivered_ids
    evidence_legal = float(not illegal)

    grounding_groups = obligation.required_evidence_any_of
    grounding_correct = float(
        all(any(candidate in used_ids for candidate in group) for group in grounding_groups)
    )

    missing_updates: list[str] = []
    wrong_updates: list[str] = []
    for expected in obligation.required_updates:
        actual = _find_update(commit, expected.slot)
        if actual is None:
            missing_updates.append(expected.slot)
            continue
        if actual.operation != expected.operation or (
            expected.new_value is not None and actual.new_value != expected.new_value
        ):
            wrong_updates.append(expected.slot)
    revision_correct = float(not missing_updates and not wrong_updates)

    changed_preserved: list[str] = []
    for slot in obligation.must_preserve:
        before = previous_state.slots.get(slot)
        after = current_state.slots.get(slot)
        if before != after:
            changed_preserved.append(slot)
    preservation_correct = float(not changed_preserved)

    closed_unknown: list[str] = []
    for slot in obligation.must_remain_unknown:
        after = current_state.slots.get(slot)
        if after is not None and not after.unknown:
            closed_unknown.append(slot)
    unknown_preservation = float(not closed_unknown)

    action_name = commit.action.action
    action_admissible = float(
        (not obligation.admissible_actions or action_name in obligation.admissible_actions)
        and action_name not in obligation.forbidden_actions
    )
    timing = True
    if obligation.earliest_admissible_time and checkpoint_time < obligation.earliest_admissible_time:
        timing = False
    if obligation.latest_safe_time and checkpoint_time > obligation.latest_safe_time:
        timing = False
    action_timing_correct = float(timing)

    span_ids = {ref.span_id for ref in commit.evidence_used if ref.span_id}
    region_ids = {ref.region_id for ref in commit.evidence_used if ref.region_id}
    if obligation.required_span_ids:
        grounding_correct *= float(set(obligation.required_span_ids).issubset(span_ids))
    if obligation.required_region_ids:
        grounding_correct *= float(set(obligation.required_region_ids).issubset(region_ids))

    audit = AuditVector(
        evidence_legal=evidence_legal,
        grounding_correct=grounding_correct,
        revision_correct=revision_correct,
        preservation_correct=preservation_correct,
        unknown_preservation=unknown_preservation,
        action_admissible=action_admissible,
        action_timing_correct=action_timing_correct,
        model_owned_commit=float(model_owned_commit),
        commit_used=commit_used,
    )
    return TransitionScore(
        transition_id=obligation.transition_id,
        audit=audit,
        strict_pass=audit.strict_score(),
        diagnostics={
            "illegal_evidence_ids": sorted(illegal),
            "missing_updates": missing_updates,
            "wrong_updates": wrong_updates,
            "changed_must_preserve": changed_preserved,
            "closed_unknown": closed_unknown,
        },
    )


def paired_commit_metrics(
    *,
    actual_score: float,
    masked_score: float,
    oracle_score: float,
    edited_target_changed_correctly: bool,
    edited_stable_frontier_changed: bool,
) -> dict[str, float]:
    return {
        "commit_utility": actual_score - masked_score,
        "oracle_recovery": oracle_score - actual_score,
        "edited_carrier_selectivity": float(
            edited_target_changed_correctly and not edited_stable_frontier_changed
        ),
    }
