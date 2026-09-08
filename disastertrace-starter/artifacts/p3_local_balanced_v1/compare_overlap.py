"""Descriptive comparison only on the exact 18 historical episodes shared by both runs."""

import argparse
from pathlib import Path

from disastertrace.automated.common import fingerprint, read_jsonl
from disastertrace.controlled.scorer import METRICS
from disastertrace.local_eval.storage import digest, read, seal, verify_seal, write

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "p2_deepseek_output_contract_v2"


def matched_metrics(old_episodes, new_episodes, old_score, new_score):
    old_ids = {e["episode_id"] for e in old_episodes}
    new_by_id = {e["episode_id"]: e for e in new_episodes}
    if len(old_ids) != len(old_episodes) or len(new_by_id) != len(new_episodes):
        raise ValueError("duplicate episode")
    if any(new_by_id.get(e["episode_id"]) != e for e in old_episodes):
        raise ValueError("shared episode semantics differ")
    planned = {
        (ep["episode_id"], cp["checkpoint_id"]) for ep in old_episodes for cp in ep["checkpoints"]
    }
    left, right = {}, {}
    for source, destination in ((old_score, left), (new_score, right)):
        for row in source["per_checkpoint"]:
            key = (row["episode_id"], row["checkpoint_id"])
            if row["episode_id"] in old_ids:
                if key in destination:
                    raise ValueError("duplicate checkpoint")
                destination[key] = row
        if set(destination) != planned:
            raise ValueError("shared opportunities missing or extra")
    for key in planned:
        for denominator in {d for _, d in METRICS.values()}:
            if left[key]["counts"][denominator] != right[key]["counts"][denominator]:
                raise ValueError("shared checkpoint denominator differs")

    def metrics(rows):
        return {
            name: {
                "numerator": sum(r["counts"][n] for r in rows.values()),
                "denominator": sum(r["counts"][d] for r in rows.values()),
            }
            for name, (n, d) in METRICS.items()
        }

    return {
        "historical_deepseek": metrics(left),
        "current_qwen_shared_subset": metrics(right),
        "matched_checkpoints": len(planned),
    }


def generate():
    old_report_root = OLD / "runtime/report"
    verify_seal(old_report_root)
    verify_seal(HERE / "model_report")
    old_report = read(old_report_root / "report.json")
    new_report = read(HERE / "model_report/report.json")
    new_plan = read(HERE / "execution/execution.json")
    if (
        old_report["mode"] != "model_http"
        or new_report["origin"] != "local_model_vllm"
        or new_report["execution_id"] != new_plan["execution_id"]
        or old_report["output_contract"] != new_plan["settings"]["output_contract"]
    ):
        raise ValueError("matching actual model origins and common output contract required")
    if not old_report["complete"] or not new_report["complete"]:
        raise ValueError("complete reports required")
    old_data = OLD / "execution/dataset"
    new_data = HERE / "execution/dataset"
    old_episodes, new_episodes = (
        read_jsonl(old_data / "episodes.jsonl"),
        read_jsonl(new_data / "episodes.jsonl"),
    )
    for name in (
        "generator.py",
        "renderer.py",
        "compiler.py",
        "schema.py",
        "scorer.py",
        "public_oracle.py",
    ):
        key = "src/disastertrace/controlled/" + name
        if digest(old_data / "implementation_source" / key) != digest(
            HERE / "execution/implementation_source" / key
        ):
            raise ValueError("shared task/scoring source differs")
    old_gold = read_jsonl(old_data / "private/gold.jsonl")
    new_gold = {
        (r["episode_id"], r["checkpoint_id"]): r
        for r in read_jsonl(new_data / "private/gold.jsonl")
    }
    if any(new_gold.get((r["episode_id"], r["checkpoint_id"])) != r for r in old_gold):
        raise ValueError("shared Gold differs")
    result = {
        "kind": "descriptive_exact_legacy_overlap_not_balanced_model_ranking",
        "selection_rule": "All 18 historical episodes; membership fixed before local outputs",
        "legacy_episodes": len(old_episodes),
        "legacy_requests_per_model": 270,
        "old_execution_id": old_report["execution_id"],
        "new_execution_id": new_report["execution_id"],
        "old_report_sha256": digest(old_report_root / "report.json"),
        "new_report_sha256": digest(HERE / "model_report/report.json"),
        "same_task_gold_and_scoring": True,
        "same_collection_time_or_sampling": False,
        "causal_or_general_ranking_claim": False,
        "methods": {
            m: matched_metrics(
                old_episodes, new_episodes, old_report["methods"][m], new_report["methods"][m]
            )
            for m in old_report["methods"]
        },
        "limitations": "Old source/case confounding remains within this subset; one repeat, "
        "different collection times, tokenizers, reasoning/sampling and model sizes. "
        "The full 540-version still has only one evaluated model.",
    }
    result["comparison_id"] = fingerprint(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = generate()
    output = HERE / "legacy_overlap"
    if args.verify:
        verify_seal(output)
        if read(output / "comparison.json") != result:
            raise ValueError("overlap comparison reconstruction differs")
    else:
        output.mkdir(exist_ok=False)
        write(output / "comparison.json", result)
        seal(output)
    print({"status": "passed", "comparison_id": result["comparison_id"], "requests_each": 270})
