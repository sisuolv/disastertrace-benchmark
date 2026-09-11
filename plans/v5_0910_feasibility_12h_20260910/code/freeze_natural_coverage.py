"""Freeze a separate, source-native missingness diagnostic without withholding."""

from datetime import datetime, timezone
import json
import shutil

from common import ROOT, digest, dump
from evidence_core import legal_cards, reference, validate_episode
from model_adapter import load_frontend, prepare, sha_file
from public_inputs_v2 import SYSTEM, request
from render_native_vil import render
from verify_public_solvability import solve


def main():
    import torch

    torch.set_num_threads(4)
    batch = ROOT / "gpu/wave6_natural_coverage"
    batch.mkdir(exist_ok=False)
    (batch / "assets").mkdir()
    (batch / "source").mkdir()
    small = json.loads((ROOT / "gpu/wave2/PLAN.json").read_text())
    large = json.loads((ROOT / "gpu/wave3_32b/PLAN.json").read_text())
    models = {"qwen3vl_8b": small["models"]["qwen3vl_8b"],
              "qwen3vl_32b": large["models"]["qwen3vl_32b"]}
    private_file = "data/NATURAL_EPISODES_PRIVATE.json"
    episodes = json.loads((ROOT / private_file).read_text())
    manifest = json.loads((ROOT / "data/NATURAL_COVERAGE_ARRAYS.json").read_text())
    if len(episodes) != 12 or len(manifest) != 6:
        raise ValueError("natural coverage diagnostic denominator changed")
    conditions = {
        "full_text": {"mode": "full", "representation": "text", "budget": 4, "max_calls": 1},
        "native_vil_full": {"mode": "full", "representation": "image", "budget": 4, "max_calls": 1},
    }
    public, native_manifests, solvability = {}, {}, []
    for episode in episodes:
        validate_episode(episode)
        cards = sorted(legal_cards(episode), key=lambda c: c["id"])
        ids = [c["id"] for c in cards]
        if len(cards) != 4 or episode["variant"] != "native_missingness":
            raise ValueError("expected complete native four-quadrant pool")
        public[episode["id"]] = {}
        for name, condition in conditions.items():
            text, _ = request(episode, ids, condition["representation"], "full", 4)
            assets = []
            if condition["representation"] == "image":
                text["representation_note"] = (
                    "Images show actual archived VIL pixels with native255missing retained. "
                    "Positive/negative counts are not printed. Only the left square is data. "
                    "Each2x2display block is one original pixel. Use the color legend and "
                    "keep the declared full-frame denominator."
                )
                for card in cards:
                    png, rendered = render(card, episode, manifest)
                    sha = digest(png)
                    path = "assets/" + sha + ".png"
                    if not (batch / path).exists():
                        (batch / path).write_bytes(png)
                    native_manifests[sha] = rendered
                    assets.append({"id": card["id"], "path": path, "sha256": sha})
            else:
                answer = solve(text)
                if answer != reference(episode, ids)["decision"]:
                    raise ValueError("public exact-arithmetic solver disagrees")
                solvability.append({"episode": episode["id"], "decision": answer})
            public[episode["id"]][name] = {
                "initial": {"system": SYSTEM, "public": text, "assets": assets}, "states": {}}
    dump(batch / "PUBLIC.json", public)
    dump(batch / "NATIVE_RENDER_MANIFEST.json", native_manifests)
    dump(batch / "PUBLIC_SOLVABILITY.json", {"status": "passed", "checks": solvability})
    tasks, workers = {}, {}
    ordered = sorted(episodes, key=lambda e: digest(("natural-coverage-20260910" + e["id"]).encode()))
    for model, worker_ids in [("qwen3vl_8b", ["0", "1"]), ("qwen3vl_32b", ["2", "3"])]:
        for worker in worker_ids:
            workers[worker] = {"model": model, "tasks": [], "max_calls": 0}
        for index, episode in enumerate(ordered):
            worker = worker_ids[index % 2]
            for name, condition in conditions.items():
                tid = "n" + digest((model + episode["id"] + name).encode())[:16]
                tasks[tid] = {"id": tid, "episode": episode["id"], "model": model,
                              "condition": name, **condition}
                workers[worker]["tasks"].append(tid)
                workers[worker]["max_calls"] += 1
    settings = {**small["settings"], "context_limit": 16384}
    checks = []
    for model, spec in models.items():
        frontend = load_frontend(spec, settings)
        rows = []
        for episode in episodes:
            for condition in conditions:
                state = public[episode["id"]][condition]["initial"]
                _, record = prepare(frontend, "vl", state, batch, settings)
                rows.append({"episode": episode["id"], "condition": condition, **record})
        dump(batch / ("CPU_PREFLIGHT_" + model + ".json"), rows)
        checks.append({"model": model, "profiles": len(rows),
                       "max_input_tokens": max(row["input_tokens"] for row in rows)})
    for name in ["model_adapter.py", "gpu_worker.py"]:
        shutil.copy2(ROOT / "code" / name, batch / "source" / name)
    source_names = ["freeze_natural_coverage.py", "render_native_vil.py", "public_inputs.py",
                    "public_inputs_v2.py", "evidence_core.py", "audit_gpu.py"]
    plan = {
        "created_at": datetime.now(timezone.utc).isoformat(), "wave": "wave6-natural-coverage",
        "models": models, "episodes": len(episodes), "conditions": conditions,
        "tasks": tasks, "workers": workers, "max_requests": 48,
        "settings": settings, "max_worker_seconds": 7200, "max_concurrent_gpus": 4,
        "deadline_unix": small["deadline_unix"], "runtime_files": small["runtime_files"],
        "runtime_versions": small["runtime_versions"], "preflight": checks,
        "private_data_file": private_file, "private_data_sha256": sha_file(ROOT / private_file),
        "source_sha256": {name: sha_file(ROOT / "code" / name) for name in source_names},
        "bound_files": {str(p.relative_to(batch)): sha_file(p) for p in batch.rglob("*") if p.is_file()},
        "scope_amendment_sha256": sha_file(ROOT / "SCOPE_AMENDMENT_01.json"),
        "source_selection": "Six VIL sequences stratified by official catalog missing fraction; no target-value selection.",
        "frame_selection": "First native-missing frame and a distinct minimum-missing frame, earliest tie.",
        "values_modified": False, "controlled_withholding": False, "development_only": True,
        "comparison_limit": "Native VIL pixels versus privileged exact counts, not an equal-information representation control.",
        "statistics_limit": "Twelve paired diagnostic frames from six sequences; selected goal balance is not natural prevalence.",
    }
    if sum(w["max_calls"] for w in workers.values()) != plan["max_requests"]:
        raise ValueError("call accounting differs")
    dump(batch / "PLAN.json", plan)
    print(json.dumps({"tasks": len(tasks), "max_calls": 48, "preflight": checks,
                      "plan_sha256": sha_file(batch / "PLAN.json")}))


if __name__ == "__main__":
    main()
