from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AvailabilityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    GIS = "gis"
    TABLE = "table"
    OTHER = "other"


class BeliefOperation(str, Enum):
    ADD = "ADD"
    KEEP = "KEEP"
    UPDATE = "UPDATE"
    RETRACT = "RETRACT"
    KEEP_UNKNOWN = "KEEP_UNKNOWN"


class ActionOperation(str, Enum):
    HOLD = "HOLD"
    ESCALATE = "ESCALATE"
    DOWNGRADE = "DOWNGRADE"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"


def _require_aware(value: datetime | None, field: str) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


class TimeRange(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_range(self) -> "TimeRange":
        _require_aware(self.start, "start")
        _require_aware(self.end, "end")
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self


class Artifact(BaseModel):
    artifact_id: str
    episode_id: str
    kind: str
    modality: Modality
    path: str
    sha256: str | None = None
    issued_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    effective_at: datetime | None = None
    available_at: TimeRange
    availability_grade: AvailabilityGrade
    version_parent: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_times(self) -> "Artifact":
        for field in ("issued_at", "valid_from", "valid_to", "effective_at"):
            _require_aware(getattr(self, field), field)
        return self

    def local_path(self, root: Path) -> Path:
        candidate = (root / self.path).resolve()
        root_resolved = root.resolve()
        if root_resolved not in candidate.parents and candidate != root_resolved:
            raise ValueError(f"artifact path escapes data root: {self.path}")
        return candidate


class Checkpoint(BaseModel):
    checkpoint_id: str
    at: datetime
    released_artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time(self) -> "Checkpoint":
        _require_aware(self.at, "at")
        return self


class Episode(BaseModel):
    episode_id: str
    storm_id: str
    subject_id: str
    artifacts: list[Artifact]
    checkpoints: list[Checkpoint]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_episode(self) -> "Episode":
        artifact_ids = [a.artifact_id for a in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact_id values must be unique")
        checkpoint_ids = [c.checkpoint_id for c in self.checkpoints]
        if len(checkpoint_ids) != len(set(checkpoint_ids)):
            raise ValueError("checkpoint_id values must be unique")
        if self.checkpoints != sorted(self.checkpoints, key=lambda c: c.at):
            raise ValueError("checkpoints must be sorted by time")
        known = set(artifact_ids)
        for checkpoint in self.checkpoints:
            missing = set(checkpoint.released_artifact_ids) - known
            if missing:
                raise ValueError(
                    f"checkpoint {checkpoint.checkpoint_id} references unknown artifacts: {missing}"
                )
        return self

    def artifact_map(self) -> dict[str, Artifact]:
        return {a.artifact_id: a for a in self.artifacts}


class EvidenceReference(BaseModel):
    artifact_id: str
    span_id: str | None = None
    region_id: str | None = None
    role: str = "supports"


class BeliefUpdate(BaseModel):
    slot: str
    operation: BeliefOperation
    old_value: Any | None = None
    new_value: Any | None = None
    uncertainty: str | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_values(self) -> "BeliefUpdate":
        if self.operation in {BeliefOperation.ADD, BeliefOperation.UPDATE} and self.new_value is None:
            raise ValueError(f"{self.operation} requires new_value")
        if self.operation == BeliefOperation.KEEP_UNKNOWN and self.new_value is not None:
            raise ValueError("KEEP_UNKNOWN must not provide new_value")
        return self


class ActionCommit(BaseModel):
    operation: ActionOperation
    action: str
    rationale_evidence: list[EvidenceReference] = Field(default_factory=list)
    requested_evidence: list[str] = Field(default_factory=list)


class CheckpointCommit(BaseModel):
    schema_version: str = "checkpoint_commit_v1"
    checkpoint_id: str
    evidence_used: list[EvidenceReference] = Field(default_factory=list)
    belief_updates: list[BeliefUpdate] = Field(default_factory=list)
    action: ActionCommit
    unresolved_questions: list[str] = Field(default_factory=list)


class SlotState(BaseModel):
    value: Any | None = None
    unknown: bool = True
    uncertainty: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class StateLedger(BaseModel):
    slots: dict[str, SlotState] = Field(default_factory=dict)

    def apply(self, commit: CheckpointCommit, checkpoint_time: datetime) -> "StateLedger":
        next_state = self.model_copy(deep=True)
        for update in commit.belief_updates:
            current = next_state.slots.get(update.slot, SlotState())
            if update.operation == BeliefOperation.KEEP:
                continue
            if update.operation in {BeliefOperation.RETRACT, BeliefOperation.KEEP_UNKNOWN}:
                next_state.slots[update.slot] = SlotState(
                    value=None,
                    unknown=True,
                    uncertainty=update.uncertainty,
                    evidence_ids=[e.artifact_id for e in update.evidence],
                    updated_at=checkpoint_time,
                )
            else:
                next_state.slots[update.slot] = SlotState(
                    value=update.new_value,
                    unknown=False,
                    uncertainty=update.uncertainty,
                    evidence_ids=[e.artifact_id for e in update.evidence],
                    updated_at=checkpoint_time,
                )
            if update.old_value is not None and not current.unknown and current.value != update.old_value:
                raise ValueError(
                    f"old_value mismatch for {update.slot}: commit={update.old_value!r}, "
                    f"ledger={current.value!r}"
                )
        return next_state


class ExpectedUpdate(BaseModel):
    slot: str
    operation: BeliefOperation
    new_value: Any | None = None


class ObligationSheet(BaseModel):
    transition_id: str
    checkpoint_id: str
    required_evidence_any_of: list[list[str]] = Field(default_factory=list)
    required_updates: list[ExpectedUpdate] = Field(default_factory=list)
    must_preserve: list[str] = Field(default_factory=list)
    must_remain_unknown: list[str] = Field(default_factory=list)
    admissible_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    earliest_admissible_time: datetime | None = None
    latest_safe_time: datetime | None = None
    required_span_ids: list[str] = Field(default_factory=list)
    required_region_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_times(self) -> "ObligationSheet":
        _require_aware(self.earliest_admissible_time, "earliest_admissible_time")
        _require_aware(self.latest_safe_time, "latest_safe_time")
        return self
