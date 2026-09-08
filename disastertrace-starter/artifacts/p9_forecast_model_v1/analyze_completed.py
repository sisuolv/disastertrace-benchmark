"""Derive native-method tables and actual token/timing accounting from verified raw journals."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median

from disastertrace.forecast_model import audit, package
from disastertrace.forecast_model.storage import write
from disastertrace.forecast_task.common import fingerprint, read
from disastertrace.forecast_task.contract import parse_answer
from disastertrace.forecast_task.scoring import _totals


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_diagnostics(report, run):
    finish = {}
    for path in sorted(run.glob("worker-*/batches/*/raw.json")):
        for result in read(path)["results"]:
            if len(result["candidates"]) != 1:
                raise ValueError("format accounting expects one returned candidate")
            finish[result["attempt_id"]] = result["candidates"][0]["finish_reason"]
    units, syntax, by_finish, largest = defaultdict(Counter), Counter(), defaultdict(Counter), []
    totals = Counter()
    for worker in report["workers"]:
        for capture in worker["captures"]:
            text = capture["final_text"] or ""
            whitespace = sum(ch.isspace() for ch in text)
            totals.update(characters=len(text), whitespace_characters=whitespace, captured=1)
            reason = finish[capture["attempt_id"]]
            largest.append({"slot_id": capture["slot_id"], "worker_id": worker["worker_id"],
                            "characters": len(text), "whitespace_characters": whitespace,
                            "finish_reason": reason, "final_text_sha256": fingerprint(text)})
            try:
                answer = parse_answer(text)
            except (TypeError, ValueError) as exc:
                syntax[type(exc).__name__ + ": " + str(exc)] += 1
                by_finish[reason]["shape_invalid"] += 1
            else:
                by_finish[reason]["shape_valid"] += 1
                for field in ("latitude", "longitude", "max_sustained_wind"):
                    units[field][answer[field]["unit"]] += 1
    return {"totals": dict(totals), "observed_unit_strings_on_shape_valid_answers":
            {k: dict(sorted(v.items())) for k, v in units.items()}, "parse_errors": dict(syntax),
            "shape_by_finish": {k: dict(v) for k,v in by_finish.items()},
            "largest_final_texts": sorted(largest, key=lambda r: (-r["characters"],r["slot_id"]))[:12],
            "units_not_normalized_or_rescored": True,
            "whitespace_count_includes_whitespace_inside_strings": True}


def analyze(execution, run, saved_report):
    execution, run = Path(execution), Path(run)
    plan, public, slots = package.verify(execution, code=True)
    report = audit.aggregate(execution, run)
    if report != read(saved_report) or plan["kind"] != "model":
        raise ValueError("analysis requires an independently reconstructable actual model run")
    private = read(execution / "task/data/private_reference.json")
    scores = {r["slot_id"]: r["score"] for r in report["scores"]["records"]}
    groups, histories, repeats = defaultdict(list), defaultdict(dict), defaultdict(dict)
    for slot in slots:
        opportunity = public["opportunities"][slot["opportunity_id"]]
        reference = private["references"][slot["opportunity_id"]]
        score = scores[slot["slot_id"]]
        method = slot["method"]
        for dimension, value in (("storm", opportunity["query"]["storm_id"]),
                                 ("transition", reference["transition"]),
                                 ("status", reference["answer"]["status"]), ("repeat", str(slot["repeat"]))):
            groups[dimension, value, method].append(score)
        histories[slot["opportunity_id"], slot["repeat"]][method] = score["all_correct"]
        repeats[slot["opportunity_id"], method][slot["repeat"]] = score["all_correct"]
    cross = defaultdict(dict)
    for (dimension, value, method), rows in sorted(groups.items()):
        cross[dimension].setdefault(value, {})[method] = _totals(rows)
    for dimension in cross.values():
        assert sum(rows["planned"] for methods in dimension.values() for rows in methods.values()) == len(slots)
        assert sum(rows["all_correct"] for methods in dimension.values() for rows in methods.values()) == report["scores"]["counts"]["all_correct"]
    paired_methods = {}
    for first, second in (("snapshot", "structured_state"), ("snapshot", "answer_history"), ("structured_state", "answer_history")):
        counts = Counter(("correct" if row[first] else "wrong") + "_" + ("correct" if row[second] else "wrong") for row in histories.values())
        paired_methods[first + "_vs_" + second] = {"paired_checkpoints": len(histories), "counts": dict(counts),
                "second_minus_first_correct": counts["wrong_correct"] - counts["correct_wrong"],
                "same_task_and_repeat_not_same_generated_history": True}
    repeat_agreement = {}
    for method in ("snapshot", "structured_state", "answer_history"):
        rows = [values for (_, m), values in repeats.items() if m == method]
        if any(len(values) != 2 for values in rows):
            raise ValueError("repeat analysis must retain both planned outcomes")
        counts = Counter("both_correct" if all(v.values()) else "both_wrong" if not any(v.values()) else "disagree" for v in rows)
        repeat_agreement[method] = {"paired_checkpoints": len(rows), "counts": dict(counts)}
    workers, prompt_lengths, output_lengths = [], [], []
    for worker in report["workers"]:
        wid = worker["worker_id"]
        batch_seconds, first_dispatch, last_return = [], None, None
        for path in sorted((run / f"worker-{wid}").glob("batches/*/started.json")):
            folder = path.parent
            started = read(path)
            intent = read(folder / "intent.json")
            prompt_lengths.extend(len(p["prompt_token_ids"]) for p in intent["prepared"])
            if first_dispatch is None:
                first_dispatch = started["at"]
            if (folder / "raw.json").exists():
                raw = read(folder / "raw.json")
                last_return = raw["at"]
                batch_seconds.append((stamp(raw["at"]) - stamp(started["at"])).total_seconds())
                output_lengths.extend(len(c["output_token_ids"]) for r in raw["results"] for c in r["candidates"])
        job = next(j for j in report["platform_jobs"] if j["worker_id"] == wid)
        allocation_seconds = ((stamp(job["complete_time"]) - stamp(job["start_time"])).total_seconds()
                              if job.get("start_time") and job.get("complete_time") else None)
        workers.append({"worker_id": wid, "job_id": job.get("job_id"), "job_state": job["state"],
                        "first_dispatch": first_dispatch, "last_return": last_return,
                        "completed_batch_seconds": sum(batch_seconds), "allocation_seconds": allocation_seconds,
                        "completed_batches": len(batch_seconds)})
    if sum(output_lengths) != report["counts"]["output_tokens"]:
        raise ValueError("actual output token accounting differs from independent extraction")
    missing_allocation = [w["worker_id"] for w in workers if w["allocation_seconds"] is None]
    observed_allocation_hours = sum(w["allocation_seconds"] or 0 for w in workers) / 3600
    result = {"schema_version": "second_model_native_descriptive_analysis_v1", "execution_id": plan["execution_id"],
              "source_report_id": report["report_id"], "model_id": plan["settings"]["model_id"],
              "counts": report["counts"], "overall_scores": report["scores"]["counts"],
              "method_scores": report["scores"]["breakdowns"]["method"], "cross_tables": dict(cross),
              "method_pairs": paired_methods, "repeat_agreement": repeat_agreement,
              "whole_trajectories": report["scores"]["whole_trajectories"], "both_repeats": report["scores"]["both_repeats"],
              "workers": workers, "prompt_tokens": {"attempted": len(prompt_lengths), "min": min(prompt_lengths, default=0),
                   "max": max(prompt_lengths, default=0), "mean": mean(prompt_lengths) if prompt_lengths else None},
              "output_tokens": {"captured": len(output_lengths), "sum": sum(output_lengths), "min": min(output_lengths, default=0),
                   "max": max(output_lengths, default=0), "mean": mean(output_lengths) if output_lengths else None,
                   "median": median(output_lengths) if output_lengths else None},
              "generation_allocation_h100_hours": observed_allocation_hours if not missing_allocation else None,
              "observed_allocation_h100_hours": observed_allocation_hours,
              "workers_with_unknown_allocation_duration": missing_allocation,
              "allocation_measurement_excludes_preflight": True, "new_model_calls": 0,
              "independent_storms": len(report["scores"]["breakdowns"]["storm"]), "population_inference": False}
    result["format_diagnostics"] = format_diagnostics(report, run)
    stopped = [read(Path(__file__).with_name(f"stopped_context_worker{i}_01.json")) for i in range(4)]
    for row in stopped:
        if row["analysis_id"] != fingerprint({k: v for k,v in row.items() if k != "analysis_id"}):
            raise ValueError("stopped context reconstruction identity differs")
    result["stopped_workers"] = stopped
    if sum(row["unattempted_after_worker_stop"] for row in stopped) != report["counts"]["unattempted"]:
        raise ValueError("stopped-worker unattempted denominator differs")
    result["planned_denominator_is_primary"] = True
    result["capture_coverage"] = report["counts"]["raw_returned"] / len(slots)
    result["strict_all_correct_rate_planned"] = report["scores"]["counts"]["all_correct"] / len(slots)
    result["strict_all_correct_rate_received_conditional"] = report["scores"]["counts"]["all_correct"] / report["counts"]["raw_returned"]
    result["analysis_id"] = fingerprint(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = analyze(args.execution, args.run_root, args.report)
    if args.verify:
        if read(args.output) != result:
            raise ValueError("saved descriptive analysis differs")
    else:
        write(args.output, result)
    print({"analysis_id": result["analysis_id"], "method_scores": result["method_scores"],
           "generation_allocation_h100_hours": result["generation_allocation_h100_hours"]}, flush=True)


if __name__ == "__main__":
    main()
