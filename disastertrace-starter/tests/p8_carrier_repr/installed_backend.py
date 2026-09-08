"""Actual tokenizer and vLLM parameters for two encodings of a shared native prefix."""

import os
from pathlib import Path

import pytest

from disastertrace.carrier_repr import adapter, design
from disastertrace.forecast_task.common import canonical, read
from disastertrace.forecast_task.contract import empty_answer
from disastertrace.forecast_task.protocol import request


@pytest.fixture(scope="module")
def installed():
    from transformers import AutoTokenizer

    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    root = Path(os.environ["FORECAST_TASK_EXECUTION"])
    tokenizer = AutoTokenizer.from_pretrained(
        root / "tokenizer", local_files_only=True, trust_remote_code=False
    )
    public = read(root / "data/public.json")
    slot = next(
        s
        for s in read(root / "schedule.json")
        if s["method"] == "structured_state"
        and public["opportunities"][s["opportunity_id"]]["previous_checkpoint_ids"]
    )
    return tokenizer, public, slot


@pytest.mark.parametrize("previous", ["valid_shape_wrong_semantics", "invalid", "missing"])
def test_both_encodings_share_sampling_and_lossless_source_with_real_tokenizer(installed, previous):
    tokenizer, public, slot = installed
    opportunity = public["opportunities"][slot["opportunity_id"]]
    answer = empty_answer(opportunity["query"])
    answer["storm_id"] = "wrong-storm"
    answer["max_sustained_wind"] = {"value": -0.0, "unit": "wrong-unit"}
    final = (
        canonical(answer)
        if previous == "valid_shape_wrong_semantics"
        else "invalid"
        if previous == "invalid"
        else None
    )
    history = [
        {"checkpoint_id": cid, "final_text": final}
        for cid in opportunity["previous_checkpoint_ids"]
    ]
    native = request(public, slot["opportunity_id"], slot["method"], history)
    items = []
    for encoding in ("json", "text"):
        messages = design.represent(native, encoding)
        assert canonical(design.restore(messages)) == canonical(native)
        item = adapter.prepare(messages, {**slot, "attempt_id": "fixture-" + encoding}, tokenizer)
        values = adapter.sampling_params(item)
        assert values.seed == slot["seed"] and values.max_tokens == 8192
        assert values.guided_decoding.disable_fallback is True
        assert len(item["prompt_token_ids"]) + 8192 <= 32768
        items.append(item)
    assert items[0]["sampling"] == items[1]["sampling"]
    assert items[0]["prompt_token_ids"] != items[1]["prompt_token_ids"]
