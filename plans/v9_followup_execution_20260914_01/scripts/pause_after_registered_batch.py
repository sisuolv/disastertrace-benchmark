"""Summarize the current finite jobs, then mark the batch paused for user review."""

import datetime as dt
import json
import os
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

from status_followup import status

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime/pause_after_batch_01"
TERMINAL = {"SUCCEEDED", "FAILED", "STOPPED", "CANCELLED", "TERMINATED"}


def read(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write(path, value):
    temp = path.with_name(path.name + ".pending")
    with temp.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temp, path)
    temp.unlink()


def platform(job):
    reply = subprocess.run([
        "/mnt/afs/260010168/bin/sco", "acp", "jobs", "describe",
        "--workspace-name=share-space", "--format=json", job,
    ], capture_output=True, text=True, timeout=45, check=False)
    if reply.returncode:
        return {"name": job, "query_returncode": reply.returncode, "state": "UNKNOWN"}
    data = json.loads(reply.stdout)
    return {k: data[k] for k in ["name", "state", "start_time", "finish_time", "roles"] if k in data}


def forecast_table(lines, label, audit):
    lines += ["", "## " + label, ""]
    if not audit:
        lines += ["没有完成独立 F 审计；原始结果和失败记录保留，暂不报告通过审计的预测成绩。"]
        return
    lines += [audit["selection"], "",
              "| 阈值 | 方法 | 已结算/缺失 | 正例机会 | Brier | 相对 FOLLOW 差值 | 新概率提议数 |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    groups = defaultdict(Counter)
    for row in audit["records"]:
        if row["arm"] not in ["follow", "batch_program", "copy_current", "copy_baseline"] and not row["arm"].startswith("deepseek"):
            continue
        key = (row["case"].rsplit("__", 1)[1], row["arm"])
        groups[key].update(mature=row["mature"], missing=row["missing"], positive=row["positive"],
                           losses=(row["brier"] or 0) * row["mature"],
                           delta=(row["delta_brier_vs_follow"] or 0) * row["mature"],
                           new_probability=row["value_proposals"].get("more_than_0_005_from_visible_values", 0))
    for (threshold, arm), g in sorted(groups.items()):
        mean = f"{g['losses']/g['mature']:.6f}" if g["mature"] else "未结算"
        delta = f"{g['delta']/g['mature']:.6f}" if g["mature"] else "未结算"
        lines.append(f"| {threshold}m | {arm} | {g['mature']}/{g['missing']} | {g['positive']} | {mean} | {delta} | {g['new_probability']} |")
    lines += ["", "Brier 越低越好，负差值表示损失下降。“新概率提议”仅指与可见当前值和基线值都相差超过 0.005 的提议，不能单独证明新信息或最终生效。两个阈值、多个站点与相邻时段存在依赖。"]


def finish(jobs):
    live = status()
    e = read(ROOT / "reports/api_evidence_audit_02/VALIDATION.json")
    f = read(ROOT / "reports/api_forecast_audit_01/VALIDATION.json")
    rare = read(ROOT / "reports/api_rare_forecast_audit_01/VALIDATION.json")
    temp = read(ROOT / "reports/temperature_fullcalendar_audit_01/VALIDATION.json")
    coverage = read(ROOT / "runtime/temperature_fullcalendar_01/COVERAGE.json")
    completed = bool(e and e["passed"] and f and f["all_registered_arms_finished"] and
                     rare and rare["all_registered_arms_finished"] and temp and temp["passed"] and
                     all(j["state"] == "SUCCEEDED" for j in jobs.values()))
    result = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": "PAUSED_FOR_USER_REVIEW",
              "all_registered_work_verified": completed, "jobs": jobs, "status": live,
              "temperature_fullcalendar": temp, "temperature_coverage": coverage,
              "no_further_download_model_or_gpu_launch": True, "confirmation_opened": False}
    write(ROOT / "PAUSED_RESULT.json", result)
    lines = ["# 本轮暂停与结果汇总", "", "生成时间（UTC）：" + result["at"], "",
             "状态：已完成本轮运行并暂停，等待用户检查。" if completed else
             "状态：本轮计算任务已结束并暂停；存在失败或未完成的验证门槛，不能将整批标为通过。", "",
             "本报告覆盖普通日历 DeepSeek F 评测、单独登记的 Denver 正例诊断，以及完整 2017–2018 温度程序对照。后台不会从这里启动下一轮下载、模型试验、GPU 任务或打开确认周。", "",
             "## 已完成的基础工作", "",
             "616 项监测工程测试通过。四区域 3,303 次原生 TAF/METAR 获取完成；清除跨期窗口重叠后，区域基线拟合 9,678 条、校准 2,780 条。原 8 窗口温度程序链完成 64 条轨迹、876 个机会与 280 个唯一目标。", "",
             "CCI 仅有 2 核/8GiB，F 程序重放迁移至 64 核/256GiB 的 ACP CPU 任务。18 条原轨迹保留，其余 102 条在新节点完成；模型请求并发仍为 4。温度扩展使用单独的 16 核/64GiB CPU 任务，本轮新增 GPU 占用为 0。", "",
             "## E 证据理解结果", "",
             "修复后的 E02 完成 1,008 次调用并通过原始响应、参考与费用审计；42 个底层问题生成相依视图。", "",
             "| 模型 | 完整/直接 | 完整/逐槽 | 聚焦/直接 | 聚焦/逐槽 |",
             "| --- | ---: | ---: | ---: | ---: |",
             "| DeepSeek Flash | 114/126 | 125/126 | 109/126 | 126/126 |",
             "| DeepSeek v4 Pro | 85/126 | 106/126 | 84/126 | 101/126 |", "",
             "Pro 聚焦逐槽的 25 个错误均为槽位判断全部正确后的最终汇总错误；Flash 完整逐槽的一份格式无效输出仍计入分母。这是固定 thinking disabled 设置下的开发结果，不是模型一般能力排名，也不是未来预测准确率。"]
    forecast_table(lines, "普通日历的未来报告预测", f)
    forecast_table(lines, "Denver 正例机制诊断", rare)
    lines += ["", "## 温度完整历史", ""]
    if temp:
        lines += [f"按 24 个自然月完成 {temp['sessions']} 条程序轨迹、{temp['target_opportunities']} 个目标机会、{temp['unique_targets']} 个唯一目标，独立评分复核通过。来源为 EUPP 51 成员日极值和 DWD 原生参考；没有温度模型调用。"]
    else:
        lines += ["完整月历尚未通过独立验证；当前文件中的中间结果不能算已完成实验。"]
    if coverage:
        lines += ["", "| 事件 | 唯一目标 | 可结算 | 正例目标 |", "| --- | ---: | ---: | ---: |"]
        for event, counts in sorted(coverage["by_event"].items()):
            lines.append(f"| {event} | {counts['targets']} | {counts['mature']} | {counts['positive']} |")
    lines += ["", "## 费用与保留问题", "",
             "| 批次 | 账本尝试 | 已结算 | 未知/待定 | 峰时费用上界USD | 未决预留USD |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, row in live["api"].items():
        if not row["started"]:
            continue
        c = row["status_counts"]
        lines.append(f"| {name} | {row['attempts']} | {c.get('settled',0)} | {c.get('reserved',0)+c.get('unknown',0)} | {row['settled_peak_fee_usd']:.6f} | {row['unresolved_reservation_usd']:.6f} |")
    lines += ["", "费用按保存的峰时价和未命中缓存输入计算，属于保守估计，不是服务商账单。首次 E01 因 AFS 文件锁竞争出现采集失败；其原始响应、失败和未知费用预留全部保留，模型排名使用完整 E02。",
              "", "当前限制：历史首次公开时间仍未被证明；自然日历的严格低能见度正例少；按结果选择的 Denver 诊断单独报告；过程相关块不等于独立天气系统；API 服务端计算未知；尚无 16 类灾害的完整模型评价。", "",
              "## 等待你决定的后续工作", "",
              "优先审阅本轮 F 是否超过 FOLLOW/COPY/证据映射强基线，以及改好、改坏和回退各占多少。之后再决定是否扩充独立正例过程、比较逐槽汇总的 E/F 管线、启用持久修订协议，以及接入温度模型。以上均尚未自动启动。", "",
              "详细记录：`RUN_REPORT_CN.md`、`reports/api_forecast_audit_01/VALIDATION.json`、`reports/api_rare_forecast_audit_01/VALIDATION.json`、`reports/e_error_mechanisms_01/REPORT_CN.md`、`reports/temperature_fullcalendar_audit_01/REPORT_CN.md`。"]
    report = ROOT / "PAUSED_SUMMARY_CN.md"
    with report.open("x") as handle:
        handle.write("\n".join(lines) + "\n")
    state = read(ROOT / "EXECUTION_STATUS.json") or {}
    state.update(phase="PAUSED_FOR_USER_REVIEW", updated_at=result["at"],
                 all_registered_work_verified=completed, final_summary="PAUSED_SUMMARY_CN.md")
    temp_state = ROOT / "EXECUTION_STATUS.pause"
    temp_state.write_text(json.dumps(state, indent=2) + "\n")
    temp_state.replace(ROOT / "EXECUTION_STATUS.json")
    write(RUNTIME / "COMPLETE.json", {"paused": True, "all_registered_work_verified": completed})


def main():
    write(RUNTIME / "CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "pid": os.getpid()})
    plan = read(ROOT / "PAUSE_AFTER_BATCH.json")
    deadline = time.monotonic() + 12 * 3600
    jobs = {}
    while time.monotonic() < deadline:
        for name, job in plan["jobs"].items():
            if jobs.get(name, {}).get("state") not in TERMINAL:
                try:
                    jobs[name] = platform(job)
                except (subprocess.TimeoutExpired, json.JSONDecodeError):
                    jobs[name] = {"name": job, "state": "UNKNOWN"}
        tmp = RUNTIME / "STATUS.next"
        tmp.write_text(json.dumps({"at": dt.datetime.now(dt.timezone.utc).isoformat(), "jobs": jobs}, indent=2) + "\n")
        tmp.replace(RUNTIME / "STATUS.json")
        if len(jobs) == len(plan["jobs"]) and all(j.get("state") in TERMINAL for j in jobs.values()):
            batch = read(ROOT / "BATCH_RESULT.json")
            if batch is not None:
                finish(jobs)
                return
        time.sleep(180)
    write(RUNTIME / "WAIT_LIMIT.json", {"jobs": jobs, "pause_confirmed": False,
          "reason": "Terminal job and audit evidence incomplete; no automatic retry or next phase"})


if __name__ == "__main__":
    main()
