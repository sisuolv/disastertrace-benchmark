"""CPU-only recovery after the preserved worker's stop-token audit failure."""

import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

from disastertrace.local_eval.storage import digest, now, read, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
GRAMMAR_CPU = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"


def main():
    if read(HERE / "finalization_001/result.json")["status"] != "failed":
        raise ValueError("the original failure record must remain present")
    completion = read(PROJECT / "work/p6-live-v1/model/completion.json")
    if completion["complete"] is not True or completion["raw_received"] != 2160:
        raise ValueError("this recovery expects the complete preserved capture")
    directory = HERE / "finalization_002"
    directory.mkdir(exist_ok=False)
    write(
        directory / "claim.json",
        {"at": now(), "script_sha256": digest(__file__), "pid": os.getpid()},
    )
    execution = HERE / "execution_live_02"
    run = PROJECT / "work/p6-live-v1/model"
    report = HERE / "reports/model_review_v2"
    review_source = HERE / "token_text_review_v2/review_source"
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(p in k.upper() for p in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        CUDA_VISIBLE_DEVICES="",
        TOKENIZERS_PARALLELISM="false",
        PYTHONPATH=str(review_source / "src"),
    )
    steps = []

    def command(name, argv, child_env=env, timeout=1800):
        folder = directory / name
        folder.mkdir(exist_ok=False)
        write(folder / "intent.json", {"at": now(), "argv": argv, "timeout_seconds": timeout})
        start = time.monotonic()
        with (folder / "output.log").open("x") as log:
            completed = subprocess.run(
                argv,
                cwd=PROJECT,
                env=child_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        result = {
            "name": name,
            "exit_code": completed.returncode,
            "finished_at": now(),
            "wall_seconds": time.monotonic() - start,
            "log_sha256": digest(folder / "output.log"),
        }
        write(folder / "result.json", result)
        steps.append(result)
        print(result, flush=True)
        if completed.returncode:
            raise RuntimeError("CPU recovery failed: " + name)

    result = {"status": "failed", "additional_model_calls": 0, "new_gpu_jobs": 0}
    try:
        common = ["--execution", str(execution), "--run", str(run), "--output", str(report)]
        command("01_report", [CPU, "-m", "disastertrace.repeat_live_review.cli", "report", *common])
        command(
            "02_verify_report",
            [CPU, "-m", "disastertrace.repeat_live_review.cli", "verify-report", *common],
        )
        command(
            "03_token_mask_replay",
            [
                GRAMMAR_CPU,
                "-m",
                "disastertrace.repeat_live_review.grammar",
                "--execution",
                str(execution),
                "--run",
                str(run),
                "--output",
                str(HERE / "grammar_model"),
            ],
        )
        command("04_model_attribution", [CPU, str(HERE / "analyze_model.py")])
        copied = PROJECT / "work/p6-live-portable-review-v2"
        copied.mkdir(exist_ok=False)
        for source, name in (
            (execution, "execution"),
            (run, "run"),
            (report, "report"),
            (review_source, "review_source"),
        ):
            shutil.copytree(source, copied / name)
        command(
            "05_cpu_relocation",
            [
                CPU,
                "-m",
                "disastertrace.repeat_live_review.portable",
                "--copy",
                str(copied),
                "--original-project",
                str(PROJECT),
                "--model-directory",
                "/mnt/afs/260010168/models/Qwen3-8B-modelscope-pinned-v1",
                "--output",
                str(copied / "CPU_RELOCATION.json"),
            ],
            {**env, "PYTHONPATH": str(copied / "review_source/src")},
        )
        shutil.copyfile(copied / "CPU_RELOCATION.json", HERE / "CPU_RELOCATION.json")
        command(
            "06_historical_acceptance",
            [
                str(PROJECT / ".venv/bin/python"),
                str(PROJECT / "artifacts/p6_offline_v1/accept_offline.py"),
                "--verify",
            ],
            {**env, "PYTHONPATH": str(PROJECT / "src")},
        )
        source = PROJECT / "artifacts/nhc_forecast_source_v1"
        source_env = {**env, "PYTHONPATH": str(source / "acquisition_source/src")}
        command(
            "07_nhc_acquisition",
            [
                CPU,
                "-m",
                "disastertrace.forecast_source.pipeline",
                "acquire",
                "--bundle",
                str(source),
            ],
            source_env,
            600,
        )
        for step, operation in (("08_nhc_consensus", "review"), ("09_nhc_verify", "verify")):
            command(
                step,
                [
                    CPU,
                    "-m",
                    "disastertrace.forecast_source.pipeline",
                    operation,
                    "--bundle",
                    str(source),
                    "--output",
                    str(source / "review_v1"),
                ],
                source_env,
            )
        result["status"] = "passed"
    except BaseException as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    result.update(steps=steps, finished_at=now())
    write(directory / "result.json", result)
    print(result, flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
