"""One fresh expanded-task freeze followed by isolated CPU reconstruction."""

import os
from pathlib import Path
import shutil
import subprocess
import traceback

from disastertrace.forecast_task.common import digest, fingerprint, read, write
from disastertrace.forecast_live.storage import now

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"


def main():
    output = ROOT / "validation_01"
    output.mkdir(exist_ok=False)
    write(output / "CLAIM.json", {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__), "model_calls": 0})
    env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               CUDA_VISIBLE_DEVICES="", USE_TORCH="0", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    results = []

    def run(name, argv):
        intent = {"name": name, "argv": argv, "started_at": now()}
        write(output / (name + "_intent.json"), intent)
        with (output / (name + ".log")).open("x") as stream:
            completed = subprocess.run(argv, cwd=PROJECT, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        result = {**intent, "finished_at": now(), "exit_code": completed.returncode, "log_sha256": digest(output / (name + ".log"))}
        write(output / (name + "_result.json"), result)
        results.append(result)
        print({"step": name, "exit_code": completed.returncode}, flush=True)
        if completed.returncode:
            raise RuntimeError(name + " failed; no replacement freeze or model call")

    final = {"status": "failed", "started_at": now()}
    try:
        execution = ROOT / "execution_01"
        run("build", [CPU, "-m", "disastertrace.forecast_cohort", "build", "--execution", str(execution),
            "--source-input", str(PROJECT / "artifacts/p10_source_catalog_v1/review_v2"), "--project", str(PROJECT),
            "--qwen-tokenizer", str(PROJECT / "artifacts/p7_forecast_task_v1/execution_v1/tokenizer"),
            "--deepseek-tokenizer", str(PROJECT / "artifacts/p9_forecast_model_v1/resources_01/tokenizer"),
            "--protocol", str(ROOT / "PROTOCOL.md")])
        isolated = PROJECT / "work/p10-cohort-task-portable-v1"
        isolated.mkdir(exist_ok=False)
        shutil.copytree(execution, isolated / "execution")
        shutil.copyfile(ROOT / "portable_review.py", isolated / "portable_review.py")
        run("cpu_relocation", [CPU, str(isolated / "portable_review.py"), "--execution", str(isolated / "execution"),
             "--isolation-root", str(isolated), "--blocked-root", str(PROJECT),
             "--blocked-root", "/mnt/afs/260010168/models", "--output", str(isolated / "receipt.json")])
        receipt = read(isolated / "receipt.json")
        if receipt["status"] != "passed" or receipt["cli_exits"] != [0, 0]:
            raise ValueError("CPU relocation did not pass")
        execution_record = read(execution / "execution.json")
        final.update(status="passed", execution_id=execution_record["execution_id"],
                     package_id=read(execution / "manifest.json")["package_id"], planned_per_model=2412,
                     candidate_total_model_answers=4824, model_calls=0, cpu_relocation=receipt)
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final.update(finished_at=now(), steps=results)
        final["status_id"] = fingerprint(final)
        write(output / "FINAL_STATUS.json", final)
        print({k: final[k] for k in ("status", "status_id", "finished_at")}, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
