"""Role placement preserves the exact logical contract, evidence and history bytes."""

from copy import deepcopy

from disastertrace.compact_live import adapter_deepseek as before
from disastertrace.forecast_task.common import fingerprint
from disastertrace.forecast_task.protocol import request
from disastertrace.prompt_role_live import adapter_deepseek as after


def test_only_registered_role_setting_changes_and_guide_is_identical():
    assert {k: v for k, v in after.SETTINGS.items() if k != "prompt_role_policy"} == before.SETTINGS
    assert after.guide() == before.guide()
    assert after.ENGINE_OPTIONS == before.ENGINE_OPTIONS


def test_logical_messages_remain_intact_and_actual_transport_is_recorded(bundle):
    _, _, _, public, slots, tokenizer, _ = bundle
    slot = slots[0]
    messages = request(public, slot["opportunity_id"], slot["method"], [])
    original = deepcopy(messages)
    prepared = after.prepare(messages, slot, tokenizer)
    actual = [{"role": "user", "content": messages[0]["content"] + "\n\n" + messages[1]["content"]}]
    assert messages == original and prepared["messages"] == original
    assert prepared["rendered_messages"] == actual
    assert prepared["rendered_messages_sha256"] == fingerprint(actual)
    assert prepared["prompt"] == tokenizer.apply_chat_template(
        actual, tokenize=False, add_generation_prompt=True, enable_thinking=True
    )
    assert prepared["prompt_token_ids"] == tokenizer.encode(
        prepared["prompt"], add_special_tokens=False
    )
    assert (
        prepared["prompt_token_ids"]
        != before.prepare(original, slot, tokenizer)["prompt_token_ids"]
    )
