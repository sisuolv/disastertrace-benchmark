"""Freeze an identical-case second-model E diagnostic without new case selection."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent


def main(args):
    from transformers import AutoTokenizer

    parent = json.loads((args.parent / "PLAN.json").read_text())
    for name, expected in parent["files"].items():
        if digest(args.parent / name) != expected:
            raise ValueError("Original E input changed")
    check = json.loads(args.model_verification.read_text())
    if check["match"] is not True or not all(r["match"] for r in check["rows"]):
        raise ValueError("The second model has not passed its hash check")
    manifest = BASE.parents[1] / check["prior_manifest"]
    if digest(manifest) != check["prior_manifest_sha256"]:
        raise ValueError("Pinned model manifest changed")
    model_key = check["model"]
    spec = json.loads(manifest.read_text())["models"][model_key]
    if {r["path"]: r["sha256"] for r in check["rows"]} != {r["path"]: r["sha256"] for r in spec["files"]}:
        raise ValueError("Verified model file list differs")
    tokenizer = AutoTokenizer.from_pretrained(spec["directory"], local_files_only=True)
    data = json.loads((args.parent / "environment.json").read_text())
    preflight = []
    for task in parent["workers"]["0"]:
        condition = task["config"]["condition"]
        for case in data["cases"]:
            messages = [{"role": "system", "content": data["systems"][condition]},
                {"role": "user", "content": json.dumps(case["requests"][condition], separators=(",", ":"))}]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            n = len(tokenizer(text, add_special_tokens=False)["input_ids"])
            if n > task["config"]["input_token_cap"]:
                raise ValueError("Second model tokenizer exceeds the fixed input cap")
            preflight.append({"condition": condition, "case_id": case["case_id"], "input_tokens": n})
    args.output.mkdir(exist_ok=False)
    for name in ("environment.json", "BANK.json"):
        shutil.copyfile(args.parent / name, args.output / name)
    shutil.copytree(args.parent / "source", args.output / "source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    worker = args.output / "source/gpu_worker.py"
    text = worker.read_text()
    if text.count("AutoModelForCausalLM") != 2:
        raise ValueError("Unexpected model loader adapter")
    worker.write_text(text.replace("AutoModelForCausalLM", "Qwen3VLForConditionalGeneration"))
    shutil.copyfile(__file__, args.output / "source/freeze_second_e_model.py")
    save(args.output / "TOKENIZER_PREFLIGHT.json", preflight)
    save(args.output / "MODEL_VERIFICATION.json", check)
    plan = {**parent, "frozen_at": datetime.now(timezone.utc).isoformat(),
        "cci_hostname": socket.gethostname(), "models": {model_key: spec},
        "worker_models": {"0": model_key}, "max_worker_seconds": 2400,
        "runtime_versions": {name: version(name) for name in parent["runtime_versions"]},
        "parent_case_freeze": str(args.parent), "parent_plan_sha256": digest(args.parent / "PLAN.json"),
        "case_messages_byte_identical": digest(args.output / "environment.json") == digest(args.parent / "environment.json"),
        "files": {str(p.relative_to(args.output)): digest(p) for p in args.output.rglob("*") if p.is_file()},
        "interpretation": "Same 96 real E cases and four fixed representations as the 8B diagnostic, now Qwen3-VL-32B using text inputs only. No adaptive case selection, F outcome scoring, image gain claim, or active-policy result."}
    save(args.output / "PLAN.json", plan)
    print(json.dumps({"model": model_key, "cases": len(data["cases"]), "calls": plan["maximum_model_calls"],
        "max_input_tokens": max(r["input_tokens"] for r in preflight), "same_case_messages": plan["case_messages_byte_identical"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=BASE / "gpu_e_diagnostic_01")
    parser.add_argument("--model-verification", type=Path, default=BASE / "MODEL32_VERIFICATION_01.json")
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
