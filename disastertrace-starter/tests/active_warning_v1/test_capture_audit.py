"""Capture integrity checks without loading weights or making model calls."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest


class FixtureTokenizer:
    def apply_chat_template(self, messages, **kwargs):
        return json.dumps(messages)

    def __call__(self, rendered, **kwargs):
        return {"input_ids": list(rendered.encode())}

    def decode(self, ids, **kwargs):
        return bytes(t for t in ids if t != 0).decode()


@pytest.fixture
def capture(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[3] / "plans/active_warning_miniloop_20260912"
    monkeypatch.syspath_prepend(str(scripts))
    validator = importlib.import_module("collect_models").validate_capture
    messages = [
        {"role": "system", "content": "fixture"},
        {"role": "user", "content": "public view"},
    ]
    tokenizer = FixtureTokenizer()
    rendered = tokenizer.apply_chat_template(messages)
    raw = '{"queries":[]}'
    request = {
        "messages": messages,
        "plan_sha256": "fixture-plan",
        "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "input_ids": list(rendered.encode()),
        "input_tokens": len(rendered),
    }
    response = {
        "output_ids": list(raw.encode()) + [0],
        "output_tokens": len(raw) + 1,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": len(rendered),
        "capture_prefix": "acquire-0",
        "ended_with_eos": True,
        "seconds": 0.2,
    }
    for suffix, value in (("request", request), ("response", response)):
        (tmp_path / f"acquire-0-{suffix}.json").write_text(json.dumps(value))
    (tmp_path / "acquire-0-raw.txt").write_text(raw)

    def validate():
        return validator(
            tmp_path,
            "acquire-0",
            messages,
            tokenizer,
            [0],
            {"max_new_tokens": 384, "context_limit": 8192},
            "fixture-plan",
        )

    return tmp_path, validate


def test_valid_capture_reconstructs_without_generation(capture):
    _, validate = capture
    raw, details = validate()
    assert raw == '{"queries":[]}'
    assert details["ended_with_eos"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("messages", [{"role": "user", "content": "future private answer"}]),
        ("plan_sha256", "different-plan"),
        ("input_ids", [100]),
        ("rendered_sha256", "different-prompt"),
    ],
)
def test_request_tampering_fails(capture, field, value):
    root, validate = capture
    path = root / "acquire-0-request.json"
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        validate()


@pytest.mark.parametrize(
    "field,value",
    [
        ("output_ids", [100, 0]),
        ("output_tokens", 999),
        ("ended_with_eos", False),
        ("seconds", float("nan")),
        ("raw_sha256", "different-output"),
    ],
)
def test_response_tampering_fails(capture, field, value):
    root, validate = capture
    path = root / "acquire-0-response.json"
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        validate()


def test_raw_text_tampering_fails(capture):
    root, validate = capture
    (root / "acquire-0-raw.txt").write_text('{"queries":["forecast"]}')
    with pytest.raises(ValueError):
        validate()


def test_length_finish_is_retained_but_not_accepted(capture):
    root, validate = capture
    path = root / "acquire-0-response.json"
    data = json.loads(path.read_text())
    data["output_ids"].pop()
    data["output_tokens"] -= 1
    data["ended_with_eos"] = False
    path.write_text(json.dumps(data))
    raw, details = validate()
    assert raw == ""
    assert not details["ended_with_eos"]
    assert (root / "acquire-0-raw.txt").read_text() == '{"queries":[]}'
