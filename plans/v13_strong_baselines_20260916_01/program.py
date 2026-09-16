"""One-use B02 program matrix with explicit B00/bank/engineering gates."""

import argparse
import datetime as dt
import itertools
import json
import math
import signal
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_v1.formal_session import FormalSession, score_formal
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
PREV = REPO / "plans/v13_followup_20260916_01"
sys.path.insert(0, str(PREV))
from b00 import ARMS as OLD_ARMS, GROUPS, restore_contract
from b00 import contract as contract
from finalize import metrics, paired

ARMS = ["B11_RR_CYCLE", "B11_RISK_AGE", "B11_FIXED_HASH",
        "B00_COVERAGE", "B01_COVERAGE", "B10_COVERAGE"]
ALL_ARMS = OLD_ARMS + ARMS
OUT = RUN / "B02"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def verify(files):
    for name, sha in files.items():
        if digest(Path(name)) != sha:
            raise ValueError("Frozen file differs: " + name)


def gates_ready(b00, regression, compatibility, decision, reuse):
    if not all(r.get("passed") is True for r in (b00, regression, compatibility, reuse)):
        return False
    return (b00.get("completed_cases") == b00.get("registered_cases") == 168
            and b00.get("method_rows") == 60480 and b00.get("trajectories") == 840
            and decision.get("status") == "RETAINED_FOR_B02"
            and bool(decision.get("frozen_bank_identity")))


def verify_reuse(row):
    original = PREV / "B00" / row["case"]
    verify(row["original_files"])
    result = read(original / "RESULT.json")
    if not result["passed"] or digest(original / "ROWS.json") != result["rows_sha256"]:
        raise ValueError("B00 reference rows did not qualify")
    outcomes = read(original / "OUTCOMES.json")
    comparisons = read(original / "COMPARISONS.json")
    for group, arms in GROUPS.items():
        score = score_formal(outcomes, {a: original/a/"admission.jsonl" for a in arms},
                             comparison=restore_contract(comparisons[group]),
                             run_references={a: original/a for a in arms})
        if score != read(original / ("SCORE_"+group+".json")):
            raise ValueError("Original bound formal score did not reconstruct")
    files = {str(p): digest(p) for p in (original/"ROWS.json", original/"RESULT.json")}
    for a in OLD_ARMS:
        for n in ("FORMAL_REPORT.json", "CONTRACT.json", "STOP.json", "admission.jsonl", "admission.jsonl.formal.json"):
            files[str(original/a/n)] = digest(original/a/n)
    return {"case": row["case"], "passed": True, "files": files,
            "scoring_contract": "original bound comparison for each B00 group; never rebind old journals"}


def accept_b00():
    reg = read(RUN / "REGISTRATION.json")
    verify(reg["source_files"] | reg["runner_files"] | reg["input_files"])
    result = read(PREV / "B00/RESULT.json")
    if not result["passed"] or result.get("completed_cases") != 168:
        raise ValueError("Full B00 did not pass")
    old_registration = read(PREV / "B00/REGISTRATION.json")
    verify(old_registration["source_files"])
    for row in old_registration["cases"]:
        verify(row["files"])
        folder = PREV / "B00" / row["case"]
        case_result = read(folder / "RESULT.json")
        if not case_result["passed"] or digest(folder/"ROWS.json") != case_result["rows_sha256"]:
            raise ValueError("B00 case or row identity failed")
    if digest(PREV/"B00/ROWS.json") != result["rows_sha256"]:
        raise ValueError("B00 outer rows changed")
    with ProcessPoolExecutor(max_workers=8) as pool:
        reuse = list(pool.map(verify_reuse, reg["cases"]))
    publish(RUN/"REUSE_QUALIFICATION.json", {"passed":True,"cases":reuse,"reused_trajectories":60,
        "old_whole_package_same_bytes":False,"compatibility":digest(RUN/"COMPATIBILITY.json")})
    proposal = read(RUN/"BANK_DECISION_PROPOSAL.json")
    verify({r["path"]:r["sha256"] for r in proposal["banks"].values()})
    decision = {"at":now(),"status":"RETAINED_FOR_B02","new_fit_status":"NOT_NEEDED_FOR_THIS_FIXED_CONSUMER_COMPARISON",
        "frozen_bank_identity":proposal["banks"],"new_fits":0,"B00_result_sha256":digest(PREV/"B00/RESULT.json"),
        "rationale":proposal["reason"],"clock_limitation":proposal["refit"],
        "not_claimed":"absence of timing mismatch or proof that slot-aligned refitting cannot help"}
    publish(RUN/"BANK_DECISION.json",decision)
    publish(RUN/"FROZEN_BANK_IDENTITY.json",proposal["banks"])
    if not gates_ready(result, read(RUN/"regression/RESULT.json"), read(RUN/"COMPATIBILITY.json"),
                       decision,read(RUN/"REUSE_QUALIFICATION.json")):
        raise ValueError("B02 technical gates incomplete")
    census()
    paths=[PREV/"B00/RESULT.json",RUN/"regression/RESULT.json",RUN/"COMPATIBILITY.json",
           RUN/"BANK_DECISION.json",RUN/"FROZEN_BANK_IDENTITY.json",RUN/"REUSE_QUALIFICATION.json",
           RUN/"PUBLIC_ACTION_CENSUS.json"]
    publish(RUN/"GATES.json",{"passed":True,"at":now(),"files":{str(p):digest(p) for p in paths},
                              "model_calls":0,"new_method_days_max":72})


def timeout(*_):
    raise TimeoutError("Registered program method exceeded two-hour wall cap")


def run_method(task):
    reg = read(RUN/"REGISTRATION.json")
    row = next(r for r in reg["cases"] if r["case"]==task["case"])
    case, arm = OUT / row["case"], task["arm"]
    publish(case/(arm+"_CLAIM.json"),{"at":now(),"one_use":True})
    result = {"case":row["case"],"arm":arm,"passed":False}
    start = time.monotonic()
    session = None
    try:
        signal.signal(signal.SIGALRM,timeout);signal.alarm(7200)
        verify(reg["source_files"] | reg["runner_files"] | reg["input_files"] | row["files"])
        verify(read(RUN/"GATES.json")["files"])
        original = PREV/"B00"/row["case"]
        data,bank = read(original/"DATA.json"),read(original/"BANK.json")
        comparison = restore_contract(read(case/"COMPARISON.json"))
        files = {**reg["source_files"],**reg["runner_files"],**row["files"],**reg["input_files"],
                 str(RUN/"REGISTRATION.json"):digest(RUN/"REGISTRATION.json"),
                 str(RUN/"GATES.json"):digest(RUN/"GATES.json")}
        session = FormalSession(data,bank,read(case/"CONFIGS.json")[arm],comparison=comparison,
                                bound_files=files,directory=case/arm)
        report=session.finish(max_steps=24)
        session.export_journal(case/arm/"admission.jsonl")
        outcomes=read(original/"OUTCOMES.json")
        score=score_formal(outcomes,{arm:case/arm/"admission.jsonl"},comparison=comparison,
                           run_references={arm:case/arm})
        publish(case/(arm+"_SCORE.json"),score)
        registry={o["opportunity_id"]:o for o in outcomes}
        roster={o["opportunity_id"] for o in data["opportunities"]}
        if len(registry)!=len(outcomes) or set(registry)!=roster or len(report["snapshots"])!=72:
            raise ValueError("Method opportunity denominator mismatch")
        old=read(original/"B11_COVERAGE/FORMAL_REPORT.json")
        schedule=lambda r:[(c["opportunity_id"],c["started_at"],c["persisted_at"]) for c in r["calls"]]
        if schedule(report)!=schedule(old) or report["actual_model_calls"]!=0:
            raise ValueError("Fixed forecast schedule or model role changed")
        base=lambda r:[(s["opportunity_id"],s["base_forecast"]) for s in r["snapshots"]]
        if base(old)!=base(report):raise ValueError("Common baseline changed")
        statuses={k:v for f in report["frames"] for k,v in f["e_statuses"].items()}
        rows=[]
        for s in report["snapshots"]:
            oid,p=s["opportunity_id"],s["forecast"]["value"]
            y=registry[oid]["value"] if registry[oid]["status"]=="mature" else None
            rows.append({**{k:row[k] for k in ("case","region","week","date","threshold")},
                "arm":arm,"opportunity_id":oid,"probability":p,"outcome":y,
                "loss":None if y is None else (p-y)**2,"e_status":statuses.get(oid),
                "outcome_status":registry[oid]["status"]})
        losses=[r["loss"] for r in rows if r["loss"] is not None]
        scored=score["scores"]["arms"][arm]
        if scored["scored"]!=len(losses) or not math.isclose(scored["loss_sum"],math.fsum(losses),abs_tol=1e-10):
            raise ValueError("Independent arithmetic differs from formal scorer")
        publish(case/(arm+"_ROWS.json"),rows)
        result.update(passed=True,method_rows=72,rows_sha256=digest(case/(arm+"_ROWS.json")),
                      report_sha256=digest(case/arm/"FORMAL_REPORT.json"),model_calls=0)
    except Exception as exc:
        result.update(error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        if session is not None and not (session.directory/"STOP.json").exists():session.stop("failed")
    finally:signal.alarm(0)
    result.update(seconds=time.monotonic()-start,finished_at=now())
    publish(case/(arm+"_RESULT.json"),result)
    print(json.dumps({k:v for k,v in result.items() if k!="traceback"}),flush=True)
    return result


def census():
    """Public topology at scheduled wakeup, before outcome-based comparison."""
    reg=read(RUN/"REGISTRATION.json"); rows=[]
    for row in reg["cases"]:
        original=PREV/"B00"/row["case"]
        data=read(original/"DATA.json")
        cfg=read(original/"CONFIGS.json")["B11_COVERAGE"]
        # FOLLOW has no private acquisitions or predictive overrides.
        report=read(original/"FOLLOW/FORMAL_REPORT.json")
        catalog={q["query_id"]:q for q in data["query_catalog"]}
        for frame in report["frames"]:
            common=frame["public_selector_view"]
            at=frame["cutoff"]-cfg["wakeup_seconds"]*1000000
            candidates=[]
            for qid in sorted({q for c in common.values() for q in c["public_query_ids"]}):
                q=catalog[qid]
                if q["available_at"]>at:continue
                served=[t for t in common if qid in common[t]["public_query_ids"]]
                candidates.append({"query_id":qid,"cost_requests":1,"latency_ms":q["latency_ms"],
                    "public_available_age_us":at-q["available_at"],"public_coverage":len(served),
                    "public_risk_sum":math.fsum(common[t]["baseline_probability"] for t in sorted(served))})
            fields=["cost_requests","latency_ms","public_available_age_us","public_coverage","public_risk_sum"]
            rows.append({"case":row["case"],"cutoff":frame["cutoff"],"candidates":candidates,
                "asymmetric_fields":[k for k in fields if len({q[k] for q in candidates})>1]})
    publish(RUN/"PUBLIC_ACTION_CENSUS.json",{"rows":rows,"decision_points":len(rows),
        "with_public_feature_asymmetry":sum(bool(r["asymmetric_fields"]) for r in rows),
        "scope":"potential public catalogue at nominal wakeup; actual cache, spent budget and deadline legality depend on each trajectory",
        "outcomes_read":False,"source_values_read_for_selection":False,"not_an_expected_VOI_estimate":True})


def aggregate():
    reg=read(RUN/"REGISTRATION.json")
    shards=[read(RUN/f"SHARD_{s}.json") for s in range(2)]
    attempts=[r for s in shards for r in s["results"]]
    expected={(r["case"],a) for r in reg["cases"] for a in ARMS}
    keys=[(r["case"],r["arm"]) for r in attempts]
    passed=len(keys)==72 and set(keys)==expected and all(r["passed"] for r in attempts)
    result={"passed":passed,"registered_new_method_days":72,"completed_new_method_days":sum(r["passed"] for r in attempts),
        "failed":[r for r in attempts if not r["passed"]],"registered_days":12,"model_calls":0,"new_fits":0,
        "confirmation_opened":False,"finished_at":now()}
    if not passed:
        publish(RUN/"FINAL_RESULT.json",result);return
    reuse=read(RUN/"REUSE_QUALIFICATION.json")
    for row in reuse["cases"]:verify(row["files"])
    rows=[];actions=[]
    for row in reg["cases"]:
        case=OUT/row["case"];original=PREV/"B00"/row["case"]
        rows.extend(read(original/"ROWS.json"))
        reports={a:read(original/a/"FORMAL_REPORT.json") for a in OLD_ARMS}
        for a in ARMS:
            receipt=read(case/(a+"_RESULT.json"));p=case/(a+"_ROWS.json")
            verify({str(p):receipt["rows_sha256"],str(case/a/"FORMAL_REPORT.json"):receipt["report_sha256"]})
            rows.extend(read(p));reports[a]=read(case/a/"FORMAL_REPORT.json")
        for a,b in itertools.combinations(ALL_ARMS,2):
            seq=lambda x:[(s["query_id"],s["payer"],s["started_at"]) for s in x["source_receipts"]]
            values=lambda x:[(s["opportunity_id"],s["forecast"]["value"]) for s in x["snapshots"]]
            actions.append({"case":row["case"],"left":a,"right":b,
                "same_acquisition_sequence":seq(reports[a])==seq(reports[b]),
                "same_probabilities":values(reports[a])==values(reports[b]),
                "left_requests":reports[a]["resource_spent"]["requests"],
                "right_requests":reports[b]["resource_spent"]["requests"]})
    expected_rows={(r["case"],a,oid) for r in reg["cases"] for a in ALL_ARMS
                   for oid in read(PREV/"B00"/r["case"]/"ROSTER.json")}
    actual=[(r["case"],r["arm"],r["opportunity_id"]) for r in rows]
    if len(actual)!=9504 or set(actual)!=expected_rows:raise ValueError("Strong baseline outer matrix differs")
    contrasts=[("F_BASE_ONLY",a) for a in ARMS]+[("B11_BATCH",a) for a in ARMS[:3]]+[
        ("B11_COVERAGE",a) for a in ARMS[:3]]+[("B00_COVERAGE","B01_COVERAGE"),
        ("B00_COVERAGE","B10_COVERAGE"),("B01_COVERAGE","B11_COVERAGE"),("B10_COVERAGE","B11_COVERAGE")]
    comparisons=[{"scope":"all",**paired(rows,a,b)} for a,b in contrasts]
    for dimension in ("week","region","date"):
        for key in sorted({r[dimension] for r in rows}):
            subset=[r for r in rows if r[dimension]==key]
            comparisons.extend({"scope":dimension,"value":key,**paired(subset,a,b)} for a,b in contrasts)
    publish(RUN/"ROWS.json",rows)
    publish(RUN/"STRONG_BASELINE_COMPARISON.json",{"metrics":{a:metrics([r for r in rows if r["arm"]==a]) for a in ALL_ARMS},
        "comparisons":comparisons,"availability_basis":"declared_archive_scenario",
        "scope":"12 metadata-selected exposed development days; neither independent confirmation nor causal guarantee"})
    publish(RUN/"ACTION_EQUIVALENCE_REPORT.json",{"rows":actions,
        "selector_contrasts_with_different_actions":sum(not r["same_acquisition_sequence"] for r in actions
            if r["left"]=="B11_COVERAGE" and r["right"] in ARMS[:3]),
        "M01_decision":"not automatically launched; inspect public exploitability, outcomes and C00 jointly",
        "no_scaling_if_all_legal_paths_equivalent":True})
    result.update(reused_method_days=60,method_rows=len(rows),new_method_rows=5184,
                  registered_opportunities=864,rows_sha256=digest(RUN/"ROWS.json"))
    publish(RUN/"FINAL_RESULT.json",result)
    lines=["# B02 strong program baseline result", "",json.dumps(result,ensure_ascii=False),"",
           "Positive paired gain means candidate has lower Brier loss. All rows remain in the denominator; missing outcomes have explicit binary sensitivity bounds.","",
           "| Reference | Candidate | Settled mean gain | Missing-Y bound |","|---|---|---:|---|"]
    for r in comparisons:
        if r["scope"]=="all":lines.append(f"| {r['reference']} | {r['candidate']} | {r['settled_mean_gain']} | {r['all_opportunity_missing_Y_bound']} |")
    (RUN/"RESULT_SUMMARY.md").write_text("\n".join(lines)+"\n")


def execute(shard,workers):
    reg=read(RUN/"REGISTRATION.json")
    publish(RUN/f"CLAIM_{shard}.json",{"at":now(),"workers":workers,"one_use":True})
    verify(reg["source_files"] | reg["runner_files"] | reg["input_files"])
    deadline=dt.datetime.fromisoformat(reg["deadline_utc"]).timestamp()
    gate=PREV/"B00/RESULT.json" if shard==0 else RUN/"GATES.json"
    while not gate.exists():
        failure=RUN/"runtime/shard0/EXIT.json"
        if shard==1 and failure.exists() and read(failure)["exit_code"]!=0:
            raise RuntimeError("Lead shard stopped before opening B02 gates")
        if time.time()>deadline:raise TimeoutError("B02 gate deadline reached")
        time.sleep(60)
    if shard==0:
        accept_b00()
    verify(read(RUN/"GATES.json")["files"])
    tasks=[t for t in reg["tasks"] if t["shard"]==shard];results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run_method,t):t for t in tasks}
        for f in as_completed(futures):
            try:results.append(f.result())
            except Exception as exc:results.append({**futures[f],"passed":False,"error":type(exc).__name__,"message":str(exc)})
    publish(RUN/f"SHARD_{shard}.json",{"passed":all(r["passed"] for r in results),"results":results,"at":now()})
    if shard==0:
        while not (RUN/"SHARD_1.json").exists():
            failure=RUN/"runtime/shard1/EXIT.json"
            if failure.exists() and read(failure)["exit_code"]!=0:
                raise RuntimeError("Peer shard terminated without complete method receipts")
            if time.time()>deadline:raise TimeoutError("B02 peer deadline reached")
            time.sleep(60)
        aggregate()
    return 0 if all(r["passed"] for r in results) else 1


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--shard",type=int,choices=[0,1],required=True)
    p.add_argument("--workers",type=int,default=12);a=p.parse_args()
    raise SystemExit(execute(a.shard,a.workers))
