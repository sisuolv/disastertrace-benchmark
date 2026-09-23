"""Offline transport faults must retain the original response without new HTTP."""
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import pytest

from disastertrace.monitoring_v1.spool_backend import publish, read


@pytest.fixture
def worker():
    path=Path(__file__).resolve().parents[2]/"plans/v12_execution_20260915_01/siliconflow_worker.py"
    spec=importlib.util.spec_from_file_location("siliconflow_test_worker",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def fixture(tmp_path):
    class Spool:
        directory=tmp_path

        def _key(self,call_id):
            return call_id

        def claim_ready(self,call_id,*,worker_id):
            publish(self.directory/(call_id+".claim.json"),{"worker_id":worker_id})
            return read(self.directory/(call_id+".request.json"))
    publish(tmp_path/"select-0.request.json",{"call_id":"select-0","execution_sha256":"a"*64,
        "messages":[{"role":"user","content":"Synthetic transport fixture"}]})
    policy={"model":"synthetic-model","allowed_call_ids":["select-0"],"input_cap":8192,"output_cap":512,
        "deadline_wall_ns":time.time_ns()+60_000_000_000}
    sent=[]
    def send(payload,policy):
        sent.append(payload)
        body=json.dumps({"model":"synthetic-model","usage":{"prompt_tokens":20,"completion_tokens":10},
            "choices":[{"finish_reason":"stop","message":{"content":"{\"query_order\":[],\"forecast_handles\":[]}"}}]}).encode()
        return 200,body,hashlib.sha256(body).hexdigest(),False
    return Spool(),policy,send,sent


def test_original_request_is_delivered_once_and_can_be_reconciled_without_http(tmp_path,worker):
    backend,policy,send,sent=fixture(tmp_path)
    response=worker.deliver(backend,"select-0",policy,send=send)
    assert worker.reconcile_capture(backend,"select-0",policy)==response
    assert response["input_tokens"]==20 and len(sent)==1
    with pytest.raises(FileExistsError):
        worker.deliver(backend,"select-0",policy,send=send)
    assert len(sent)==1


def test_publication_failure_preserves_recoverable_wire_and_failure_identity(tmp_path,worker,monkeypatch):
    backend,policy,send,sent=fixture(tmp_path)
    original=worker.publish
    def interrupted(path,value):
        if str(path).endswith(".worker.json"):
            raise OSError("synthetic persistence interruption")
        return original(path,value)
    monkeypatch.setattr(worker,"publish",interrupted)
    with pytest.raises(OSError):
        worker.deliver(backend,"select-0",policy,send=send)
    assert (tmp_path/"select-0.api_capture.json").exists()
    failure=read(tmp_path/"select-0.failure.json")
    monkeypatch.setattr(worker,"publish",original)
    worker.reconcile_capture(backend,"select-0",policy)
    assert read(tmp_path/"select-0.failure.json")==failure
    assert len(sent)==1


@pytest.mark.parametrize("fault",["model","usage","http"])
def test_provider_mismatch_keeps_capture_and_no_success_response(tmp_path,worker,fault):
    backend,policy,send,sent=fixture(tmp_path)
    def faulty(payload,policy):
        status,body,_,redacted=send(payload,policy)
        data=json.loads(body)
        if fault=="model": data["model"]="wrong-model"
        if fault=="usage": data["usage"]["prompt_tokens"]=True
        if fault=="http": status=429
        body=json.dumps(data).encode()
        return status,body,hashlib.sha256(body).hexdigest(),redacted
    with pytest.raises(ValueError):
        worker.deliver(backend,"select-0",policy,send=faulty)
    assert (tmp_path/"select-0.api_capture.json").exists()
    assert (tmp_path/"select-0.failure.json").exists()
    assert not (tmp_path/"select-0.response.json").exists()


def test_unknown_call_cannot_dispatch(tmp_path,worker):
    backend,policy,send,sent=fixture(tmp_path)
    with pytest.raises(ValueError):
        worker.deliver(backend,"select-1",policy,send=send)
    assert sent==[]
