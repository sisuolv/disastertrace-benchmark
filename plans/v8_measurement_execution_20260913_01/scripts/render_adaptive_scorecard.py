"""Render the independently qualified adaptive tables without pooling protocols."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, default=HERE / "reports/adaptive_large_analysis_01")
    parser.add_argument("--visible", type=Path, default=HERE / "reports/visible_forecast_values_01")
    parser.add_argument("--audit", type=Path, default=HERE / "gpu/adaptive_large_02/audit_01")
    parser.add_argument("--attribution", type=Path, default=HERE / "reports/forecast_attribution_01")
    parser.add_argument("--output", type=Path, default=HERE / "ADAPTIVE_SCORECARD_CN.md")
    args = parser.parse_args()
    analysis, visible = args.analysis.resolve(), args.visible.resolve()
    validation = read(analysis / "VALIDATION.json")
    values = read(visible / "VALIDATION.json")
    arms = read(analysis / "ARMS.json")
    if not validation["passed"] or not values["passed"]:
        raise ValueError("Qualified source analyses required")
    if validation["engineering_rehearsal"]:
        raise ValueError("Rehearsal is not a model scorecard")
    if hashlib.sha256((args.audit / "VALIDATION.json").read_bytes()).hexdigest() != validation["original_audit_sha256"]:
        raise ValueError("Audit origin differs from the analysis binding")
    for name, expected in values["source_hashes"].items():
        if hashlib.sha256((analysis / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Changed independent analysis")
    opportunities = read(analysis / "OPPORTUNITIES.json")
    unique = len({row["opportunity_id"] for row in opportunities})
    labels = {
        "A00_follow": "直接跟随共同基线",
        "A01_base_program": "无补充资料 + 程序预测",
        "A02_one_program": "单条取证 + 程序预测",
        "A03_batch_program": "批量取证 + 程序预测",
        "A04_risk_program": "风险取证 + 程序预测",
        "A05_coverage_program": "覆盖取证 + 程序预测",
        "A06_llm_program": "LLM 取证 + 程序预测",
        "A07_base_llm": "无补充资料 + LLM 预测",
        "A08_one_llm": "单条取证 + LLM 预测",
        "A09_batch_llm": "批量取证 + LLM 预测",
        "A10_risk_llm": "风险取证 + LLM 预测",
        "A11_coverage_llm": "覆盖取证 + LLM 预测",
        "A12_llm_llm": "LLM 取证 + LLM 预测",
    }
    lines = [
        "# 235B 自适应开发实验：完整分层结果",
        "",
        (
            f"注册 {validation['registered_sessions']} 个会话，"
            f"独立核验通过 {validation['qualified_sessions']} 个；"
            f"完整注册分母为 {validation['registered_opportunity_rows']:,} 个方法机会。"
        ),
        f"已核验部分实际使用 {unique} 个不同 cutoff 机会，均来自同一个 Bay 开发日。",
        (
            f"整批发出 {validation['issued_model_calls_all_sessions']:,} 次模型调用，"
            "其中 selector 调用与 predictor 回答分别统计。没有把重复方法或提前量当作独立天气过程。"
        ),
        "",
        (
            "E 可判定数在 cutoff 计算；E 正确和无依据确定性使用模型 dispatch 时实际可见资料。"
            "两者对应不同的时间和分母。无依据确定性指合法支持仍为未知/冲突时，模型给出确定结论。"
        ),
        "Brier 越低越好；净增益为共同基线 Brier 减去方法 Brier，正值才表示该日损失下降。",
        "",
        "## 概率提议的数值来源",
        "",
        (
            f"共有 {values['model_predictor_calls']:,} 个模型预测回答；"
            f"{values['model_proposals_equal_visible_state']:,} 个提议精确等于输入里的当前生效概率；"
            f"{values['model_proposals_differ_from_dispatch_baseline']:,} 个不同于 dispatch 时最新共同基线；"
            f"{values['model_proposals_differ_from_both_visible_probabilities']:,} 个同时不同于这两个可见概率。"
        ),
        "",
        (
            "数值相等不证明模型内部如何推理，但说明相应 F 数值可以在相同捕获输入上由"
            "直接读取 `state.forecast.value` 的简单规则复现。这不复现 E 判断、selector 或新的连续会话。"
            "持续保留旧概率仍可能相对更新中的共同基线产生收益或损害，不能把这种差异直接称作新预测信息。"
        ),
        "本批使用 `typed_auto_propose.v1`：有效数值由系统按合同提出 OVERRIDE，模型没有另行输出 FOLLOW/OVERRIDE 动作。因此不能把自动采纳或回退描述为模型主动选择了该动作。",
        "",
    ]
    for group in sorted({row["group"] for row in arms}):
        subset = [row for row in arms if row["group"] == group]
        qualified = [row for row in subset if row["status"] == "qualified"]
        lines.extend([f"## {group}", ""])
        if qualified:
            reference = qualified[0]
            lines.append(
                f"每方法 {reference['registered_opportunities']} 个注册机会；"
                f"{reference['positive_opportunities']} 个正例机会，"
                f"对应 {reference['unique_positive_targets']} 个不同正目标。"
            )
            lines.append("")
        lines.extend(
            [
                "| 方法 | 查询 | 模型调用 | E 可判定 | 模型 E 正确/回答 | 无依据确定 | Brier | 净增益 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in subset:
            label = row["arm"] + " " + labels[row["arm"]]
            if row["status"] != "qualified":
                lines.append(f"| {label} | 未核验，不填补分数 | - | - | - | - | - | - |")
                continue
            total = row["E_model_calls"]
            correct = row["E_call_counts"].get("correct_parsed_answers", 0)
            e = f"{correct}/{total}" if total else "不适用"
            fscore = "缺失" if row["formal_score"] is None else f"{row['formal_score']:.8f}"
            gain = row["F_metrics"]["net_realized_gain"]
            gain_text = "缺失" if gain is None else f"{gain:+.8f}"
            lines.append(
                f"| {label} | {row['source_queries']} | {row['actual_model_calls']} | "
                f"{row['E_determined_at_cutoff']}/{row['registered_opportunities']} | "
                f"{e} | {row['E_call_counts'].get('unsupported_determination', 0)} | {fscore} | {gain_text} |"
            )
        lines.append("")
    lines.extend(
        [
            "## 解释边界与复核入口",
            "",
            (
                "这些是已暴露单日上的描述性结果，没有独立过程置信区间。1km 零正例条件不能"
                "证明罕见灾害识别收益。专业 TAF 是共同输入，数值概率来自明确标为研究映射的历史频率银行，"
                "不等于官方已校准事件概率。"
            ),
            "",
            (
                "本批 source 预算为 48，模型采用实测计算/交付时间，程序采用声明的 1ms 情景。"
                "它与 W07 的 72 查询/公共调用时隙分开，不作跨批次 LLM 效果归因或部署成本效益声称。"
            ),
            "",
            f"- 本表绑定的完整审计：`{args.audit.resolve().relative_to(HERE)}/VALIDATION.json`。",
            f"- 全方法机会、E 混淆表、无提交比例、费用与延迟：`{analysis.relative_to(HERE)}/`。",
            f"- dispatch 与 cutoff 基线变化：`{args.attribution.resolve().relative_to(HERE)}/`。",
            f"- dispatch 可见状态数值匹配：`{visible.relative_to(HERE)}/`。",
            f"- 同批策略比较：`{analysis.relative_to(HERE)}/CONTRASTS.json`。",
            "",
            (
                "下一步优先补同预算状态沿用程序对照、独立训练/校准的强数值基线，以及预登记的"
                "极端诊断集和独立过程确认。X09 本轮未在预定时间启动，没有实际模型分数。"
            ),
        ]
    )
    output = args.output
    with output.open("x") as handle:
        handle.write("\n".join(lines) + "\n")
    print(json.dumps({"output": str(output), "registered_methods": len(arms)}))


if __name__ == "__main__":
    main()
