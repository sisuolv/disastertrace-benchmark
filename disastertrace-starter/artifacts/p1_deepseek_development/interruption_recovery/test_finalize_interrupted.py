"""Offline regressions for preserving an uncertain attempt and its full denominator."""

from __future__ import annotations

import copy
import importlib.util
import shutil
from pathlib import Path

import pytest

from disastertrace.automated.collection_audit import audit_collection
from disastertrace.automated.common import canonical, read_jsonl, write_json
from disastertrace.automated.provider import ProviderClient
from disastertrace.automated.workflow import selected_episodes

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "interrupted_finalizer", Path(__file__).with_name("finalize_interrupted.py")
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline finalization must never call the provider")

    monkeypatch.setattr(ProviderClient, "complete", forbidden)
    live = ROOT / "work/p1-deepseek-development-v1"
    source = tmp_path / "source"
    shutil.copytree(live / "runs/answer_history/collection", source)
    ledger = tmp_path / "budget_ledger.json"
    shutil.copyfile(live / "budget_ledger.json", ledger)
    episodes = selected_episodes(
        ROOT / "work/build-p1-deepseek-v1",
        "development",
        group_ids=["AL092021", "AL062018", "AL052019"],
    )
    return source, ledger, episodes


def test_derived_collection_preserves_uncertain_attempt_and_original_bytes(inputs, tmp_path):
    source, ledger, episodes = inputs
    before, ledger_before = MODULE.tree_hashes(source), ledger.read_bytes()
    original, derived = MODULE.derive_collection(
        source, tmp_path / "derived", episodes, ledger_path=ledger
    )
    assert original["inflight_request"] and not original["safe_to_resume"]
    assert not derived["inflight_request"] and not derived["safe_to_resume"]
    assert derived["status"] == "provider_error"
    assert derived["counters"] == original["counters"]
    assert derived["counters"]["attempts_started"] == 19
    assert derived["counters"]["completions_received"] == 18
    assert derived["counters"]["unsubmitted_checkpoints"] == 12
    assert len(derived["responses"]) == 18
    assert len(derived["verified_requests"]) == 19
    assert len(derived["verified_outcomes"]) == 19
    assert MODULE.tree_hashes(source) == before
    assert ledger.read_bytes() == ledger_before
    disposition = MODULE.read_object(tmp_path / "derived/interruption_finalization.json")
    assert disposition["new_provider_calls"] == 0
    assert not disposition["provider_returned_error"]
    assert disposition["pending_reservation_usd"] == 0.46678016
    assert (
        disposition["administrative_outcome"]["state_after"]
        == original["verified_outcomes"][-1]["state_after"]
    )
    for name in ("plan.json", "requests.jsonl", "responses.jsonl"):
        assert (source / name).read_bytes() == (tmp_path / "derived" / name).read_bytes()
    assert (
        (tmp_path / "derived/outcomes.jsonl")
        .read_bytes()
        .startswith((source / "outcomes.jsonl").read_bytes())
    )


@pytest.mark.parametrize("mutation", ["no_pending", "resumable", "invalid"])
def test_requires_actual_uncertain_audit(inputs, mutation):
    source, _, episodes = inputs
    audit = audit_collection(episodes, source, allow_incomplete=True)
    if mutation == "no_pending":
        audit["inflight_request"] = False
    elif mutation == "resumable":
        audit["safe_to_resume"] = True
    else:
        audit["valid"] = False
    with pytest.raises(ValueError, match="uncertain"):
        MODULE.administrative_outcome(audit)


def test_orphan_raw_response_is_not_discarded(inputs, tmp_path):
    source, ledger, episodes = inputs
    requests = read_jsonl(source / "requests.jsonl")
    response = copy.deepcopy(read_jsonl(source / "responses.jsonl")[-1])
    response.update({key: requests[-1][key] for key in ("episode_id", "checkpoint_id")})
    with (source / "responses.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(canonical(response) + "\n")
    with pytest.raises(ValueError, match="orphan"):
        MODULE.derive_collection(source, tmp_path / "derived", episodes, ledger_path=ledger)
    assert not (tmp_path / "derived").exists()


@pytest.mark.parametrize("mutation", ["released", "completed", "wrong_request"])
def test_pending_ledger_must_identify_original_call(inputs, tmp_path, mutation):
    source, ledger, episodes = inputs
    document = MODULE.read_object(ledger)
    if mutation == "released":
        document["attempts"][-1]["reservation_released"] = True
    elif mutation == "completed":
        document["attempts"][-1]["completion_received"] = True
    else:
        document["attempts"][-1]["request_sha256"] = "0" * 64
    write_json(ledger, document)
    with pytest.raises(ValueError, match="original ledger"):
        MODULE.derive_collection(source, tmp_path / "derived", episodes, ledger_path=ledger)
    assert not (tmp_path / "derived").exists()


def test_existing_output_is_never_overwritten(inputs, tmp_path):
    source, ledger, episodes = inputs
    destination = tmp_path / "derived"
    destination.mkdir()
    (destination / "sentinel").write_text("keep", encoding="ascii")
    with pytest.raises(ValueError, match="already exists"):
        MODULE.derive_collection(source, destination, episodes, ledger_path=ledger)
    assert (destination / "sentinel").read_text() == "keep"


def test_output_cannot_be_nested_under_original(inputs):
    source, ledger, episodes = inputs
    with pytest.raises(ValueError, match="outside the original"):
        MODULE.derive_collection(source, source / "derived", episodes, ledger_path=ledger)
    assert not (source / "derived").exists()
