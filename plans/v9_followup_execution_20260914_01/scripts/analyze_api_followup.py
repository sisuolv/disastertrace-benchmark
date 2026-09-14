"""Reconstruct API outputs and paired losses; this script never calls a model."""

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
import math
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import score_admitted
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, Forecast
from disastertrace.monitoring_fixed_v1.heads import parse_response
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.api_capture import RATES
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

ROOT = Path(__file__).resolve().parents[1]


def budget_audit(folder):
    budget = read(folder/"BUDGET.json")
    requests = list(folder.rglob("REQUEST.json"))
    ids = set()
    totals = defaultdict(Counter)
    for request_path in requests:
        request = read(request_path)
        cid, model = request["call_id"], request["payload"]["model"]
        assert cid not in ids
        ids.add(cid)
        entry = budget["calls"][cid]
        assert request["fee_reservation_nanodollars"] == entry["reserved"]
        totals[model]["request_receipts"] += 1
        response_path = request_path.parent/"RESPONSE.json"
        if response_path.exists():
            receipt = read(response_path)
            response = receipt["body"]
            wire_path=request_path.parent/"RESPONSE.body"
            if wire_path.exists():
                wire=read(request_path.parent/"WIRE_RECEIPT.json")
                assert digest(wire_path)==wire["stored_body_sha256"]
                assert json.loads(wire_path.read_bytes())==response
            usage = response["usage"]
            input_rate, output_rate = RATES[model]
            amount = usage["prompt_tokens"]*input_rate + usage["completion_tokens"]*output_rate
            if entry["status"] == "settled":
                assert entry["actual"] == amount
            else:
                assert entry["status"] in ["unknown","reserved"] and entry["reserved"]>=amount
                totals[model]["received_but_billing_unreconciled"]+=1
            assert amount == receipt["peak_tariff_cost_upper_nanodollars"]
            assert receipt["provider_compute_seconds"] is None
            totals[model].update(responses=1, input_tokens=usage["prompt_tokens"],
                                  output_tokens=usage["completion_tokens"], fee_nanodollars=amount)
        elif (request_path.parent/"FAILURE.json").exists():
            totals[model]["failed_attempts"] += 1
        else:
            totals[model]["unfinished_attempts"] += 1
    assert ids <= set(budget["calls"])
    charged = sum(r["actual"] if r["status"] == "settled" else r["reserved"] for r in budget["calls"].values())
    return {"per_model": dict(totals), "attempt_statuses": dict(Counter(r["status"] for r in budget["calls"].values())),
            "unmatched_reservations": sorted(set(budget["calls"])-ids), "committed_upper_usd": charged/1e9,
            "budget_limit_usd": budget["limit_nanodollars"]/1e9,
            "within_budget": charged <= budget["limit_nanodollars"],
            "timing": "API client delivery only; provider compute and exact model weights unavailable"}


def audit_e(evidence="api_evidence_01"):
    folder = ROOT/evidence
    read(folder/"COMPLETE.json")
    out = ROOT/("reports/api_evidence_audit_01" if evidence=="api_evidence_01" else "reports/api_evidence_audit_02")
    out.mkdir(exist_ok=False)
    plan = read(folder/"PLAN.json")
    for path, sha in plan["files"].items():
        assert digest(Path(path)) == sha
    spec = importlib.util.spec_from_file_location("frozen_api_evidence", folder/"source/evidence_diagnostic.py")
    reducer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reducer)
    expected = read(folder/"evaluator/REFERENCES.json")
    policies = {t["call_id"]:read(folder/"policy"/(t["call_id"]+".json")) for t in plan["tasks"]}
    views = {(t["region"],t["opportunity_id"],t["condition"]): json.loads(policies[t["call_id"]]["messages"][1]["content"])
             for t in plan["tasks"] if t["representation"] == "full_bundle"}
    saved = {(r["model"],r["call_id"]):r for r in read(folder/"RESULTS.json")}
    groups = defaultdict(Counter)
    for task in plan["tasks"]:
        cid = task["call_id"]
        view = views[task["region"],task["opportunity_id"],task["condition"]]
        assert reducer.independent_reference(view) == expected[cid]
        assert reducer.messages(view,task["representation"],task["reasoning"]) == policies[cid]["messages"]
        for model in plan["models"]:
            row = saved[model,cid]
            path = folder/"captures"/model/cid/"RESPONSE.json"
            valid = correct = all_fields = False
            answer = None
            if path.exists():
                receipt = read(path)
                choice = receipt["body"]["choices"][0]
                try:
                    answer = reducer.parse(choice["message"]["content"],task["query_ids"],task["reasoning"])
                    valid = choice["finish_reason"] == "stop"
                    correct = valid and answer["fact_truth"] == expected[cid]["fact_truth"]
                    all_fields = correct and (task["reasoning"] == "direct" or answer["slots"] == expected[cid]["slots"])
                except (ValueError, TypeError):
                    pass
            assert (valid,correct,all_fields) == (row["valid"],row["correct"],row["all_fields_correct"])
            keys = [model+"__"+task["representation"]+"__"+task["reasoning"],
                    model+"__"+task["region"]+"__"+task["representation"]+"__"+task["reasoning"]]
            for key in keys:
                g=groups[key]
                g.update(n=1,valid=int(valid),correct=int(correct),all_fields_correct=int(all_fields),
                         always_unknown_correct=int(expected[cid]["fact_truth"]=="unknown"))
                g["collection_failures"]+=int(not path.exists())
                if valid:
                    g["unsupported_determinate"] += int(expected[cid]["fact_truth"] == "unknown" and answer["fact_truth"] in ["true","false"])
                    if task["reasoning"] == "slotwise":
                        g["slots"] += len(task["query_ids"])
                        g["correct_slots"] += sum(answer["slots"][q] == expected[cid]["slots"][q] for q in task["query_ids"])
                        g["aggregate_inconsistent_with_own_slots"] += int(reducer.aggregate(answer["slots"].values()) != answer["fact_truth"])
                if path.exists():
                    g.update(input_tokens=receipt["body"]["usage"]["prompt_tokens"],output_tokens=receipt["body"]["usage"]["completion_tokens"],
                             client_delivery_seconds=receipt["elapsed_seconds"],fee_nanodollars=receipt["peak_tariff_cost_upper_nanodollars"])
    result={"passed":True,"groups":dict(groups),"underlying_opportunities":plan["underlying_opportunities"],
            "planned_comparisons":len(saved),"reference_views_reconstructed":len(plan["tasks"]),
            "budget":budget_audit(folder),"scope":"state-stratified exposed E diagnostics; views are dependent; no F scores or population frequency claim"}
    publish(out/"VALIDATION.json", result)
    lines=["# DeepSeek E 诊断复核", "", "多个视图共享底层问题；以下不是独立天气过程的样本量。", "",
           "| 模型 | 输入 | 输出方式 | 最终E正确 | 全字段正确 | 格式有效 | 保守费用USD |", "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for key,g in groups.items():
        parts=key.split("__")
        if len(parts)==3:
            lines.append(f"| {' | '.join(parts)} | {g['correct']}/{g['n']} | {g['all_fields_correct']}/{g['n']} | {g['valid']}/{g['n']} | {g['fee_nanodollars']/1e9:.5f} |")
    (out/"REPORT_CN.md").write_text("\n".join(lines)+"\n")


def audit_f(pilot="api_pilot_01"):
    folder=ROOT/pilot
    complete=read(folder/"COMPLETE.json")
    out=ROOT/("reports/api_forecast_audit_01" if pilot=="api_pilot_01" else "reports/api_rare_forecast_audit_01")
    out.mkdir(exist_ok=False)
    cases=sorted(p.parent for p in folder.glob("*/CONFIGS.json"))
    records=[]
    unfinished=[]
    for case in cases:
        for path,sha in read(case/"FREEZE.json")["files"].items():
            assert digest(Path(path))==sha
        configs=read(case/"CONFIGS.json")
        done=[a for a in configs if (case/a/"COMPLETE.json").exists()]
        unfinished += [{"case":case.name,"arm":a} for a in configs if a not in done]
        reports={a:read(case/a/"REPORT.json") for a in done}
        assert "follow" in reports
        contract=read(case/"COMPARISON.json")["payload"]
        scored=score_admitted(read(case/"OUTCOMES.json"), {a:case/a/"admission.jsonl" for a in done},
            comparison=ComparisonContract(contract["invariants"],contract["allowed_interventions"]))
        publish(out/(case.name+"__CANONICAL_SCORES.json"),scored)
        follow={r["opportunity_id"]:r for r in reports["follow"]["snapshots"]}
        outcomes={r["opportunity_id"]:r for r in read(case/"OUTCOMES.json")}
        bank=read(case/"BANK.json")
        threshold=read(case/"DATA.json")["targets"][0]["threshold"]
        pooled=bank["cells"][json.dumps([threshold,"pooled"],separators=(",",":"))]
        prior=(pooled["positive"]+1)/(pooled["n"]+2)
        observed=[o["value"] for o in outcomes.values() if o["status"]=="mature"]
        reference_losses={"always_zero_brier":sum(observed)/len(observed) if observed else None,
                          "fit_period_constant_probability":prior,
                          "fit_period_constant_brier":sum((prior-y)**2 for y in observed)/len(observed) if observed else None,
                          "scope":"analytical score references only; not additional executed trajectories"}
        for arm,report in reports.items():
            assert not report["outcome_table_accessed_by_policy"]
            rows=report["snapshots"]
            assert len(rows)==72 and set(follow)=={r["opportunity_id"] for r in rows}
            losses,deltas,missing_endpoints=[],[],[]
            differing=0
            for row in rows:
                oid=row["opportunity_id"];p=row["forecast"]["value"];b=follow[oid]["forecast"]["value"]
                differing+=int(p!=b)
                outcome=outcomes[oid]
                if outcome["status"]=="mature":
                    loss=(p-outcome["value"])**2
                    losses.append(loss);deltas.append(loss-(b-outcome["value"])**2)
                else:
                    endpoints=[(p-y)**2-(b-y)**2 for y in [0,1]]
                    missing_endpoints.append((min(endpoints),max(endpoints)))
            mean=math.fsum(losses)/len(losses) if losses else None
            assert mean is None or math.isclose(mean,scored["scores"]["arms"][arm]["mean_loss"],abs_tol=1e-14)
            call_counts=Counter()
            for call in report["calls"]:
                view=call["bundle"]["payload"]
                f=None
                supported=native_slot_support(EvidenceBundle.restore(call["bundle"]))["status"]
                assert supported==call["expected_e_from_disclosed_products"]
                try:
                    if not call["details"].get("ended_with_eos") or call.get("response_error") is not None:
                        raise ValueError("Incomplete or rejected original response")
                    if call["head"]=="program":
                        f=Forecast(**json.loads(call["raw"]))
                    else:
                        answer=parse_response(call["raw"], EvidenceBundle.restore(call["bundle"]),call["head"])
                        f=answer.forecast
                        assert answer.e_status==call["reported_e"]
                        call_counts["E_answers"]+=int(answer.e_status is not None)
                        call_counts["E_correct"]+=int(answer.e_status==supported)
                        call_counts["E_unjustified_determinate"]+=int(supported=="undetermined" and answer.e_status in ["supported","refuted"])
                except (ValueError,TypeError):
                    call_counts["invalid_responses"]+=1
                if f is not None:
                    val=f.value
                    assert val==call["proposed_probability"]
                    call_counts["proposed_values"]+=1
                    call_counts["equal_visible_current"]+=int(val==view["state"]["forecast"]["value"])
                    call_counts["equal_visible_baseline"]+=int(val==view["baseline"]["forecast"]["value"])
                    call_counts["new_vs_visible_current_and_baseline"]+=int(val not in [view["state"]["forecast"]["value"],view["baseline"]["forecast"]["value"]])
                    distance=min(abs(val-view["state"]["forecast"]["value"]),abs(val-view["baseline"]["forecast"]["value"]))
                    call_counts["within_0_000001_of_visible_value"]+=int(distance<=1e-6)
                    call_counts["within_0_005_of_visible_value"]+=int(distance<=0.005)
                    call_counts["more_than_0_005_from_visible_values"]+=int(distance>0.005)
                    outcome=outcomes[call["opportunity_id"]]
                    if call["reported_e"] is not None and outcome["status"]=="mature":
                        e="correct_E" if call["reported_e"]==supported else "incorrect_E"
                        delta=(val-outcome["value"])**2-(view["baseline"]["forecast"]["value"]-outcome["value"])**2
                        call_counts[e+"__F_improved"]+=int(delta < -1e-14)
                        call_counts[e+"__F_worsened"]+=int(delta > 1e-14)
                        call_counts[e+"__F_equal"]+=int(abs(delta) <= 1e-14)
            records.append({"case":case.name,"arm":arm,"opportunities":72,"mature":len(losses),"missing":len(missing_endpoints),
                "positive":sum(o["status"]=="mature" and o["value"]==1 for o in outcomes.values()),
                "brier":mean,"delta_brier_vs_follow":math.fsum(deltas)/len(deltas) if deltas else None,
                "lower_loss":sum(d < -1e-14 for d in deltas),"higher_loss":sum(d > 1e-14 for d in deltas),
                "effective_values_different_from_follow":differing,
                "all_opportunity_delta_bounds":[(math.fsum(deltas)+sum(m[j] for m in missing_endpoints))/72 for j in [0,1]],
                "model_calls":report["actual_model_calls"],"program_calls":report["actual_program_forecast_calls"],
                "constant_references":reference_losses,
                "E":report["e_counts"],"value_proposals":dict(call_counts),"resource_spent":report["resource_spent"],
                "resource_reserved":report["resource_reserved"],"admission_statuses":dict(Counter(a["status"] for a in report["attempts"])),
                "report_sha256":digest(case/arm/"REPORT.json")})
        print(json.dumps({"case":case.name,"audited_arms":len(done)}),flush=True)
    publish(out/"VALIDATION.json",{"passed":True,"records":records,"unfinished_arms":unfinished,
        "all_registered_arms_finished":complete["all_completed"] and not unfinished,
        "budget":budget_audit(folder),"source_timing":"declared archive delays, program/persistence costs; measured API client delivery",
        "scope":"exposed historical development pilot, base-bound protocol only; not independent process confirmation or deployment resource parity",
        "selection":read(folder/"PREREGISTRATION.json")["selection"],
        "numeric_change_limit":"Differences, including rounding, do not themselves establish new forecast information; compare paired losses and controls."})


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=["E","F"])
    parser.add_argument("--evidence",choices=["api_evidence_01","api_evidence_02"],default="api_evidence_01")
    parser.add_argument("--pilot",choices=["api_pilot_01","api_rare_pilot_01"],default="api_pilot_01")
    args=parser.parse_args()
    audit_e(args.evidence) if args.stage=="E" else audit_f(args.pilot)
