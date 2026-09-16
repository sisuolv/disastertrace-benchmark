"""Derive corrected E counts and all ten comparisons from unchanged audited rows."""

import importlib.util
import itertools
from collections import defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.native_feature import NativeFeaturePredictor
from disastertrace.monitoring_v1.reporting import e_status_summary
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OLD = REPO / "plans/v11_execution_20260915_01"
ARMS = ["FOLLOW", "F_COMMON", "F_BASE_ONLY", "B11_BATCH", "B11_COVERAGE"]


def main():
    audit, path = read(OLD / "fullweek_02/RESULT.json"), OLD / "fullweek_02/ROWS.json"
    if not audit["passed"] or digest(path) != audit["rows_sha256"]:
        raise ValueError("Original formal audit/rows not verified")
    rows = read(path)
    if len(rows) != 60480 or len({(r["case"], r["arm"], r["opportunity_id"]) for r in rows}) != len(rows):
        raise ValueError("Full method roster is incomplete or duplicated")
    origin = OLD / "analyze_fullweek.py"
    spec = importlib.util.spec_from_file_location("original_paired_analysis", origin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    groups, evidence = defaultdict(list), defaultdict(list)
    for row in rows:
        for label in ("all", "week:" + row["week"], "region:" + row["region"],
                      "region_week:" + row["region"] + ":" + row["week"]):
            groups[(row["threshold"], label)].append(row)
        evidence[(row["threshold"], row["arm"])].append(row)
    counts = {}
    for (threshold, arm), selected in sorted(evidence.items()):
        states = {row["case"] + "/" + row["opportunity_id"]: row["e_status"] for row in selected}
        actual = e_status_summary(states, list(states))
        actual["old_determined"] = audit["metrics"][f"{threshold}__all__{arm}"]["e_determined"]
        actual["newly_counted_supported"] = actual["determined"] - actual["old_determined"]
        actual["future_outcomes_missing_but_E_retained"] = sum(row["outcome"] is None for row in selected)
        counts[f"{threshold}__{arm}"] = actual
    publish(RUN / "E_STATUS_SUMMARY_IMPACT.json", {
        "passed": True, "groups": counts, "method_rows": len(rows),
        "rows_sha256": digest(path), "original_F_Y_mask_loss_unchanged": True,
        "source": "original producer states, fixed roster, independent of Y mask"})
    pairs = list(itertools.combinations(ARMS, 2))
    metrics = {f"{threshold}__{label}__{method}_vs_{reference}": module.paired(values, reference, method)
               for (threshold, label), values in sorted(groups.items()) for reference, method in pairs}
    publish(RUN / "FULLWEEK_PAIRED_DECOMPOSITION.json", {
        "passed": True, "method_rows": len(rows), "pairs": pairs, "metrics": metrics,
        "rows_sha256": digest(path), "original_audit_sha256": digest(OLD / "fullweek_02/RESULT.json"),
        "analysis_base_sha256": digest(origin), "new_analysis_sha256": digest(Path(__file__)),
        "scope": "posthoc descriptive development comparisons, not confirmatory hypothesis tests",
        "global_week_blocks": 4, "independent_process_count": None,
        "missing_bounds_are_not_confidence_intervals": True, "new_model_calls": 0})
    banks = {}
    for case in read(OLD / "fullweek_02/PLAN.json")["cases"]:
        config_path = OLD / "fullweek_02" / case["case"] / "CONFIGS.json"
        for arm, config in read(config_path).items():
            bank = config.get("native_feature_bank")
            if bank is None:
                continue
            key = canonical_hash(bank)
            if key not in banks:
                result = {"bank_sha256": key, "uses": [], "consumer_checks": {}}
                for calibrated in (False, True):
                    try:
                        NativeFeaturePredictor(bank, at=0, calibrated=calibrated)
                        check = {"accepted": True}
                    except (ValueError, OverflowError, TypeError) as exc:
                        check = {"accepted": False, "error": type(exc).__name__, "message": str(exc)}
                    result["consumer_checks"]["calibrated" if calibrated else "raw"] = check
                banks[key] = result
            banks[key]["uses"].append({"case": case["case"], "arm": arm,
                                      "program_prediction": config.get("program_prediction")})
    publish(RUN / "BANK_GUARD_IMPACT.json", {
        "passed": all(row["consumer_checks"]["raw"]["accepted"] for row in banks.values()),
        "banks": list(banks.values()), "historical_probabilities_recomputed": False,
        "scope": "all native feature banks referenced by original fullweek configs",
        "original_raw_track_not_invalidated_by_calibrated_map_validation": True})
    annual = read(OLD / "annual_catalog_01/RESULT.json")
    sample = read(OLD / "annual_catalog_01/SAMPLE_RESULT.json")
    ids = [row["unit"] for row in annual["results"]]
    publish(RUN / "ANNUAL_SUMMARY_IMPACT.json", {
        "passed": len(ids) == len(set(ids)) == 72,
        "original_sample_passed": sample["passed"], "original_unique_units": len(set(ids)),
        "original_complete": sum(row["complete"] for row in annual["results"]),
        "original_failed": sum(not row["complete"] for row in annual["results"]),
        "actual_annual_run_suffers_sample_duplication": not sample["passed"],
        "original_result_sha256": digest(OLD / "annual_catalog_01/RESULT.json"),
        "fixed_future_collector": "annual_catalogs.py", "new_source_requests": 0,
        "regression": "tests/REPORTING_RED.xml -> tests/REPORTING_GREEN.xml"})
    lines = ["# v12：原整周结果的修订解释", "",
             "原840条轨迹、60480方法行已经通过原正式审计；本报告只派生分析，不重新生成原预测。",
             "已暴露开发日历，只有四个全局周；不作为独立确认或新LLM实验。", "",
             "| 阈值 | 方法 | Brier | 正例/已结算 | 缺失 |", "|---|---|---:|---:|---:|"]
    for threshold in (1000, 5000):
        for arm in ARMS:
            row = audit["metrics"][f"{threshold}__all__{arm}"]
            lines.append(f"| {threshold}m | {arm} | {row['brier']:.8f} | {row['positive']}/{row['settled']} | {row['missing']} |")
    lines += ["", "gain = 参考损失 - 方法损失，正数表示改善。", "",
              "| 阈值 | 比较 | 平均gain |", "|---|---|---:|"]
    for threshold in (1000, 5000):
        for reference, method in pairs:
            value = metrics[f"{threshold}__all__{method}_vs_{reference}"]["net_realized_gain"]
            lines.append(f"| {threshold}m | {reference} -> {method} | {value:.8f} |")
    lines += ["", "F_COMMON与其他values后端不同；同后端补证比较应使用F_BASE_ONLY。BATCH为48次/日预算内策略。",
              "E修订补上supported肯定状态，保留缺frame和缺Y；不改变原F、Y、分母、掩膜或Brier。",
              "十个比较均为新增开发描述性分析。缺失敏感性界不是置信区间，不按当前输赢扩展确认日期。", ""]
    (RUN / "FULLWEEK_FINDINGS_CN.md").write_text("\n".join(lines))
    print({"passed": True, "method_rows": len(rows), "pairs": len(pairs), "unique_banks": len(banks)})


if __name__ == "__main__":
    main()
