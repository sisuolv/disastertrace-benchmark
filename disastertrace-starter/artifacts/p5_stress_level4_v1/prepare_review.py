"""Copy complete review inputs, then observe an isolated CPU reconstruction."""

import shutil
import subprocess

from acp_common import CPU_PYTHON, FACTORS, HERE, PROJECT, runtime_env

from disastertrace.local_eval.storage import digest, now, read, write


def main():
    copied = PROJECT / "work/p5-portable-acp-review-001"
    copied.mkdir(exist_ok=False)
    new_bundle = copied / "artifacts/p5_stress_level4_v1"
    for factor in FACTORS:
        old = HERE / "units" / factor
        new = new_bundle / "units" / factor
        for name in ("execution_live", "model_report"):
            shutil.copytree(old / name, new / name)
        plan = read(old / "execution_live/execution.json")
        run = PROJECT / "work" / ("p5-qwen3-" + factor.replace("_", "-") + "-v1")
        if str(run) != plan["run_path"]:
            raise ValueError("unexpected canonical run")
        shutil.copytree(run, copied / "work" / run.name)
        new_runtime = new_bundle / "acp/phase_001" / factor
        new_runtime.mkdir(parents=True)
        for name in ("collect_result.json", "hardware.json"):
            shutil.copyfile(HERE / "acp/phase_001" / factor / name, new_runtime / name)
    base = HERE.parent / "p4_constrained_output_v1"
    for name in ("execution_live", "model_report"):
        shutil.copytree(base / name, copied / "artifacts/p4_constrained_output_v1" / name)
    shutil.copytree(
        PROJECT / "work/p4-qwen3-constrained-v1", copied / "work/p4-qwen3-constrained-v1"
    )
    for name in ("analysis", "stress_comparison"):
        shutil.copytree(HERE / name, new_bundle / name)
    for name in ("compare_stress.py", "analyze_p5.py", "verify_review.py"):
        shutil.copyfile(HERE / name, new_bundle / name)
    source = new_bundle / "units/revision_chain/execution_live/implementation_source/src"
    command = [
        CPU_PYTHON,
        str(new_bundle / "verify_review.py"),
        "--copy",
        str(copied),
        "--original-project",
        str(PROJECT),
        "--model-directory",
        "/mnt/afs/260010168/models/Qwen3-8B-modelscope-pinned-v1",
    ]
    observed = HERE / "portable_review"
    observed.mkdir(exist_ok=False)
    started = now()
    write(
        observed / "intent.json", {"command": command, "source": str(source), "started_at": started}
    )
    with (observed / "stdout.log").open("xb") as stream:
        outcome = subprocess.run(
            command,
            env=runtime_env(source, observed / "cache"),
            cwd=copied,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    write(
        observed / "result.json",
        {
            "command": command,
            "started_at": started,
            "finished_at": now(),
            "exit_code": outcome.returncode,
            "log_sha256": digest(observed / "stdout.log"),
        },
    )
    if outcome.returncode:
        raise SystemExit(outcome.returncode)
    result = read(copied / "verification_result.json")
    write(HERE / "portable_model_verification.json", result)
    print(result)


if __name__ == "__main__":
    main()
