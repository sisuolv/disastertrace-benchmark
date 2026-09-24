import json

import pytest

from disastertrace.monitoring_v1.run_journal_v18 import RunJournal


def test_journal_persists_dispatch_before_response(tmp_path):
    journal = RunJournal(tmp_path / "run", run_id="OFFLINE-TEST-001", scope="CODE", config={"model": "stub"})
    journal.dispatch(request_id="r1", request_sha256="a" * 64, model="stub", settings={"max_tokens": 1})
    journal.response(request_id="r1", http_status=200, provider_model="stub", provider_request_id="id",
                     response_sha256="b" * 64, parse_status="valid")
    events = [json.loads(line) for line in (tmp_path / "run" / "events.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events] == ["REGISTERED", "DISPATCH_INTENT", "RESPONSE_RECEIVED"]


def test_journal_refuses_closed_dispatch_and_sensitive_config(tmp_path):
    with pytest.raises(ValueError, match="Sensitive"):
        RunJournal(tmp_path / "bad", run_id="OFFLINE-TEST-002", scope="CODE", config={"api_key": "x"})
    journal = RunJournal(tmp_path / "run", run_id="OFFLINE-TEST-003", scope="CODE", config={})
    journal.close(reason="offline")
    with pytest.raises(ValueError, match="CLOSED"):
        journal.dispatch(request_id="r1", request_sha256="a" * 64, model="stub", settings={})
