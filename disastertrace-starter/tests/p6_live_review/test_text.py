from copy import deepcopy

import pytest

from disastertrace.local_eval.adapter import FixtureTokenizer
from disastertrace.repeat_live_review.text import verify_runtime_text


@pytest.fixture
def sample():
    tokenizer = FixtureTokenizer()
    tokens = tokenizer.encode("Reasoning.") + [256] + tokenizer.encode('{"value":3}') + [257]
    result = {
        "output_token_ids": tokens,
        "runtime_output_text": tokenizer.decode(tokens[:-1]),
        "finish_reason": "stop",
    }
    settings = {"include_stop_str_in_output": False, "skip_special_tokens": False}
    return result, tokenizer, settings


def test_stop_token_is_recorded_but_not_rendered_by_vllm(sample):
    verify_runtime_text(*sample, model=True)


@pytest.mark.parametrize(
    "mutation", ("wrong_value", "missing_delimiter", "added_stop_text", "extra_space")
)
def test_real_content_mismatch_still_fails(sample, mutation):
    result, tokenizer, settings = deepcopy(sample)
    if mutation == "wrong_value":
        result["runtime_output_text"] = result["runtime_output_text"].replace("3", "4")
    elif mutation == "missing_delimiter":
        result["runtime_output_text"] = result["runtime_output_text"].replace("</think>", "")
    elif mutation == "added_stop_text":
        result["runtime_output_text"] += "<|im_end|>"
    else:
        result["runtime_output_text"] += " "
    with pytest.raises(ValueError):
        verify_runtime_text(result, tokenizer, settings, model=True)


def test_length_finish_must_not_lose_its_last_token(sample):
    result, tokenizer, settings = sample
    result["finish_reason"] = "length"
    with pytest.raises(ValueError):
        verify_runtime_text(result, tokenizer, settings, model=True)
    result["runtime_output_text"] = tokenizer.decode(result["output_token_ids"])
    verify_runtime_text(result, tokenizer, settings, model=True)


def test_explicit_include_stop_preserves_stop_text(sample):
    result, tokenizer, settings = sample
    settings["include_stop_str_in_output"] = True
    with pytest.raises(ValueError):
        verify_runtime_text(result, tokenizer, settings, model=True)
    result["runtime_output_text"] = tokenizer.decode(result["output_token_ids"])
    verify_runtime_text(result, tokenizer, settings, model=True)


def test_diagnostic_text_contract_stays_unchanged(sample):
    result, tokenizer, settings = sample
    with pytest.raises(ValueError):
        verify_runtime_text(result, tokenizer, settings, model=False)
    result["runtime_output_text"] = tokenizer.decode(result["output_token_ids"])
    verify_runtime_text(result, tokenizer, settings, model=False)


def test_nonterminal_token_cannot_be_dropped(sample):
    result, tokenizer, settings = sample
    result["output_token_ids"].pop()
    result["runtime_output_text"] = tokenizer.decode(result["output_token_ids"][:-1])
    with pytest.raises(ValueError):
        verify_runtime_text(result, tokenizer, settings, model=True)
