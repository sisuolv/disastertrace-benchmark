import copy
from datetime import datetime, timezone
import json

import pytest

from disastertrace.revision_v1.pilot_v17 import provider, runner
from disastertrace.revision_v1.pilot_v17.agent_view import initial_state, schema_example


@pytest.fixture
def broker(tmp_path, monkeypatch):
    obj = provider.Broker(tmp_path, "SYNTHETIC-NOT-A-CREDENTIAL")
    obj.calls = []
    def response(suffix, body=None):
        obj.calls.append(copy.deepcopy(body))
        return {"http_status": 200, "provider_response": {"choices": []}, "latency_s": 0.1}
    monkeypatch.setattr(obj, "_http", response)
    return obj


def query(stage="smoke", identity="smoke:0"):
    return {"command": "chat", "stage": stage, "logical_id": identity,
            "payload": {"model": provider.MODELS[0], "messages": [], "stream": False, "max_tokens": 4096}}


def test_capture_reuse_and_identity_mismatch(broker):
    first = broker.handle(query())
    second = broker.handle(query())
    assert second["reused_capture"] and first["request_sha256"] == second["request_sha256"]
    assert len(broker.calls) == 1 and broker.handle({"command": "status"})["total_attempts"] == 1
    changed = query()
    changed["payload"]["max_tokens"] = 2048
    with pytest.raises(ValueError, match="different input"):
        broker.handle(changed)


def test_pending_attempt_is_not_resent(broker):
    request = query()
    row = {"logical_id": request["logical_id"], "stage": "smoke",
           "request_sha256": provider.digest(request["payload"])}
    provider.append_json(broker.run / "attempts.jsonl", row)
    recovered = provider.Broker(broker.run, "fake")
    result = recovered.handle(request)
    assert result["status"] == "UNRESOLVED_PRIOR_ATTEMPT" and not result["resend_allowed"]
    assert recovered.counts["smoke"] == 1


def test_attempt_caps_and_no_secret_persistence(broker):
    for index in range(12):
        broker.handle(query(identity=f"smoke:{index}"))
    with pytest.raises(ValueError, match="cap reached"):
        broker.handle(query(identity="smoke:13"))
    assert len(broker.calls) == 12
    for name in ("attempts.jsonl", "responses.jsonl"):
        assert broker.secret not in (broker.run / name).read_text()
    broker.counts = {"smoke": 12, "main": 432, "e2": 108, "e3": 24, "retry": 24}
    with pytest.raises(ValueError, match="cap reached"):
        broker.handle(query("main", "main:after-total-cap"))


def test_real_stage_requires_lock(broker):
    with pytest.raises(ValueError, match="not locked"):
        broker.handle(query("main", "main:0"))
    assert broker.calls == []


@pytest.mark.parametrize("status", [None, 400, 401, 403, 200])
def test_nonretryable_result_cannot_retry(broker, monkeypatch, status):
    (broker.run / "PROTOCOL_LOCK.json").write_text("{}")
    monkeypatch.setattr(broker, "_http", lambda *args: {"http_status": status, "provider_response": None})
    broker.handle(query())
    retry = query("retry", "retry:smoke:0")
    retry["retry_of"] = "smoke:0"
    with pytest.raises(ValueError, match="explicit retryable"):
        broker.handle(retry)
    assert sum(broker.counts.values()) == 1


def test_explicit_http_retry_is_counted_and_limited(broker, monkeypatch):
    (broker.run / "PROTOCOL_LOCK.json").write_text("{}")
    monkeypatch.setattr(broker, "_http", lambda *args: {"http_status": 503, "provider_response": None})
    broker.handle(query())
    retry = query("retry", "retry:smoke:0")
    retry["retry_of"] = "smoke:0"
    broker.handle(retry)
    retry["logical_id"] = "retry:second"
    with pytest.raises(ValueError, match="one retry"):
        broker.handle(retry)
    assert broker.counts["smoke"] == broker.counts["retry"] == 1


def test_dispatch_cutoff_prevents_api_call(tmp_path, monkeypatch):
    (tmp_path / "protocol.json").write_text(json.dumps({"deadline_at": "2000-01-01T00:00:00Z"}))
    def forbidden(*args, **kwargs):
        pytest.fail("expired dispatch reached provider")
    monkeypatch.setattr(runner, "call_broker", forbidden)
    with pytest.raises(TimeoutError):
        runner.execute_one(tmp_path, "smoke", "smoke:expired", provider.MODELS[0],
                           runner.synthetic_views()[0], "FRESH", initial_state(), {})
    runner.check_dispatch_window(tmp_path, now=datetime(1999, 12, 31, tzinfo=timezone.utc))


def test_locked_source_tampering_is_rejected(tmp_path):
    path = tmp_path / "source.txt"
    path.write_text("original")
    import hashlib
    (tmp_path / "PROTOCOL_LOCK.json").write_text(json.dumps({"file_sha256": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()}}))
    runner.verify_lock(tmp_path)
    path.write_text("changed")
    with pytest.raises(ValueError, match="locked input/source changed"):
        runner.verify_lock(tmp_path)


def test_mock_capture_is_validated_without_repair(tmp_path, monkeypatch):
    (tmp_path / "protocol.json").write_text(json.dumps({"deadline_at": "2099-01-01T00:00:00Z"}))
    view = runner.synthetic_views()[0]
    before = initial_state()
    commit = schema_example(view, before)
    source = view["evidence"][0]["source_id"]
    commit["evidence_ids"] = [source]
    fact = commit["fact_updates"][0]
    fact["source_ids"] = [source]
    fact["value"] = {"active_source_ids": [source], "valid_start": "2023-01-10T10:00:00Z",
                     "valid_end": "2023-01-11T12:00:00Z", "relation_status": "RESOLVED"}
    commit["forecast_updates"][0]["event_probability"] = 0.1
    monkeypatch.setattr(runner, "call_broker", lambda *args, **kwargs: {
        "logical_id": kwargs["logical_id"], "http_status": 200,
        "provider_response": {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(commit)}}]}})
    record = runner.execute_one(tmp_path, "smoke", "smoke:mock", provider.MODELS[0], view,
                                "FRESH", before, {"stream": False, "max_tokens": 4096})
    assert record["validation"]["valid"] and record["after"]["probability"] == 0.1
    assert before == initial_state() and record["before"] == before


def test_main_independent_states_and_resume(tmp_path, monkeypatch):
    (tmp_path / "protocol.json").write_text('{"readset_path":"synthetic-readset"}')
    provider.append_json(tmp_path / "episodes.jsonl", {"episode_id": "synthetic-episode"})
    lock = {"enabled_models": ["synthetic-model"], "settings_by_model": {"synthetic-model": {}}}
    monkeypatch.setattr(runner, "verify_lock", lambda run: lock)
    monkeypatch.setattr(runner, "readset_rows", lambda path: [])
    monkeypatch.setattr(runner, "install_guard", lambda rows: None)
    monkeypatch.setattr(runner, "NativeReader", lambda path: None)
    monkeypatch.setattr(runner, "public_view", lambda e, i, reader: {"episode_id": e["episode_id"], "index": i})
    seen = []
    def execute(run, stage, logical_id, model, view, arm, before, settings, **kwargs):
        seen.append((arm, view["index"], copy.deepcopy(before)))
        after = copy.deepcopy(before)
        after["fact_state"] = {"arm": arm, "index": view["index"]}
        return {"logical_id": logical_id, "before": copy.deepcopy(before), "after": after,
                "validation": {"valid": True, "errors": []}}
    monkeypatch.setattr(runner, "execute_one", execute)
    assert runner.run_main(tmp_path, 2) == {"completed": 6, "expected": 6}
    for arm, index, before in seen:
        assert before["fact_state"] == (None if index == 0 else {"arm": arm, "index": index - 1})
    assert runner.run_main(tmp_path, 2) == {"completed": 6, "expected": 6}
    assert len(seen) == 6
