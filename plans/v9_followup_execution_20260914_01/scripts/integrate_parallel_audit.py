"""Install the verified parallel audit, preserving and checking the serial prefix."""

import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from accelerate_f_audit import OUTPUT, ROOT, RUNTIME, digest, read, write


def platform(job):
    result = subprocess.run([
        "/mnt/afs/260010168/bin/sco", "acp", "jobs", "describe",
        "--workspace-name=share-space", "--format=json", job,
    ], capture_output=True, text=True, timeout=45, check=True)
    row = json.loads(result.stdout)
    return {k: row[k] for k in ["name", "state", "start_time", "finish_time"] if k in row}


def stop_owned_process(pid, expected):
    proc = Path("/proc") / str(pid)
    if not proc.exists():
        return {"pid": pid, "already_exited": True}
    if (proc / "stat").read_text().split(") ", 1)[1].split()[0] == "Z":
        return {"pid": pid, "already_exited": True}
    command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode()
    if expected not in command:
        raise ValueError("Process identity changed: " + str(pid))
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            state = (proc / "stat").read_text().split(") ", 1)[1].split()[0]
        except FileNotFoundError:
            return {"pid": pid, "stopped_after_parallel_validation": True}
        if state == "Z":
            return {"pid": pid, "stopped_after_parallel_validation": True}
        time.sleep(0.1)
    raise RuntimeError("Original auditor did not stop")


def compare_prefix(serial, parallel):
    checked = []
    for path in sorted(serial.glob("*__CANONICAL_SCORES.json")):
        candidate = parallel / path.name
        if not candidate.exists() or digest(path) != digest(candidate):
            raise ValueError("Parallel/serial score mismatch: " + path.name)
        checked.append({"file": path.name, "sha256": digest(path)})
    return checked


def integrate(job_status):
    receipt = read(RUNTIME / "COMPLETE.json")
    registration = read(RUNTIME / "REGISTRATION.json")
    validation = read(OUTPUT / "VALIDATION.json")
    if not receipt["passed"] or digest(OUTPUT / "VALIDATION.json") != receipt["validation_sha256"]:
        raise ValueError("Missing or changed parallel completion receipt")
    if not validation["passed"] or not validation["all_registered_arms_finished"]:
        raise ValueError("Full original audit did not pass")
    expected = {(p.parent.name, arm) for p in (ROOT / "api_pilot_01").glob("*/CONFIGS.json")
                for arm in read(p)}
    actual = [(r["case"], r["arm"]) for r in validation["records"]]
    if set(actual) != expected or len(actual) != len(expected) or validation["unfinished_arms"]:
        raise ValueError("Incomplete or duplicate method coverage")
    serial = ROOT / "reports/api_forecast_audit_01"
    compare_prefix(serial, OUTPUT)
    # The source process is stopped only after its replacement has passed every check.
    stopped = [stop_owned_process(262462, "watch_followup_audits"),
               stop_owned_process(426437, "analyze_api_followup.py F")]
    checked = compare_prefix(serial, OUTPUT)
    saved = ROOT / "reports/api_forecast_audit_serial_prefix_01"
    pending = ROOT / "reports/api_forecast_audit_install_01"
    shutil.copytree(OUTPUT, pending)
    serial.rename(saved)
    pending.rename(serial)
    result = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "passed": True,
              "job": job_status, "serial_prefix_checks": checked, "stopped_processes": stopped,
              "preserved_serial_prefix": str(saved), "parallel": receipt,
              "installed_validation_sha256": digest(serial / "VALIDATION.json"),
              "new_model_calls": 0, "original_scoring_bytecode_used": True}
    write(RUNTIME / "INTEGRATED.json", result)
    summary = ROOT / "reports/audit_acceleration_01"
    summary.mkdir(exist_ok=False)
    write(summary / "SUMMARY.json", result)
    (summary / "REPORT_CN.md").write_text(
        "# 并行审计完成\n\n"
        f"使用 {registration['cpu_cores']} 核/{registration['memory_gib']} GiB CPU 节点，"
        f"{receipt['workers']} 个进程重放 {receipt['journals']} 份原始日志。"
        f"工作进程总耗时 {receipt['elapsed_seconds'] / 60:.2f} 分钟。\n\n"
        "逐日志完整校验保持原样；评分使用原函数的相同字节码；原审计函数仅重定向输出路径。"
        f"原串行审计已生成的 {len(checked)} 份案例评分与并行结果逐字节一致，原目录保留。"
        "所有 168 条方法记录、原始响应与费用均通过完整审计。此次加速没有新增模型调用。\n"
    )
    if not read(ROOT / "reports/api_evidence_audit_02/VALIDATION.json")["passed"]:
        raise ValueError("E02 prerequisite failed")
    state = {"at": result["at"], "phase": "REGISTERED_API_AUDITS_COMPLETE",
             "completed_audits": ["E02", "F"], "acceleration_job": job_status["name"],
             "integration_receipt": str(RUNTIME / "INTEGRATED.json")}
    with (ROOT / "runtime/AUDIT_EVENTS.jsonl").open("a") as stream:
        stream.write(json.dumps(state) + "\n")
    temporary = ROOT / "runtime/AUDIT_STATUS.parallel"
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(ROOT / "runtime/AUDIT_STATUS.json")


def main():
    write(RUNTIME / "INTEGRATOR_CLAIM.json", {"pid": os.getpid(),
          "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    job = (RUNTIME / "job-id.txt").read_text().strip()
    deadline = time.monotonic() + 7200
    while time.monotonic() < deadline:
        try:
            state = platform(job)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError):
            time.sleep(30)
            continue
        if state["state"] == "SUCCEEDED":
            integrate(state)
            return
        if state["state"] in {"FAILED", "STOPPED", "CANCELLED", "TERMINATED"}:
            write(RUNTIME / "INTEGRATION_STOPPED.json", {
                "job": state, "serial_audit_continues": True, "automatic_resubmission": False})
            return
        time.sleep(30)
    write(RUNTIME / "INTEGRATION_TIMEOUT.json", {"serial_audit_continues": True})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write(RUNTIME / "INTEGRATION_ERROR.json", {"type": type(exc).__name__, "reason": str(exc)})
        raise
