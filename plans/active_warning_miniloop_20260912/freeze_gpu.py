"""Freeze a small, outcome-free development matrix before local model dispatch."""

import hashlib
import json
import shutil
import socket
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    batch = BASE / "gpu_01"
    batch.mkdir(exist_ok=False)
    dataset = BASE / "dataset_v2"
    ids = json.loads((dataset / "pilot_ids.json").read_text())
    episodes = [
        e for e in json.loads((dataset / "episodes.json").read_text()) if e["id"] in ids
    ]
    (batch / "episodes.json").write_text(json.dumps(episodes, indent=2) + "\n")
    source = batch / "source"
    package = source / "disastertrace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Frozen minimal model runtime."""\n')
    originals = REPO / "disastertrace-starter/src/disastertrace"
    for namespace, modules in {
        "active_forecast": ("schema.py", "provenance.py"),
        "active_warning_v1": (
            "__init__.py",
            "schema.py",
            "environment.py",
            "policies.py",
        ),
    }.items():
        dest = package / namespace
        dest.mkdir()
        if "__init__.py" not in modules:
            (dest / "__init__.py").write_text(
                '"""Frozen schema dependencies only."""\n'
            )
        for name in modules:
            shutil.copyfile(originals / namespace / name, dest / name)
    shutil.copyfile(BASE / "gpu_worker.py", source / "gpu_worker.py")
    old = json.loads(
        (
            REPO / "plans/v5_0910_feasibility_12h_20260910/gpu/wave1/PLAN.json"
        ).read_text()
    )
    arms = [
        ("fixed_forecast", 2),
        ("fixed_observation", 2),
        ("active_raw", 2),
        ("active_canonical", 2),
        ("all_read", 4),
    ]
    workers = {str(i): [] for i in range(4)}
    for index, episode_id in enumerate(ids):
        order = arms[index % len(arms) :] + arms[: index % len(arms)]
        scenarios = ("clean", "stale") if index % 2 == 0 else ("stale", "clean")
        for scenario in scenarios:
            for policy, budget in order:
                workers[str(index % 4)].append(
                    {
                        "run_id": episode_id + "-" + scenario + "-" + policy,
                        "episode_id": episode_id,
                        "scenario": scenario,
                        "policy": policy,
                        "budget": budget,
                    }
                )
    max_calls = max(
        sum(4 if task["policy"].startswith("active_") else 2 for task in tasks)
        for tasks in workers.values()
    )
    plan = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "cci_hostname": socket.gethostname(),
        "model": old["models"]["qwen3_8b"],
        "seed": 20260912,
        "do_sample": False,
        "thinking": False,
        "dtype": "bfloat16",
        "attention": "sdpa",
        "max_new_tokens": 384,
        "context_limit": 8192,
        "max_generation_seconds": 90,
        "max_worker_seconds": 3600,
        "max_concurrent_gpus": 4,
        "max_calls_per_worker": max_calls,
        "maximum_model_calls": sum(
            4 if t["policy"].startswith("active_") else 2
            for ts in workers.values()
            for t in ts
        ),
        "workers": workers,
        "pilot_targets": len(ids),
        "arms": arms,
        "runtime_versions": {
            name: version(name)
            for name in (
                "torch",
                "transformers",
                "pydantic",
                "accelerate",
                "tokenizers",
                "safetensors",
            )
        },
        "files": {
            str(p.relative_to(batch)): sha(p) for p in batch.rglob("*") if p.is_file()
        },
        "outcome_files_in_worker_package": False,
        "evaluation_bindings": {
            str(p.relative_to(REPO)): sha(p)
            for p in (
                originals / "active_warning_v1/scoring.py",
                dataset / "episodes.json",
                dataset / "outcomes_private.json",
                dataset / "pilot_ids.json",
                dataset / "SOURCE_BINDINGS.json",
                BASE / "build_data.py",
                BASE / "run_programs.py",
                BASE / "programs_01/SUMMARY_MODEL_PILOT.json",
                BASE / "PLAN_CN.md",
                BASE / "freeze_gpu.py",
                BASE / "launch_gpu.py",
            )
        },
        "automatic_retries": 0,
        "interpretation": "exposed development; controlled clock; text-only Qwen3-8B; no online claim",
        "comparisons": {
            "E1": "active_raw versus fixed policies at budget 2; identical forecast backend and renderer",
            "E2": "clean versus stale re-delivery; raw versus canonical is a combined representation/state diagnostic",
            "all_read": "budget 4 reference, not an equal-budget comparator to budget 2",
        },
    }
    (batch / "PLAN.json").write_text(json.dumps(plan, indent=2) + "\n")
    print(
        json.dumps(
            {
                "batch": str(batch),
                "plan_sha256": sha(batch / "PLAN.json"),
                "trajectories": sum(map(len, workers.values())),
                "maximum_calls": plan["maximum_model_calls"],
                "workers": {k: len(v) for k, v in workers.items()},
            }
        )
    )


if __name__ == "__main__":
    main()
