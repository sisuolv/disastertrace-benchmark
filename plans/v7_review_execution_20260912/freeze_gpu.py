"""Freeze public/provider inputs and real tokenizer dry-runs before GPU use."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / "disastertrace-starter/src"))

from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.policies import run_session
from gpu_worker import digest, save


def main(args):
    from transformers import AutoTokenizer

    batch = args.output.resolve()
    batch.mkdir(exist_ok=False)
    source = batch / "source"
    package = source / "disastertrace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Frozen monitoring runtime."""\n')
    shutil.copytree(
        REPO / "disastertrace-starter/src/disastertrace/monitoring_v1",
        package / "monitoring_v1",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copyfile(BASE / "gpu_worker.py", source / "gpu_worker.py")
    shutil.copyfile(BASE / "freeze_gpu.py", source / "freeze_gpu.py")
    shutil.copyfile(args.bank, batch / "BANK.json")
    bank = json.loads(args.bank.read_text())
    old = json.loads(
        (
            REPO / "plans/v5_0910_feasibility_12h_20260910/gpu/wave1/PLAN.json"
        ).read_text()
    )
    model_spec = old["models"]["qwen3_8b"]
    tokenizer = AutoTokenizer.from_pretrained(
        model_spec["directory"], local_files_only=True
    )
    for item in model_spec["files"]:
        if ("tokenizer" in item["path"] or "chat_template" in item["path"]) and (
            digest(Path(model_spec["directory"]) / item["path"]) != item["sha256"]
        ):
            raise ValueError("Tokenizer changed")
    data = load_session(
        args.dataset,
        stations=["KSFO", "KOAK", "KSJC"][: args.sites],
        hours=args.hours,
        threshold=args.threshold,
    )
    save(batch / "POLICY_ENVIRONMENT.json", data)
    calls_per_run = min(args.hours * 2, args.calls)
    config = {
        "seed": 20260912,
        "request_budget": args.hours * 2,
        "forecast_call_cap": calls_per_run,
        "per_tick_forecast_cap": 2,
        "input_token_cap": 8192,
        "output_token_cap": 384,
        "call_compute_cap_ms": 120000,
        "wakeup_seconds": 600,
        "token_cap": calls_per_run * (8192 + 384),
        "compute_ms_cap": calls_per_run * 120000 + args.hours * 2 * 100,
        "selector_kind": "round_robin",
        "isolation_mode": "public_schedule",
        "public_call_slot_ms": 120000,
        "protocol": args.protocol,
        "allocation_dimensions": ["requests", "bytes"],
    }
    workers, dry_runs = {}, {}
    for i, (allocation, authorization) in enumerate(
        [
            ("fixed_quota", "target_private"),
            ("fixed_quota", "session_shared"),
            ("global_budget", "target_private"),
            ("global_budget", "session_shared"),
        ]
    ):
        arm = dict(config, allocation_mode=allocation, authorization_mode=authorization)
        workers[str(i)] = [
            {
                "run_id": "x01-" + str(i),
                "data_file": "POLICY_ENVIRONMENT.json",
                "config": arm,
            }
        ]
        samples = []

        def backend(system, request, call_id, arm=arm, samples=samples):
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(request, separators=(",", ":"))},
            ]
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
            if len(ids) > arm["input_token_cap"]:
                raise ValueError("Dry-run input exceeds reservation")
            samples.append(
                {
                    "call_id": call_id,
                    "input_tokens": len(ids),
                    "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                }
            )
            return json.dumps(
                {
                    "probability": request["common_baseline"]["probability"],
                    "e_status": "undetermined",
                    "decision": "follow",
                    "citations": [],
                }
            ), {
                "input_tokens": len(ids),
                "output_tokens": 64,
                "seconds": 0.001,
                "ended_with_eos": True,
            }

        trace = run_session(data, bank, arm, backend=backend)
        if (
            len(trace["snapshots"]) != len(data["opportunities"])
            or len(samples) != calls_per_run
        ):
            raise ValueError("Preflight opportunity/call count differs")
        dry_runs[str(i)] = {
            "calls": samples,
            "opportunities": len(trace["snapshots"]),
            "resource_spent": trace["resource_spent"],
            "resource_reserved": trace["resource_reserved"],
        }
    save(batch / "TOKENIZER_PREFLIGHT.json", dry_runs)
    plan = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "cci_hostname": socket.gethostname(),
        "models": {"qwen3_8b": model_spec},
        "worker_models": {str(i): "qwen3_8b" for i in range(4)},
        "seed": 20260912,
        "do_sample": False,
        "thinking": False,
        "dtype": "bfloat16",
        "attention": "sdpa",
        "max_new_tokens": 384,
        "context_limit": 12288,
        "max_generation_seconds": 90,
        "max_worker_seconds": args.worker_seconds,
        "max_concurrent_gpus": 4,
        "max_calls_per_worker": calls_per_run,
        "maximum_model_calls": calls_per_run * 4,
        "workers": workers,
        "runtime_versions": {
            name: version(name)
            for name in (
                "torch",
                "transformers",
                "accelerate",
                "tokenizers",
                "safetensors",
            )
        },
        "files": {
            str(p.relative_to(batch)): digest(p)
            for p in batch.rglob("*")
            if p.is_file()
        },
        "evaluation_bindings": {
            str(p.resolve()): digest(p)
            for p in (
                args.dataset / "private/OUTCOMES.json",
                args.dataset / "REGIONAL_JOIN_AUDIT.json",
                args.bank,
                BASE / "programs_short_01/SUMMARY.json",
                BASE / "PLAN_AMENDMENT_CN.md",
            )
        },
        "outcomes_in_worker_package": False,
        "automatic_retries": 0,
        "interpretation": "Exposed development; R-track mapped TAF; public padded X01 timing control; no online or independent-event claim",
    }
    save(batch / "PLAN.json", plan)
    print(
        json.dumps(
            {
                "batch": str(batch),
                "plan_sha256": digest(batch / "PLAN.json"),
                "maximum_calls": calls_per_run * 4,
                "workers": 4,
                "max_input_tokens": max(
                    s["input_tokens"] for r in dry_runs.values() for s in r["calls"]
                ),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=BASE / "regional_02")
    parser.add_argument(
        "--bank", type=Path, default=BASE / "calibration_bank_01/BANK.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--sites", type=int, default=2, choices=[2, 3])
    parser.add_argument("--threshold", type=int, default=1000, choices=[1000, 5000])
    parser.add_argument("--calls", type=int, default=4)
    parser.add_argument("--worker-seconds", type=int, default=1200)
    parser.add_argument(
        "--protocol",
        choices=["base_bound_override", "persistent_override"],
        default="base_bound_override",
    )
    main(parser.parse_args())
