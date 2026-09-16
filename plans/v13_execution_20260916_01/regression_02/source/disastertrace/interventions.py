from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .models import Checkpoint, Episode


class EvidenceIntervention(Protocol):
    name: str

    def apply(
        self,
        *,
        episode: Episode,
        checkpoint: Checkpoint,
        checkpoint_index: int,
        legal_ids: frozenset[str],
    ) -> frozenset[str]: ...


@dataclass(frozen=True)
class IdentityIntervention:
    name: str = "natural"

    def apply(self, *, episode, checkpoint, checkpoint_index, legal_ids):
        del episode, checkpoint, checkpoint_index
        return legal_ids


@dataclass(frozen=True)
class WithholdArtifacts:
    artifact_ids: frozenset[str]
    until_checkpoint_index: int | None = None
    name: str = "withhold"

    def apply(self, *, episode, checkpoint, checkpoint_index, legal_ids):
        del episode, checkpoint
        if self.until_checkpoint_index is not None and checkpoint_index >= self.until_checkpoint_index:
            return legal_ids
        return frozenset(x for x in legal_ids if x not in self.artifact_ids)


@dataclass(frozen=True)
class StaleVersionReplay:
    """Replace selected current versions with their legal parent versions."""

    artifact_ids: frozenset[str]
    name: str = "stale_version"

    def apply(self, *, episode, checkpoint, checkpoint_index, legal_ids):
        del checkpoint, checkpoint_index
        artifact_map = episode.artifact_map()
        output = set(legal_ids)
        for artifact_id in self.artifact_ids:
            if artifact_id not in output:
                continue
            parent = artifact_map[artifact_id].version_parent
            output.remove(artifact_id)
            if parent and parent in legal_ids:
                output.add(parent)
        return frozenset(output)


@dataclass(frozen=True)
class CompositeIntervention:
    interventions: tuple[EvidenceIntervention, ...] = field(default_factory=tuple)
    name: str = "composite"

    def apply(self, *, episode, checkpoint, checkpoint_index, legal_ids):
        current = legal_ids
        for intervention in self.interventions:
            current = intervention.apply(
                episode=episode,
                checkpoint=checkpoint,
                checkpoint_index=checkpoint_index,
                legal_ids=current,
            )
        return current
