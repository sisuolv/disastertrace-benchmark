"""Freeze an independent VLM-family comparison on the same protocol-v2 pool."""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from common import ROOT, digest, dump
from model_adapter_intern import load_frontend, prepare, sha_file


def main():
    import torch
    import transformers.models.internvl.modeling_internvl as modeling
    import transformers.models.internvl.processing_internvl as processing
    import transformers.models.got_ocr2.image_processing_got_ocr2_fast as image_processing

    torch.set_num_threads(4)
    acquisition_root = ROOT / "gpu/internvl_acquisition"
    completed = json.loads((acquisition_root / "COMPLETED.json").read_text())
    if not completed["all_verified"]:
        raise ValueError("InternVL snapshot incomplete")
    acquisition = json.loads((acquisition_root / "PLAN.json").read_text())
    old = ROOT / "gpu/wave2"
    batch = ROOT / "gpu/wave4_internvl"
    batch.mkdir(exist_ok=False)
    for name in ["PUBLIC.json", "ASSETS.json"]:
        shutil.copy2(old / name, batch / name)
    shutil.copytree(old / "assets", batch / "assets")
    (batch / "source").mkdir()
    for name in ["model_adapter.py", "model_adapter_intern.py"]:
        shutil.copy2(ROOT / "code" / name, batch / "source" / name)
    shutil.copy2(ROOT / "code/gpu_worker_intern.py", batch / "source/gpu_worker.py")
    plan = json.loads((old / "PLAN.json").read_text())
    spec = {"directory": acquisition["destination"], "kind": "internvl",
        "revision": "per-file official ModelScope revisions and SHA256 in acquisition manifest",
        "files": [{"path": x["Path"], "bytes": x["Size"], "sha256": x["Sha256"], "revision": x["Revision"]}
                  for x in acquisition["files"]]}
    model = "internvl3_5_8b"
    public = json.loads((batch / "PUBLIC.json").read_text())
    tasks, workers = {}, {str(i): {"model": model, "tasks": [], "max_calls": 0} for i in range(4)}
    for index, episode in enumerate(sorted(public, key=lambda e: digest(("assignment-20260910" + e).encode()))):
        worker = str(index % 4)
        for condition in ["full_text", "full_image", "active2_image"]:
            tid = "t" + digest((model + episode + condition).encode())[:16]
            tasks[tid] = {"id": tid, "episode": episode, "condition": condition, "model": model, **plan["conditions"][condition]}
            workers[worker]["tasks"].append(tid)
            workers[worker]["max_calls"] += tasks[tid]["max_calls"]
    settings = {**plan["settings"], "internvl_max_patches": 12, "context_limit": 16384,
                "internvl_crop_to_patches": True, "internvl_thinking_prompt": False}
    frontend = load_frontend(spec, settings)
    checks = []
    for task in tasks.values():
        _, record = prepare(frontend, "internvl", public[task["episode"]][task["condition"]]["initial"], batch, settings)
        checks.append({"task": task["id"], **record})
    dump(batch / "CPU_PREFLIGHT.json", checks)
    for module in [modeling, processing, image_processing]:
        plan["runtime_files"][module.__file__] = sha_file(module.__file__)
    plan.update(created_at=datetime.now(timezone.utc).isoformat(), wave="wave4-internvl", models={model: spec},
        settings=settings, tasks=tasks, workers=workers, max_requests=sum(x["max_calls"] for x in workers.values()),
        preflight=[{"model": model, "initial_states": len(checks), "max_input_tokens": max(x["input_tokens"] for x in checks),
                    "max_image_patches": max(x["internvl_patch_count"] for x in checks),
                    "attached_images": sum(len(x["assets"]) for x in checks)}],
        parent_public_plan_sha256=sha_file(old / "PLAN.json"),
        family_limit="Different VLM architecture/training; Qwen3 backbone shared, so not fully independent language-model lineage.",
        image_profile="Native InternVL dynamic patches, max12plusthumbnail per image; avoids squeezing wide tables into448square.")
    for name in ["freeze_internvl.py", "model_adapter_intern.py", "gpu_worker_intern.py"]:
        plan["source_sha256"][name] = sha_file(ROOT / "code" / name)
    plan["bound_files"] = {str(p.relative_to(batch)): sha_file(p) for p in batch.rglob("*") if p.is_file()}
    dump(batch / "PLAN.json", plan)
    print(json.dumps({"tasks": len(tasks), "max_requests": plan["max_requests"], "preflight": plan["preflight"], "sha256": sha_file(batch / "PLAN.json")}))


if __name__ == "__main__":
    main()
