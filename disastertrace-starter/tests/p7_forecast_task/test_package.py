import pytest

from disastertrace.forecast_task.common import read, seal, verify, write
from disastertrace.forecast_task.package import prepare_request


class TokenizerFixture:
    def __init__(self, count):
        self.count = count

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == {"tokenize": True, "add_generation_prompt": True, "enable_thinking": True}
        return [42] * self.count


def test_output_reservation_inclusive_boundary_and_no_truncation():
    messages = [{"role": "user", "content": "fixture"}]
    assert prepare_request(messages, TokenizerFixture(24576))["prompt_tokens"] == 24576
    with pytest.raises(ValueError, match="no truncation"):
        prepare_request(messages, TokenizerFixture(24577))
    with pytest.raises(ValueError, match="closing delimiter"):
        prepare_request(
            [{"role": "user", "content": "own earlier </think> output"}], TokenizerFixture(10)
        )


@pytest.mark.parametrize("context,output", [(True, 1), (10, 10), (10, 0), (5, 9)])
def test_context_invalid_budget_is_rejected(context, output):
    with pytest.raises(ValueError, match="reservation"):
        prepare_request([], TokenizerFixture(1), context, output)


def test_exclusive_files_seal_and_tamper_detection(tmp_path):
    write(tmp_path / "nested/value.json", {"test": 1})
    with pytest.raises(FileExistsError):
        write(tmp_path / "nested/value.json", {"test": 2})
    record = seal(tmp_path)
    assert verify(tmp_path) == record
    (tmp_path / "nested/value.json").write_text('{"test":2}\n')
    with pytest.raises(ValueError, match="inventory"):
        verify(tmp_path)


def test_added_files_and_rebound_manifest_id_rejected(tmp_path):
    write(tmp_path / "original.json", {})
    seal(tmp_path)
    write(tmp_path / "extra.json", {})
    with pytest.raises(ValueError, match="inventory"):
        verify(tmp_path)
    manifest = read(tmp_path / "manifest.json")
    manifest["package_id"] = "0" * 64
    (tmp_path / "manifest.json").write_text(str(manifest).replace("'", '"'))
    with pytest.raises(ValueError, match="identity"):
        verify(tmp_path)
