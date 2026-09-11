"""Freeze natural-text state traces, fixed acquisition, and source-raster controls."""

from datetime import datetime, timezone
import json
import shutil

from common import ROOT, digest, dump
from evidence_core import legal_cards
from model_adapter_intern import load_frontend, prepare, sha_file
from program_baselines import relevant_ids
from public_inputs_v2 import SYSTEM, request
from render_native_vil import render
from state_inputs import state_request


def main():
    import torch

    torch.set_num_threads(4)
    batch = ROOT / "gpu/wave5_diagnostics"
    batch.mkdir(exist_ok=False)
    (batch / "assets").mkdir()
    (batch / "source").mkdir()
    prior = json.loads((ROOT / "gpu/wave2/PLAN.json").read_text())
    large = json.loads((ROOT / "gpu/wave3_32b/PLAN.json").read_text())
    models = {"qwen3vl_8b": prior["models"]["qwen3vl_8b"], "qwen3vl_32b": large["models"]["qwen3vl_32b"]}
    episodes = json.loads((ROOT / "data/PILOT_EPISODES_PRIVATE.json").read_text())
    traces = {t["id"]: t for t in json.loads((ROOT / "data/STATE_PUBLIC.json").read_text())}
    raster_manifest = json.loads((ROOT / "data/SEVIR_ARRAYS.json").read_text())
    public = {"traces": traces, "static": {}}
    static_specs, native_manifests = [], {}
    for episode in episodes:
        ids = relevant_ids(episode)[:2]
        text, assets = request(episode, ids, "image", "full", 2)
        key = episode["id"] + ":fixed2_image"
        attached = []
        for asset in assets:
            sha = digest(asset["png"])
            path = "assets/" + sha + ".png"
            if not (batch / path).exists():
                (batch / path).write_bytes(asset["png"])
            attached.append({"id": asset["id"], "path": path, "sha256": sha})
        public["static"][key] = {"system": SYSTEM, "public": text, "assets": attached}
        static_specs.append({"episode": episode["id"], "condition": "fixed2_image", "public_key": key,
                             "budget": 2, "read_ids": ids})
        if episode["family"] != "SEVIR":
            continue
        ids = [c["id"] for c in legal_cards(episode)]
        text, _ = request(episode, ids, "image", "full", 4)
        text["representation_note"] = ("Images show the actual archived VIL pixel arrays using a fixed color scale; "
            "positive/negative counts are not printed. Only the left square in each attachment is data. "
            "Each2x2display block is one original pixel. Use the color legend and keep the declared full-frame denominator.")
        key = episode["id"] + ":native_vil_full"
        attached = []
        for card in sorted(legal_cards(episode), key=lambda c: c["id"]):
            png, manifest = render(card, episode, raster_manifest)
            sha = digest(png)
            path = "assets/" + sha + ".png"
            if not (batch / path).exists():
                (batch / path).write_bytes(png)
            native_manifests[sha] = manifest
            attached.append({"id": card["id"], "path": path, "sha256": sha})
        public["static"][key] = {"system": SYSTEM, "public": text, "assets": attached}
        static_specs.append({"episode": episode["id"], "condition": "native_vil_full", "public_key": key,
                             "budget": 4, "read_ids": ids})
    dump(batch / "PUBLIC.json", public)
    dump(batch / "NATIVE_RENDER_MANIFEST.json", native_manifests)
    tasks, workers = {}, {}
    for model, worker_ids in [("qwen3vl_8b", ["0", "1"]), ("qwen3vl_32b", ["2", "3"])]:
        for worker in worker_ids:
            workers[worker] = {"model": model, "tasks": [], "max_calls": 0}
        planned = []
        for trace in traces:
            for carrier in ["full_history", "last_state"]:
                planned.append({"kind": "state", "trace": trace, "carrier": carrier, "max_calls": 7})
        for spec in static_specs:
            planned.append({"kind": "static", **spec, "max_calls": 1})
        planned.sort(key=lambda t: digest(json.dumps(t, sort_keys=True).encode()))
        for index, task in enumerate(planned):
            tid = "d" + digest((model + json.dumps(task, sort_keys=True)).encode())[:16]
            worker = worker_ids[index % 2]
            tasks[tid] = {"id": tid, "model": model, **task}
            workers[worker]["tasks"].append(tid)
            workers[worker]["max_calls"] += task["max_calls"]
    checks = []
    settings = {**prior["settings"], "context_limit": 16384}
    for model, spec in models.items():
        frontend = load_frontend(spec, settings)
        records = []
        for trace in traces.values():
            for step in range(7):
                for carrier in ["full_history", "last_state"]:
                    placeholder = {"wind_kt": 999, "source_id": "nxxxxxxxxxx", "issue_time": "2024-01-01T00:00:00+00:00"}
                    state = state_request(trace, step, carrier, placeholder if step else None)
                    _, record = prepare(frontend, "vl", state, batch, settings)
                    records.append({"kind": "state", "trace": trace["id"], "step": step, "carrier": carrier, **record})
        for key, state in public["static"].items():
            _, record = prepare(frontend, "vl", state, batch, settings)
            records.append({"kind": "static", "key": key, **record})
        dump(batch / ("CPU_PREFLIGHT_" + model + ".json"), records)
        checks.append({"model": model, "profiles": len(records), "max_input_tokens": max(r["input_tokens"] for r in records)})
    for name in ["model_adapter.py", "model_adapter_intern.py", "diagnostic_backend.py", "state_inputs.py"]:
        shutil.copy2(ROOT / "code" / name, batch / "source" / name)
    shutil.copy2(ROOT / "code/extra_worker.py", batch / "source/gpu_worker.py")
    plan = {"created_at": datetime.now(timezone.utc).isoformat(), "wave": "wave5-diag", "models": models,
        "workers": workers, "tasks": tasks, "settings": settings, "max_requests": sum(w["max_calls"] for w in workers.values()),
        "max_worker_seconds": 14400, "max_concurrent_gpus": 4, "deadline_unix": prior["deadline_unix"],
        "runtime_files": prior["runtime_files"], "runtime_versions": prior["runtime_versions"], "preflight": checks,
        "bound_files": {str(p.relative_to(batch)): sha_file(p) for p in batch.rglob("*") if p.is_file()},
        "private_reference_hashes": {p: sha_file(ROOT / p) for p in
            ["data/PILOT_EPISODES_PRIVATE.json", "data/STATE_REFERENCES_PRIVATE.json"]},
        "fixed_acquisition": "First two compatible IDs in sorted catalog order; selection never reads hidden values; one model finalization.",
        "state_comparison": "Full delivered source history versus previous model state plus new source; information and token cost differ, not a token-matched algorithm claim.",
        "native_visual_limit": "Exploratory VIL source-raster rendering versus privileged count tables; no SAR or general perception claims.",
        "scope_amendment_sha256": sha_file(ROOT / "SCOPE_AMENDMENT_01.json"), "development_only": True}
    dump(batch / "PLAN.json", plan)
    print(json.dumps({"tasks": len(tasks), "max_calls": plan["max_requests"], "preflight": checks,
                      "sha256": sha_file(batch / "PLAN.json")}))


if __name__ == "__main__":
    main()
