"""The new decoder changes JSON formatting freedom without encoding correct answers."""

import pytest

from disastertrace.cohort_live import profiles as previous
from disastertrace.compact_live import profiles


@pytest.mark.parametrize("name", ["qwen3", "deepseek_r1"])
def test_only_formatting_configuration_changes_between_tracks(name):
    before, after = previous.ADAPTERS[name], profiles.ADAPTERS[name]
    assert {k for k in before.SETTINGS if before.SETTINGS[k] != after.SETTINGS[k]} == {
        "structured_engine_options"
    }
    assert {
        k for k in before.ENGINE_OPTIONS if before.ENGINE_OPTIONS[k] != after.ENGINE_OPTIONS[k]
    } == {"guided_decoding_disable_any_whitespace"}
    assert {k for k in before.guide() if before.guide()[k] != after.guide()[k]} == {
        "disable_any_whitespace"
    }
    assert before.guide()["json"] == after.guide()["json"]
    assert after.guide()["disable_any_whitespace"] is True
    assert before.guide()["disable_any_whitespace"] is False
