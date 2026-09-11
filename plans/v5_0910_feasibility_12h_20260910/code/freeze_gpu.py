"""Freeze a new development matrix and public-only model input state machine."""

from datetime import datetime, timezone
import importlib.metadata
import itertools
import json
from pathlib import Path
import shutil

from common import ROOT, digest, dump
from evidence_core import legal_cards, validate_episode
from model_adapter import load_frontend, prepare, sha_file
from public_inputs import SYSTEM, request


def main():
    import torch

    torch.set_num_threads(4)
    batch = ROOT / "gpu/wave1"
    batch.mkdir(exist_ok=False)
    (batch / "assets").mkdir()
    (batch / "source").mkdir()
    scope = json.loads((ROOT / "SCOPE.json").read_text())
    episodes = json.loads((ROOT / "data/PILOT_EPISODES_PRIVATE.json").read_text())
    conditions = {
        "full_text": {"mode": "full", "representation": "text", "budget": 4, "max_calls": 1},
        "full_image": {"mode": "full", "representation": "image", "budget": 4, "max_calls": 1},
        "active2_text": {"mode": "active", "representation": "text", "budget": 2, "max_calls": 3},
        "active2_image": {"mode": "active", "representation": "image", "budget": 2, "max_calls": 3},
        "none": {"mode": "none", "representation": "text", "budget": 0, "max_calls": 1},
    }
    public = {}
    assets = {}
    for episode in episodes:
        validate_episode(episode)
        ids = sorted(x["id"] for x in legal_cards(episode))
        public[episode["id"]] = {}
        for name, condition in conditions.items():
            def state(read_ids):
                text, images = request(episode, read_ids, condition["representation"],
                                       condition["mode"], condition["budget"])
                attachments = []
                for asset in images:
                    sha = digest(asset["png"])
                    rel = "assets/" + sha + ".png"
                    if sha not in assets:
                        (batch / rel).write_bytes(asset["png"])
                        assets[sha] = asset["manifest"]
                    attachments.append({"id": asset["id"], "path": rel, "sha256": sha})
                return {"system": SYSTEM, "public": text, "assets": attachments}
            initial = ids if condition["mode"] == "full" else []
            states = {}
            if condition["mode"] == "active":
                for count in range(3):
                    for subset in itertools.combinations(ids, count):
                        states[",".join(subset)] = state(subset)
            public[episode["id"]][name] = {"initial": state(initial), "states": states}
    dump(batch / "PUBLIC.json", public)
    dump(batch / "ASSETS.json", assets)
    old = ROOT.parent.parent / "disastertrace-starter/artifacts"
    text_old = json.loads((old / "p6_offline_v1/execution/model_snapshot.json").read_text())
    vl_old = json.loads((old / "multimodal_v1/mm4_atomic_20260909/model_acquisition/plan.json").read_text())
    models = {
        "qwen3_8b": {"directory": text_old["local_path"], "kind": "text",
            "revision": "per-file commits; weight revision 7c9709d23bd2136dac1d6ea1fe30f4107d681cd6",
            "files": [{k: x[k] for k in ["path", "bytes", "sha256", "revision"]} for x in text_old["files"]]},
        "qwen3vl_8b": {"directory": "/mnt/afs/260010168/models/Qwen3-VL-8B-Instruct-mm3-pinned-v1",
            "kind": "vl", "revision": vl_old["revision"], "files": [
                {"path": x["Path"], "bytes": x["Size"], "sha256": x["Sha256"], "revision": x["Revision"]}
                for x in vl_old["files"]]},
    }
    settings = {"seed": 20260910, "max_new_tokens": 768, "context_limit": 12288,
        "max_generation_seconds": 120, "min_pixels": 65536, "max_pixels": 1048576,
        "dtype": "bfloat16", "attention": "sdpa", "do_sample": False,
        "text_model_thinking": False, "response_parsing": "strict JSON, exact keys, EOS required",
        "automatic_retries": 0, "invalid_action": "terminate and retain in denominator"}
    tasks, workers = {}, {}
    for model, worker_ids in [("qwen3vl_8b", ["0", "1"]), ("qwen3_8b", ["2", "3"])]:
        enabled = list(conditions) if models[model]["kind"] == "vl" else ["full_text", "active2_text", "none"]
        for worker in worker_ids:
            workers[worker] = {"model": model, "tasks": [], "max_calls": 0}
        ordered = sorted(episodes, key=lambda e: digest(("assignment-20260910" + e["id"]).encode()))
        for index, episode in enumerate(ordered):
            worker = worker_ids[index % 2]
            for condition in enabled:
                task_id = "t" + digest((model + episode["id"] + condition).encode())[:16]
                tasks[task_id] = {"id": task_id, "episode": episode["id"], "condition": condition,
                                  "model": model, **conditions[condition]}
                workers[worker]["tasks"].append(task_id)
                workers[worker]["max_calls"] += conditions[condition]["max_calls"]
    max_calls = sum(w["max_calls"] for w in workers.values())
    if max_calls > scope["max_new_model_requests"]:
        raise ValueError("scope request budget exceeded")
    checks = []
    for name, spec in models.items():
        for row in spec["files"]:
            if (Path(spec["directory"]) / row["path"]).stat().st_size != row["bytes"]:
                raise ValueError("model file size mismatch")
        frontend = load_frontend(spec, settings)
        unique = {(t["episode"], t["condition"]) for t in tasks.values() if t["model"] == name}
        records = []
        for episode_id, condition in sorted(unique):
            state = public[episode_id][condition]["initial"]
            _, record = prepare(frontend, spec["kind"], state, batch, settings)
            records.append({"episode": episode_id, "condition": condition, **record})
        dump(batch / ("PREFLIGHT_" + name + ".json"), records)
        checks.append({"model": name, "initial_states": len(records),
                       "max_input_tokens": max(r["input_tokens"] for r in records),
                       "attached_images": sum(len(r["assets"]) for r in records)})
        print(json.dumps(checks[-1]), flush=True)
    for name in ["model_adapter.py", "gpu_worker.py"]:
        shutil.copy2(ROOT / "code" / name, batch / "source" / name)
    runtime = json.loads((old / "multimodal_v1/mm4_atomic_20260909/RUNTIME_BINDINGS.json").read_text())
    # Bind the text model implementation too; the historical matrix only used VL.
    import transformers.models.qwen3.modeling_qwen3 as qwen3_module
    runtime[qwen3_module.__file__] = sha_file(qwen3_module.__file__)
    versions = {name: importlib.metadata.version(name) for name in
                ["torch", "torchvision", "transformers", "accelerate", "tokenizers", "safetensors", "Pillow"]}
    bound = {str(p.relative_to(batch)): sha_file(p) for p in batch.rglob("*") if p.is_file()}
    plan = {"created_at": datetime.now(timezone.utc).isoformat(), "wave": "wave1", "episodes": len(episodes),
        "development_only": True, "paid_api": False, "models": models, "settings": settings,
        "conditions": conditions, "workers": workers, "tasks": tasks, "max_requests": max_calls,
        "deadline_unix": datetime.fromisoformat(scope["deadline_utc"]).timestamp() - 1800,
        "max_worker_seconds": 14400, "max_concurrent_gpus": 4, "bound_files": bound,
        "runtime_files": runtime, "runtime_versions": versions, "preflight": checks,
        "private_data_sha256": sha_file(ROOT / "data/PILOT_EPISODES_PRIVATE.json"),
        "source_sha256": {name: sha_file(ROOT / "code" / name) for name in
                          ["public_inputs.py", "evidence_core.py", "build_pilot.py", "freeze_gpu.py"]},
        "experiment_limit": "Product-fact acquisition and equal-information raster-table control; no native image or physical forecast claims.",
        "statistics": "Report fixed denominator by source/model/condition; episode count is not independent event count."}
    dump(batch / "PLAN.json", plan)
    print(json.dumps({"status": "frozen", "tasks": len(tasks), "max_requests": max_calls,
                      "plan_sha256": sha_file(batch / "PLAN.json")}))


if __name__ == "__main__":
    main()
