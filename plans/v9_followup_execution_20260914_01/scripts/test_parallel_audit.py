"""Verify process replay preserves scores, missingness, and corruption rejection."""

import concurrent.futures
import multiprocessing
from pathlib import Path

import pytest
from accelerate_f_audit import replay_journal, scorer_with_replayed_engines
from disastertrace.monitoring_fixed_v1.admission import score_admitted
from disastertrace.monitoring_fixed_v1.contracts import Target
from disastertrace.monitoring_v1.journal import EventJournal
from test_monitoring_admission import complete, setup_engine


@pytest.mark.parametrize("status", ["mature", "provisional"])
def test_spawn_replay_is_identical_to_serial(tmp_path, status):
    paths = {}
    for arm, value in [("a", -5), ("b", -2)]:
        path = tmp_path / (arm + ".jsonl")
        with EventJournal(path) as journal:
            engine, bundle, events = setup_engine(journal=journal)
            engine.run(events + [complete(bundle, value=value)], until=90)
        paths[arm] = path
    outcomes = [{"opportunity_id": "o", "value": -6, "status": status,
                 "source_revision": "obs-v1",
                 "target_contract_hash": Target(**bundle.policy_view()["target"]).contract_hash}]
    expected = score_admitted(outcomes, paths)
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=2, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        rows = list(pool.map(replay_journal, paths.values()))
    fast, remaining = scorer_with_replayed_engines(score_admitted, {p: e for p, e, _ in rows})
    assert fast.__code__ is score_admitted.__code__
    assert fast(outcomes, paths) == expected
    assert not remaining
    with pytest.raises(ValueError, match="Unverified or reused"):
        fast(outcomes, paths)


def test_corrupt_journal_still_fails_in_worker(tmp_path):
    path = tmp_path / "corrupt.jsonl"
    with EventJournal(path) as journal:
        engine, bundle, events = setup_engine(journal=journal)
        engine.run(events + [complete(bundle)], until=90)
    content = path.read_text()
    path.write_text(content.replace("obs-v1", "changed") + '{"incomplete":')
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=1, mp_context=multiprocessing.get_context("spawn")
    ) as pool, pytest.raises(ValueError):
        pool.submit(replay_journal, path).result()


def test_unregistered_journal_is_rejected():
    fast, _ = scorer_with_replayed_engines(score_admitted, {})
    with pytest.raises(ValueError, match="Unverified"):
        fast([], {"unknown": Path("unknown.jsonl")})
