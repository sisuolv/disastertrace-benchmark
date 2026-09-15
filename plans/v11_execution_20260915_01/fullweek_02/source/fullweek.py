"""Complete the exposed seasonal calendars; retain every registered failure."""

import argparse
import copy
import datetime as dt
import importlib.util
import json
import math
import shutil
import time
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import (
    ComparisonContract,
    experiment_spec,
)
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.formal_session import (
    FormalSession,
    required_source_files,
    score_formal,
)
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import utc_us

DAY = 86400_000_000
ARMS = ["FOLLOW", "F_COMMON", "F_BASE_ONLY", "B11_BATCH", "B11_COVERAGE"]
STATIONS = {"new_york": ["KJFK", "KLGA", "KEWR"],
            "chicago": ["KORD", "KMDW", "KRFD"], "denver": ["KDEN", "KBJC", "KAPA"]}


def comparison(configs, data, bank):
    allowed, invariant = defaultdict(list), None
    for config in configs.values():
        spec = experiment_spec(data, bank, config)
        invariant = invariant or spec["invariants"]
        if invariant != spec["invariants"]:
            raise ValueError("A comparison cannot silently change its predictor bank")
        for k, v in spec["interventions"].items():
            if v not in allowed[k]:
                allowed[k].append(v)
    return ComparisonContract(invariant, allowed).export()


def prepare(out, repo):
    old = repo / "plans/v10_execution_20260914_01"
    units = read(old / "seasonal_completion_02/COMPLETE.json")["units"]
    if len(units) != 12 or not all(u["complete"] for u in units):
        raise ValueError("All twelve original region-weeks are required")
    out.mkdir(exist_ok=False)
    publish(out / "REGISTRATION.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "arms": ARMS,
        "calendar_rule": "all seven UTC cutoff days of every original region-week; all sites; lead1h",
        "daily_session_rule": "fresh session each UTC cutoff day; no cross-day paid-cache carry",
        "request_budget_per_daily_session": 48, "protocol": "base_bound_override",
        "bank": "original Dec2024 posthoc no-year-feature banks; no new fitting",
        "scope": "complete-calendar development diagnostic; four global week blocks, not independent confirmation",
        "program_latency": "registered1ms computation plus1ms persistence scenario; not measured deployment",
        "comparisons": "same-values-bank four-arm group; common-only bank separately bound",
        "missing_and_failed": "all registered IDs retained; incomplete groups are not complete comparisons",
        "shards": 4, "model_calls": 0, "confirmation_opened": False,
    })
    helper_path = repo / "plans/v9_followup_execution_20260914_01/api_pilot_01/source/program_reference.py"
    spec = importlib.util.spec_from_file_location("v11_outcome_reference", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    cards = []
    for unit_index, unit in enumerate(units):
        dataset = Path(unit["dataset"])
        for name, sha in unit["dataset_files"].items():
            if digest(dataset / name) != sha:
                raise ValueError("Original seasonal data changed")
        region, week = unit["unit"].split("__")
        for threshold in (1000, 5000):
            full = load_session(dataset, stations=STATIONS[region], threshold=threshold)
            original = read(old / "seasonal_controls_01" / (unit["unit"] + "__" + str(threshold)) / "CONFIGS.json")
            for day_index in range(7):
                date = (dt.date.fromisoformat(week) + dt.timedelta(days=day_index)).isoformat()
                case = out / (region + "__" + date + "__" + str(threshold))
                case.mkdir()
                data = copy.deepcopy(full)
                start = utc_us(date + "T00:00:00Z")
                data["opportunities"] = [r for r in data["opportunities"]
                                         if start <= r["cutoff"] < start + DAY and r["lead_hours"] == 1]
                oids = {r["opportunity_id"] for r in data["opportunities"]}
                tids = {r["target_id"] for r in data["opportunities"]}
                if len(oids) != 72 or len(data["opportunities"]) != 72:
                    raise ValueError("Full UTC daily roster must have72 opportunities")
                for key in ("targets", "baseline_candidates", "baseline_withdrawals"):
                    data[key] = [r for r in data[key] if r["target_id"] in tids]
                data["e_f_pairs"] = [r for r in data["e_f_pairs"] if r["opportunity_id"] in oids]
                bank = read(old / "seasonal_evaluation_01/banks" / (region + ".json"))
                configs = {}
                for arm in ARMS:
                    config = copy.deepcopy(original["F_BASE_ONLY" if arm == "F_COMMON" else arm])
                    if arm == "F_COMMON":
                        config["native_feature_bank"] = read(old / "calendar_feature_ablation_01/banks/common.json")
                    config.pop("execution_contract", None)
                    configs[arm] = bind_source(bind_execution(config, None), None)
                groups = {
                    "same_values_bank": [a for a in ARMS if a != "F_COMMON"],
                    "common_bank": ["F_COMMON"],
                }
                comparisons = {g: comparison({a: configs[a] for a in names}, data, bank)
                               for g, names in groups.items()}
                for name, value in (("DATA", data), ("BANK", bank), ("CONFIGS", configs),
                                    ("COMPARISONS", comparisons)):
                    publish(case / (name + ".json"), value)
                # The complete public roster is fixed before materializing evaluator-only labels.
                publish(case / "ROSTER.json", sorted(oids))
                (case / "outcome_preparation").mkdir()
                outcomes = helper.outcomes(dataset, data, case / "outcome_preparation")
                publish(case / "OUTCOMES.json", [{**r, "resolution_policy": "h15_routine_archive.v1",
                    "provider": "IEM", "provider_version": "native_h15_snapshot.v1"} for r in outcomes])
                publish(case / "SOURCE_BINDINGS.json", {"dataset": str(dataset),
                    "dataset_files": unit["dataset_files"], "parent_unit": unit["unit"]})
                cards.append({"case": case.name, "region": region, "date": date, "week": week,
                              "threshold": threshold, "arms": ARMS, "groups": groups,
                              "opportunities": 72, "shard": unit_index % 4})
    for package in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(repo / "disastertrace-starter/src/disastertrace" / package,
                        out / "source/disastertrace" / package, ignore=shutil.ignore_patterns("__pycache__"))
    (out / "source/disastertrace/__init__.py").write_text('"""Frozen full-week development execution."""\n')
    shutil.copyfile(__file__, out / "source/fullweek.py")
    shutil.copyfile(helper_path, out / "source/program_reference.py")
    shutil.copyfile(old / "contracts/H15_REPORT_LABEL_DATA_CARD.json", out / "DATA_CARD.json")
    publish(out / "PLAN.json", {"cases": cards, "trajectories": 840, "opportunities": 12096,
        "files": {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()}})
    print(json.dumps({"prepared": len(cards), "trajectories": 840}), flush=True)


def run_arm(task):
    case, arm, group = task
    start = time.monotonic()
    try:
        data, bank, configs = (read(case / n) for n in ("DATA.json", "BANK.json", "CONFIGS.json"))
        payload = read(case / "COMPARISONS.json")[group]["payload"]
        comp = ComparisonContract(payload["invariants"], payload["allowed_interventions"])
        files = {str(p): digest(p) for p in required_source_files()}
        files.update({str(case / n): digest(case / n) for n in
                      ("DATA.json", "BANK.json", "CONFIGS.json", "COMPARISONS.json", "ROSTER.json")})
        files.update({str(case.parent / n): digest(case.parent / n) for n in ("REGISTRATION.json", "DATA_CARD.json")})
        run = FormalSession(data, bank, configs[arm], comparison=comp, bound_files=files,
                            directory=case / arm)
        report = run.finish(max_steps=100)
        run.export_journal(case / arm / "admission.jsonl")
        result = {"case": case.name, "arm": arm, "state": "completed", "seconds": time.monotonic() - start,
                  "opportunities": len(report["snapshots"]), "model_calls": report["actual_model_calls"]}
        publish(case / arm / "COMPLETE.json", result)
        return result
    except Exception as exc:  # noqa: BLE001 - retain failed registered arms without replacing them.
        result = {"case": case.name, "arm": arm, "state": "failed", "error": type(exc).__name__,
                  "message": str(exc), "traceback": traceback.format_exc(), "seconds": time.monotonic() - start}
        publish(case / (arm + ".FAILED.json"), result)
        return result


def run_shard(out, shard, workers):
    plan = read(out / "PLAN.json")
    if shard not in range(4):
        raise ValueError("Unregistered shard")
    publish(out / ("CLAIM_" + str(shard) + ".json"), {"at": dt.datetime.now(dt.timezone.utc).isoformat()})
    for name, sha in plan["files"].items():
        if digest(out / name) != sha:
            raise ValueError("Frozen execution input changed")
    tasks = [(out / c["case"], a, g) for c in plan["cases"] if c["shard"] == shard
             for g, arms in c["groups"].items() for a in arms]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = [pool.submit(run_arm, task) for task in tasks]
        for future in as_completed(pending):
            results.append(future.result())
            if len(results) % 10 == 0:
                print(json.dumps({"shard": shard, "finished": len(results), "expected": len(tasks),
                                  "failed": sum(r["state"] == "failed" for r in results)}), flush=True)
    publish(out / ("COMPLETE_" + str(shard) + ".json"), {"results": results,
        "passed": len(results) == len(tasks) and all(r["state"] == "completed" for r in results)})


def audit_case(task):
    out, card = task
    case = out / card["case"]
    outcomes = read(case / "OUTCOMES.json")
    registry = {r["opportunity_id"]: r for r in outcomes}
    roster = read(case / "ROSTER.json")
    if len(registry) != len(outcomes) or set(roster) != set(registry):
        raise ValueError("Outcome roster mismatch")
    scores = {}
    for group, arms in card["groups"].items():
        p = read(case / "COMPARISONS.json")[group]["payload"]
        scores.update(score_formal(outcomes, {a: case / a / "admission.jsonl" for a in arms},
            comparison=ComparisonContract(p["invariants"], p["allowed_interventions"]),
            run_references={a: case / a for a in arms})["scores"]["arms"])
    rows, schedule, baselines = [], None, None
    for arm in card["arms"]:
        report = read(case / arm / "FORMAL_REPORT.json")
        if {s["opportunity_id"] for s in report["snapshots"]} != set(roster) or len(report["snapshots"]) != len(roster):
            raise ValueError("Forecast roster mismatch")
        trace = [(s["opportunity_id"], s["base_forecast"]) for s in report["snapshots"]]
        if baselines is not None and trace != baselines:
            raise ValueError("Common baseline changed across arms")
        baselines = trace
        if arm != "FOLLOW":
            actual = [(c["opportunity_id"], c["started_at"], c["persisted_at"]) for c in report["calls"]]
            if schedule is not None and actual != schedule:
                raise ValueError("Predictor schedules differ")
            schedule = actual
        statuses = {oid: state for f in report["frames"] for oid, state in f["e_statuses"].items()}
        losses = []
        for s in report["snapshots"]:
            oid, probability = s["opportunity_id"], s["forecast"]["value"]
            outcome = registry[oid]["value"] if registry[oid]["status"] == "mature" else None
            loss = None if outcome is None else (probability - outcome)**2
            if loss is not None:
                losses.append(loss)
            rows.append({"case": case.name, "region": card["region"], "date": card["date"],
                "week": card["week"], "threshold": card["threshold"], "arm": arm,
                "opportunity_id": oid, "probability": probability, "outcome": outcome,
                "loss": loss, "e_status": statuses.get(oid)})
        if scores[arm]["scored"] != len(losses) or not math.isclose(scores[arm]["loss_sum"], math.fsum(losses), abs_tol=1e-10):
            raise ValueError("Independent arithmetic differs from formal score")
    return rows


def audit(out, workers):
    plan = read(out / "PLAN.json")
    attempts = [r for shard in range(4) for r in read(out / ("COMPLETE_" + str(shard) + ".json"))["results"]]
    expected = {(c["case"], a) for c in plan["cases"] for a in c["arms"]}
    got = {(r["case"], r["arm"]) for r in attempts}
    if got != expected or len(attempts) != len(expected) or any(r["state"] != "completed" for r in attempts):
        publish(out / "INCOMPLETE.json", {"expected": len(expected), "attempted": len(attempts),
            "missing": sorted(expected-got), "failed": [r for r in attempts if r["state"] != "completed"]})
        raise ValueError("Incomplete registered comparison; failures retained")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = [r for part in pool.map(audit_case, [(out, c) for c in plan["cases"]]) for r in part]
    publish(out / "ROWS.json", rows)
    groups = defaultdict(list)
    for row in rows:
        groups[(row["threshold"], "all", row["arm"])].append(row)
        groups[(row["threshold"], row["week"], row["arm"])].append(row)
    metrics = {}
    for (threshold, block, arm), values in groups.items():
        settled = [r for r in values if r["loss"] is not None]
        metrics[f"{threshold}__{block}__{arm}"] = {"registered": len(values), "settled": len(settled),
            "positive": sum(r["outcome"] == 1 for r in settled), "missing": len(values)-len(settled),
            "brier": math.fsum(r["loss"] for r in settled)/len(settled) if settled else None,
            "e_determined": sum(r["e_status"] in {"entailed", "refuted"} for r in values)}
    publish(out / "RESULT.json", {"passed": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "trajectories": len(attempts), "method_rows": len(rows), "opportunities": 12096,
        "global_calendar_blocks": 4, "independent_confirmation": False, "model_calls": 0,
        "metrics": metrics, "rows_sha256": digest(out / "ROWS.json"),
        "qualification": "historical declared-availability development; code-bound scores and arithmetic audit, not independent physical truth"})
    print(json.dumps({"passed": True, "trajectories": len(attempts), "rows": len(rows)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "run", "audit"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--shard", type=int)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.out.absolute(), args.repo.absolute())
    elif args.mode == "run":
        run_shard(args.out.absolute(), args.shard, args.workers)
    else:
        audit(args.out.absolute(), args.workers)
