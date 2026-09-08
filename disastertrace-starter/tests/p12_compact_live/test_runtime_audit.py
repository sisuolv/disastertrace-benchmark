"""Failure and provenance regressions against independently rebuilt native trajectories."""

from copy import deepcopy

import pytest

from disastertrace.compact_live import audit, package, profiles, runtime
from disastertrace.compact_live.backend import ProgramBackend
from disastertrace.forecast_task.common import canonical, read


def collect(bundle, worker=0, **kwargs):
    root, run, _, _, _, tokenizer, backend = bundle
    return runtime.collect(root, run, worker, tokenizer=tokenizer, backend=backend, **kwargs)


def change(path, key, value):
    record = read(path)
    record[key] = value
    path.write_text(canonical(record) + "\n")


def test_complete_two_worker_reconstruction_and_no_duplicate_launch(bundle):
    root, run, _, _, slots, tokenizer, _ = bundle
    for worker in range(2):
        assert collect(bundle, worker)["stop_reason"] == "complete"
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    assert result["scores"]["counts"]["all_correct"] == len(slots)
    assert result["counts"]["planned"] == result["counts"]["attempted"] == len(slots)
    assert result["counts"]["unknown_outcomes"] == 0
    with pytest.raises(FileExistsError):
        collect(bundle)


@pytest.mark.parametrize(
    "fault,attempted,returned,recovered",
    [
        ("before_started", 0, 0, 0),
        ("before_raw", 4, 0, 0),
        ("after_raw", 4, 4, 4),
        ("after_first_parse", 4, 4, 3),
    ],
)
def test_interruptions_preserve_unknowns_and_recover_only_without_generation(
    bundle, fault, attempted, returned, recovered
):
    root, run, _, _, slots, tokenizer, _ = bundle
    assert collect(bundle, fault=fault)["stop_reason"] == "exception"
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    assert result["counts"]["attempted"] == attempted
    assert result["counts"]["raw_returned"] == returned
    assert result["counts"]["recovered_raw"] == recovered
    assert result["counts"]["unknown_outcomes"] == attempted - returned
    assert result["scores"]["counts"]["planned"] == len(slots)
    assert result["scores"]["counts"]["all_correct"] == returned


@pytest.mark.parametrize("policy", ["invalid_even", "missing_even"])
def test_invalid_and_missing_histories_continue_without_fallback(bundle, policy):
    root, run, _, public, slots, tokenizer, _ = bundle
    for worker in range(2):
        runtime.collect(
            root, run, worker, tokenizer=tokenizer, backend=ProgramBackend(tokenizer, policy)
        )
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    expected = sum(public["opportunities"][s["opportunity_id"]]["delivery_step"] % 2 for s in slots)
    assert result["scores"]["counts"]["all_correct"] == expected
    assert result["scores"]["counts"]["planned"] == len(slots)
    carriers = []
    from disastertrace.forecast_task.common import strict_json

    for path in run.glob("worker-*/batches/*/intent.json"):
        for prepared in read(path)["prepared"]:
            payload = strict_json(prepared["messages"][1]["content"])
            if (
                payload["method"] == "structured_state"
                and payload["checkpoint"]["delivery_step"] == 3
            ):
                carriers.append(payload["carrier"]["kind"])
    assert carriers and set(carriers) == {"invalid" if policy == "invalid_even" else "missing"}


@pytest.mark.parametrize("mode", ["reverse", "partial", "duplicate", "unknown", "wrong_prompt"])
def test_returned_id_handling_is_not_positional(bundle, mode):
    root, run, _, _, _, tokenizer, backend = bundle
    original = backend.generate

    def generate(items):
        result = original(items)
        if mode == "reverse":
            return result[::-1]
        if mode == "partial":
            backend.last_error = "injected partial device failure"
            return result[:1]
        if mode == "duplicate":
            return [result[0], result[0]]
        if mode == "unknown":
            result[0]["attempt_id"] = "unknown"
        if mode == "wrong_prompt":
            result[0]["prompt_token_ids"] = [1]
        return result

    backend.generate = generate
    collect(bundle)
    if mode in ("duplicate", "unknown", "wrong_prompt"):
        with pytest.raises(ValueError):
            audit.aggregate(root, run, tokenizer=tokenizer)
    else:
        result = audit.aggregate(root, run, tokenizer=tokenizer)
        assert result["counts"]["unknown_outcomes"] == (3 if mode == "partial" else 0)
        assert result["workers"][0]["status"] == (
            "stopped_prefix" if mode == "partial" else "complete"
        )


@pytest.mark.parametrize(
    "file,key,value",
    [
        ("manifest.json", "origin", "local_model_vllm_second_model_native_forecast_v1"),
        ("manifest.json", "worker_id", 1),
        ("batches/000000/intent.json", "phase_id", "stale-phase"),
        ("batches/000000/started.json", "intent_sha256", "unbound"),
        ("batches/000000/raw.json", "worker_id", 1),
        ("completion.json", "attempted", 0),
    ],
)
def test_changed_origin_owner_journal_and_counters_rejected(bundle, file, key, value):
    root, run, _, _, _, tokenizer, _ = bundle
    collect(bundle)
    change(run / "worker-0" / file, key, value)
    with pytest.raises(ValueError):
        audit.aggregate(root, run, tokenizer=tokenizer)


def test_parser_cache_cannot_replace_raw_or_change_next_carrier(bundle):
    root, run, _, _, _, tokenizer, _ = bundle
    collect(bundle)
    path = next((run / "worker-0").glob("batches/*/parsed/*.json"))
    data = read(path)
    data["capture"]["final_text"] = "{}"
    path.write_text(canonical(data))
    with pytest.raises(ValueError, match="parsed cache"):
        audit.aggregate(root, run, tokenizer=tokenizer)


def test_absent_manifest_and_temporary_write_are_reported(bundle):
    root, run, _, _, slots, tokenizer, _ = bundle
    worker = run / "worker-0"
    worker.mkdir(parents=True)
    (worker / (".manifest.json." + "a" * 32 + ".tmp")).write_text("partial")
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    assert result["counts"]["planned"] == len(slots)
    assert result["counts"]["attempted"] == 0
    assert result["workers"][0]["temporary_files"]
    (worker / "unexplained.json").write_text("{}")
    with pytest.raises(ValueError, match="unexplained"):
        audit.aggregate(root, run, tokenizer=tokenizer)


def test_dispatch_guards_cannot_mix_diagnostics_or_move_model_root(bundle):
    _, run, plan, _, _, _, _ = bundle
    with pytest.raises(ValueError):
        runtime.validate_mode(plan, "model", run)
    live = {**plan, "kind": "model", "generation_authorized": True, "run_root": str(run)}
    with pytest.raises(ValueError):
        runtime.validate_mode(live, "diagnostic", run)
    with pytest.raises(ValueError):
        runtime.validate_mode(live, "model", run / "elsewhere")


def test_episode_ownership_round_dependencies_and_fresh_attempt_ids(bundle):
    _, _, _, public, slots, _, _ = bundle
    source_slots = [
        {k: v for k, v in s.items() if k not in ("attempt_id", "live_trajectory_id", "worker_id")}
        for s in slots
    ]
    newer = package.assign(public, source_slots, "fresh-phase")
    assert not {s["attempt_id"] for s in slots} & {s["attempt_id"] for s in newer}
    assert {s["slot_id"] for s in slots} == {s["slot_id"] for s in newer}
    ownership = {}
    for s in slots:
        ownership.setdefault(s["episode_id"], set()).add(s["worker_id"])
    assert all(len(v) == 1 for v in ownership.values())
    for worker in range(2):
        history = {}
        seen = []
        for batch in package.batches(slots, public, worker):
            assert len(batch) <= 4 and len({s["trajectory_id"] for s in batch}) == len(batch)
            for s in batch:
                step = len(public["opportunities"][s["opportunity_id"]]["previous_checkpoint_ids"])
                assert history.get(s["trajectory_id"], 0) == step
                history[s["trajectory_id"]] = step + 1
                seen.append(s["slot_id"])
        assert len(seen) == len(set(seen))


def test_context_overflow_fails_before_dispatch_without_truncation(bundle):
    root, run, _, _, _, tokenizer, _ = bundle
    tokenizer.apply_chat_template = lambda *a, **kw: "x" * 32769
    result = collect(bundle)
    assert result["attempted"] == 0 and "context budget" in result["error"]
    report = audit.aggregate(root, run, tokenizer=tokenizer)
    assert report["counts"]["attempted"] == 0


@pytest.mark.parametrize(
    "mode", ["stop", "length", "wrong_eos_text", "whitespace", "missing_stop", "double_eos"]
)
def test_exact_eos_rendering_and_reasoning_extraction(bundle, mode):
    tokenizer = bundle[5]
    adapter = profiles.adapter_for(bundle[2])
    ids = tokenizer.encode(" reasoning ") + [256] + tokenizer.encode(" {} \n")
    output = deepcopy(ids)
    if mode != "length":
        output += [257]
    if mode == "missing_stop":
        output = ids
    if mode == "double_eos":
        output += [257]
    text = tokenizer.decode(ids)
    if mode == "wrong_eos_text":
        text += "<|im_end|>"
    if mode == "whitespace":
        text = text.strip()
    result = {
        "output_token_ids": output,
        "runtime_output_text": text,
        "finish_reason": "length" if mode == "length" else "stop",
    }
    if mode in ("stop", "length"):
        adapter.verify_runtime_text(result, tokenizer)
        assert adapter.extract(output, tokenizer)["content"] == " {} \n"
    else:
        with pytest.raises(ValueError):
            adapter.verify_runtime_text(result, tokenizer)
