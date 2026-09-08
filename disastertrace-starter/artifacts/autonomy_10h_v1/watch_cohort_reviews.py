"""Analyze each final audited cohort once, then compare the two registered tracks."""

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
PHASES = {"p11": ("p11_cohort_live_v1", "native", "cohort"),
          "p12": ("p12_compact_grammar_v1", "default_spacing", "compact")}


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
    record = {"at": now(), "exit_code": result.returncode, "log_sha256": digest(log)}
    write(folder / (label + "_result.json"), record)
    if result.returncode:
        raise RuntimeError("review command failed: " + label)


def main():
    output = ROOT / "cohort_reviews_01"
    output.mkdir(exist_ok=False)
    source = inventory(PROJECT / "src/disastertrace/cohort_review")
    write(output / "CLAIM.json", {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__),
          "analysis_source": source, "test_files": inventory(PROJECT / "tests/cohort_review"),
          "test_log_sha256": digest(ROOT / "validation/cohort_review_02.log"), "new_model_calls": 0})
    done, comparisons, final = {}, {}, {"status": "failed"}
    try:
        deadline = datetime.fromisoformat(read(PROJECT / "artifacts/p7_forecast_live_v1/AUTONOMY_WINDOW.json")["autonomous_work_deadline"])
        while len(done) < 4:
            for phase, (bundle_name, track, label) in PHASES.items():
                for profile in ("qwen3", "deepseek_r1"):
                    key = phase + "_" + profile
                    bundle = PROJECT / "artifacts" / bundle_name
                    status = bundle / ("finalization_" + profile + "_01/FINAL_STATUS.json")
                    if key in done or not status.exists():
                        continue
                    if read(status)["status"] != "passed":
                        raise RuntimeError("predecessor audit did not pass: " + key)
                    if inventory(PROJECT / "src/disastertrace/cohort_review") != source:
                        raise RuntimeError("bound analysis source changed")
                    analysis = output / (key + ".json")
                    argv = [CPU, "-m", "disastertrace.cohort_review", "analyze", "--track", track,
                            "--execution", str(bundle / ("execution_" + profile + "_live_01")),
                            "--run-root", str(PROJECT / ("work/" + phase + "-" + label + "-" + profile + "-model-v1")),
                            "--report", str(status.with_name("global_report.json")), "--output", str(analysis)]
                    command(argv, output, key + "_analyze")
                    command(argv + ["--verify"], output, key + "_verify")
                    done[key] = {"analysis_id": read(analysis)["analysis_id"], "at": now()}
                    print({"at": now(), "completed": key, **done[key]}, flush=True)
            if len(done) < 4:
                if datetime.now(timezone.utc) >= deadline:
                    final.update(status="window_ended_with_pending_reviews", completed=done)
                    return 0
                time.sleep(30)
        for profile in ("qwen3", "deepseek_r1"):
            path = output / ("comparison_" + profile + ".json")
            argv = [CPU, "-m", "disastertrace.cohort_review", "compare", "--native", str(output / ("p11_" + profile + ".json")),
                    "--default-spacing", str(output / ("p12_" + profile + ".json")), "--output", str(path)]
            command(argv, output, "compare_" + profile)
            command(argv + ["--verify"], output, "compare_" + profile + "_verify")
            comparisons[profile] = read(path)["comparison_id"]
        final.update(status="passed", completed=done, comparisons=comparisons)
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final.update(at=now(), new_model_calls=0, completed=done, comparisons=comparisons)
        write(output / "FINAL_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
