"""Context measurement must exactly match the actual prompt and cap guard."""

import importlib.util
from pathlib import Path

import pytest

from disastertrace.constrained_eval import adapter
from disastertrace.controlled import generator, renderer
from disastertrace.local_eval.adapter import FixtureTokenizer

spec = importlib.util.spec_from_file_location(
    "p4_stress_calibration", Path(__file__).with_name("calibrate_stress.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_adapter_tokens_without_gold_input():
    request = renderer.render_request(generator.micro_episodes()[0], "c1", method="snapshot")
    tokenizer = FixtureTokenizer()
    measurement, ids = module.measure(request, tokenizer)
    assert measurement["fits_full_output_cap"]
    assert adapter.prepare(request, {"slot_id": "test"}, tokenizer)["prompt_token_ids"] == ids
    assert measurement["remaining_tokens"] == adapter.SETTINGS["max_model_len"] - len(ids)


def test_over_budget_is_reported_without_truncating_or_lowering_output_cap():
    request = renderer.render_request(generator.micro_episodes()[0], "c1", method="snapshot")
    original = request["evidence"]
    request["evidence"] = [
        {**original[index % len(original)], "delivery_id": "context-replay-" + str(index)}
        for index in range(50)
    ]
    measurement, ids = module.measure(request, FixtureTokenizer())
    assert not measurement["fits_full_output_cap"]
    assert measurement["prompt_tokens"] == len(ids)
    assert measurement["reserved_output_tokens"] == 8192
    with pytest.raises(ValueError, match="context budget exceeded"):
        adapter.prepare(request, {"slot_id": "test"}, FixtureTokenizer())
