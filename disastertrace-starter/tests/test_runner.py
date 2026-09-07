from pathlib import Path

import pytest

from disastertrace.adapters import ScriptedAdapter
from disastertrace.evidence import EvidenceGate
from disastertrace.models import (
    ActionCommit,
    ActionOperation,
    BeliefOperation,
    BeliefUpdate,
    CheckpointCommit,
    Episode,
    EvidenceReference,
)
from disastertrace.policies import structured_state_policy
from disastertrace.runner import EpisodeRunner


@pytest.mark.asyncio
async def test_runner_uses_fresh_requests_and_explicit_carrier(tmp_path: Path) -> None:
    episode = Episode.model_validate_json(Path("examples/episode.json").read_text())
    commits = {
        "CP_01": CheckpointCommit(
            checkpoint_id="CP_01",
            belief_updates=[
                BeliefUpdate(slot="warning_status", operation=BeliefOperation.KEEP_UNKNOWN)
            ],
            action=ActionCommit(operation=ActionOperation.HOLD, action="monitor"),
        ),
        "CP_02": CheckpointCommit(
            checkpoint_id="CP_02",
            evidence_used=[EvidenceReference(artifact_id="ADV_02")],
            belief_updates=[
                BeliefUpdate(
                    slot="warning_status",
                    operation=BeliefOperation.ADD,
                    new_value="tropical_storm_warning",
                    evidence=[EvidenceReference(artifact_id="ADV_02")],
                )
            ],
            action=ActionCommit(operation=ActionOperation.ESCALATE, action="prepare"),
        ),
    }
    adapter = ScriptedAdapter(commits)
    runner = EpisodeRunner(
        adapter=adapter,
        gate=EvidenceGate(),
        policy=structured_state_policy(),
        data_root=Path("examples/data"),
        output_root=tmp_path,
        model_name="fixture",
    )
    trace = await runner.run(episode=episode, run_id="test")
    assert len(trace.checkpoints) == 2
    assert len(adapter.requests) == 2
    assert "Previous model-authored state carrier:\nNONE" not in adapter.requests[1].user_prompt
    assert adapter.requests[0].metadata["selected_artifact_ids"] == ["ADV_01"]
    assert adapter.requests[1].metadata["selected_artifact_ids"] == ["ADV_02"]
    assert (tmp_path / "test/fixture/B3_structured_state/DEMO_STORM_PORT_BLUE/trajectory.json").exists()
