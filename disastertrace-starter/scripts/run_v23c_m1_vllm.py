#!/usr/bin/env python3
"""Offline v23-C M1 worker (Qwen3-8B via vLLM)."""

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


def run(input_path: Path, output_path: Path, model_path: str, *, batch_size: int = 32, max_items: int | None = None) -> dict:
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    from vllm import LLM, SamplingParams

    llm = LLM(model=model_path, dtype="bfloat16", max_model_len=4096, gpu_memory_utilization=0.85, enforce_eager=True, seed=20260927)
    tokenizer = llm.get_tokenizer()
    sampling = SamplingParams(temperature=0.0, max_tokens=48)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = set()
    if output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            try:
                completed.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    pending = []
    total = invalid = skipped = 0
    started = time.time()

    def flush(items):
        nonlocal total, invalid
        if not items:
            return
        prompts = []
        for item in items:
            messages = [{"role": "user", "content": item["prompt"]}]
            prompts.append(tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False))
        outputs = llm.generate(prompts, sampling, use_tqdm=False)
        with output_path.open("a", encoding="utf-8") as sink:
            for item, result in zip(items, outputs, strict=True):
                text = result.outputs[0].text.strip() if result.outputs else ""
                p, valid, error = _parse(text)
                invalid += int(not valid)
                sink.write(json.dumps({"id": item["target_id"] + "::" + item["checkpoint_id"], "target_id": item["target_id"], "checkpoint_id": item["checkpoint_id"], "p": p, "valid": valid, "error": error, "raw_output": text, "model_path": model_path, "worker": "v23c_m1_vllm"}, sort_keys=True, ensure_ascii=False) + "\n")
                total += 1
            sink.flush()

    with input_path.open(encoding="utf-8") as source:
        for line in source:
            item = json.loads(line)
            ident = item["target_id"] + "::" + item["checkpoint_id"]
            if ident in completed:
                skipped += 1
                continue
            pending.append(item)
            if len(pending) >= batch_size:
                flush(pending); pending = []
            if max_items is not None and total >= max_items:
                break
    flush(pending)
    return {"status": "ok", "processed": total, "skipped_existing": skipped, "invalid": invalid, "elapsed_seconds": time.time() - started, "model_path": model_path, "output": str(output_path), "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-items", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output, args.model_path, batch_size=args.batch_size, max_items=args.max_items), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
