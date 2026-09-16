"""Read-only registered-roster analysis; never launches a historical controller."""

import itertools
import json
import math
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1.analysis_integrity import load_bound_json, validate_branch_set
from disastertrace.monitoring_v1.comparison_fingerprint import fingerprint, compare
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OLD = REPO / "plans/v12_execution_20260915_01"
TRUST = {str(REPO / k):v for k,v in read(RUN / "PROTECTION_MANIFEST.json")["historical_files"].items()}
USED = {}


def bound(path, expected=None):
    path = Path(path).resolve()
    expected = expected or TRUST.get(str(path))
    if expected is None:
        raise ValueError("No registered hash for " + str(path))
    value = load_bound_json(path, expected)
    USED[str(path)] = expected
    return value


def index(rows, key):
    result = {}
    for row in rows:
        if row[key] in result: raise ValueError("Duplicate registered " + key)
        result[row[key]] = row
    return result


def settled(outcome):
    return outcome["status"] == "mature" and outcome["value"] is not None


def losses(report, outcomes, opportunity_ids):
    snaps = index(report["snapshots"], "opportunity_id")
    if not set(opportunity_ids) <= snaps.keys(): raise ValueError("Missing registered opportunity")
    selected = [oid for oid in opportunity_ids if settled(outcomes[oid])]
    total = math.fsum((snaps[oid]["forecast"]["value"] - outcomes[oid]["value"])**2 for oid in selected)
    return {"registered":len(opportunity_ids), "settled":len(selected),
            "positive":sum(outcomes[oid]["value"] for oid in selected),
            "loss_sum":total, "brier":total/len(selected) if selected else None}


def c2_audit():
    roster = bound(OLD / "C2_BRANCH_ROSTER.json")
    prior = {p["case"]:p for p in bound(OLD / "C2_ENGINEERING_RESULT.json")["parents"]}
    all_results, impacts, residual_impact = [], [], []
    for item in roster["parents"]:
        case = item["parent"]["case"]; folder = OLD / "branches" / case
        parent = bound(OLD / "parents" / case / "PARENT_CHECKPOINT.json", item["parent_checkpoint_sha256"])
        if canonical_hash(parent["payload"]) != parent["sha256"]: raise ValueError("Parent payload changed")
        execution = bound(folder / "RESULT.json")
        outcomes_binding = bound(folder / "COMMON_OUTCOMES_BINDING.json")
        outcomes = index(bound(outcomes_binding["path"], outcomes_binding["sha256"]), "opportunity_id")
        score = bound(folder / "FORMAL_SCORE.json")["scores"]
        runs = index(execution["results"], "rule")
        if set(runs) != set(item["plans"]): raise ValueError("C2 expected branch set changed")
        reg = {"opportunity_ids":item["U_parent"], "all_opportunity_ids":list(outcomes),
               "parent_sha256":parent["sha256"], "data_sha256":item["data_sha256"],
               "bank_sha256":item["bank_sha256"], "trace_heads":["program"],
               "branches":{name:runs[name].get("alias_of") for name in item["plans"]}}
        artifacts, reports = {}, {}
        for name, alias in reg["branches"].items():
            actual = alias or name
            if actual in artifacts: continue
            where = folder / actual
            contract = bound(where / "CONTRACT.json")
            stop = bound(where / "STOP.json")
            report = bound(where / "FORMAL_REPORT.json")
            trace = bound(where / "FIELD_FEATURE_TRACE.json", runs[actual]["feature_trace_sha256"])
            action = bound(where / "ACTION_TRACE.json")
            if (contract["parent_reference"]["checkpoint_sha256"] != item["parent_checkpoint_sha256"]
                    or contract["input_identity"] != {"data":item["data_sha256"], "bank":item["bank_sha256"]}
                    or stop["contract_sha256"] != canonical_hash(contract)
                    or stop["report_sha256"] != canonical_hash(report)):
                raise ValueError("C2 execution lineage changed")
            calculated = losses(report, outcomes, list(outcomes))
            original = score["arms"][actual]
            same = (calculated["registered"] == score["registered"]
                    and calculated["settled"] == original["scored"]
                    and math.isclose(calculated["loss_sum"], original["loss_sum"], rel_tol=1e-12, abs_tol=1e-12))
            artifacts[actual] = {"report":report, "traces":trace, "actions":action,
                "parent_sha256":contract["parent_reference"]["checkpoint_payload_sha256"],
                "data_sha256":contract["input_identity"]["data"], "bank_sha256":contract["input_identity"]["bank"],
                "score_verified":same, "execution_complete":bool(stop["done"] and runs[actual]["passed"])}
            reports[actual] = report
        result = validate_branch_set(reg, artifacts)
        result.update(case=case, formal_qualification="formal_bound_original_receipts_plus_arithmetic_reconciliation",
                      formal_scorer_reexecuted=False)
        all_results.append(result)
        for name,alias in reg["branches"].items():
            new = losses(reports[alias or name],outcomes,item["U_parent"])
            old = prior[case]["metrics"][name]
            same = all(new[k] == old[k] for k in ("registered","settled","positive","brier"))
            impacts.append({"case":case,"rule":name,"same_original_metrics":same,**new})
            plan = item["plans"][name]
            selected = set(plan["planned_query_order"])
            blocked = [r["catalog"]["query_id"] for r in plan["catalog_inventory"]
                       if r["catalog"]["query_id"] in selected and (r["already_cached"] or r["already_requested"])]
            residual_impact.append({"case":case,"rule":name,"old_planned_already_cached_or_requested":blocked,
                                    "would_change_due_to_new_exclusion":bool(blocked)})
        # Registered pairs, with the original full residual denominator, including missing Y.
        for previous in prior[case]["comparisons"]:
            a,b=previous["left"],previous["right"]
            left=index(reports[reg["branches"][a] or a]["snapshots"],"opportunity_id")
            right=index(reports[reg["branches"][b] or b]["snapshots"],"opportunity_id")
            ids=item["U_parent"]; known=[o for o in ids if settled(outcomes[o])]
            delta=math.fsum((left[o]["forecast"]["value"]-outcomes[o]["value"])**2-
                            (right[o]["forecast"]["value"]-outcomes[o]["value"])**2 for o in known)
            bounds=[(delta+s*(len(ids)-len(known)))/len(ids) for s in (-1,1)]
            if bounds != previous["missing_result_sensitivity_bounds"]:
                raise ValueError("C2 previous missing-Y bounds differ")
    publish(RUN / "C2_INTEGRITY.json", {"schema":"disastertrace.v13.c2_history.v1",
        "analysis_complete":all(r["analysis_complete"] for r in all_results),
        "execution_complete":all(r["execution_complete"] for r in all_results),
        "parents":all_results,"logical_branches":sum(r["registered_logical_branches"] for r in all_results),
        "expected_pairs":sum(r["expected_pair_count"] for r in all_results),
        "no_new_execution":True,"new_scientific_confirmation":False})
    publish(RUN / "RESIDUAL_V1_IMPACT.json",{"rows":residual_impact,
        "observed_affected":sum(r["would_change_due_to_new_exclusion"] for r in residual_impact),
        "old_v1_artifacts_rewritten":False,"v2_new_real_branches":0})
    return impacts


def stage_audit():
    root=OLD / "stage_C"; intent=bound(root / "INTENT.json")
    execution=bound(root / "RESULT.json"); old=bound(root / "ANALYSIS.json")
    score_by_case={}
    for row in execution["scored"]:
        if not row["passed"]: raise ValueError("Unqualified original formal score")
        score=bound(row["score_path"],row["score_sha256"])["scores"]
        score_by_case.setdefault(row["case"],{}).update(score["arms"])
    fingerprints, contrasts, rows, sessions = [], [], [], []
    for item in intent["cases"]:
        folder=root / item["case"]
        configs=bound(folder / "CONFIGS.json"); bank=bound(folder / "BANK.json")
        outcomes=index(bound(folder / "OUTCOMES.json"),"opportunity_id")
        ids=[o["opportunity_id"] for o in bound(folder / "DATA.json")["opportunities"]]
        if set(ids) != set(outcomes) or len(ids)!=len(set(ids)):raise ValueError("Stage roster changed")
        casefps, probabilities = {}, {}
        for arm in intent["arms"]:
            contract=bound(folder / arm / "CONTRACT.json")
            stop=bound(folder / arm / "STOP.json")
            report=bound(folder / arm / "FORMAL_REPORT.json")
            if (not stop["done"] or stop["contract_sha256"] != canonical_hash(contract)
                    or stop["report_sha256"] != canonical_hash(report)):
                raise ValueError("Original formal stop qualification mismatch")
            snaps=index(report["snapshots"],"opportunity_id"); index(report["calls"],"call_id")
            if set(snaps)!=set(ids):raise ValueError("Stage report denominator differs")
            calculated=losses(report,outcomes,ids); original=score_by_case[item["case"]][arm]
            if calculated["settled"]!=original["scored"] or not math.isclose(calculated["loss_sum"],original["loss_sum"],rel_tol=1e-12,abs_tol=1e-12):
                raise ValueError("Stage original formal loss mismatch")
            probabilities[arm]={oid:s["forecast"]["value"] for oid,s in snaps.items()}
            sessions.append({"case":item["case"],"arm":arm,"formal_arithmetic_unchanged":True,**calculated})
            consumer_files={p:h for p,h in contract["files"].items() if p.endswith((
                "/monitoring_fixed_v1/native_feature.py","/monitoring_v1/native_feature_forecast.py",
                "/monitoring_v1/evidence.py","/monitoring_v1/policies.py","/monitoring_v1/runtime.py"))}
            if not consumer_files:raise ValueError("Missing frozen consumer identity")
            # Paths are evidence, not identity: relocation must not change the consumer hash.
            codehash=canonical_hash({p.split('/disastertrace/')[-1]:h for p,h in consumer_files.items()})
            fp=fingerprint(configs[arm],baseline_bank=bank,consumer_code_sha256=codehash,
                source_contract_sha256=canonical_hash(contract["provider_policy"]))
            casefps[arm]=fp
            fingerprints.append({"case":item["case"],"arm":arm,"fingerprint":fp,"consumer_files":consumer_files})
        for a,b in itertools.combinations(intent["arms"],2):
            contrasts.append({"case":item["case"],"left":a,"right":b,**compare(casefps[a],casefps[b]),
                "old_name_based_bank_flag":(a=="F_COMMON") != (b=="F_COMMON")})
        rows.extend({"case":item["case"],"opportunity_id":oid,"settled":settled(outcomes[oid]),
                     "y":outcomes[oid]["value"],"probabilities":{a:p[oid] for a,p in probabilities.items()}} for oid in ids)
    metrics={}
    for arm in intent["arms"]:
        known=[r for r in rows if r["settled"]]
        value=math.fsum((r["probabilities"][arm]-r["y"])**2 for r in known)/len(known)
        metrics[arm]={"registered":len(rows),"settled":len(known),"brier":value,
                      "same_prior_brier":math.isclose(value,old["metrics"][arm]["brier"],rel_tol=1e-14)}
    for prior in old["all_pairwise"]:
        a,b=prior["reference"],prior["candidate"]
        known=math.fsum((r["probabilities"][a]-r["y"])**2-(r["probabilities"][b]-r["y"])**2 for r in rows if r["settled"])
        unknown=[]
        for r in rows:
            if r["settled"]:continue
            pa,pb=r["probabilities"][a],r["probabilities"][b]
            delta=[pa*pa-pb*pb,(1-pa)**2-(1-pb)**2];unknown.append([min(delta),max(delta)])
        bounds=[(known+math.fsum(d[i] for d in unknown))/len(rows) for i in (0,1)]
        if any(not math.isclose(x,y,abs_tol=1e-14) for x,y in zip(bounds,prior["prediction_specific_missing_Y_bounds"])):
            raise ValueError("Stage missing-result bounds differ")
    corrections=[c for c in contrasts if not c["same_predictor"] and not c["old_name_based_bank_flag"]]
    publish(RUN / "METHOD_FINGERPRINTS.json",{"method_sessions":len(fingerprints),"fingerprints":fingerprints,
        "contrasts":contrasts,"name_based_classification_corrections":corrections,
        "interpretation":"actual consumer identity, not proof of causal comparability"})
    return {"sessions":sessions,"metrics":metrics,"all_previous_missing_bounds_unchanged":True,
            "consumer_classification_corrections":len(corrections)}


def main():
    c2=c2_audit(); stage=stage_audit()
    result={"schema":"disastertrace.v13.historical_report_impact.v1",
        "c2_metrics":c2,"stage_C":stage,"new_policy_runs":0,"original_scores_modified":False,
        "all_checked_numerical_results_unchanged":all(r["same_original_metrics"] for r in c2)
                and all(r["same_prior_brier"] for r in stage["metrics"].values()),
        "classification_correction":"FOLLOW is a baseline consumer, not the native values predictor",
        "input_hashes":USED}
    publish(RUN / "HISTORICAL_REPORT_IMPACT.json",result)
    print(json.dumps({"c2_metric_rows":len(c2),"stage_sessions":len(stage["sessions"]),
                      "same_numbers":result["all_checked_numerical_results_unchanged"],
                      "classification_corrections":stage["consumer_classification_corrections"]}),flush=True)


if __name__ == "__main__":main()
