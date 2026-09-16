"""Frozen full-calendar bridge; one launch per case, complete denominators."""
import argparse
import copy
import datetime as dt
import json
import math
import signal
import time
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, experiment_spec
from disastertrace.monitoring_v1.comparison_fingerprint import compare, fingerprint
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.formal_session import FormalSession, required_source_files, score_formal
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OLD = REPO / "plans/v11_execution_20260915_01/fullweek_02"
PREV = REPO / "plans/v13_execution_20260916_01"
OUT = RUN / "B00"
ARMS = ["FOLLOW", "F_COMMON", "F_BASE_ONLY", "B11_BATCH", "B11_COVERAGE"]
GROUPS = {"follow": ["FOLLOW"], "common": ["F_COMMON"], "values": ARMS[2:]}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def contract(configs, data, bank):
    specs = [experiment_spec(data, bank, c) for c in configs.values()]
    invariant, allowed = specs[0]["invariants"], defaultdict(list)
    for spec in specs:
        if spec["invariants"] != invariant:
            raise ValueError("Comparison invariants differ")
        for key, value in spec["interventions"].items():
            if value not in allowed[key]:
                allowed[key].append(value)
    return ComparisonContract(invariant, allowed)


def restore_contract(value):
    p = value["payload"]
    return ComparisonContract(p["invariants"], p["allowed_interventions"])


def verify(files):
    for name, sha in files.items():
        if digest(Path(name)) != sha:
            raise ValueError("Frozen input changed: " + name)


def prepare():
    auth = read(RUN / "AUTHORIZATION.json")
    verify(auth["prior_bindings"])
    verify(auth["source_files"])
    prior = read(PREV / "regression_02/REGISTRATION.json")
    verify(prior["source_hashes"])
    proposal = read(PREV / "B00_ROSTER_PROPOSAL.json")
    OUT.mkdir(exist_ok=False)
    banks = {}
    for mode, ref in proposal["banks"].items():
        verify({ref["path"]: ref["sha256"]})
        banks[mode] = read(Path(ref["path"]))
        banks[mode].pop("post_calibration", None)
        publish(OUT / ("RAW_BANK_" + mode + ".json"), banks[mode])
    consumer = canonical_hash({str(p.relative_to(RUN / "source")): digest(p)
                               for p in required_source_files()})
    cases = []
    for i, row in enumerate(proposal["cases"]):
        original, case = OLD / row["case"], OUT / row["case"]
        case.mkdir()
        data, bank = read(original / "DATA.json"), read(original / "BANK.json")
        roster = [o["opportunity_id"] for o in data["opportunities"]]
        if len(roster) != 72 or len(set(roster)) != 72:
            raise ValueError("Unexpected daily roster")
        originals = {str(original / n): digest(original / n)
                     for n in ("DATA.json", "BANK.json", "CONFIGS.json", "OUTCOMES.json")}
        for name in ("DATA.json", "BANK.json", "OUTCOMES.json"):
            publish(case / name, read(original / name))
        configs = {}
        for arm in ARMS:
            cfg = copy.deepcopy(read(original / "CONFIGS.json")["B11_COVERAGE"])
            cfg.pop("execution_contract", None)
            cfg.update(native_feature_bank=banks["common" if arm == "F_COMMON" else "values"],
                       selector_kind="batch_complete" if arm == "B11_BATCH" else "coverage",
                       model_call_budget=24, acquire=arm not in ARMS[:3], predict=arm != "FOLLOW")
            configs[arm] = bind_execution(cfg, None)
        groups = {g: contract({a: configs[a] for a in arms}, data, bank).export()
                  for g, arms in GROUPS.items()}
        prints = {a: fingerprint(c, baseline_bank=bank, consumer_code_sha256=consumer,
                                source_contract_sha256=canonical_hash(data)) for a, c in configs.items()}
        pairs = {a + "__" + b: compare(prints[a], prints[b])
                 for a, b in [("F_BASE_ONLY", "B11_BATCH"), ("F_BASE_ONLY", "B11_COVERAGE"),
                              ("B11_BATCH", "B11_COVERAGE"), ("FOLLOW", "F_BASE_ONLY"),
                              ("F_COMMON", "F_BASE_ONLY")]}
        if not all(pairs[k]["same_predictor"] for k in list(pairs)[:3]):
            raise ValueError("Primary acquisition contrasts change predictor")
        publish(case / "CONFIGS.json", configs)
        publish(case / "COMPARISONS.json", groups)
        publish(case / "ROSTER.json", roster)
        publish(case / "FACTORS.json", {"fingerprints": prints, "comparisons": pairs})
        files = {str(p): digest(p) for p in case.glob("*.json")}
        cases.append({**row, "shard": i % 3, "arms": ARMS, "files": files, "originals": originals})
    publish(OUT / "REGISTRATION.json", {
        "at": now(), "cases": cases, "arms": ARMS, "groups": GROUPS,
        "qualification_case": cases[0]["case"], "trajectories_max": 840,
        "opportunities": 12096, "method_rows": 60480, "shards": 3,
        "source_files": auth["source_files"], "runner_sha256": digest(Path(__file__)),
        "banks": {m: digest(OUT / ("RAW_BANK_" + m + ".json")) for m in banks},
        "scope": "four exposed global week blocks; annual raw fixed banks; development only",
        "reused_trajectories": 0, "reuse_reason": "new frozen consumer code; no asserted old-run equivalence",
        "qualification_is_part_of_roster": True, "automatic_retries": 0,
        "model_calls": 0, "new_weather_HTTP": 0, "new_fitting": 0,
        "program_latency": "1ms computation plus1ms persistence scenario, not deployment measurement",
        "confirmation_opened": False})
    print(json.dumps({"prepared": len(cases), "trajectories": 840}), flush=True)


def timeout(*_):
    raise TimeoutError("Case exceeded frozen three-hour wall cap")


def run_case(row):
    case = OUT / row["case"]
    publish(case / "CLAIM.json", {"at": now(), "one_use": True})
    result = {"case": row["case"], "passed": False, "arms": [], "scored_groups": []}
    start = time.monotonic()
    session = None
    try:
        signal.signal(signal.SIGALRM, timeout)
        signal.alarm(10800)
        verify(row["files"])
        reg = read(OUT / "REGISTRATION.json")
        data, bank, configs, comps = [read(case / n) for n in
                                     ("DATA.json", "BANK.json", "CONFIGS.json", "COMPARISONS.json")]
        files = {**reg["source_files"], **row["files"],
                 str(OUT / "REGISTRATION.json"): digest(OUT / "REGISTRATION.json"),
                 str(Path(__file__)): reg["runner_sha256"]}
        for arm in ARMS:
            comp = restore_contract(comps[next(g for g in GROUPS if arm in GROUPS[g])])
            session = FormalSession(data, bank, configs[arm], comparison=comp,
                                    bound_files=files, directory=case / arm)
            report = session.finish(max_steps=24)
            session.export_journal(case / arm / "admission.jsonl")
            result["arms"].append({"arm": arm, "passed": True,
                                   "opportunities": len(report["snapshots"]),
                                   "actual_model_calls": report["actual_model_calls"]})
        outcomes = read(case / "OUTCOMES.json")
        registry = {o["opportunity_id"]: o for o in outcomes}
        roster = set(read(case / "ROSTER.json"))
        if set(registry) != roster or len(registry) != len(outcomes):
            raise ValueError("Outcome roster mismatch")
        scores = {}
        for group, arms in GROUPS.items():
            score = score_formal(outcomes, {a: case / a / "admission.jsonl" for a in arms},
                                 comparison=restore_contract(comps[group]),
                                 run_references={a: case / a for a in arms})
            publish(case / ("SCORE_" + group + ".json"), score)
            scores.update(score["scores"]["arms"])
            result["scored_groups"].append(group)
        rows, schedule, baseline = [], None, None
        for arm in ARMS:
            report = read(case / arm / "FORMAL_REPORT.json")
            snaps = report["snapshots"]
            if len(snaps) != len(roster) or {s["opportunity_id"] for s in snaps} != roster:
                raise ValueError("Snapshot denominator mismatch")
            current = [(s["opportunity_id"], s["base_forecast"]) for s in snaps]
            if baseline is not None and current != baseline:
                raise ValueError("Common baseline differs")
            baseline = current
            if arm != "FOLLOW":
                current = [(c["opportunity_id"], c["started_at"], c["persisted_at"]) for c in report["calls"]]
                if schedule is not None and current != schedule:
                    raise ValueError("Program schedule differs")
                schedule = current
            statuses = {k: v for f in report["frames"] for k, v in f["e_statuses"].items()}
            losses = []
            for snap in snaps:
                oid, p = snap["opportunity_id"], snap["forecast"]["value"]
                y = registry[oid]["value"] if registry[oid]["status"] == "mature" else None
                loss = None if y is None else (p - y) ** 2
                if loss is not None:
                    losses.append(loss)
                rows.append({**{k: row[k] for k in ("case", "region", "date", "week", "threshold")},
                             "arm": arm, "opportunity_id": oid, "probability": p,
                             "outcome": y, "loss": loss, "e_status": statuses.get(oid),
                             "outcome_status": registry[oid]["status"]})
            if scores[arm]["scored"] != len(losses) or not math.isclose(
                    scores[arm]["loss_sum"], math.fsum(losses), abs_tol=1e-10):
                raise ValueError("Independent arithmetic differs from formal score")
        publish(case / "ROWS.json", rows)
        result.update(passed=True, method_rows=len(rows), rows_sha256=digest(case / "ROWS.json"))
    except Exception as exc:
        result.update(error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        if session is not None and not (session.directory / "STOP.json").exists():
            session.stop("failed")
    finally:
        signal.alarm(0)
    result.update(seconds=time.monotonic() - start, finished_at=now())
    publish(case / "RESULT.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"traceback", "arms"}}), flush=True)
    return result


def execute(shard, workers):
    reg = read(OUT / "REGISTRATION.json")
    verify(reg["source_files"])
    verify({str(Path(__file__)): reg["runner_sha256"]})
    if shard not in range(3):
        raise ValueError("Unregistered shard")
    publish(OUT / (f"CLAIM_{shard}.json"), {"at": now(), "workers": workers})
    pilot = reg["qualification_case"]
    rows = [r for r in reg["cases"] if r["shard"] == shard]
    results = []
    if shard == 0:
        result = run_case(next(r for r in rows if r["case"] == pilot))
        publish(OUT / "QUALIFICATION.json", result)
        results.append(result)
    else:
        deadline = time.monotonic() + 10860
        while not (OUT / "QUALIFICATION.json").exists() and time.monotonic() < deadline:
            time.sleep(30)
    if not (OUT / "QUALIFICATION.json").exists() or not read(OUT / "QUALIFICATION.json")["passed"]:
        publish(OUT / f"SHARD_{shard}.json", {"passed": False, "status": "qualification_blocked", "results": results})
        return 1
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_case, r): r for r in rows if r["case"] != pilot}
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as exc:
                results.append({"case": futures[f]["case"], "passed": False,
                                "error": type(exc).__name__, "message": str(exc)})
    passed = len(results) == len(rows) and all(r["passed"] for r in results)
    publish(OUT / f"SHARD_{shard}.json", {"passed": passed, "results": results, "finished_at": now()})
    return 0 if passed else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["prepare", "execute"])
    p.add_argument("--shard", type=int, default=0)
    p.add_argument("--workers", type=int, default=12)
    args = p.parse_args()
    if args.mode == "prepare":
        prepare()
    else:
        raise SystemExit(execute(args.shard, args.workers))
