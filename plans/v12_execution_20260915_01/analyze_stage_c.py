"""Describe fixed-roster development comparisons, including failures and missing Y."""
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read

RUN = Path(__file__).resolve().parent
OUT = RUN / "stage_C"


def paired(rows, reference, candidate):
    selected = [r for r in rows if reference in r["probabilities"] and candidate in r["probabilities"]]
    settled = [r for r in selected if r["settled"]]
    missing = [r for r in selected if not r["settled"]]
    deltas = [(r["probabilities"][reference]-r["y"])**2 - (r["probabilities"][candidate]-r["y"])**2 for r in settled]
    unknown = []
    for r in missing:
        a, b = r["probabilities"][reference], r["probabilities"][candidate]
        alternatives = [a*a-b*b, (1-a)**2-(1-b)**2]
        unknown.append((min(alternatives), max(alternatives)))
    known = math.fsum(deltas)
    return {"reference": reference, "candidate": candidate, "registered": len(selected),
        "settled": len(settled), "missing": len(missing),
        "positive": sum(r["y"] for r in settled),
        "positive_delta_favors": candidate,
        "mean_brier_improvement": known/len(settled) if settled else None,
        "positive_contribution_per_settled_opportunity": math.fsum(d for r,d in zip(settled,deltas) if r["y"]==1)/len(settled) if settled else None,
        "negative_contribution_per_settled_opportunity": math.fsum(d for r,d in zip(settled,deltas) if r["y"]==0)/len(settled) if settled else None,
        "prediction_specific_missing_Y_bounds": [(known+math.fsum(x[i] for x in unknown))/len(selected) for i in (0,1)] if selected else None,
        "bounds_are_confidence_intervals": False,
        "bank_difference_involved": (reference=="F_COMMON") != (candidate=="F_COMMON"),
        "interpretation": "descriptive exposed development; calendar blocks are not independent-process confirmation"}


def main():
    execution = read(OUT / "RESULT.json")
    if not execution.get("results"):
        publish(OUT / "ANALYSIS.json", {"available": False, "reason": execution.get("status"), "formal_comparison_complete": False})
        return
    intent = read(OUT / "INTENT.json")
    rows, resources, source_files, model_receipts = [], [], {}, []
    selector_statuses, format_diagnostics, error_key_profiles = Counter(), Counter(), Counter()
    incomplete = []
    for item in intent["cases"]:
        case = OUT / item["case"]
        targets = {o["opportunity_id"]: o for o in read(case / "DATA.json")["opportunities"]}
        outcomes = {o["opportunity_id"]: o for o in read(case / "OUTCOMES.json")}
        if set(targets) != set(outcomes):
            raise ValueError("Evaluation outcome roster differs from registered opportunities")
        source_files[str(case / "OUTCOMES.json")] = digest(case / "OUTCOMES.json")
        reports = {}
        for arm in intent["arms"]:
            path = case / arm / "FORMAL_REPORT.json"
            if not path.exists():
                incomplete.append({"case": item["case"], "arm": arm, "status": "missing_formal_report"})
                continue
            report = read(path)
            if len(report["snapshots"]) != len(targets):
                raise ValueError("Formal report changed the opportunity denominator")
            reports[arm] = {o["opportunity_id"]: o for o in report["snapshots"]}
            if set(reports[arm]) != set(targets):
                raise ValueError("Formal report opportunity IDs differ")
            source_files[str(path)] = digest(path)
            for selector in report["selector_calls"]:
                error = selector.get("execution_status") or selector.get("response_error")
                selector_statuses[error or "valid"] += 1
                if error:
                    try:
                        raw_object = json.loads(selector["raw"])
                    except (ValueError, TypeError):
                        format_diagnostics["not_a_plain_JSON_response"] += 1
                    else:
                        if isinstance(raw_object, dict):
                            error_key_profiles[",".join(sorted(raw_object))] += 1
                        if isinstance(raw_object,dict) and "queries" in raw_object and "query_order" not in raw_object:
                            format_diagnostics["queries_instead_of_query_order"] += 1
                        elif isinstance(raw_object,dict) and "query_handles" in raw_object and "query_order" not in raw_object:
                            format_diagnostics["query_handles_instead_of_query_order"] += 1
                        else:
                            format_diagnostics["other_structural_or_semantic_error"] += 1
            resources.append({"case": item["case"], "arm": arm,
                "spent": report["resource_spent"], "reserved": report["resource_reserved"],
                "model_dispatches": report["actual_model_calls"], "program_forecasts": sum(c["head"]=="program" for c in report["calls"]),
                "selector_errors": dict(Counter((c.get("execution_status") or c.get("response_error") or "valid") for c in report["selector_calls"])),
                "forecast_admission": dict(Counter(c["admission_status"] for c in report["calls"])),
                "effective_modes": dict(Counter(r["mode"] for r in report["snapshots"]))})
        for oid in sorted(targets):
            y = outcomes[oid]
            rows.append({"case": item["case"], "region": item["case"].split("__")[0],
                "calendar_week": item["case"].split("__")[1], "opportunity_id": oid,
                "cutoff": targets[oid]["cutoff"], "y": y["value"],
                "settled": y["status"]=="mature" and y["value"] is not None,
                "outcome_status": y["status"], "quality_status": y.get("quality_status"),
                "probabilities": {arm: snaps[oid]["forecast"]["value"] for arm,snaps in reports.items()}})
        for p in (case / "spool").glob("*.api_intent.json"):
            prefix = p.name.removesuffix(".api_intent.json")
            capture_path = p.with_name(prefix + ".api_capture.json")
            capture = read(capture_path) if capture_path.exists() else None
            usage = None
            if capture is not None:
                try:
                    usage = json.loads(capture["body"]).get("usage")
                except (ValueError, TypeError, AttributeError):
                    pass
            model_receipts.append({"case": item["case"], "intent_sha256": digest(p),
                "http_status": None if capture is None else capture["http_status"], "provider_usage": usage,
                "response_published": p.with_name(prefix + ".response.json").exists(),
                "failure_retained": p.with_name(prefix + ".failure.json").exists(),
                "provider_processing_unknown": capture is None})
    metrics = {}
    for arm in intent["arms"]:
        eligible = [r for r in rows if arm in r["probabilities"]]
        settled = [r for r in eligible if r["settled"]]
        squared = [(r["probabilities"][arm]-r["y"])**2 for r in settled]
        metrics[arm] = {"registered": len(eligible), "settled": len(settled),
            "positive": sum(r["y"] for r in settled), "missing": len(eligible)-len(settled),
            "brier": math.fsum(squared)/len(squared) if squared else None,
            "positive_brier": math.fsum(d for r,d in zip(settled,squared) if r["y"]==1)/sum(r["y"]==1 for r in settled) if any(r["y"]==1 for r in settled) else None,
            "negative_brier": math.fsum(d for r,d in zip(settled,squared) if r["y"]==0)/sum(r["y"]==0 for r in settled) if any(r["y"]==0 for r in settled) else None}
    reconciled = set()
    for group in execution["scored"]:
        if not group["passed"]:
            continue
        score_path = Path(group.get("score_path", str(OUT / group["case"] / ("SCORE_" + group["group"] + ".json"))))
        if group.get("score_sha256") and digest(score_path) != group["score_sha256"]:
            raise ValueError("Formal score file changed before report reconciliation")
        score = read(score_path)["scores"]
        source_files[str(score_path)] = digest(score_path)
        case_rows = [r for r in rows if r["case"] == group["case"]]
        if score["registered"] != len(case_rows):
            raise ValueError("Formal score and derived report denominators differ")
        for arm, formal in score["arms"].items():
            settled = [r for r in case_rows if r["settled"]]
            calculated = math.fsum((r["probabilities"][arm] - r["y"])**2 for r in settled)
            key = (group["case"], arm)
            if (key in reconciled or formal["scored"] != len(settled)
                    or not math.isclose(formal["loss_sum"], calculated, rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError("Derived loss differs from original formal scoring")
            reconciled.add(key)
    expected = {(item["case"], arm) for item in intent["cases"] for arm in intent["arms"]}
    if execution["passed"] and reconciled != expected:
        raise ValueError("Formal score reconciliation is incomplete")
    comparisons = [paired(rows,a,b) for a,b in itertools.combinations(intent["arms"],2)]
    primary = [paired(rows,a,"LLM_SELECTOR") for a in intent["arms"] if a!="LLM_SELECTOR"]
    strata = {axis: {value: [paired([r for r in rows if r[axis]==value], a, "LLM_SELECTOR")
        for a in ("F_COMMON", "B11_BATCH", "B11_COVERAGE")]
        for value in sorted({r[axis] for r in rows})} for axis in ("region", "calendar_week")}
    total_tokens = sum(r["provider_usage"].get("total_tokens", 0) for r in model_receipts if isinstance(r["provider_usage"],dict))
    result = {"available": True, "formal_comparison_complete": execution["passed"] and not incomplete,
        "registered_cases": len(intent["cases"]), "calendar_blocks": len(strata["calendar_week"]),
        "independent_weather_processes_established": False, "metrics": metrics,
        "primary_model_comparisons": primary, "all_pairwise": comparisons, "strata": strata,
        "incomplete": incomplete, "http_intents": len(model_receipts),
        "provider_reported_tokens": total_tokens, "unknown_provider_responses": sum(r["provider_processing_unknown"] for r in model_receipts),
        "provider_invoice_cost": None, "model_role": "query selector; frozen program produces probabilities",
        "selector_calls": sum(selector_statuses.values()), "valid_selector_calls": selector_statuses["valid"],
        "selector_statuses": dict(selector_statuses), "format_diagnostics": dict(format_diagnostics),
        "error_key_profiles": dict(error_key_profiles),
        "posthoc_reply_normalization_or_reexecution": False,
        "formal_score_reconciliation": {"matched_case_arms": len(reconciled), "expected_case_arms": len(expected), "passed": reconciled == expected},
        "source_files": source_files, "execution_result_sha256": digest(OUT / "RESULT.json"),
        "confirmation_opened": False}
    publish(OUT / "ANALYSIS_ROWS.json", rows)
    publish(OUT / "RESOURCE_AND_API_LEDGER.json", {"resources": resources, "model_receipts": model_receipts})
    publish(OUT / "ANALYSIS.json", result)
    lines = ["# 年度预测器下的查询策略比较", "",
        "模型仅决定补充资料的查询顺序；概率由相同的冻结程序预测器产生。以下是已暴露开发数据的历史回放，不是独立确认或实时未来预报。",
        f"注册 {len(intent['cases'])} 个日会话，{len(rows)} 个机会，四个全球周块；正式比较完整：{result['formal_comparison_complete']}。", "",
        f"派生损失与正式评分逐组核对：{len(reconciled)}/{len(expected)} 个方法会话的分母和损失总和一致。", "",
        "| 方法 | 可结算/注册 | 正例 | Brier | 正例 Brier | 负例 Brier |", "|---|---:|---:|---:|---:|---:|"]
    number = lambda value: "NA" if value is None else f"{value:.7f}"
    for arm,m in metrics.items():
        lines.append(f"| {arm} | {m['settled']}/{m['registered']} | {m['positive']} | {number(m['brier'])} | {number(m['positive_brier'])} | {number(m['negative_brier'])} |")
    lines += ["", "| 参照方法 | 参照损失 - LLM 损失 | 是否更换预测器 bank |", "|---|---:|---|"]
    for p in primary:
        lines.append(f"| {p['reference']} | {number(p['mean_brier_improvement'])} | {p['bank_difference_involved']} |")
    lines += ["", f"API 请求意图 {len(model_receipts)}，供应方报告 token {total_tokens}；没有完整供应方响应的请求 {result['unknown_provider_responses']}。供应方实际账单未查询，不填作零成本。",
        f"合法 selector 回复 {result['valid_selector_calls']}/{result['selector_calls']}。错误按原契约保留：{dict(selector_statuses)}。",
        f"只读格式诊断：{dict(format_diagnostics)}。没有把别名键或解释文字事后改成合法动作，也没有重跑预测。",
        f"无效 JSON 对象的实际顶层键组合：{dict(error_key_profiles)}。字段别名与契约不一致和 JSON 外文字分别计数；这些是接口失败，不能单独作为取证推理能力结论。",
        "无效回复、运输失败、费用未知和未取得资料的机会均保留。完整账本见 RESOURCE_AND_API_LEDGER.json。",
        "相同结果掩膜保证方法间可比，不保证缺失无偏；逐预测值敏感性界及地区、周块分层见 ANALYSIS.json。",
        "F_COMMON 与其他方法采用不同 bank，其差异不能全归因于查询策略。B00/B01/B10/B11 固定 coverage selector 比较预算分配和资料共享。",
        "本轮不根据这些开发损失选择新的日期、模型或提示词；一次开发胜负不构成 novelty 或独立过程泛化证明。"]
    (OUT / "REPORT_CN.md").write_text("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
