"""One detached P2 output-contract v2 development launch, without retries."""

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
EXECUTION_ID = "6285f92ac7af631816b272b14ff51f975464a11aabdca731815f581d607d684c"
OUTPUT_CONTRACT = {
    "version": "controlled_output_contract_v2",
    "system_message_sha256": "f4cfe17c214a7571de8e40a9467e9f2ee0f87e4172b3b181ecb6ad691305eb7e",
}


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
    frozen = HERE / "execution/dataset/implementation_source"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(frozen / "src"))
    from disastertrace.automated.run_store import durable_json
    from disastertrace.controlled import live, live_audit, live_report

    for module in tuple(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if name.startswith("disastertrace.") and getattr(module, "__file__", None):
            if not Path(module.__file__).resolve().is_relative_to(frozen):
                raise ValueError("implementation did not load from the frozen copy")
    return live, live_audit, live_report, durable_json


def verify(*, live_authorization=False):
    manifest = validate_files(HERE)
    live, _, _, _ = frozen_modules()
    plan = live.verify_execution(HERE / "execution")
    if (
        plan["execution_id"] != EXECUTION_ID
        or manifest["execution_id"] != EXECUTION_ID
        or plan["schema_version"] != "controlled_execution_v2"
        or plan["output_contract"] != OUTPUT_CONTRACT
        or manifest["output_contract"] != OUTPUT_CONTRACT
        or plan["planned_opportunities"] != 270
        or plan["planned_trajectories"] != 54
        or plan["config"]["max_output_tokens"] != 8192
        or plan["budget"]["allowance"] != "3.00"
        or plan["registry_path"] != manifest["canonical_registry_path"]
    ):
        raise ValueError("frozen launch scope changed")
    if live_authorization:
        live.validate_authorization(plan, read(HERE / "authorization.json"))
        live.validate_attestation(plan, read(HERE / "price_attestation.json"))
    return manifest, plan


def execute(*, diagnostic=False):
    manifest, _ = verify(live_authorization=not diagnostic)
    live, audit_module, report_module, durable_json = frozen_modules()
    run = HERE / "diagnostic/run" if diagnostic else Path(manifest["run_output"])
    auxiliary = HERE / "diagnostic" if diagnostic else HERE / "runtime"
    if not diagnostic:
        intent = read(auxiliary / "launch_intent.json")
        if intent["execution_id"] != EXECUTION_ID or intent["run_output"] != str(run):
            raise ValueError("missing matching one-use launch intent")
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

    result = {
        "diagnostic": diagnostic,
        "execution_id": manifest["execution_id"],
        "output_contract": OUTPUT_CONTRACT,
    }
    try:
        result["collection"] = live.collect(
            HERE / "execution",
            run,
            transport=live.diagnostic_transport if diagnostic else None,
            registry=HERE / "diagnostic/registry" if diagnostic else None,
            authorization=None if diagnostic else read(HERE / "authorization.json"),
            price_attestation=None if diagnostic else read(HERE / "price_attestation.json"),
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
        report = report_module.report_run(
            HERE / "execution", run, auxiliary / "report", require_model=not diagnostic
        )
        result["report"] = {
            k: report[k]
            for k in (
                "complete",
                "mode",
                "attempted",
                "received",
                "unsubmitted",
                "model_calls",
                "stop_reason",
                "reliability",
            )
        }
        result["report_verification"] = report_module.verify_report(
            HERE / "execution", run, auxiliary / "report"
        )
    except Exception as exc:
        result["finalization_error_type"] = type(exc).__name__
    code = (
        0
        if result.get("report", {}).get("complete")
        and "collection_error_type" not in result
        and "finalization_error_type" not in result
        else 2
    )
    result.update(ended_at=datetime.now(timezone.utc).isoformat(), intended_exit_code=code)
    durable_json(auxiliary / "completion.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "audit"}), flush=True)
    return code


def launch():
    manifest, plan = verify(live_authorization=True)
    runtime = HERE / "runtime"
    claim = Path(plan["registry_path"]) / (plan["execution_id"] + ".json")
    if runtime.exists() or Path(manifest["run_output"]).exists() or claim.exists():
        raise ValueError("initial launch already claimed; inspect existing run, never relaunch")
    credential = os.environ.get("DEEPSEEK_API_KEY") or getpass.getpass(
        "DeepSeek API key (hidden): "
    )
    if not credential or any(ord(char) < 33 or ord(char) > 126 for char in credential):
        raise ValueError("missing or invalid credential")
    runtime.mkdir(exist_ok=False)
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
    env["PYTHONPATH"] = str(HERE / "execution/dataset/implementation_source/src")
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
    os.environ.pop("DEEPSEEK_API_KEY", None)
    credential = None
    record = {
        "pid": process.pid,
        "command": command,
        "execution_id": manifest["execution_id"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "run_output": manifest["run_output"],
        "model_request_limit": 270,
        "allowance_usd": "3.00",
        "output_contract": OUTPUT_CONTRACT,
    }
    durable_json(runtime / "process.json", record)
    print(json.dumps(record), flush=True)


def status():
    result = {}
    for name in ("launch_intent", "process", "progress", "completion"):
        path = HERE / "runtime" / (name + ".json")
        if path.exists():
            result[name] = read(path)
    if "process" in result:
        path = Path("/proc") / str(result["process"]["pid"]) / "stat"
        result["process_stat_exists"] = path.exists()
        if path.exists():
            result["process_state"] = path.read_text().rsplit(") ", 1)[1].split()[0]
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "diagnostic", "launch", "worker", "status"))
    args = parser.parse_args()
    if args.command == "verify":
        _, plan = verify(live_authorization=True)
        print(
            json.dumps(
                {
                    "valid": True,
                    "execution_id": plan["execution_id"],
                    "output_contract": OUTPUT_CONTRACT,
                    "model_calls": 0,
                }
            )
        )
    elif args.command == "diagnostic":
        return execute(diagnostic=True)
    elif args.command == "worker":
        return execute()
    elif args.command == "status":
        status()
    else:
        launch()
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as exc:
        print(json.dumps({"runner_error_type": type(exc).__name__}), flush=True)
        exit_code = 2
    raise SystemExit(exit_code)
