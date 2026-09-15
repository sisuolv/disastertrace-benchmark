import json
from io import BytesIO
from urllib.error import HTTPError

import pytest
from test_monitoring_api_capture import invoke, setup_capture

from disastertrace.monitoring_v1.process_split import chronological_roles, process_components
from disastertrace.monitoring_v1.selection import parse_selection


@pytest.mark.parametrize("field", ["query_order", "forecast_handles"])
def test_selector_duplicate_fields_are_rejected(field):
    raw = '{"query_order":[],"forecast_handles":[],"' + field + '":[]}'
    with pytest.raises(ValueError, match="duplicate"):
        parse_selection(raw, query_handles=[], target_handles=[], forecast_cap=1)


@pytest.mark.parametrize("fn", [chronological_roles, process_components])
@pytest.mark.parametrize("lo,hi", [(8, 2), (2, 2), (True, 2), (0, float("inf"))])
def test_both_process_entrypoints_reject_invalid_footprints(fn, lo, hi):
    rows = [{"opportunity_id": "a", "footprint_start": lo, "footprint_end": hi}]
    with pytest.raises(ValueError, match="footprint"):
        fn(rows, {"fit": (0, 10)}) if fn is chronological_roles else fn(rows)


def test_chronological_roles_reject_duplicate_opportunities():
    row = {"opportunity_id": "a", "footprint_start": 0, "footprint_end": 2}
    with pytest.raises(ValueError, match="Duplicate"):
        chronological_roles([row, dict(row)], {"fit": (0, 10)})


def test_capture_failure_receipt_survives_both_ledger_updates_failing(tmp_path, monkeypatch):
    response = {"usage": {"prompt_tokens": 20, "completion_tokens": 5}, "model": "fixture",
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
    budget, directory = setup_capture(tmp_path, monkeypatch, response)
    original = budget.transact

    def blocked(call_id, reserve=None, **kwargs):
        if reserve is not None:
            return original(call_id, reserve)
        raise TimeoutError("fixture: both ledger mutations unavailable")

    monkeypatch.setattr(budget, "transact", blocked)
    with pytest.raises(RuntimeError, match="Original API attempt"):
        invoke(budget, directory)
    assert json.loads((directory / "RESPONSE.body").read_bytes()) == response
    failure = json.loads((directory / "FAILURE.json").read_text())
    assert failure["error_type"] == "TimeoutError"
    assert json.loads(budget.path.read_text())["calls"]["original"]["status"] == "reserved"


def test_capture_http_body_read_failure_has_terminal_receipt(tmp_path, monkeypatch):
    class BrokenError(HTTPError):
        def read(self, limit):
            raise OSError("fixture: broken error stream")

    error = BrokenError("https://api.deepseek.com", 503, "Unavailable", {}, BytesIO())
    budget, directory = setup_capture(tmp_path, monkeypatch, error)
    with pytest.raises(RuntimeError, match="Original API attempt"):
        invoke(budget, directory)
    failure = json.loads((directory / "FAILURE.json").read_text())
    assert failure["http_status"] == 503
    assert failure["error_body_read_error"] == "OSError"


def test_capture_retains_sanitized_http_error_body(tmp_path, monkeypatch):
    error = HTTPError("https://api.deepseek.com", 429, "Limit", {},
                      BytesIO(b"limit test-credential"))
    budget, directory = setup_capture(tmp_path, monkeypatch, error)
    with pytest.raises(RuntimeError):
        invoke(budget, directory)
    assert (directory / "ERROR.body").read_bytes() == b"limit [REDACTED]"
