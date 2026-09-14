"""The adaptive auditor rejects altered text, token counts and timing receipts."""

import copy
import hashlib
import importlib.util
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "plans/v8_measurement_execution_20260913_01/gpu/verify_adaptive.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_capture_audit", SOURCE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class TokenizerFixture:
    eos_token_id = 2

    def apply_chat_template(self, messages, **kwargs):
        assert messages == [{"role": "user", "content": "fixture"}]
        return [11, 12]

    def decode(self, ids, **kwargs):
        assert ids == [21, 2]
        return '{"probability":0.2}'


def receipts():
    raw = '{"probability":0.2}'
    request = {
        "call_id": "forecast-0",
        "execution_sha256": "execution",
        "dispatched_wall_ns": 1_000_000_000,
        "messages": [{"role": "user", "content": "fixture"}],
    }
    response = {
        "schema": "disastertrace.spool_response.v1",
        "call_id": "forecast-0",
        "request_sha256": "request",
        "execution_sha256": "execution",
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": 2,
        "output_tokens": 2,
        "compute_seconds": 0.1,
        "ended_with_eos": True,
        "worker_receipt_sha256": "worker",
    }
    worker = {k: v for k, v in response.items() if k not in {"schema", "worker_receipt_sha256"}}
    worker.update(
        input_ids=[11, 12],
        output_ids=[21, 2],
        origin="actual_local_vllm_TP4",
        wall_started_ns=1_100_000_000,
        finish_reason="stop",
        stop_reason=None,
    )
    delivered = {"observed_wall_ns": 1_300_000_000}
    return request, response, worker, delivered


def test_original_live_receipt_reconstructs_elapsed_delivery():
    assert AUDIT.check_response(*receipts(), TokenizerFixture(), rehearsal=False) == 0.3


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_tokens", 1),
        ("output_tokens", 1),
        ("compute_seconds", 0.5),
        ("compute_seconds", float("nan")),
        ("raw", "changed"),
        ("ended_with_eos", False),
    ],
)
def test_coordinated_worker_and_response_edits_still_fail_independent_checks(field, value):
    request, response, worker, delivered = copy.deepcopy(receipts())
    response[field] = worker[field] = value
    with pytest.raises(AssertionError):
        AUDIT.check_response(
            request, response, worker, delivered, TokenizerFixture(), rehearsal=False
        )


def test_program_rehearsal_cannot_be_claimed_as_actual_inference():
    request, response, worker, delivered = receipts()
    worker["origin"] = "engineering_program_rehearsal"
    with pytest.raises(AssertionError):
        AUDIT.check_response(
            request, response, worker, delivered, TokenizerFixture(), rehearsal=False
        )


def test_delivery_before_original_dispatch_is_rejected():
    request, response, worker, delivered = receipts()
    delivered["observed_wall_ns"] = 900_000_000
    with pytest.raises(AssertionError):
        AUDIT.check_response(
            request, response, worker, delivered, TokenizerFixture(), rehearsal=False
        )


def test_unfinished_but_consistently_recorded_generation_is_retained():
    request, response, worker, delivered = receipts()
    response["ended_with_eos"] = worker["ended_with_eos"] = False
    worker["finish_reason"] = "length"
    assert (
        AUDIT.check_response(
            request, response, worker, delivered, TokenizerFixture(), rehearsal=False
        )
        == 0.3
    )
