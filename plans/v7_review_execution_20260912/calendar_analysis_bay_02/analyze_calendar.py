"""Paired all-opportunity reports; calendar resampling is an assumption sensitivity."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
HOUR = 3_600_000_000


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def paired_gain(candidate, reference):
    left = {r["opportunity_id"]: r for r in candidate}
    right = {r["opportunity_id"]: r for r in reference}
    if len(left) != len(candidate) or len(right) != len(reference) or set(left) != set(right):
        raise ValueError("Paired opportunity denominators differ or contain duplicates")
    gains, bounds = [], [0.0, 0.0]
    missing_by_target = defaultdict(lambda: [0.0, 0.0])
    for ident, row in left.items():
        other = right[ident]
        if row["target_id"] != other["target_id"] or row["outcome"] != other["outcome"]:
            raise ValueError("Paired target/outcome masks differ")
        p, q, y = row["prediction"], other["prediction"], row["outcome"]
        values = [(q - outcome) ** 2 - (p - outcome) ** 2
                  for outcome in ((0, 1) if y is None else (y,))]
        if y is None:
            for endpoint, value in enumerate(values):
                missing_by_target[row["target_id"]][endpoint] += value
        else:
            bounds[0] += values[0]
            bounds[1] += values[0]
            gains.append(values[0])
    for endpoints in missing_by_target.values():
        bounds[0] += min(endpoints)
        bounds[1] += max(endpoints)
    n = len(left)
    return {"opportunities": n, "settled": len(gains),
            "mean_gain": sum(gains) / len(gains) if gains else None,
            "full_population_gain_bounds": [v / n for v in bounds] if n else None,
            "bounds_scope": "One common unknown binary outcome per target, shared across its lead-time opportunities",
            "improved_opportunities": sum(g > 1e-12 for g in gains),
            "worsened_opportunities": sum(g < -1e-12 for g in gains),
            "unchanged_opportunities": sum(abs(g) <= 1e-12 for g in gains)}


def quantile(values, fraction):
    values = sorted(values)
    point = (len(values) - 1) * fraction
    index = int(point)
    tail = min(index + 1, len(values) - 1)
    return values[index] + (values[tail] - values[index]) * (point - index)


def calendar_sensitivity(rows, block_hours, draws=2000):
    groups = defaultdict(list)
    start = min(r["physical_start"] for r in rows)
    for row in rows:
        if row["outcome"] is not None:
            groups[(row["physical_start"] - start) // (block_hours * HOUR)].append(row)
    blocks = [{"block": key, "opportunities": len(values),
               "unique_targets": len({r["target_id"] for r in values}),
               "gain_sum": sum(r["gain"] for r in values)}
              for key, values in sorted(groups.items())]
    numerator = sum(r["gain_sum"] for r in blocks)
    denominator = sum(r["opportunities"] for r in blocks)
    rng = random.Random(20260912 + block_hours)
    boot = []
    if len(blocks) >= 2:
        for _ in range(draws):
            chosen = [rng.choice(blocks) for _ in blocks]
            boot.append(sum(b["gain_sum"] for b in chosen) / sum(b["opportunities"] for b in chosen))
    omitted = [(numerator - b["gain_sum"]) / (denominator - b["opportunities"])
               for b in blocks if denominator > b["opportunities"]]
    return {"block_hours": block_hours, "calendar_blocks": len(blocks),
            "unique_targets": len({r["target_id"] for r in rows if r["outcome"] is not None}),
            "mean_gain": numerator / denominator if denominator else None,
            "bootstrap_percentile_95": [quantile(boot, 0.025), quantile(boot, 0.975)] if boot else None,
            "leave_one_block_out_range": [min(omitted), max(omitted)] if omitted else None,
            "resamples": len(boot), "blocks": blocks, "independent_process_claim": False,
            "interpretation": "Descriptive sensitivity assuming exchangeable calendar blocks. Blocks are grouped by target support start, so repeated leads remain together. Nearby weather can span blocks; this is not a verified independent-storm confidence interval."}


def reliability(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["outcome"] is not None:
            groups[min(9, int(row["prediction"] * 10))].append(row)
    bins = [{"decile": key, "count": len(values),
             "mean_prediction": sum(r["prediction"] for r in values) / len(values),
             "positive_rate": sum(r["outcome"] for r in values) / len(values)}
            for key, values in sorted(groups.items())]
    n = sum(r["count"] for r in bins)
    return {"settled": n, "missing": len(rows) - n, "bins": bins,
            "binned_ece": sum(r["count"] * abs(r["mean_prediction"] - r["positive_rate"]) for r in bins) / n if n else None,
            "interpretation": "Descriptive reliability on settled opportunities, not a guarantee or independent calibration sample. Repeated leads share outcomes."}


def main(args):
    from disastertrace.monitoring_v1.scoring import brier_report

    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_calendar.py")
    outcomes_path = args.dataset / "private/OUTCOMES.json"
    outcomes = {r["target_id"]: r for r in load(outcomes_path)}
    targets = {r["target_id"]: r for r in load(args.dataset / "public/TARGETS.json")}
    arms, counters, bindings, settings = defaultdict(list), defaultdict(Counter), {}, {}

    def consume(label, trace_path, config, checked):
        trace = load(trace_path)
        if trace["config"] != config or trace.get("outcome_table_accessed_by_policy"):
            raise ValueError("Trace contract or outcome isolation changed")
        bindings[str(trace_path.resolve())] = digest(trace_path)
        rows = []
        for s in trace["snapshots"]:
            result = outcomes[s["target_id"]]
            t = targets[s["target_id"]]
            rows.append({"opportunity_id": s["opportunity_id"], "target_id": s["target_id"],
                "cutoff": s["cutoff"], "physical_start": t["physical_start"], "station": t["entity"],
                "lead_hours": (t["physical_start"] - s["cutoff"]) // HOUR,
                "base": s["base_probability"], "prediction": s["probability"],
                "outcome": result["outcome"], "quality": result["status"],
                "baseline_kind": s["baseline_kind"], "mode": s["mode"],
                "period": str(s["cutoff"] // (24 * HOUR)), "source": "native_metar",
                "maturity": "final_archive", "region": args.region})
        score = brier_report(rows)
        for key in ("opportunities", "settled", "base_brier", "system_brier", "net_realized_gain"):
            if score[key] != checked["scores"][key]:
                raise ValueError("Previously verified score changed: " + label + "/" + key)
        arms[label].extend(rows)
        count = counters[label]
        count.update({"resource_" + k: v for k, v in trace["resource_spent"].items()})
        count.update({"limit_tokens": config["token_cap"], "limit_compute_ms": config["compute_ms_cap"],
                      "limit_source_requests": config["request_budget"]})
        if trace["actual_model_calls"]:
            count["limit_model_calls"] += config.get("model_call_budget", config["forecast_call_cap"])
            count["sessions_model_call_budget_exhausted"] += trace["actual_model_calls"] == config.get("model_call_budget", config["forecast_call_cap"])
        count["sessions_source_request_budget_exhausted"] += trace["resource_spent"]["requests"] == config["request_budget"]
        count["resource_sessions"] += 1
        count.update({"E_" + k: v for k, v in trace["e_counts"].items()})
        count.update({"attempt_" + k: v for k, v in Counter(a["status"] for a in trace["attempts"]).items()})
        count.update({"decision_" + k: v for k, v in Counter(c["decision"] for c in trace["calls"]).items()})
        count["actual_model_calls"] += trace["actual_model_calls"]
        count["selector_calls"] += len(trace.get("selector_calls", []))
        count["forecast_updates"] += len(trace["calls"])
        count["E_correct_on_updated_targets"] += sum(c["reported_e"] == c["expected_e_from_disclosed_products"] for c in trace["calls"])
        count["invalid_forecast_responses"] += sum(c["response_error"] is not None for c in trace["calls"])
        settings[label] = {"protocol": config["protocol"], "selector": config["selector_kind"],
            "allocation": config["allocation_mode"], "authorization": config["authorization_mode"],
            "session_call_budget": config.get("model_call_budget"), "source_budget_per_session": config["request_budget"],
            "input_token_cap": config["input_token_cap"], "per_tick_forecast_cap": config["per_tick_forecast_cap"]}

    for verification_path in args.model_verifications:
        verification = load(verification_path)
        batch = BASE / Path(verification["batch"]).name
        plan = load(batch / "PLAN.json")
        if digest(batch / "PLAN.json") != verification["plan_sha256"]:
            raise ValueError("Verified model plan changed")
        if digest(outcomes_path) not in plan["evaluation_bindings"].values():
            raise ValueError("Model outcomes do not match this cohort")
        bindings[str(verification_path.resolve())] = digest(verification_path)
        for key, checked in verification["reports"].items():
            worker, run_id = key.split(":", 1)
            config = checked["config"]
            label = "/".join(("model", plan["worker_models"][worker], config["selector_kind"], config["protocol"]))
            consume(label, batch / ("worker-" + worker) / run_id / "TRACE.json", config, checked)
    joint_references = []
    for directory in args.controls:
        summary = load(directory / "SUMMARY.json")
        if summary["source_audit_sha256"] != digest(args.dataset / "REGIONAL_JOIN_AUDIT.json"):
            raise ValueError("Control dataset does not match")
        bindings[str((directory / "SUMMARY.json").resolve())] = digest(directory / "SUMMARY.json")
        for key, checked in summary["runs"].items():
            config = checked["config"]
            label = "/".join(("program", checked["label"], config["protocol"]))
            path = directory / (key + "-TRACE.json")
            if digest(path) != checked["trace_sha256"]:
                raise ValueError("Frozen program trace changed")
            consume(label, path, config, checked)
        for path in sorted(directory.glob("block-*/JOINT-budget*.json")):
            reference = load(path)
            joint_references.append({"path": str(path), "exact": reference["exact"],
                "requests": reference["limits"], "joint_E_utility": reference["joint_E_utility"],
                "opportunities": reference["full_opportunities"]})
            bindings[str(path.resolve())] = digest(path)
    if not arms:
        raise ValueError("No completed arms")
    reports, comparisons = {}, {}
    anchor = next(iter(arms.values()))
    anchor_map = {r["opportunity_id"]: r for r in anchor}
    for label, rows in arms.items():
        paired_gain(rows, anchor)
        if any(r["base"] != anchor_map[r["opportunity_id"]]["base"] for r in rows):
            raise ValueError("Methods did not use the same common baseline")
        base_rows = [dict(r, prediction=r["base"]) for r in rows]
        for row in rows:
            row["gain"] = None if row["outcome"] is None else (row["base"] - row["outcome"]) ** 2 - (row["prediction"] - row["outcome"]) ** 2
        reports[label] = {"scores": brier_report(rows), "relative_to_common_base": paired_gain(rows, base_rows),
            "costs_and_process": dict(counters[label]), "settings": settings[label],
            "unique_settled_targets": len({r["target_id"] for r in rows if r["outcome"] is not None}),
            "unique_positive_targets": len({r["target_id"] for r in rows if r["outcome"] == 1}),
            "positive_opportunities": sum(r["outcome"] == 1 for r in rows),
            "post_acquisition_reliability": reliability(rows),
            "by_lead": {str(lead): brier_report([r for r in rows if r["lead_hours"] == lead]) for lead in (1, 3, 6)},
            "by_station": {station: brier_report([r for r in rows if r["station"] == station]) for station in sorted({r["station"] for r in rows})},
            "calendar_sensitivity": [calendar_sensitivity(rows, n) for n in (24, 72, 168)]}
        for reference_label, reference_rows in arms.items():
            if label.startswith("model/") and label != reference_label and label.split("/")[-1] == reference_label.split("/")[-1]:
                comparisons[label + " VS " + reference_label] = paired_gain(rows, reference_rows)
    write(args.output / "ROWS.json", dict(arms))
    write(args.output / "REPORT.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset), "source_audit_sha256": digest(args.dataset / "REGIONAL_JOIN_AUDIT.json"),
        "outcomes_sha256": digest(outcomes_path), "arms": reports, "paired_comparisons": comparisons,
        "joint_E_references": joint_references, "input_bindings": bindings,
        "implementation_sha256": digest(args.output / "analyze_calendar.py"),
        "interpretation": "Whole predeclared calendar, divided into resource sessions. Session state resets at boundaries. Reference is a research TAF mapping, not a native official probability. Missing outcome bounds and block resampling do not prove representative sampling, weather-process independence, or post-acquisition calibration."})
    lines = ["# 同日历全机会比较", "", f"数据：`{args.dataset.name}`。本报告由冻结 trace 生成。", "",
        "| 方法 | 可结算机会 | 正例目标 | Brier | 相对共同基线增益 | 实际模型调用 | 请求 | E 可判定机会 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label, report in reports.items():
        s, c = report["scores"], report["costs_and_process"]
        lines.append(f"| {label} | {s['settled']} | {report['unique_positive_targets']} | {s['system_brier']:.8f} | {s['net_realized_gain']:+.8f} | {c['actual_model_calls']} | {c.get('resource_requests',0)} | {c.get('E_supported',0)+c.get('E_refuted',0)} |")
    lines += ["", "增益为共同基线 Brier 减去该方法 Brier，正值表示损失下降。", "",
        "程序全读与邻站持久性采用不紧的逻辑源预算；这是强对照及实际批量接口的敏感性参照，不能声称它们实际执行了历史线上批量请求。便宜程序的 1ms 记账不是测得的 CPU 延迟。", "",
        "每个方法保留相同机会与结果掩膜。缺测界、按提前量/站点统计、24/72/168h 日历分组敏感性及同条件成对比较见 REPORT.json。成对比较的缺测界共享同一个目标结果；原始评分器逐机会的界仍是有效但可能更宽的保守界。多个提前量共享结果；日历块不能自动当作独立风暴。", "",
        "资源计数同时列出实际用量、总硬上限及会话上限耗尽次数。源请求数和模型调用次数的配额可能生效，而 token/计算时间上限留有余量；不能把声明的预算维度都称为实际瓶颈。", ""]
    (args.output / "REPORT_CN.md").write_text("\n".join(lines))
    print(json.dumps({"arms": len(arms), "opportunities_per_arm": len(anchor), "paired_comparisons": len(comparisons)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--model-verifications", type=Path, nargs="*", default=[])
    parser.add_argument("--controls", type=Path, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
