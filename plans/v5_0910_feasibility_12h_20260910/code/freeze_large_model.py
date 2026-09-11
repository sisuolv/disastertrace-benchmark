"""Freeze the same protocol-v2 tasks for a fully verified32B snapshot."""

from datetime import datetime, timezone
import json
import shutil

from common import ROOT, digest, dump
from model_adapter import load_frontend, prepare, sha_file


def main():
    import torch

    torch.set_num_threads(4)
    old = ROOT / "gpu/wave2"
    batch = ROOT / "gpu/wave3_32b"
    batch.mkdir(exist_ok=False)
    for name in ["PUBLIC.json", "ASSETS.json"]:
        shutil.copy2(old / name, batch / name)
    for name in ["source", "assets"]:
        shutil.copytree(old / name, batch / name)
    plan = json.loads((old / "PLAN.json").read_text())
    acquisition = json.loads((ROOT / "gpu/model32_acquisition/PLAN.json").read_text())
    resume = json.loads((ROOT / "gpu/model32_resume_01/COMPLETED.json").read_text())
    if not resume["all_verified"]:
        raise ValueError("32B snapshot incomplete")
    spec = {"directory": acquisition["destination"], "kind": "vl",
        "revision": "per-file commits; weights8ee644102b9aef163388c49635ca1e57ae2cb040",
        "files": [{"path": x["Path"], "bytes": x["Size"], "sha256": x["Sha256"], "revision": x["Revision"]}
                  for x in acquisition["files"]]}
    model = "qwen3vl_32b"
    public = json.loads((batch / "PUBLIC.json").read_text())
    tasks, workers = {}, {str(i): {"model": model, "tasks": [], "max_calls": 0} for i in range(4)}
    for index, episode in enumerate(sorted(public, key=lambda e: digest(("assignment-20260910" + e).encode()))):
        worker = str(index % 4)
        for condition in ["full_text", "full_image", "active2_image"]:
            tid = "t" + digest((model + episode + condition).encode())[:16]
            tasks[tid] = {"id": tid, "episode": episode, "condition": condition,
                          "model": model, **plan["conditions"][condition]}
            workers[worker]["tasks"].append(tid)
            workers[worker]["max_calls"] += tasks[tid]["max_calls"]
    frontend = load_frontend(spec, plan["settings"])
    checks = []
    for task in tasks.values():
        _, record = prepare(frontend, "vl", public[task["episode"]][task["condition"]]["initial"], batch, plan["settings"])
        checks.append({"task": task["id"], **record})
    dump(batch / "CPU_PREFLIGHT.json", checks)
    plan.update(created_at=datetime.now(timezone.utc).isoformat(), wave="wave3-32b", models={model: spec},
        tasks=tasks, workers=workers, max_requests=sum(x["max_calls"] for x in workers.values()),
        preflight=[{"model": model, "initial_states": len(checks),
                    "max_input_tokens": max(x["input_tokens"] for x in checks),
                    "attached_images": sum(len(x["assets"]) for x in checks)}],
        parent_public_plan_sha256=sha_file(old / "PLAN.json"),
        acquisition_sources=["gpu/model32_acquisition/PLAN.json", "gpu/model32_resume_01/COMPLETED.json"])
    plan["source_sha256"]["freeze_large_model.py"] = sha_file(ROOT / "code/freeze_large_model.py")
    plan["bound_files"] = {str(p.relative_to(batch)): sha_file(p) for p in batch.rglob("*") if p.is_file()}
    dump(batch / "PLAN.json", plan)
    print(json.dumps({"tasks": len(tasks), "max_requests": plan["max_requests"], "preflight": plan["preflight"],
                      "sha256": sha_file(batch / "PLAN.json")}))


if __name__ == "__main__":
    main()
