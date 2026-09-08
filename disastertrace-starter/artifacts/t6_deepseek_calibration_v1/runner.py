"""One detached T6 launch from frozen sources; no automatic retry or restart."""

import argparse
import getpass
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_files(root):
    manifest = read(root / "launch_manifest.json")
    for relative, expected in manifest["files"].items():
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("unsafe frozen path")
        if not path.is_file() or sha(path) != expected:
            raise ValueError("frozen file mismatch: " + relative)
    return manifest


def frozen_modules():
    sys.path.insert(0, str(HERE / "frozen/src"))
    from disastertrace.automated import calibration_report, live_calibration, live_calibration_audit
    from disastertrace.automated.run_store import durable_json

    if not Path(live_calibration.__file__).resolve().is_relative_to(HERE / "frozen"):
        raise ValueError("collector did not load from the frozen copy")
    return live_calibration, live_calibration_audit, calibration_report, durable_json


def verify(*, live_authorization=False):
    manifest = validate_files(HERE)
    live, _, _, _ = frozen_modules()
    plan = live.verify_execution(HERE / "execution")
    if (
        plan["execution_id"] != manifest["execution_id"]
        or plan["planned_opportunities"] != 270
        or plan["budget"]["allowance"] != "3.00"
    ):
        raise ValueError("frozen launch scope changed")
    if live_authorization:
        live._authorize(plan, read(HERE / "authorization.json"))
    return manifest, plan


def execute(*, diagnostic=False):
    manifest, _ = verify(live_authorization=not diagnostic)
    live, audit_module, report_module, durable_json = frozen_modules()
    run = HERE / "diagnostic/run" if diagnostic else Path(manifest["run_output"])
    auxiliary = HERE / "diagnostic" if diagnostic else HERE / "runtime"
    auxiliary.mkdir(parents=True, exist_ok=True)
    if diagnostic:
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def progress(kind, index):
        if kind != "decision":
            return
        try:
            durable_json(
                auxiliary / "progress.json",
                {
                    "finalized": index + 1,
                    "planned": 270,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "diagnostic": diagnostic,
                },
            )
        except OSError:
            pass
        print("finalized", index + 1, "/ 270", flush=True)

    result = {"diagnostic": diagnostic, "execution_id": manifest["execution_id"]}
    try:
        result["collection"] = live.collect(
            HERE / "execution",
            run,
            transport=live.diagnostic_transport if diagnostic else None,
            registry=HERE / "diagnostic/registry" if diagnostic else None,
            authorization=None if diagnostic else read(HERE / "authorization.json"),
            fault=progress,
        )
    except Exception as exc:
        result["collection_error_type"] = type(exc).__name__
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        audit = audit_module.audit_run(HERE / "execution", run)
        result["audit"] = {
            k: v
            for k, v in audit.items()
            if k not in {"records", "histories", "pending", "accounting_rows"}
        }
        report = report_module.report_run(HERE / "execution", run, auxiliary / "report")
        result["report"] = {
            k: report[k]
            for k in (
                "complete",
                "mode",
                "attempted",
                "received",
                "unsubmitted",
                "selected_output_tokens",
                "live_recommendation",
                "model_api_calls",
                "stop_reason",
            )
        }
    except Exception as exc:
        result["finalization_error_type"] = type(exc).__name__
    result["ended_at"] = datetime.now(timezone.utc).isoformat()
    durable_json(auxiliary / "completion.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "audit"}), flush=True)
    return (
        0
        if result.get("report", {}).get("complete") and "collection_error_type" not in result
        else 2
    )


def launch():
    manifest, _ = verify(live_authorization=True)
    runtime = HERE / "runtime"
    if runtime.exists() or Path(manifest["run_output"]).exists():
        raise ValueError("initial launch already claimed; inspect existing run, never relaunch")
    credential = os.environ.get("DEEPSEEK_API_KEY") or getpass.getpass(
        "DeepSeek API key (hidden): "
    )
    if not credential or any(char.isspace() for char in credential):
        raise ValueError("missing or invalid credential")
    runtime.mkdir()
    _, _, _, durable_json = frozen_modules()
    durable_json(
        runtime / "launch_intent.json",
        {
            "execution_id": manifest["execution_id"],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "run_output": manifest["run_output"],
            "automatic_restart": False,
        },
    )
    env = os.environ.copy()
    for key in list(env):
        if any(part in key.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD")):
            env.pop(key)
    env.pop("DISASTERTRACE_OFFLINE", None)
    env["DEEPSEEK_API_KEY"] = credential
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(HERE / "frozen/src")
    command = [sys.executable, "-u", str(Path(__file__).resolve()), "worker"]
    with (runtime / "worker.log").open("xb") as log:
        process = subprocess.Popen(
            command,
            cwd=HERE,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    env.pop("DEEPSEEK_API_KEY", None)
    credential = None
    record = {
        "pid": process.pid,
        "command": command,
        "execution_id": manifest["execution_id"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "run_output": manifest["run_output"],
        "model_request_limit": 270,
        "allowance_usd": "3.00",
    }
    durable_json(runtime / "process.json", record)
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "diagnostic", "launch", "worker"))
    args = parser.parse_args()
    if args.command == "verify":
        manifest, plan = verify(live_authorization=True)
        print(json.dumps({"valid": True, "execution_id": plan["execution_id"], "model_calls": 0}))
    elif args.command == "diagnostic":
        raise SystemExit(execute(diagnostic=True))
    elif args.command == "worker":
        raise SystemExit(execute())
    else:
        launch()
