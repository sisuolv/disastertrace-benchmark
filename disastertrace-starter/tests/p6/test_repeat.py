"""Paired seeds, whole-batch durability, independent reconstruction and failure denominators."""

from collections import defaultdict
from copy import deepcopy

import pytest

from disastertrace.automated.common import fingerprint
from disastertrace.controlled.generator import micro_episodes
from disastertrace.local_eval.storage import read
from disastertrace.repeat_eval import audit, package, protocol, runtime, statistics


@pytest.fixture
def candidate(tmp_path):
    ep = micro_episodes()[0]
    data = {"base": [ep], "irrelevant_scope": [deepcopy(ep)]}
    path = tmp_path / "execution"
    package.freeze(data, path, tmp_path / "registry", fixture=True, repeats=2)
    return path


def test_identity_and_sampling_are_separate(candidate):
    plan, _, slots = package.verify(candidate)
    groups = defaultdict(list)
    for s in slots:
        groups[s["pair_id"]].append(s)
    assert len(slots) == 60 and len({s["trajectory_id"] for s in slots}) == 12
    for pair in groups.values():
        a, b = pair
        assert a["condition"] != b["condition"] and a["slot_id"] != b["slot_id"]
        assert a["sampling_seed"] == b["sampling_seed"] and a["sampling_key"] == b["sampling_key"]
    assert len({s["sampling_seed"] for s in slots}) == len(groups)
    assert not plan["generation_authorized"]
    for batch in protocol.batches(slots):
        assert len({s["trajectory_id"] for s in batch}) == len(batch)
        assert len({s["checkpoint_id"] for s in batch}) == 1


@pytest.mark.parametrize("mode", ["correct", "invalid-control", "wrong-valid"])
def test_full_replay_isolated_carriers(candidate, tmp_path, mode):
    run = tmp_path / mode
    runtime.collect(candidate, run, mode=mode)
    result = audit.reconstruct(candidate, run)
    assert result["summary"]["received"] == result["summary"]["planned"] == 60
    assert result["summary"]["additional_model_calls"] == 0
    for trace in result["traces"]:
        if trace["checkpoint_id"] != "c3" or trace["method"] == "snapshot":
            continue
        carrier = trace["request"].get("previous_state")
        if trace["method"] == "answer_history":
            carrier = trace["request"]["answer_history"][-1]
        if mode == "invalid-control":
            assert trace["prior_accepted_checkpoint"] == "c1"
        if mode == "wrong-valid":
            assert carrier["action"] == "request_evidence"


@pytest.mark.parametrize(
    "fault,received", [("before_raw", 0), ("after_raw", 12), ("after_first_parse", 12)]
)
def test_crash_recovery_never_regenerates(candidate, tmp_path, fault, received):
    run = tmp_path / fault
    with pytest.raises(RuntimeError, match="injected"):
        runtime.collect(candidate, run, fault=fault)
    result = audit.reconstruct(candidate, run)
    assert result["summary"]["received"] == received
    assert result["summary"]["planned"] == 60
    assert result["summary"]["complete"] is False
    assert result["summary"]["incomplete_infrastructure"] is True
    if received:
        assert result["summary"]["raw_recovered_without_parsed_record"] == (
            12 if fault == "after_raw" else 11
        )
    else:
        assert result["summary"]["outcome_unknown"] == 12
    scores = statistics.summarize(result)
    assert sum(r["counts"]["checkpoints"] for r in scores["cells"]) == 60
    with pytest.raises((ValueError, FileExistsError)):
        runtime.collect(candidate, tmp_path / "bypass", fault=None)


def test_duplicate_launch_rejected_even_at_different_run_path(candidate, tmp_path):
    runtime.collect(candidate, tmp_path / "first")
    with pytest.raises((ValueError, FileExistsError)):
        runtime.collect(candidate, tmp_path / "second")


def test_offline_package_cannot_be_relabelled_model(candidate, tmp_path):
    with pytest.raises(ValueError, match="offline"):
        runtime.collect(candidate, tmp_path / "model", mode="model")


@pytest.mark.parametrize("mutation", ["seed", "repeat", "request", "carrier"])
def test_recomputed_surface_hash_does_not_bypass_prompt_audit(candidate, tmp_path, mutation):
    from disastertrace.automated.common import canonical

    run = tmp_path / mutation
    runtime.collect(candidate, run)
    path = run / "intents/0000.json"
    intent = read(path)
    if mutation == "seed":
        intent["prepared"][0]["sampling"]["seed"] += 1
    elif mutation == "repeat":
        intent["slots"][0]["repeat"] += 1
    elif mutation == "request":
        intent["requests"][0]["instruction"] += " tampered"
    else:
        intent["requests"][0]["previous_state"] = {"fake": "carrier"}
    path.write_text(canonical(intent) + "\n")
    raw_path = run / "raw/0000.json"
    raw = read(raw_path)
    raw["intent_sha256"] = fingerprint(intent)
    raw_path.write_text(canonical(raw) + "\n")
    with pytest.raises(ValueError):
        audit.reconstruct(candidate, run)


def test_raw_complete_batch_survives_one_extraction_failure(candidate, tmp_path):
    runtime.collect(candidate, tmp_path / "bad", mode="extraction-control")
    result = audit.reconstruct(candidate, tmp_path / "bad")
    assert result["summary"]["received"] == 60
    assert any(t["status"] == "invalid" for t in result["traces"])


@pytest.mark.parametrize(
    "successes,repeats,k,expected", [(1, 2, 2, 0), (2, 2, 2, 1), (2, 3, 2, 1 / 3), (1, 1, 2, None)]
)
def test_pass_power_is_episode_reliability(successes, repeats, k, expected):
    assert statistics.pass_power(successes, repeats, k) == expected


def test_atomic_file_never_overwrites(tmp_path):
    from disastertrace.repeat_eval.storage import atomic_write

    path = tmp_path / "raw.json"
    atomic_write(path, {"first": True})
    with pytest.raises(FileExistsError):
        atomic_write(path, {"first": False})
    assert read(path) == {"first": True}


def test_partial_batch_preserves_received_slots_and_unknowns(candidate, tmp_path):
    run = tmp_path / "partial"
    with pytest.raises(RuntimeError, match="partial"):
        runtime.collect(candidate, run, fault="partial_raw")
    result = audit.reconstruct(candidate, run)
    assert result["summary"]["received"] == 6
    assert result["summary"]["outcome_unknown"] == 6
    assert result["summary"]["unsubmitted"] == 48
    assert statistics.summarize(result)["counts"]["checkpoints"] == 60


@pytest.mark.parametrize("mutation", ["complete", "naive_time", "calls", "nan_wall"])
def test_audit_rejects_misleading_completion(candidate, tmp_path, mutation):
    from disastertrace.automated.common import canonical

    run = tmp_path / mutation
    runtime.collect(candidate, run)
    path = run / "completion.json"
    value = read(path)
    if mutation == "complete":
        value["complete"] = False
    elif mutation == "naive_time":
        value["at"] = "2099-01-01T00:00:00"
    elif mutation == "calls":
        value["additional_model_calls"] = 1
    else:
        path = run / "raw/0000.json"
        value = read(path)
        value["batch_wall_seconds"] = -1
    path.write_text(canonical(value) + "\n")
    with pytest.raises(ValueError):
        audit.reconstruct(candidate, run)


def test_schedule_ignores_global_random_state_and_process_hash_seed(candidate):
    import os
    import random
    import subprocess
    import sys

    plan, _, slots = package.verify(candidate)
    random.seed(42)
    for _ in range(100):
        random.random()
    assert protocol.schedule(plan) == slots
    code = (
        "import sys; from disastertrace.local_eval.storage import read; "
        "from disastertrace.repeat_eval.protocol import schedule; "
        "from disastertrace.automated.common import fingerprint; "
        "print(fingerprint(schedule(read(sys.argv[1]))))"
    )
    for seed in ("17", "982"):
        value = subprocess.check_output(
            [sys.executable, "-c", code, str(candidate / "execution.json")],
            env={**os.environ, "PYTHONHASHSEED": seed},
            text=True,
        )
        assert value.strip() == fingerprint(slots)


def test_seed_collision_is_rejected(candidate, monkeypatch):
    plan, _, _ = package.verify(candidate)
    monkeypatch.setattr(protocol, "sampling_seed", lambda key: 7)
    with pytest.raises(ValueError, match="collision"):
        protocol.schedule(plan)


def test_competing_launchers_cannot_claim_different_paths(candidate, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    def launch(index):
        try:
            runtime.collect(candidate, tmp_path / str(index))
        except FileExistsError:
            return "rejected"
        return "collected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(launch, range(2))) == ["collected", "rejected"]


def test_context_failure_preserves_complete_planned_denominator(candidate, tmp_path, monkeypatch):
    original = protocol.prepare_request

    def prepare(request, slot, tokenizer):
        if slot["checkpoint_id"] == "c2":
            raise ValueError("context budget exceeded; automatic truncation is forbidden")
        return original(request, slot, tokenizer)

    monkeypatch.setattr(protocol, "prepare_request", prepare)
    run = tmp_path / "context"
    with pytest.raises(ValueError, match="context budget"):
        runtime.collect(candidate, run)
    result = audit.reconstruct(candidate, run)
    assert result["summary"]["received"] == 24 and result["summary"]["unsubmitted"] == 36
    assert statistics.summarize(result)["counts"]["checkpoints"] == 60


def test_actual_oversize_carrier_is_not_truncated(candidate):
    from disastertrace.controlled.public_oracle import answer
    from disastertrace.controlled.renderer import render_request
    from disastertrace.local_eval.adapter import FixtureTokenizer

    _, datasets, slots = package.verify(candidate)
    ep = datasets["base"][0]
    previous = answer(render_request(ep, "c1", method="snapshot"))
    req = render_request(ep, "c2", method="answer_history", history=[previous] * 300)
    slot = next(s for s in slots if s["method"] == "answer_history" and s["checkpoint_id"] == "c2")
    with pytest.raises(ValueError, match="context budget"):
        protocol.prepare_request(req, slot, FixtureTokenizer())
    assert len(req["answer_history"]) == 300


@pytest.mark.parametrize(
    "field,value",
    [
        ("response_cache", True),
        ("retries", 1),
        ("repair", True),
        ("generation_authorized", 0),
        ("max_model_attempts", False),
    ],
)
def test_rehashed_candidate_cannot_change_protocol_flags(candidate, field, value):
    from disastertrace.automated.common import canonical
    from disastertrace.local_eval.storage import inventory

    plan = read(candidate / "execution.json")
    plan[field] = value
    plan["experiment_id"] = fingerprint(
        {
            k: v
            for k, v in plan.items()
            if k not in ("experiment_id", "execution_id", "schedule_sha256", "resource_files")
        }
    )
    plan["execution_id"] = fingerprint({k: v for k, v in plan.items() if k != "execution_id"})
    (candidate / "execution.json").write_text(canonical(plan) + "\n")
    files = inventory(candidate, exclude=("manifest.json",))
    manifest = {"schema_version": "local_eval_manifest_v1", "files": files}
    manifest["package_id"] = fingerprint(manifest)
    (candidate / "manifest.json").write_text(canonical(manifest) + "\n")
    with pytest.raises(ValueError, match="offline scope"):
        package.verify(candidate)


def test_extraction_exception_keeps_other_raw_results(candidate, tmp_path, monkeypatch):
    run = tmp_path / "exception"
    with monkeypatch.context() as scoped:

        def fail(*args, **kwargs):
            raise RuntimeError("injected extraction failure")

        scoped.setattr(runtime.adapter, "extract", fail)
        with pytest.raises(RuntimeError, match="extraction"):
            runtime.collect(candidate, run)
    result = audit.reconstruct(candidate, run)
    assert result["summary"]["received"] == 12
    assert result["summary"]["raw_recovered_without_parsed_record"] == 12


def test_report_reverification_and_origin_guard(candidate, tmp_path):
    run, saved = tmp_path / "run", tmp_path / "report"
    runtime.collect(candidate, run)
    audit.report(candidate, run, saved)
    assert audit.verify_report(candidate, run, saved)["status"] == "passed"
    with pytest.raises(ValueError, match="relabelled"):
        audit.reconstruct(candidate, run, require_model=True)
