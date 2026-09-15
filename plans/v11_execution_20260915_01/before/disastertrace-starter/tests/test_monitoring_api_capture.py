import json
from urllib.error import HTTPError

import pytest

from disastertrace.monitoring_v1 import api_capture


def setup_capture(tmp_path, monkeypatch, response):
    key = tmp_path / "private.key"
    key.write_text("test-credential")
    monkeypatch.setenv("DISASTERTRACE_DEEPSEEK_KEY_FILE", str(key))
    ledger = tmp_path / "budget.json"
    ledger.write_text(json.dumps({"limit_nanodollars": 100_000_000, "max_calls": 1, "calls": {}}))

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return json.dumps(response).encode()[:limit]

    class Opener:
        def open(self, request, timeout):
            assert request.headers["Authorization"] == "Bearer test-credential"
            assert "test-credential" not in request.data.decode()
            if isinstance(response, Exception):
                raise response
            return Response()

    monkeypatch.setattr(api_capture, "build_opener", lambda *args: Opener())
    return api_capture.ApiBudget(ledger), tmp_path / "capture"


def invoke(budget, directory):
    return api_capture.capture([{"role": "user", "content": "Return JSON"}],
                               "deepseek-flash", "original", directory, budget)


def test_original_invalid_model_text_and_length_finish_are_retained(tmp_path, monkeypatch):
    response = {"usage": {"prompt_tokens": 20, "completion_tokens": 30}, "model": "provider-id",
                "choices": [{"finish_reason": "length", "message": {"content": "{bad JSON"}}]}
    budget, directory = setup_capture(tmp_path, monkeypatch, response)
    raw, details = invoke(budget, directory)
    assert raw == "{bad JSON"
    assert not details["ended_with_eos"]
    assert details["fee_upper_nanodollars"] == 42000
    saved = json.loads((directory / "RESPONSE.json").read_text())
    assert saved["body"] == response
    assert json.loads((directory / "RESPONSE.body").read_bytes()) == response
    assert saved["provider_compute_seconds"] is None
    assert "test-credential" not in (directory / "REQUEST.json").read_text()


def test_http_failure_is_one_unknown_attempt_with_no_retry(tmp_path, monkeypatch):
    from io import BytesIO

    error = HTTPError("https://api.deepseek.com", 503, "Unavailable", {}, BytesIO(b"temporary"))
    budget, directory = setup_capture(tmp_path, monkeypatch, error)
    with pytest.raises(RuntimeError, match="Original API attempt"):
        invoke(budget, directory)
    state = json.loads(budget.path.read_text())
    assert state["calls"]["original"]["status"] == "unknown"
    assert json.loads((directory / "FAILURE.json").read_text())["http_status"] == 503
    with pytest.raises(FileExistsError):
        invoke(budget, directory)


def test_missing_usage_never_releases_the_fee_reservation(tmp_path, monkeypatch):
    budget, directory = setup_capture(tmp_path, monkeypatch, {"choices": []})
    with pytest.raises(RuntimeError, match="Original API attempt"):
        invoke(budget, directory)
    assert json.loads(budget.path.read_text())["calls"]["original"]["status"] == "unknown"
    assert json.loads((directory / "RESPONSE.body").read_bytes()) == {"choices": []}


def test_received_answer_survives_a_later_billing_failure(tmp_path, monkeypatch):
    response = {"usage": {"prompt_tokens": 20, "completion_tokens": 5}, "model": "provider-id",
                "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]}
    b, directory = setup_capture(tmp_path, monkeypatch, response)
    original = b.transact

    def failing_settlement(call_id, reserve=None, *, actual=None, outcome=None):
        if actual is not None:
            raise TimeoutError("Simulated ledger timeout")
        return original(call_id, reserve, outcome=outcome)

    monkeypatch.setattr(b, "transact", failing_settlement)
    with pytest.raises(RuntimeError, match="Original API attempt"):
        invoke(b, directory)
    assert json.loads((directory / "RESPONSE.body").read_bytes()) == response
    assert json.loads((directory / "RESPONSE.json").read_text())["body"] == response
    assert json.loads(b.path.read_text())["calls"]["original"]["status"] == "unknown"
