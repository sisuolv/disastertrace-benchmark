from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .adapters import ModelRequest
from .evidence import EvidenceView
from .models import Artifact, Checkpoint, Episode, StateLedger


class PromptPolicy(Protocol):
    name: str

    def build_request(
        self,
        *,
        episode: Episode,
        checkpoint: Checkpoint,
        view: EvidenceView,
        previous_state: StateLedger | None,
        data_root: Path,
    ) -> ModelRequest: ...


def _current_versions(artifacts: list[Artifact]) -> list[Artifact]:
    superseded = {a.version_parent for a in artifacts if a.version_parent}
    return [a for a in artifacts if a.artifact_id not in superseded]


def _render_artifacts(artifacts: list[Artifact], data_root: Path) -> tuple[str, tuple[Path, ...]]:
    text_blocks: list[str] = []
    images: list[Path] = []
    for artifact in sorted(artifacts, key=lambda a: (a.available_at.end, a.artifact_id)):
        path = artifact.local_path(data_root)
        header = (
            f"ARTIFACT {artifact.artifact_id}\n"
            f"kind={artifact.kind}; issued_at={artifact.issued_at}; "
            f"available_at={artifact.available_at.model_dump_json()}\n"
        )
        if artifact.modality.value == "image":
            images.append(path)
            text_blocks.append(header + f"[image attached: {artifact.artifact_id}]")
        else:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            text_blocks.append(header + text)
    return "\n\n".join(text_blocks), tuple(images)


@dataclass(frozen=True)
class ConfigurablePolicy:
    name: str
    history_mode: str = "new"  # new | all
    carry_state: bool = True
    version_filter: bool = False

    def build_request(self, *, episode, checkpoint, view, previous_state, data_root):
        artifact_map = episode.artifact_map()
        selected_ids = (
            view.newly_delivered_ids if self.history_mode == "new" else view.delivered_ids
        )
        artifacts = [artifact_map[x] for x in selected_ids]
        if self.version_filter:
            artifacts = _current_versions(artifacts)
        actual_selected_ids = {artifact.artifact_id for artifact in artifacts}
        artifact_text, images = _render_artifacts(artifacts, data_root)
        state_text = "NONE"
        if self.carry_state and previous_state is not None:
            state_text = previous_state.model_dump_json(indent=2)
        user_prompt = f"""Current checkpoint: {checkpoint.checkpoint_id} at {checkpoint.at.isoformat()}

Previous model-authored state carrier:
{state_text}

Evidence delivered at this checkpoint under policy={self.name}:
{artifact_text or '[no newly delivered evidence]'}

Submit the minimal evidence-grounded belief revision and current action. Do not infer a negative fact merely because evidence is absent. Preserve unaffected state slots.
"""
        return ModelRequest(
            system_prompt=(
                "You are participating in an auditable disaster-operations replay. "
                "Use only the evidence in this request and the explicit state carrier."
            ),
            user_prompt=user_prompt,
            image_paths=images,
            metadata={
                "episode_id": episode.episode_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "policy": self.name,
                "selected_artifact_ids": sorted(actual_selected_ids),
            },
        )


def snapshot_policy() -> ConfigurablePolicy:
    return ConfigurablePolicy(name="B0_snapshot", history_mode="new", carry_state=False)


def full_history_policy() -> ConfigurablePolicy:
    return ConfigurablePolicy(name="B1_full_legal_history", history_mode="all", carry_state=False)


def asof_version_policy() -> ConfigurablePolicy:
    return ConfigurablePolicy(
        name="B2_asof_version", history_mode="all", carry_state=False, version_filter=True
    )


def structured_state_policy() -> ConfigurablePolicy:
    return ConfigurablePolicy(name="B3_structured_state", history_mode="new", carry_state=True)
