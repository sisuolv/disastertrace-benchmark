import json
from io import BytesIO
from urllib.error import HTTPError

import pytest


def setup(tmp_path, monkeypatch, response, count=1):
    from disastertrace.monitoring_v1 import api_capture_v2 as api
    from disastertrace.monitoring_v1.api_ledger import ApiLedger, call_spec

    messages = [{"role": "user", "content": "Return JSON"}]
    key = tmp_path / "key"
    key.write_text("fixture-secret")
    monkeypatch.setenv("DISASTERTRACE_DEEPSEEK_KEY_FILE", str(key))
    calls = [call_spec(str(i), messages, "deepseek-flash", input_cap=8192, max_tokens=512) for i in range(count)]
    ledger = ApiLedger.create(tmp_path / "ledger", calls, limit_nanodollars=100_000_000,
                              max_calls=count, deadline_wall_ns=9_999_999_999_999_999_999)

    class Response:
        status = 200

        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, cap): return response if isinstance(response, bytes) else json.dumps(response).encode()

    class Opener:
        def open(self, request, timeout):
            if isinstance(response, Exception): raise response
            return Response()

    monkeypatch.setattr(api, "build_opener", lambda *args: Opener())
    return api, ledger, messages


def valid_response():
    return {"usage": {"prompt_tokens": 20, "completion_tokens": 5}, "model": "fixture-model",
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}


def test_immutable_per_call_capture_and_exact_reduction(tmp_path, monkeypatch):
    api, ledger, messages = setup(tmp_path, monkeypatch, valid_response())
    raw, meta = api.capture(ledger, "0", messages)
    assert raw == "{}" and meta["input_tokens"] == 20
    before = ledger.reduce()
    assert before["settled"] == 1 and before["actual_upper_nanodollars"] == 12000
    with pytest.raises(FileExistsError): api.capture(ledger, "0", messages)
    assert ledger.reduce() == before
    assert "fixture-secret" not in (ledger.path / "contract.json").read_text()


def test_ledger_rejects_same_call_id_different_request_before_claim(tmp_path, monkeypatch):
    api, ledger, _messages = setup(tmp_path, monkeypatch, valid_response())
    with pytest.raises(ValueError, match="request"):
        api.capture(ledger, "0", [{"role": "user", "content": "Different"}])
    assert ledger.reduce()["claimed"] == 0


def test_response_survives_billing_write_failure_and_can_be_reconciled(tmp_path, monkeypatch):
    api, ledger, messages = setup(tmp_path, monkeypatch, valid_response())
    original = ledger.write

    def broken(call_id, name, data):
        if name == "billing.json": raise OSError("fixture bill failure")
        return original(call_id, name, data)

    monkeypatch.setattr(ledger, "write", broken)
    with pytest.raises(RuntimeError): api.capture(ledger, "0", messages)
    assert (ledger.attempt("0") / "response.raw").exists()
    assert (ledger.attempt("0") / "terminal.json").exists()
    assert ledger.reduce()["unresolved_reservations"] == 1
    monkeypatch.setattr(ledger, "write", original)
    ledger.reconcile("0")
    assert ledger.reduce()["reconciled"] == 1
    assert ledger.reduce()["unresolved_reservations"] == 0
    with pytest.raises(FileExistsError): ledger.reconcile("0")


@pytest.mark.parametrize("response", [b"\xff\xfe", b"{broken", {"choices": []}])
def test_bad_provider_envelope_preserves_wire_and_unknown_fee(tmp_path, monkeypatch, response):
    api, ledger, messages = setup(tmp_path, monkeypatch, response)
    with pytest.raises(RuntimeError): api.capture(ledger, "0", messages)
    assert (ledger.attempt("0") / "response.raw").exists()
    assert ledger.reduce()["unresolved_reservations"] == 1


def test_http_error_body_is_preserved_and_sanitized(tmp_path, monkeypatch):
    error = HTTPError("https://api.deepseek.com", 429, "limit", {}, BytesIO(b"fixture-secret"))
    api, ledger, messages = setup(tmp_path, monkeypatch, error)
    with pytest.raises(RuntimeError): api.capture(ledger, "0", messages)
    assert (ledger.attempt("0") / "error.raw").read_bytes() == b"[REDACTED]"
    assert ledger.reduce()["unresolved_reservations"] == 1


def test_preallocated_escrow_cannot_overbook_concurrent_calls(tmp_path):
    from disastertrace.monitoring_v1.api_ledger import ApiLedger, call_spec

    messages = [{"role": "user", "content": "JSON"}]
    calls = [call_spec(str(i), messages, "deepseek-flash", input_cap=8192, max_tokens=512) for i in range(10)]
    with pytest.raises(ValueError, match="budget"):
        ApiLedger.create(tmp_path / "ledger", calls, limit_nanodollars=1,
                         max_calls=10, deadline_wall_ns=9_999_999_999_999_999_999)


@pytest.mark.parametrize("receipt", ["reserve.json", "dispatch.json"])
def test_reducer_rejects_receipts_from_a_different_call(tmp_path, monkeypatch, receipt):
    api, ledger, messages = setup(tmp_path, monkeypatch, valid_response())
    api.capture(ledger, "0", messages)
    path = ledger.attempt("0") / receipt
    record = json.loads(path.read_text())
    record["call_id"] = "another-call"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="identity"):
        ledger.reduce()


def test_reduction_checks_bound_contract_before_accepting_bills(tmp_path, monkeypatch):
    api, ledger, messages = setup(tmp_path, monkeypatch, valid_response())
    api.capture(ledger, "0", messages)
    with (ledger.path / "contract.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="contract"):
        ledger.reduce()
