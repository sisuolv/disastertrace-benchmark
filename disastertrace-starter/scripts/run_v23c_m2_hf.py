#!/usr/bin/env python3
"""Offline v23-C M2 worker (Qwen3.8-27B via transformers)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path


def _parse(text: str):
    try:
        value = json.loads(text).get("p")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0:
            return float(value), True, None
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return None, False, "invalid_json_probability"


def run(input_path: Path, output_path: Path, model_path: str, *, shard_index: int = 0, shard_count: int = 1, max_items: int | None = None) -> dict:
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import torch
    import transformers
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForImageTextToText.from_pretrained(model_path, local_files_only=True, trust_remote_code=False, dtype=torch.bfloat16, device_map={"": "cuda:0"}, attn_implementation="sdpa")
    model.eval()
    device = next(model.parameters()).device
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = set()
    if output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            try:
                completed.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    total = invalid = skipped = 0
    started = time.time()
    with input_path.open(encoding="utf-8") as source, output_path.open("a", encoding="utf-8") as sink:
        for ordinal, line in enumerate(source):
            if ordinal % shard_count != shard_index:
                continue
            item = json.loads(line)
            ident = item["target_id"] + "::" + item["checkpoint_id"]
            if ident in completed:
                skipped += 1
                continue
            messages = [{"role": "user", "content": item["prompt"]}]
            text = ""
            try:
                tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False, return_dict=False)
                encoded = {"input_ids": torch.tensor([tokens], device=device)}
                encoded["attention_mask"] = torch.ones_like(encoded["input_ids"])
                with torch.inference_mode():
                    generated = model.generate(**encoded, do_sample=False, max_new_tokens=48)
                text = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                p, valid, error = _parse(text)
            except Exception as exc:
                p, valid, error = None, False, f"inference_error:{type(exc).__name__}:{exc}"
            invalid += int(not valid)
            sink.write(json.dumps({"id": ident, "target_id": item["target_id"], "checkpoint_id": item["checkpoint_id"], "p": p, "valid": valid, "error": error, "raw_output": text, "model_path": model_path, "worker": "v23c_m2_hf", "torch_version": torch.__version__, "transformers_version": transformers.__version__}, sort_keys=True, ensure_ascii=False) + "\n")
            sink.flush()
            completed.add(ident)
            total += 1
            if max_items is not None and total >= max_items:
                break
    return {"status": "ok", "processed": total, "skipped_existing": skipped, "invalid": invalid, "elapsed_seconds": time.time() - started, "model_path": model_path, "output": str(output_path), "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(), "shard_index": shard_index, "shard_count": shard_count}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--max-items", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output, args.model_path, shard_index=args.shard_index, shard_count=args.shard_count, max_items=args.max_items), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
