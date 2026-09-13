"""Frozen one-use monitoring worker; evaluation outcomes are not in its package."""

from __future__ import annotations

import argparse
import hashlib
import json
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
            raise ValueError("Runtime differs from the preflight environment")
        spec = plan["models"][plan["worker_models"][args.worker]]
        for item in spec["files"]:
            path = Path(spec["directory"]) / item["path"]
            if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
                raise ValueError("Pinned model changed: " + item["path"])

        import torch
        from disastertrace.monitoring_v1.journal import EventJournal
        from disastertrace.monitoring_v1.policies import run_session
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.cuda.device_count() != 1:
            raise ValueError("Exactly one visible GPU required")
        props = torch.cuda.get_device_properties(0)
        if "H100" not in props.name or props.total_memory < 75 * 1024**3:
            raise ValueError("A full H100 80GB is required")
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
                "cci_hostname": plan["cci_hostname"],
                "model_files_verified": True,
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
        bank = json.loads((batch / "BANK.json").read_text())
        worker_started = time.monotonic()
        completed = 0
        for task in plan["workers"][args.worker]:
            task_dir = output / task["run_id"]
            task_dir.mkdir()
            data = json.loads((batch / task["data_file"]).read_text())

            def backend(system, request, call_id, task=task, task_dir=task_dir):
                nonlocal total_calls
                if total_calls >= plan["max_calls_per_worker"]:
                    raise RuntimeError("Frozen model-call cap reached")
                total_calls += 1
                started = time.monotonic()
                messages = [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": json.dumps(request, separators=(",", ":")),
                    },
                ]
                rendered = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                inputs = tokenizer(
                    rendered, return_tensors="pt", add_special_tokens=False
                )
                input_tokens = int(inputs["input_ids"].shape[-1])
                if input_tokens > task["config"]["input_token_cap"]:
                    raise RuntimeError(
                        "Input token reservation exceeded before generation"
                    )
                if input_tokens + plan["max_new_tokens"] > plan["context_limit"]:
                    raise RuntimeError("Context reservation exceeded before generation")
                save(
                    task_dir / (call_id + "-request.json"),
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "messages": messages,
                        "input_ids": inputs["input_ids"][0].tolist(),
                        "input_tokens": input_tokens,
                        "rendered_sha256": hashlib.sha256(
                            rendered.encode()
                        ).hexdigest(),
                        "plan_sha256": args.plan_sha,
                        "call_id": call_id,
                    },
                )
                inputs = {key: value.to("cuda:0") for key, value in inputs.items()}
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
                ids = generated[0, input_tokens:].tolist()
                raw = tokenizer.decode(ids, skip_special_tokens=True)
                eos = model.generation_config.eos_token_id
                eos = eos if isinstance(eos, list) else [eos]
                details = {
                    "input_tokens": input_tokens,
                    "output_tokens": len(ids),
                    "seconds": time.monotonic() - started,
                    "inference_seconds": inference_seconds,
                    "ended_with_eos": bool(ids and ids[-1] in eos),
                    "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "capture_prefix": call_id,
                    "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                }
                with (task_dir / (call_id + "-raw.txt")).open("x") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                save(
                    task_dir / (call_id + "-response.json"),
                    {**details, "output_ids": ids},
                )
                print(
                    json.dumps(
                        {
                            "run_id": task["run_id"],
                            "call": total_calls,
                            "input_tokens": input_tokens,
                            "output_tokens": len(ids),
                            "seconds": details["seconds"],
                        }
                    ),
                    flush=True,
                )
                return raw, details

            with (
                EventJournal(task_dir / "EVENTS.jsonl") as journal,
                EventJournal(task_dir / "RESOURCES.jsonl") as resource_journal,
            ):
                trace = run_session(
                    data,
                    bank,
                    task["config"],
                    backend=backend,
                    journal=journal,
                    resource_journal=resource_journal,
                )
            trace.update(run_id=task["run_id"], plan_sha256=args.plan_sha)
            save(task_dir / "TRACE.json", trace)
            completed += 1
            print(
                json.dumps(
                    {"completed_sessions": completed, "model_calls": total_calls}
                ),
                flush=True,
            )
        save(
            output / "COMPLETE.json",
            {
                "sessions": completed,
                "model_calls": total_calls,
                "seconds_after_load": time.monotonic() - worker_started,
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
