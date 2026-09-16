"""Paired residual-session diagnostics, retaining the full registered denominator."""
import itertools
import json
import math
from pathlib import Path
from collections import Counter
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    execution = read(ROOT / "C2_BRANCH_EXECUTION_RESULT.json")
    roster = read(ROOT / "C2_BRANCH_ROSTER.json")
    parents, actions, field_rows, pair_rows = [], [], [], []
    for row in roster["parents"]:
        meta = row["parent"]; case = ROOT / "branches" / meta["case"]
        result = read(case / "RESULT.json")
        selected = set(row["U_parent"])
        outcome_path = (REPO / meta["directory"]).parent / "OUTCOMES.json"
        outcomes = {r["opportunity_id"]: r for r in read(outcome_path)}
        settled = {oid for oid in selected if outcomes[oid]["status"] == "mature" and outcomes[oid]["value"] is not None}
        reports, traces, metrics = {}, {}, {}
        for entry in result["results"]:
            name = entry["rule"]
            effective = entry.get("alias_of", name)
            path = case / effective / "FORMAL_REPORT.json"
            if not path.exists():
                continue
            report = read(path)
            snaps = {r["opportunity_id"]: r for r in report["snapshots"]}
            if not selected <= set(snaps):
                raise ValueError("Residual-session roster changed")
            reports[name] = {oid: snaps[oid]["forecast"]["value"] for oid in selected}
            traces[name] = {r["opportunity_id"]: r for r in read(case / effective / "FIELD_FEATURE_TRACE.json") if r["opportunity_id"] in selected}
            calls = {r["opportunity_id"]: r for r in report["calls"]}
            states = {oid: status for frame in report["frames"] for oid,status in frame["e_statuses"].items() if oid in selected}
            losses = {oid: (reports[name][oid]-outcomes[oid]["value"])**2 for oid in settled}
            prefix = read(ROOT / "parents" / meta["case"] / "PARENT_CHECKPOINT.json")["payload"]
            resource_delta = {k: report["resource_spent"][k]-prefix["ledger"]["spent"][k] for k in report["resource_spent"]}
            metrics[name] = {"registered": len(selected), "settled": len(settled),
                "positive": sum(outcomes[oid]["value"] for oid in settled),
                "brier": math.fsum(losses.values())/len(settled) if settled else None,
                "e_states": dict(Counter(states.values())), "resource_delta": resource_delta,
                "selected_target_probability": reports[name][meta["opportunity_id"]],
                "alias_of": entry.get("alias_of")}
            action = read(case / effective / "ACTION_TRACE.json")
            actions.append({"case": meta["case"], "rule": name, "alias_of": entry.get("alias_of"), **action})
            for oid in sorted(selected):
                call = calls.get(oid)
                feature = traces[name].get(oid)
                field_rows.append({"case": meta["case"], "rule": name, "opportunity_id": oid,
                    "selected_probe": oid == meta["opportunity_id"], "e_status": states.get(oid),
                    "trace": feature, "admission_status": None if call is None else call["admission_status"],
                    "adoption_decision": None if call is None else call["adoption_decision"],
                    "effective_probability": reports[name][oid], "outcome": outcomes[oid]["value"],
                    "settled": oid in settled, "brier": losses.get(oid)})
        comparisons = []
        for left, right in itertools.combinations(reports, 2):
            delta = [((reports[left][oid]-outcomes[oid]["value"])**2 - (reports[right][oid]-outcomes[oid]["value"])**2) for oid in settled]
            shared_calls = set(traces[left]) & set(traces[right])
            collision = [oid for oid in shared_calls
                if traces[left][oid]["baseline_sha256"] == traces[right][oid]["baseline_sha256"]
                and traces[left][oid]["started_at"] == traces[right][oid]["started_at"]
                and traces[left][oid]["claims_sha256"] != traces[right][oid]["claims_sha256"]
                and traces[left][oid]["features_sha256"] == traces[right][oid]["features_sha256"]]
            entry = {"case": meta["case"], "left": left, "right": right, "positive_delta_favors": right,
                "registered": len(selected), "settled": len(settled),
                "claims_changed_calls": sum(traces[left][oid]["claims_sha256"] != traces[right][oid]["claims_sha256"] for oid in shared_calls),
                "features_changed_calls": sum(traces[left][oid]["features_sha256"] != traces[right][oid]["features_sha256"] for oid in shared_calls),
                "candidate_changed_calls": sum(traces[left][oid]["proposed_probability"] != traces[right][oid]["proposed_probability"] for oid in shared_calls),
                "effective_probability_changed": sum(reports[left][oid] != reports[right][oid] for oid in selected),
                "mean_brier_difference": math.fsum(delta)/len(settled) if settled else None,
                "missing_result_sensitivity_bounds": [(math.fsum(delta) + sign*(len(selected)-len(settled)))/len(selected) for sign in (-1,1)],
                "representation_collisions": collision,
                "source_result_sha256": digest(case / "RESULT.json")}
            comparisons.append(entry); pair_rows.append(entry)
        parents.append({"case": meta["case"], "metrics": metrics, "comparisons": comparisons,
            "shared_wakeup_equal": result["shared_wakeup_equal"], "outcomes_sha256": digest(outcome_path)})
    passed = execution["passed"] and all(p["shared_wakeup_equal"] for p in parents)
    summary = {"passed": passed, "actual_treatment_attempts": execution["actual_treatment_attempts"],
        "parents": parents, "global_dates": 1, "new_model_calls": 0,
        "engineering_only": True, "independent_process_confirmation": False,
        "formal_scored_parents": len(parents), "unique_physical_date": "2025-03-03",
        "comparisons": len(pair_rows), "comparisons_with_feature_change": sum(r["features_changed_calls"]>0 for r in pair_rows),
        "comparisons_with_effective_probability_change": sum(r["effective_probability_changed"]>0 for r in pair_rows),
        "representation_collision_count": sum(len(r["representation_collisions"]) for r in pair_rows),
        "C2_claim": "finite acquisition changes are traceable through the actual consumer; effect and failure counts are descriptive development diagnostics"}
    publish(ROOT / "PLANNED_EXECUTED_ACTIONS.json", actions)
    publish(ROOT / "C2_FIELD_TO_LOSS.json", field_rows)
    publish(ROOT / "C2_ENGINEERING_RESULT.json", summary)
    lines = ["# C2 真实有限分支结果", "",
        f"正式执行 {execution['actual_treatment_attempts']} 条处理分支，六个父状态；同一个全球日期（2025-03-03），不是六个独立天气过程。",
        "四条策略继承相同的父费用、缓存、公共唤醒与预测日程，主分母包含父状态之后的全部剩余会话机会。",
        "", "| 父会话 | 规则 | 剩余机会/可结算 | 新增查询 | Brier |", "|---|---|---:|---:|---:|"]
    for p in parents:
        for rule, m in p["metrics"].items():
            brier = "不可结算" if m["brier"] is None else f"{m['brier']:.8f}"
            lines.append(f"| {p['case']} | {rule} | {m['registered']}/{m['settled']} | {m['resource_delta']['requests']} | {brier} |")
    lines += ["", f"{summary['comparisons_with_feature_change']}/{len(pair_rows)} 个配对存在特征变化，{summary['comparisons_with_effective_probability_change']}/{len(pair_rows)} 个配对存在实际生效概率变化。",
        f"同机会、同基线条件下统计到的字段→相同特征碰撞数量为 {summary['representation_collision_count']}；这个样本中的零碰撞不能证明表示无损。",
        "", "这验证了获取动作到字段、特征、候选、采用和损失的工程链。没有新增 LLM 天气评测，不能据此声称模型优于强程序或 C2 已跨独立天气过程得到确认。",
        "所有两两比较属于已暴露开发集描述，缺失敏感性界不等于抽样置信区间。年度银行和下一阶段模型实验另设门槛。"]
    with (ROOT / "C2_ENGINEERING_REPORT_CN.md").open("x") as f:
        f.write("\n".join(lines)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="parents"}),flush=True)


if __name__ == "__main__":
    main()
