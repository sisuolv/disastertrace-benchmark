"""Give reviewers explicit preferred artifacts while retaining earlier attempts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest

BASE = Path(__file__).resolve().parent


def main():
    groups = {
        "Contracts and implementation": [
            "PLAN_AMENDMENT_CN.md", "OVERALL_EXECUTION_ROADMAP_CN.md", "REVIEW_RESOLUTION.json",
            "HAZARD_REVIEW_OVERLAY.json", "NOVELTY_RECHECK_CN.md", "review_replay_01/CORE_AND_ANALYSIS_VALIDATION_09.xml",
        ],
        "Native data and prior calibration": [
            "extension_bay_area_01/REGIONAL_JOIN_AUDIT.json", "extension_front_range_03/REGIONAL_JOIN_AUDIT.json",
            "replication_2026_01/REGIONAL_JOIN_AUDIT.json", "calibration_bank_01/CHECK_REPORT.json",
            "calibration_bank_2025_01/CHECK_REPORT.json", "independent_metar_validation_02/VERIFIED.json",
            "independent_metar_validation_03/VERIFIED.json", "independent_taf_validation_02/REPORT.json",
        ],
        "All-opportunity F and protocol results": [
            "calendar_analysis_bay_02/REPORT.json", "calendar_analysis_front_02/REPORT.json", "calendar_analysis_replication_01/REPORT.json",
            "wrapper_analysis_bay_01/REPORT.json", "wrapper_analysis_front_01/REPORT.json", "wrapper_analysis_replication_01/REPORT.json",
            "static_baselines_bay_03/REPORT.json", "static_baselines_front_02/REPORT.json", "static_baselines_replication_01/REPORT.json",
            "ranking_analysis_bay_01/REPORT.json", "ranking_analysis_front_01/REPORT.json", "ranking_analysis_replication_01/REPORT.json",
            "figures_execution_01/PLOT_VALUES.json",
        ],
        "E coverage, model understanding and costs": [
            "joint_E_analysis_bay_01/REPORT.json", "joint_E_analysis_front_01/REPORT.json", "joint_E_analysis_replication_01/REPORT.json",
            "e_diagnostic_analysis_01/REPORT.json", "e_order_analysis_01/REPORT.json", "E_CASE_WALKTHROUGH_CN.md",
            "WRAPPER_CASE_WALKTHROUGH_CN.md", "report_event_profile_02/REPORT.json",
        ],
        "Native multimodal and source-version checks": [
            "gpu_mm_01_validation_01/VERIFIED.json", "bulk_service_validation_01/VERIFIED.json",
            "live_observer_validation_01/VERIFIED.json", "hydro_revision_validation_01/REPORT.json",
            "HYDRO_PAYLOAD_VERSION_CHECK.json", "hydro_metadata_validation_01/REPORT.json", "hydro_stage_validation_01/REPORT.json",
        ],
        "Portable replay and actual execution": [
            "packaged_replay_01_receipts/COMPLETE.json", "packaged_replay_02_receipts/COMPLETE.json",
            "packaged_replay_replication_01_receipts/COMPLETE.json",
            "EXECUTION_STATUS.json", "gpu_queue_01/STATUS.json", "delivery_queue_01/STATUS.json", "e_order_queue_01/STATUS.json",
            "FINAL_ACCOUNT_CHECK.json",
        ],
    }
    for prefix, group in (("resource_analysis_", "E coverage, model understanding and costs"),
                          ("gpu_occupancy_validation_", "Portable replay and actual execution")):
        name = "REPORT.json" if prefix.startswith("resource") else "VERIFIED.json"
        paths = sorted(BASE.glob(prefix + "*/" + name))
        if paths:
            groups[group].append(str(paths[-1].relative_to(BASE)))
    records = []
    lines = ["# 本轮文件阅读索引", "",
             "先读 FINAL_REPORT_CN.md，再按本表定位。较早目录保留为历史输入、失败或较窄实验，不能只按文件数量推断完成范围。",
             "表中路径相对本目录；大型原始数据和输出通过发布目录的 EVIDENCE_INDEX.json 定位并恢复。",
             "本表只说明推荐入口和文件是否存在，不代替科学准入或完整复跑。", ""]
    for group, paths in groups.items():
        lines += ["## " + group, "", "| 推荐文件 | 当前状态 |", "| --- | --- |"]
        for name in paths:
            path = BASE / name
            exists = path.is_file()
            status = "available" if exists else "pending"
            records.append({"group": group, "path": name, "status": status,
                            "sha256": digest(path) if exists else None})
            lines.append(f"| `{name}` | {status} |")
        lines.append("")
    lines += ["## 版本解释", "",
              "- Front Range 当前输入使用 extension_front_range_03；更早尝试保留，不替代该数据审计。",
              "- 完整 Bay/Front 两协议比较使用 calendar_analysis_*_02；早期仅 base 协议或程序分析单列。",
              "- Bay 常数强对照使用 static_baselines_bay_03，Front 使用 static_baselines_front_02；旧失败日志保留。",
              "- charged selector 的首个独立核验使用 gpu_active_pilot_01_validation_02，后续日历使用各自冻结 v2 批次。",
              "- 109 项实现/分析测试、原审阅包示例、排序/配对/发布补查分别记录；不能把重复运行加成独立测试或模型样本。",
              "- e_order 队列只处理已有 96 个 E 案例的顺序复核；H08 检查只处理来源、原生水位链和阈值合同预检。",
              "- 两次隔离发布包回放各重建 5,656 条已记录输出；回放没有新增模型推理。", ""]
    (BASE / "ARTIFACT_INDEX_CN.md").write_text("\n".join(lines))
    (BASE / "PREFERRED_ARTIFACTS.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "path_root": "this_bundle", "artifacts": records,
        "scientific_admission_implied": False, "historical_attempts_preserved": True,
    }, indent=2) + "\n")
    print(json.dumps({"preferred": len(records), "pending": [r["path"] for r in records if r["status"] == "pending"]}))


if __name__ == "__main__":
    main()
