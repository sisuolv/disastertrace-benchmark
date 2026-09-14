"""Check frozen experiment bytes and staged identities without writing Git state."""

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(base, files):
    total = 0
    for relative, expected in files.items():
        path = base / relative
        if not path.resolve().is_relative_to(base.resolve()) or sha(path) != expected:
            raise ValueError("Changed frozen file: " + str(path))
        total += path.stat().st_size
    return {"files": len(files), "bytes": total, "all_match": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    previous = read(HERE / "PRESERVATION_CHECK_2354.json")
    frozen = []
    for row in previous["frozen_batches"]:
        base = HERE / "gpu" / row["batch"]
        if sha(base / "PLAN.json") != row["plan_sha256"]:
            raise ValueError("Changed frozen plan: " + row["batch"])
        plan = read(base / "PLAN.json")
        checked = verify_files(base, plan["files"])
        record = dict(batch=row["batch"], plan_sha256=row["plan_sha256"], **checked)
        if "evaluator_manifest_sha256" in plan:
            manifest = base / "EVALUATOR_MANIFEST.json"
            if sha(manifest) != plan["evaluator_manifest_sha256"]:
                raise ValueError("Changed evaluator manifest")
            record["separate_evaluator"] = verify_files(base, read(manifest))
        frozen.append(record)
    process = read(HERE / "FINALIZATION_PROCESS.json")
    if sha(Path(process["script"])) != process["script_sha256"]:
        raise ValueError("Changed original finalization orchestrator")
    pipeline = read(HERE / "finalization_pipeline_01/STARTED.json")
    for name, expected in pipeline["script_hashes"].items():
        if sha(HERE / "scripts" / name) != expected:
            raise ValueError("Changed bound analysis script: " + name)
    spec = importlib.util.spec_from_file_location(
        "index_preservation", HERE / "gpu/index_preservation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index = module.verify_index()
    result = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "passed": True,
        "frozen_batches": frozen,
        "original_finalizer_and_five_bound_scripts_unchanged": True,
        "git_index": index,
        "new_model_calls": 0,
        "git_mutations": 0,
        "executed_source_sha256": sha(Path(__file__)),
        "weights_rehashed": False,
        "weight_evidence": "Original GPU hardware/model-file receipts; this check covers frozen code, data, policy and evaluator bytes.",
    }
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"passed": True, "bound_files": sum(r["files"] for r in frozen)}))


if __name__ == "__main__":
    main()
