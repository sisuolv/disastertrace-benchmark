"""Freeze charged LLM selection against strong shared selectors, with explicit state."""

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


def slice_session(data, cutoffs):
    result = dict(data)
    result["opportunities"] = [
        o for o in data["opportunities"] if o["cutoff"] in cutoffs
    ]
    ids = {o["opportunity_id"] for o in result["opportunities"]}
    targets = {o["target_id"] for o in result["opportunities"]}
    result["targets"] = [t for t in data["targets"] if t["target_id"] in targets]
    result["baseline_candidates"] = [
        b
        for b in data["baseline_candidates"]
        if b["target_id"] in targets and b["available_at"] <= max(cutoffs)
    ]
    result["baseline_withdrawals"] = [
        b
        for b in data.get("baseline_withdrawals", [])
        if b["target_id"] in targets and b["available_at"] <= max(cutoffs)
    ]
    result["e_f_pairs"] = [p for p in data["e_f_pairs"] if p["opportunity_id"] in ids]
    qids = {q for p in result["e_f_pairs"] for q in p["query_ids"]}
    result["query_catalog"] = [
        q for q in data["query_catalog"] if q["query_id"] in qids
    ]
    result["query_results"] = [
        q for q in data["query_results"] if q["query_id"] in qids
    ]
    return result


def main(args):
    from transformers import AutoTokenizer

    batch = args.output.resolve()
    batch.mkdir(exist_ok=False)
    package = batch / "source/disastertrace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Frozen monitoring runtime."""\n')
    shutil.copytree(
        REPO / "disastertrace-starter/src/disastertrace/monitoring_v1",
        package / "monitoring_v1",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copyfile(BASE / "gpu_worker.py", batch / "source/gpu_worker.py")
    shutil.copyfile(BASE / "freeze_active.py", batch / "source/freeze_active.py")
    shutil.copyfile(args.bank, batch / "BANK.json")
    bank = json.loads(args.bank.read_text())
    old = json.loads(
        (
            REPO / "plans/v5_0910_feasibility_12h_20260910/gpu/wave1/PLAN.json"
        ).read_text()
    )
    spec = old["models"]["qwen3_8b"]
    tokenizer = AutoTokenizer.from_pretrained(spec["directory"], local_files_only=True)
    all_data = load_session(
        args.dataset, stations=args.stations, threshold=args.threshold
    )
    all_cutoffs = sorted({o["cutoff"] for o in all_data["opportunities"]})
    chosen = all_cutoffs[args.start_hour : args.start_hour + args.hours]
    if len(chosen) != args.hours:
        raise ValueError("Requested calendar hours not present")
    workers = {str(i): [] for i in range(4)}
    dry_runs = {}
    total_caps = 0
    for block_index, position in enumerate(range(0, len(chosen), args.block_hours)):
        block_cutoffs = chosen[position : position + args.block_hours]
        data = slice_session(all_data, block_cutoffs)
        filename = f"environment-{block_index:02d}.json"
        save(batch / filename, data)
        n = len(block_cutoffs)
        model_cap = n * 2
        base_config = {
            "seed": 20260912,
            "request_budget": n * 2,
            "forecast_call_cap": model_cap,
            "model_call_budget": model_cap,
            "per_tick_forecast_cap": 2,
            "input_token_cap": args.input_token_cap,
            "output_token_cap": 384,
            "call_compute_cap_ms": 120000,
            "wakeup_seconds": 600,
            "token_cap": model_cap * (args.input_token_cap + 384),
            "compute_ms_cap": model_cap * 120000 + n * 200,
            "isolation_mode": "actual_cost_clock",
            "allocation_mode": "global_budget",
            "authorization_mode": "session_shared",
            "protocol": args.protocol,
            "prompt_contract": "explicit_target_state_actions.v2",
            "selector_contract": "shared_target_state_resources.v2",
            "acquisition_pacing": "public_calendar_fraction",
        }
        for i, selector in enumerate(("round_robin", "risk", "batch_complete", "llm")):
            arm = dict(base_config, selector_kind=selector)
            run_id = f"block{block_index:02d}-" + selector
            samples = []

            def backend(system, request, call_id, arm=arm, samples=samples):
                messages = [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": json.dumps(request, separators=(",", ":")),
                    },
                ]
                rendered = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
                if len(ids) > arm["input_token_cap"]:
                    raise ValueError(
                        "Selector/forecast input exceeds its common reservation"
                    )
                samples.append(
                    {
                        "call_id": call_id,
                        "input_tokens": len(ids),
                        "rendered_sha256": hashlib.sha256(
                            rendered.encode()
                        ).hexdigest(),
                    }
                )
                if call_id.startswith("select-"):
                    answer = {
                        "query_order": list(request["queries"]),
                        "forecast_handles": [next(iter(request["targets"]))],
                    }
                else:
                    answer = {
                        "probability": request["common_baseline"]["probability"],
                        "e_status": "undetermined",
                        "decision": "follow",
                        "citations": [],
                    }
                return json.dumps(answer), {
                    "input_tokens": len(ids),
                    "output_tokens": 80,
                    "seconds": 0.001,
                    "ended_with_eos": True,
                }

            trace = run_session(data, bank, arm, backend=backend)
            if (
                len(trace["snapshots"]) != len(data["opportunities"])
                or len(samples) > model_cap
            ):
                raise ValueError("Dry-run opportunity/model-call cap violated")
            if trace["actual_model_calls"] != len(samples):
                raise ValueError("Selector calls were not charged as model calls")
            workers[str(i)].append(
                {"run_id": run_id, "data_file": filename, "config": arm}
            )
            dry_runs[run_id] = {
                "calls": samples,
                "opportunities": len(trace["snapshots"]),
                "resource_spent": trace["resource_spent"],
                "actual_model_calls": trace["actual_model_calls"],
            }
        total_caps += model_cap * 4
    save(batch / "TOKENIZER_PREFLIGHT.json", dry_runs)
    plan = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "cci_hostname": socket.gethostname(),
        "models": {"qwen3_8b": spec},
        "worker_models": {str(i): "qwen3_8b" for i in range(4)},
        "seed": 20260912,
        "do_sample": False,
        "thinking": False,
        "max_new_tokens": 384,
        "context_limit": max(12288, args.input_token_cap + 384),
        "max_generation_seconds": 90,
        "max_worker_seconds": args.worker_seconds,
        "max_concurrent_gpus": 4,
        "max_calls_per_worker": total_caps // 4,
        "maximum_model_calls": total_caps,
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
            )
        },
        "outcomes_in_worker_package": False,
        "automatic_retries": 0,
        "interpretation": "Exposed calendar development; same shared source/model-call/token limits; LLM selector calls compete with forecasting; explicit per-target state and action definitions v2",
        "calendar": {
            "start_hour": args.start_hour,
            "hours": args.hours,
            "block_hours": args.block_hours,
            "threshold_m": args.threshold,
            "stations": args.stations,
            "independence": "resource sessions, not claims of independent meteorological processes",
        },
    }
    save(batch / "PLAN.json", plan)
    print(
        json.dumps(
            {
                "batch": str(batch),
                "maximum_calls": total_caps,
                "blocks": len(workers["0"]),
                "max_input_tokens": max(
                    c["input_tokens"] for r in dry_runs.values() for c in r["calls"]
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
    parser.add_argument("--stations", nargs="+", default=["KSFO", "KOAK", "KSJC"])
    parser.add_argument("--hours", type=int, default=8)
    parser.add_argument("--start-hour", type=int, default=0)
    parser.add_argument("--block-hours", type=int, default=72)
    parser.add_argument("--threshold", type=int, default=1000)
    parser.add_argument("--input-token-cap", type=int, default=11264)
    parser.add_argument(
        "--protocol",
        choices=["base_bound_override", "persistent_override"],
        default="base_bound_override",
    )
    parser.add_argument("--worker-seconds", type=int, default=1800)
    main(parser.parse_args())
