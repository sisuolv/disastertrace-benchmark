"""Freeze a chronological EMOS/ECC control on the existing native temperature bank."""

import argparse
import datetime as dt
import json
import math
import shutil
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.temperature_postprocess import ecc_products, event_probability


def timestamp(day):
    return int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp()*1_000_000)


def role(row):
    target=row["target"]
    if row["origin"]>=timestamp("2017-01-01") and target["physical_end"]<=timestamp("2018-01-01"):
        return "fit_2017"
    if (row["origin"]>=timestamp("2018-01-04") and target["physical_start"]>=timestamp("2018-01-08")
            and target["physical_end"]<=timestamp("2019-01-01")):
        return "development_2018"
    return "retained_outside_chronological_comparison"


def fit(records):
    repeats=Counter(r["date"] for r in records)
    means=np.array([statistics.fmean(r["members"]) for r in records])
    variances=np.array([statistics.pvariance(r["members"]) for r in records])
    y=np.array([r["observed"] for r in records])
    weights=np.array([1/repeats[r["date"]] for r in records])

    def objective(theta):
        a,b,log_c,log_d=theta
        c,d=np.exp(log_c),np.exp(log_d)
        variance=c+d*variances
        error=y-a-b*means
        loss=.5*np.sum(weights*(np.log(variance)+error**2/variance))/weights.sum()
        derivative=.5*(1/variance-error**2/variance**2)
        gradient=np.array([-np.sum(weights*error/variance),-np.sum(weights*error*means/variance),
            np.sum(weights*derivative*c),np.sum(weights*derivative*d*variances)])/weights.sum()
        return loss,gradient

    result=minimize(objective,[0,1,0,0],jac=True,method="L-BFGS-B",
        bounds=[(None,None),(0,None),(-12,12),(-12,12)],options={"maxiter":1000,"ftol":1e-12,"gtol":1e-7})
    if not result.success:
        raise ValueError("Declared EMOS optimizer failed: "+str(result.message))
    return {**dict(zip(("a","b","log_c","log_d"),map(float,result.x),strict=True)),
        "fit_forecasts":len(records),"distinct_observed_days":len(repeats),"weighted_days":float(weights.sum()),
        "objective":float(result.fun),"iterations":int(result.nit),"gradient":list(map(float,result.jac))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    out=args.out.absolute()
    out.mkdir(exist_ok=False)
    root=Path(__file__).resolve().parents[3]
    original=root/"plans/v9_followup_execution_20260914_01/temperature_fullcalendar_01"
    publish(out/"SPEC.json",{"at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "fit":"2017 physical outcomes, origins2017 or later; one total weight per observed day in each variable",
        "evaluation":"2018 target starts Jan8 onward, origins Jan4 onward, physical support within2018",
        "primary":"Gaussian EMOS with mean=a+b*ensemble_mean, variance=exp(c)+exp(d)*ensemble_variance",
        "coupling":"51 quantiles ranked by original member across all days; equal-weight min/max projection for violating members",
        "endpoints":"original Celsius ge/lt UTC-day and same-member3day definitions unchanged",
        "baseline":"raw51 plus past-year event climatology with Beta(.5,.5)",
        "optimizer":"fixed L-BFGS-B likelihood; b>=0, log-variance bounds[-12,12], no test tuning",
        "scope":"chronological exposed development at one station; not independent confirmation or temperature C1",
        "joint_calibration_guarantee":False,"availability":"unchanged declared3h publication/4h cutoff archive scenario",
        "supplementary_queries":0,"model_calls":0,"confirmation_opened":False})
    rows=[]
    bindings={}
    for case in sorted(original.glob("20??-??")):
        policies=read(case/"POLICY.json")["rows"]
        outcomes={r["opportunity_id"]:r for r in read(case/"OUTCOMES.json")}
        for filename in ("POLICY.json","OUTCOMES.json"):
            bindings[str(case/filename)]=digest(case/filename)
        for row in policies:
            rows.append({"policy":row,"outcome":outcomes[row["opportunity_id"]],"role":role(row)})
    if len(rows)!=11644 or len({r["policy"]["opportunity_id"] for r in rows})!=11644:
        raise ValueError("Original11644 opportunity registry changed")
    training={"min":{},"max":{}}
    binary={}
    for item in rows:
        if item["role"]!="fit_2017" or item["outcome"]["status"]!="mature" or item["outcome"]["value"] is None:
            continue
        row,outcome=item["policy"],item["outcome"]
        binary[row["target"]["target_id"]]=(row["event"],outcome["value"])
        daily={p["target_date"]:p for p in row["common"]["daily_products"]}
        variable="min" if row["target"]["variable"]=="daily_min_2m_temperature" else "max"
        native_field="TNK" if variable=="min" else "TXK"
        field="forecast_"+variable+"_members_C"
        for ref in outcome["references"]:
            date=ref["date"]
            record={"date":date,"origin":row["origin"],"members":daily[date][field],
                    "observed":ref["values_C"][native_field],"reference_row_sha256":ref["row_sha256"]}
            key=(row["origin"],date)
            if key in training[variable] and training[variable][key]!=record:
                raise ValueError("One native daily forecast/observation has conflicting representations")
            training[variable][key]=record
    publish(out/"ROLE_REGISTRY.json",[{"opportunity_id":r["policy"]["opportunity_id"],"role":r["role"],
        "target_id":r["policy"]["target"]["target_id"],"missing_outcome":r["outcome"]["value"] is None} for r in rows])
    publish(out/"TRAINING_RECORDS.json",{k:list(v.values()) for k,v in training.items()})
    parameters={key:fit(list(values.values())) for key,values in training.items()}
    event_values=defaultdict(list)
    for event,value in binary.values():
        event_values[event].append(value)
    climatology={event:{"n":len(values),"positives":sum(values),"probability":(sum(values)+.5)/(len(values)+1)}
                 for event,values in event_values.items()}
    bank={"mapping_version":"emos_ecc51_minmax_projection.v1",**parameters,"climatology":climatology}
    publish(out/"BANK.json",bank)
    (out/"source").mkdir()
    for package in ("monitoring_v1","monitoring_fixed_v1","forecast_task"):
        shutil.copytree(root/"disastertrace-starter/src/disastertrace"/package,out/"source/disastertrace"/package,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (out/"source/disastertrace/__init__.py").write_text('"""Frozen native temperature postprocessing."""\n')
    shutil.copyfile(__file__,out/"source/fit_temperature_postprocess.py")
    publish(out/"FREEZE_BEFORE_EVALUATION.json",{"at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "input_files":bindings,"bank_sha256":digest(out/"BANK.json"),
        "source_files":{str(p.relative_to(out)):digest(p) for p in (out/"source").rglob("*.py")},
        "registration_sha256":digest(out/"SPEC.json"),"roles_sha256":digest(out/"ROLE_REGISTRY.json")})
    cache={}
    scored=[]
    metrics=defaultdict(lambda:{"registered":0,"scored":0,"positive":0,"losses":[]})
    for item in rows:
        row,outcome=item["policy"],item["outcome"]
        native=event_probability(row)
        if not math.isclose(native,row["probability"],abs_tol=1e-12,rel_tol=0):
            raise ValueError("Independent member probability disagrees with original")
        if item["role"]!="development_2018":
            continue
        origin=row["origin"]
        if origin not in cache:
            cache[origin]=ecc_products(row["common"]["daily_products"],bank)
        products,trace=cache[origin]
        probabilities={"raw51":native,"emos_ecc51":event_probability(row,products=products),
                       "past_year_climatology":climatology[row["event"]]["probability"]}
        record={"opportunity_id":row["opportunity_id"],"target_id":row["target"]["target_id"],
            "origin":origin,"target_start":row["target"]["physical_start"],"event":row["event"],
            "outcome":outcome["value"],"outcome_status":outcome["status"],"probabilities":probabilities,
            "projection_count_in_full_issuance":trace["minmax_projections"]}
        scored.append(record)
        for method,p in probabilities.items():
            m=metrics[row["event"]+"__"+method]
            m["registered"]+=1
            if outcome["value"] is not None and outcome["status"]=="mature":
                m["scored"]+=1
                m["positive"]+=outcome["value"]
                m["losses"].append((p-outcome["value"])**2)
    for value in metrics.values():
        value["loss_sum"]=math.fsum(value.pop("losses"))
        value["brier"]=value["loss_sum"]/value["scored"] if value["scored"] else None
    with (out/"EVALUATION_ROWS.jsonl").open("x") as handle:
        for row in scored:
            handle.write(json.dumps(row,sort_keys=True,allow_nan=False)+"\n")
    publish(out/"RESULT.json",{"passed":True,"original_opportunities_retained":len(rows),
        "role_counts":dict(Counter(r["role"] for r in rows)),"development_forecasts":len(scored),
        "development_distinct_targets":len({r["target_id"] for r in scored}),"metrics":dict(metrics),
        "development_issuances":len(cache),"minmax_projection_member_days":sum(t["minmax_projections"] for _,t in cache.values()),
        "member_days":sum(t["member_day_pairs"] for _,t in cache.values()),"model_calls":0,"supplementary_queries":0,
        "threshold_or_hyperparameters_selected_on_test":False,"confirmation_opened":False})
    print({"original":len(rows),"evaluation":len(scored),"issuances":len(cache)},flush=True)


if __name__=="__main__":
    main()
