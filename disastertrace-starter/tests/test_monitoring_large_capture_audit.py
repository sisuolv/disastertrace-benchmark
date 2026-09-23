"""The independent collector cannot silently accept changed or incomplete receipts."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / (
    "plans/v8_measurement_execution_20260913_01/gpu/verify_large_diagnostic.py"
)
SPEC = importlib.util.spec_from_file_location("large_capture_audit", SOURCE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class TokenizerFixture:
    eos_token_id = 2

    def apply_chat_template(self, messages, **kwargs):
        assert messages == [{"role": "user", "content": "fixture"}]
        return [11, 12]

    def decode(self, output, **kwargs):
        assert output == [21, 2]
        return '{"probability":0.2}'


def write(path, row):
    path.write_text(json.dumps(row) + "\n")


@pytest.fixture
def capture(tmp_path):
    raw = '{"probability":0.2}'
    messages = [{"role": "user", "content": "fixture"}]
    task = {
        "call_id": "fixture-call",
        "messages_sha256": AUDIT.fingerprint(messages),
        "models": {
            "fixture-model": {"input_tokens": 2, "input_ids_sha256": AUDIT.fingerprint([11, 12])}
        },
        "logical_started_at": 1_000_000,
        "logical_cutoff": 2_000_000,
    }
    request = {
        "call_id": task["call_id"],
        "model": "fixture-model",
        "plan_sha256": "fixture-plan",
        "messages": messages,
        "input_ids": [11, 12],
        "input_tokens": 2,
        "logical_started_at": task["logical_started_at"],
        "logical_cutoff": task["logical_cutoff"],
        "batch_offset": 0,
        "batch_size": 4,
    }
    response = {
        "call_id": task["call_id"],
        "model": "fixture-model",
        "plan_sha256": "fixture-plan",
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "output_ids": [21, 2],
        "input_tokens": 2,
        "output_tokens": 2,
        "finish_reason": "stop",
        "stop_reason": None,
        "ended_with_eos": True,
        "batch_elapsed_us": 1000,
        "logical_started_at": task["logical_started_at"],
        "logical_completed_at": task["logical_started_at"] + 1000,
    }
    paths = {
        k: tmp_path / (task["call_id"] + "-" + k + ".json")
        for k in ("request", "response", "commit")
    }
    write(paths["request"], request)
    write(paths["response"], response)
    commit = {
        "call_id": task["call_id"],
        "plan_sha256": "fixture-plan",
        "request_sha256": AUDIT.digest(paths["request"]),
        "response_sha256": AUDIT.digest(paths["response"]),
        "raw_sha256": response["raw_sha256"],
        "persisted_elapsed_us": 2000,
        "completed_elapsed_us": 1000,
        "logical_persisted_at": task["logical_started_at"] + 2000,
        "wall_started_ns": 9_000_000_000,
        "wall_after_response_fsync_ns": 9_002_000_000,
    }
    write(paths["commit"], commit)
    return tmp_path, task, paths


def verify(capture):
    directory, task, _ = capture
    return AUDIT.verify_capture(
        directory, task, "fixture-model", "fixture-plan", TokenizerFixture()
    )


def test_valid_committed_receipt(capture):
    assert verify(capture)["disposition"] == "committed"


@pytest.mark.parametrize(
    "remaining,disposition",
    [
        ([], "unattempted"),
        (["request"], "unknown_execution"),
        (["request", "response"], "uncommitted_response"),
    ],
)
def test_missing_capture_stays_explicit(capture, remaining, disposition):
    for kind, path in capture[2].items():
        if kind not in remaining:
            path.unlink()
    assert verify(capture)["disposition"] == disposition


@pytest.mark.parametrize(
    "kind,field,value",
    [
        ("request", "call_id", "other"),
        ("request", "batch_offset", 4),
        ("request", "input_tokens", 99),
        ("response", "raw_sha256", "wrong"),
        ("response", "ended_with_eos", False),
        ("response", "logical_completed_at", 1),
        ("commit", "request_sha256", "wrong"),
        ("commit", "logical_persisted_at", 1),
        ("commit", "persisted_elapsed_us", 999),
    ],
)
def test_corrupt_receipt_cannot_be_scored(capture, kind, field, value):
    path = capture[2][kind]
    row = json.loads(path.read_text())
    row[field] = value
    write(path, row)
    with pytest.raises(AUDIT.AuditError):
        verify(capture)


def test_commit_without_response_is_integrity_failure(capture):
    capture[2]["response"].unlink()
    with pytest.raises(AUDIT.AuditError, match="Commit without response"):
        verify(capture)


def test_late_receipt_is_verified_then_left_for_cutoff_admission(capture):
    path = capture[2]["commit"]
    row = json.loads(path.read_text())
    row.update(
        persisted_elapsed_us=2_000_000,
        logical_persisted_at=3_000_000,
        wall_after_response_fsync_ns=11_000_000_000,
    )
    write(path, row)
    result = verify(capture)
    assert result["disposition"] == "committed"
    assert result["commit"]["logical_persisted_at"] > capture[1]["logical_cutoff"]
