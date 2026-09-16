"""Query-only selection through the real controller and durable resume path."""

import json

import pytest
from test_monitoring_forecast_schedule import scheduled, expected_schedule
from test_monitoring_committed_spool import response

from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import CommittedSpoolBackend


def config_fixture(**changes):
    return scheduled(selector_kind="llm", authorization_mode="session_shared",
                     selector_contract_version="selector_query_only.v2", **changes)


def test_query_only_response_reaches_controller_and_keeps_fixed_forecasts():
    data, bank, config = config_fixture()
    def backend(system, request, call_id):
        assert '"forecast_handles"' not in system
        assert request["selector_contract_version"] == "selector_query_only.v2"
        return json.dumps({"query_order": list(request["queries"])}), {
            "input_tokens": 10, "output_tokens": 10, "seconds": .001, "ended_with_eos": True}
    report = run_session(data, bank, config, backend=backend)
    assert report["selector_calls"]
    assert all(c["response_error"] is None for c in report["selector_calls"])
    assert [(c["opportunity_id"],c["started_at"]) for c in report["calls"]] == expected_schedule(data, config)


@pytest.mark.parametrize("raw", ['{"query_order":["q0","q0"]}', '{"query_order":["no"]}',
    '{"query_order":[],"forecast_handles":[]}', '{"query_order":[],"query_order":[]}',
    '{"query_order":false}', '{"query_order":[1]}', '```json\n{"query_order":[]}\n```',
    'I refuse', '{"query_order": [', '{"query_order": [], "x": 1}'])
def test_strict_parser_rejects_malformed_or_legacy_outputs(raw):
    from disastertrace.monitoring_v1.selector_contract_v2 import parse_query_only
    with pytest.raises(ValueError):
        parse_query_only(raw, ["q0", "q1"])


@pytest.mark.parametrize("handles,selected", [([],[]), (["q0"],[]), (["q0"],["q0"]),
    (["q0","q1"],["q1","q0"]), (["q0","q1"],["q1"]),
    ([f"q{i}" for i in range(1000)], [f"q{i}" for i in range(1000)])])
def test_prompt_schema_parser_share_one_contract(handles, selected):
    from disastertrace.monitoring_v1.selector_contract_v2 import contract, parse_query_only, to_internal
    spec = contract(handles)
    value = {"query_order":selected}
    assert spec["provider_schema"]["json_schema"]["schema"] == spec["logical_schema"]
    assert spec["logical_schema"]["required"] == ["query_order"]
    assert spec["logical_schema"]["additionalProperties"] is False
    assert parse_query_only(json.dumps(value), handles) == value
    assert to_internal(value) == {**value, "forecast_handles":[]}
    assert spec["logical_schema"]["properties"]["query_order"]["maxItems"] == len(handles)
    assert '"enum": []' not in json.dumps(spec)


def test_pending_v2_resume_binds_new_prompt_and_charges_once(tmp_path):
    spec = {k:{} for k in ("model","weights","tokenizer","adapter","generation","runtime")}
    backend = CommittedSpoolBackend(tmp_path, spec, run_id="selector-v2")
    data, bank, config = config_fixture(model_call_budget=1)
    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step()
    record = session.persist(tmp_path / "checkpoint.json")
    pending = record["payload"]["pending_selector"]
    backend.claim_ready(pending["call_id"], worker_id="original")
    response(backend, pending, '{"query_order":[]}')
    report = SessionCoordinator.restore(record, data, bank, backend=backend).finish()
    assert report["selector_calls"][0]["response_error"] is None
    assert report["resource_spent"]["tokens"] == 20
    assert report["resource_reserved"]["tokens"] == 0


@pytest.mark.parametrize("changes", [{"predictor_kind":"llm"},{"forecast_schedule":None},
                                     {"selector_contract_version":"unknown"}])
def test_v2_rejects_incompatible_or_unknown_mode(changes):
    data, bank, config = config_fixture()
    config.update(changes)
    with pytest.raises(ValueError):
        run_session(data, bank, config, backend=lambda *_:None)


def test_query_intent_can_exceed_affordable_prefix_without_changing_schema():
    data, bank, config = config_fixture(request_budget=0)
    candidate_counts=[]
    def backend(system, request, call_id):
        candidate_counts.append(len(request["queries"]))
        assert request["output_contract"]["properties"]["query_order"]["maxItems"] == len(request["queries"])
        return json.dumps({"query_order":list(request["queries"])}), {
            "input_tokens":10,"output_tokens":10,"seconds":.001,"ended_with_eos":True}
    report=run_session(data,bank,config,backend=backend)
    assert max(candidate_counts)>0 and report["resource_spent"]["requests"] == 0
    assert all(c["response_error"] is None for c in report["selector_calls"])


@pytest.mark.parametrize("raw,eos,seconds", [('refused',True,.001), ('{"query_order":[]}',False,.001),
                                         ('{"query_order":[]}',True,601)])
def test_invalid_or_late_selection_retains_costs_and_full_calendar(raw,eos,seconds):
    data,bank,config=config_fixture(model_call_budget=1,call_compute_cap_ms=700000,compute_ms_cap=2800000)
    report=run_session(data,bank,config,backend=lambda *_:(raw,{
        "input_tokens":10,"output_tokens":10,"seconds":seconds,"ended_with_eos":eos}))
    assert report["resource_spent"]["tokens"] == 20
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["resource_spent"]["requests"] == 0
    if seconds < 600: assert report["selector_calls"][0]["response_error"]


def select_all(system,request,call_id):
    return json.dumps({"query_order":list(request["queries"])}), {
        "input_tokens":10,"output_tokens":10,"seconds":.001,"ended_with_eos":True}


@pytest.mark.parametrize("budget",[0,2])
def test_query_only_dispositions_keep_whole_intent_and_unexecuted_tail(budget):
    data,bank,config=config_fixture(request_budget=budget,model_call_budget=1)
    report=run_session(data,bank,config,backend=select_all)
    trace=report["frames"][0]["selector_query_intent"]
    assert len(trace["planned_query_order"])>=2
    assert [r["query_id"] for r in trace["dispositions"]] == trace["planned_query_order"]
    assert trace["executed_query_order"] == trace["planned_query_order"][:budget//2]
    assert trace["dispositions"][budget//2]["status"] == "budget_exhausted"


def test_v2_does_not_skip_infeasible_first_intent_to_execute_later_query():
    data,bank,config=config_fixture(request_budget=10,model_call_budget=1)
    slow_station=data["query_catalog"][0]["station"]
    for q in data["query_catalog"]:
        if q["station"] == slow_station:q["latency_ms"]=600000
    def backend(system,request,call_id):
        ordered=sorted(request["queries"],key=lambda h:-request["queries"][h]["metadata"]["latency_ms"])
        assert request["queries"][ordered[0]]["metadata"]["latency_ms"] == 600000
        return json.dumps({"query_order":ordered}),{"input_tokens":10,"output_tokens":10,"seconds":.001,"ended_with_eos":True}
    report=run_session(data,bank,config,backend=backend)
    assert not report["source_receipts"]
    trace=report["frames"][0]["selector_query_intent"]
    assert trace["dispositions"][0]["status"]=="late"
    assert all(r["status"]=="unexecuted_tail" for r in trace["dispositions"][1:])


def test_v2_intent_survives_original_pending_source_resume(tmp_path):
    from test_monitoring_pending_source import PendingSource,reply
    data,bank,config=config_fixture(request_budget=2,model_call_budget=1)
    source=PendingSource(tmp_path,data["query_results"])
    session=SessionCoordinator(data,bank,config,backend=select_all,source_backend=source)
    session.step();snapshot=session.snapshot()
    assert "pending_source" in snapshot["payload"]
    trace=snapshot["payload"]["controller"]["selector_records"][0]["query_intent"]
    assert trace["dispositions"]==[]
    reply(tmp_path,data,session)
    result=session.finish()
    restored=SessionCoordinator.restore(snapshot,data,bank,backend=select_all,source_backend=source).finish()
    assert result==restored
    trace=result["frames"][0]["selector_query_intent"]
    assert trace["dispositions"][0]["status"]=="executed"
    assert trace["dispositions"][1]["status"]=="budget_exhausted"
    assert len(list(tmp_path.glob("*.request.json")))==1
