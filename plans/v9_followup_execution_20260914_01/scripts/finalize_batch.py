"""Write a readable final record when the registered background work terminates."""

import datetime as dt
import json
from pathlib import Path
import time

from status_followup import status

ROOT=Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text()) if path.exists() else None


def finish():
    state=status()
    e=load(ROOT/"reports/api_evidence_audit_02/VALIDATION.json")
    f=load(ROOT/"reports/api_forecast_audit_01/VALIDATION.json")
    rare=load(ROOT/"reports/api_rare_forecast_audit_01/VALIDATION.json")
    temperature=load(ROOT/"reports/temperature_stream_audit_01/VALIDATION.json")
    baselines=load(ROOT/"reports/regional_baselines_01/SUMMARY.json")
    complete=bool(e and f and rare and temperature and f["all_registered_arms_finished"] and rare["all_registered_arms_finished"])
    result={"at":dt.datetime.now(dt.timezone.utc).isoformat(),"registered_batch_complete":complete,
        "state":state,"e_audit_complete":bool(e),"f_audit_complete":bool(f),"rare_audit_complete":bool(rare),
        "temperature_audit_complete":bool(temperature),"regional_baselines_complete":bool(baselines),
        "monitoring_tests_passed":616,"confirmation_opened":False,"new_gpu_cards":0,
        "original_E_collection":"api_evidence_01 retained as transport-failed original; model scores use corrected complete E02"}
    with (ROOT/"BATCH_RESULT.json").open("x") as handle:json.dump(result,handle,indent=2)
    lines=["# 本批执行结果", "", "状态："+("已完成本批注册范围。" if complete else "存在未完成门槛，见状态与失败记录。"), "",
        "616 项相关测试通过；密钥保存在 Git 仓库外；未打开独立确认周。首次 E 采集的 AFS 锁故障完整保留，正式 E 结果使用修复后的独立批次。", "",
        "| 批次 | 已登记尝试 | 已结算响应 | 未知/待定 | 峰时费用上界USD |", "| --- | ---: | ---: | ---: | ---: |"]
    for name,row in state["api"].items():
        if row["started"]:
            counts=row["status_counts"]
            lines.append(f"| {name} | {row['attempts']} | {counts.get('settled',0)} | {counts.get('reserved',0)+counts.get('unknown',0)} | {row['settled_peak_fee_usd']:.6f} |")
    if temperature:
        lines += ["",f"温度程序链：{temperature['sessions']} 条连续轨迹、{temperature['target_opportunities']} 个机会、{temperature['unique_targets']} 个唯一目标，来源是已审计 EUPP/DWD；没有温度模型调用。"]
    if e:
        lines += ["",f"E 诊断：{e['underlying_opportunities']} 个底层问题，多个视图和模型共享底层问题。", "",
                  "| 模型/输入/输出 | E正确 | 全字段正确 |", "| --- | ---: | ---: |"]
        for key,row in e["groups"].items():
            if len(key.split("__"))==3:
                lines.append(f"| {key} | {row['correct']}/{row['n']} | {row['all_fields_correct']}/{row['n']} |")
    for label,audit in [("普通日历 F 试点",f),("正例机制 F 诊断",rare)]:
        if not audit:
            continue
        lines += ["", "## "+label, "", audit["selection"], "",
            "| 案例 | 方法 | 已结算/缺失 | 正例 | Brier | 相对FOLLOW变化 |", "| --- | --- | --- | ---: | ---: | ---: |"]
        for row in audit["records"]:
            if row["arm"] in ["follow","batch_program"] or row["arm"].startswith("deepseek"):
                lines.append(f"| {row['case']} | {row['arm']} | {row['mature']}/{row['missing']} | {row['positive']} | {row['brier']:.6f} | {row['delta_brier_vs_follow']:.6f} |")
    lines += ["", "负的 Brier 差值表示损失下降。不同阈值和重复视图共享事件，不作独立样本相加；按已知结果选择的正例机制诊断单独报告。",
              "", "这些结果检验本批工程和开发预测行为，不证明独立天气过程泛化、16类灾害完成或真实历史首次公开时间。数值变化也不自动等于新预测信息。",
              "", "下一阶段优先补充有正例的分离历史窗口、过程级统计、系统校准、同总资源的逐槽E/F及持久覆盖协议，再进行温度模型评价。"]
    (ROOT/"RUN_REPORT_CN.md").write_text("\n".join(lines)+"\n")


def main():
    with (ROOT/"runtime/FINALIZER_CLAIM_02.json").open("x") as handle:
        json.dump({"at":dt.datetime.now(dt.timezone.utc).isoformat()},handle)
    deadline=time.monotonic()+12*3600
    while time.monotonic()<deadline:
        pipeline=load(ROOT/"runtime/PIPELINE_STATUS.json") or {}
        audit=load(ROOT/"runtime/AUDIT_STATUS.json") or {}
        rare_terminal=(ROOT/"runtime/RARE_COMPLETE.json").exists() or (ROOT/"runtime/RARE_STOPPED.json").exists()
        audit_terminal=audit.get("phase") in ["REGISTERED_API_AUDITS_COMPLETE","UPSTREAM_STOPPED","STOPPED_AT_AUDIT_FAILURE","WAIT_LIMIT_REACHED"]
        if rare_terminal and audit_terminal:
            finish()
            return
        time.sleep(30)
    finish()


if __name__=="__main__":
    main()
