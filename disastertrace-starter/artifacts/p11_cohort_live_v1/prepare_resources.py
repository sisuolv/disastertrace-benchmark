"""Reverify and copy already pinned resources; no downloads or model execution."""

from pathlib import Path
import shutil

from disastertrace.cohort_live import package, profiles
from disastertrace.forecast_task.common import digest, fingerprint, inventory, read, seal, verify
from disastertrace.forecast_live.storage import now, write

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def main():
    task = PROJECT / "artifacts/p10_forecast_cohort_v1/execution_01"
    acceptance = read(PROJECT / "artifacts/p10_forecast_cohort_v1/validation_01/FINAL_STATUS.json")
    if acceptance["status"] != "passed":
        raise ValueError("expanded task has not passed independent CPU relocation")
    task_manifest = verify(task)
    write(ROOT / "RESOURCE_CLAIM.json", {"at": now(), "script_sha256": digest(__file__), "new_downloads": 0, "model_calls": 0})
    registration = {"at": now(), "design_sha256": digest(ROOT / "DESIGN.md"),
                    "task_package_id": task_manifest["package_id"], "task_execution_id": read(task / "execution.json")["execution_id"],
                    "source_schedule_sha256": digest(task / "schedule.json"),
                    "expanded_model_scores_read": False, "p7_prior_development_scores_read": True,
                    "generation_authorized_by_this_document": False,
                    "model_profiles": {name: adapter.SETTINGS["model_id"] for name, adapter in profiles.ADAPTERS.items()},
                    "planned_answers": 2412, "combined_planned_answers": 4824,
                    "planned_output_reservation": 19759104, "max_parallel_h100": 4, "max_phase_seconds": 14400,
                    "autonomous_work_deadline": read(PROJECT / "artifacts/p7_forecast_live_v1/AUTONOMY_WINDOW.json")["autonomous_work_deadline"]}
    registration["design_id"] = fingerprint(registration)
    write(ROOT / "PREREGISTRATION.json", registration)
    deepseek = PROJECT / "artifacts/p9_forecast_model_v1/resources_01"
    original_resources = verify(deepseek)
    qwen_execution = PROJECT / "artifacts/p7_forecast_live_v1/execution_live_01"
    verify(qwen_execution)
    result = {}
    for name in profiles.ADAPTERS:
        destination = ROOT / ("resources_" + name + "_01")
        snapshot_root = qwen_execution if name == "qwen3" else deepseek
        snapshot = read(snapshot_root / "model_snapshot.json")
        if snapshot["model_id"] != profiles.ADAPTERS[name].SETTINGS["model_id"]:
            raise ValueError("pinned model profile differs")
        package.verify_model(snapshot)
        if name == "deepseek_r1":
            shutil.copytree(deepseek, destination)
            manifest = verify(destination)
        else:
            destination.mkdir(exist_ok=False)
            for filename in ("model_snapshot.json", "environment.json"):
                shutil.copyfile(snapshot_root / filename, destination / filename)
            for filename in ("backend_files.json",):
                shutil.copyfile(deepseek / filename, destination / filename)
            shutil.copytree(deepseek / "backend_source", destination / "backend_source")
            shutil.copytree(task / "tokenizers/qwen3", destination / "tokenizer")
            if read(destination / "environment.json") != read(deepseek / "environment.json"):
                raise ValueError("prior runtime environments differ")
            files = {f["path"]: f["sha256"] for f in snapshot["files"]}
            if any(files.get(k) != v for k, v in inventory(destination / "tokenizer").items()):
                raise ValueError("copied tokenizer differs from pinned checkpoint")
            write(destination / "resources.json", {"at": now(), "status": "passed", "model_calls": 0,
                  "new_downloads": 0, "model_identity": fingerprint(snapshot),
                  "environment_sha256": fingerprint(read(destination / "environment.json")),
                  "backend_files": read(destination / "backend_files.json"),
                  "checkpoint_hash_verification": "all_pinned_files_read_and_sha256_matched",
                  "backend_evidence_parent_package_id": original_resources["package_id"],
                  "checkpoint_evidence_parent_execution_id": read(qwen_execution / "execution.json")["execution_id"]})
            manifest = seal(destination)
        result[name] = {"resource_package_id": manifest["package_id"], "model_identity": fingerprint(snapshot)}
        print({"model_profile": name, **result[name]}, flush=True)
    write(ROOT / "RESOURCE_RESULT.json", {"at": now(), "status": "passed", "resources": result,
          "design_id": registration["design_id"], "model_calls": 0, "new_downloads": 0})


if __name__ == "__main__":
    main()
