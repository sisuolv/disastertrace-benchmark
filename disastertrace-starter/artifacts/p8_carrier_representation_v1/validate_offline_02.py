"""One-use paired-prefix validation after the native run independently finalizes."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import time

from disastertrace.carrier_repr import package
from disastertrace.carrier_repr.storage import now, write
from disastertrace.forecast_task.common import digest, read

PROJECT = Path(__file__).resolve().parents[2]
BUNDLE = Path(__file__).resolve().parent
NATIVE = PROJECT / "artifacts/p7_forecast_live_v1"
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
GPU = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"


def run(name, argv, env, logroot):
    write(logroot / (name + "_intent.json"), {"argv": argv, "at": now()})
    log = logroot / (name + ".log")
    with log.open("x") as stream:
        result = subprocess.run(argv, cwd=PROJECT, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    record = {"exit_code": result.returncode, "log_sha256": digest(log), "at": now()}
    write(logroot / (name + "_result.json"), record)
    print({"step": name, **record}, flush=True)
    if result.returncode:
        raise RuntimeError("offline validation failed: " + name)
    return record


def main():
    os.chdir(PROJECT)
    validation = BUNDLE / "offline_validation_02"
    validation.mkdir(exist_ok=False)
    write(validation / "DRIVER_CLAIM.json", {"at": now(), "script_sha256": digest(__file__), "model_calls": 0})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONPATH=str(PROJECT / "src"),
               CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               OMP_NUM_THREADS="4", VLLM_USE_V1="1", VLLM_ENABLE_V1_MULTIPROCESSING="0",
               FORECAST_TASK_EXECUTION=str(PROJECT / "artifacts/p7_forecast_task_v1/execution_v1"),
               FORECAST_P6_RESOURCES=str(PROJECT / "artifacts/p6_live_v1/execution_live_02"))
    core = run("core", [str(PROJECT / ".venv/bin/python"), "-m", "pytest", "-o", "addopts=", "-q", "tests/p8_carrier_repr"], env, validation)
    backend = run("installed_backend", [GPU, "-m", "pytest", "--import-mode=importlib", "-o", "addopts=", "-q",
                  "tests/p8_carrier_repr/installed_backend.py", "tests/p7_forecast_live/installed_backend.py"], env, validation)
    final_path = NATIVE / "finalization_01/FINAL_STATUS.json"
    deadline = datetime.fromisoformat(read(NATIVE / "AUTONOMY_WINDOW.json")["autonomous_work_deadline"])
    while not final_path.exists():
        if datetime.now(timezone.utc) >= deadline:
            raise RuntimeError("autonomous window ended before native finalization")
        print({"at": now(), "status": "waiting_for_independent_native_finalization"}, flush=True)
        time.sleep(30)
    final = read(final_path)
    report_path = NATIVE / "finalization_01/global_report.json"
    if final["status"] != "passed" or final["report_sha256"] != digest(report_path):
        raise ValueError("native run did not pass its independent finalizer")
    for name in ("token_replay.json", "cpu_relocated/receipt.json"):
        if read(NATIVE / "finalization_01" / name)["status"] != "passed":
            raise ValueError("native token or relocation verification failed")
    write(validation / "native_gate.json", {"at": now(), "final_status_sha256": digest(final_path),
          "report_id": final["report_id"], "native_counts": final["counts"]})
    source = BUNDLE / "source_prefixes_01"
    receipt = package.prepare_source(NATIVE / "execution_live_01", PROJECT / "work/p7-native-qwen3-v1",
                                     report_path, BUNDLE, source)
    write(validation / "source_receipt.json", receipt)
    execution = BUNDLE / "execution_diagnostic_01"
    plan = package.freeze(source, execution)
    env["PYTHONPATH"] = str(execution / "source")
    write(validation / "execution_receipt.json", {"execution_id": plan["execution_id"], "at": now()})
    context_path = validation / "context_check.json"
    context_code = "from disastertrace.carrier_repr.context import inspect; from disastertrace.carrier_repr.storage import write; import sys; write(sys.argv[2],inspect(sys.argv[1]))"
    run("context_check", [CPU, "-c", context_code, str(execution), str(context_path)], env, validation)
    proofs = {}
    runbase = PROJECT / "work/p8-carrier-diagnostics-v1"
    runbase.mkdir(exist_ok=False)
    for policy in ("latest_explicit", "invalid_even", "missing_even"):
        processes = []
        for worker in range(4):
            label = f"{policy}_worker_{worker}"
            argv = [CPU, "-u", "-m", "disastertrace.carrier_repr", "collect", "--execution", str(execution),
                    "--run-root", str(runbase / policy), "--worker", str(worker), "--policy", policy]
            write(validation / (label + "_intent.json"), {"argv": argv, "at": now()})
            log = validation / (label + ".log")
            stream = log.open("x")
            process = subprocess.Popen(argv, cwd=PROJECT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            processes.append((label, process, stream, log))
        codes = []
        for label, process, stream, log in processes:
            code = process.wait()
            stream.close()
            codes.append(code)
            write(validation / (label + "_result.json"), {"exit_code": code, "at": now(), "log_sha256": digest(log)})
        if any(codes):
            raise RuntimeError("diagnostic collector failed: " + policy)
        report = validation / (policy + "_report.json")
        argv = [CPU, "-u", "-m", "disastertrace.carrier_repr", "report", "--execution", str(execution),
                "--run-root", str(runbase / policy), "--output", str(report)]
        run(policy + "_report", argv, env, validation)
        argv[4] = "verify-report"
        run(policy + "_verify", argv, env, validation)
        score = read(report)
        expected = plan["diagnostic_expectations"][policy]
        if (score["scores"]["counts"]["all_correct"] != expected or score["counts"]["attempted"] != plan["eligible_answers"]
                or score["counts"]["planned"] != 844 or score["paired_representation"]["planned_pairs"] != 422):
            raise ValueError("paired diagnostic denominator or semantic score differs")
        proofs[policy] = {"report_id": score["report_id"], "report_sha256": digest(report), "planned": 844,
                          "attempted": plan["eligible_answers"], "all_correct": expected, "verified": True}
    copied = PROJECT / "work/p8-carrier-portable-v1"
    copied.mkdir(exist_ok=False)
    shutil.copytree(execution, copied / "execution")
    shutil.copytree(runbase, copied / "runs")
    (copied / "reports").mkdir()
    specs = []
    for policy in proofs:
        shutil.copyfile(validation / (policy + "_report.json"), copied / "reports" / (policy + ".json"))
        specs.append({"run": "runs/" + policy, "report": "reports/" + policy + ".json"})
    write(copied / "review_spec.json", specs)
    shutil.copyfile(BUNDLE / "portable_review.py", copied / "portable_review.py")
    relocate = run("portable", [CPU, str(copied / "portable_review.py"), "--execution", str(copied / "execution"),
         "--isolation-root", str(copied), "--blocked-root", str(PROJECT), "--blocked-root", "/mnt/afs/260010168/models",
         "--review-spec", str(copied / "review_spec.json"), "--output", str(copied / "receipt.json")], env, validation)
    portable = read(copied / "receipt.json")
    proof = {"status": "passed", "model_calls": 0, "source_files": plan["source_files"], "settings": plan["settings"],
             "task_package_id": plan["task_package_id"], "source_binding_id": plan["source_binding_id"],
             "core_tests_exit_code": core["exit_code"], "backend_tests_exit_code": backend["exit_code"],
             "portable_review_exit_code": relocate["exit_code"], "diagnostics": proofs,
             "context_check": {k: v for k, v in read(context_path).items() if k != "records"},
             "native_archive_replay": portable["native_archive_replay"], "diagnostic_execution_id": plan["execution_id"],
             "at": now(), "receipt_sha256": digest(copied / "receipt.json")}
    from disastertrace.carrier_repr.launch import validate_cpu
    validate_cpu(proof, plan)
    write(BUNDLE / "CPU_ACCEPTANCE.json", proof)
    print({"status": "passed", "model_calls": 0, "diagnostics": proofs}, flush=True)


if __name__ == "__main__":
    main()
