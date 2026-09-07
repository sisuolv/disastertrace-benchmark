from pathlib import Path

from disastertrace.evidence import EvidenceGate
from disastertrace.interventions import StaleVersionReplay, WithholdArtifacts
from disastertrace.models import Episode


def load_episode() -> Episode:
    return Episode.model_validate_json(Path("examples/episode.json").read_text())


def test_release_delay_hides_then_releases() -> None:
    episode = load_episode()
    gate = EvidenceGate()
    intervention = WithholdArtifacts(frozenset({"ADV_02"}), until_checkpoint_index=2)
    cp = episode.checkpoints[1]
    legal = gate.legal_ids(episode, cp)
    delivered = intervention.apply(
        episode=episode, checkpoint=cp, checkpoint_index=1, legal_ids=legal
    )
    assert delivered == frozenset({"ADV_01"})


def test_stale_version_replaces_current_with_parent() -> None:
    episode = load_episode()
    gate = EvidenceGate()
    cp = episode.checkpoints[1]
    legal = gate.legal_ids(episode, cp)
    delivered = StaleVersionReplay(frozenset({"ADV_02"})).apply(
        episode=episode, checkpoint=cp, checkpoint_index=1, legal_ids=legal
    )
    assert delivered == frozenset({"ADV_01"})
