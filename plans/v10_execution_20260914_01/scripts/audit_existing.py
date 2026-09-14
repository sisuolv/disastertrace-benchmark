"""Parallel, read-only rechecks of registered v9 artifacts; no model dispatch."""

import argparse
import importlib.util
import json
import math
import os
import re
import socket
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.forecast_task.common import strict_json
from disastertrace.monitoring_v1.audit_contracts import require_exact_ids
from disastertrace.monitoring_v1.calibration_diagnostics import trace_prediction
from disastertrace.monitoring_v1.e_composition import compose
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def check(condition, message):
    if not condition:
        raise ValueError(message)


def temperature_case(args):
    case, out, arms = args
    rows = read(case / "POLICY.json")["rows"]
    ids = [r["opportunity_id"] for r in rows]
    targets = {r["target"]["target_id"] for r in rows}
    by_id = {r["opportunity_id"]: r for r in rows}
    results = read(case / "OUTCOMES.json")
    require_exact_ids(
        ids, [r["opportunity_id"] for r in results], case.name + " outcomes"
    )
    results = {r["opportunity_id"]: r for r in results}
    scores = read(case / "SCORES.json")["scores"]["arms"]
    require_exact_ids(arms, scores, case.name + " scores")
    require_exact_ids(
        arms,
        [p.name for p in case.iterdir() if p.is_dir() and "__" in p.name],
        case.name + " arms",
    )
    follow = read(case / "follow__base_bound_override/SNAPSHOTS.json")
    require_exact_ids(ids, follow, case.name + " follow")
    groups = defaultdict(Counter)
    hashes = {
        str(p): digest(p)
        for p in [case / "POLICY.json", case / "OUTCOMES.json", case / "SCORES.json"]
    }
    for arm in arms:
        snapshots = read(case / arm / "SNAPSHOTS.json")
        require_exact_ids(ids, snapshots, case.name + "/" + arm)
        complete = read(case / arm / "COMPLETE.json")
        check(
            complete["snapshots"] == len(ids) and complete["model_calls"] == 0,
            "Temperature completion count mismatch",
        )
        losses = []
        for oid in ids:
            row = by_id[oid]
            p, b = snapshots[oid]["forecast"]["value"], follow[oid]["forecast"]["value"]
            check(
                type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1,
                "Invalid temperature probability",
            )
            g = groups[row["event"] + "__" + arm]
            g.update(opportunities=1, different_from_follow=int(p != b))
            result = results[oid]
            if result["status"] != "mature":
                g["missing"] += 1
                continue
            y = result["value"]
            loss, delta = (p - y) ** 2, (p - y) ** 2 - (b - y) ** 2
            losses.append(loss)
            g.update(
                mature=1,
                positive=y,
                loss_sum=loss,
                delta_sum=delta,
                improved=int(delta < -1e-14),
                worsened=int(delta > 1e-14),
            )
        check(
            math.isclose(
                math.fsum(losses) / len(losses), scores[arm]["mean_loss"], abs_tol=1e-14
            ),
            "Temperature arithmetic mismatch",
        )
        hashes[str(case / arm / "SNAPSHOTS.json")] = digest(
            case / arm / "SNAPSHOTS.json"
        )
    result = {
        "case": case.name,
        "passed": True,
        "opportunities": len(ids),
        "targets": sorted(targets),
        "sessions": len(arms),
        "groups": dict(groups),
        "files": hashes,
    }
    publish(out / (case.name + ".json"), result)
    return result


def forecast_case(args):
    case, out, cohort = args
    configs, data, bank = [
        read(case / n) for n in ("CONFIGS.json", "DATA.json", "BANK.json")
    ]
    ids = [r["opportunity_id"] for r in data["opportunities"]]
    outcomes = read(case / "OUTCOMES.json")
    require_exact_ids(ids, [r["opportunity_id"] for r in outcomes], "F outcomes")
    outcomes = {r["opportunity_id"]: r for r in outcomes}
    present = [
        p.name for p in case.iterdir() if p.is_dir() and (p / "REPORT.json").exists()
    ]
    require_exact_ids(configs, present, "F registered arms")
    follow_report = read(case / "follow/REPORT.json")
    follow = {r["opportunity_id"]: r for r in follow_report["snapshots"]}
    require_exact_ids(ids, follow, "F follow snapshots")
    summary, proposal_rows, score_rows, parser_hits = [], [], [], []
    for arm, config in configs.items():
        report = read(case / arm / "REPORT.json")
        require_exact_ids(
            ids, [r["opportunity_id"] for r in report["snapshots"]], "F " + arm
        )
        check(not report["outcome_table_accessed_by_policy"], "Policy saw outcomes")
        complete = read(case / arm / "COMPLETE.json")
        check(complete["snapshots"] == len(ids), "F completion count mismatch")
        for call in report["selector_calls"]:
            raw = call["raw"].strip()
            if raw.startswith("```json\n") and raw.endswith("```"):
                raw = raw[8:-3].strip()
            elif raw.startswith("```\n") and raw.endswith("```"):
                raw = raw[4:-3].strip()
            try:
                strict_json(raw)
            except ValueError as error:
                parser_hits.append(
                    {
                        "case": case.name,
                        "arm": arm,
                        "call_id": call["call_id"],
                        "duplicate_key": "duplicate" in str(error),
                        "was_rejected": bool(call["response_error"]),
                    }
                )
        losses, deltas, missing = [], [], []
        positive = 0
        for row in report["snapshots"]:
            oid = row["opportunity_id"]
            p, b = row["forecast"]["value"], follow[oid]["forecast"]["value"]
            result = outcomes[oid]
            scored = result["status"] == "mature"
            y = result["value"] if scored else None
            loss = (p - y) ** 2 if scored else None
            delta = loss - (b - y) ** 2 if scored else None
            if scored:
                losses.append(loss)
                deltas.append(delta)
                positive += y
            else:
                endpoints = [(p - v) ** 2 - (b - v) ** 2 for v in (0, 1)]
                missing.append((min(endpoints), max(endpoints)))
            score_rows.append(
                {
                    "cohort": cohort,
                    "case": case.name,
                    "arm": arm,
                    "opportunity_id": oid,
                    "target_id": row["target"]["target_id"],
                    "cutoff": row["cutoff"],
                    "probability": p,
                    "follow": b,
                    "outcome": y,
                    "loss": loss,
                    "delta_vs_follow": delta,
                }
            )
        saved_score = read(case / arm / "SCORES.json")["scores"]["arms"][arm][
            "mean_loss"
        ]
        mean = math.fsum(losses) / len(losses) if losses else None
        check(
            mean is None or math.isclose(mean, saved_score, abs_tol=1e-14),
            "F independent arithmetic mismatch",
        )
        counter = Counter()
        for call in report["calls"]:
            view = call["bundle"]["payload"]
            content = view["baseline"]["content"]
            trace = trace_prediction(
                bank,
                content["legacy_target_contract"],
                content["native_taf"],
                content["E_question"]["query_ids"],
                {a["content"]["query_id"]: a["content"] for a in view["assets"]},
            )
            if (
                config.get("predictor_kind") == "program"
                and config.get("program_prediction") == "frequency_mapping"
            ):
                check(
                    call["proposed_probability"] == trace["post_probability"],
                    "Program mapping differs from original proposal",
                )
            p = call.get("proposed_probability")
            b, current = (
                view["baseline"]["forecast"]["value"],
                view["state"]["forecast"]["value"],
            )
            kind = (
                "invalid"
                if p is None
                else "exact_current"
                if p == current
                else "exact_latest_baseline"
                if p == b
                else "exact_program_mapping"
                if p == trace["post_probability"]
                else "numerically_distinct"
            )
            counter[kind] += 1
            counter["same_raw_cell"] += trace["same_raw_cell_as_base"]
            counter["mapping_only_numeric_change"] += trace[
                "mapping_only_numeric_change"
            ]
            counter["no_taf"] += trace["no_taf"]
            counter["unrelated_disclosure"] += bool(trace["unrelated_disclosed_ids"])
            proposal_rows.append(
                {
                    "case": case.name,
                    "arm": arm,
                    "call_id": call["call_id"],
                    "opportunity_id": call["opportunity_id"],
                    "proposal": p,
                    "exact_class": kind,
                    "delta_current": None if p is None else p - current,
                    "delta_baseline": None if p is None else p - b,
                    "admission_status": call["admission_status"],
                    **trace,
                }
            )
        summary.append(
            {
                "case": case.name,
                "cohort": cohort,
                "arm": arm,
                "opportunities": len(ids),
                "mature": len(losses),
                "positive": positive,
                "missing": len(missing),
                "brier": mean,
                "delta_vs_follow": math.fsum(deltas) / len(deltas) if deltas else None,
                "full_denominator_delta_bounds": [
                    (math.fsum(deltas) + sum(x[k] for x in missing)) / len(ids)
                    for k in (0, 1)
                ],
                "mapping": dict(counter),
                "model_calls": report["actual_model_calls"],
                "program_calls": report["actual_program_forecast_calls"],
                "selector_calls": len(report["selector_calls"]),
                "resource_spent": report["resource_spent"],
                "resource_reserved": report["resource_reserved"],
                "report_sha256": digest(case / arm / "REPORT.json"),
            }
        )
    for name, rows in [("proposals", proposal_rows), ("scores", score_rows)]:
        with (out / (case.name + "__" + name + ".jsonl")).open("x") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    result = {
        "passed": True,
        "records": summary,
        "parser_hits": parser_hits,
        "opportunities": len(ids),
        "arms": len(configs),
        "cohort": cohort,
    }
    publish(out / (case.name + ".json"), result)
    return result


def audit_e(old, out):
    folder = old / "api_evidence_02"
    plan, refs = read(folder / "PLAN.json"), read(folder / "evaluator/REFERENCES.json")
    spec = importlib.util.spec_from_file_location(
        "frozen_e", folder / "source/evidence_diagnostic.py"
    )
    reducer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reducer)
    groups, rows = defaultdict(Counter), []
    views = {}
    for task in plan["tasks"]:
        if task["representation"] == "full_bundle":
            policy = read(folder / "policy" / (task["call_id"] + ".json"))
            view = strict_json(policy["messages"][1]["content"])
            key = (task["opportunity_id"], task["condition"])
            if key in views:
                check(view == views[key], "Paired full representations differ")
            views[key] = view
    for model in plan["models"]:
        require_exact_ids(
            [t["call_id"] for t in plan["tasks"]],
            [p.name for p in (folder / "captures" / model).iterdir() if p.is_dir()],
            "E02 captures",
        )
        for task in plan["tasks"]:
            captured = read(
                folder / "captures" / model / task["call_id"] / "RESPONSE.json"
            )
            choice = captured["body"]["choices"][0]
            g = groups[model + "__" + task["representation"] + "__" + task["reasoning"]]
            g["n"] += 1
            row = {"model": model, **task, "status": "invalid", "composed": None}
            reference = reducer.independent_reference(
                views[task["opportunity_id"], task["condition"]]
            )
            check(
                reference == refs[task["call_id"]], "Reference reconstruction mismatch"
            )
            g["always_unknown_correct"] += reference["fact_truth"] == "unknown"
            try:
                check(choice["finish_reason"] == "stop", "Length failure")
                answer = reducer.parse(
                    choice["message"]["content"], task["query_ids"], task["reasoning"]
                )
                g["original_correct"] += answer["fact_truth"] == reference["fact_truth"]
                row.update(status="valid", original=answer, reference=reference)
                if task["reasoning"] == "slotwise":
                    composition = compose(
                        choice["message"]["content"], task["query_ids"]
                    )
                    row["composed"] = composition
                    g["composed_correct"] += (
                        composition["composed_aggregate"] == reference["fact_truth"]
                    )
                    g["all_slots_correct"] += answer["slots"] == reference["slots"]
                    g["aggregation_changes"] += (
                        composition["reported_aggregate"]
                        != composition["composed_aggregate"]
                    )
            except (ValueError, TypeError):
                g["invalid"] += 1
            rows.append(row)
    with (out / "E_COMPOSITION.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    result = {
        "passed": True,
        "groups": dict(groups),
        "captured_answers": len(rows),
        "underlying_opportunities": plan["underlying_opportunities"],
        "new_model_calls": 0,
        "scope": "posthoc model-slot composition; original answers and scores unchanged",
    }
    publish(out / "E_COMPOSITION.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    started = time.time()
    args.out.mkdir(exist_ok=False)
    publish(
        args.out / "START.json",
        {
            "host": socket.gethostname(),
            "workers": args.workers,
            "started_epoch": started,
            "visible_cpus": len(os.sched_getaffinity(0)),
        },
    )
    temp = args.historical / "temperature_fullcalendar_01"
    prereg = read(temp / "PREREGISTRATION.json")
    months = [f"{year}-{month:02d}" for year in (2017, 2018) for month in range(1, 13)]
    arms = [a + "__" + p for a in prereg["arms"] for p in prereg["protocols"]]
    require_exact_ids(
        months,
        [
            p.name
            for p in temp.iterdir()
            if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}", p.name)
        ],
        "temperature months",
    )
    complete = read(temp / "COMPLETE.json")
    require_exact_ids(
        [m + "/" + a for m in months for a in arms],
        [
            r["case"] + "/" + r["arm"] + "__" + r["protocol"]
            for r in complete["programs"]
        ],
        "temperature exits",
    )
    check(
        all(r["exit_code"] == 0 for r in complete["programs"]),
        "Nonzero temperature task",
    )
    temp_out, f_out = args.out / "temperature", args.out / "forecast"
    temp_out.mkdir()
    f_out.mkdir()
    fwork = []
    for pilot, cohort in [
        ("api_pilot_01", "natural_development"),
        ("api_rare_pilot_01", "outcome_selected_diagnostic"),
    ]:
        folder = args.historical / pilot
        reg = read(folder / "PREREGISTRATION.json")
        expected = [
            r + "__" + d + "__" + str(t)
            for r in reg["regions"]
            for d in reg["days"]
            for t in reg["thresholds"]
        ]
        observed = [p.parent.name for p in folder.glob("*/CONFIGS.json")]
        require_exact_ids(expected, observed, pilot)
        fwork += [(folder / name, f_out, cohort) for name in expected]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        tfutures = [
            pool.submit(temperature_case, (temp / m, temp_out, arms)) for m in months
        ]
        ffutures = [pool.submit(forecast_case, item) for item in fwork]
        eresult = audit_e(args.historical, args.out)
        temperature = [f.result() for f in tfutures]
        forecast = [f.result() for f in ffutures]
    tstats = {
        "months": len(temperature),
        "sessions": sum(r["sessions"] for r in temperature),
        "opportunities": sum(r["opportunities"] for r in temperature),
        "unique_targets": len({t for r in temperature for t in r["targets"]}),
    }
    summary = {
        "passed": True,
        "temperature": tstats,
        "E": eresult,
        "forecast_cases": len(forecast),
        "forecast_sessions": sum(r["arms"] for r in forecast),
        "all_arms": [r for result in forecast for r in result["records"]],
        "parser_hits": [r for result in forecast for r in result["parser_hits"]],
        "new_model_calls": 0,
        "confirmation_opened": False,
        "seconds": time.time() - started,
        "scope": "Exact registered coverage and independent snapshot arithmetic; not a new full journal replay",
    }
    publish(args.out / "RESULT.json", summary)
    print(
        json.dumps(
            {
                "passed": True,
                "temperature": tstats,
                "forecast_sessions": summary["forecast_sessions"],
                "seconds": summary["seconds"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
