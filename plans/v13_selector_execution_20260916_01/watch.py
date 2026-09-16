"""Observe existing runs without dispatching, resuming, or retrying anything."""

import datetime as dt
import json
import os
import time
from pathlib import Path

RUN=Path(__file__).resolve().parent
B02=RUN.parent/"v13_strong_baselines_20260916_01"
PRIOR=RUN.parent/"v13_followup_20260916_01"


def read(p):
    try:return json.loads(p.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None
def write(p,v):
    tmp=p.with_suffix(".tmp")
    tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n");os.replace(tmp,p)


def snapshot():
    cases=[value for p in (RUN/"cases").glob("*/RESULT.json") if (value:=read(p)) is not None]
    http=len(list((RUN/"cases").glob("*/spool/*.api_intent.json")))
    return {"at":dt.datetime.now(dt.timezone.utc).isoformat(),"B00_C00_M00":read(PRIOR/"STATUS.json"),
        "B02":read(B02/"STATUS.json"),
        "scheduling":{"job":read(RUN/"runtime/JOB.json"),
            "resource_wait":read(RUN/"runtime/submission_wait/STATUS.json"),
            "submitter_stop":read(RUN/"runtime/submission_wait/STOP.json"),
            "submitter_error":read(RUN/"runtime/submission_wait/ERROR.json")},
        "M01":{"gates_open":(RUN/"GATES.json").exists(),
            "registered_days":12,"completed_days":sum(c["passed"] for c in cases),
            "failed_days":sum(not c["passed"] for c in cases),"request_cap":288,"HTTP_intents":http,
            "case_results":cases,"not_launched":read(RUN/"NOT_LAUNCHED.json"),
            "final_result":read(RUN/"FINAL_RESULT.json"),"worker_exit":read(RUN/"runtime/EXIT.json")},
        "observer_model_calls":0,"confirmation_opened":False}


def summary(status):
    prior=status["B00_C00_M00"] or {};b=prior.get("B00",{});m=status["M01"]
    lines=["# v13 连续执行检查点","",f"更新时间：{status['at']}","",
        f"- B00 日历通过 {b.get('verified_cases',0)}/168，失败 {b.get('failed_cases',0)}。",
        f"- B02 状态见相邻强程序批次；M01 启动门槛已打开：{m['gates_open']}。",
        f"- M01 完成 {m['completed_days']}/12 天，失败 {m['failed_days']}；HTTP 意图 {m['HTTP_intents']}/288。",
        "- 此页由普通 Python 更新，不执行模型请求，不重试。",
        "- 正式模型角色仅为查询选择器，概率由冻结程序生成；完整日历和机会分母保留。",
        "- 既有强程序批次的 M01_READINESS 描述该批当时的边界；本批 AUTHORIZATION、GATE_DECISION 和实时回执定义后续状态。"]
    if m["not_launched"]:lines.append("- 本批未启动："+json.dumps(m["not_launched"],ensure_ascii=False))
    if m["final_result"]:lines.append("- 本批完成回执已生成，详见 FINAL_RESULT.json 和 RESULT_SUMMARY.md。")
    scheduling=status["scheduling"]
    if scheduling["job"]:lines.append("- ACP 已接受作业："+scheduling["job"]["job_id"]+"；是否开始模型调用以上述 HTTP 意图为准。")
    else:lines.append("- M01 暂无平台接受回执；首次提交被 CPU 配额拒绝，独立脚本等待资源释放。")
    if scheduling["submitter_error"]:lines.append("- 提交脚本异常："+json.dumps(scheduling["submitter_error"],ensure_ascii=False))
    (RUN/"PROGRESS_CN.md").write_text("\n".join(lines)+"\n")


def main():
    with (RUN/"OBSERVER_CLAIM.json").open("x") as f:json.dump({"pid":os.getpid(),"poll_seconds":60,"model_calls":0},f)
    until=dt.datetime(2026,9,17,0,30,tzinfo=dt.timezone.utc).timestamp()
    while time.time()<until:
        state=snapshot();write(RUN/"STATUS.json",state);summary(state)
        stop=state["scheduling"]["submitter_stop"]
        submission_terminal=state["scheduling"]["submitter_error"] or (stop and stop["reason"]!="submission_accepted")
        if state["M01"]["final_result"] or state["M01"]["not_launched"] or state["M01"]["worker_exit"] or submission_terminal:
            write(RUN/"OBSERVER_STOP.json",{"at":state["at"],"reason":"terminal_artifact_observed"});return
        time.sleep(60)
    write(RUN/"OBSERVER_STOP.json",{"reason":"observer_deadline","at":dt.datetime.now(dt.timezone.utc).isoformat()})


if __name__=="__main__":main()
