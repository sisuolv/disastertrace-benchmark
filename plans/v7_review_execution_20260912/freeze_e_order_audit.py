"""Freeze counterbalanced reruns of unchanged E-only and fact-table messages."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent


def main(args):
    from transformers import AutoTokenizer

    parent = json.loads((args.parent / "PLAN.json").read_text())
    checked = json.loads(args.verification.read_text())
    if digest(args.parent / "PLAN.json") != checked["plan_sha256"]:
        raise ValueError("Parent diagnostic has no matching completed audit")
    for name, expected in parent["files"].items():
        if digest(args.parent / name) != expected:
            raise ValueError("Parent diagnostic input changed")
    args.output.mkdir(exist_ok=False)
    data = json.loads((args.parent / "environment.json").read_text())
    if data["systems"]["E_only"] != data["systems"]["E_fact_table"]:
        raise ValueError("The paired E conditions must have identical system/output instructions")
    if len(data["cases"]) != 96 or len({c["case_id"] for c in data["cases"]}) != 96:
        raise ValueError("Unexpected exposed-development case set")
    original_messages = {
        (c["case_id"], condition): json.dumps(c["requests"][condition], separators=(",", ":"))
        for c in data["cases"] for condition in ("E_only", "E_fact_table")
    }
    random.Random(args.order_seed).shuffle(data["cases"])
    order = ("E_only", "E_fact_table") if args.condition_order == "ab" else ("E_fact_table", "E_only")
    specs = parent["models"]
    model = parent["worker_models"]["0"]
    tokenizer = AutoTokenizer.from_pretrained(specs[model]["directory"], local_files_only=True)
    tasks, preflight = [], []
    original_tasks = {t["config"]["condition"]: t for t in parent["workers"]["0"]}
    for condition in order:
        config = dict(original_tasks[condition]["config"])
        tasks.append({"run_id": condition, "data_file": "environment.json", "config": config})
        for case in data["cases"]:
            request = json.dumps(case["requests"][condition], separators=(",", ":"))
            if request != original_messages[case["case_id"], condition]:
                raise ValueError("A case message changed while reordering")
            messages = [{"role": "system", "content": data["systems"][condition]},
                        {"role": "user", "content": request}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            n = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
            if n > config["input_token_cap"]:
                raise ValueError("Reordered diagnostic exceeds original input bound")
            preflight.append({"case_id": case["case_id"], "condition": condition, "input_tokens": n})
    save(args.output / "environment.json", data)
    shutil.copyfile(args.parent / "BANK.json", args.output / "BANK.json")
    shutil.copytree(args.parent / "source", args.output / "source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(__file__, args.output / "source/freeze_e_order_audit.py")
    shutil.copyfile(BASE / "E_ORDER_AUDIT_PROTOCOL_CN.md", args.output / "E_ORDER_AUDIT_PROTOCOL_CN.md")
    save(args.output / "TOKENIZER_PREFLIGHT.json", preflight)
    plan = {**parent, "frozen_at": datetime.now(timezone.utc).isoformat(),
            "cci_hostname": socket.gethostname(), "workers": {"0": tasks},
            "maximum_model_calls": 192, "max_calls_per_worker": 192,
            "max_worker_seconds": 2400, "parent_case_freeze": str(args.parent.resolve()),
            "parent_plan_sha256": digest(args.parent / "PLAN.json"),
            "parent_verification_sha256": digest(args.verification),
            "case_messages_byte_identical": True,
            "case_order_seed": args.order_seed, "condition_order": list(order),
            "new_generation_settings": False,
            "interpretation": "Post-hoc development execution-order audit: unchanged 96 E-only/fact-table messages and greedy generation, two case permutations and reversed condition order. No new case selection, prompt tuning, F result, independent-weather sample, stochastic-repeat CI or formal isolated-effect guarantee.",
            "files": {str(p.relative_to(args.output)): digest(p) for p in args.output.rglob("*") if p.is_file()}}
    save(args.output / "PLAN.json", plan)
    print(json.dumps({"model": model, "maximum_calls": 192, "same_case_messages": True,
                      "case_order_seed": args.order_seed, "condition_order": list(order)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--condition-order", choices=["ab", "ba"], required=True)
    parser.add_argument("--order-seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
