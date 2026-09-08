"""One-step pairing, fixed denominators and raw-first interruption recovery."""

from copy import deepcopy

import pytest

from disastertrace.carrier_repr import audit, design, package, protocol, runtime
from disastertrace.carrier_repr.backend import ProgramBackend
from disastertrace.forecast_task.common import canonical, read


def collect(bundle, worker=0, **kwargs):
    root, run, _, _, _, tokenizer, backend = bundle
    return runtime.collect(root, run, worker, tokenizer=tokenizer, backend=backend, **kwargs)


def test_four_workers_preserve_both_arms_and_prohibit_duplicate_launch(bundle):
    root, run, _, _, slots, tokenizer, _ = bundle
    for worker in range(4):
        assert collect(bundle, worker)["stop_reason"] == "complete"
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    assert result["scores"]["counts"]["all_correct"] == len(slots)
    assert result["counts"]["attempted"] == result["counts"]["planned"] == len(slots)
    assert result["paired_representation"]["counts"] == {
        "json_correct_text_correct": len(slots) // 2
    }
    assert result["paired_representation"]["text_minus_json_accuracy"] == 0
    with pytest.raises(FileExistsError):
        collect(bundle)


def test_ineligible_prefix_never_dispatches_but_remains_in_paired_denominator(bundle):
    root, run, _, public, slots, tokenizer, _ = bundle
    pair_id = slots[0]["pair_id"]
    for slot in slots:
        if slot["pair_id"] == pair_id:
            slot["eligible"] = False
            public["representation_requests"][slot["slot_id"]].update(eligible=False, messages=None)
    for worker in range(4):
        assert collect(bundle, worker)["stop_reason"] == "complete"
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    assert result["eligibility"]["ineligible_prefix"] == 2
    assert result["counts"]["planned"] == len(slots)
    assert result["counts"]["attempted"] == len(slots) - 2
    assert result["scores"]["absent_capture_records"] == 2
    assert result["paired_representation"]["counts"]["json_wrong_text_wrong"] == 1


def test_every_worker_can_be_empty_without_shrinking_population(bundle):
    root, run, _, _, slots, tokenizer, _ = bundle
    for slot in slots:
        slot["eligible"] = False
    for worker in range(4):
        assert collect(bundle, worker)["stop_reason"] == "complete"
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    assert result["counts"]["planned"] == len(slots) and result["counts"]["attempted"] == 0
    assert result["paired_representation"]["counts"] == {"json_wrong_text_wrong": len(slots) // 2}


@pytest.mark.parametrize("policy", ["invalid_even", "missing_even"])
def test_branch_failures_cannot_change_any_later_source_prefix(bundle, policy):
    root, run, _, public, slots, tokenizer, _ = bundle
    before = deepcopy(public["representation_requests"])
    for worker in range(4):
        runtime.collect(
            root, run, worker, tokenizer=tokenizer, backend=ProgramBackend(tokenizer, policy)
        )
    result = audit.aggregate(root, run, tokenizer=tokenizer)
    expected = sum(public["opportunities"][s["opportunity_id"]]["delivery_step"] % 2 for s in slots)
    assert result["scores"]["counts"]["all_correct"] == expected
    assert public["representation_requests"] == before
    for path in run.glob("worker-*/batches/*/intent.json"):
        for item in read(path)["prepared"]:
            assert item["messages"] == before[item["slot_id"]]["messages"]
            design.restore(item["messages"])


@pytest.mark.parametrize(
    "fault,attempted,returned,recovered",
    [
        ("before_started", 0, 0, 0),
        ("before_raw", 4, 0, 0),
        ("after_raw", 4, 4, 4),
        ("after_first_parse", 4, 4, 3),
    ],
)
def test_interrupted_pair_batch_recovers_raw_without_new_generation(
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


@pytest.mark.parametrize("mode", ["reverse", "partial", "duplicate", "unknown", "wrong_prompt"])
def test_partial_or_out_of_order_returns_use_explicit_branch_id(bundle, mode):
    root, run, _, _, _, tokenizer, backend = bundle
    original = backend.generate

    def generate(items):
        results = original(items)
        if mode == "reverse":
            return results[::-1]
        if mode == "partial":
            backend.last_error = "fixture device failure"
            return results[:1]
        if mode == "duplicate":
            return [results[0], results[0]]
        if mode == "unknown":
            results[0]["attempt_id"] = "foreign"
        if mode == "wrong_prompt":
            results[0]["prompt_token_ids"] = [1]
        return results

    backend.generate = generate
    collect(bundle)
    if mode in ("duplicate", "unknown", "wrong_prompt"):
        with pytest.raises(ValueError):
            audit.aggregate(root, run, tokenizer=tokenizer)
    else:
        result = audit.aggregate(root, run, tokenizer=tokenizer)
        assert result["counts"]["unknown_outcomes"] == (3 if mode == "partial" else 0)


def test_mutated_parsed_cache_and_swapped_representation_are_rejected(bundle):
    root, run, _, public, slots, tokenizer, _ = bundle
    collect(bundle)
    path = next((run / "worker-0").glob("batches/*/parsed/*.json"))
    record = read(path)
    record["capture"]["final_text"] = "{}"
    path.write_text(canonical(record))
    with pytest.raises(ValueError, match="parsed cache"):
        audit.aggregate(root, run, tokenizer=tokenizer)
    slot = slots[0]
    with pytest.raises(ValueError, match="binding"):
        protocol.request(
            public, {**slot, "method": "text" if slot["method"] == "json" else "json"}, []
        )
    with pytest.raises(ValueError, match="one-step"):
        protocol.request(public, slot, [{"final_text": "an output from another fork"}])


def test_target_ownership_pair_seed_and_dispatch_order_are_fixed(bundle):
    _, _, _, public, slots, _, _ = bundle
    ownership, seen = {}, []
    for slot in slots:
        ownership.setdefault(slot["episode_id"], set()).add(slot["worker_id"])
    assert all(len(v) == 1 for v in ownership.values())
    for worker in range(4):
        for batch in package.batches(slots, public, worker):
            assert len(batch) <= 4 and len(batch) % 2 == 0
            for a, b in zip(batch[::2], batch[1::2]):
                assert a["pair_id"] == b["pair_id"] and a["seed"] == b["seed"]
                assert a["trajectory_id"] != b["trajectory_id"]
                assert {a["encoding"], b["encoding"]} == {"json", "text"}
                seen.extend((a["slot_id"], b["slot_id"]))
    assert len(seen) == len(set(seen)) == len(slots)


def test_inconsistent_pair_eligibility_fails_closed(bundle):
    _, _, _, public, slots, _, _ = bundle
    slots[0]["eligible"] = False
    with pytest.raises(ValueError, match="pair"):
        package.batches(slots, public, slots[0]["worker_id"])
