"""Bounded M01 execution: original production receipts and complete scoring."""

import argparse
import json
import math
import signal
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.native_feature import NativeFeaturePredictor
from disastertrace.monitoring_v1.api_transport_v2 import deliver, validate_publication
from disastertrace.monitoring_v1.formal_session import FormalSession, score_formal
from disastertrace.monitoring_v1.production import ProductionSpoolBackend
from disastertrace.monitoring_v1.selector_contract_v2 import parse_query_only
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

RUN=Path(__file__).resolve().parent
REPO=RUN.parents[1]
B02=RUN.parent/"v13_strong_baselines_20260916_01"
PRIOR=RUN.parent/"v13_followup_20260916_01"
sys.path.insert(0,str(B02))
from program import ALL_ARMS, now, paired, metrics, restore_contract, verify

MODEL="deepseek-ai/DeepSeek-V4-Flash"
CREDENTIAL=Path("/mnt/afs/260010168/.config/disastertrace/credentials/siliconflow.json")
ARM="LLM_SELECTOR_V2"


def backend(case):
    return ProductionSpoolBackend(case/"spool",read(RUN/"MODEL_CONTRACT.json"),
        run_id="v13-m01-20260916-01-"+case.name,bound_files=read(case/"BACKEND_FILES.json"))


def gate_decision(b00,b02,m00,engineering,consumer,actions):
    if not all(x.get("passed") is True for x in (b00,b02,m00,engineering,consumer)):
        return {"qualified":False,"reason":"required_acceptance_missing_or_failed"}
    if (b00.get("completed_cases")!=168 or b02.get("completed_new_method_days")!=72
            or b02.get("registered_opportunities")!=864 or m00.get("valid_outputs")!=12):
        return {"qualified":False,"reason":"incomplete_registered_denominator"}
    if consumer.get("calls_reproduced",0)==0 or consumer.get("paid_asset_calls",0)==0:
        return {"qualified":False,"reason":"no_qualified_paid_field_to_forecast_consumer"}
    # A concrete differing F trajectory is a witness against all-path equivalence.
    # Positive skill is deliberately not a prerequisite.
    witnesses=[r for r in actions.get("rows",[]) if r["left"]=="B11_COVERAGE"
               and r["right"] in ALL_ARMS[5:8] and not r["same_acquisition_sequence"]
               and not r["same_probabilities"]]
    if not witnesses:
        return {"qualified":False,"reason":"no_observed_non_equivalent_selector_path_witness",
                "all_legal_paths_equivalent_proven":False}
    return {"qualified":True,"reason":"registered_acceptances_and_real_non_equivalence_witness",
            "witnesses":witnesses,"positive_gain_required":False}


def audit_consumer(report,feature_bank):
    counts={"calls_reproduced":0,"paid_asset_calls":0,"paid_assets":0}
    receipts={r["receipt_id"]:r for r in report["source_receipts"]}
    for call in report["calls"]:
        bundle=EvidenceBundle.restore(call["bundle"])
        reproduced=NativeFeaturePredictor(feature_bank,at=call["started_at"]).predict(bundle)
        if reproduced.value!=call["proposed_probability"] or call["head"]!="program":
            raise ValueError("Actual frozen program probability does not reproduce")
        view=bundle.policy_view();visible=view["assets"]
        for receipt in view["receipts"]:
            source=receipts[receipt["receipt_id"]]
            if source["completed_at"]>call["started_at"]:
                raise ValueError("Source is not timely at its actual consumer")
        if {a["content"]["query_id"] for a in visible}!=set(call["evidence_query_ids"]):
            raise ValueError("Consumer evidence differs from actual bundle")
        counts["calls_reproduced"]+=1
        counts["paid_asset_calls"]+=bool(visible)
        counts["paid_assets"]+=len(visible)
    return counts


def drive_controller(session,api,checkpoints,*,dispatch=deliver,credential_path=CREDENTIAL,max_steps=60):
    """One submission per committed ID. Failures resume only the consumer."""
    dispatched=set();failures=[]
    for step in range(max_steps):
        if session.done:break
        session.step()
        cp=session.snapshot()
        pending=cp["payload"].get("pending_selector")
        if pending is None:continue
        call=pending["call_id"]
        if call in dispatched:raise ValueError("Controller tried to redispatch a consumed call")
        if len(dispatched)>=24:raise ValueError("Daily24request cap exceeded")
        session.persist(checkpoints/f"step-{step:03d}.json")
        dispatched.add(call)
        try:dispatch(api,call,credential_path=credential_path)
        except Exception as exc:
            failures.append({"call_id":call,"error_type":type(exc).__name__})
            # deliver persists transport failures. Pre-claim/binding failures
            # cannot be silently converted into a manufactured provider result.
            if not (api.directory/(api._key(call)+".failure.json")).exists():raise
    if not session.done:raise ValueError("Model controller exceeded registered step ceiling")
    return {"dispatched_call_ids":sorted(dispatched),"transport_failures":failures}


def response_audit(api,report):
    selectors={s["call_id"]:s for s in report["selector_calls"]}
    requests=list(api.directory.glob("*.request.json"));results=[]
    for path in requests:
        request=read(path);call=request["call_id"]
        if call not in selectors:raise ValueError("Committed request lacks terminal controller consumer")
        base=path.with_name(path.name.removesuffix(".request.json"))
        response=Path(str(base)+".response.json")
        failure=Path(str(base)+".failure.json")
        record={"call_id":call,"publication_verified":False,"contract_valid":False,"provider_tokens":None,
                "HTTP_intent":Path(str(base)+".api_intent.json").exists()}
        if response.exists():
            record["publication_verified"]=validate_publication(api,call)
            if not record["publication_verified"]:raise ValueError("Original provider capture did not bind publication")
            answer=read(response)
            try:parse_query_only(answer["raw"],request["request"]["queries"]);record["contract_valid"]=True
            except (TypeError,ValueError):pass
            record["provider_tokens"]=answer["input_tokens"]+answer["output_tokens"]
            record["finish_with_eos"]=answer["ended_with_eos"]
        elif not failure.exists():raise ValueError("Unaccounted terminal model request")
        record["consumer_parse_error"]=selectors[call].get("parse_error")
        record["consumer_response_error"]=selectors[call].get("response_error")
        record["failure_receipt"]=read(failure) if failure.exists() else None
        results.append(record)
    if len(requests)!=len(selectors) or len(requests)>24:raise ValueError("Model request/consumer denominator differs")
    return {"passed":True,"requests":results,"actual_controller_calls":report["actual_model_calls"],
        "HTTP_intents":sum(r["HTTP_intent"] for r in results),
        "schema_valid":sum(r["contract_valid"] for r in results),
        "provider_tokens_known":sum(r["provider_tokens"] or 0 for r in results),
        "requests_without_usage":sum(r["provider_tokens"] is None for r in results),
        "reserved_resources":report["resource_reserved"],"new_HTTP_during_audit":0}


def timeout(*_):raise TimeoutError("Model day exceeded frozen three-hour wall cap")


def one(row):
    case=RUN/"cases"/row["case"];origin=PRIOR/"B00"/row["case"]
    publish(case/"CLAIM.json",{"at":now(),"one_use":True,"requests_max":24})
    result={"case":row["case"],"passed":False};session=None;started=time.monotonic()
    try:
        signal.signal(signal.SIGALRM,timeout);signal.alarm(10800)
        reg=read(RUN/"REGISTRATION.json")
        verify(reg["files"]);verify(read(RUN/"FREEZE.json")["files"]);verify(read(RUN/"GATES.json")["files"])
        data,bank=read(origin/"DATA.json"),read(origin/"BANK.json")
        cfg=read(case/"CONFIG.json");api=backend(case)
        files=read(case/"BACKEND_FILES.json")|{str(case/n):digest(case/n) for n in ("CONFIG.json","COMPARISON.json")}
        files[str(RUN/"GATES.json")]=digest(RUN/"GATES.json")
        comp=restore_contract(read(case/"COMPARISON.json"))
        session=FormalSession(data,bank,cfg,comparison=comp,bound_files=files,directory=case/ARM,backend=api)
        execution=drive_controller(session,api,case/"checkpoints")
        session.finish(max_steps=1);session.export_journal(case/ARM/"admission.jsonl")
        report=session.report;audit=response_audit(api,report)
        publish(case/"API_AUDIT.json",audit);publish(case/"EXECUTION.json",execution)
        consumer=audit_consumer(report,cfg["native_feature_bank"])
        publish(case/"CONSUMER_AUDIT.json",consumer)
        outcomes=read(origin/"OUTCOMES.json")
        score=score_formal(outcomes,{ARM:case/ARM/"admission.jsonl"},comparison=comp,run_references={ARM:case/ARM})
        publish(case/"SCORE.json",score)
        registry={o["opportunity_id"]:o for o in outcomes}
        roster={o["opportunity_id"] for o in data["opportunities"]}
        if len(report["snapshots"])!=72 or {s["opportunity_id"] for s in report["snapshots"]}!=roster:
            raise ValueError("Failed or late model calls erased forecast opportunities")
        old=read(origin/"B11_COVERAGE/FORMAL_REPORT.json")
        bases=lambda r:[(s["opportunity_id"],s["base_forecast"]) for s in r["snapshots"]]
        if bases(report)!=bases(old):raise ValueError("Common baseline at registered cutoffs differs")
        statuses={k:v for f in report["frames"] for k,v in f["e_statuses"].items()};rows=[]
        for snap in report["snapshots"]:
            oid,p=snap["opportunity_id"],snap["forecast"]["value"]
            y=registry[oid]["value"] if registry[oid]["status"]=="mature" else None
            rows.append({**{k:row[k] for k in ("case","region","week","date","threshold")},
                "arm":ARM,"opportunity_id":oid,"probability":p,"outcome":y,"loss":None if y is None else (p-y)**2,
                "outcome_status":registry[oid]["status"],"e_status":statuses.get(oid)})
        losses=[r["loss"] for r in rows if r["loss"] is not None];scored=score["scores"]["arms"][ARM]
        if scored["scored"]!=len(losses) or not math.isclose(scored["loss_sum"],math.fsum(losses),abs_tol=1e-10):
            raise ValueError("Model formal score fails independent arithmetic")
        publish(case/"ROWS.json",rows)
        result.update(passed=True,method_rows=len(rows),rows_sha256=digest(case/"ROWS.json"),
            HTTP_intents=audit["HTTP_intents"],schema_valid=audit["schema_valid"],actual_model_calls=report["actual_model_calls"],
            provider_tokens_known=audit["provider_tokens_known"],requests_without_usage=audit["requests_without_usage"],
            forecast_calls=len(report["calls"]),forecast_call_cap=72,resource_reserved=report["resource_reserved"],
            resource_spent=report["resource_spent"],complete_does_not_require_valid_model_outputs=True)
    except Exception as exc:
        result.update(error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        if session is not None and not (session.directory/"STOP.json").exists():session.stop("failed")
        if session is not None and session.report is not None:publish(case/"PARTIAL_REPORT.json",session.report)
    finally:signal.alarm(0)
    result.update(seconds=time.monotonic()-started,finished_at=now())
    publish(case/"RESULT.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="traceback"}),flush=True)
    return result


def qualify():
    reg=read(RUN/"REGISTRATION.json");verify(reg["files"]);verify(read(RUN/"FREEZE.json")["files"])
    b00,b02,m00=read(PRIOR/"B00/RESULT.json"),read(B02/"FINAL_RESULT.json"),read(PRIOR/"M00/RESULT.json")
    consumer={"passed":True,"calls_reproduced":0,"paid_asset_calls":0,"paid_assets":0,"cases":[]}
    for row in reg["cases"]:
        folder=PRIOR/"B00"/row["case"]
        cfg=read(folder/"CONFIGS.json")["B11_COVERAGE"]
        stats=audit_consumer(read(folder/"B11_COVERAGE/FORMAL_REPORT.json"),cfg["native_feature_bank"])
        for k,v in stats.items():consumer[k]+=v
        consumer["cases"].append({"case":row["case"],**stats})
    publish(RUN/"PRE_MODEL_CONSUMER_AUDIT.json",consumer)
    actions=read(B02/"ACTION_EQUIVALENCE_REPORT.json") if b02["passed"] else {}
    decision=gate_decision(b00,b02,m00,read(RUN/"OFFLINE_RESULT.json"),consumer,actions)
    decision["at"]=now();publish(RUN/"GATE_DECISION.json",decision)
    if not decision["qualified"]:return False
    bank=read(B02/"BANK_DECISION.json")
    if bank["status"]!="RETAINED_FOR_B02":raise ValueError("Predictor bank decision differs")
    verify({r["path"]:r["sha256"] for r in bank["frozen_bank_identity"].values()})
    if digest(B02/"ROWS.json")!=b02["rows_sha256"]:raise ValueError("Strong baseline rows changed")
    for row in read(B02/"REUSE_QUALIFICATION.json")["cases"]:verify(row["files"])
    files=[PRIOR/"B00/RESULT.json",PRIOR/"M00/RESULT.json",PRIOR/"M00/INDEPENDENT_AUDIT.json",
        B02/"FINAL_RESULT.json",B02/"BANK_DECISION.json",B02/"ROWS.json",B02/"ACTION_EQUIVALENCE_REPORT.json",
        B02/"PUBLIC_ACTION_CENSUS.json",B02/"GATES.json",RUN/"OFFLINE_RESULT.json",RUN/"GATE_DECISION.json",
        RUN/"PRE_MODEL_CONSUMER_AUDIT.json"]
    verify(read(B02/"GATES.json")["files"])
    if not read(PRIOR/"M00/INDEPENDENT_AUDIT.json")["passed"]:raise ValueError("Interface audit failed")
    publish(RUN/"GATES.json",{"passed":True,"at":now(),"files":{str(p):digest(p) for p in files},
        "qualification":"frozen public12-day roster; actual program consumer and non-equivalent queries; no gain-based selection",
        "C00_independent_mechanism":"not a required gate for selector comparison; remains separate"})
    return True


def summarize(results):
    complete=len(results)==12 and len({r["case"] for r in results})==12 and all(r["passed"] for r in results)
    value={"passed":complete,"registered_days":12,"complete_days":sum(r["passed"] for r in results),
        "registered_opportunities":864,"registered_request_cap":288,"results":results,
        "HTTP_intents":len(list((RUN/"cases").glob("*/spool/*.api_intent.json"))),
        "source":"actual model capture; program probabilities; end-to-end development only",
        "confirmation_opened":False,"automatic_retries":0,"finished_at":now()}
    if value["HTTP_intents"]>288:raise ValueError("Global request cap exceeded")
    if complete:
        baseline=read(B02/"ROWS.json");rows=[]
        for r in results:
            path=RUN/"cases"/r["case"]/"ROWS.json"
            if digest(path)!=r["rows_sha256"]:raise ValueError("Model rows changed")
            rows.extend(read(path))
        if len(rows)!=864:raise ValueError("Full model opportunity denominator differs")
        primary=[a for a in ALL_ARMS if a not in {"FOLLOW","F_COMMON"}]
        combined=baseline+rows
        comparisons=[{"scope":"all",**paired(combined,a,ARM)} for a in primary]
        for dim in ("week","region","date"):
            for key in sorted({r[dim] for r in rows}):
                sub=[r for r in combined if r[dim]==key]
                comparisons.extend({"scope":dim,"value":key,**paired(sub,a,ARM)} for a in primary)
        publish(RUN/"ROWS.json",rows)
        publish(RUN/"COMPARISONS.json",{"model_metrics":metrics(rows),"comparisons":comparisons,
            "same_predictor":True,"fixed_planned_slots":True,"actual_late_or_skipped_slots_not_removed":True,
            "missing_Y_bounds":"paired binary sensitivity, not a missing-at-random or independent-process assumption"})
        value.update(schema_valid=sum(r["schema_valid"] for r in results),
            provider_tokens_known=sum(r["provider_tokens_known"] for r in results),
            requests_without_usage=sum(r["requests_without_usage"] for r in results),
            rows_sha256=digest(RUN/"ROWS.json"))
    publish(RUN/"FINAL_RESULT.json",value)
    lines=["# M01 selector development result","",json.dumps({k:v for k,v in value.items() if k!="results"},ensure_ascii=False),"",
        "The model chooses source queries. The frozen program produces probabilities. Invalid responses, HTTP failures, late forecasts and fallback remain in the end-to-end denominator.","",
        "This comparison does not validate model-authored weather probabilities, independent confirmation, or another hazard."]
    if complete:
        lines += ["","| Program reference | Mean Brier gain (positive favors model) | Missing-Y bound |","|---|---:|---|"]
        for c in comparisons:
            if c["scope"]=="all":lines.append(f"| {c['reference']} | {c['settled_mean_gain']} | {c['all_opportunity_missing_Y_bound']} |")
    (RUN/"RESULT_SUMMARY.md").write_text("\n".join(lines)+"\n")


def execute(workers):
    reg=read(RUN/"REGISTRATION.json");verify(reg["files"]);verify(read(RUN/"FREEZE.json")["files"])
    publish(RUN/"CLAIM.json",{"at":now(),"workers":workers,"single_node_authority":True})
    until=reg["launch_deadline_wall_ns"]
    while not (B02/"FINAL_RESULT.json").exists():
        if time.time_ns()>=until:
            publish(RUN/"NOT_LAUNCHED.json",{"reason":"B02_not_complete_before_deadline","HTTP_intents":0});return 0
        for path in (B02/"runtime").glob("*/EXIT.json"):
            if read(path)["exit_code"]!=0:
                publish(RUN/"NOT_LAUNCHED.json",{"reason":"B02_worker_failed","HTTP_intents":0});return 0
        time.sleep(60)
    if time.time_ns()>=until or not qualify():
        publish(RUN/"NOT_LAUNCHED.json",{"reason":"technical_gate_or_deadline","HTTP_intents":0});return 0
    results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(one,row):row for row in reg["cases"]}
        for future in as_completed(pending):
            try:results.append(future.result())
            except Exception as exc:results.append({"case":pending[future]["case"],"passed":False,"error":type(exc).__name__})
    summarize(results)
    return 0 if all(r["passed"] for r in results) else 1


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--workers",type=int,default=4);args=p.parse_args()
    raise SystemExit(execute(args.workers))
