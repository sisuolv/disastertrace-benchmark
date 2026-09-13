"""One-use fixed-snapshot inference; no evaluator labels or retrieval tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import socket
import time
import traceback
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main(args):
    batch = args.batch.resolve()
    output = batch / ("worker-" + args.worker)
    output.mkdir(exist_ok=False)
    total_calls = 0
    try:
        if digest(batch / "PLAN.json") != args.plan_sha:
            raise ValueError("Plan changed after submission")
        plan = json.loads((batch / "PLAN.json").read_text())
        for name, expected in plan["files"].items():
            if digest(batch / name) != expected:
                raise ValueError("Frozen input changed: " + name)
        runtime = {name: version(name) for name in plan["runtime_versions"]}
        if runtime != plan["runtime_versions"]:
            raise ValueError("Runtime changed")
        spec = plan["model"]
        for item in spec["files"]:
            path = Path(spec["directory"]) / item["path"]
            if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
                raise ValueError("Model file changed: " + item["path"])

        import torch
        from disastertrace.monitoring_fixed_v1.heads import model_messages
        from disastertrace.monitoring_fixed_v1.contracts import (
            EvidenceBundle,
            fingerprint,
        )
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.cuda.device_count() != 1:
            raise ValueError("Exactly one visible GPU required")
        props = torch.cuda.get_device_properties(0)
        if "H100" not in props.name or props.total_memory < 75 * 1024**3:
            raise ValueError("Full H10080GB required")
        torch.set_num_threads(4)
        torch.manual_seed(plan["seed"])
        save(
            output / "HARDWARE.json",
            {
                "name": props.name,
                "bytes": props.total_memory,
                "count": 1,
                "hostname": socket.gethostname(),
                "runtime_versions": runtime,
                "model_files_verified": True,
                "cci_hostname": plan["cci_hostname"],
            },
        )
        tokenizer = AutoTokenizer.from_pretrained(
            spec["directory"], local_files_only=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            spec["directory"],
            local_files_only=True,
            torch_dtype=torch.bfloat16,
            device_map={"": "cuda:0"},
            attn_implementation="sdpa",
        ).eval()
        save(output / "PREFLIGHT.json", {"model_loaded": True, "generation_calls": 0})
        started = time.monotonic()
        totals = {"input_tokens": 0, "output_tokens": 0}
        for item in plan["workers"][args.worker]:
            if total_calls >= plan["max_calls_per_worker"]:
                raise ValueError("Frozen call cap exceeded")
            call_id = item["call_id"]
            bundle = EvidenceBundle.restore(
                json.loads((batch / "policy" / (call_id + ".json")).read_text())
            )
            messages = model_messages(bundle, item["head"])
            if fingerprint(messages) != item["messages_sha256"]:
                raise ValueError("Message binding changed")
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            inputs = tokenizer(rendered, return_tensors="pt", add_special_tokens=False)
            n = int(inputs["input_ids"].shape[-1])
            if (
                n != item["input_tokens"]
                or n + plan["max_new_tokens"] > plan["context_limit"]
            ):
                raise ValueError("Input tokens differ from CPU qualification")
            call_started = time.monotonic()
            wall_started_ns = time.time_ns()
            save(
                output / (call_id + "-request.json"),
                {
                    "messages": messages,
                    "messages_sha256": item["messages_sha256"],
                    "input_ids": inputs["input_ids"][0].tolist(),
                    "input_tokens": n,
                    "bundle_hash": bundle.bundle_hash,
                    "plan_sha256": args.plan_sha,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
            total_calls += 1
            inputs = {k: v.to("cuda:0") for k, v in inputs.items()}
            torch.cuda.synchronize()
            inference_started = time.monotonic()
            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=plan["max_new_tokens"],
                    do_sample=False,
                    max_time=plan["max_generation_seconds"],
                    pad_token_id=tokenizer.eos_token_id,
                )
            torch.cuda.synchronize()
            inference_seconds = time.monotonic() - inference_started
            ids = generated[0, n:].tolist()
            raw = tokenizer.decode(ids, skip_special_tokens=True)
            completed_elapsed_us = max(1, math.ceil((time.monotonic() - call_started) * 1_000_000))
            eos = model.generation_config.eos_token_id
            eos = eos if isinstance(eos, list) else [eos]
            save(
                output / (call_id + "-response.json"),
                {
                    "call_id": call_id,
                    "raw": raw,
                    "output_ids": ids,
                    "input_tokens": n,
                    "output_tokens": len(ids),
                    "seconds": time.monotonic() - call_started,
                    "inference_seconds": inference_seconds,
                    "ended_with_eos": bool(ids and ids[-1] in eos),
                    "bundle_hash": bundle.bundle_hash,
                    "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "plan_sha256": args.plan_sha,
                },
            )
            persisted_elapsed_us = max(completed_elapsed_us, math.ceil((time.monotonic() - call_started) * 1_000_000))
            save(output / (call_id + "-commit.json"), {
                "schema": "disastertrace.smoke_response_commit.v1",
                "call_id": call_id, "head": item["head"],
                "bundle_hash": bundle.bundle_hash, "plan_sha256": args.plan_sha,
                "request_sha256": digest(output / (call_id + "-request.json")),
                "response_sha256": digest(output / (call_id + "-response.json")),
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "wall_started_ns": wall_started_ns,
                "wall_after_response_fsync_ns": time.time_ns(),
                "logical_started_at": item["logical_started_at"],
                "completed_elapsed_us": completed_elapsed_us,
                "persisted_elapsed_us": persisted_elapsed_us,
                "origin": "actual_local_model; measured duration mapped to declared archive clock",
            })
            totals["input_tokens"] += n
            totals["output_tokens"] += len(ids)
            print(
                json.dumps(
                    {
                        "calls": total_calls,
                        "call_id": call_id,
                        "seconds": time.monotonic() - call_started,
                    }
                ),
                flush=True,
            )
        save(
            output / "COMPLETE.json",
            {
                "model_calls": total_calls,
                **totals,
                "seconds_after_load": time.monotonic() - started,
                "plan_sha256": args.plan_sha,
            },
        )
    except Exception:
        save(
            output / "FAILED.json",
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "attempted_calls": total_calls,
                "traceback": traceback.format_exc(),
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--plan-sha", required=True)
    parser.add_argument("--worker", required=True)
    main(parser.parse_args())
