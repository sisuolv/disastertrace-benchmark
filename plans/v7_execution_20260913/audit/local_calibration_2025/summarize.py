"""Write the completed cross-year local calibration handoff from checked artifacts."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def main():
    validation = load(HERE / "FULL_VALIDATION.json")
    dataset = load(HERE / "local_dataset_01/REGIONAL_JOIN_AUDIT.json")
    results = load(HERE / "static_comparison_01/REPORT.json")
    network = []
    for name in ["full_captures_01", "full_native_new_01", "native_retry_02"]:
        path = HERE / name / "MANIFEST.json"
        if path.exists():
            network.extend(load(path)["rows"])
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_cross_year_local_fit_and_exposed_static_evaluation",
        "source_period": "2025-12-01/2025-12-30 exclusive",
        "network_attempts": len(network), "complete_http200": sum(r["complete"] and r["http_status"] == 200 for r in network),
        "network_body_bytes": sum(r["bytes"] for r in network),
        "native_taf_products": dataset["native_taf_bulletins_decoded"] + dataset["unparsed_native_taf_envelopes_preserved"],
        "decoded_native_taf": dataset["native_taf_bulletins_decoded"],
        "preserved_unparsed_native_taf": dataset["unparsed_native_taf_envelopes_preserved"],
        "native_metar_rows": dataset["metar_rows"], "decoded_metar_rows": dataset["decoded_metar_rows"],
        "opportunities_two_thresholds": dataset["opportunities"],
        "banks": ["bank_matched_01", "bank_expanded_01"], "dataset": "local_dataset_01",
        "static_comparison": "static_comparison_01/REPORT.json", "validation": "FULL_VALIDATION.json",
        "january_outcomes_used_in_fit": False, "january_calendar_previously_exposed": True,
        "full_adaptive_policy_execution": False, "formal_monitoring_admission": False,
        "new_model_calls": 0,
    }
    lines = [
        "# Dec2025 Front 本地映射与 Jan2026 固定日历比较", "",
        "沿用 Dec2023 扩展已经固定的两个分割与同一计数映射，年份平移到 2025→2026。",
        "没有根据 Jan2026 的收益调整日期、阈值、方法或选择映射；旧 Bay2025 迁移银行作为原样对手。", "",
        "## 1. 实际下载与验收", "",
        f"真实尝试 {summary['network_attempts']} 个网络请求，其中 {summary['complete_http200']} 个 HTTP200 完整成功；",
        f"新正文 {summary['network_body_bytes']:,} bytes。原生 METAR {summary['native_metar_rows']} 条，",
        f"解析成功 {summary['decoded_metar_rows']} 条；原生 TAF {summary['native_taf_products']} 份，",
        f"解析成功 {summary['decoded_native_taf']} 份，不可解析版本保留 {summary['preserved_unparsed_native_taf']} 份。", "",
        f"构建两阈值共 {summary['opportunities_two_thresholds']} 个机会，正式比较仍只使用原 Jan2026 的 1,000 m 目标。",
        f"独立核验 {validation['source_bodies_and_receipts_verified']} 个构建源正文/回执，两个训练分割、特征格计数和六组静态成绩均通过。", "",
        "这里的完整公告覆盖指固定站点/日期 TAF 目录列出的所有产品；不能据此保证目录包含每个取消/NIL 公告。",
        "原始 first-seen 时序仍未证明，历史可用时间保持声明的回放假设。", "",
        "## 2. 训练与检查", "",
        "matched: 12/02–12/14 训练，12/15 隔离，12/16–12/21 检查，与原 Bay2025 日期相同。",
        "expanded: 12/02–12/21 训练，12/22 隔离，12/23–12/28 检查；同时改变地区与训练长度。", "",
        "| 映射 | 训练机会 | 不同训练目标 | 检查机会 | 检查期正例机会（按阈值） |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, split in validation["splits"].items():
        lines.append(f"| {name} | {split['fit_opportunities']} | {split['fit_unique_targets']} | {split['check_opportunities']} | {json.dumps(split['heldout_positive_opportunities_by_threshold'])} |")
    lines += ["", "不同目标计数包含两个阈值，重复时距共用同一个小时结果，不等于独立天气过程数量。",
              "未出现的正例阈值计数为零；没有正例的检查期不能验证极端类别的区分能力。", "",
              "## 3. 同一 Jan2026 日历的实际结果", "",
              "| 前期拟合映射 | 只有共同 TAF 的 Brier | 全部注册邻站槽位的 Brier |",
              "| --- | ---: | ---: |"]
    names = [("bay_transferred_original", "原 Bay2025 迁移"), ("front_local_matched_window", "Front matched 本地"), ("front_local_expanded_window", "Front expanded 本地")]
    for name, label in names:
        common = results["arms"][name + "/common_only"]["scores"]
        all_read = results["arms"][name + "/all_registered"]["scores"]
        lines.append(f"| {label} | {common['system_brier']:.9f} | {all_read['system_brier']:.9f} |")
    reference = results["arms"]["bay_transferred_original/common_only"]["scores"]
    lines += ["", f"六组完全保留 {reference['opportunities']} 个机会及共同的 {reference['settled']} 个结算结果，",
              f"{reference['missing']} 个缺失结果没有按方法删除或补成负例。先冻结程序预测，再在比较进程中读取结果。",
              "项目已经使用过这套 Jan2026 日历，所以它仍是已暴露开发比较，不是新独立确认。", "",
              "## 4. 两年份对照", "",
              "| 日历 | 映射 | common-only Brier | all-registered Brier |",
              "| --- | --- | ---: | ---: |"]
    earlier = load(HERE.parent / "local_calibration_precheck/static_comparison_01/REPORT.json")
    for year, report in [("Jan2024", earlier), ("Jan2026", results)]:
        for name, label in names:
            common = report["arms"][name + "/common_only"]["scores"]["system_brier"]
            all_read = report["arms"][name + "/all_registered"]["scores"]["system_brier"]
            lines.append(f"| {year} | {label.replace('2025', '')} | {common:.9f} | {all_read:.9f} |")
    lines += ["", "两年采用相同方法有助于检查结论是否只来自某一年份，仍不能把日历年等同于已核验的独立天气过程。",
              "本地化不保证更低损失，取得全部邻站证据也不保证对未来目标有用；保留每一个正负结果。", "",
              "实际方向：Jan2024 两版本地映射的 common-only 损失均低于 Bay 迁移；Jan2026 两版均高于 Bay 迁移。",
              "Jan2026 的 matched 映射读取全部邻站槽位后略低于自身 common-only，但仍高于原 Bay 基线；",
              "expanded 映射全读后反而更差。不能利用这些已暴露结果事后选择主银行。",
              "Jan2026 本地银行的 pooled 回退机会从原 Bay 的 418 降至 32，但损失反而升高：格子覆盖率不等于预测质量。", "",
              "## 5. 后续使用规则", "",
              "1. 新运行同时保留原迁移与两版本地基线，并预先确定主比较；旧 LLM 分数不套换新基线。",
              "2. 先诊断固定证据的 E 理解、直接 F 输出与提示敏感性，再解释主动获取或共享分配。",
              "3. 完整自适应比较必须重新运行状态、选源与提示，静态程序表不能替代重跑。",
              "4. 进一步的时间/地区确认须事先登记；不要利用本表挑选收益更好的月份或银行。", "",
              "入口：`FULL_EXECUTION.json`、`FULL_VALIDATION.json`、`static_comparison_01/REPORT.json`。", ""]
    report_path = HERE / "FULL_REPORT_CN.md"
    with report_path.open("x") as stream:
        stream.write("\n".join(lines))
    summary["artifact_sha256"] = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in ["FULL_REPORT_CN.md", "FULL_VALIDATION.json", "FULL_CONTRACT.json", "bank_matched_01/BANK.json", "bank_expanded_01/BANK.json", "static_comparison_01/REPORT.json"]}
    with (HERE / "FULL_EXECUTION.json").open("x") as stream:
        json.dump(summary, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "artifact_sha256"}, indent=2))


if __name__ == "__main__":
    main()
