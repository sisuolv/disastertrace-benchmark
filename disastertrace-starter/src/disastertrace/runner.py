from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import ModelAdapter
from .evidence import EvidenceGate, EvidenceView
from .interventions import EvidenceIntervention, IdentityIntervention
from .models import CheckpointCommit, Episode, StateLedger
from .policies import PromptPolicy


@dataclass(frozen=True)
class CarrierTransform:
    mode: str = "actual"  # actual | masked | oracle | edited
    target_checkpoint_id: str | None = None
    edit_slot: str | None = None
    edit_value: Any | None = None

    def apply(
        self,
        *,
        checkpoint_id: str,
        actual: StateLedger | None,
        oracle: StateLedger | None,
    ) -> StateLedger | None:
        if self.target_checkpoint_id is not None and checkpoint_id != self.target_checkpoint_id:
            return actual
        if self.mode == "actual":
            return actual
        if self.mode == "masked":
            return None
        if self.mode == "oracle":
            if oracle is None:
                raise ValueError("oracle carrier requested but not provided")
            return oracle.model_copy(deep=True)
        if self.mode == "edited":
            if actual is None or self.edit_slot is None:
                raise ValueError("edited carrier requires actual state and edit_slot")
            edited = actual.model_copy(deep=True)
            slot = edited.slots.get(self.edit_slot)
            if slot is None:
                raise ValueError(f"cannot edit missing slot {self.edit_slot!r}")
            slot.value = self.edit_value
            slot.unknown = self.edit_value is None
            return edited
        raise ValueError(f"unknown carrier mode: {self.mode}")


@dataclass
class CheckpointTrace:
    checkpoint_id: str
    checkpoint_time: str
    legal_artifact_ids: list[str]
    delivered_artifact_ids: list[str]
    newly_delivered_artifact_ids: list[str]
    carrier_mode: str
    request_hash: str
    raw_response: str
    commit: dict[str, Any]
    state_after: dict[str, Any]
    usage: dict[str, Any]


@dataclass
class EpisodeTrace:
    schema_version: str
    run_id: str
    episode_id: str
    model_name: str
    policy_name: str
    intervention_name: str
    carrier_mode: str
    started_at: str
    checkpoints: list[CheckpointTrace] = field(default_factory=list)


class EpisodeRunner:
    def __init__(
        self,
        *,
        adapter: ModelAdapter,
        gate: EvidenceGate,
        policy: PromptPolicy,
        data_root: Path,
        output_root: Path,
        model_name: str,
    ) -> None:
        self.adapter = adapter
        self.gate = gate
        self.policy = policy
        self.data_root = data_root
        self.output_root = output_root
        self.model_name = model_name

    @staticmethod
    def _request_hash(system: str, user: str, image_paths: tuple[Path, ...]) -> str:
        digest = hashlib.sha256()
        digest.update(system.encode())
        digest.update(user.encode())
        for path in image_paths:
            digest.update(path.read_bytes())
        return digest.hexdigest()

    async def run(
        self,
        *,
        episode: Episode,
        run_id: str,
        intervention: EvidenceIntervention | None = None,
        carrier_transform: CarrierTransform = CarrierTransform(),
        oracle_carriers: dict[str, StateLedger] | None = None,
    ) -> EpisodeTrace:
        intervention = intervention or IdentityIntervention()
        oracle_carriers = oracle_carriers or {}
        trace = EpisodeTrace(
            schema_version="episode_trace_v1",
            run_id=run_id,
            episode_id=episode.episode_id,
            model_name=self.model_name,
            policy_name=self.policy.name,
            intervention_name=intervention.name,
            carrier_mode=carrier_transform.mode,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        state = StateLedger()
        previous_delivered: frozenset[str] = frozenset()

        for index, checkpoint in enumerate(episode.checkpoints):
            legal_ids = self.gate.legal_ids(episode, checkpoint)
            delivered_ids = intervention.apply(
                episode=episode,
                checkpoint=checkpoint,
                checkpoint_index=index,
                legal_ids=legal_ids,
            )
            if not delivered_ids.issubset(legal_ids):
                raise ValueError("intervention delivered evidence that was not legally available")
            view = EvidenceView(
                legal_ids=legal_ids,
                delivered_ids=delivered_ids,
                newly_delivered_ids=delivered_ids - previous_delivered,
            )
            carrier = carrier_transform.apply(
                checkpoint_id=checkpoint.checkpoint_id,
                actual=state,
                oracle=oracle_carriers.get(checkpoint.checkpoint_id),
            )

            # Fresh session by construction: build one request from current evidence + explicit carrier.
            request = self.policy.build_request(
                episode=episode,
                checkpoint=checkpoint,
                view=view,
                previous_state=carrier,
                data_root=self.data_root,
            )
            response = await self.adapter.generate(request)
            if response.commit.checkpoint_id != checkpoint.checkpoint_id:
                raise ValueError("model commit checkpoint_id does not match current checkpoint")
            # Stateful policies evolve from the exact carrier shown to the model.
            # Snapshot/full-history policies start from an empty state at every checkpoint.
            carry_state = bool(getattr(self.policy, "carry_state", True))
            transition_base = (carrier or StateLedger()) if carry_state else StateLedger()
            state = transition_base.apply(response.commit, checkpoint.at)
            request_hash = self._request_hash(
                request.system_prompt, request.user_prompt, request.image_paths
            )
            trace.checkpoints.append(
                CheckpointTrace(
                    checkpoint_id=checkpoint.checkpoint_id,
                    checkpoint_time=checkpoint.at.isoformat(),
                    legal_artifact_ids=sorted(legal_ids),
                    delivered_artifact_ids=sorted(delivered_ids),
                    newly_delivered_artifact_ids=sorted(view.newly_delivered_ids),
                    carrier_mode=carrier_transform.mode,
                    request_hash=request_hash,
                    raw_response=response.raw_text,
                    commit=response.commit.model_dump(mode="json"),
                    state_after=state.model_dump(mode="json"),
                    usage=response.usage,
                )
            )
            previous_delivered = delivered_ids

        out_dir = self.output_root / run_id / self.model_name / self.policy.name / episode.episode_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "trajectory.json").write_text(
            json.dumps(
                {
                    **{k: v for k, v in trace.__dict__.items() if k != "checkpoints"},
                    "checkpoints": [x.__dict__ for x in trace.checkpoints],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return trace
