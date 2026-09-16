"""Gated dispatch and real production consumption with mocked HTTP only."""

import copy
import json
import time

import pytest
from test_monitoring_v13_selector import config_fixture

from disastertrace.monitoring_v1 import api_transport_v2 as transport
from disastertrace.monitoring_v1.production import ProductionSpoolBackend
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import digest, read
from model_run import drive_controller, gate_decision, response_audit


def gate_inputs():
    return [{"passed":True,"completed_cases":168},
        {"passed":True,"completed_new_method_days":72,"registered_opportunities":864},
        {"passed":True,"valid_outputs":12},{"passed":True},
        {"passed":True,"calls_reproduced":864,"paid_asset_calls":400},
        {"rows":[{"left":"B11_COVERAGE","right":"B11_FIXED_HASH",
                  "same_acquisition_sequence":False,"same_probabilities":False,"mean_gain":-0.1}]}]


def test_negative_skill_does_not_block_a_qualified_model_comparison():
    assert gate_decision(*gate_inputs())["qualified"]


@pytest.mark.parametrize("i",range(5))
def test_no_dispatch_gate_on_failed_dependency(i):
    inputs=gate_inputs();inputs[i]["passed"]=False
    assert not gate_decision(*inputs)["qualified"]


def test_different_query_names_alone_do_not_establish_forecast_non_equivalence():
    inputs=gate_inputs();inputs[-1]["rows"][0]["same_probabilities"]=True
    result=gate_decision(*inputs)
    assert not result["qualified"] and not result["all_legal_paths_equivalent_proven"]


def test_unconsumed_paid_information_cannot_qualify():
    inputs=gate_inputs();inputs[-2]["paid_asset_calls"]=0
    assert not gate_decision(*inputs)["qualified"]


@pytest.mark.parametrize("change",[{"completed_new_method_days":71},{"registered_opportunities":863}])
def test_full_program_denominator_required(change):
    inputs=gate_inputs();inputs[1].update(change)
    assert not gate_decision(*inputs)["qualified"]


def controller(tmp_path):
    authority=tmp_path/"authority";authority.mkdir()
    spool=tmp_path/"spool";spool.mkdir()
    checkpoints=tmp_path/"checkpoints";checkpoints.mkdir()
    bound=tmp_path/"bound.txt";bound.write_text("mocked HTTP qualification only")
    policy={"version":transport.VERSION,"model":"fixture-model","base_url":"https://invalid.test/v1",
        "input_cap":32768,"output_cap":512,"read_limit_bytes":4000,"deadline_wall_ns":time.time_ns()+120_000_000_000,
        "authority_directory":str(authority),"stop_path":str(tmp_path/"STOP.json"),
        "dispatch_authority":"single_local_authority","allowed_call_ids":["select-0","select-1"]}
    spec={k:{} for k in ("model","weights","tokenizer","adapter","generation","runtime")}
    spec["api_transport_v2"]=policy
    backend=ProductionSpoolBackend(spool,spec,run_id="m01-offline-two-ticks",bound_files={str(bound):digest(bound)})
    data,bank,config=config_fixture(model_call_budget=2,input_token_cap=32768,output_token_cap=512,token_cap=66560,
        failure_continuation_policy="skip_failed_call_continue_v1",execution_mode="production_bound_v1",
        pending_timing_policy="lifecycle_wall_v1")
    return SessionCoordinator(data,bank,config,backend=backend),backend,checkpoints,data


@pytest.mark.parametrize("kind",["valid","invalid","unknown"])
def test_two_real_production_ticks_complete_with_failures_in_denominator(tmp_path,kind):
    session,api,checkpoints,data=controller(tmp_path);sent=[]
    def send(payload,limit):
        sent.append(payload)
        if kind=="unknown" and len(sent)==1:raise TimeoutError("injected unknown provider execution")
        raw="malformed" if kind=="invalid" and len(sent)==1 else '{"query_order":[]}'
        body=json.dumps({"model":"fixture-model","usage":{"prompt_tokens":10,"completion_tokens":10},
            "choices":[{"message":{"content":raw},"finish_reason":"stop"}]}).encode()
        return 200,body,True
    def dispatch(api,call,*,credential_path):
        return transport.deliver(api,call,credential_path="unused",prepare=lambda p,*_:(p,()),send=send)
    execution=drive_controller(session,api,checkpoints,dispatch=dispatch)
    assert len(sent)==2 and len(execution["dispatched_call_ids"])==2
    report=session.finish()
    assert len(report["snapshots"])==len(data["opportunities"])
    audit=response_audit(api,report)
    assert audit["passed"] and audit["HTTP_intents"]==2
    assert audit["schema_valid"]==(2 if kind=="valid" else 1)
    assert (report["resource_reserved"]["tokens"]>0)==(kind=="unknown")
    assert audit["requests_without_usage"]==(1 if kind=="unknown" else 0)
    if kind!="unknown":assert not execution["transport_failures"]


def test_durable_capture_tampering_fails_independent_audit(tmp_path):
    session,api,checkpoints,_=controller(tmp_path)
    def dispatch(api,call,*,credential_path):
        body=json.dumps({"model":"fixture-model","usage":{"prompt_tokens":10,"completion_tokens":10},
            "choices":[{"message":{"content":'{"query_order":[]}'},"finish_reason":"stop"}]}).encode()
        return transport.deliver(api,call,credential_path="unused",prepare=lambda p,*_:(p,()),send=lambda *_:(200,body,True))
    drive_controller(session,api,checkpoints,dispatch=dispatch)
    report=copy.deepcopy(session.finish())
    p=next(api.directory.glob("*.api_capture.json"));value=read(p);value["http_status"]=201
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError):response_audit(api,report)
