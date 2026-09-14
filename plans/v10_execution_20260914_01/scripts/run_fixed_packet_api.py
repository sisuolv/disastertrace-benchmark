"""Single-attempt, bounded concurrent capture; evaluator labels are never loaded."""

import argparse
import datetime as dt
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from disastertrace.forecast_task.common import strict_json
from disastertrace.monitoring_v1.api_capture_v2 import capture
from disastertrace.monitoring_v1.api_ledger import ApiLedger
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch.absolute()
    plan = read(batch / "PLAN.json")
    publish(
        batch / "api/RUN_CLAIM.json",
        {
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "plan_sha256": digest(batch / "PLAN.json"),
            "network_retries": 0,
        },
    )
    for rel, sha in plan["files"].items():
        if digest(batch / rel) != sha:
            raise ValueError("Frozen packet/source/ledger identity mismatch")
    ledger = ApiLedger(batch / "api/ledger")
    if ledger.contract_sha256 != read(batch / "PREFLIGHT.json")["ledger_sha256"]:
        raise ValueError("API qualification no longer matches ledger")
    observations = batch / "api/observations"
    observations.mkdir(exist_ok=False)
    compatible = {}
    for model in plan["api_models"]:
        try:
            raw, meta = capture(
                ledger,
                model + "/compatibility",
                read(batch / "api/COMPATIBILITY_REQUEST.json"),
            )
            compatible[model] = bool(
                meta["ended_with_eos"] and strict_json(raw) == {"ready": True}
            )
        except Exception:  # noqa: BLE001 - Capture retains the original transport failure and reservation.
            compatible[model] = False
    publish(batch / "api/COMPATIBILITY.json", compatible)

    def invoke(model, task):
        key = model + "/" + task["call_id"]
        row = {
            "model": model,
            "call_id": task["call_id"],
            "request_key": key,
            "state": "NOT_ATTEMPTED",
            "original_network_attempts_ceiling": 1,
        }
        if not compatible[model]:
            row["reason"] = "model_compatibility_failed"
        elif (
            time.time_ns() >= ledger.contract["deadline_wall_ns"]
            or (ledger.path / "STOP.json").exists()
        ):
            row["reason"] = "registered_deadline_or_stop"
        else:
            policy = read(batch / "policy" / (task["call_id"] + ".json"))
            try:
                raw, meta = capture(ledger, key, policy["messages"])
                row.update(state="RECEIVED", raw=raw, details=meta)
            except Exception as exc:  # noqa: BLE001 - Record failure; never selectively retry a model answer.
                row.update(state="FAILED", error_type=type(exc).__name__)
        publish(observations / (model + "__" + task["call_id"] + ".json"), row)
        return row["state"]

    counts = {}
    # Interleave models and formats so a deadline does not systematically censor one arm.
    with ThreadPoolExecutor(max_workers=plan["api_workers"]) as pool:
        futures = [
            pool.submit(invoke, model, task)
            for task in plan["tasks"]
            for model in plan["api_models"]
        ]
        for number, future in enumerate(as_completed(futures), 1):
            state = future.result()
            counts[state] = counts.get(state, 0) + 1
            if number % 64 == 0:
                print(json.dumps({"completed": number, "states": counts}), flush=True)
    ledger.stop("registered packet batch drained")
    publish(
        batch / "api/COMPLETE.json",
        {
            "states": counts,
            "ledger": ledger.reduce(),
            "benchmark_tasks": len(futures),
            "compatibility": compatible,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "retried": 0,
        },
    )
    print(json.dumps(read(batch / "api/COMPLETE.json")), flush=True)


if __name__ == "__main__":
    main()
