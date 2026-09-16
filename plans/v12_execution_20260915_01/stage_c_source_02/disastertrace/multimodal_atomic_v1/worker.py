"""One immutable shard on one H100; four disjoint shards share a fixed atomic plan."""

import argparse
import hashlib
import importlib.metadata
import os
import socket
import subprocess
import time
import traceback
from pathlib import Path

from disastertrace.multimodal_v1.storage import digest, now, read, write

from .adapter import AtomicBackend, readability
from .audit import validate_plan
from .runner import collect


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def run(batch, execution_sha, worker):
    root = batch / "gpu_runs" / worker
    root.mkdir(parents=True, exist_ok=False)
    write(
        root / "WORKER_CLAIM.json",
        {"at": now(), "hostname": socket.gethostname(), "pid": os.getpid()},
    )
    try:
        if digest((batch / "EXECUTION.json").read_bytes()) != execution_sha:
            raise ValueError("execution differs from submitted identity")
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        scope = read(batch / "EXECUTION.json")
        plan = read(batch / "REQUEST_PLAN.json")
        if digest((batch / "REQUEST_PLAN.json").read_bytes()) != scope["plan_sha256"]:
            raise ValueError("frozen plan changed")
        validate_plan(plan)
        task_ids = plan["assignments"][worker]
        by_id = {t["task_id"]: t for t in plan["tasks"]}
        tasks = [by_id[tid] for tid in task_ids]
        for name, expected in scope["bound_files"].items():
            if file_hash(batch / name) != expected:
                raise ValueError("frozen source changed: " + name)
        if file_hash(batch / "RUNTIME_BINDINGS.json") != scope["runtime_bindings_sha256"]:
            raise ValueError("runtime bindings changed")
        for name, expected in read(batch / "RUNTIME_BINDINGS.json").items():
            if file_hash(Path(name)) != expected:
                raise ValueError("runtime implementation changed: " + name)
        versions = {key: importlib.metadata.version(key) for key in scope["runtime_versions"]}
        if versions != scope["runtime_versions"]:
            raise ValueError("runtime version mismatch")
        if time.time() >= scope["not_after_unix"]:
            raise ValueError("fresh execution window expired")
        torch.set_num_threads(4)
        torch.manual_seed(20260909)
        if torch.cuda.device_count() != 1:
            raise ValueError("expected exactly one visible GPU")
        prop = torch.cuda.get_device_properties(0)
        if "H100" not in prop.name or prop.total_memory < 75 * 1024**3:
            raise ValueError("expected full H100 80GB")
        hardware = {
            "name": prop.name,
            "total_memory": prop.total_memory,
            "count": torch.cuda.device_count(),
            "capability": list(torch.cuda.get_device_capability()),
            "hostname": socket.gethostname(),
            "runtime_versions": versions,
            "torch_cuda": torch.version.cuda,
            "nvidia_smi": subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,uuid,driver_version,memory.total",
                    "--format=csv,noheader",
                ],
                text=True,
            ),
        }
        write(root / "HARDWARE.json", hardware)
        model_dir = Path(scope["model_directory"])
        acquisition = read(batch / "model_acquisition/plan.json")
        for row in acquisition["files"]:
            path = model_dir / row["Path"]
            if path.stat().st_size != row["Size"] or file_hash(path) != row["Sha256"]:
                raise ValueError("model integrity failed: " + row["Path"])
        write(
            root / "MODEL_VERIFIED.json",
            {"at": now(), "revision": acquisition["revision"], "files": len(acquisition["files"])},
        )
        processor = AutoProcessor.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False
        )
        processor.image_processor.size = {"shortest_edge": 65536, "longest_edge": 1048576}
        write(root / "PROCESSOR_CONFIG.json", processor.to_dict())
        write(root / "IMAGE_PROCESSOR_CONFIG.json", processor.image_processor.to_dict())
        started = time.monotonic()
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_dir,
            local_files_only=True,
            trust_remote_code=False,
            dtype=torch.bfloat16,
            device_map={"": 0},
            attn_implementation="sdpa",
        ).eval()
        backend = AtomicBackend(processor, model, scope["settings"])
        load_seconds = time.monotonic() - started
        write(
            root / "MODEL_LOADED.json",
            {
                "at": now(),
                "seconds": load_seconds,
                "parameter_count": sum(p.numel() for p in model.parameters()),
                "dtype": str(next(model.parameters()).dtype),
                "attention": model.config._attn_implementation,
                "allocated_bytes": torch.cuda.memory_allocated(),
            },
        )
        checks, contexts, forwards = [], [], []
        for task in tasks:
            slot = root / "preflight" / task["task_id"]
            slot.mkdir(parents=True)
            write(slot / "request.json", task)
            inputs = backend.prepare(task, slot)
            checks.extend(readability(task, inputs, processor, slot))
            contexts.append(read(slot / "processor.json")["input_tokens"])
            image_count = len(inputs.get("image_grid_thw", []))
            if image_count not in forwards:
                with torch.inference_mode():
                    output = model(
                        **{k: v.to("cuda") for k, v in inputs.items()},
                        use_cache=False,
                        logits_to_keep=1,
                    )
                    if not torch.isfinite(output.logits).all():
                        raise ValueError("non-finite no-generation forward")
                del output
                forwards.append(image_count)
        write(
            root / "PREFLIGHT.json",
            {
                "status": "passed",
                "at": now(),
                "generations": 0,
                "readability_checks": checks,
                "input_tokens_without_carrier": contexts,
                "forward_image_counts": sorted(forwards),
                "load_seconds": load_seconds,
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            },
        )
        if (
            time.time() + len(tasks) * scope["settings"]["max_generation_seconds"]
            >= scope["not_after_unix"]
        ):
            raise ValueError("insufficient remaining execution window")
        result = collect(root / "live", tasks, backend, execution_sha, scope["not_after_unix"])
        write(
            root / "DONE.json",
            {
                "at": now(),
                "status": "completed",
                "counts": result["counts"],
                "generation_intents": len(list((root / "live").glob("*/intent.json"))),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            },
        )
    except BaseException as error:
        write(
            root / "FAILED.json",
            {
                "at": now(),
                "error_type": type(error).__name__,
                "message": str(error)[:500],
                "traceback": traceback.format_exc(),
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--execution-sha", required=True)
    parser.add_argument("--worker", choices=["0", "1", "2", "3"], required=True)
    args = parser.parse_args()
    run(args.batch.resolve(), args.execution_sha, args.worker)
