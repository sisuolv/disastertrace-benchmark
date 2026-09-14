"""Continuous native daily-extrema version streams, with automatic COPY controls."""

import argparse
from collections import Counter, defaultdict
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, AdmissionEvent, TypedOpportunity, score_admitted
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, Forecast, Target, canonical, fingerprint
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, OutcomeRegistry
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

ROOT = Path(os.environ.get("DISASTERTRACE_FOLLOWUP_ROOT", Path(__file__).resolve().parents[1]))
REPO = ROOT.parents[1]
V8 = ROOT.parent / "v8_measurement_execution_20260913_01"
V9 = ROOT.parent / "v9_integration_execution_20260914_01"
OUT = ROOT / "temperature_fullcalendar_01"
ARMS = ["follow", "copy_latest", "copy_current", "first_issue_hold"]
PROTOCOLS = ["base_bound_override", "persistent_override"]
HOUR = 3_600_000_000


def us(value):
    return round(dt.datetime.fromisoformat(value).timestamp() * 1_000_000)


def window_for(date):
    value = dt.date.fromisoformat(date)
    return value.strftime("%Y-%m") if value.year in [2017, 2018]  else None


def bundle(row, protocol, state=None):
    target = Target(**row["target"])
    forecast = Forecast(target.contract_hash, "event_probability", "probability", row["probability"])
    return EvidenceBundle.freeze({
        "schema": "disastertrace.frozen_evidence.v1", "opportunity_id": row["opportunity_id"],
        "target": target.to_dict(), "cutoff": row["cutoff"],
        "baseline": {"forecast": forecast.to_dict(), "source_revision": row["source_revision"],
                     "issued_at": row["origin"], "available_at": row["origin"] + 3 * HOUR,
                     "valid_until": target.physical_start, "kind": "research",
                     "mapping_version": "raw51_native_extrema_fraction.v1", "content": row["common"]},
        "state": state or {"forecast": forecast.to_dict(), "mode": "FOLLOW", "protocol": protocol},
        "assets": [], "receipts": [], "authorization_mode": "session_shared",
        "representation": "full_station_daily_extrema_product",
        "availability_basis": "declared_archive_scenario", "provider_version": "eupp_extrema_stream.v1",
    })


def run_case(case, arm, protocol):
    folder = case / (arm + "__" + protocol)
    folder.mkdir(exist_ok=False)
    publish(folder / "CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat()})
    for path, sha in read(OUT / "FREEZE.json")["files"].items():
        assert digest(Path(path)) == sha
    data = read(case / "POLICY.json")
    rows = data["rows"]
    opportunities = [TypedOpportunity(r["opportunity_id"], Target(**r["target"]), r["cutoff"]) for r in rows]
    targets = {o.target.target_id: o.target for o in opportunities}
    invariant = {"case_data_sha256": digest(case / "POLICY.json"), "full_station_product": True,
                 "supplementary_queries": 0, "clock": "declared3h_release_4h_cutoff_1ms_compute_1ms_persist"}
    engine = AdmissionEngine(opportunities, protocol=protocol,
        fallbacks={tid: Forecast(t.contract_hash, "event_probability", "probability", 0.5).to_dict() for tid,t in targets.items()},
        experiment={"invariants": invariant, "interventions": {"arm": arm, "protocol": protocol}})
    by_origin = defaultdict(list)
    for row in rows:
        by_origin[row["origin"]].append(row)
    seen = set()
    decisions = []
    for origin, active in sorted(by_origin.items()):
        cutoff = origin + 4 * HOUR
        baseline_events = [AdmissionEvent("base:" + r["opportunity_id"], origin + 3*HOUR,
                          "baseline", {"bundle": bundle(r, protocol).to_dict()}) for r in active]
        dispatch = cutoff - 60_000_000
        engine.run(baseline_events, until=dispatch-1)
        events = []
        for row in active:
            tid, oid = row["target"]["target_id"], row["opportunity_id"]
            if arm == "follow" or (arm == "first_issue_hold" and tid in seen):
                continue
            state = engine.states[tid]
            current = state.effective(dispatch)
            frozen = bundle(row, protocol, {"forecast": current.to_dict(),
                "mode": "FOLLOW" if state.override is None else "OVERRIDE", "protocol": protocol})
            proposed = current if arm == "copy_current" else Forecast(Target(**row["target"]).contract_hash,
                               "event_probability", "probability", row["probability"])
            raw = canonical(proposed.to_dict())
            cid = "copy:" + oid
            events += [AdmissionEvent("begin:" + oid, dispatch, "begin", {"call_id": cid,
                "bundle": frozen.to_dict(), "head": "program", "executor": arm}),
                AdmissionEvent("complete:" + oid, dispatch+2000, "completion", {"call_id": cid,
                    "bundle_hash": frozen.bundle_hash, "raw": raw, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "started_at": dispatch, "completed_at": dispatch+1000, "persisted_at": dispatch+2000,
                    "expires_at": row["target"]["physical_start"]-1,
                    "cost": {"requests": 0, "bytes": len(raw.encode()), "tokens": 0, "compute_ms": 1},
                    "ended_with_eos": True, "head": "program", "executor": arm})]
            decisions.append({"opportunity_id": oid, "proposed_probability": proposed.value,
                              "current_probability": current.value, "latest_probability": row["probability"]})
            seen.add(tid)
        engine.run(events, until=cutoff)
    assert len(engine.snapshots) == len(rows)
    assert all(a["status"] == "accepted" for a in engine.attempts)
    exported = engine.export()
    assert AdmissionEngine.restore(exported).export() == exported
    engine.write_journal(folder / "admission.jsonl")
    publish(folder / "SNAPSHOTS.json", engine.snapshots)
    publish(folder / "DECISIONS.json", decisions)
    publish(folder / "COMPLETE.json", {"snapshots": len(rows), "targets": len(targets),
        "program_calls": len(decisions), "model_calls": 0, "source_queries": 0,
        "continuous_version_updates": len(by_origin), "exact_replay": True,
        "invariants": invariant, "statuses": dict(Counter(a["status"] for a in engine.attempts))})


def prepare():
    OUT.mkdir(exist_ok=False)
    audit_path = V8 / "temperature_daily_forecast_01/independent_audit_01/VALIDATION.json"
    audit = read(audit_path)
    assert audit["passed"]
    analysis = V8 / "temperature_daily_forecast_01/analysis_01"
    for name, sha in audit["analysis_files"].items():
        assert digest(analysis/name) == sha
    for module in ["monitoring_v1", "monitoring_fixed_v1"]:
        shutil.copytree(REPO/"disastertrace-starter/src/disastertrace"/module, OUT/"source/disastertrace"/module,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (OUT/"source/disastertrace/__init__.py").write_text('"""Frozen temperature version replay."""\n')
    shutil.copyfile(Path(__file__), OUT/"source/run_temperature_stream.py")
    publish(OUT/"PREREGISTRATION.json", {"windows": "target start dates all calendar months in 2017 and 2018; all archived prior issuances",
        "selection": "calendar-only, without outcome or model-performance selection", "arms": ARMS, "protocols": PROTOCOLS,
        "future_support": "full00-24UTC days; day0 excluded; 3day products use same-member joint predicates",
        "baseline": "uncalibrated51member professional-source research projection; complete station4day daily extrema product free",
        "costs": "declared1ms program +1ms persistence; queries0 and modelcalls0", "forecast_gap": "F program stream only; no C1/supplementary or model-gain claim",
        "confirmation_opened": False, "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    daily, durations = read(analysis/"DAILY_FORECASTS.json"), read(analysis/"DURATION_FORECASTS.json")
    common = defaultdict(list)
    for r in daily:
        common[r["initialization"]].append({k:r[k] for k in ["target_date", "day_index", "forecast_max_members_C", "forecast_min_members_C", "probabilities"]})
    target_path = V9/"reports/outcome_policy_01/DWD_TARGETS.json"
    registry_path = V9/"reports/outcome_policy_01/DWD_REGISTRY.json"
    targets = {r["target_id"]: Target(**r) for r in read(target_path)}
    registry = OutcomeRegistry(targets.values())
    for r in read(registry_path)["payload"]["records"]:
        registry.register(r)
    windows = defaultdict(list)

    def add(r, event, date, probability):
        window = window_for(date)
        if window is None:
            return
        target = targets["DWD460-" + date + "-" + event]
        origin = us(r["initialization"])
        oid = target.target_id + "-init-" + r["initialization"]
        cutoff = origin + 4 * HOUR
        target.check_cutoff(cutoff)
        windows[window].append({"opportunity_id": oid, "target": target.to_dict(), "cutoff": cutoff,
            "origin": origin, "probability": probability, "event": event,
            "source_revision": "EUPP_station460:" + r["initialization"],
            "common": {"initialization": r["initialization"], "daily_products": common[r["initialization"]],
                       "duration_rule": "same member across three target days; never multiply marginal probabilities",
                       "product_scope": "complete station daily extrema product at days1-4"}})

    for row in daily:
        for event in ["hot_day", "frost_day", "ice_day"]:
            add(row, event, row["target_date"], row["probabilities"][event])
    for row in durations:
        add(row, row["event"], row["target_dates"][0], row["probability"])
    cases = []
    for name, rows in sorted(windows.items()):
        case = OUT / name
        case.mkdir()
        rows.sort(key=lambda r:(r["cutoff"],r["opportunity_id"]))
        publish(case/"POLICY.json", {"rows": rows})
        opportunities = [TypedOpportunity(r["opportunity_id"], Target(**r["target"]), r["cutoff"]) for r in rows]
        versions = {r["target_contract_hash"]: r["resolution_version"] for r in registry.records.values()}
        outcomes = registry.opportunity_rows(opportunities, {o.opportunity_id: versions[o.target.contract_hash] for o in opportunities})
        publish(case/"OUTCOMES.json", outcomes)
        cases.append(case)
    bound_paths = [audit_path, target_path, registry_path, OUT/"PREREGISTRATION.json"]
    bound_paths += [analysis/n for n in audit["analysis_files"]]
    bound_paths += list((OUT/"source").rglob("*.py"))
    bound_paths += [case/n for case in cases for n in ["POLICY.json", "OUTCOMES.json"]]
    publish(OUT/"FREEZE.json", {"files": {str(p): digest(p) for p in bound_paths}})
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path)
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--protocol", choices=PROTOCOLS)
    args = parser.parse_args()
    if args.case:
        run_case(args.case, args.arm, args.protocol)
        return
    cases = prepare()
    env = dict(os.environ, PYTHONPATH=str(OUT/"source"), PYTHONDONTWRITEBYTECODE="1", DISASTERTRACE_FOLLOWUP_ROOT=str(ROOT))

    def run(item):
        case, arm, protocol = item
        cmd = [sys.executable,str(OUT/"source/run_temperature_stream.py"),"--case",str(case),"--arm",arm,"--protocol",protocol]
        with (case/(arm+"__"+protocol+".log")).open("x") as log:
            result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        row = {"case": case.name,"arm": arm,"protocol": protocol,"exit_code": result.returncode}
        publish(case/(arm+"__"+protocol+".exit.json"), row)
        return row

    work = [(c,a,p) for c in cases for a in ARMS for p in PROTOCOLS]
    reused = []
    fresh = list(work)
    prefix = []
    for item in fresh[:6]:
        result = run(item)
        prefix.append(result)
        assert result["exit_code"] == 0, "Native temperature COPY/protocol preflight failed; no model calls"
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = [*reused, *prefix, *pool.map(run, fresh[6:])]
    publish(OUT/"PROGRAM_EXIT.json", results)
    assert all(r["exit_code"] == 0 for r in results)
    score_rows = []
    for case in cases:
        invariant = read(case/(ARMS[0]+"__"+PROTOCOLS[0])/"COMPLETE.json")["invariants"]
        comparison = ComparisonContract(invariant, {"arm": ARMS, "protocol": PROTOCOLS})
        scores = score_admitted(read(case/"OUTCOMES.json"),
            {a+"__"+p:case/(a+"__"+p)/"admission.jsonl" for a in ARMS for p in PROTOCOLS}, comparison=comparison)
        publish(case/"SCORES.json", scores)
        score_rows.append({"case":case.name,"scores_sha256":fingerprint(scores)})
    publish(OUT/"COMPLETE.json", {"programs":results,"scores":score_rows,"model_calls":0,
        "confirmation_opened":False,"scope":"continuous native F program control pilot; C1 and model temperature prediction remain untested"})
    print(json.dumps({"sessions":len(results),"scored_windows":len(cases),"model_calls":0}),flush=True)


if __name__ == "__main__":
    main()
