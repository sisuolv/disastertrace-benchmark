from pathlib import Path

from disastertrace.evidence import EvidenceGate, GateMode
from disastertrace.models import Episode


def load_episode() -> Episode:
    return Episode.model_validate_json(Path("examples/episode.json").read_text())


def test_strict_gate_releases_only_as_of_time() -> None:
    episode = load_episode()
    gate = EvidenceGate(GateMode.STRICT)
    assert gate.legal_ids(episode, episode.checkpoints[0]) == frozenset({"ADV_01"})
    assert gate.legal_ids(episode, episode.checkpoints[1]) == frozenset({"ADV_01", "ADV_02"})
