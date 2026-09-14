"""Freeze native-feature E-to-F and real temperature F-only model pilots."""

import argparse
import datetime as dt
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path

from disastertrace.monitoring_v1.api_ledger import ApiLedger, call_spec
from disastertrace.monitoring_v1.feature_tasks import FEATURE_SYSTEM, TEMPERATURE_SYSTEM, temperature_ensemble_probability
from disastertrace.monitoring_v1.native_feature_forecast import feature_vector, native_claims, predict_features
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    run = root / "plans/v10_execution_20260914_01"
    feature_bank = run / "native_feature_bank_01"
    if not read(feature_bank / "RESULT.json")["passed"]:
        raise ValueError("Frozen feature backend is not qualified")
    registration = {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "aviation": "all84 threshold-free all-registered information units from the previous fixed-packet study; 72ordinary/12Denver diagnostic",
        "temperature": "all targets from Jan1/Apr1/Jul1/Oct1 00UTC issuances in each of2017/2018; complete4day station product",
        "feature_pipeline": "model extracts native visibility/temp/dewpoint; the identical frozen values backend predicts both future thresholds",
        "temperature_pipeline": "F-only real model probabilities; no supplementary observations or temperature C1 claim",
        "new_source_selection_by_outcome": False, "confirmation_opened": False,
        "primary_feature_F": "raw coherent softmax, common-only same backend fallback on invalid output",
        "secondary_feature_F": "fixed-total-prior2 PAV then same-information CDF; reported separately, not chosen by model scores",
        "format": "bare JSON or one whole JSON code fence, uniformly declared before calls; original earlier bare-only results unchanged",
        "invalids": "all original replies and unattempted opportunities retained; no retries",
        "scope": "finite fixed-information mechanism/second-process pilot, not independent confirmation or active joint-budget deployment"}
    publish(out / "SELECTION.json", registration)
    for folder in ("policy", "bundles", "evaluator", "banks", "source", "api"):
        (out / folder).mkdir()
    for mode in ("common", "mask_age", "values"):
        shutil.copyfile(feature_bank / ("BANK_"+mode+".json"), out / "banks" / (mode+".json"))
    bank = read(out / "banks/values.json")
    previous = run / "fixed_packet_01"
    previous_packets = read(previous / "PACKETS.json")
    previous_refs = read(previous / "evaluator/REFERENCES.json")
    paired = defaultdict(dict)
    for pid, row in previous_packets.items():
        if row["condition"] != "all_registered":
            continue
        paired[row["region"], row["cohort"], row["station"], row["cutoff"]][row["threshold"]] = (pid, row)
    tasks, packets, refs = [], {}, {}
    for key, pair in sorted(paired.items()):
        if set(pair) != {1000, 5000}:
            raise ValueError("Both future target thresholds are required")
        pid, meta = pair[1000]
        other_pid, other = pair[5000]
        if meta["information_id"] != other["information_id"]:
            raise ValueError("Threshold pair does not have identical native information")
        view = read(previous / "bundles" / (pid+".json"))["payload"]
        content = view["baseline"]["content"]
        target, candidate = content["legacy_target_contract"], content["native_taf"]
        disclosed = {a["content"]["query_id"]: a["content"] for a in view["assets"]}
        qids, at = meta["query_ids"], meta["cutoff"]-600_000_000
        reference = native_claims(qids, disclosed, at=at)
        features = feature_vector(target, candidate, qids, disclosed, at=at, claims=reference)
        native = predict_features(bank, features)
        fallback = predict_features(bank, feature_vector(target, candidate, qids, {}, at=at))
        cid = canonical_hash(["v10-native-feature", key])[:24]
        payload = {"target_window": {k:target[k] for k in ("entity", "physical_start", "physical_end")},
            "as_of": at, "common_full_taf": None if candidate is None else candidate["raw"],
            "common_forecast_probabilities": {"1000": previous_refs[pid]["FOLLOW"], "5000": previous_refs[other_pid]["FOLLOW"]},
            "read_products": {q:{"query_id":q, "source_status":p["status"], "reports":[
                {k:r[k] for k in ("station", "observation_time", "raw")} for r in p.get("reports", [])]}
                for q,p in disclosed.items()}}
        messages = [{"role": "system", "content": FEATURE_SYSTEM},
                    {"role": "user", "content": json.dumps(payload, sort_keys=True, separators=(",", ":"))}]
        publish(out / "policy" / (cid+".json"), {"call_id":cid, "messages":messages})
        publish(out / "bundles" / (cid+".json"), {"target":target, "candidate":candidate, "disclosed":disclosed,
                "query_ids":qids, "at":at, "original_bundle_sha256":digest(previous / "bundles" / (pid+".json"))})
        metadata = {"call_id":cid, "kind":"aviation_features", "region":meta["region"], "cohort":meta["cohort"],
            "representation":"native_text_only", "reasoning":"typed_measurement_extraction", "read_ids":sorted(disclosed),
            "policy_sha256":digest(out / "policy" / (cid+".json"))}
        refs[cid] = {"claims":reference, "native_probabilities":native, "fallback_probabilities":fallback,
            "future":{str(t):previous_refs[pair[t][0]]["future"] for t in (1000,5000)},
            "original_baseline":payload["common_forecast_probabilities"]}
        tasks.append(metadata)
        packets[cid] = metadata
    if len(tasks) != 84:
        raise ValueError("Registered84 aviation units did not reconstruct")
    temperature_count = 0
    old = root / "plans/v9_followup_execution_20260914_01/temperature_fullcalendar_01"
    original_files = {str(previous / "PACKETS.json"):digest(previous / "PACKETS.json"),
        str(feature_bank / "BANK_FREEZE_BEFORE_EVALUATION.json"):digest(feature_bank / "BANK_FREEZE_BEFORE_EVALUATION.json")}
    for year in (2017,2018):
        for month in (1,4,7,10):
            case = old / f"{year}-{month:02d}"
            policy = read(case / "POLICY.json")
            outcomes = {r["opportunity_id"]:r for r in read(case / "OUTCOMES.json")}
            origin = int(dt.datetime(year,month,1,tzinfo=dt.timezone.utc).timestamp()*1_000_000)
            chosen = [r for r in policy["rows"] if r["origin"] == origin]
            if len(chosen) != 16:
                raise ValueError("All16 native temperature targets per issuance required")
            for row in chosen:
                p = temperature_ensemble_probability(row)
                if not math.isclose(p,row["probability"],abs_tol=1e-12,rel_tol=0):
                    raise ValueError("Independent same-member probability differs from original baseline")
                cid = canonical_hash(["v10-temperature-F", row["opportunity_id"]])[:24]
                payload = {"target":row["target"], "cutoff":row["cutoff"], "current_complete_product":row["common"],
                    "professional_source_research_baseline":p,
                    "availability_contract":"archive scenario: full issuance available3h after origin; cutoff4h after origin",
                    "baseline_qualification":"raw51-member fraction; no strong calibrated temperature postprocessor yet"}
                publish(out / "policy" / (cid+".json"), {"call_id":cid,"messages":[
                    {"role":"system","content":TEMPERATURE_SYSTEM},
                    {"role":"user","content":json.dumps(payload,sort_keys=True,separators=(",",":"))}]})
                publish(out / "bundles" / (cid+".json"), row)
                meta = {"call_id":cid,"kind":"temperature_F","cohort":"seasonal_development",
                    "origin":origin,"event":row["event"],"opportunity_id":row["opportunity_id"],
                    "representation":"complete_station_ensemble","reasoning":"F_only",
                    "policy_sha256":digest(out / "policy" / (cid+".json"))}
                tasks.append(meta)
                packets[cid] = meta
                refs[cid] = {"future":outcomes[row["opportunity_id"]],"FOLLOW":p,
                             "native_same_member_recomputed":True}
                temperature_count += 1
            for name in ("POLICY.json","OUTCOMES.json"):
                original_files[str(case/name)] = digest(case/name)
    publish(out / "PACKETS.json", packets)
    publish(out / "evaluator/REFERENCES.json", refs)
    publish(out / "INPUTS.json", original_files)
    for module in ("monitoring_v1","monitoring_fixed_v1","forecast_task"):
        shutil.copytree(root / "disastertrace-starter/src/disastertrace" / module, out / "source/disastertrace" / module,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (out / "source/disastertrace/__init__.py").write_text('"""Frozen feature/temperature model trial."""\n')
    for name in ("prepare_feature_temperature_trial.py","run_fixed_packet_api.py","qwen38_worker_v10.py", "score_feature_temperature.py"):
        shutil.copyfile(Path(__file__).parent / name, out / "source" / name)
    shutil.copyfile(previous / "source/PRICING.html", out / "source/PRICING.html")
    models = ["deepseek-flash","deepseek-v4-pro"]
    smoke = [{"role":"user","content":'Return only the JSON object {"ready":true}.'}]
    publish(out / "api/COMPATIBILITY_REQUEST.json", smoke)
    calls = []
    for model in models:
        calls.append(call_spec(model+"/compatibility",smoke,model,max_tokens=1024))
        for task in tasks:
            calls.append(call_spec(model+"/"+task["call_id"],read(out / "policy" / (task["call_id"]+".json"))["messages"],model,max_tokens=1024))
    deadline = dt.datetime(2026,9,14,23,30,tzinfo=dt.timezone.utc)
    ledger = ApiLedger.create(out / "api/ledger",calls,limit_nanodollars=20_000_000_000,
                             max_calls=len(calls),deadline_wall_ns=int(deadline.timestamp()*1e9))
    frozen = {str(p.relative_to(out)):digest(p) for folder in ("policy","bundles","evaluator","banks","source")
              for p in (out / folder).rglob("*") if p.is_file()}
    for name in ("SELECTION.json","INPUTS.json","PACKETS.json","api/COMPATIBILITY_REQUEST.json","api/ledger/contract.json"):
        frozen[name] = digest(out / name)
    plan = {"schema":"disastertrace.feature_temperature_trial.v1","tasks":tasks,"files":frozen,
        "api_models":models,"api_workers":16,"max_tokens":1024,"input_token_cap":32768,
        "api_benchmark_calls":len(tasks)*2,"api_compatibility_calls":2,"api_limit_usd":20,
        "api_escrow_upper_nanodollars":sum(c["reserved_nanodollars"] for c in calls),
        "local_benchmark_calls":len(tasks),"local_compatibility_calls":4,
        "gpu_worker_source":"source/qwen38_worker_v10.py","last_worker_time":deadline.isoformat(),
        "late_start_cutoff":"2026-09-14T22:30:00+00:00","scope":registration["scope"],
        "aviation_information_units":84,"temperature_information_units":temperature_count,
        "warm_local_latency":"prompt preparation through durable response; not an adaptive source/selector lifecycle",
        "scorer_source":"source/score_feature_temperature.py",
        "scorer_preflight_required":"scorer_preflight/RESULT.json",
        "scoring": {"aviation_primary":"values_model_raw compared with values_native_raw and values_validmask_raw",
                    "aviation_secondary":"fixed-prior PAV plus coherent CDF; all three pretrained families reported",
                    "extraction":"literal and semantic exact; numeric abs tolerance1e-6 is secondary; infinity closure is irrelevant",
                    "temperature":"raw model_F versus same-member FOLLOW; preserve invalids and all registered targets",
                    "invalid_or_late":"all registered rows retained; >600s or non-EOS output falls back",
                    "native_values_at_model_missing_mask":"posthoc perception diagnostic only"},
        "confirmation_opened":False,"retries":0}
    publish(out / "PLAN.json",plan)
    publish(out / "PREFLIGHT.json",{"passed":True,"ledger_sha256":ledger.contract_sha256,
        "plan_sha256":digest(out / "PLAN.json"),"native_claims_verified":84,"temperature_same_member_probabilities_verified":temperature_count,
        "source_features_and_bank_frozen":True})
    print({"aviation_units":84,"temperature_units":temperature_count,"total_per_model":len(tasks),
           "api_reserved_usd":plan["api_escrow_upper_nanodollars"]/1e9},flush=True)


if __name__ == "__main__":
    main()
