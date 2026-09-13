"""Separate repeated policy executions from fixed-candidate wrapper replay."""

from __future__ import annotations

import argparse
import inspect
import shutil
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, paired_gain, write
from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.monitoring_v1.state import MonitoringEngine
from disastertrace.monitoring_v1.targets import canonical_hash

BASE = Path(__file__).resolve().parent
BOUND = "base_bound_override"
PERSISTENT = "persistent_override"


def check_scores(rows, expected):
    actual = brier_report(rows)
    for key in ("opportunities", "settled", "base_brier", "system_brier"):
        if actual[key] != expected[key]:
            raise ValueError("Previously verified wrapper score changed: " + key)


def process_counts(trace):
    result = Counter({"forecast_attempts": len(trace["attempts"])})
    result.update("attempt:" + row["status"] for row in trace["attempts"])
    result.update("decision:" + row["decision"] for row in trace["calls"])
    result.update("snapshot_mode:" + row["mode"] for row in trace["snapshots"])
    result.update(
        "override_end:" + row["reason"]
        for row in trace["state_audit"]
        if row["kind"] == "override_end"
    )
    result["snapshots_different_from_base"] += sum(
        row["probability"] != row["base_probability"] for row in trace["snapshots"]
    )
    return result


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_wrappers.py")
    rows = load(args.analysis / "ROWS.json")
    calendar = load(args.analysis / "REPORT.json")
    bindings = {
        str((args.analysis / name).resolve()): digest(args.analysis / name)
        for name in ("ROWS.json", "REPORT.json")
    }
    repeated = {}
    for label, candidate in rows.items():
        if not label.endswith("/" + PERSISTENT):
            continue
        other = label.rsplit("/", 1)[0] + "/" + BOUND
        if other not in rows:
            raise ValueError("Missing separately executed protocol: " + other)
        repeated[label.rsplit("/", 1)[0]] = paired_gain(candidate, rows[other])

    fixed, counts, seen = defaultdict(list), defaultdict(Counter), set()
    for path in args.model_verifications:
        verified = load(path)
        batch = BASE / Path(verified["batch"]).name
        plan = load(batch / "PLAN.json")
        if digest(batch / "PLAN.json") != verified["plan_sha256"]:
            raise ValueError("Verified plan changed")
        if calendar["outcomes_sha256"] not in plan["evaluation_bindings"].values():
            raise ValueError("Outcome contract differs from calendar")
        bindings[str(path.resolve())] = digest(path)
        for identity, report in verified["reports"].items():
            worker, run = identity.split(":", 1)
            config = report["config"]
            protocol = config["protocol"]
            label = "/".join(("model", plan["worker_models"][worker],
                              config["selector_kind"], protocol))
            trace_path = batch / ("worker-" + worker) / run / "TRACE.json"
            trace = load(trace_path)
            if trace["config"] != config or trace.get("outcome_table_accessed_by_policy"):
                raise ValueError("Trace contract or isolation mismatch")
            if trace["plan_sha256"] != verified["plan_sha256"]:
                raise ValueError("Trace plan binding changed")
            bindings[str(trace_path.resolve())] = digest(trace_path)
            anchor = {r["opportunity_id"]: r for r in rows[label]}

            def convert(snapshots, anchor=anchor):
                converted = []
                for row in snapshots:
                    expected = anchor[row["opportunity_id"]]
                    if row["target_id"] != expected["target_id"] or row["base_probability"] != expected["base"]:
                        raise ValueError("Wrapper target or common baseline changed")
                    converted.append(dict(expected, prediction=row["probability"]))
                return converted

            original = convert(trace["snapshots"])
            for row in original:
                key = (label, row["opportunity_id"])
                if key in seen or row["prediction"] != anchor[row["opportunity_id"]]["prediction"]:
                    raise ValueError("Duplicate or different actual trajectory")
                seen.add(key)
            check_scores(original, report["scores"])
            alternate = deepcopy(trace["event_replay"])
            alternate["payload"]["protocol"] = PERSISTENT if protocol == BOUND else BOUND
            alternate["sha256"] = canonical_hash(alternate["payload"])
            engine = MonitoringEngine.restore(alternate)
            other = convert(list(engine.snapshots.values()))
            check_scores(other, report["alternate_fixed_candidate_scores"])
            if alternate["payload"]["protocol"] != report["alternate_fixed_candidate_protocol"]:
                raise ValueError("Alternate protocol identity changed")
            other_by_id = {r["opportunity_id"]: r for r in other}
            for row in original:
                fixed[label].append({
                    "original": row,
                    "alternate": other_by_id[row["opportunity_id"]],
                })
            counts[label].update(process_counts(trace))
            print(label + ": " + run, flush=True)

    direct = {}
    for label, pairs in fixed.items():
        if len(pairs) != len(rows[label]):
            raise ValueError("Fixed-candidate replay is missing calendar opportunities")
        original = [p["original"] for p in pairs]
        alternate = [p["alternate"] for p in pairs]
        persistent, bound = (alternate, original) if label.endswith(BOUND) else (original, alternate)
        direct[label] = paired_gain(persistent, bound)
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "separately_executed_persistent_vs_bound": repeated,
        "fixed_candidates_persistent_vs_bound": direct,
        "actual_process_counts": {k: dict(v) for k, v in counts.items()},
        "input_bindings": bindings,
        "implementation_sha256": digest(args.output / "analyze_wrappers.py"),
        "state_implementation_sha256": digest(Path(inspect.getfile(MonitoringEngine))),
        "paired_bound_implementation_sha256": digest(BASE / "analyze_calendar.py"),
        "new_model_calls": 0,
        "interpretation": "Positive gain means lower persistent-wrapper Brier. Separate runs include adapted contexts, stochastic/numerical generation and measured-time differences. Fixed-candidate replay holds recorded actions, probabilities and timings fixed; it is a direct wrapper sensitivity, not a newly inferred adaptive policy and not an additive causal decomposition.",
    }
    write(args.output / "REPORT.json", result)
    lines = ["# 两种修订协议的独立执行与固定输出复算", "",
             "正值表示 persistent_override 的 Brier 更低。全部使用相同登记机会和结果掩膜。", "",
             "| 方法 | 分别实际运行的 persistent − bound 收益 |",
             "| --- | ---: |"]
    for label, pair in repeated.items():
        lines.append(f"| {label} | {pair['mean_gain']:+.9f} |")
    lines += ["", "## 固定候选与完成时间，仅更换 wrapper", "",
              "| 候选轨迹的原始协议 | persistent 相对 bound 收益 | 改善 / 恶化 / 不变机会 |",
              "| --- | ---: | --- |"]
    for label, pair in direct.items():
        lines.append(f"| {label} | {pair['mean_gain']:+.9f} | "
                     f"{pair['improved_opportunities']} / {pair['worsened_opportunities']} / {pair['unchanged_opportunities']} |")
    lines += ["", "分别运行会改变提示中的当前状态，也保留推理和实际耗时差异；不能把全部差异归因于回退规则。",
              "固定输出复算使用同一组行动、概率和时间，仅改变协议，不是模型在另一协议下重新作出的决策。",
              "两项结果不能相加或换算为因果贡献百分比。已接受、失效、主动撤销、迟到和回退次数见 REPORT.json。",
              "共同基线仍为 R 轨的 TAF 研究映射；相对它的收益不等于超越官方概率预报。", ""]
    (args.output / "REPORT_CN.md").write_text("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--model-verifications", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
