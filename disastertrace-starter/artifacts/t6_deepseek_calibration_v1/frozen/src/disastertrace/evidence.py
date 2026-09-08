from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import Artifact, AvailabilityGrade, Checkpoint, Episode


class GateMode(str, Enum):
    STRICT = "strict"
    OPTIMISTIC = "optimistic"


@dataclass(frozen=True)
class EvidenceView:
    legal_ids: frozenset[str]
    delivered_ids: frozenset[str]
    newly_delivered_ids: frozenset[str]


class EvidenceGate:
    """Fail-closed as-of-time gate.

    Strict mode admits an artifact only after the upper bound of its public
    availability interval. Optimistic mode admits it after the lower bound.
    """

    def __init__(
        self,
        mode: GateMode = GateMode.STRICT,
        allowed_grades: frozenset[AvailabilityGrade] = frozenset(
            {AvailabilityGrade.A, AvailabilityGrade.B}
        ),
    ) -> None:
        self.mode = mode
        self.allowed_grades = allowed_grades

    def is_legal(self, artifact: Artifact, checkpoint: Checkpoint) -> bool:
        if artifact.availability_grade not in self.allowed_grades:
            return False
        boundary = (
            artifact.available_at.end
            if self.mode == GateMode.STRICT
            else artifact.available_at.start
        )
        return boundary <= checkpoint.at

    def legal_ids(self, episode: Episode, checkpoint: Checkpoint) -> frozenset[str]:
        return frozenset(
            artifact.artifact_id
            for artifact in episode.artifacts
            if self.is_legal(artifact, checkpoint)
        )
