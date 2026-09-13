"""Post-hoc probability-ranking and fixed-threshold diagnostics for rare reports."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, paired_gain, write


def ranking(rows, thresholds=(0.01, 0.05, 0.1, 0.2, 0.5)):
    settled = [r for r in rows if r["outcome"] is not None]
    if any(r["outcome"] not in (0, 1) or not 0 <= r["prediction"] <= 1 for r in settled):
        raise ValueError("Invalid probability or outcome")
    positives = sum(r["outcome"] for r in settled)
    negatives = len(settled) - positives
    groups = defaultdict(lambda: [0, 0])
    for row in settled:
        groups[row["prediction"]][row["outcome"]] += 1
    tp = fp = 0
    ap = concordance = 0.0
    for probability in sorted(groups, reverse=True):
        n, p = groups[probability]
        tp += p
        fp += n
        if positives:
            ap += (p / positives) * (tp / (tp + fp))
        concordance += p * (negatives - fp + 0.5 * n)
    points = []
    for threshold in thresholds:
        selected = [r for r in settled if r["prediction"] >= threshold]
        tp = sum(r["outcome"] for r in selected)
        fp = len(selected) - tp
        points.append({"threshold": threshold, "true_positive": tp, "false_positive": fp,
                       "false_negative": positives - tp, "true_negative": negatives - fp,
                       "precision": tp / len(selected) if selected else None,
                       "recall": tp / positives if positives else None,
                       "false_positive_rate": fp / negatives if negatives else None})
    return {"opportunities": len(rows), "settled": len(settled), "missing": len(rows) - len(settled),
            "positive_opportunities": positives, "positive_rate": positives / len(settled) if settled else None,
            "average_precision": ap if positives else None,
            "roc_auc": concordance / (positives * negatives) if positives and negatives else None,
            "fixed_thresholds": points,
            "tie_rule": "Each distinct score is one threshold group; ROC ties receive half credit",
            "scope": "Descriptive settled-opportunity ranking; repeated lead outcomes and dependent weather are not independent samples"}


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_warning_ranking.py")
    rows = load(args.analysis / "ROWS.json")
    original = next(iter(rows.values()))
    arms = dict(rows)
    arms["shared_research_TAF_base"] = [dict(r, prediction=r["base"]) for r in original]
    arms["zero_event"] = [dict(r, prediction=0.0) for r in original]
    reports = {}
    for name, values in arms.items():
        paired_gain(values, original)
        reports[name] = ranking(values)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "arms": reports,
              "design": "Post-hoc descriptive ranking and fixed thresholds, declared after initial Brier results; no threshold selected for a winning method",
              "input_bindings": {str((args.analysis / "ROWS.json").resolve()): digest(args.analysis / "ROWS.json")},
              "implementation_sha256": digest(args.output / "analyze_warning_ranking.py"),
              "new_model_calls": 0, "new_network_requests": 0,
              "interpretation": "Ranking can distinguish event discrimination from probability calibration. It does not replace proper loss, missing-result bounds or independent-process confirmation. No operational cost/benefit claim."}
    write(args.output / "REPORT.json", result)
    lines = ["# 稀有事件的概率排序与固定阈值诊断", "",
             "这是在首轮 Brier 结果后补充的描述性检查，全部方法用同一可结算机会；不选择获胜阈值。",
             "AP 的常数基准等于事件率。较好的排序和较差的 Brier 可以同时发生；排序不替代校准或损失。", "",
             "| 方法 | AP | ROC AUC | 正例机会 |", "| --- | ---: | ---: | ---: |"]
    for name, values in reports.items():
        if name.startswith("model/") or name in {"shared_research_TAF_base", "zero_event"}:
            ap = values["average_precision"]
            auc = values["roc_auc"]
            lines.append(f"| {name} | {ap if ap is None else round(ap, 8)} | {auc if auc is None else round(auc, 8)} | {values['positive_opportunities']} |")
    lines += ["", "0.01/0.05/0.10/0.20/0.50 五个固定概率阈值的 TP/FP/FN/TN、precision、recall、FPR 均在 REPORT.json。",
              "没有正例时 AP/recall 不可用；没有两类时 ROC 不可用。无报警时 precision 不伪造为 1。",
              "同分数统一成组，避免由输入顺序制造 PR 优势。重复提前量仍共享同一结果，未给独立样本置信区间。", ""]
    (args.output / "REPORT_CN.md").write_text("\n".join(lines))
    print(json.dumps({"arms": len(reports), "opportunities_per_arm": len(original)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
