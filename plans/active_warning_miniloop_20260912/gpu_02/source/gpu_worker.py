"""One-use, one-H100 model worker; its input package contains no outcome table."""

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
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--worker", type=int, required=True)
    parser.add_argument("--plan-sha", required=True)
    args = parser.parse_args()
    batch = args.batch
    output = batch / "runs" / str(args.worker)
    output.mkdir(parents=True, exist_ok=False)
    save(
        output / "CLAIM.json",
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
        },
    )
    try:
        if digest(batch / "PLAN.json") != args.plan_sha:
            raise ValueError("frozen plan mismatch")
        plan = json.loads((batch / "PLAN.json").read_text())
        for name, sha in plan["files"].items():
            if digest(batch / name) != sha:
                raise ValueError("frozen public input or source changed: " + name)
        runtime = {name: version(name) for name in plan["runtime_versions"]}
        if runtime != plan["runtime_versions"]:
            raise ValueError("runtime package versions changed")
        spec = plan["model"]
        for item in spec["files"]:
            path = Path(spec["directory"]) / item["path"]
            if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
                raise ValueError("model file changed: " + item["path"])
        import torch
        from disastertrace.active_forecast.provenance import load_json
        from disastertrace.active_warning_v1 import Episode
        from disastertrace.active_warning_v1.policies import (
            run_episode,
            scenario_episode,
        )
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.cuda.device_count() != 1:
            raise ValueError("exactly one GPU required")
        props = torch.cuda.get_device_properties(0)
        if "H100" not in props.name or props.total_memory < 75 * 1024**3:
            raise ValueError("full H100 80GB required")
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
        save(
            output / "PREFLIGHT.json",
            {
                "model_hashes_verified": True,
                "model_loaded": True,
                "generation_calls": 0,
            },
        )
        episodes = {
            row["id"]: Episode.model_validate(row)
            for row in load_json(batch / "episodes.json")
        }
        total_calls = 0
        completed = 0
        worker_start = time.monotonic()
        for task in plan["workers"][str(args.worker)]:
            task_dir = output / task["run_id"]
            task_dir.mkdir()
            episode = scenario_episode(episodes[task["episode_id"]], task["scenario"])

            def backend(system, prompt, stage, round_index, task_dir=task_dir):
                nonlocal total_calls
                if total_calls >= plan["max_calls_per_worker"]:
                    raise RuntimeError("frozen model-call cap reached")
                total_calls += 1
                prefix = f"{stage}-{round_index}"
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
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
                if input_tokens + plan["max_new_tokens"] > plan["context_limit"]:
                    raise RuntimeError("context reservation exceeded")
                save(
                    task_dir / (prefix + "-request.json"),
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "messages": messages,
                        "input_ids": inputs["input_ids"][0].tolist(),
                        "input_tokens": input_tokens,
                        "rendered_sha256": hashlib.sha256(
                            rendered.encode()
                        ).hexdigest(),
                        "plan_sha256": args.plan_sha,
                    },
                )
                inputs = {key: value.to("cuda:0") for key, value in inputs.items()}
                started = time.monotonic()
                with torch.inference_mode():
                    generated = model.generate(
                        **inputs,
                        max_new_tokens=plan["max_new_tokens"],
                        do_sample=False,
                        max_time=plan["max_generation_seconds"],
                        pad_token_id=tokenizer.eos_token_id,
                    )
                torch.cuda.synchronize()
                ids = generated[0, input_tokens:].tolist()
                raw = tokenizer.decode(ids, skip_special_tokens=True)
                eos = model.generation_config.eos_token_id
                eos = eos if isinstance(eos, list) else [eos]
                finished = bool(ids and ids[-1] in eos)
                details = {
                    "input_tokens": input_tokens,
                    "output_tokens": len(ids),
                    "seconds": time.monotonic() - started,
                    "ended_with_eos": finished,
                    "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "capture_prefix": prefix,
                }
                with (task_dir / (prefix + "-raw.txt")).open("x") as stream:
                    stream.write(raw)
                save(
                    task_dir / (prefix + "-response.json"),
                    {**details, "output_ids": ids},
                )
                return (raw if finished else ""), details

            trace = run_episode(
                episode, task["budget"], task["policy"], backend=backend
            )
            trace.update(run_id=task["run_id"], plan_sha256=args.plan_sha)
            save(task_dir / "TRACE.json", trace)
            completed += 1
            print(
                json.dumps(
                    {
                        "completed_trajectories": completed,
                        "model_calls": total_calls,
                        "run_id": task["run_id"],
                    }
                ),
                flush=True,
            )
        save(
            output / "COMPLETE.json",
            {
                "trajectories": completed,
                "model_calls": total_calls,
                "seconds_after_load": time.monotonic() - worker_start,
                "plan_sha256": args.plan_sha,
            },
        )
    except Exception:
        save(
            output / "FAILED.json",
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "traceback": traceback.format_exc(),
            },
        )
        raise


if __name__ == "__main__":
    main()
