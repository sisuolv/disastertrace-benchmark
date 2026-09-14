"""Register a complete, error-informed prompt clarification without selecting errors."""

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

from disastertrace.monitoring_v1.providers.aviation import parse_metar
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from transformers import AutoTokenizer


CLARIFICATION = """
The following report-label contract examples apply uniformly to every slot:
1. A statute-mile visibility token without P or M denotes a closed single-point interval in this task, even if a sensor or outside convention could imply a ceiling. In particular, 10SM is {"lower":16093.44,"upper":16093.44,"lower_closed":true,"upper_closed":true}; do not change its upper endpoint to +inf. This defines the reported label and does not assert error-free physical visibility.
2. Use the main-body signed integer temperature/dewpoint group before RMK. For "03/M02 ... RMK ... T00331022", return temperature_c=3 and dewpoint_c=-2. Do not replace them by the more precise remarks values 3.3 or -2.2. Ignore remarks even if their measurement seems more accurate.
3. P and M censoring remains as defined above. A missing or conflicting report has null fields. These are generic examples, not reference answers for any supplied report.
""".strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    parent, out = args.parent.absolute(), args.out.absolute()
    plan = read(parent / "PLAN.json")
    if not read(parent / "final_audit_01/RESULT.json")["passed"]:
        raise ValueError("Requires the original completed model study")
    for name, sha in plan["files"].items():
        if digest(parent / name) != sha:
            raise ValueError("Original frozen study changed")
    selected = [t for t in plan["tasks"] if t["kind"] == "aviation_features"]
    if len(selected) != 84 or len({t["call_id"] for t in selected}) != 84:
        raise ValueError("Expected all original 84 extraction tasks")
    example = "KZZZ 010000Z 00000KT 10SM CLR 03/M02 A3000 RMK T00331022"
    parsed = parse_metar(
        example, observation_time="2025-01-01T00:00:00Z", report_type="routine"
    )
    expected = {
        "lower": 16093.44,
        "upper": 16093.44,
        "lower_closed": True,
        "upper_closed": True,
    }
    if (
        parsed.visibility.to_dict() != expected
        or parsed.temperature_c != 3
        or parsed.dewpoint_c != -2
    ):
        raise ValueError("Generic prompt example disagrees with the native contract")
    out.mkdir(exist_ok=False)
    publish(
        out / "QUALIFIED_EXAMPLE.json",
        {
            "raw": example,
            "visibility": expected,
            "temperature_c": 3,
            "dewpoint_c": -2,
            "not_a_benchmark_source_record": True,
        },
    )
    for name in ("banks", "source"):
        shutil.copytree(
            parent / name, out / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in ("MODEL_MANIFEST.json", "INPUTS.json", "PACKETS.json"):
        shutil.copyfile(parent / name, out / name)
    for name in ("policy", "bundles", "evaluator"):
        (out / name).mkdir()
    for name in (
        "prepare_clarified_feature_trial.py",
        "score_feature_temperature.py",
        "launch_large_feature_trial.py",
    ):
        shutil.copyfile(Path(__file__).with_name(name), out / "source" / name)
    references = read(parent / "evaluator/REFERENCES.json")
    publish(
        out / "evaluator/REFERENCES.json",
        {t["call_id"]: references[t["call_id"]] for t in selected},
    )
    tasks = []
    for task in selected:
        cid = task["call_id"]
        shutil.copyfile(
            parent / "bundles" / (cid + ".json"), out / "bundles" / (cid + ".json")
        )
        policy = read(parent / "policy" / (cid + ".json"))
        original = json.loads(json.dumps(policy))
        policy["messages"][0]["content"] += "\n\n" + CLARIFICATION
        publish(out / "policy" / (cid + ".json"), policy)
        if policy["messages"][1:] != original["messages"][1:]:
            raise ValueError("Clarification changed native evidence")
        tasks.append(
            {**task, "policy_sha256": digest(out / "policy" / (cid + ".json"))}
        )
    publish(
        out / "SELECTION.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "parent_plan_sha256": digest(parent / "PLAN.json"),
            "selection": "all84 aviation extraction units; not selected by correctness",
            "ordinary": 72,
            "outcome_selected_Denver_diagnostic": 12,
            "prompt_is_error_informed": True,
            "independent_confirmation": False,
            "same_native_evidence_and_references": True,
            "same_numeric_banks_and_scoring_rules": True,
            "change": "append one identical report-label clarification to system message",
            "output_contract_and_caps_unchanged": True,
            "original_scores_preserved": True,
            "api_calls": 0,
            "local_benchmark_calls": 84,
            "local_compatibility_calls": 1,
            "retries": 0,
            "max_simultaneous_h100": 4,
            "reason": "Separate report-label instruction interpretation from native extraction and downstream probability mapping",
        },
    )
    tokenizer = AutoTokenizer.from_pretrained(
        read(out / "MODEL_MANIFEST.json")["directory"],
        local_files_only=True,
        trust_remote_code=False,
    )
    tokens = []
    for task in tasks:
        policy = read(out / "policy" / (task["call_id"] + ".json"))
        ids = tokenizer.apply_chat_template(
            policy["messages"],
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if len(ids) + plan["max_tokens"] > plan["gpu_engine"]["max_model_len"]:
            raise ValueError("Clarified input exceeds the unchanged context bound")
        tokens.append({"call_id": task["call_id"], "input_tokens": len(ids)})
    publish(
        out / "TOKENIZER_PREFLIGHT.json",
        {"passed": True, "tasks": len(tokens), "rows": tokens},
    )
    files = {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()}
    fresh = {
        **plan,
        "schema": "disastertrace.feature_contract_clarification.v1",
        "tasks": tasks,
        "files": files,
        "local_benchmark_calls": len(tasks),
        "aviation_information_units": len(tasks),
        "temperature_targets": 0,
        "late_start_cutoff": "2026-09-14T23:20:00+00:00",
        "last_worker_time": "2026-09-15T00:30:00+00:00",
        "comparison_scope": "same-model, error-informed all-unit prompt clarification; no independent confirmation",
    }
    publish(out / "PLAN.json", fresh)
    publish(
        out / "PREFLIGHT.json",
        {
            "passed": True,
            "plan_sha256": digest(out / "PLAN.json"),
            "all_original_aviation_units": True,
            "evidence_unchanged": True,
            "scorer_qualification_required": True,
            "actual_gpu_model_rehash_required": True,
        },
    )
    print(
        json.dumps(
            {
                "registered": len(tasks),
                "max_input_tokens": max(t["input_tokens"] for t in tokens),
            }
        )
    )


if __name__ == "__main__":
    main()
