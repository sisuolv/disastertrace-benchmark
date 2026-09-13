"""Freeze a same-calendar Qwen3-VL representation diagnostic and actual processors."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import socket
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / "disastertrace-starter/src"))

from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.policies import run_session
from gpu_worker import digest, save
from mm_inputs import prepare_inputs


def micros(value):
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=timezone.utc
    )
    return int(parsed.timestamp() * 1_000_000)


def main(args):
    import numpy as np
    from transformers import AutoProcessor

    batch = args.output.resolve()
    batch.mkdir(exist_ok=False)
    package = batch / "source/disastertrace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Frozen monitoring runtime."""\n')
    shutil.copytree(
        REPO / "disastertrace-starter/src/disastertrace/monitoring_v1",
        package / "monitoring_v1",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copyfile(BASE / "mm_worker.py", batch / "source/gpu_worker.py")
    shutil.copyfile(BASE / "mm_inputs.py", batch / "source/mm_inputs.py")
    shutil.copyfile(BASE / "freeze_mm.py", batch / "source/freeze_mm.py")
    bank_path = BASE / "calibration_bank_01/BANK.json"
    shutil.copyfile(bank_path, batch / "BANK.json")
    bank = json.loads(bank_path.read_text())
    old = json.loads(
        (
            REPO / "plans/v5_0910_feasibility_12h_20260910/gpu/wave1/PLAN.json"
        ).read_text()
    )
    model_spec = old["models"]["qwen3vl_8b"]
    processor = AutoProcessor.from_pretrained(
        model_spec["directory"],
        local_files_only=True,
        min_pixels=256 * 32 * 32,
        max_pixels=1024 * 32 * 32,
    )
    dataset = BASE / "regional_02"
    data = load_session(
        dataset, stations=["KSFO", "KOAK", "KSJC"], hours=72, threshold=1000
    )
    dates = ["2024-01-05T02:00:00+00:00", "2024-01-06T02:00:00+00:00"]
    cutoffs = [
        int(datetime.fromisoformat(day).timestamp() * 1_000_000) for day in dates
    ]
    data["opportunities"] = [o for o in data["opportunities"] if o["cutoff"] in cutoffs]
    ids = {o["opportunity_id"] for o in data["opportunities"]}
    targets = {o["target_id"] for o in data["opportunities"]}
    data["targets"] = [t for t in data["targets"] if t["target_id"] in targets]
    data["baseline_candidates"] = [
        b
        for b in data["baseline_candidates"]
        if b["target_id"] in targets and b["available_at"] <= max(cutoffs)
    ]
    data["e_f_pairs"] = [p for p in data["e_f_pairs"] if p["opportunity_id"] in ids]
    qids = {q for p in data["e_f_pairs"] for q in p["query_ids"]}
    data["query_catalog"] = [q for q in data["query_catalog"] if q["query_id"] in qids]
    data["query_results"] = [q for q in data["query_results"] if q["query_id"] in qids]
    if len(data["opportunities"]) != 18:
        raise ValueError("The frozen MM opportunity set has changed")
    save(batch / "POLICY_ENVIRONMENT.json", data)
    scenes, parent_costs = {}, []
    (batch / "images").mkdir()
    join = json.loads((BASE / "images_03/REGIONAL_IMAGE_JOIN.json").read_text())
    for cutoff, scene in zip(cutoffs, join["scenes"]):
        features_started = time.monotonic()
        source = BASE / "images_03" / scene["image_file"]
        array_source = BASE / "images_03" / scene["array_file"]
        if (
            digest(source) != scene["image_sha256"]
            or digest(array_source) != scene["array_sha256"]
        ):
            raise ValueError("Image/array source binding changed")
        shutil.copyfile(source, batch / "images" / scene["image_file"])
        shutil.copyfile(array_source, batch / "images" / scene["array_file"])
        with np.load(array_source) as archive:
            channels = archive["brightness_temperature_K"]
            features = {}
            for station, pixel in scene["station_pixels"].items():
                row, col = pixel["row"], pixel["column"]
                c7, c13 = map(float, channels[:, row, col])
                features[station] = {
                    "C07_K": c7,
                    "C13_K": c13,
                    "C07_minus_C13_K": c7 - c13,
                    "paired_best_quality": bool(archive["best_quality_pair"][row, col]),
                }
        for channel in scene["channels"]:
            source_path = BASE / channel["source_path"]
            if digest(source_path) != channel["sha256"]:
                raise ValueError("Native NetCDF source changed")
            parent_costs.append(
                {
                    "source": channel["source_path"],
                    "bytes": source_path.stat().st_size,
                    "sha256": channel["sha256"],
                }
            )
        available = (
            max(micros(c["date_created"]) for c in scene["channels"])
            + 5 * 60 * 1_000_000
        )
        if available >= cutoff - 600 * 1_000_000:
            raise ValueError("Scene is too late for the registered request start")
        scenes[str(cutoff)] = {
            "scene_id": scene["scene_id"],
            "available_at": available,
            "image_file": "images/" + scene["image_file"],
            "image_sha256": scene["image_sha256"],
            "array_file": "images/" + scene["array_file"],
            "array_sha256": scene["array_sha256"],
            "public_metadata": {
                "platform": "GOES-18",
                "channels": [7, 13],
                "time_coverage_start": scene["channels"][0]["time_coverage_start"],
                "time_coverage_end": scene["channels"][0]["time_coverage_end"],
                "roi_lonlat": join["roi_lonlat"],
                "quality_pair_fraction": scene["best_quality_pair_fraction"],
                "display": "fixed-scale C07 and C13 brightness temperatures; third panel C07-C13; airport markers",
                "support": "thermal sensor values only, not a surface visibility or fog label",
                "availability": "date_created plus declared 5min archive replay lag; not verified first-seen",
            },
            "numeric_features": {
                "nearest_station_pixels": features,
                "regional_statistics": scene["pixel_statistics"],
                "information_limit": "lossy summaries; do not preserve cloud geometry",
            },
            "feature_preparation_ms": math.ceil(
                (time.monotonic() - features_started) * 1000
            ),
        }
    config = {
        "seed": 20260912,
        "request_budget": 6,
        "forecast_call_cap": 18,
        "per_tick_forecast_cap": 9,
        "input_token_cap": 8192,
        "output_token_cap": 384,
        "call_compute_cap_ms": 120000,
        "wakeup_seconds": 600,
        "token_cap": 18 * (8192 + 384),
        "compute_ms_cap": 18 * 120000 + 600,
        "selector_kind": "round_robin",
        "isolation_mode": "actual_cost_clock",
        "allocation_mode": "global_budget",
        "authorization_mode": "session_shared",
        "protocol": "base_bound_override",
    }
    workers, preflight = {}, {}
    for i, representation in enumerate(
        ("text_only", "image", "numeric", "image_numeric")
    ):
        records = []

        def backend(
            system, request, call_id, representation=representation, records=records
        ):
            _, manifest = prepare_inputs(
                processor,
                system,
                request,
                representation,
                scenes[str(request["cutoff"])],
                batch,
            )
            if manifest["input_tokens"] > config["input_token_cap"]:
                raise ValueError("Actual MM processor exceeds input reservation")
            records.append(
                {
                    k: manifest[k]
                    for k in (
                        "input_tokens",
                        "visual_tokens",
                        "image_grid_thw",
                        "scene_id",
                        "representation",
                    )
                }
            )
            return json.dumps(
                {
                    "probability": request["common_baseline"]["probability"],
                    "e_status": "undetermined",
                    "decision": "follow",
                    "citations": [],
                }
            ), {
                "input_tokens": manifest["input_tokens"],
                "output_tokens": 64,
                "seconds": 0.001,
                "ended_with_eos": True,
            }

        trace = run_session(data, bank, config, backend=backend)
        if len(records) != 18 or len(trace["snapshots"]) != 18:
            raise ValueError("MM preflight lost an opportunity")
        preflight[str(i)] = records
        workers[str(i)] = [
            {
                "run_id": representation,
                "representation": representation,
                "data_file": "POLICY_ENVIRONMENT.json",
                "config": config,
            }
        ]
    save(batch / "PROCESSOR_PREFLIGHT.json", preflight)
    plan = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "cci_hostname": socket.gethostname(),
        "models": {"qwen3vl_8b": model_spec},
        "worker_models": {str(i): "qwen3vl_8b" for i in range(4)},
        "seed": 20260912,
        "max_new_tokens": 384,
        "context_limit": 12288,
        "max_generation_seconds": 90,
        "max_worker_seconds": 1800,
        "max_concurrent_gpus": 4,
        "max_calls_per_worker": 18,
        "maximum_model_calls": 72,
        "workers": workers,
        "scenes": scenes,
        "runtime_versions": {
            name: version(name)
            for name in (
                "torch",
                "transformers",
                "accelerate",
                "tokenizers",
                "safetensors",
                "Pillow",
                "numpy",
            )
        },
        "files": {
            str(p.relative_to(batch)): digest(p)
            for p in batch.rglob("*")
            if p.is_file()
        },
        "evaluation_bindings": {
            str(p.resolve()): digest(p)
            for p in (
                dataset / "private/OUTCOMES.json",
                dataset / "REGIONAL_JOIN_AUDIT.json",
                BASE / "images_03/REGIONAL_IMAGE_JOIN.json",
                bank_path,
            )
        },
        "fixed_sensor_collection": {
            "parent_product_requests": len(parent_costs),
            "parent_product_bytes": sum(p["bytes"] for p in parent_costs),
            "parent_products": parent_costs,
            "rule": "Same fixed collection paid by all four representation arms, including image-withheld ablation; not a query-selection experiment",
            "additional_numeric_preparation": "measured separately; summaries are lossy, not equal-information or privileged labels",
        },
        "outcomes_in_worker_package": False,
        "automatic_retries": 0,
        "interpretation": "Two real GOES-18 scenes, same 18 future report opportunities; exposed representation diagnostic; no fog truth or independent-process claim",
    }
    save(batch / "PLAN.json", plan)
    print(
        json.dumps(
            {
                "batch": str(batch),
                "plan_sha256": digest(batch / "PLAN.json"),
                "maximum_calls": 72,
                "processor_inputs": 72,
                "visual_tokens": sorted(
                    {r["visual_tokens"] for rows in preflight.values() for r in rows}
                ),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
