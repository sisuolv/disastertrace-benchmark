"""Separate implementation acceptance, scientific comparison and batch closure."""
import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AUTHORIZED_SOURCE_EDITS = {
    "monitoring_fixed_v1/adaptive.py", "monitoring_fixed_v1/admission.py",
    "monitoring_fixed_v1/native_feature.py", "monitoring_fixed_v1/outcomes.py",
    "monitoring_v1/formal_session.py", "monitoring_v1/policies.py",
    "monitoring_v1/session_checkpoint.py",
}


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)


def preservation():
    before = read(ROOT / "PRESERVATION_BEFORE.json")
    source = REPO / "disastertrace-starter/src/disastertrace"
    records = []
    for name, sha in before["files"].items():
        p = Path(name)
        actual = digest(p) if p.exists() else None
        status = "unchanged"
        if actual != sha:
            try:
                relative = p.relative_to(source).as_posix()
            except ValueError:
                relative = None
            frozen = ROOT / "branch_source/disastertrace" / (relative or "invalid")
            status = "authorized_current_implementation_edit" if relative in AUTHORIZED_SOURCE_EDITS and frozen.exists() and digest(frozen)==actual else "unexpected_change"
        records.append({"path": name, "before": sha, "after": actual, "status": status})
    frozen = read(ROOT / "STAGE_C_SOURCE_FREEZE_02.json")["files"]
    differences = [p for p,sha in frozen.items() if not Path(p).exists() or digest(Path(p)) != sha]
    return {"passed": not differences and all(r["status"]!="unexpected_change" for r in records),
        "scope": before["scope"], "records": records, "isolated_source_differences": differences,
        "unchanged": sum(r["status"]=="unchanged" for r in records),
        "authorized_source_edits": sum(r["status"]=="authorized_current_implementation_edit" for r in records),
        "raw_data_universal_preservation_claim": False}


def tests():
    names = ["MONITORING_REGRESSION_01.xml", "SILICONFLOW_TRANSPORT.xml", "STAGE_C_INTEGRATION_05.xml", "REPORT_BOUNDS.xml", "CLOSEOUT_HANDOFF.xml"]
    nodes, failures, skips = set(), [], []
    for name in names:
        for node in ET.parse(ROOT / "tests" / name).findall(".//testcase"):
            key = node.attrib.get("classname", "") + "::" + node.attrib["name"]
            nodes.add(key)
            if node.find("failure") is not None or node.find("error") is not None:
                failures.append(key)
            if node.find("skipped") is not None:
                skips.append(key)
    return {"passed": bool(nodes) and not failures and not skips, "unique_nodes": len(nodes),
        "failures": failures, "skips": skips, "files": names,
        "synthetic_API_responses_are_not_real_model_calls": True,
        "prior_failed_qualification_logs_retained": True}


def jobs():
    result = []
    handoff = read(ROOT / "stage_C_audit_handoff_01/ORIGINAL_JOB_TERMINAL.json", {})
    for p in ROOT.glob("runtime/*/JOB.json"):
        job = read(p)
        job.update(runtime=str(p.parent), exit=read(p.parent / "EXIT.json"),
            deadline_stop=read(p.parent / "DEADLINE_STOP.json"))
        if job["job_id"] == handoff.get("job_id") and handoff.get("state") in {"STOPPED", "FAILED", "SUCCEEDED"}:
            job["controlled_audit_handoff_terminal"] = handoff
        result.append(job)
    return result


def summary():
    auth = read(ROOT / "EXECUTION_AUTHORIZATION.json")
    now = dt.datetime.now(dt.timezone.utc)
    keep, checks = preservation(), tests()
    engineering = read(ROOT / "C2_ENGINEERING_RESULT.json", {})
    noop = read(ROOT / "C2_NOOP_EQUIVALENCE.json", {})
    census = read(ROOT / "C2_STATE_CENSUS.json", {})
    download = read(ROOT / "annual_stage_B/DOWNLOAD_STATUS.json", {})
    joins = read(ROOT / "annual_stage_B/joins/RESULT.json", {})
    fit = read(ROOT / "annual_stage_B/fit/RESULT.json", {})
    stage = read(ROOT / "stage_C/RESULT.json", {})
    analysis = read(ROOT / "stage_C/ANALYSIS.json", {})
    behavior = read(ROOT / "SELECTOR_BEHAVIOR_DIAGNOSTIC.json", {})
    full = read(REPO / "plans/v11_execution_20260915_01/fullweek_02/RESULT.json", {})
    compatibility = read(ROOT / "api_compatibility_01/RESULT.json", {})
    compatibility_results = [read(p) for p in sorted(ROOT.glob("api_compatibility_*/RESULT.json"))]
    running = jobs()
    all_exited = all(j["exit"] is not None for j in running)
    all_terminal = all(j["exit"] is not None or j.get("controlled_audit_handoff_terminal") for j in running)
    timed_out = now >= dt.datetime.fromisoformat(auth["deadline_at"])
    a_passed = all([keep["passed"], checks["passed"], engineering.get("passed"),
        noop.get("passed_all_parents"), census.get("passed"), (ROOT / "E_STATUS_SUMMARY_IMPACT.json").exists(),
        read(ROOT / "ANNUAL_SUMMARY_IMPACT.json", {}).get("passed")])
    actual_intents = len(list((ROOT / "stage_C").glob("*/spool/*.api_intent.json")))
    return {"at": now.isoformat(), "started_at": auth["at"], "deadline_at": auth["deadline_at"],
        "SCOPED_IMPLEMENTATION_ACCEPTANCE": bool(a_passed),
        "SCIENTIFIC_COMPARISON_COMPLETE": {"old_fullweek_development": bool(full.get("passed")),
            "finite_C2_development": bool(engineering.get("passed")),
            "annual_model_development": bool(analysis.get("formal_comparison_complete")),
            "independent_confirmation": False, "novelty_proved": False},
        "ready_to_close": all_terminal or timed_out, "all_worker_exits_observed": all_exited,
        "all_worker_terminal_states_observed": all_terminal,
        "stage_A": {"passed": bool(a_passed), "parent_reconstructions": 6, "original_policy_continuations": 6,
            "treatment_branches": engineering.get("actual_treatment_attempts"),
            "pairs_with_probability_change": engineering.get("comparisons_with_effective_probability_change"),
            "branch_positive_outcomes": sum(next(iter(p["metrics"].values()))["positive"] for p in engineering.get("parents", [])),
            "global_dates": engineering.get("global_dates"),
            "taf_coverage_tasks": census.get("coverage"), "taf_reference_tasks": census.get("new_taf_tasks"),
            "taf_intervention_status": census.get("taf_intervention_status")},
        "stage_B": {"catalog_months": read(ROOT / "annual_stage_B/PREPARATION_RESULT.json", {}).get("completed_region_months"),
            "download": download, "native_joins_complete": joins.get("completed_units", 0),
            "all_native_joins_passed": joins.get("passed", False), "fit_result": fit,
            "tail_result": read(ROOT / "annual_stage_B/TAIL_RESULT.json")},
        "stage_C": {"status": stage.get("status", "completed" if stage else "waiting_or_running"),
            "execution_passed": stage.get("passed", False), "formal_controller_dispatches": stage.get("new_model_calls"),
            "http_attempt_intents": actual_intents, "registered_HTTP_cap": auth["max_model_formal_requests"],
            "provider_reported_tokens": analysis.get("provider_reported_tokens"),
            "selector_calls": analysis.get("selector_calls"), "valid_selector_calls": analysis.get("valid_selector_calls"),
            "selector_statuses": analysis.get("selector_statuses"), "format_diagnostics": analysis.get("format_diagnostics"),
            "error_key_profiles": analysis.get("error_key_profiles"),
            "selector_behavior": {k: behavior.get(k) for k in ("counts", "option_count_histogram", "valid_selection_patterns", "actual_source_statuses")},
            "analysis_available": analysis.get("available", False),
            "completed_arms": len(stage.get("results", [])), "formal_score_groups": len(stage.get("scored", []))},
        "parallel_scoring_handoff": read(ROOT / "stage_C_audit_handoff_01/RESULT.json"),
        "compatibility": {"attempts": sum(r.get("attempts",0) for r in compatibility_results),
            "initial_http_status": compatibility.get("http_status"),
            "initial_synthetic_instruction_passed": compatibility.get("passed"),
            "results": compatibility_results, "retry_attempts": 0},
        "tests": checks, "preservation": {k:v for k,v in keep.items() if k!="records"}, "jobs": running,
        "h100_submissions": sum(j.get("gpus",0) for j in running),
        "confirmation_opened": False, "benchmark_hazard_this_batch": "H15 aviation visibility",
        "resource_interpretation": "CPU acquisition/build/replay plus remote API; no local GPU generation. Codex does not parse each weather report; Codex token accounting unavailable.",
        "preservation_detail": keep}


def main(write):
    if (ROOT / "RESULT_SUMMARY.json").exists():
        raise ValueError("Batch summary already published; do not overwrite closure")
    if write and (ROOT / "annual_stage_B/joins/RESULT.json").exists() and not (ROOT / "annual_stage_B/DATA_QUALITY_REPORT.json").exists():
        with (ROOT / "logs/annual_quality_analysis.log").open("x") as log:
            quality = subprocess.run([sys.executable, str(ROOT / "analyze_annual.py")], stdout=log, stderr=subprocess.STDOUT)
        if quality.returncode:
            publish(ROOT / "ANNUAL_QUALITY_ANALYSIS_FAILURE.json", {"exit_code": quality.returncode})
    stage = ROOT / "stage_C/RESULT.json"
    if write and stage.exists() and not (ROOT / "stage_C/ANALYSIS.json").exists():
        with (ROOT / "logs/stage_c_analysis.log").open("x") as log:
            completed = subprocess.run([sys.executable, str(ROOT / "analyze_stage_c.py")], stdout=log, stderr=subprocess.STDOUT)
        if completed.returncode:
            publish(ROOT / "STAGE_C_ANALYSIS_FAILURE.json", {"exit_code": completed.returncode})
    data = summary()
    if not write:
        print(json.dumps({k:v for k,v in data.items() if k!="preservation_detail"}, indent=2))
        return
    if not data["ready_to_close"]:
        raise ValueError("Registered workers are not terminal; keep the batch open")
    keep = data.pop("preservation_detail")
    publish(ROOT / "PRESERVATION_AFTER.json", keep)
    data["BATCH_CLOSEOUT"] = ("CLOSED" if data["all_worker_exits_observed"] else
        "CLOSED_WITH_CONTROLLED_AUDIT_HANDOFF" if data["all_worker_terminal_states_observed"] else
        "CLOSED_WITH_UNOBSERVED_WORKER_EXIT")
    publish(ROOT / "RESULT_SUMMARY.json", data)
    a, b, c = data["stage_A"], data["stage_B"], data["stage_C"]
    lines = ["# v12 十小时执行结果", "", f"开始：{data['started_at']}；汇总：{data['at']}；约定截止：{data['deadline_at']}。", "",
        "本轮实际灾种是 H15 航空能见度。全体 16 类灾害的总体计划保持，但不能把本轮结果当作全部灾种的完成证明。", "",
        "## 已完成的工程与真实数据验证", "",
        f"- 局部实现验收：{data['SCOPED_IMPLEMENTATION_ACCEPTANCE']}；测试共 {data['tests']['unique_nodes']} 个去重节点，失败 {len(data['tests']['failures'])}、跳过 {len(data['tests']['skips'])}。",
        "- 修复 E 汇总漏计 supported、年度样例摘要和校准 bank 输入守卫。原全周 F、Y、掩膜和损失不改写。",
        "- 既有全周正式审计完成：840 条轨迹、12,096 个机会；重新派生完整十配对、正负例和缺失分层，见 FULLWEEK_FINDINGS_CN.md。",
        f"- 六个父状态重建及六次原策略续跑逐项一致；正式完成 {a['treatment_branches']} 条处理分支，{a['pairs_with_probability_change']} 个配对出现有效概率变化。",
        "- 六个工程父会话的已结算正例均为零，来自同一日期；当前查询收益仅是负例概率误差的诊断，不是极端事件检出能力证据。",
        "- 来源普查及 144 个 TAF E 参考任务完成，72 个注册覆盖任务全为 full；TAF 消费接口已审计，尚未做真实 TAF 处理干预。", "",
        "## 年度数据与模型实验", "",
        f"- 年度目录：{b['catalog_months']}/72；新增唯一报文成功数：{b['download'].get('verified_new_unique')}/{b['download'].get('planned_unique')}。",
        f"- 完整原生月构建：{b['native_joins_complete']}/72；年度拟合状态：{b['fit_result'].get('status','尚无终态')}。",
        "- 原文字节、TAF 解析、目标标签与缺报分别核验，见 annual_stage_B/DATA_QUALITY_REPORT_CN.md；传输成功不等于每条语义都可解析。",
        "- 预先固定 2023 年拟合、2024 年 1—11 月校准；原先使用过的 2024 年 12 月排除。本次没有参数搜索或确认集访问。",
        f"- DeepSeek-V4-Flash 条件实验：{c['status']}；HTTP 请求意图 {c['http_attempt_intents']}/288；正式控制器派发 {c['formal_controller_dispatches']}。",
        f"- 合法 selector 回复：{c['valid_selector_calls']}/{c['selector_calls']}；原契约下的格式失败仍计入完整分母。",
        "- 只读行为诊断：71 次合法回复中，58 次不查询、13 次按目录原顺序选择全部三个候选；未观察到合法的严格子集选择或重排。实际完成 38 个来源请求，37 个产品事实与 1 个订正时序无法证明分别记录；不能把完整实验误写成已经证明精细主动分配能力。",
        "- 模型只选择补充查询，概率由冻结程序预测器产生；9 个条件区分模型选择、批量获取、覆盖率规则与预算/共享 2×2。",
        "- 结果表、正负例贡献、缺失敏感性界及实际 API 账本在 stage_C/REPORT_CN.md、ANALYSIS.json、RESOURCE_AND_API_LEDGER.json；未满足放行门槛时不生成模型胜负。", "",
        "## 失败与限制", "",
        "首次 API 兼容性请求返回 HTTP 200 且 JSON 合法，但未遵守合成题的一查询要求；失败保留，没有重试或据此挑选其他模型。生产 selector 合同允许排名列表并由引擎执行预算约束，正式表现另行统计。",
        "观察到真实输出契约失败后，使用第二个且最后一个兼容性名额测试供应方 JSON schema 模式：相同合成提示通过结构与选择检查。这是开发诊断；不替换本轮自由文本正式回复，也不证明完整天气任务已修复。",
        "本地离线接入最初出现测试夹具预期错误和源码包入口缺失；保留全部失败记录后，完整独立源码快照通过接入核验。ACP 原分支合同实际绑定了冻结分支源码，本地 CCI 的 editable 导入差异单独记录。",
        "年度下载超时、429、缺字节、解析不支持、模型无效回复、未知费用及缺失结果均按原记录保留，不换日期补好结果。详细终态在 RESULT_SUMMARY.json 与各 worker.log。",
        "108 个方法运行完成后，原串行评分尾部通过有记录的平台停止交给独立并行审计。已完成评分复用，剩余组使用相同冻结评分代码；原停止状态和未知的进程退出码保留，不伪称原 worker 正常结束。未新增模型请求或预测轨迹，交接依据在 stage_C_audit_handoff_01。",
        "年度拟合按已有 cutoff−600 秒特征约定，应用使用实际固定预测时点；这一区别已登记，后续应检查分布差异，不能声称时间完全一致。",
        "当前结果属于已暴露开发数据。共享掩膜不保证缺失无偏，小时级样本不等于独立天气过程；novelty、LLM 增量和完整 16 类交付仍需独立验证。", "",
        "## 资源与保全", "",
        f"本轮 H100 提交 {data['h100_submissions']}；使用并行 CPU 作业和远程模型 API。数据解析、下载、hash 和统计均在程序中执行，不逐条调用 Codex。Codex token 无可用精确统计，不能给出虚构节省比例。",
        f"保护检查：{keep['passed']}；原清单 {keep['unchanged']} 项未变，{keep['authorized_source_edits']} 个当前实现文件是本次明确修改。检查范围是 188 项相关文件，不是全仓库原始数据逐字节审计。",
        "用户授权保存的凭据位于仓库之外，未写入本报告或源码；供应方实际账单未查询，未知费用不记作零。", "",
        f"批次收尾：{data['BATCH_CLOSEOUT']}。后续工作见 NEXT_ACTION.md；已消耗父重建、续跑、分支和模型请求身份均不得重新使用。"]
    (ROOT / "FINAL_REPORT_CN.md").write_text("\n".join(lines)+"\n")
    next_text = """# 后续执行建议

先复核本轮 RESULT_SUMMARY.json 和 FINAL_REPORT_CN.md，保持 C1/C2/C3 方向，不再增加核心概念。

1. 年度源链若未完整通过，按原失败 ID、字节和日志定位恢复范围；新恢复身份只处理明确缺项，保留原失败，禁止重开消费过的 launcher。若已完成，则核对 fit/calibration 足迹、正例季节覆盖及 fit/application 时点差异。
2. 读取固定年度预测器下的模型与强程序比较。先处理已观察到的 queries（主要别名）、query_handles 等字段与 query_order 的不一致及 JSON 外文字；原 288 槽不修改或重跑。供应方 strict JSON schema 已通过一个合成兼容性试验，后续应在新身份中验证实际接口，并与原自由输出分轨。区分格式失败、合法选择、负例贡献、正例贡献及基线更新；不以一次均值胜出作为扩大模型矩阵的理由。
   现有 71 次合法动作只有 58 次全不取、13 次全取，未出现严格子集或重排。先用本轮冻结目录检查选择空间、预算约束和程序预测器对不同合法资料的响应，区分任务选择空间有限与策略没有利用空间；增加模型数量不能代替这项检查。行为诊断不访问未来 Y，也不把 217 次无效答案重新解释成合法动作。
3. C2 下一实证应按公开源状态选择多个独立过程的缺报、删失、冲突、真实版本订正及 TAF 窗口案例，预先冻结父会话与有限计划。当前六父均为负例且同日，不能承担极端天气检出结论；新的正例研究需在开发日历预注册，不选择当前最有利损失。
4. 在同一个总预算、并发及截止下报告联合可达集合和费用—时间可行组合，继续保持 E 与 F 分离。先确认严格支持任务具有真实多样性，再扩展影像感知；gold mask 不得当作模型已见证据。
5. 确认集保持关闭，直到方法、预测器、失败处理、统计过程分组和主比较全部固定。之后单独注册跨独立天气过程确认；无收益也完整报告。
6. 温度、水文和其他灾种按各自 A0—A5、E/F/D/MM 门槛推进；已有 sample 可读不代表专业基线、时间语义、监督标签及完整任务链均合格。

减少 Codex 开销的方式继续固定为：程序批处理数据、每阶段写短状态、失败一次后定位具体回执、关键门槛再由 Codex 阅读；不让 LLM 做逐条原始数据解析或替代确定性评分。
"""
    (ROOT / "NEXT_ACTION.md").write_text(next_text)
    publish(ROOT / "BATCH_CLOSED.json", {"at": data["at"], "state": data["BATCH_CLOSEOUT"],
        "summary_sha256": digest(ROOT / "RESULT_SUMMARY.json"), "scope_acceptance": data["SCOPED_IMPLEMENTATION_ACCEPTANCE"]})
    print(json.dumps({"closed": True, "state": data["BATCH_CLOSEOUT"], "scope_accepted": data["SCOPED_IMPLEMENTATION_ACCEPTANCE"]}))


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--write", action="store_true")
    main(parser.parse_args().write)
