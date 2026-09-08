"""Single-use native runtime validation; every subprocess command and exit is retained."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from disastertrace.qwen_role_live import package
from disastertrace.qwen_role_live.storage import now, write
from disastertrace.forecast_task.common import digest, inventory, read

PROJECT = Path(__file__).resolve().parents[2]
BUNDLE = Path(__file__).resolve().parent
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
GPU = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"


def run(name, argv, env, logroot):
    write(logroot / (name + "_intent.json"), {"argv": argv, "at": now()})
    log = logroot / (name + ".log")
    with log.open("x") as stream:
        result = subprocess.run(argv, cwd=PROJECT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    record = {"exit_code": result.returncode, "log_sha256": digest(log), "at": now()}
    write(logroot / (name + "_result.json"), record)
    print({"step": name, **record}, flush=True)
    if result.returncode:
        raise RuntimeError("offline validation failed: " + name)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("qwen3",), required=True)
    profile = parser.parse_args().profile
    os.chdir(PROJECT)
    gates = read(BUNDLE / "TEST_GATES.json")
    if gates["core_tests_exit_code"] != 0 or gates["backend_tests_exit_codes"][profile] != 0:
        raise ValueError("current model profile tests did not pass")
    if inventory(PROJECT / "src/disastertrace/qwen_role_live") != gates["source_files"]:
        raise ValueError("implementation changed after tests")
    if inventory(PROJECT / "tests/p14_qwen_role") != gates["test_files"]:
        raise ValueError("tests changed after gate binding")
    validation = BUNDLE / ("offline_validation_" + profile + "_01")
    validation.mkdir(exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               PYTHONPATH=str(PROJECT / "src"), CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", OMP_NUM_THREADS="4",
               VLLM_USE_V1="1", VLLM_ENABLE_V1_MULTIPROCESSING="0",
               FORECAST_TASK_EXECUTION=str(PROJECT / "artifacts/p10_forecast_cohort_v1/execution_01"),
               FORECAST_MODEL_RESOURCES=str(BUNDLE / ("resources_" + profile + "_01")))
    execution = BUNDLE / ("execution_" + profile + "_diagnostic_01")
    core = {"exit_code": gates["core_tests_exit_code"]}
    backend = {"exit_code": gates["backend_tests_exit_codes"][profile]}
    plan = package.freeze(env["FORECAST_TASK_EXECUTION"], env["FORECAST_MODEL_RESOURCES"], execution, model_profile=profile)
    env["PYTHONPATH"] = str(execution / "source")
    write(validation / "execution_receipt.json", {"execution_id": plan["execution_id"], "at": now()})
    proofs = {}
    runbase = PROJECT / ("work/p14-role-" + profile + "-diagnostics-v1")
    runbase.mkdir(exist_ok=False)
    for policy in ("latest_explicit", "invalid_even", "missing_even"):
        processes = []
        for worker in range(2):
            label = f"{policy}_worker_{worker}"
            argv = [CPU, "-u", "-m", "disastertrace.qwen_role_live", "collect", "--execution", str(execution),
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
        argv = [CPU, "-u", "-m", "disastertrace.qwen_role_live", "report", "--execution", str(execution),
                "--run-root", str(runbase / policy), "--output", str(report)]
        run(policy + "_report", argv, env, validation)
        argv[4] = "verify-report"
        run(policy + "_verify", argv, env, validation)
        score = read(report)
        expected = 2412 if policy == "latest_explicit" else 1224
        if score["scores"]["counts"]["all_correct"] != expected or score["counts"]["attempted"] != 2412:
            raise ValueError("native diagnostic denominator or semantic score differs")
        proofs[policy] = {"report_id": score["report_id"], "report_sha256": digest(report),
                          "planned": 2412, "attempted": 2412, "all_correct": expected, "verified": True}
    copied = PROJECT / ("work/p14-role-" + profile + "-portable-v1")
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
         "--isolation-root", str(copied), "--blocked-root", str(PROJECT),
         "--blocked-root", "/mnt/afs/260010168/models", "--review-spec", str(copied / "review_spec.json"),
         "--output", str(copied / "receipt.json")], env, validation)
    proof = {"status": "passed", "model_calls": 0, "source_files": plan["source_files"],
             "settings": plan["settings"], "task_package_id": plan["task_package_id"],
             "resource_package_id": plan["resource_package_id"], "design_id": plan["design_id"],
             "core_tests_exit_code": core["exit_code"], "backend_tests_exit_code": backend["exit_code"],
             "portable_review_exit_code": relocate["exit_code"], "diagnostics": proofs,
             "diagnostic_execution_id": plan["execution_id"], "at": now(),
             "receipt_sha256": digest(copied / "receipt.json")}
    from disastertrace.qwen_role_live.launch import validate_cpu
    validate_cpu(proof, plan)
    write(BUNDLE / ("CPU_ACCEPTANCE_" + profile + ".json"), proof)
    print({"status": "passed", "model_calls": 0, "diagnostics": proofs}, flush=True)


if __name__ == "__main__":
    main()
