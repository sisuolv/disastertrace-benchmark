"""Continue the unchanged twelve-source scope after a pre-network import failure."""

import os
import subprocess
import sys
import traceback
from pathlib import Path

from disastertrace.local_eval.storage import digest, now, read, verify_seal, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"


def main():
    previous = read(HERE / "finalization_002/result.json")
    if (
        previous["status"] != "failed"
        or len(previous["steps"]) != 7
        or any(s["exit_code"] for s in previous["steps"][:6])
        or previous["steps"][-1]["name"] != "07_nhc_acquisition"
    ):
        raise ValueError("unexpected prior recovery boundary")
    source = PROJECT / "artifacts/nhc_forecast_source_v1"
    if (source / "acquisition").exists():
        raise ValueError("an existing acquisition claim cannot be reused")
    package = verify_seal(source / "source_execution_v2")
    if package["package_id"] != read(source / "SOURCE_RUNTIME_V2.json")["source_package_id"]:
        raise ValueError("source runtime binding differs")
    directory = HERE / "finalization_003"
    directory.mkdir(exist_ok=False)
    write(
        directory / "claim.json",
        {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__)},
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(p in k.upper() for p in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        CUDA_VISIBLE_DEVICES="",
        PYTHONPATH=str(source / "source_execution_v2/src"),
    )
    commands = [
        (
            "01_import_scope",
            [
                CPU,
                "-c",
                "from disastertrace.forecast_source.pipeline import verify_scope; import sys; s=verify_scope(sys.argv[1], acquisition=True); print({'scope_id':s['scope_id'],'planned':s['planned_bodies']})",
                str(source),
            ],
        ),
        (
            "02_acquire",
            [
                CPU,
                "-m",
                "disastertrace.forecast_source.pipeline",
                "acquire",
                "--bundle",
                str(source),
            ],
        ),
        (
            "03_review",
            [
                CPU,
                "-m",
                "disastertrace.forecast_source.pipeline",
                "review",
                "--bundle",
                str(source),
                "--output",
                str(source / "review_v1"),
            ],
        ),
        (
            "04_verify",
            [
                CPU,
                "-m",
                "disastertrace.forecast_source.pipeline",
                "verify",
                "--bundle",
                str(source),
                "--output",
                str(source / "review_v1"),
            ],
        ),
    ]
    steps, result = [], {"status": "failed", "additional_model_calls": 0, "new_gpu_jobs": 0}
    try:
        for name, argv in commands:
            folder = directory / name
            folder.mkdir(exist_ok=False)
            write(folder / "intent.json", {"at": now(), "argv": argv})
            with (folder / "output.log").open("x") as log:
                completed = subprocess.run(
                    argv,
                    cwd=PROJECT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=600,
                    check=False,
                )
            step = {
                "name": name,
                "exit_code": completed.returncode,
                "at": now(),
                "log_sha256": digest(folder / "output.log"),
            }
            write(folder / "result.json", step)
            steps.append(step)
            print(step, flush=True)
            if completed.returncode:
                raise RuntimeError("source continuation failed: " + name)
        result["status"] = "passed"
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    result.update(steps=steps, finished_at=now())
    write(directory / "result.json", result)
    print(result, flush=True)
    return int(result["status"] != "passed")


if __name__ == "__main__":
    sys.exit(main())
