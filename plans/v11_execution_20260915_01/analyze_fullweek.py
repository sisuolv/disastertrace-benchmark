"""Summarize the complete audited roster, including missing and event-only effects."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

ARMS = ("FOLLOW", "F_COMMON", "F_BASE_ONLY", "B11_BATCH", "B11_COVERAGE")
PAIRS = (("FOLLOW", "F_COMMON"), ("FOLLOW", "F_BASE_ONLY"), ("FOLLOW", "B11_BATCH"),
         ("FOLLOW", "B11_COVERAGE"), ("F_BASE_ONLY", "B11_COVERAGE"), ("B11_BATCH", "B11_COVERAGE"))


def paired(rows, reference, method):
    arms = defaultdict(dict)
    for row in rows:
        key = row["case"] + "/" + row["opportunity_id"]
        if key in arms[row["arm"]]:
            raise ValueError("Duplicate method opportunity")
        arms[row["arm"]][key] = row
    if set(arms[reference]) != set(arms[method]):
        raise ValueError("Different method rosters")
    values = []
    for key, row in sorted(arms[method].items()):
        base = arms[reference][key]
        if base["outcome"] != row["outcome"]:
            raise ValueError("Different settlement masks")
        values.append({"opportunity_id": key, "prediction": row["probability"],
            "base": base["probability"], "outcome": row["outcome"], "region": row["region"],
            "period": row["week"], "source": "IEM routine METAR", "baseline_kind": "research",
            "maturity": "archived_report", "quality": "missing" if row["outcome"] is None else "settled"})
    result = brier_report(values)
    for y, name in ((0, "negative"), (1, "positive")):
        selected = [r for r in values if r["outcome"] == y]
        gain = math.fsum((r["base"]-y)**2 - (r["prediction"]-y)**2 for r in selected)
        result[name] = {"count": len(selected), "conditional_gain": gain/len(selected) if selected else None,
            "gain_contribution_per_settled_opportunity": gain/result["settled"] if result["settled"] else None}
    result["predictions_changed"] = sum(r["base"] != r["prediction"] for r in values)
    return result


def main(batch, out):
    audit = read(batch / "RESULT.json")
    if not audit["passed"] or audit["trajectories"] != 840 or audit["method_rows"] != 60480:
        raise ValueError("Full840trajectory formal audit required")
    if digest(batch / "ROWS.json") != audit["rows_sha256"]:
        raise ValueError("Audited row identity changed")
    rows = read(batch / "ROWS.json")
    if len(rows) != 60480 or {r["arm"] for r in rows} != set(ARMS):
        raise ValueError("Registered five-arm row roster changed")
    groups = defaultdict(list)
    for row in rows:
        for label in ("all", "week:" + row["week"], "region:" + row["region"],
                      "region_week:" + row["region"] + ":" + row["week"],
                      "region_day:" + row["region"] + ":" + row["date"]):
            groups[(row["threshold"], label)].append(row)
    metrics = {f"{threshold}__{label}__{method}_vs_{ref}": paired(values, ref, method)
               for (threshold, label), values in sorted(groups.items()) for ref, method in PAIRS}
    result = {"passed": True, "metrics": metrics, "paired_groups": len(metrics),
        "rows_sha256": digest(batch / "ROWS.json"), "audit_sha256": digest(batch / "RESULT.json"),
        "source_sha256": digest(Path(__file__)), "global_week_blocks": 4,
        "independent_process_count_established": False, "confirmation_opened": False, "new_model_calls": 0,
        "bounds_scope": "binary missing-result sensitivity, not confidence intervals",
        "common_comparison": "different frozen common/values banks; not same-backend acquisition attribution"}
    out.mkdir(exist_ok=False)
    publish(out / "RESULT.json", result)
    lines = ["# 完整季节周五组对照结果", "", "本报告为已暴露开发日历的程序实验；未运行新的 LLM，也未打开独立确认集。",
        "", "168 个日会话条件、840 条方法轨迹、12,096 个机会，保留缺失结果。Brier 越低越好。", "",
        "| 阈值 | 条件 | 已结算 | 正例 | 缺失 | Brier |", "|---|---|---:|---:|---:|---:|"]
    for threshold in (1000, 5000):
        for arm in ARMS:
            m = audit["metrics"][f"{threshold}__all__{arm}"]
            lines.append(f"| {threshold}m | {arm} | {m['settled']} | {m['positive']} | {m['missing']} | {m['brier']:.6f} |")
    lines += ["", "## Coverage 相对 FOLLOW 的季节差异", "",
        "增量定义为 FOLLOW 损失减去 Coverage 损失，正数表示改善。缺失结果界不是统计置信区间。", "",
        "| 阈值 | 全局周 | 平均增量 | 正例数 | 正例条件增量 |", "|---|---|---:|---:|---:|"]
    for key, m in metrics.items():
        if "__week:" in key and key.endswith("B11_COVERAGE_vs_FOLLOW"):
            threshold, week, _ = key.split("__")
            value = m["positive"]["conditional_gain"]
            formatted = "不适用" if value is None else f"{value:.6f}"
            lines.append(f"| {threshold}m | {week[5:]} | {m['net_realized_gain']:.6f} | {m['positive']['count']} | {formatted} |")
    lines += ["", "只有四个全局周，不能把逐小时机会当作独立天气过程。总体、地区、地区周、逐日、正负例及缺失敏感性详表见 RESULT.json。",
        "共同信息银行与 values 银行分别绑定；两者差异同时包含后端差异。C1 的同后端对照应读 F_BASE_ONLY、B11_BATCH 与 B11_COVERAGE。", ""]
    (out / "REPORT_CN.md").write_text("\n".join(lines))
    print(json.dumps({k: v for k, v in result.items() if k != "metrics"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.batch.absolute(), args.out.absolute())
