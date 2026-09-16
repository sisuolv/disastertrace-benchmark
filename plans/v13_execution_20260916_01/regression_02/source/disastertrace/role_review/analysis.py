"""Reconstruct six-storm reports and label single-repeat reliability explicitly."""

import importlib
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median

from disastertrace.forecast_task.common import fingerprint, read
from disastertrace.forecast_task.contract import parse_answer
from disastertrace.forecast_task.scoring import _totals

TRACKS = {"deepseek_user": "prompt_role_live", "qwen_user": "qwen_role_live"}
METHODS = ("snapshot", "structured_state", "answer_history")


def single_repeat_targets(slots, scores):
    if not slots or any(s["repeat"] != 0 for s in slots):
        raise ValueError("this analysis requires exactly repeat0")
    if len({s["slot_id"] for s in slots}) != len(slots) or set(scores) != {
        s["slot_id"] for s in slots
    }:
        raise ValueError("score coverage or unique slot identity differs")
    targets = defaultdict(list)
    for slot in slots:
        targets[slot["method"], slot["episode_id"]].append(scores[slot["slot_id"]])
    result = {}
    for method in sorted({s["method"] for s in slots}):
        rows = [values for (m, _), values in targets.items() if m == method]
        result[method] = {
            "planned_targets": len(rows),
            "whole_target_single_repeat": sum(all(r["all_correct"] for r in v) for v in rows),
            "fully_captured_targets": sum(all(r["received"] for r in v) for v in rows),
        }
    return result


def distribution(values):
    return {
        "count": len(values),
        "sum": sum(values),
        "min": min(values, default=None),
        "max": max(values, default=None),
        "mean": mean(values) if values else None,
        "median": median(values) if values else None,
    }


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def analyze(track, execution, run, report_path):
    namespace = TRACKS[track]
    package = importlib.import_module("disastertrace." + namespace + ".package")
    audit = importlib.import_module("disastertrace." + namespace + ".audit")
    execution, run = Path(execution), Path(run)
    plan, public, slots = package.verify(execution, code=True)
    actual = audit.aggregate(execution, run)
    if plan["kind"] != "model" or actual != read(report_path):
        raise ValueError("analysis requires a reconstructable actual model report")
    scores = {r["slot_id"]: r["score"] for r in actual["scores"]["records"]}
    private = read(execution / "task/data/private_reference.json")
    groups, combined, score_rows = defaultdict(list), {}, []
    for slot in slots:
        query = public["opportunities"][slot["opportunity_id"]]["query"]
        reference = private["references"][slot["opportunity_id"]]
        score = scores[slot["slot_id"]]
        for dimension, value in (
            ("storm", query["storm_id"]),
            ("status", reference["answer"]["status"]),
            ("transition", reference["transition"]),
        ):
            groups[dimension, value, slot["method"]].append(score)
        score_rows.append(
            {
                "slot_id": slot["slot_id"],
                "opportunity_id": slot["opportunity_id"],
                "episode_id": slot["episode_id"],
                "method": slot["method"],
                "storm_id": query["storm_id"],
                "score": score,
            }
        )
    for (dimension, value, method), rows in sorted(groups.items()):
        combined.setdefault(dimension, {}).setdefault(value, {})[method] = _totals(rows)
    for dimension in combined.values():
        totals = [v for methods in dimension.values() for v in methods.values()]
        if (
            sum(r["planned"] for r in totals) != len(slots)
            or sum(r["all_correct"] for r in totals) != actual["scores"]["counts"]["all_correct"]
        ):
            raise ValueError("descriptive partition does not reconstruct full score")
    targets = single_repeat_targets(slots, scores)
    for method, result in targets.items():
        old = actual["scores"]["both_repeats"][method]
        if (
            result["planned_targets"] != old["planned_episodes"]
            or result["whole_target_single_repeat"] != old["all_checkpoints_both_repeats_correct"]
        ):
            raise ValueError("single-repeat reconstruction differs from frozen report")
    lengths, prompts, whitespace, unit_strings = [], [], [], defaultdict(Counter)
    by_finish, finish, worker_rows = defaultdict(Counter), {}, []
    for worker in actual["workers"]:
        wid = worker["worker_id"]
        for path in sorted((run / f"worker-{wid}").glob("batches/*/started.json")):
            intent = read(path.with_name("intent.json"))
            prompts.extend(len(i["prompt_token_ids"]) for i in intent["prepared"])
            raw_path = path.with_name("raw.json")
            if raw_path.exists():
                for result in read(raw_path)["results"]:
                    for candidate in result["candidates"]:
                        lengths.append(len(candidate["output_token_ids"]))
                        finish[result["attempt_id"]] = candidate["finish_reason"]
        for capture in worker["captures"]:
            text = capture["final_text"] or ""
            whitespace.append(sum(ch.isspace() for ch in text))
            shape = "shape_invalid"
            try:
                answer = parse_answer(text)
            except (ValueError, TypeError):
                pass
            else:
                shape = "shape_valid"
                for field in ("latitude", "longitude", "max_sustained_wind"):
                    unit_strings[field][answer[field]["unit"]] += 1
            by_finish[finish[capture["attempt_id"]]][shape] += 1
        job = next(j for j in actual["platform_jobs"] if j["worker_id"] == wid)
        seconds = (
            (stamp(job["complete_time"]) - stamp(job["start_time"])).total_seconds()
            if job.get("complete_time") and job.get("start_time")
            else None
        )
        worker_rows.append(
            {
                "worker_id": wid,
                "planned": worker["planned"],
                "attempted": worker["attempted"],
                "returned": worker["raw_returned"],
                "status": worker["status"],
                "completion": worker["completion"],
                "job": job,
                "allocation_seconds": seconds,
            }
        )
    if sum(lengths) != actual["counts"]["output_tokens"]:
        raise ValueError("raw token accounting differs")
    matched = [
        {
            k: s[k]
            for k in (
                "slot_id",
                "seed",
                "method",
                "repeat",
                "episode_id",
                "opportunity_id",
                "worker_id",
            )
        }
        for s in slots
    ]
    result = {
        "schema_version": "role_descriptive_review_v1",
        "track": track,
        "execution_id": plan["execution_id"],
        "report_id": actual["report_id"],
        "model_profile": plan["model_profile"],
        "settings": plan["settings"],
        "task_package_id": plan["task_package_id"],
        "resource_package_id": plan["resource_package_id"],
        "matched_schedule_sha256": fingerprint(matched),
        "counts": actual["counts"],
        "score_counts": actual["scores"]["counts"],
        "methods": actual["scores"]["breakdowns"]["method"],
        "cross_tables": combined,
        "targets": targets,
        "records": score_rows,
        "workers": worker_rows,
        "prompt_tokens": distribution(prompts),
        "output_tokens": distribution(lengths),
        "whitespace_characters": distribution(whitespace),
        "whitespace_includes_inside_strings": True,
        "observed_unit_strings": {f: dict(sorted(c.items())) for f, c in unit_strings.items()},
        "shape_by_finish": {f: dict(c) for f, c in by_finish.items()},
        "finish_reasons": actual["finish_reasons"],
        "generation_h100_hours": sum(w["allocation_seconds"] for w in worker_rows) / 3600
        if all(w["allocation_seconds"] is not None for w in worker_rows)
        else None,
        "storm_macro_accuracy_by_method": {
            m: mean(row[m]["all_correct"] / row[m]["planned"] for row in combined["storm"].values())
            for m in METHODS
        },
        "single_repeat_only": True,
        "storm_groups": len(combined["storm"]),
        "planned_denominator_is_primary": True,
        "population_inference": False,
        "unit_normalization": False,
        "new_model_calls": 0,
    }
    result["analysis_id"] = fingerprint(result)
    return result


def compare(before, after):
    for analysis in (before, after):
        if analysis["analysis_id"] != fingerprint(
            {k: v for k, v in analysis.items() if k != "analysis_id"}
        ):
            raise ValueError("analysis identity differs")
    expected = {"deepseek_r1": "deepseek_user", "qwen3": "qwen_user"}
    if before["track"] != "default_spacing" or after["track"] != expected.get(
        after["model_profile"]
    ):
        raise ValueError("role comparison requires the registered model/track pairing")
    for key in (
        "task_package_id",
        "resource_package_id",
        "model_profile",
        "matched_schedule_sha256",
    ):
        if before[key] != after[key]:
            raise ValueError("comparison pairing differs: " + key)
    if (
        before["settings"]
        != {k: v for k, v in after["settings"].items() if k != "prompt_role_policy"}
        or after["settings"].get("prompt_role_policy") != "system_contract_prepended_to_user_v1"
    ):
        raise ValueError("role comparison changed other model settings")
    mapping = {r["slot_id"]: r for r in after["records"]}
    if len({r["slot_id"] for r in before["records"]}) != len(before["records"]):
        raise ValueError("system-role analysis contains duplicate slots")
    if len(mapping) != len(after["records"]) or set(mapping) != {
        r["slot_id"] for r in before["records"]
    }:
        raise ValueError("comparison lacks complete unique slot pairing")
    groups = defaultdict(Counter)
    for left in before["records"]:
        right = mapping[left["slot_id"]]
        if any(left[k] != right[k] for k in ("opportunity_id", "episode_id", "method", "storm_id")):
            raise ValueError("paired source identity differs")
        for group in (
            "all",
            "method/" + left["method"],
            "storm/" + left["storm_id"],
            "storm_method/" + left["storm_id"] + "/" + left["method"],
        ):
            c = groups[group]
            c["planned"] += 1
            for metric in (
                "received",
                "shape_valid",
                "key_correct",
                "status_correct",
                "current_source",
                "locator_correct",
                "all_correct",
            ):
                c["system_" + metric] += left["score"][metric]
                c["user_" + metric] += right["score"][metric]
            label = (
                ("correct" if left["score"]["all_correct"] else "wrong")
                + "_"
                + ("correct" if right["score"]["all_correct"] else "wrong")
            )
            c["pair_" + label] += 1
    tables = {
        name: {
            **dict(v),
            "all_correct_difference": v["user_all_correct"] - v["system_all_correct"],
            "all_correct_difference_percentage_points": 100
            * (v["user_all_correct"] - v["system_all_correct"])
            / v["planned"],
        }
        for name, v in sorted(groups.items())
    }
    result = {
        "schema_version": "cohort_role_track_comparison_v1",
        "model_profile": before["model_profile"],
        "system_analysis_id": before["analysis_id"],
        "user_analysis_id": after["analysis_id"],
        "paired_tables": tables,
        "planned_denominator_is_primary": True,
        "same_task_seeds_and_worker_assignment": True,
        "same_generated_histories": False,
        "shared_prefix_causal_effect": False,
        "failure_driven_development": True,
        "single_repeat_only": True,
        "population_inference": False,
        "new_model_calls": 0,
    }
    result["comparison_id"] = fingerprint(result)
    return result
