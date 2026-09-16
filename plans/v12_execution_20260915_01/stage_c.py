"""Conditional 12-session selector comparison with frozen annual feature banks."""
import argparse
import copy
import datetime as dt
import json
import time
import traceback
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, experiment_spec
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.formal_session import FormalSession, required_source_files, score_formal
from disastertrace.monitoring_v1.production import ProductionSpoolBackend
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash
from siliconflow_worker import deliver

RUN=Path(__file__).resolve().parent
REPO=RUN.parents[1]
OUT=RUN/"stage_C"
ARMS=["LLM_SELECTOR","FOLLOW","F_COMMON","F_BASE_ONLY","B11_BATCH","B11_COVERAGE","B00_COVERAGE","B01_COVERAGE","B10_COVERAGE"]


def qualified_sources():
    frozen=read(RUN/"STAGE_C_SOURCE_FREEZE_02.json")["files"]
    if not {str(p) for p in required_source_files()} <= set(frozen):
        raise ValueError("Runtime imported modules outside the isolated stage C package")
    for name,sha in frozen.items():
        if digest(Path(name))!=sha:raise ValueError("Isolated stage C source changed")
    return frozen


def offline_qualified():
    files=[RUN/"tests/SILICONFLOW_TRANSPORT.xml",RUN/"tests/STAGE_C_INTEGRATION_05.xml"]
    for path in files:
        nodes=ET.parse(path).findall(".//testcase")
        if not nodes or any(list(node) for node in nodes):
            raise ValueError("Offline integration qualification has failures or skips")
    return {str(p):digest(p) for p in files}


def intent():
    source_files=qualified_sources()
    test_files=offline_qualified()
    OUT.mkdir(exist_ok=False)
    units=read(REPO/"plans/v10_execution_20260914_01/seasonal_completion_02/COMPLETE.json")["units"]
    cases=[]
    for unit in units:
        name=unit["unit"]+"__5000"
        original=REPO/"plans/v11_execution_20260915_01/fullweek_02"/name
        cases.append({"case":name,"original":str(original),
            "input_files":{str(original/n):digest(original/n) for n in ("DATA.json","BANK.json","CONFIGS.json","OUTCOMES.json")}})
    assert len(cases)==12
    publish(OUT/"INTENT.json",{"at":dt.datetime.now(dt.timezone.utc).isoformat(),"cases":cases,"arms":ARMS,
        "model":"deepseek-ai/DeepSeek-V4-Flash","provider":"siliconflow","model_role":"query_only_selector",
        "model_choice":"user-authorized exact catalog ID frozen in the compatibility registration; no performance-based model selection",
        "threshold_m":5000,"calendar":"first complete UTC day of each of the12 previously exposed region-weeks; three stations;24cutoffs",
        "max_requests":288,"max_requests_per_case":24,"automatic_retries":0,
        "failed_compatibility_preserved":"HTTP/schema passed; strict synthetic one-query preference failed. Production accepts a ranked list and enforces acquisition budget. No retry or model replacement.",
        "target_selection_uses_new_Y":False,"confirmation_opened":False,
        "required_gates":["C2_engineering_passed","all72_native_joins_passed","annual_banks_frozen","offline_API_transport_qualified"],
        "new_launch_deadline_at":"2026-09-15T23:24:27+00:00","model_HTTP_deadline_at":"2026-09-16T00:24:27+00:00",
        "max_H100":4,"local_H100_required":False,
        "scope":"bounded development mechanism comparison; no significance or independent-confirmation claim",
        "source_files":{**test_files,**{str(p):digest(p) for p in [Path(__file__),RUN/"siliconflow_worker.py",RUN/"STAGE_C_SOURCE_FREEZE_02.json"]}},
        "backend_source_files":source_files})


def backend_for(case):
    files=read(case/"FILES.json")
    contract=read(OUT/"MODEL_CONTRACT.json")
    return ProductionSpoolBackend(case/"spool",contract,run_id="v12-annual-selector-"+case.name,bound_files=files)


def prepare_cases():
    registration=read(OUT/"INTENT.json")
    fit=RUN/"annual_stage_B/fit"
    policies={"model":registration["model"],"base_url":"https://api.siliconflow.cn/v1",
        "credential_path":read(RUN/"EXECUTION_AUTHORIZATION.json")["credential_path"],
        "allowed_call_ids":["select-"+str(i) for i in range(24)],"input_cap":32768,"output_cap":512,
        "deadline_wall_ns":int(dt.datetime.fromisoformat(registration["model_HTTP_deadline_at"]).timestamp()*1e9)}
    publish(OUT/"API_POLICY.json",policies)
    publish(OUT/"MODEL_CONTRACT.json",{"model":registration["model"],
        "weights":{"provider_managed":True,"checkpoint_revision_not_exposed":True},
        "tokenizer":{"provider_managed":True,"usage_source":"provider response"},
        "adapter":{"source_sha256":digest(RUN/"siliconflow_worker.py"),"endpoint":"https://api.siliconflow.cn/v1"},
        "generation":{"temperature":0,"max_tokens":512,"enable_thinking":False,"stream":False},
        "runtime":{"kind":"API via managed committed spool","no_retries":True,"one_use_call_slots":288}})
    for row in registration["cases"]:
        case=OUT/row["case"];case.mkdir();(case/"spool").mkdir();(case/"checkpoints").mkdir()
        original=Path(row["original"])
        data,bank=read(original/"DATA.json"),read(original/"BANK.json")
        for name in ("DATA.json","BANK.json","OUTCOMES.json"):
            publish(case/name,read(original/name))
        feature_banks={mode:read(fit/("BANK_"+mode+".json")) for mode in ("common","values")}
        frozen_banks=read(fit/"BANK_FREEZE.json")["banks"]
        for mode in feature_banks:
            if digest(fit/("BANK_"+mode+".json"))!=frozen_banks[mode]:
                raise ValueError("Annual bank changed before comparison freeze")
            # Raw forecasts never consume post-calibration tables. Keep those
            # large diagnostic tables outside per-tick controller checkpoints.
            feature_banks[mode].pop("post_calibration",None)
            publish(case/("RAW_BANK_"+mode+".json"),feature_banks[mode])
        source_files={str(p):digest(p) for p in required_source_files()}
        source_files.update(registration.get("backend_source_files",{}))
        source_files.update({str(p):digest(p) for p in [RUN/"stage_c.py",RUN/"siliconflow_worker.py",OUT/"INTENT.json",OUT/"API_POLICY.json",OUT/"MODEL_CONTRACT.json",fit/"BANK_FREEZE.json",case/"RAW_BANK_common.json",case/"RAW_BANK_values.json",case/"DATA.json",case/"BANK.json"]})
        publish(case/"FILES.json",source_files)
        backend=backend_for(case)
        base=read(original/"CONFIGS.json")["B11_COVERAGE"]
        configs={}
        for arm in ARMS:
            cfg=copy.deepcopy(base);cfg.pop("execution_contract",None)
            cfg.update(native_feature_bank=feature_banks["common" if arm=="F_COMMON" else "values"],
                model_call_budget=24,selector_kind="llm" if arm=="LLM_SELECTOR" else "batch_complete" if arm=="B11_BATCH" else "coverage",
                acquire=arm not in {"FOLLOW","F_COMMON","F_BASE_ONLY"},predict=arm!="FOLLOW")
            if arm=="B00_COVERAGE":cfg.update(allocation_mode="fixed_quota",authorization_mode="target_private")
            if arm=="B01_COVERAGE":cfg.update(allocation_mode="fixed_quota",authorization_mode="session_shared")
            if arm=="B10_COVERAGE":cfg.update(allocation_mode="global_budget",authorization_mode="target_private")
            configs[arm]=bind_execution(cfg,backend if arm=="LLM_SELECTOR" else None)
        groups={}
        for mode in ("common","values"):
            subset={k:v for k,v in configs.items() if (k=="F_COMMON")== (mode=="common")}
            specs=[experiment_spec(data,bank,cfg) for cfg in subset.values()]
            invariant=specs[0]["invariants"];allowed=defaultdict(list)
            for spec in specs:
                if spec["invariants"]!=invariant:raise ValueError("Registered same-bank comparison changed invariants")
                for k,v in spec["interventions"].items():
                    if v not in allowed[k]:allowed[k].append(v)
            groups[mode]={"arms":list(subset),"contract":ComparisonContract(invariant,allowed).export()}
        publish(case/"CONFIGS.json",configs);publish(case/"COMPARISONS.json",groups)
    publish(OUT/"CASE_FREEZE.json",{"files":{str(p):digest(p) for row in registration["cases"] for p in (OUT/row["case"]).glob("*.json")},
        "fit_bank_freeze_sha256":digest(fit/"BANK_FREEZE.json"),"new_model_calls_before_freeze":0})


def run_arm(task):
    name,arm=task;case=OUT/name
    result={"case":name,"arm":arm,"passed":False};started=time.monotonic();session=None
    try:
        data,bank,cfg=(read(case/p) for p in ("DATA.json","BANK.json","CONFIGS.json"));cfg=cfg[arm]
        group=read(case/"COMPARISONS.json")["common" if arm=="F_COMMON" else "values"]["contract"]["payload"]
        comparison=ComparisonContract(group["invariants"],group["allowed_interventions"])
        files=read(case/"FILES.json");files.update({str(case/n):digest(case/n) for n in ("CONFIGS.json","COMPARISONS.json")})
        backend=backend_for(case) if arm=="LLM_SELECTOR" else None
        session=FormalSession(data,bank,cfg,comparison=comparison,bound_files=files,directory=case/arm,backend=backend)
        if backend is None:
            session.finish(max_steps=24)
        else:
            steps=0;failures=[]
            while not session.done and steps<60:
                session.step();steps+=1
                cp=session.snapshot()
                if "pending_selector" in cp["payload"]:
                    call=cp["payload"]["pending_selector"]["call_id"]
                    session.persist(case/"checkpoints"/(f"step-{steps:03}.json"))
                    try:deliver(backend,call,read(OUT/"API_POLICY.json"))
                    except Exception as exc:
                        failures.append({"call_id":call,"error_type":type(exc).__name__})
                        key=backend._key(call);request_path=backend.directory/(key+".request.json")
                        failure_path=backend.directory/(key+".failure.json")
                        if not failure_path.exists():
                            publish(failure_path,{"call_id":call,"request_sha256":digest(request_path),
                                "execution_sha256":read(request_path)["execution_sha256"],"error_type":type(exc).__name__,
                                "phase":"worker_preflight_or_existing_claim","automatic_retry":False})
            if not session.done:raise ValueError("Model controller exceeds finite step ceiling")
            session.finish(max_steps=1)
            publish(case/arm/"API_FAILURES.json",failures)
        session.export_journal(case/arm/"admission.jsonl")
        result.update(passed=True,actual_model_calls=session.report["actual_model_calls"],opportunities=len(session.report["snapshots"]),resource_spent=session.report["resource_spent"])
    except Exception as exc:
        result.update(error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        if session is not None and not (session.directory/"STOP.json").exists():session.stop("failed")
        if session is not None and session.report is not None:
            publish(case/arm/"PARTIAL_REPORT.json",session.report)
            result["actual_model_calls"]=session.report["actual_model_calls"]
    result["seconds"]=time.monotonic()-started
    publish(case/(arm+"_RESULT.json"),result)
    print(json.dumps({k:v for k,v in result.items() if k!="traceback"}),flush=True)
    return result


def execute(workers):
    reg=read(OUT/"INTENT.json")
    for p,sha in {**reg["source_files"],**reg["backend_source_files"]}.items():
        if digest(Path(p))!=sha:raise ValueError("Registered stage C source changed")
    publish(OUT/"CLAIM.json",{"at":dt.datetime.now(dt.timezone.utc).isoformat(),"workers":workers})
    deadline=dt.datetime.fromisoformat(reg["new_launch_deadline_at"]).timestamp()
    fit=RUN/"annual_stage_B/fit/RESULT.json"
    while not fit.exists():
        tail=RUN/"annual_stage_B/TAIL_RESULT.json"
        if time.time()>=deadline or (tail.exists() and not read(tail)["passed"]):
            publish(OUT/"RESULT.json",{"passed":False,"status":"not_launched_annual_gates_unmet","new_model_calls":0});return
        time.sleep(60)
    joins=RUN/"annual_stage_B/joins/RESULT.json"
    if (time.time()>=deadline or not read(fit)["passed"] or not read(RUN/"C2_ENGINEERING_RESULT.json")["passed"]
            or not joins.exists() or not read(joins).get("passed") or read(joins).get("completed_units")!=72):
        publish(OUT/"RESULT.json",{"passed":False,"status":"not_launched_qualification_failed","new_model_calls":0});return
    qualified_sources();offline_qualified()
    for row in reg["cases"]:
        for p,sha in row["input_files"].items():
            if digest(Path(p))!=sha:raise ValueError("Original exposed comparison inputs changed")
    prepare_cases()
    results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks=[(row["case"],arm) for arm in ARMS for row in reg["cases"]]
        futures=[pool.submit(run_arm,t) for t in tasks]
        for f in as_completed(futures):results.append(f.result())
    scored=[]
    for row in reg["cases"]:
        case=OUT/row["case"]
        for mode,group in read(case/"COMPARISONS.json").items():
            c=group["contract"]["payload"];comparison=ComparisonContract(c["invariants"],c["allowed_interventions"])
            arms={arm:case/arm/"admission.jsonl" for arm in group["arms"]}
            if not all(p.exists() for p in arms.values()):
                scored.append({"case":row["case"],"group":mode,"passed":False});continue
            try:
                score=score_formal(read(case/"OUTCOMES.json"),arms,comparison=comparison,run_references={a:case/a for a in arms})
                publish(case/("SCORE_"+mode+".json"),score)
                scored.append({"case":row["case"],"group":mode,"passed":True})
            except Exception as exc:
                failure={"case":row["case"],"group":mode,"passed":False,"error_type":type(exc).__name__,"traceback":traceback.format_exc()}
                publish(case/("SCORE_"+mode+"_FAILURE.json"),failure);scored.append(failure)
    publish(OUT/"RESULT.json",{"passed":all(r["passed"] for r in results+scored),"results":results,"scored":scored,
        "new_model_calls":sum(r.get("actual_model_calls",0) for r in results),"confirmation_opened":False,
        "model_count_semantics":"Controller dispatches; HTTP intents counted separately. Preflight failures do not establish provider processing; unknown costs are retained.",
        "http_attempt_intents":len(list(OUT.glob("*/spool/*.api_intent.json"))),
        "scope":"12 exposed daily development sessions; threshold5000; four global week blocks; one model"})


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["intent","execute"]);p.add_argument("--workers",type=int,default=12);args=p.parse_args()
    intent() if args.mode=="intent" else execute(args.workers)
