"""Freeze one query-only model against the already registered B02 roster."""

import copy
import datetime as dt
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from model_run import B02, PRIOR, REPO, RUN, MODEL, ARM, backend, now, verify
from disastertrace.monitoring_v1.comparison_fingerprint import compare, fingerprint
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.formal_session import required_source_files
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

import sys
sys.path.insert(0,str(PRIOR))
from b00 import contract


def main():
    xml=RUN/"OFFLINE_TESTS_01.xml"
    cases=ET.parse(xml).getroot().findall(".//testcase")
    if len(cases)!=14 or any(c.find(k) is not None for c in cases for k in ("failure","error","skipped")):
        raise ValueError("M01 runner qualification not complete")
    breg=read(B02/"REGISTRATION.json")
    verify(breg["source_files"] | breg["runner_files"] | breg["input_files"])
    if not {str(p) for p in required_source_files()}<=set(breg["source_files"]):
        raise ValueError("M01 imported a package outside the qualified frozen source")
    source=dict(breg["source_files"])
    roster=read(B02/"PROGRAM_ROSTER.json")["selected"]
    assert len(roster)==len({r["case"] for r in roster})==12
    inputs=[B02/"REGISTRATION.json",B02/"PROGRAM_ROSTER.json",B02/"regression/RESULT.json",B02/"COMPATIBILITY.json",
        PRIOR/"M00/RESULT.json",PRIOR/"M00/INDEPENDENT_AUDIT.json",RUN/"model_run.py",RUN/"prepare.py",
        RUN/"test_model_run.py",RUN/"CONSUMER_PREFLIGHT.json",xml]
    files={**source,**{str(p):digest(p) for p in inputs},**breg["runner_files"]}
    for row in breg["cases"]:files.update(row["original_files"])
    publish(RUN/"OFFLINE_RESULT.json",{"passed":True,"at":now(),"new_runner_tests":14,
        "source_qualification":{"same_frozen_package":True,"prior_regression_tests":912,
                                "regression_result_sha256":digest(B02/"regression/RESULT.json")},
        "mocked_HTTP_only":True,"real_HTTP_attempts":0,"checks":["negative gain remains eligible",
        "failed/incomplete gates prevent dispatch","two production ticks","invalid and unknown outcomes retain denominator",
        "durable capture tampering rejected","existing72program probabilities and actual paid bundles reproduce"],
        "files":{str(p):digest(p) for p in (RUN/"model_run.py",RUN/"test_model_run.py",xml,RUN/"CONSUMER_PREFLIGHT.json")}})
    files[str(RUN/"OFFLINE_RESULT.json")]=digest(RUN/"OFFLINE_RESULT.json")
    launch_deadline=int(dt.datetime(2026,9,16,20,tzinfo=dt.timezone.utc).timestamp()*1e9)
    http_deadline=int(dt.datetime(2026,9,16,23,tzinfo=dt.timezone.utc).timestamp()*1e9)
    publish(RUN/"AUTHORIZATION.json",{"at":now(),"basis":"user approved sequential followup execution on2026-09-16; prior resource and SiliconFlow permission persists",
        "model":MODEL,"role":"query_only_selector; fixed program F","daily_sessions_max":12,
        "requests_per_session_max":24,"requests_max":288,"automatic_retries":0,"scope":"M01 after actual technical gates",
        "M00_scope":"previous12requests already consumed; no new interface probe",
        "new_weather_HTTP":0,"new_fits":0,"confirmation_payload_reads":0,"automatic_git_push":False,
        "credential":"existing private external SiliconFlow credential; never copied into artifacts"})
    files[str(RUN/"AUTHORIZATION.json")]=digest(RUN/"AUTHORIZATION.json")
    publish(RUN/"REGISTRATION.json",{"at":now(),"cases":roster,"model":MODEL,"model_role":"query_only_selector",
        "files":files,"requests_max":288,"requests_per_session_max":24,"automatic_retries":0,
        "registered_opportunities":864,"program_reference_methods":breg["reuse_arms"]+breg["arms"],
        "roster_source":"exact B02metadata/hash-selected12days, no score-based substitution",
        "launch_deadline_wall_ns":launch_deadline,"HTTP_deadline_wall_ns":http_deadline,
        "controller_steps_max":60,"workers_max":4,"input_cap_per_call":32768,"output_cap_per_call":512,
        "total_reserved_token_ceiling":288*(32768+512),"currency_cap":"none specified by user; usage and unknown reservations reported",
        "positive_program_gain_required":False,"non_equivalent_path_witness_required":True,
        "full_day_model_forecast_sessions":True,"model_authored_probabilities":False,
        "confirmation_opened":False,"new_fits":0,"source_package_byte_identical_to_B02":True})
    (RUN/"authority").mkdir()
    publish(RUN/"MODEL_CONTRACT.json",{"model":MODEL,
        "weights":{"provider_managed":True,"checkpoint_revision_not_exposed":True},
        "tokenizer":{"provider_managed":True,"usage_source":"provider capture"},
        "adapter":{"version":"receipt_bound_api.v2","runner_sha256":digest(RUN/"model_run.py")},
        "generation":{"temperature":0,"max_tokens":512,"enable_thinking":False,"stream":False},
        "runtime":{"kind":"single_node_committed_production_spool","automatic_retries":0},
        "api_transport_v2":{"version":"receipt_bound_api.v2","model":MODEL,"base_url":"https://api.siliconflow.cn/v1",
            "input_cap":32768,"output_cap":512,"read_limit_bytes":1048576,"deadline_wall_ns":http_deadline,
            "authority_directory":str(RUN/"authority"),"stop_path":str(RUN/"API_STOP.json"),
            "dispatch_authority":"single_local_authority","allowed_call_ids":["select-"+str(i) for i in range(24)]}})
    (RUN/"cases").mkdir()
    consumer_sha=read(B02/"COMPATIBILITY.json")["prediction_consumer_sha256"]
    for row in roster:
        folder=RUN/"cases"/row["case"];folder.mkdir();(folder/"spool").mkdir();(folder/"checkpoints").mkdir()
        origin=PRIOR/"B00"/row["case"]
        data,bank=read(origin/"DATA.json"),read(origin/"BANK.json")
        # Source identity is shared; every case still has its own managed run ID.
        binding={**files,**{str(RUN/n):digest(RUN/n) for n in ("REGISTRATION.json","MODEL_CONTRACT.json")}}
        publish(folder/"BACKEND_FILES.json",binding)
        old=read(origin/"CONFIGS.json")["B11_COVERAGE"];cfg=copy.deepcopy(old);cfg.pop("execution_contract",None)
        cfg.update(selector_kind="llm",selector_contract_version="selector_query_only.v2",model_call_budget=24)
        cfg=bind_execution(cfg,backend(folder))
        publish(folder/"CONFIG.json",cfg)
        publish(folder/"COMPARISON.json",contract({ARM:cfg},data,bank).export())
        prints=[fingerprint(c,baseline_bank=bank,consumer_code_sha256=consumer_sha,
                            source_contract_sha256=canonical_hash(data)) for c in (old,cfg)]
        factors=compare(*prints)
        if not factors["same_predictor"] or not factors["same_schedule"]:raise ValueError("Model role changed predictor or planned slots")
        publish(folder/"FACTORS.json",{"vs_B11_COVERAGE":factors,"fingerprints":prints,
            "separate_comparison_contracts":"Original program journals retain their contracts; model uses its own query-only execution contract and is paired only after formal scoring",
            "selector_schema_changed":True,"actual_HTTP_elapsed_time_is_charged":True,
            "late_program_slots_may_be_skipped_and_remain_in_denominator":True})
    paths=[RUN/"REGISTRATION.json",RUN/"MODEL_CONTRACT.json",RUN/"AUTHORIZATION.json",RUN/"OFFLINE_RESULT.json"]
    paths.extend(p for folder in (RUN/"cases").iterdir() for p in folder.glob("*.json"))
    publish(RUN/"FREEZE.json",{"at":now(),"files":{str(p):digest(p) for p in paths},"model_requests_before_freeze":0})
    print(json.dumps({"days":12,"opportunities":864,"API_requests_max":288,"new_HTTP":0,
                      "launch_deadline_UTC":"2026-09-16T20:00:00Z","HTTP_deadline_UTC":"2026-09-16T23:00:00Z"}),flush=True)


if __name__=="__main__":main()
