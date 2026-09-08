"""Rebuild attribution and source consensus in a disconnected, relocated CPU copy."""

import argparse
import importlib.util
import os
import runpy
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
WEIGHTS = "/mnt/afs/260010168/models/Qwen3-8B-modelscope-pinned-v1"


def child(args):
    copied = args.copy.resolve()
    blocked = (args.original_project.resolve(), args.model_directory.resolve())
    forbidden = {"original_reads": 0, "socket_connections": 0}

    def guard(event, fields):
        if event == "open" and isinstance(fields[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(fields[0])).resolve()
            if not path.is_relative_to(copied) and any(path.is_relative_to(p) for p in blocked):
                forbidden["original_reads"] += 1
                raise RuntimeError("supplementary CPU review attempted original-file access")
        if event == "socket.connect":
            forbidden["socket_connections"] += 1
            raise RuntimeError("supplementary CPU review attempted network access")

    sys.addaudithook(guard)
    if any(importlib.util.find_spec(name) is not None for name in ("torch", "vllm")):
        raise RuntimeError("the review environment must contain neither Torch nor vLLM")

    # Exercise the guards before reconstructing, without reading a byte or opening a connection.
    for root in blocked:
        try:
            (root / "intentionally_forbidden_probe").read_bytes()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("original-path guard did not fire")
    with socket.socket() as probe:
        try:
            probe.connect(("127.0.0.1", 9))
        except RuntimeError:
            pass
        else:
            raise RuntimeError("network guard did not fire")
    if forbidden != {"original_reads": 2, "socket_connections": 1}:
        raise RuntimeError("guard self-check counters differ")
    forbidden.update(original_reads=0, socket_connections=0)

    from disastertrace.local_eval.storage import inventory, read, verify_seal, write

    if args.mode == "attribution":
        from disastertrace.repeat_live import package

        loaded = Path(package.__file__).resolve()
        if not loaded.is_relative_to(copied):
            raise RuntimeError("attribution imported original source")
        runpy.run_path(str(HERE / "analyze_model.py"), run_name="__main__")
        verify_seal(HERE / "analysis")
        if inventory(HERE / "analysis") != inventory(HERE / "expected_analysis"):
            raise ValueError("relocated attribution differs from the audited original")
        rebuilt = read(HERE / "analysis/summary.json")
        details = {
            "analysis_id": rebuilt["analysis_id"],
            "audit_id": rebuilt["audit_id"],
            "field_opportunities": rebuilt["received_field_opportunities"],
            "exact_analysis_inventory_match": True,
        }
    else:
        from disastertrace.forecast_source import pipeline

        loaded = Path(pipeline.__file__).resolve()
        if not loaded.is_relative_to(copied):
            raise RuntimeError("source review imported original source")
        bundle = copied / "artifacts/nhc_forecast_source_v1"
        pipeline.review(bundle, bundle / "review_v1", verify=True)
        rebuilt = read(bundle / "review_v1/report.json")
        details = {
            "scope_id": rebuilt["scope_id"],
            "admitted_bodies": rebuilt["admitted_bodies"],
            "quarantined_bodies": rebuilt["quarantined_bodies"],
            "all_saved_source_review_objects_match": True,
        }
    if any(forbidden.values()):
        raise RuntimeError("reconstruction attempted a forbidden operation")
    receipt = {
        "status": "passed",
        "mode": args.mode,
        "loaded_source": str(loaded),
        "python": sys.version,
        "torch_and_vllm_absent": True,
        "original_project_and_weights_blocked": True,
        "network_blocked": True,
        "guard_self_checks_passed": True,
        "forbidden_operations_during_reconstruction": forbidden,
        "additional_model_calls": 0,
        **details,
    }
    write(copied / (args.mode + "_receipt.json"), receipt)
    print(receipt, flush=True)


def parent():
    from disastertrace.local_eval.storage import digest, now, read, write

    finalization = read(HERE / "finalization_003/result.json")
    if finalization["status"] != "passed":
        raise ValueError("the primary CPU continuation must pass first")
    record = HERE / "supplementary_relocation_001"
    record.mkdir(exist_ok=False)
    copied = PROJECT / "work/p6-supplement-portable-review-v1"
    copied.mkdir(parents=True, exist_ok=False)
    write(
        record / "claim.json",
        {"at": now(), "script_sha256": digest(__file__), "copy": str(copied)},
    )
    sources = [
        "artifacts/p6_live_v1/execution_live_02",
        "artifacts/p6_live_v1/reports/model_review_v2",
        "artifacts/p6_live_v1/token_text_review_v2/review_source",
        "work/p6-live-v1/model",
        "artifacts/nhc_forecast_source_v1",
    ]
    for name in sources:
        shutil.copytree(PROJECT / name, copied / name)
    copied_live = copied / "artifacts/p6_live_v1"
    shutil.copytree(HERE / "analysis", copied_live / "expected_analysis")
    for name in ("analyze_model.py", "portable_supplement.py"):
        shutil.copyfile(HERE / name, copied_live / name)
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(part in k.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        CUDA_VISIBLE_DEVICES="",
        TOKENIZERS_PARALLELISM="false",
    )
    steps = []
    for mode, source in (
        ("attribution", copied_live / "token_text_review_v2/review_source/src"),
        ("source", copied / "artifacts/nhc_forecast_source_v1/source_execution_v2/src"),
    ):
        argv = [
            CPU,
            str(copied_live / "portable_supplement.py"),
            "--mode",
            mode,
            "--copy",
            str(copied),
            "--original-project",
            str(PROJECT),
            "--model-directory",
            WEIGHTS,
        ]
        write(record / (mode + "_intent.json"), {"at": now(), "argv": argv})
        start = time.monotonic()
        with (record / (mode + ".log")).open("x") as log:
            completed = subprocess.run(
                argv,
                cwd=copied,
                env={**env, "PYTHONPATH": str(source)},
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=1800,
                check=False,
            )
        result = {
            "mode": mode,
            "exit_code": completed.returncode,
            "wall_seconds": time.monotonic() - start,
            "finished_at": now(),
            "log_sha256": digest(record / (mode + ".log")),
        }
        write(record / (mode + "_result.json"), result)
        steps.append(result)
        if completed.returncode:
            raise RuntimeError("supplementary relocation failed: " + mode)
        shutil.copyfile(copied / (mode + "_receipt.json"), record / (mode + "_receipt.json"))
    write(record / "result.json", {"status": "passed", "steps": steps, "model_calls": 0})
    print({"status": "passed", "steps": steps, "model_calls": 0}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("parent", "attribution", "source"), default="parent")
    parser.add_argument("--copy", type=Path)
    parser.add_argument("--original-project", type=Path)
    parser.add_argument("--model-directory", type=Path)
    args = parser.parse_args()
    if args.mode == "parent":
        parent()
    else:
        if not all((args.copy, args.original_project, args.model_directory)):
            parser.error("child modes require all three path arguments")
        child(args)


if __name__ == "__main__":
    main()
