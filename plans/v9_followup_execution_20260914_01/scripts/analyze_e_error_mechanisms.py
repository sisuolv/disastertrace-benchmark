"""Attribute existing slotwise errors without repairing original model scores."""

from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def main():
    folder = ROOT / "api_evidence_02"
    out = ROOT / "reports/e_error_mechanisms_01"
    out.mkdir(exist_ok=False)
    assert read(ROOT / "reports/api_evidence_audit_02/VALIDATION.json")["passed"]
    plan = read(folder / "PLAN.json")
    references = read(folder / "evaluator/REFERENCES.json")
    spec = importlib.util.spec_from_file_location("frozen_e_reducer", folder / "source/evidence_diagnostic.py")
    reducer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reducer)
    groups = defaultdict(Counter)
    rows = []
    for task in plan["tasks"]:
        if task["reasoning"] != "slotwise":
            continue
        for model in plan["models"]:
            key = model + "__" + task["representation"]
            counts = groups[key]
            counts["n"] += 1
            reference = references[task["call_id"]]
            capture = read(folder / "captures" / model / task["call_id"] / "RESPONSE.json")
            choice = capture["body"]["choices"][0]
            try:
                answer = reducer.parse(choice["message"]["content"], task["query_ids"], "slotwise")
                assert choice["finish_reason"] == "stop"
            except (ValueError, TypeError, AssertionError):
                counts["invalid"] += 1
                rows.append({"model": model, "call_id": task["call_id"], "mechanism": "invalid"})
                continue
            slots_correct = answer["slots"] == reference["slots"]
            final_correct = answer["fact_truth"] == reference["fact_truth"]
            self_consistent = answer["fact_truth"] == reducer.aggregate(answer["slots"].values())
            counts.update(valid=1, all_slots_correct=int(slots_correct), final_correct=int(final_correct),
                          aggregate_consistent=int(self_consistent))
            if slots_correct and final_correct:
                label = "all_correct"
            elif slots_correct:
                label = "correct_slots_wrong_aggregate"
                assert not self_consistent
            elif self_consistent:
                label = "wrong_slots_consistent_aggregate"
            else:
                label = "wrong_slots_inconsistent_aggregate"
            counts[label] += 1
            rows.append({"model": model, "call_id": task["call_id"], "region": task["region"],
                         "opportunity_id": task["opportunity_id"], "condition": task["condition"],
                         "representation": task["representation"], "mechanism": label})
    result = {"passed": True, "underlying_opportunities": plan["underlying_opportunities"],
              "groups": dict(groups), "rows": rows, "model_calls": 0,
              "interpretation": "Posthoc attribution only; no score replacement or paired independent-sample claim"}
    (out / "VALIDATION.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# E 错误机制：原始回答的补充分析", "",
             "本分析复用修复后 E02 的全部逐槽回答，不调用模型，不修改原始评分。42 个底层问题生成多种相依视图；结果仅适用于本批固定设置。", "",
             "| 模型 / 输入 | 全部槽正确 | 最终E正确 | 槽全对但汇总错 | 格式无效 |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for key, row in groups.items():
        lines.append(f"| {key} | {row['all_slots_correct']}/{row['n']} | {row['final_correct']}/{row['n']} | {row['correct_slots_wrong_aggregate']} | {row['invalid']} |")
    lines += ["", "这里的汇总错误指模型对可见记录的逐槽结论已经全部正确，但最终事实结论与这些结论不一致。它为 C2 的过程分解提供一个可测的开发现象，尚不说明这些事实能改善未来概率预测。",
              "", "后续比较可另行固定一个由程序汇总模型逐槽答案的输出管线，同时保留原生模型输出、确定性原生资料 reducer、同信息和同总预算对照。不能把离线替换结论后的准确率作为原模型成绩。",
              "", "两模型本批均为 thinking disabled、temperature 0、512 输出 token。结果不代表其他推理配置或模型一般能力的排序。"]
    (out / "REPORT_CN.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"groups": dict(groups), "model_calls": 0}))


if __name__ == "__main__":
    main()
