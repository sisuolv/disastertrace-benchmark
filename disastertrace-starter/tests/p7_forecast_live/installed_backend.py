"""Actual installed vLLM/XGrammar/tokenizer checks; CUDA hidden, no model load."""

import importlib.metadata
import os
from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.forecast_live import adapter, package
from disastertrace.forecast_live.grammar import GrammarReplay
from disastertrace.forecast_task.common import canonical, read
from disastertrace.forecast_task.contract import empty_answer, parse_answer
from disastertrace.forecast_task.protocol import request
from disastertrace.forecast_task.public_resolver import resolve


@pytest.fixture(scope="module")
def installed():
    from transformers import AutoTokenizer

    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    root = Path(os.environ["FORECAST_TASK_EXECUTION"])
    tokenizer = AutoTokenizer.from_pretrained(
        root / "tokenizer", local_files_only=True, trust_remote_code=False
    )
    config = read(root / "tokenizer/config.json")
    public = read(root / "data/public.json")
    source_slots = read(root / "schedule.json")
    slots = package.assign(public, source_slots, "installed-tests-no-generation")
    replay = GrammarReplay(tokenizer, config["vocab_size"])
    return tokenizer, public, slots, replay


def test_actual_environment_and_backend_hashes_match_p6(installed):
    resource = Path(os.environ["FORECAST_P6_RESOURCES"])
    assert package.environment() == read(resource / "parent/environment.json")
    expected = {
        k.removeprefix("backend_source/"): v
        for k, v in read(resource / "parent/execution.json")["resource_files"].items()
        if k.startswith("backend_source/")
    }
    expected.update(read(resource / "execution.json")["engine_files"])
    assert package.backend_inventory() == expected
    assert importlib.metadata.version("vllm") == "0.10.2"
    assert importlib.metadata.version("xgrammar") == "0.1.23"


def test_real_sampling_parameters_and_no_semantic_dynamic_guide(installed):
    tokenizer, public, slots, _ = installed
    slot = slots[0]
    messages = request(public, slot["opportunity_id"], slot["method"], [])
    item = adapter.prepare(messages, slot, tokenizer)
    values = adapter.sampling_params(item)
    assert values.max_tokens == 8192 and values.seed == slot["seed"]
    assert values.include_stop_str_in_output is False
    assert values.guided_decoding.json == adapter.guide()["json"]
    assert values.guided_decoding.disable_fallback is True
    assert len(item["prompt_token_ids"]) + 8192 <= 32768


@pytest.mark.parametrize(
    "kind", ["numeric", "DISSIPATED", "ABSORBED", "not_stated", "wrong_semantics"]
)
def test_native_schema_accepts_legal_shapes_including_wrong_semantics(installed, kind):
    _, public, slots, replay = installed
    query = public["opportunities"][slots[0]["opportunity_id"]]["query"]
    answer = empty_answer(query)
    answer["status"] = kind if kind != "wrong_semantics" else "numeric"
    if kind in ("numeric", "wrong_semantics"):
        for field, value in (("latitude", 24.8), ("longitude", -96.4), ("max_sustained_wind", 65)):
            answer[field]["value"] = value
        answer["citation"] = {"source_id": "arbitrary", "forecast_line": 25, "wind_line": 26}
    if kind in ("DISSIPATED", "ABSORBED"):
        answer["citation"] = {"source_id": "arbitrary", "forecast_line": 25, "wind_line": None}
    if kind == "wrong_semantics":
        answer["storm_id"] = "not-the-storm"
        answer["valid_at"] = "not-a-time"
        answer["measurement_kind"] = "observation"
        answer["max_sustained_wind"] = {"value": None, "unit": "wrong-unit"}
        answer["citation"]["source_id"] = "never-seen-source"
    text = canonical(answer)
    assert parse_answer(text) == answer
    assert replay.check_text(text)["accepted"] is True


def test_native_schema_rejects_extra_field_and_wrong_number_type(installed):
    _, public, slots, replay = installed
    answer = empty_answer(public["opportunities"][slots[0]["opportunity_id"]]["query"])
    bad = deepcopy(answer)
    bad["hidden_gold"] = True
    assert replay.check_text(canonical(bad))["accepted"] is False
    answer["latitude"]["value"] = "24.8"
    assert replay.check_text(canonical(answer))["accepted"] is False


def test_real_reasoning_mask_and_exact_terminal_rendering(installed):
    tokenizer, public, slots, replay = installed
    slot = slots[0]
    final = canonical(resolve(request(public, slot["opportunity_id"], slot["method"], [])))
    ids = tokenizer.encode("Reasoning is not JSON.\n", add_special_tokens=False)
    ids += tokenizer.encode("</think>", add_special_tokens=False)
    ids += tokenizer.encode("\n\n" + final, add_special_tokens=False)
    candidate = {
        "output_token_ids": ids + [tokenizer.eos_token_id],
        "finish_reason": "stop",
        "runtime_output_text": tokenizer.decode(ids, skip_special_tokens=False),
    }
    adapter.verify_runtime_text(candidate, tokenizer)
    assert adapter.extract(candidate["output_token_ids"], tokenizer)["content"] == "\n\n" + final
    result = replay.check_output(candidate["output_token_ids"])
    assert result["accepted"] is False and result["rejected_at"] == 0
    # The compiled root starts at '{'; any_whitespace permits internal JSON whitespace.
    legal = tokenizer.encode("Reasoning is not JSON.\n", add_special_tokens=False)
    legal += tokenizer.encode("</think>", add_special_tokens=False)
    legal += tokenizer.encode(final, add_special_tokens=False) + [tokenizer.eos_token_id]
    accepted = replay.check_output(legal)
    assert accepted["accepted"] and accepted["terminated"]
    candidate["runtime_output_text"] += tokenizer.decode(
        [tokenizer.eos_token_id], skip_special_tokens=False
    )
    with pytest.raises(ValueError, match="detokenization"):
        adapter.verify_runtime_text(candidate, tokenizer)
