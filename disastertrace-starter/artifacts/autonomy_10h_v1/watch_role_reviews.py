"""Audit the two prompt-role matrices against their independently verified P12 controls."""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import time
import traceback

from disastertrace.forecast_task.common import digest, inventory, read, write

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
TASKS = (("p13", "p13_prompt_role_v1", "deepseek_r1", "deepseek_user"),
         ("p14", "p14_qwen_prompt_role_v1", "qwen3", "qwen_user"))


def now():
    return datetime.now(timezone.utc).isoformat()


def command(argv, folder, label):
    write(folder / (label + "_intent.json"), {"at": now(), "argv": argv})
    log = folder / (label + ".log")
    env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONDONTWRITEBYTECODE="1",
               PYTHONNOUSERSITE="1", CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", OMP_NUM_THREADS="4")
    with log.open("x") as stream:
        result = subprocess.run(argv, cwd=PROJECT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    write(folder / (label + "_result.json"), {"at": now(), "exit_code": result.returncode, "log_sha256": digest(log)})
    if result.returncode:
        raise RuntimeError("role review command failed: " + label)


def main():
    output = ROOT / "role_reviews_01"
    output.mkdir(exist_ok=False)
    source = inventory(PROJECT / "src/disastertrace/role_review")
    write(output / "CLAIM.json", {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__),
          "analysis_source": source, "test_files": inventory(PROJECT / "tests/role_review"),
          "test_log_sha256": digest(ROOT / "validation/role_review_01.log"), "new_model_calls": 0})
    done, final = {}, {"status": "failed"}
    try:
        deadline = datetime.fromisoformat(read(PROJECT / "artifacts/p7_forecast_live_v1/AUTONOMY_WINDOW.json")["autonomous_work_deadline"])
        while len(done) < 2:
            for phase, name, profile, track in TASKS:
                key = phase + "_" + profile
                bundle = PROJECT / "artifacts" / name
                status = bundle / ("finalization_" + profile + "_01/FINAL_STATUS.json")
                base_review = ROOT / "cohort_reviews_01"
                base_verified = base_review / ("p12_" + profile + "_verify_result.json")
                if key in done or not status.exists() or not base_verified.exists():
                    continue
                if read(status)["status"] != "passed" or read(base_verified)["exit_code"] != 0:
                    raise RuntimeError("source or role audit did not pass: " + key)
                if inventory(PROJECT / "src/disastertrace/role_review") != source:
                    raise RuntimeError("bound role-analysis source changed")
                result = output / (key + ".json")
                argv = [CPU, "-m", "disastertrace.role_review", "analyze", "--track", track,
                        "--execution", str(bundle / ("execution_" + profile + "_live_01")),
                        "--run-root", str(PROJECT / ("work/" + phase + "-role-" + profile + "-model-v1")),
                        "--report", str(status.with_name("global_report.json")), "--output", str(result)]
                command(argv, output, key + "_analyze")
                command(argv + ["--verify"], output, key + "_verify")
                comparison = output / ("comparison_" + profile + ".json")
                argv = [CPU, "-m", "disastertrace.role_review", "compare", "--system-analysis",
                        str(base_review / ("p12_" + profile + ".json")), "--user-analysis", str(result),
                        "--output", str(comparison)]
                command(argv, output, "compare_" + profile)
                command(argv + ["--verify"], output, "compare_" + profile + "_verify")
                done[key] = {"analysis_id": read(result)["analysis_id"],
                             "comparison_id": read(comparison)["comparison_id"], "at": now()}
                print({"at": now(), "completed": key, **done[key]}, flush=True)
            if len(done) < 2:
                if datetime.now(timezone.utc) >= deadline:
                    final.update(status="window_ended_with_pending_reviews")
                    return 0
                time.sleep(30)
        final.update(status="passed")
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final.update(at=now(), new_model_calls=0, completed=done)
        write(output / "FINAL_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
