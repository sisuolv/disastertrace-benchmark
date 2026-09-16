"""Audit actual legal C00 parent information; never infer strata from case names."""
import datetime as dt
import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from b00 import RUN, OUT as B00, now
from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_v1.native_feature_forecast import native_claims
from disastertrace.monitoring_v1.spool_backend import read, publish, digest

OUT = RUN / "SOURCE_STRATA"


def coverage(candidate):
    if candidate is None:
        return "none"
    projection = candidate["projection"]
    start,end = projection["target_start"],projection["target_end"]
    intervals = sorted((max(start,s["start"]),min(end,s["end"])) for s in projection["segments"]
                       if s.get("prevailing") and s["end"]>start and s["start"]<end)
    covered,cursor = 0,start
    for a,b in intervals:
        if b>max(cursor,a): covered += b-max(cursor,a)
        cursor=max(cursor,b)
    return "none" if covered==0 else "full" if covered==end-start else "partial"


def analyze(row):
    folder = RUN / "C00" / row["case"]
    checkpoint_path = folder / "PARENT_CHECKPOINT.json"
    if not checkpoint_path.exists():
        return {"case":row["case"],"passed":False,"status":"parent_not_materialized"}
    cp = read(checkpoint_path)["payload"]
    data = read(B00 / row["case"] / "DATA.json")
    opportunity = next(o for o in data["opportunities"] if o["opportunity_id"]==row["opportunity_id"])
    pair = next(o for o in data["e_f_pairs"] if o["opportunity_id"]==row["opportunity_id"])
    engine = AdmissionEngine.restore(cp["runtime"])
    base = engine.baselines.get(opportunity["target_id"])
    if base is not None and base["valid_until"]<=cp["clock"]:
        base=None
    candidate = base["content"].get("native_taf") if base else None
    legal={}
    for asset in cp["store"]["assets"]:
        qid = asset["content"]["query_id"]
        if opportunity["target_id"] in asset["entitlement"] and qid in pair["query_ids"]:
            legal[qid]=asset["content"]
    claims = native_claims(pair["query_ids"],legal,at=cp["clock"])
    slots=[]
    for qid in pair["query_ids"]:
        product=legal.get(qid)
        vis=claims.get(qid,{}).get("visibility")
        slots.append({"query_id":qid,"authorized_product_visible":product is not None,
            "status":product["status"] if product else "not_acquired",
            "reported_record_count":len(product.get("reports",[])) if product else 0,
            "visibility_missing":product is not None and vis is None,
            "visibility_censored":vis is not None and (vis["lower"]!=vis["upper"] or
                                                       not vis["lower_closed"] or not vis["upper_closed"]),
            "reference_kind":product.get("reference_kind") if product else None,
            "support_assumption":product.get("support_assumption") if product else None})
    result={"case":row["case"],"passed":True,"opportunity_id":row["opportunity_id"],
        "checkpoint_sha256":digest(checkpoint_path),"clock":cp["clock"],"next_tick":cp["next_tick"],
        "TAF_temporal_coverage_at_parent":coverage(candidate),
        "TAF_amendment_kind":candidate.get("amendment_kind") if candidate else None,
        "TAF_source_id":candidate.get("source_id") if candidate else None,
        "required_report_slots":len(slots),"authorized_visible_slots":len(legal),"slots":slots,
        "baseline_conflict_in_processed_history":any(x.get("status")=="baseline_conflict" for x in engine.attempts),
        "boundary":"quiescent parent before next shared public wakeup; later public updates may change coverage",
        "TAF_coverage_meaning":"union of native projection intervals with prevailing records, not physical forecast correctness",
        "new_HTTP":0,"model_calls":0,"policy_experiments":0}
    publish(OUT/(row["case"]+".json"),result)
    return result


def main():
    OUT.mkdir(exist_ok=False)
    reg=read(RUN/'C00/REGISTRATION_02.json')
    publish(OUT/'REGISTRATION.json',{'at':now(),'parents':reg['parents'],'code_sha256':digest(Path(__file__)),
        'role':'evaluation-only legal-state classification, no candidate reselection, no source acquisition'})
    deadline=dt.datetime(2026,9,16,22,tzinfo=dt.timezone.utc).timestamp()
    waiting=list(reg['parents']);pending={};results=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        while waiting or pending:
            for row in list(waiting):
                p=RUN/'C00'/row['case']
                if (p/'PARENT_CHECKPOINT.json').exists() or (p/'C00_RESULT.json').exists():
                    pending[pool.submit(analyze,row)]=row;waiting.remove(row)
            for future in list(pending):
                if future.done():
                    row=pending.pop(future)
                    try:results.append(future.result())
                    except Exception as exc:
                        results.append({'case':row['case'],'passed':False,'error':type(exc).__name__,'message':str(exc)})
            if time.time()>deadline and waiting:
                results.extend({'case':r['case'],'passed':False,'status':'parent_unavailable'} for r in waiting);waiting=[]
            if waiting or pending:time.sleep(30)
    valid=[r for r in results if r['passed']]
    publish(OUT/'RESULT.json',{'passed':len(valid)==12,'parents':results,
        'TAF_temporal_coverage':dict(Counter(r['TAF_temporal_coverage_at_parent'] for r in valid)),
        'TAF_amendment_kinds':dict(Counter(r['TAF_amendment_kind'] or 'none' for r in valid)),
        'visible_source_statuses':dict(Counter(s['status'] for r in valid for s in r['slots'])),
        'censored_slots':sum(s['visibility_censored'] for r in valid for s in r['slots']),
        'missing_visible_slots':sum(s['visibility_missing'] for r in valid for s in r['slots']),
        'new_weather_HTTP':0,'new_policy_experiments':0,'finished_at':now()})


if __name__=='__main__':main()
