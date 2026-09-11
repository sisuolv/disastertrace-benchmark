"""Freeze after real CPU processor preflight, before any ACP submission."""

import importlib.metadata
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "source/src"))

from disastertrace.multimodal_atomic_v1.adapter import AtomicBackend, readability
from disastertrace.multimodal_v1.storage import digest, now, read, write


def main():
    write(ROOT / "FREEZE_CLAIM.json", {"at": now(), "generations": 0})
    accepted = read(ROOT / "OFFLINE_ACCEPTANCE.json")
    for name, expected in accepted["source_sha256"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("accepted offline source changed")
    previous = read(ROOT.parent / "mm3_contract_v2_live_20260909/EXECUTION.json")
    versions = {k: importlib.metadata.version(k) for k in previous["runtime_versions"]}
    if versions != previous["runtime_versions"]:
        raise ValueError("model runtime changed")
    for name, expected in read(ROOT / "RUNTIME_BINDINGS.json").items():
        if digest(Path(name).read_bytes()) != expected:
            raise ValueError("runtime implementation changed")
    import torch
    from transformers import AutoProcessor

    torch.set_num_threads(4)
    processor = AutoProcessor.from_pretrained(previous["model_directory"], local_files_only=True, trust_remote_code=False)
    processor.image_processor.size = {"shortest_edge": 65536, "longest_edge": 1048576}
    backend = AtomicBackend(processor, None, previous["settings"])
    rows, checks = [], []
    for task in read(ROOT / "REQUEST_PLAN.json")["tasks"]:
        slot = ROOT / "cpu_preflight" / task["task_id"]
        slot.mkdir(parents=True, exist_ok=False)
        inputs = backend.prepare(task, slot)
        checks.extend(readability(task, inputs, processor, slot))
        info = read(slot / "processor.json")
        rows.append({"task_id": task["task_id"], "input_tokens": info["input_tokens"],
                     "visual_tokens": info["visual_tokens"]})
    write(ROOT / "CPU_PREFLIGHT.json", {"status": "passed", "at": now(), "generations": 0,
          "contexts": rows, "pixel_checks": checks, "runtime_versions": versions})
    files = [p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts
             and p.suffix not in {".log", ".pyc"}]
    bound = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in files}
    execution = {"schema": "mm-atomic-four-worker-execution-v1", "created_at": now(),
                 "not_after_unix": time.time() + 7200, "max_worker_seconds": 3600,
                 "max_generations": 40, "h100_workers": 4, "max_h100_global": 4,
                 "retry_times": 0, "paid_api": False, "heldout": False,
                 "settings": previous["settings"], "model_directory": previous["model_directory"],
                 "model_revision": previous["model_revision"], "runtime_versions": versions,
                 "runtime_bindings_sha256": digest((ROOT / "RUNTIME_BINDINGS.json").read_bytes()),
                 "plan_sha256": digest((ROOT / "REQUEST_PLAN.json").read_bytes()),
                 "bound_files": bound,
                 "scope": "single-event atomic development; privileged logic and metadata tasks separate",
                 "strict_gate": "all 40 correct with EOS before considering revision diagnostics"}
    write(ROOT / "EXECUTION.json", execution)
    print("frozen", digest((ROOT / "EXECUTION.json").read_bytes()), "max input tokens", max(r["input_tokens"] for r in rows))


if __name__ == "__main__":
    main()
