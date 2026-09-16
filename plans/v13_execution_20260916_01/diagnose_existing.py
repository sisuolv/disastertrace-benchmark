"""Bounded clock/public-action/API audit of already exposed v12 inputs."""

import base64
import json
import math
from collections import Counter
from pathlib import Path

from audit_history import RUN, REPO, OLD, TRUST, USED, bound, index
from disastertrace.monitoring_v1.native_feature_forecast import feature_vector, predict_features
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def candidate_at(data, target_id, at):
    candidates=[r for r in data["baseline_candidates"] if r["target_id"]==target_id
                and r["available_at"]<=at and r["issued_at"]<=at and at<r["valid_until"]]
    withdrawals=[r for r in data.get("baseline_withdrawals",[]) if r["target_id"]==target_id and r["available_at"]<=at]
    latest=max([r["issued_at"] for r in candidates]+[r.get("issued_at",r["available_at"]) for r in withdrawals],default=None)
    if latest is None:return None
    current=[r for r in candidates if r["issued_at"]==latest]
    if any(r.get("issued_at",r["available_at"])>=latest for r in withdrawals):return None
    if not current:return None
    if len({r.get("native_semantics_sha256",canonical_hash(r["projection"])) for r in current})>1:
        raise ValueError("Ambiguous common version at diagnostic clock")
    return min(current,key=lambda r:r["source_id"])


def numeric(bank, target, candidate, qids, disclosed, at):
    features=feature_vector(target,candidate,qids,disclosed,at=at,mode=bank["mode"])
    standardized=[(features.get(k,0)-mu)/scale for k,mu,scale in zip(bank["feature_names"],bank["mean"],bank["scale"])]
    logits=[intercept+math.fsum(a*b for a,b in zip(row,standardized)) for row,intercept in zip(bank["coefficients"],bank["intercepts"])]
    probabilities=predict_features(bank,features)
    return {"at":at,"features":features,"features_sha256":canonical_hash(features),"logits":logits,
            "probability":probabilities[str(target["threshold"])],
            "native_taf_source_id":None if candidate is None else candidate["source_id"],
            "native_taf_issued_at":None if candidate is None else candidate["issued_at"],
            "disclosed_query_ids":sorted(disclosed)}


def clock_row(case, data, report, native, oid):
    opportunity=next(r for r in data["opportunities"] if r["opportunity_id"]==oid)
    calls=[r for r in report["calls"] if r["opportunity_id"]==oid and r["head"]=="program"]
    row={"case":case,"opportunity_id":oid,"selection":"two smallest SHA256 of public opportunity ID per registered case",
         "label_or_loss_used_for_selection":False,"early_view_origin":"offline reconstruction of previously registered archive; not a captured training invocation",
         "forecast_cutoff":opportunity["cutoff"],"status":"insufficient_support"}
    if len(calls)!=1:
        return {**row,"reason":"expected exactly one actual program call; no replacement target chosen"}
    call=calls[0]; payload=call["bundle"]["payload"]; content=payload["baseline"]["content"]
    early=opportunity["cutoff"]-600_000_000; actual=call["started_at"]
    target=content["legacy_target_contract"]; qids=content["E_question"]["query_ids"]
    early_candidate=candidate_at(data,target["target_id"],early)
    actual_candidate=candidate_at(data,target["target_id"],actual)
    if actual_candidate!=content["native_taf"]:
        return {**row,"reason":"offline version reconstruction differs from captured native baseline"}
    assets=payload["assets"]
    early_disclosed={a["content"]["query_id"]:a["content"] for a in assets if max(a["available_at"],a["completed_at"])<=early}
    actual_disclosed={a["content"]["query_id"]:a["content"] for a in assets if max(a["available_at"],a["completed_at"])<=actual}
    a=numeric(native,target,early_candidate,qids,early_disclosed,early)
    b=numeric(native,target,early_candidate,qids,early_disclosed,actual)
    c=numeric(native,target,actual_candidate,qids,actual_disclosed,actual)
    if not math.isclose(c["probability"],call["proposed_probability"],rel_tol=1e-12,abs_tol=1e-12):
        return {**row,"reason":"actual captured candidate probability fails arithmetic reproduction"}
    clock_delta=b["probability"]-a["probability"]; info_delta=c["probability"]-b["probability"]
    catalog=index(data["query_catalog"],"query_id")
    return {**row,"status":"drift" if abs(clock_delta)>1e-12 or abs(info_delta)>1e-12 else "no_material_drift",
            "materiality_rule":"absolute probability change > 1e-12 for numerical identity; not a scientific benefit threshold",
            "target_contract":target,"actual_call_id":call["call_id"],"actual_bundle_sha256":call["bundle"]["bundle_hash"],
            "early_legal_disclosure":a,"same_information_at_actual_clock_arithmetic":b,"actual_legal_disclosure":c,
            "clock_probability_delta":clock_delta,"information_probability_delta":info_delta,
            "clock_changed_features":sorted(k for k in a["features"]|b["features"] if a["features"].get(k)!=b["features"].get(k)),
            "information_changed_features":sorted(k for k in b["features"]|c["features"] if b["features"].get(k)!=c["features"].get(k)),
            "new_legal_query_frontier":[q for q in qids if early<catalog[q]["available_at"]<=actual],
            "new_actually_disclosed_query_ids":sorted(set(actual_disclosed)-set(early_disclosed)),
            "native_version_changed":a["native_taf_source_id"]!=c["native_taf_source_id"],
            "same_information_comparison_is_a_numeric_decomposition_not_a_new_policy_run":True}


def run():
    root=OLD/"stage_C"; intent=bound(root/"INTENT.json")
    clock_rows,action_rows,api_rows=[],[],[]
    old_policy=bound(root/"API_POLICY.json")
    for item in intent["cases"]:
        folder=root/item["case"];data=bound(folder/"DATA.json")
        report=bound(folder/"B11_COVERAGE/FORMAL_REPORT.json")
        configs=bound(folder/"CONFIGS.json"); native=configs["B11_COVERAGE"]["native_feature_bank"]
        ids=sorted((o["opportunity_id"] for o in data["opportunities"]),key=canonical_hash)[:2]
        clock_rows.extend(clock_row(item["case"],data,report,native,oid) for oid in ids)
        selectors=index(bound(folder/"LLM_SELECTOR/FORMAL_REPORT.json")["selector_calls"],"call_id")
        requests=sorted(p for p in TRUST if str(folder/"spool")+'/' in p and p.endswith('.request.json'))
        if len(requests)!=24:raise ValueError("Original registered 24-request case denominator differs")
        for request_name in requests:
            path=Path(request_name);request=bound(path);view=request["request"]
            capture_path=path.with_name(path.name.removesuffix('.request.json')+'.api_capture.json')
            capture=bound(capture_path);original=selectors[request["call_id"]]
            qrows=[]
            for handle,q in view["queries"].items():
                metadata=q["metadata"]
                qrows.append({"handle":handle,"query_id":q["query_id"],"station":metadata["station"],
                    "slot_start":metadata["slot_start"],"slot_end":metadata["slot_end"],
                    "available_at":metadata["available_at"],"age_seconds":(view["clock"]-metadata["slot_end"])/1e6,
                    "latency_ms":metadata["latency_ms"],"cost":metadata["archive_cost"],
                    "serves_target_handles":q["serves_target_handles"]})
            costs={canonical_hash(q["cost"]) for q in qrows};ages={q["age_seconds"] for q in qrows}
            raw=original["selection"]["query_order"]; error=original.get("response_error") or original.get("execution_status")
            choice="invalid" if error else "empty" if not raw else "all_original_order" if raw==list(view["queries"]) else "other_valid"
            action_rows.append({"case":item["case"],"call_id":request["call_id"],"request_sha256":digest(path),
                "request_clock":view["clock"],"queries":qrows,"unique_query_ids":len({q["query_id"] for q in qrows}),
                "cost_asymmetry":len(costs)>1,"age_asymmetry":len(ages)>1,
                "topology_degree_asymmetry":len({len(q["serves_target_handles"]) for q in qrows})>1,
                "available_credit":view["available_source_credit"],"reported_choice":choice,
                "unseen_source_payloads_used":False,"source_value_differences_inferred_from_handles":False})
            safe=capture["body"].encode('utf-8')
            sha_ok=not capture["redacted"] and __import__('hashlib').sha256(safe).hexdigest()==capture["original_body_sha256"]
            decoded=json.loads(capture["body"])
            api_rows.append({"case":item["case"],"call_id":request["call_id"],"capture_sha256":digest(capture_path),
                "stored_unredacted_bytes_match_recorded_original_hash":sha_ok,
                "observed_http_status":capture["http_status"],"observed_usage":decoded.get("usage"),
                "observed_finish_reason":decoded["choices"][0]["finish_reason"],
                "observed_body_under_old_limit":len(safe)<4_000_000,
                "original_complete_flag":capture["complete"],
                "capture_dimensions":"observed_unchanged" if sha_ok else "insufficient_evidence",
                "original_raw_eof_proved":"insufficient_evidence; no raw EOF receipt in v1",
                "final_dispatch_permit":"insufficient_evidence; no final permit timestamp in v1",
                "received_before_phase_deadline":capture["received_wall_ns"]<old_policy["deadline_wall_ns"],
                "historical_capture_rewritten":False})
    if len(action_rows)!=288 or len(clock_rows)>24:raise ValueError("Bounded audit scope differs")
    compat=[]
    for i in (1,2):
        folder=OLD/f"api_compatibility_{i:02d}";attempt=bound(folder/"ATTEMPT.json")
        path=folder/("RESPONSE.json" if i==1 else "CAPTURE.json"); value=bound(path)
        compat.append({"case":folder.name,"attempt_sha256":digest(folder/"ATTEMPT.json"),
            "response_or_capture_sha256":digest(path),"classification":"insufficient_evidence",
            "limitation":"parsed response only" if i==1 else "no final permit or raw EOF receipt",
            "new_http_attempts":0})
    publish(RUN/"API_HISTORICAL_IMPACT.json",{"formal_requests":288,"compatibility_requests":2,
        "formal_rows":api_rows,"compatibility_rows":compat,"observed_affected":0,
        "unchanged_observed_body_hashes":sum(r["stored_unredacted_bytes_match_recorded_original_hash"] for r in api_rows),
        "lifecycle_provability_insufficient":290,"all_original_dispatches_proved_timely":False,
        "new_http_attempts":0,"input_hashes":dict(USED)})
    publish(RUN/"ACTION_SPACE_CENSUS.json",{"registered_requests":288,"rows":action_rows,
        "choices":dict(Counter(r["reported_choice"] for r in action_rows)),
        "cost_asymmetric_requests":sum(r["cost_asymmetry"] for r in action_rows),
        "age_asymmetric_requests":sum(r["age_asymmetry"] for r in action_rows),
        "topology_degree_asymmetric_requests":sum(r["topology_degree_asymmetry"] for r in action_rows),
        "interpretation":"Distinct station/source identities do not establish heterogeneous public costs or known predictive value",
        "outcomes_read":False})
    publish(RUN/"CLOCK_INFORMATION_AUDIT.json",{"sample_size":len(clock_rows),"sample_cap":24,
        "selection_uses_y":False,"rows":clock_rows,"statuses":dict(Counter(r["status"] for r in clock_rows)),
        "new_fits":0,"new_forecast_sessions":0,"reconstructed_views_not_training_captures":True,
        "suggested_next_decision":"fixed-bank annual bridge first; any new fit requires a separately registered clock-matched training contract"})
    fit=bound(OLD/"annual_stage_B/fit/REGISTRATION.json")
    publish(RUN/"ROLE_LEDGER.json",{"schema":"disastertrace.v13.roles.v1",
        "fit_interval":fit["fit_interval"],"calibration_interval":fit["calibration_interval"],
        "fit_calibration_scope":"previously fitted annual banks; no new fit",
        "excluded_calendar":fit["excluded_previously_used_calendar"],
        "exposed_development_cases":[x["case"] for x in intent["cases"]],
        "confirmation":{"region":"bay","interval":["2025-02-17","2025-02-23"],"opened":False},
        "raw_metadata_scope":"original288 requests; original24 clock diagnostic targets; no Y-dependent sampling"})
    print(json.dumps({"clock":dict(Counter(r["status"] for r in clock_rows)),
                      "actions":dict(Counter(r["reported_choice"] for r in action_rows)),"api_captures":len(api_rows)+len(compat)}),flush=True)


if __name__ == "__main__":run()
