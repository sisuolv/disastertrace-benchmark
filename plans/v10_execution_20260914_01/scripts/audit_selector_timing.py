"""Attribute recorded generation time without treating batched fees as device time."""

import argparse
import ast
import datetime as dt
import json
import math
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    batch, out = args.batch.absolute(), args.out.absolute()
    out.mkdir(exist_ok=False)
    complete, plan = read(batch / "COMPLETE.json"), read(batch / "PLAN.json")
    records = []
    for path in batch.glob("*/spool/*.worker.json"):
        worker = read(path)
        tokens = read(path.with_name(path.name.replace(".worker.json", ".tokens.json")))
        records.append(
            {
                **worker,
                "case": path.parent.parent.name,
                "batch_size": tokens["batch_size"],
            }
        )
    records.sort(key=lambda r: r["generated_wall_ns"])
    logs = []
    for line in (batch / "submission_01/worker.log").read_text().splitlines():
        if not line.startswith("{'group':"):
            continue
        item = ast.literal_eval(line)
        if not {"group", "iteration", "benchmark_calls"} <= item.keys():
            raise ValueError("Unexpected generation-batch log")
        logs.append(item)
    batches, offset = [], 0
    for item in logs:
        end = item["benchmark_calls"]
        members = records[offset:end]
        allowed = set(plan["cases"][item["group"] : item["group"] + plan["batch_size"]])
        if (
            not members
            or len({r["case"] for r in members}) != len(members)
            or not {r["case"] for r in members} <= allowed
            or {r["batch_size"] for r in members} != {len(members)}
            or len({r["compute_seconds"] for r in members}) != 1
        ):
            raise ValueError(
                "Cannot uniquely reconstruct the recorded generation batch"
            )
        batches.append(
            {
                **item,
                "responses": len(members),
                "generate_seconds": members[0]["compute_seconds"],
            }
        )
        offset = end
    if offset != len(records) or len(records) != complete["benchmark_calls"]:
        raise ValueError("Generation batches do not cover every captured response")
    warm_ns = read(batch / "WARM_READY.json")["at"]
    if type(warm_ns) is not int:
        raise ValueError("Original WARM_READY uses integer Unix nanoseconds")
    warm = dt.datetime.fromtimestamp(warm_ns / 1e9, tz=dt.timezone.utc)
    finished = dt.datetime.fromisoformat(complete["at"])
    wall = (finished - warm).total_seconds()
    generation = math.fsum(r["generate_seconds"] for r in batches)
    if not 0 <= generation <= wall:
        raise ValueError("Recorded generation interval exceeds the run interval")
    result = {
        "passed": True,
        "benchmark_responses": len(records),
        "generation_batches": len(batches),
        "warm_ready_to_complete_seconds": wall,
        "deduplicated_generate_call_seconds": generation,
        "remaining_uninstrumented_seconds": wall - generation,
        "generate_call_fraction_of_warm_session": generation / wall,
        "per_response_compute_seconds_sum_not_device_time": math.fsum(
            r["compute_seconds"] for r in records
        ),
        "input_tokens": sum(r["input_tokens"] for r in records),
        "output_tokens": sum(r["output_tokens"] for r in records),
        "batch_reconstruction": batches,
        "new_inference": 0,
        "scope": "Recorded vLLM.generate elapsed time versus warm session wall time; no kernel-utilization or CPU-versus-AFS causal attribution",
        "next_performance_work": "Instrument formal stepping, tokenization, hashing, checkpoints and final reports separately before changing concurrency or persistence",
    }
    (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in result.items() if k != "batch_reconstruction"}),
        flush=True,
    )


if __name__ == "__main__":
    main()
