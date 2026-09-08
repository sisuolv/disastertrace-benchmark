"""Descriptive paired comparison of the unchanged balanced tasks across output tracks."""

import argparse
from collections import Counter
from pathlib import Path

from disastertrace.automated.common import fingerprint, read_jsonl
from disastertrace.controlled.schema import METHODS
from disastertrace.controlled.scorer import METRICS
from disastertrace.local_eval.storage import digest, inventory, read, seal, verify_seal, write

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "p3_local_balanced_v1"


def rate_denominators(value, prefix=()):
    result = {}
    if isinstance(value, dict):
        if {"numerator", "denominator"} <= set(value):
            result[prefix] = value["denominator"]
        for key, child in value.items():
            result.update(rate_denominators(child, (*prefix, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(rate_denominators(child, (*prefix, index)))
    return result


def compare_scores(left, right):
    if rate_denominators(left) != rate_denominators(right):
        raise ValueError("metric denominators changed across tracks")

    def indexed(score):
        result = {}
        for row in score["per_checkpoint"]:
            key = (row["episode_id"], row["checkpoint_id"])
            if key in result:
                raise ValueError("duplicate checkpoint in track report")
            result[key] = row
        return result

    old, new = indexed(left), indexed(right)
    if set(old) != set(new):
        raise ValueError("checkpoint opportunities changed across tracks")
    transitions = Counter()
    by_source = {}
    for key in old:
        a, b = old[key], new[key]
        if a["group_id"] != b["group_id"]:
            raise ValueError("checkpoint source group changed")
        for denominator in {d for _, d in METRICS.values()}:
            if a["counts"][denominator] != b["counts"][denominator]:
                raise ValueError("checkpoint denominator changed")
        x, y = bool(a["counts"]["all_correct"]), bool(b["counts"]["all_correct"])
        label = (
            "both_correct"
            if x and y
            else "free_only"
            if x
            else "constrained_only"
            if y
            else "neither"
        )
        transitions[label] += 1
        by_source.setdefault(a["group_id"], Counter())[label] += 1
    return {
        "free": left["metrics"],
        "constrained": right["metrics"],
        "paired_checkpoint_outcomes": dict(transitions),
        "paired_by_source": {key: dict(value) for key, value in by_source.items()},
        "matched_checkpoints": len(old),
        "denominators_checked": len(rate_denominators(left)),
    }


def generate(free_run=None, constrained_run=None):
    old_plan = read(OLD / "execution/execution.json")
    new_plan = read(HERE / "execution_live/execution.json")
    paths = {
        old_plan["execution_id"]: Path(free_run) if free_run else Path(old_plan["run_path"]),
        new_plan["execution_id"]: Path(constrained_run)
        if constrained_run
        else Path(new_plan["run_path"]),
    }
    for root in (
        OLD / "execution",
        HERE / "execution_live",
        OLD / "model_report",
        HERE / "model_report",
    ):
        verify_seal(root)
    old_report, new_report = (
        read(OLD / "model_report/report.json"),
        read(HERE / "model_report/report.json"),
    )
    for plan, report, bundle, origin in (
        (old_plan, old_report, OLD, "local_model_vllm"),
        (new_plan, new_report, HERE, "local_model_vllm_constrained_v1"),
    ):
        audit = read(bundle / "model_report/audit.json")
        if (
            report["origin"] != origin
            or not report["complete"]
            or report["execution_id"] != plan["execution_id"]
            or report["audit_id"] != audit["audit_id"]
        ):
            raise ValueError("complete audited actual track reports required")
        if inventory(paths[plan["execution_id"]]) != audit["run_files"]:
            raise ValueError("track capture changed since independent audit")
    if new_plan["parent_execution_id"] != old_plan["execution_id"]:
        raise ValueError("wrong free-output parent")
    for key in (
        "dataset_content_id",
        "dataset_package_id",
        "model_snapshot_sha256",
        "environment_sha256",
    ):
        if new_plan[key] != old_plan[key]:
            raise ValueError("data/model/environment changed across tracks")
    for key, value in old_plan["settings"].items():
        if new_plan["settings"].get(key) != value:
            raise ValueError("parent sampling/prompt setting changed: " + key)
    for name in (
        "episodes.jsonl",
        "private/gold.jsonl",
        "schedule.jsonl",
        "parent_sources.jsonl",
        "source_bindings.json",
    ):
        if digest(OLD / "execution/dataset" / name) != digest(
            HERE / "execution_live/dataset" / name
        ):
            raise ValueError("task data bytes changed: " + name)
    for name in (
        "generator.py",
        "renderer.py",
        "compiler.py",
        "schema.py",
        "scorer.py",
        "public_oracle.py",
        "output_contract.py",
    ):
        relative = "src/disastertrace/controlled/" + name
        if old_plan["implementation_files"][relative] != new_plan["implementation_files"][relative]:
            raise ValueError("semantic implementation changed: " + name)

    def preparations(plan):
        result = {}
        for path in sorted((paths[plan["execution_id"]] / "batches").glob("*.json")):
            batch = read(path)
            for slot, request, prepared in zip(
                batch["slots"], batch["requests"], batch["prepared"]
            ):
                if slot["slot_id"] in result:
                    raise ValueError("duplicate prepared slot")
                result[slot["slot_id"]] = (slot, request, prepared)
        return result

    left, right = preparations(old_plan), preparations(new_plan)
    slots = read_jsonl(HERE / "execution_live/dataset/schedule.jsonl")
    if set(left) != set(right) or set(left) != {slot["slot_id"] for slot in slots}:
        raise ValueError("complete matched preparations required")
    prompt_equality = {m: Counter() for m in METHODS}
    for slot_id in left:
        slot, request_a, a = left[slot_id]
        other_slot, request_b, b = right[slot_id]
        if slot != other_slot:
            raise ValueError("schedule changed")
        public_a = {
            k: v for k, v in request_a.items() if k not in ("previous_state", "answer_history")
        }
        public_b = {
            k: v for k, v in request_b.items() if k not in ("previous_state", "answer_history")
        }
        if public_a != public_b or a["messages"][0] != b["messages"][0]:
            raise ValueError("public evidence or system contract changed")
        if a["sampling"] != {k: v for k, v in b["sampling"].items() if k != "guided_decoding"}:
            raise ValueError("base sampling/seed changed")
        counts = prompt_equality[slot["method"]]
        counts["planned"] += 1
        counts["same_public_evidence"] += 1
        counts["identical_prompt_tokens"] += int(a["prompt_token_ids"] == b["prompt_token_ids"])
    result = {
        "kind": "descriptive_same_model_same_balanced_tasks_separate_output_tracks",
        "free_execution_id": old_plan["execution_id"],
        "constrained_execution_id": new_plan["execution_id"],
        "free_report_sha256": digest(OLD / "model_report/report.json"),
        "constrained_report_sha256": digest(HERE / "model_report/report.json"),
        "dataset_content_id": new_plan["dataset_content_id"],
        "same_task_gold_scorer_base_sampling": True,
        "prompt_equality": {m: dict(c) for m, c in prompt_equality.items()},
        "methods": {
            m: compare_scores(old_report["methods"][m], new_report["methods"][m]) for m in METHODS
        },
        "additional_model_calls": 0,
        "causal_memory_or_general_weather_claim": False,
        "limitations": "One repeat, three dependent source groups, different collection times. "
        "Decoder intervention changes output support and subsequent model-derived carriers; "
        "shared seeds do not make samples equivalent. "
        "Concurrent CPU context calibration makes timing descriptive only.",
    }
    result["comparison_id"] = fingerprint(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--free-run", type=Path)
    parser.add_argument("--constrained-run", type=Path)
    args = parser.parse_args()
    result = generate(args.free_run, args.constrained_run)
    output = HERE / "track_comparison"
    if args.verify:
        verify_seal(output)
        if read(output / "comparison.json") != result:
            raise ValueError("track comparison reconstruction differs")
    else:
        output.mkdir(exist_ok=False)
        write(output / "comparison.json", result)
        seal(output)
    print({"status": "passed", "comparison_id": result["comparison_id"]})


if __name__ == "__main__":
    main()
