"""Bounded one-H100 worker reading only the frozen public experiment package."""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import traceback

from model_adapter_intern import load_frontend, parse_action, prepare, save, sha_file, text_file


def now():
    return datetime.now(timezone.utc).isoformat()


def run(batch, expected_sha, worker):
    out = batch / "runs" / worker
    out.mkdir(parents=True, exist_ok=False)
    save(out / "CLAIM.json", {"at": now(), "hostname": socket.gethostname(), "pid": os.getpid()})
    started = time.monotonic()
    try:
        if sha_file(batch / "PLAN.json") != expected_sha:
            raise ValueError("submitted plan identity mismatch")
        plan = json.loads((batch / "PLAN.json").read_text())
        assignment = plan["workers"][worker]
        spec = plan["models"][assignment["model"]]
        settings = plan["settings"]
        for rel, sha in plan["bound_files"].items():
            if sha_file(batch / rel) != sha:
                raise ValueError("frozen file changed: " + rel)
        for path, sha in plan["runtime_files"].items():
            if sha_file(path) != sha:
                raise ValueError("runtime binding changed: " + path)
        versions = {name: importlib.metadata.version(name) for name in plan["runtime_versions"]}
        if versions != plan["runtime_versions"]:
            raise ValueError("runtime versions changed")
        if time.time() >= plan["deadline_unix"]:
            raise TimeoutError("experiment deadline passed")
        import torch
        from transformers import AutoModelForCausalLM, Qwen3VLForConditionalGeneration, InternVLForConditionalGeneration

        torch.set_num_threads(4)
        torch.manual_seed(settings["seed"])
        if torch.cuda.device_count() != 1:
            raise ValueError("expected exactly one visible GPU")
        prop = torch.cuda.get_device_properties(0)
        if "H100" not in prop.name or prop.total_memory < 75 * 1024**3:
            raise ValueError("expected full H100 80GB")
        save(out / "HARDWARE.json", {"at": now(), "name": prop.name, "bytes": prop.total_memory,
             "count": 1, "hostname": socket.gethostname(), "runtime_versions": versions,
             "cuda": torch.version.cuda, "nvidia_smi": subprocess.check_output([
                 "nvidia-smi", "--query-gpu=name,uuid,driver_version,memory.total", "--format=csv,noheader"], text=True)})
        for row in spec["files"]:
            path = Path(spec["directory"]) / row["path"]
            if path.stat().st_size != row["bytes"] or sha_file(path) != row["sha256"]:
                raise ValueError("model file mismatch: " + row["path"])
        save(out / "MODEL_VERIFIED.json", {"at": now(), "model": assignment["model"],
             "revision": spec["revision"], "files": len(spec["files"])})
        frontend = load_frontend(spec, settings)
        klass = {"vl": Qwen3VLForConditionalGeneration, "text": AutoModelForCausalLM, "internvl": InternVLForConditionalGeneration}[spec["kind"]]
        model = klass.from_pretrained(spec["directory"], local_files_only=True, trust_remote_code=False,
                    dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="sdpa").eval()
        tokenizer = frontend.tokenizer if spec["kind"] in {"vl", "internvl"} else frontend
        save(out / "LOADED.json", {"at": now(), "elapsed_seconds": time.monotonic() - started,
             "parameters": sum(p.numel() for p in model.parameters()),
             "allocated_bytes": torch.cuda.memory_allocated(), "attention": model.config._attn_implementation})
        public = json.loads((batch / "PUBLIC.json").read_text())
        tasks = [plan["tasks"][tid] for tid in assignment["tasks"]]
        checked = set()
        for task in tasks:
            state = public[task["episode"]][task["condition"]]["initial"]
            signature = (task["condition"], len(state["assets"]))
            if signature in checked:
                continue
            slot = out / "preflight" / task["id"]
            slot.mkdir(parents=True)
            inputs, record = prepare(frontend, spec["kind"], state, batch, settings, slot)
            with torch.inference_mode():
                result = model(**{k: v.to("cuda") for k, v in inputs.items()}, use_cache=False, logits_to_keep=1)
                if not torch.isfinite(result.logits).all():
                    raise ValueError("nonfinite preflight forward")
            del result, inputs
            checked.add(signature)
        save(out / "PREFLIGHT.json", {"at": now(), "status": "passed", "generations": 0,
             "signatures": sorted(checked)})
        requests = 0
        for task in tasks:
            trajectory = out / "trajectories" / task["id"]
            trajectory.mkdir(parents=True, exist_ok=False)
            bundle = public[task["episode"]][task["condition"]]
            read_ids = list(bundle["initial"]["public"]["read_ids"])
            state = bundle["initial"]
            final, status, calls = None, "unfinished", []
            for turn in range(task["max_calls"]):
                if (time.time() + settings["max_generation_seconds"] >= plan["deadline_unix"]
                        or time.monotonic() - started >= plan["max_worker_seconds"] - 180):
                    status = "deadline_not_called"
                    break
                if requests >= assignment["max_calls"]:
                    raise ValueError("worker request budget exceeded")
                slot = trajectory / ("turn-%02d" % turn)
                slot.mkdir(exist_ok=False)
                save(slot / "request.json", state)
                inputs, record = prepare(frontend, spec["kind"], state, batch, settings, slot)
                save(slot / "intent.json", {"at": now(), "task_id": task["id"], "turn": turn,
                     "read_ids": read_ids, "plan_sha256": expected_sha,
                     "request_sha256": sha_file(slot / "request.json")})
                requests += 1
                before = time.monotonic()
                try:
                    with torch.inference_mode():
                        output = model.generate(**{k: v.to("cuda") for k, v in inputs.items()},
                            max_new_tokens=settings["max_new_tokens"], max_time=settings["max_generation_seconds"],
                            do_sample=False, use_cache=True, pad_token_id=tokenizer.pad_token_id,
                            return_dict_in_generate=True)
                    torch.cuda.synchronize()
                    token_ids = output.sequences[0, inputs["input_ids"].shape[-1]:].tolist()
                    raw = tokenizer.decode(token_ids, skip_special_tokens=True)
                    # Raw response is durable before parsing or action execution.
                    text_file(slot / "raw.txt", raw)
                    save(slot / "tokens.json", token_ids)
                    eos = model.generation_config.eos_token_id
                    eos = eos if isinstance(eos, list) else [eos]
                    ended = bool(token_ids and token_ids[-1] in eos)
                    save(slot / "response.json", {"at": now(), "seconds": time.monotonic() - before,
                         "generated_tokens": len(token_ids), "ended_eos": ended,
                         "raw_sha256": sha_file(slot / "raw.txt")})
                    action, kind = parse_action(raw)
                    calls.append({"turn": turn, "kind": kind, "ended_eos": ended})
                    del output, inputs
                    if not ended:
                        status = "generation_incomplete"
                        break
                    if kind == "final":
                        final, status = action, "final"
                        break
                    if kind != "read":
                        status = kind
                        break
                    cid = action["read"]
                    catalog = {c["id"]: c for c in state["public"]["catalog"]}
                    if (task["mode"] != "active" or cid not in catalog or cid in read_ids
                            or catalog[cid]["cost"] > state["public"]["remaining_budget"]):
                        status = "illegal_read"
                        break
                    read_ids = sorted(read_ids + [cid])
                    key = ",".join(read_ids)
                    if key not in bundle["states"]:
                        raise ValueError("legal next state missing in frozen public pool")
                    state = bundle["states"][key]
                except Exception as error:
                    save(slot / "ERROR.json", {"at": now(), "type": type(error).__name__,
                         "message": str(error)[:500], "traceback": traceback.format_exc()})
                    status = "runtime_error"
                    torch.cuda.empty_cache()
                    break
            save(trajectory / "FINAL.json", {"task_id": task["id"], "episode": task["episode"],
                 "condition": task["condition"], "read_ids": read_ids, "answer": final,
                 "status": status, "calls": calls})
            print(json.dumps({"task": task["id"], "status": status, "requests": requests}), flush=True)
        save(out / "DONE.json", {"at": now(), "status": "completed", "tasks": len(tasks),
             "requests": requests, "elapsed_seconds": time.monotonic() - started,
             "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
             "peak_reserved_bytes": torch.cuda.max_memory_reserved()})
    except BaseException as error:
        save(out / "FAILED.json", {"at": now(), "type": type(error).__name__, "message": str(error)[:500],
             "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--plan-sha", required=True)
    parser.add_argument("--worker", required=True)
    args = parser.parse_args()
    run(args.batch.resolve(), args.plan_sha, args.worker)
