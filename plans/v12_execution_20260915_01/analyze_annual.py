"""Audit transport, native parsing and usable target labels as separate levels."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "annual_stage_B"


def read(path):
    return json.loads(path.read_text())


def main():
    joined = read(OUT / "joins/RESULT.json")
    rows, decisions, failures, labels = [], Counter(), Counter(), Counter()
    for result in joined.get("results", []):
        unit = result["unit"]
        if not result.get("complete"):
            rows.append({"unit": unit, "native_join_complete": False, "status": result.get("status")})
            continue
        dataset = Path(result["dataset"])
        impact = read(dataset / "SOURCE_IMPACT.json")
        outcomes = {o["target_id"]: o for o in read(dataset / "private/OUTCOMES.json")}
        opportunities = read(dataset / "public/OPPORTUNITIES.json")
        by_threshold, missing = defaultdict(Counter), Counter()
        for o in opportunities:
            y = outcomes[o["target_id"]]
            threshold = str(o["threshold_m"])
            category = "missing" if y["outcome"] is None else "positive" if y["outcome"]==1 else "negative"
            by_threshold[threshold][category] += 1
            labels[threshold+":"+category] += 1
            if y["outcome"] is None:
                missing[y["status"]] += 1
        decisions.update(impact["decisions"])
        failures.update(f.get("reason", f["status"]) for f in impact["failures"])
        rows.append({"unit": unit, "native_join_complete": True, "opportunities": len(opportunities),
            "verified_capture_references": impact["verified_captures"],
            "parsed_TAF_references": impact["decoded_native_taf"],
            "TAF_failure_references": len(impact["failures"]), "cutoff_TAF_decisions": impact["decisions"],
            "labels_by_threshold": {k:dict(v) for k,v in by_threshold.items()}, "missing_reasons": dict(missing)})
    result = {"all_native_joins_complete": joined["passed"], "registered_months": joined.get("expected_units"),
        "completed_months": joined.get("completed_units"), "units": rows,
        "cutoff_TAF_decisions": dict(decisions), "TAF_failure_reasons": dict(failures),
        "label_opportunities": dict(labels),
        "source_reference_counts_are_unique_objects": False,
        "temporal_scope": "registered2023-2024 archive windows; source QA/fit/calibration, not unseen confirmation",
        "clock_scope": "native latest-product decisions at registered cutoff; fitted features separately use cutoff minus600s",
        "transport_success_implies_parsing_or_task_success": False,
        "new_HTTP_requests": 0, "new_model_calls": 0}
    with (OUT / "DATA_QUALITY_REPORT.json").open("x") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    lines = ["# 年度数据可用性分层核验", "",
        f"严格原生构建完成 {joined.get('completed_units')}/{joined.get('expected_units')} 个月。目录、原文字节、语义解析和可结算标签分别统计。",
        "同一原文可被相邻月或多个目标引用，不能把下面的引用数量当成新的独立样本。", "",
        "| 地区月份 | 原生构建 | TAF 解析引用/失败引用 | <1km 正/负/缺 | <5km 正/负/缺 |",
        "|---|---|---:|---:|---:|"]
    for row in rows:
        if not row["native_join_complete"]:
            lines.append(f"| {row['unit']} | {row.get('status')} | NA | NA | NA |")
            continue
        counts=[]
        for threshold in ("1000", "5000"):
            m=row["labels_by_threshold"].get(threshold,{})
            counts.append("/".join(str(m.get(k,0)) for k in ("positive","negative","missing")))
        lines.append(f"| {row['unit']} | 完成 | {row['parsed_TAF_references']}/{row['TAF_failure_references']} | {counts[0]} | {counts[1]} |")
    lines += ["", "完整分层、缺失原因、TAF 冲突/无覆盖/不支持状态见 DATA_QUALITY_REPORT.json。",
        "数据构建完成允许保留真实缺报与不支持语义；它不意味着每条预报都能被解析、每个天气目标都能结算或缺失无偏。",
        "这些年份承担来源核查、拟合与校准角色，不计入独立确认。新真实异常状态可用于后续合同开发，但需登记暴露和新的实验身份。"]
    (OUT / "DATA_QUALITY_REPORT_CN.md").write_text("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
