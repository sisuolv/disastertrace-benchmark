"""Fault injection through actual production spool, controller and resource ledger."""

import copy
import hashlib
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_monitoring_v13_selector import config_fixture

from disastertrace.monitoring_v1 import api_transport_v2 as api
from disastertrace.monitoring_v1.production import ProductionSpoolBackend
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import digest, read


def fixture(tmp_path, **changes):
    authority = tmp_path / "authority"; authority.mkdir()
    spool = tmp_path / "spool"; spool.mkdir()
    artifact = tmp_path / "bound.txt"; artifact.write_text("transport test fixture")
    policy = {"version":api.VERSION, "model":"fixture-model", "base_url":"https://invalid.test/v1",
              "input_cap":32768, "output_cap":512, "read_limit_bytes":4000,
              "deadline_wall_ns":time.time_ns()+60_000_000_000,
              "authority_directory":str(authority), "stop_path":str(tmp_path/"STOP.json"),
              "dispatch_authority":"single_local_authority", "allowed_call_ids":["select-0"], **changes}
    contract = {k:{} for k in ("model","weights","tokenizer","adapter","generation","runtime")}
    contract["api_transport_v2"] = policy
    backend = ProductionSpoolBackend(spool, contract, run_id="api-v2-fixture",
                                    bound_files={str(artifact):digest(artifact)})
    data, bank, config = config_fixture(model_call_budget=1,
        input_token_cap=32768, output_token_cap=512, token_cap=65536,
        failure_continuation_policy="skip_failed_call_continue_v1", execution_mode="production_bound_v1",
        pending_timing_policy="lifecycle_wall_v1")
    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step(); saved = session.persist(tmp_path / "checkpoint.json")
    pending = saved["payload"]["pending_selector"]
    return session, backend, pending, data, bank


def body(**changes):
    return json.dumps({"model":"fixture-model", "usage":{"prompt_tokens":10,"completion_tokens":10},
                       "choices":[{"message":{"content":'{"query_order":[]}'}, "finish_reason":"stop"}],
                       **changes}).encode()


def prepare(payload, policy, credential_path):
    return payload, (b"secret-string",)


def deliver(backend, pending, **kwargs):
    return api.deliver(backend, pending["call_id"], credential_path="unused-test-only",
                       prepare=kwargs.pop("prepare",prepare),
                       send=kwargs.pop("send",lambda *_:(200,body(),True)), **kwargs)


def broken_publication(name):
    if name == "after_capture_before_publication": raise OSError("injected publication failure")


def anchor(backend):
    return digest(next(__import__('pathlib').Path(backend.execution_contract["api_transport_v2"]["authority_directory"]).glob("*.capture_anchor.json")))


def test_recovered_capture_resolves_in_production_and_settles_once(tmp_path):
    session, backend, pending, _, _ = fixture(tmp_path)
    with pytest.raises(OSError): deliver(backend,pending,hook=broken_publication)
    failure = next(backend.directory.glob("*.failure.json")); original = failure.read_bytes()
    trusted = anchor(backend)
    api.reconcile_capture(backend,pending["call_id"],trusted_anchor_sha256=trusted)
    first = next(backend.directory.glob("*.reconciliation.json")).read_bytes()
    api.reconcile_capture(backend,pending["call_id"],trusted_anchor_sha256=trusted)
    assert next(backend.directory.glob("*.reconciliation.json")).read_bytes() == first
    assert backend.resolve(pending["ticket"],pending["call_id"])[0] == '{"query_order":[]}'
    report = session.finish()
    assert report["selector_calls"][0]["response_error"] is None
    assert report["resource_spent"]["tokens"] == 20 and report["resource_reserved"]["tokens"] == 0
    assert len([e for e in report["resource_events"] if e["event"] == "completed" and e["receipt_id"] == pending["call_id"]]) == 1
    assert failure.read_bytes() == original


def test_late_recovery_changes_costs_but_cannot_reopen_old_forecasts(tmp_path):
    session, backend, pending, _, _ = fixture(tmp_path)
    with pytest.raises(OSError): deliver(backend,pending,hook=broken_publication)
    failed = session.finish(); predictions = copy.deepcopy(failed["snapshots"])
    assert failed["resource_reserved"]["tokens"] > 0
    api.reconcile_capture(backend,pending["call_id"],trusted_anchor_sha256=anchor(backend))
    receipt = api.cost_reconciliation(backend,pending,observed_at=session.snapshot()["payload"]["clock"])
    updated = session.reconcile_costs([receipt])
    assert session.reconcile_costs([receipt]) == updated
    report = session.finish()
    assert report["snapshots"] == predictions
    assert report["resource_reserved"]["tokens"] == 0 and report["resource_spent"]["tokens"] == 20


@pytest.mark.parametrize("where", ["credential", "before_permit", "intent_io"])
def test_expiry_after_preparation_or_intent_prevents_send(tmp_path, monkeypatch, where):
    _,backend,pending,_,_ = fixture(tmp_path)
    deadline = backend.execution_contract["api_transport_v2"]["deadline_wall_ns"]
    sent = []
    def expire(): monkeypatch.setattr(api.time,"time_ns",lambda:deadline+1)
    def prep(*args):
        if where == "credential": expire()
        return prepare(*args)
    original = api.publish
    def slow_io(path,value):
        original(path,value)
        if where == "intent_io" and path.name.endswith(".api_intent.json"): expire()
    monkeypatch.setattr(api,"publish",slow_io)
    with pytest.raises(ValueError,match="permit"):
        deliver(backend,pending,prepare=prep,hook=lambda n:expire() if where == n else None,
                send=lambda *_:sent.append(True))
    assert not sent
    assert read(next(backend.directory.glob("*.failure.json")))["remote_execution"] == "not_sent"


@pytest.mark.parametrize("stage,sends", [("before_permit",0),("after_permit",1)])
def test_stop_has_an_explicit_local_permit_boundary(tmp_path,stage,sends):
    _,backend,pending,_,_ = fixture(tmp_path)
    sent=[]
    def send(*_): sent.append(True); return 200,body(),True
    def hook(name):
        if name == stage: api.request_stop(backend)
    if sends:
        deliver(backend,pending,hook=hook,send=send)
    else:
        with pytest.raises(ValueError,match="STOP"):deliver(backend,pending,hook=hook,send=send)
    assert len(sent) == sends


def test_original_claim_blocks_second_worker_and_unknown_is_never_resent(tmp_path):
    session,backend,pending,_,_ = fixture(tmp_path)
    calls=[]
    def send(*_): calls.append(True); raise TimeoutError("remote outcome unknown")
    with pytest.raises(TimeoutError): deliver(backend,pending,send=send)
    with pytest.raises(FileExistsError): deliver(backend,pending,send=send)
    assert len(calls) == 1
    assert session.finish()["resource_reserved"]["tokens"] > 0


@pytest.mark.parametrize("stage", ["after_permit", "after_http_before_capture"])
def test_crash_without_capture_cannot_invent_recovery(tmp_path,stage):
    session,backend,pending,_,_ = fixture(tmp_path)
    def crash(name):
        if name == stage: raise OSError("injected crash")
    with pytest.raises(OSError):deliver(backend,pending,hook=crash)
    assert not list(backend.directory.glob("*.response.json"))
    with pytest.raises((ValueError,FileNotFoundError)):
        api.reconcile_capture(backend,pending["call_id"],trusted_anchor_sha256="0"*64)
    assert session.finish()["resource_reserved"]["tokens"] > 0


@pytest.mark.parametrize("tamper", ["capture", "capture_and_local_hash", "anchor", "intent", "wrong_trusted_hash"])
def test_first_reconciliation_verifies_external_anchor(tmp_path,tamper):
    _,backend,pending,_,_ = fixture(tmp_path)
    with pytest.raises(OSError):deliver(backend,pending,hook=broken_publication)
    trusted=anchor(backend)
    if tamper in {"capture","capture_and_local_hash"}:
        path=next(backend.directory.glob("*.api_capture.json")); value=read(path)
        value["stored_body_base64"]="e30="
        if tamper == "capture_and_local_hash":value["stored_body_sha256"]=hashlib.sha256(b"{}").hexdigest()
        path.write_text(json.dumps(value))
    elif tamper == "anchor":
        path=next((tmp_path/"authority").glob("*.capture_anchor.json")); value=read(path)
        value["capture_sha256"]="0"*64; path.write_text(json.dumps(value))
    elif tamper == "intent":
        path=next(backend.directory.glob("*.api_intent.json")); value=read(path)
        value["attempts"]=2; path.write_text(json.dumps(value))
    else:trusted="0"*64
    with pytest.raises(ValueError):api.reconcile_capture(backend,pending["call_id"],trusted_anchor_sha256=trusted)
    assert not list(backend.directory.glob("*.response.json"))


@pytest.mark.parametrize("wire,eof", [(b'\xff',True), (b"x"*4001,False),
    (body(model="wrong-model"),True), (body(usage={"prompt_tokens":True,"completion_tokens":10}),True),
    (body(usage={"prompt_tokens":10,"completion_tokens":513}),True), (body(),False)])
def test_invalid_wire_response_keeps_capture_failure_and_reservation(tmp_path,wire,eof):
    session,backend,pending,_,_ = fixture(tmp_path)
    with pytest.raises(ValueError):deliver(backend,pending,send=lambda *_:(200,wire,eof))
    assert list(backend.directory.glob("*.api_capture.json"))
    assert not list(backend.directory.glob("*.response.json"))
    assert session.finish()["resource_reserved"]["tokens"] > 0


def test_redaction_cannot_hide_original_truncation():
    raw=b"secret-string"*308
    raw=raw[:4001]
    record=api.capture_bytes(raw,eof=False,limit=4000,secrets=(b"secret-string",))
    assert record["truncated"] and not record["complete"]
    assert record["raw_full_body_sha256"] is None
    assert record["raw_prefix_length"] == 4001
    assert record["raw_prefix_sha256"] != record["stored_body_sha256"]


def test_bounded_read_proves_eof_and_handles_short_reads():
    class Short(io.BytesIO):
        def read(self,n=-1): return super().read(min(n,3))
    assert api.read_bounded(Short(b"x"*10),10) == (b"x"*10,True)
    assert api.read_bounded(Short(b"x"*11),10) == (b"x"*11,False)


def test_concurrent_workers_have_one_claim_and_one_http_attempt(tmp_path):
    _,backend,pending,_,_=fixture(tmp_path)
    started,release=Event(),Event();sent=[]
    def send(*_):
        sent.append(True);started.set()
        if not release.wait(5):raise TimeoutError("test worker did not release")
        return 200,body(),True
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(deliver,backend,pending,send=send)
        assert started.wait(5)
        try:
            second=pool.submit(deliver,backend,pending,send=send)
            with pytest.raises(FileExistsError):second.result(timeout=5)
        finally:release.set()
        first.result(timeout=5)
    assert len(sent)==1


def test_production_rejects_tampered_reconciliation_receipt(tmp_path):
    _,backend,pending,_,_=fixture(tmp_path)
    with pytest.raises(OSError):deliver(backend,pending,hook=broken_publication)
    api.reconcile_capture(backend,pending["call_id"],trusted_anchor_sha256=anchor(backend))
    path=next(backend.directory.glob("*.reconciliation.json"));value=read(path)
    value["failure_sha256"]="0"*64;path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match="reconciliation"):
        backend.resolve(pending["ticket"],pending["call_id"])
