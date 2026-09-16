"""Freeze program roster, configs, source and one combined affected regression."""

import copy
import json
import shutil
from pathlib import Path

from compatibility import audit_source
from program import ARMS, OLD_ARMS, OUT, PREV, REPO, RUN, contract, now
from disastertrace.monitoring_v1.comparison_fingerprint import compare, fingerprint
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def main():
    starter=REPO/"disastertrace-starter"
    roster=read(RUN/"PROGRAM_ROSTER.json")
    oldreg=read(PREV/"B00/REGISTRATION.json")
    if digest(PREV/"B00/REGISTRATION.json")!=roster["input_registration_sha256"]:
        raise ValueError("B00 registration changed after metadata selection")
    shutil.copytree(starter/"src/disastertrace",RUN/"source/disastertrace",
                    ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    audit=audit_source(PREV/"source/disastertrace",RUN/"source/disastertrace")
    publish(RUN/"SOURCE_AUDIT.json",audit)
    source={str(p):digest(p) for p in (RUN/"source").rglob("*.py")}
    cases=[];tasks=[]
    OUT.mkdir()
    for i,row in enumerate(roster["selected"]):
        original=PREV/"B00"/row["case"];case=OUT/row["case"];case.mkdir()
        parent=next(r for r in oldreg["cases"] if r["case"]==row["case"])
        oldcfg=read(original/"CONFIGS.json");data=read(original/"DATA.json");bank=read(original/"BANK.json")
        configs={}
        for arm in ARMS:
            c=copy.deepcopy(oldcfg["B11_COVERAGE"])
            if arm in ARMS[:3]:c["selector_kind"]={ARMS[0]:"round_robin_cycle.v1",ARMS[1]:"public_risk_age.v1",ARMS[2]:"fixed_hash.v1"}[arm]
            else:
                c["allocation_mode"]="fixed_quota" if arm in ("B00_COVERAGE","B01_COVERAGE") else "global_budget"
                c["authorization_mode"]="session_shared" if arm=="B01_COVERAGE" else "target_private"
            c.pop("execution_contract",None)
            configs[arm]=bind_execution(c,None)
        publish(case/"CONFIGS.json",configs)
        publish(case/"COMPARISON.json",contract(configs,data,bank).export())
        prints={a:fingerprint(c,baseline_bank=bank,consumer_code_sha256=audit["prediction_consumer_sha256"],
                              source_contract_sha256=canonical_hash(data)) for a,c in (oldcfg|configs).items()}
        factors={a:compare(prints["B11_COVERAGE"],prints[a]) for a in ARMS}
        if not all(v["same_predictor"] and v["same_schedule"] for v in factors.values()):
            raise ValueError("New program factor changes predictor or slots")
        publish(case/"FACTORS.json",{"fingerprints":prints,"comparisons_to_B11_COVERAGE":factors,
            "consumer_binding":audit,"source_packages_byte_identical":False})
        files={str(p):digest(p) for p in case.glob("*.json")}
        cases.append({**row,"original_files":parent["files"],"files":files|parent["files"]})
        tasks.extend({"case":row["case"],"arm":a,"shard":i%2} for a in ARMS)
    prior=read(REPO/"plans/v13_execution_20260916_01/regression_02/REGISTRATION.json")
    prior_result=read(REPO/"plans/v13_execution_20260916_01/regression_02/RESULT.json")
    modules=sorted(set(prior["modules"])|{str(starter/"tests/test_monitoring_public_query_selectors.py"),str(RUN/"test_gates.py")})
    regression=RUN/"regression";regression.mkdir()
    for name in ("logs","xml","temp"):(regression/name).mkdir()
    expected=sorted({c["node_id"] for r in prior_result["results"] for c in r["cases"]})
    tests={str(p):digest(p) for p in (starter/"tests").glob("*.py")}
    tests.update({n:digest(Path(n)) for n in modules})
    publish(regression/"REGISTRATION.json",{"modules":modules,"historical_expected_nodes":expected,
        "source_hashes":source,"test_hashes":tests,"workers":8,"per_module_timeout_seconds":900,
        "python":str(starter/".venv/bin/python"),"prepared_at":now(),
        "scope":"previous880 unique affected tests plus new public selectors and gates; no skip is a pass"})
    scripts=["program.py","compatibility.py","prepare.py","regression.py","test_gates.py"]
    runner={str(RUN/n):digest(RUN/n) for n in scripts}
    runner.update({str(PREV/n):digest(PREV/n) for n in ("b00.py","finalize.py")})
    inputs=[RUN/"PROGRAM_ROSTER.json",RUN/"BANK_DECISION_PROPOSAL.json",RUN/"AUTHORIZATION.json",
            RUN/"SOURCE_AUDIT.json",PREV/"B00/REGISTRATION.json",regression/"REGISTRATION.json"]
    publish(RUN/"REGISTRATION.json",{"at":now(),"cases":cases,"tasks":tasks,"arms":ARMS,"reuse_arms":OLD_ARMS,
        "source_files":source,"runner_files":runner,"input_files":{str(p):digest(p) for p in inputs},
        "deadline_utc":"2026-09-16T23:30:00+00:00","python":str(starter/".venv/bin/python"),
        "method_days_max":72,"model_calls":0,"weather_HTTP":0,"new_fits":0,"automatic_retries":0,
        "shards":2,"max_workers_per_shard":12,"registered_days":12,"registered_opportunities":864,
        "new_method_rows":5184,"reused_method_rows":4320,"total_method_rows":9504,
        "gate":"complete B00, regression, legacy compatibility, original formal reuse, explicit bank decision and public census"})
    print(json.dumps({"prepared":len(cases),"tasks":len(tasks),"regression_modules":len(modules),
                      "previous_expected_tests":len(expected),"source_files":len(source)}),flush=True)


if __name__=="__main__":main()
