"""Assemble immutable replay inputs; never launch inference or copy weights."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
REPO = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if digest(source) != digest(destination):
        raise ValueError("Copy checksum differs")


def build(destination, batches):
    destination.mkdir(exist_ok=False)
    copy(HERE / "run_replay.py", destination / "run_replay.py")
    copy(HERE / "README_CN.md", destination / "README_CN.md")
    matrix = ROUND / "evidence_bundle/matrix_01"
    for source in matrix.glob("*.json"):
        copy(source, destination / "matrix" / source.name)
    for source in (matrix / "policy").glob("*.json"):
        copy(source, destination / "matrix/policy" / source.name)
    bindings = json.loads((matrix / "EVALUATOR_BINDINGS.json").read_text())
    portable = {}
    for index, (original, expected) in enumerate(bindings.items()):
        source = REPO / original
        if digest(source) != expected:
            raise ValueError("Original evaluator source changed")
        target = destination / "evaluator" / f"reference_{index:02}_OUTCOMES.json"
        copy(source, target)
        portable[original] = str(target.relative_to(destination))
    registry = {"schema": "disastertrace.portable_fixed_replay.v1", "batches": [], "evaluator_path_map": portable}
    for batch_name in batches:
        batch = ROUND / "gpu" / batch_name
        plan = json.loads((batch / "PLAN.json").read_text())
        target = destination / "batches" / batch_name
        for relative, expected in plan["files"].items():
            if digest(batch / relative) != expected:
                raise ValueError("Frozen batch input changed: " + relative)
            copy(batch / relative, target / relative)
        copy(batch / "PLAN.json", target / "PLAN.json")
        for worker, tasks in plan["workers"].items():
            directory = batch / ("worker-" + worker)
            completed = json.loads((directory / "COMPLETE.json").read_text())
            if completed["model_calls"] != len(tasks):
                raise ValueError("Batch has not completed")
            for name in ("COMPLETE.json", "HARDWARE.json"):
                copy(directory / name, target / directory.name / name)
            for item in tasks:
                for kind in ("request", "response"):
                    name = item["call_id"] + "-" + kind + ".json"
                    copy(directory / name, target / directory.name / name)
        registry["batches"].append({"name": batch_name, "path": str(target.relative_to(destination)), "plan_sha256": digest(batch / "PLAN.json"), "expected_calls": plan["expected_calls"]})
    model = json.loads((ROUND / "gpu" / batches[0] / "PLAN.json").read_text())["model"]
    for item in model["files"]:
        if item["path"] in {"tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "generation_config.json", "config.json", "LICENSE"}:
            source = Path(model["directory"]) / item["path"]
            if digest(source) != item["sha256"]:
                raise ValueError("Tokenizer/model metadata changed")
            copy(source, destination / "tokenizer" / item["path"])
    registry["original_project_prefix"] = str(REPO)
    registry["original_model_prefix"] = model["directory"]
    registry["scope"] = "Replay frozen visible inputs and recorded outputs; not raw archive reconstruction or new model inference."
    save(destination / "REGISTRY.json", registry)
    files = {str(path.relative_to(destination)): digest(path) for path in sorted(destination.rglob("*")) if path.is_file()}
    save(destination / "PACKAGE_MANIFEST.json", {"schema": "portable_replay_files.v1", "files": files})
    print(json.dumps({"package": str(destination), "files": len(files), "calls": sum(batch["expected_calls"] for batch in registry["batches"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batches", nargs="+", default=["fixed_matrix_01", "prompt_probe_01", "fact_truth_probe_01"])
    args = parser.parse_args()
    build(args.output.resolve(), args.batches)
