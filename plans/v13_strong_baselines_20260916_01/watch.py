"""Minute-level artifact observer; no experiments, API calls, or retries."""

import datetime as dt
import json
import os
import time
from pathlib import Path

RUN=Path(__file__).resolve().parent
PREV=RUN.parent/"v13_followup_20260916_01"


def read(p):
    return json.loads(p.read_text()) if p.exists() else None


def publish(p,value,*,replace=False):
    if not replace:
        with p.open("x") as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write("\n")
        return
    temp=p.with_suffix(".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    os.replace(temp,p)


def snapshot():
    results=[read(p) for p in (RUN/"B02").glob("*/*_RESULT.json")]
    regression=read(RUN/"regression/RESULT.json")
    compatibility=read(RUN/"COMPATIBILITY.json")
    return {"at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "prior_batch":read(PREV/"STATUS.json"),
        "regression_passed":regression.get("passed") if regression else None,
        "regression_unique_tests":regression.get("unique_nodes") if regression else None,
        "legacy_compatibility_passed":compatibility.get("passed") if compatibility else None,
        "B02_gates_open":(RUN/"GATES.json").exists(),"B02_registered_new_method_days":72,
        "B02_passed_method_days":sum(r["passed"] for r in results),
        "B02_failed_method_days":sum(not r["passed"] for r in results),
        "B02_final_result":read(RUN/"FINAL_RESULT.json"),
        "worker_exits":{p.parent.name:read(p) for p in (RUN/"runtime").glob("*/EXIT.json")},
        "new_model_calls":0,"confirmation_opened":False}


def completion(status):
    old=read(PREV/"FINAL_RESULT.json")
    new=read(RUN/"FINAL_RESULT.json")
    if not old or not new:return False
    census=read(RUN/"PUBLIC_ACTION_CENSUS.json")
    actions=read(RUN/"ACTION_EQUIVALENCE_REPORT.json")
    publish(RUN/"M01_READINESS.json",{
        "status":"NOT_LAUNCHED_REQUIRES_RESULT_REVIEW","new_model_calls":0,
        "B02_complete":new.get("passed",False),
        "public_asymmetric_decision_points":census.get("with_public_feature_asymmetry") if census else None,
        "observed_selector_action_differences":actions.get("selector_contrasts_with_different_actions") if actions else None,
        "C00_result_exists":(PREV/"C00/RESULT.json").exists(),
        "reason":"Engineering and interface qualification alone do not establish useful public selection signal. Bind an actual12-day288-call comparison only after assessing strong baselines, field-to-forecast consumption, GET and public exploitability.",
        "all_legal_paths_equivalent_proven":False,
        "observed_equal_actions_are_not_a_proof_of_all_path_equivalence":True})
    publish(RUN/"COMPLETION_RECEIPT.json",{"at":status["at"],"prior_batch":old,"B02":new,
        "source_strata":read(PREV/"SOURCE_STRATA/RESULT.json"),"observer_model_calls":0})
    return True


def main():
    publish(RUN/"OBSERVER_CLAIM.json",{"pid":os.getpid(),"at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "poll_seconds":60,"model_calls":0,"deadline_utc":"2026-09-17T00:00:00+00:00"})
    deadline=dt.datetime(2026,9,17,tzinfo=dt.timezone.utc).timestamp()
    while time.time()<deadline:
        status=snapshot();publish(RUN/"STATUS.json",status,replace=True)
        if completion(status):return
        if any(x["exit_code"]!=0 for x in status["worker_exits"].values()):
            publish(RUN/"OBSERVER_STOP.json",{"status":"worker_failure","snapshot":status});return
        time.sleep(60)
    publish(RUN/"OBSERVER_STOP.json",{"status":"deadline_incomplete","snapshot":snapshot()})


if __name__=="__main__":main()
