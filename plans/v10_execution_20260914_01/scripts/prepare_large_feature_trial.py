"""Bind the already available 235B model to all frozen 212 feature/F tasks."""

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from transformers import AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out, parent = args.out.absolute(), args.parent.absolute()
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    previous = (
        root / "plans/v8_measurement_execution_20260913_01/gpu/large_diagnostic_02"
    )
    basis = read(previous / "PLAN.json")
    parent_plan = read(parent / "PLAN.json")
    for rel, sha in parent_plan["files"].items():
        if digest(parent / rel) != sha:
            raise ValueError("Paired parent inputs changed")
    for name in ("policy", "bundles", "evaluator", "banks", "source"):
        shutil.copytree(
            parent / name, out / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in (
        "score_feature_temperature.py",
        "finalize_feature_temperature.py",
        "qwen235_feature_worker.py",
        "prepare_large_feature_trial.py",
    ):
        shutil.copyfile(Path(__file__).parent / name, out / "source" / name)
    for name in ("PACKETS.json", "INPUTS.json"):
        shutil.copyfile(parent / name, out / name)
    registration = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "parent_plan_sha256": digest(parent / "PLAN.json"),
        "same_all_registered_212_tasks": True,
        "label_or_model_response_selection": False,
        "api_calls": 0,
        "reason": "DeepSeek compatibility returned402; extend same tasks with qualified local235B model",
        "quantization": "FP8",
        "comparison": "architecture/training/quantization differ; not a parameter-count causal effect",
        "previous_launch_reopened": False,
        "confirmation_opened": False,
        "max_simultaneous_h100": 4,
    }
    publish(out / "SELECTION.json", registration)
    model = basis["models"]["qwen235b_fp8"]
    publish(out / "MODEL_MANIFEST.json", model)
    tokenizer = AutoTokenizer.from_pretrained(
        model["directory"], local_files_only=True, trust_remote_code=False
    )
    tokens = []
    for task in parent_plan["tasks"]:
        payload = read(out / "policy" / (task["call_id"] + ".json"))
        ids = tokenizer.apply_chat_template(
            payload["messages"],
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if len(ids) + parent_plan["max_tokens"] > 32768:
            raise ValueError("Frozen task exceeds local context allowance")
        tokens.append({"call_id": task["call_id"], "input_tokens": len(ids)})
    publish(
        out / "TOKENIZER_PREFLIGHT.json",
        {
            "passed": True,
            "tasks": len(tokens),
            "max_input_tokens": max(t["input_tokens"] for t in tokens),
            "rows": tokens,
        },
    )
    files = {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()}
    plan = {
        **parent_plan,
        "schema": "disastertrace.feature_temperature_local235.v1",
        "files": files,
        "local_model": model["name"],
        "api_models": [],
        "api_workers": 0,
        "api_benchmark_calls": 0,
        "api_compatibility_calls": 0,
        "api_limit_usd": 0,
        "api_escrow_upper_nanodollars": 0,
        "local_compatibility_calls": 1,
        "gpu_worker_source": "source/qwen235_feature_worker.py",
        "gpu_runtime": basis["runtime_versions"],
        "gpu_engine": {**basis["engine"], "max_model_len": 32768},
        "batch_size": 4,
        "comparison_scope": "paired stronger local model development; unchanged input/evaluator/numerical backends",
    }
    publish(out / "PLAN.json", plan)
    publish(
        out / "PREFLIGHT.json",
        {
            "passed": True,
            "plan_sha256": digest(out / "PLAN.json"),
            "policy_identity_with_parent": True,
            "actual_gpu_model_rehash_required": True,
            "scorer_qualification_required": True,
        },
    )
    print(
        json.dumps(
            {
                "tasks": len(tokens),
                "max_input_tokens": max(t["input_tokens"] for t in tokens),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
