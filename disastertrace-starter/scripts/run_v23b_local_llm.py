#!/usr/bin/env python3
"""Offline, resumable local Qwen inference over frozen source-only prompts."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

JSON_OBJECT = re.compile(r"\{[^{}]*\}")


def _parse_probability(text: str):
    matches = JSON_OBJECT.findall(text)
    for candidate in reversed(matches):
        try:
            value = json.loads(candidate).get("p")
            if isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0:
                return float(value), True, None
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return None, False, "invalid_json_probability"


def _load_model(model_path: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        local_files_only=True,
        trust_remote_code=True,
        torch_dtype="auto",
        device_map="auto",
    )
    model.eval()
    return torch, tokenizer, model


def _format_prompt(tokenizer, prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    try:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def run(input_path: Path, output_path: Path, model_path: str, max_items: int | None = None) -> dict:
    torch, tokenizer, model = _load_model(model_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = set()
    if output_path.exists():
        for line in output_path.read_text().splitlines():
            try:
                completed.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    processed = skipped = invalid = 0
    started = time.time()
    with input_path.open() as source, output_path.open("a") as sink:
        for line in source:
            item = json.loads(line)
            ident = f"{item['target_id']}::{item['checkpoint_id']}"
            if ident in completed:
                skipped += 1
                continue
            if max_items is not None and processed >= max_items:
                break
            prompt = _format_prompt(tokenizer, item["prompt"])
            try:
                encoded = tokenizer(prompt, return_tensors="pt")
                device = next(model.parameters()).device
                encoded = {key: value.to(device) for key, value in encoded.items()}
                with torch.inference_mode():
                    generated = model.generate(**encoded, do_sample=False, temperature=0.0, max_new_tokens=48)
                text = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                probability, valid, error = _parse_probability(text)
            except Exception as exc:  # the row remains auditable and resumable
                text, probability, valid, error = "", None, False, f"inference_error:{type(exc).__name__}:{exc}"
            invalid += int(not valid)
            record = {
                "id": ident,
                "target_id": item["target_id"],
                "checkpoint_id": item["checkpoint_id"],
                "p": probability,
                "valid": valid,
                "error": error,
                "raw_output": text,
                "model_path": model_path,
            }
            sink.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            sink.flush()
            completed.add(ident)
            processed += 1
    return {"status": "ok", "processed": processed, "skipped_existing": skipped, "invalid": invalid, "elapsed_seconds": time.time() - started, "model_path": model_path, "output": str(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--max-items", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output, args.model_path, args.max_items), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
