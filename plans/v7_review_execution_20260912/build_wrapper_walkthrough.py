"""Expose every changed cutoff in a verified fixed-candidate wrapper comparison."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest
from disastertrace.monitoring_v1.state import MonitoringEngine
from disastertrace.monitoring_v1.targets import canonical_hash

BASE = Path(__file__).resolve().parent


def main():
    verification = BASE / "gpu_front_primary_base_01_validation_01/VERIFIED.json"
    checked = json.loads(verification.read_text())
    outcomes_path = BASE / "extension_front_range_03/private/OUTCOMES.json"
    outcomes = {r["target_id"]: r for r in json.loads(outcomes_path.read_text())}
    bindings = {str(p.relative_to(BASE)): digest(p) for p in (verification, outcomes_path)}
    changed = []
    for key, report in checked["reports"].items():
        if report["scores"]["system_brier"] == report["alternate_fixed_candidate_scores"]["system_brier"]:
            continue
        worker, run = key.split(":", 1)
        path = BASE / "gpu_front_primary_base_01" / ("worker-" + worker) / run / "TRACE.json"
        trace = json.loads(path.read_text())
        bindings[str(path.relative_to(BASE))] = digest(path)
        alternate = deepcopy(trace["event_replay"])
        alternate["payload"]["protocol"] = "persistent_override"
        alternate["sha256"] = canonical_hash(alternate["payload"])
        engine = MonitoringEngine.restore(alternate)
        for original in trace["snapshots"]:
            other = engine.snapshots[original["opportunity_id"]]
            if original["probability"] == other["probability"]:
                continue
            call_id = other["override_call_id"] or original["override_call_id"]
            candidates = [r for r in trace["attempts"] if r["call_id"] == call_id]
            y = outcomes[original["target_id"]]["outcome"]
            changed.append({"run": key, "opportunity_id": original["opportunity_id"],
                "original": original, "alternate": other, "outcome": y,
                "bound_loss": None if y is None else (original["probability"]-y)**2,
                "persistent_loss": None if y is None else (other["probability"]-y)**2,
                "candidate_attempts": candidates,
                "original_end_events": [r for r in trace["state_audit"] if r.get("call_id") == call_id]})
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "changed_cutoffs": changed,
        "selection": "Every changed cutoff in the Front 2024 base-run blocks with nonzero fixed-candidate Brier difference; not a representative event sample",
        "input_bindings": bindings, "new_model_calls": 0,
        "scope": "Same captured actions/probabilities/timings under two wrapper rules; no new adaptive policy or model reasoning claim"}
    (BASE / "WRAPPER_CASE_WALKTHROUGH.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# 一条真实固定候选轨迹中的 wrapper 作用", "",
        "从已核验的 Front Range 2024 base 协议批次重放，只替换 wrapper，保留候选、概率与完成时刻。",
        "这不是新模型推理；结果标签只在此分析器中使用。", "",
        "| 机会 | bound 封存概率 | persistent 封存概率 | 结果 | bound 损失 | persistent 损失 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in changed:
        lines.append(f"| {row['opportunity_id']} | {row['original']['probability']} | {row['alternate']['probability']} | {row['outcome']} | {row['bound_loss']} | {row['persistent_loss']} |")
    lines += ["", "完整候选与原 wrapper 的结束原因见 WRAPPER_CASE_WALKTHROUGH.json。",
              "如果规则取消了一个后来不利的修订，这项直接规则效果不属于模型额外预测能力。",
              "另行运行 persistent 时模型可能提交不同候选；不能把固定轨迹效果与独立运行差值相加。",
              "该样例按有差异的区块挑选，用于解释协议，不用于估计总体收益、错误率或独立天气过程数量。", ""]
    (BASE / "WRAPPER_CASE_WALKTHROUGH_CN.md").write_text("\n".join(lines))
    print(json.dumps({"changed_cutoffs": len(changed)}))


if __name__ == "__main__":
    main()
