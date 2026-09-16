"""Actual tokenizer reservation sweep over ten declared program carrier controls."""

from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.controlled import public_oracle
from disastertrace.controlled import runtime as program_runtime
from disastertrace.controlled.schema import METHODS
from disastertrace.local_eval.storage import seal, write

from . import package, protocol


def sweep(execution, output):
    plan, datasets, slots = package.verify(execution)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    tokenizer = package.tokenizer(execution, plan)
    slot_index = {
        (s["condition"], s["method"], s["episode_id"], s["checkpoint_id"]): s
        for s in slots
        if s["repeat"] == 0
    }
    rows, cache = [], {}
    for condition, episodes in datasets.items():
        for method in METHODS:
            for backend in (*public_oracle.backends, "invalid-control"):
                for trace in program_runtime.rehearse(episodes, method, backend):
                    request = trace["request"]
                    key = fingerprint(request)
                    if key not in cache:
                        slot = slot_index[
                            condition, method, trace["episode_id"], trace["checkpoint_id"]
                        ]
                        prepared = protocol.prepare_request(request, slot, tokenizer)
                        cache[key] = len(prepared["prompt_token_ids"])
                    rows.append(
                        {
                            "condition": condition,
                            "method": method,
                            "program_backend": backend,
                            "episode_id": trace["episode_id"],
                            "checkpoint_id": trace["checkpoint_id"],
                            "request_sha256": key,
                            "prompt_tokens": cache[key],
                            "full_output_reserved": 8192,
                            "context_limit": 16384,
                            "fits": cache[key] + 8192 <= 16384,
                        }
                    )
    if not all(r["fits"] for r in rows):
        raise ValueError("program carrier exceeds full output reservation")
    result = {
        "status": "passed",
        "execution_id": plan["execution_id"],
        "program_requests": len(rows),
        "unique_prompt_preparations": len(cache),
        "maximum_prompt_tokens": max(cache.values()),
        "full_output_reserved": 8192,
        "context_limit": 16384,
        "program_carriers": [*public_oracle.backends, "invalid-control"],
        "repeat_policy": "identical program carrier inputs across repeats; sampling seeds checked separately",
        "guarantees_arbitrary_model_carrier_fit": False,
        "additional_model_calls": 0,
    }
    write(output / "rows.json", rows)
    write(output / "report.json", result)
    seal(output)
    return result
