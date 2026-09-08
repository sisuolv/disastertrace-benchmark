"""Measure all predeclared stress inputs with program carriers, without inference."""

import argparse
from collections import defaultdict
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint, read_jsonl
from disastertrace.constrained_eval import adapter, execution, runtime
from disastertrace.controlled import runtime as program_runtime
from disastertrace.controlled.output_contract import V2, system_message
from disastertrace.controlled.public_oracle import backends
from disastertrace.controlled.schema import METHODS
from disastertrace.local_eval.storage import digest, read, seal, verify_seal, write

HERE = Path(__file__).resolve().parent


def measure(request, tokenizer):
    messages = [
        {"role": "system", "content": system_message(V2)},
        {"role": "user", "content": canonical(request)},
    ]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=True
    )
    ids = tokenizer.encode(prompt, add_special_tokens=False)
    settings = adapter.SETTINGS
    fits = len(ids) + settings["max_tokens"] <= settings["max_model_len"]
    return {
        "prompt_tokens": len(ids),
        "reserved_output_tokens": settings["max_tokens"],
        "context_limit": settings["max_model_len"],
        "remaining_tokens": settings["max_model_len"] - len(ids),
        "fits_full_output_cap": fits,
        "prompt_itself_exceeds_context": len(ids) > settings["max_model_len"],
        "prompt_sha256": fingerprint(prompt),
    }, ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--stress", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan, _, _ = execution.verify(args.execution)
    stress_manifest = verify_seal(args.stress)
    acceptance = read(args.stress / "acceptance.json")
    episodes = read_jsonl(args.stress / "episodes.jsonl")
    tokenizer = runtime.tokenizer_for(args.execution)
    args.output.mkdir(parents=True, exist_ok=False)
    rows, cache, cells = [], {}, defaultdict(list)
    direct_checks = 0
    for method in METHODS:
        for backend in (*backends, "invalid-control"):
            traces = program_runtime.rehearse(episodes, method, backend)
            for trace in traces:
                request = trace["request"]
                request_id = fingerprint(request)
                if request_id not in cache:
                    measurement, ids = measure(request, tokenizer)
                    try:
                        prepared = adapter.prepare(
                            request, {"slot_id": "offline-context-check"}, tokenizer
                        )
                    except ValueError as error:
                        if measurement[
                            "fits_full_output_cap"
                        ] or "context budget exceeded" not in str(error):
                            raise
                    else:
                        if (
                            not measurement["fits_full_output_cap"]
                            or prepared["prompt_token_ids"] != ids
                        ):
                            raise ValueError("context calibration differs from actual adapter")
                    direct_checks += 1
                    cache[request_id] = measurement
                measurement = cache[request_id]
                factor, level = trace["episode_id"].rsplit(":", 1)[-1].rsplit("-", 1)
                row = {
                    "episode_id": trace["episode_id"],
                    "checkpoint_id": trace["checkpoint_id"],
                    "method": method,
                    "program_backend": backend,
                    "factor": factor,
                    "level": int(level),
                    **measurement,
                }
                rows.append(row)
                cells[(factor, int(level), method, backend)].append(row)
            print({"method": method, "backend": backend, "measured_rows": len(rows)}, flush=True)
    summaries = []
    for (factor, level, method, backend), selected in sorted(cells.items()):
        summaries.append(
            {
                "factor": factor,
                "level": level,
                "method": method,
                "program_backend": backend,
                "requests": len(selected),
                "over_full_output_budget": sum(not r["fits_full_output_cap"] for r in selected),
                "prompt_itself_exceeds_context": sum(
                    r["prompt_itself_exceeds_context"] for r in selected
                ),
                "min_prompt_tokens": min(r["prompt_tokens"] for r in selected),
                "max_prompt_tokens": max(r["prompt_tokens"] for r in selected),
            }
        )
    profiles = []
    for cell in acceptance["cells"]:
        selected = [
            r for r in rows if r["factor"] == cell["factor"] and r["level"] == cell["level"]
        ]
        profiles.append(
            {
                "factor": cell["factor"],
                "level": cell["level"],
                "program_carrier_rows": len(selected),
                "all_program_carriers_fit": all(r["fits_full_output_cap"] for r in selected),
                "over_full_output_budget": sum(not r["fits_full_output_cap"] for r in selected),
                "max_prompt_tokens": max(r["prompt_tokens"] for r in selected),
                "zero_effect_episodes": sum(
                    r["added_records"] == 0 and r["added_deliveries"] == 0
                    for r in cell["effective_factor_counts"]
                ),
            }
        )
    result = {
        "profile": "p4_stress_context_calibration_v1",
        "execution_id": plan["execution_id"],
        "stress_package_id": stress_manifest["package_id"],
        "episodes": len(episodes),
        "measured_rows": len(rows),
        "unique_requests_and_adapter_checks": direct_checks,
        "program_carriers": [*backends, "invalid-control"],
        "profiles": profiles,
        "cells": summaries,
        "model_calls": 0,
        "selection_depends_on_model_errors": False,
        "guarantees_arbitrary_llm_carrier_fit": False,
        "interpretation": "Deterministic program-carrier calibration only; "
        "arbitrary valid LLM evidence arrays can be longer. "
        "No truncation or stress inference performed.",
        "script_sha256": digest(__file__),
    }
    write(args.output / "rows.json", rows)
    write(args.output / "report.json", result)
    seal(args.output)
    print({k: v for k, v in result.items() if k != "cells"})


if __name__ == "__main__":
    main()
