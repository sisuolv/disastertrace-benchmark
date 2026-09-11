"""Run whole state traces or fixed-input controls once on one pinned H100."""

import argparse
import json
import os
from pathlib import Path
import socket
import time
import traceback

from diagnostic_backend import Backend, now
from model_adapter import parse_action, save, sha_file
from state_inputs import parse_state, state_request


def main(batch, expected_sha, worker):
    output = batch / "runs" / worker
    output.mkdir(parents=True, exist_ok=False)
    save(output / "CLAIM.json", {"at": now(), "pid": os.getpid(), "hostname": socket.gethostname()})
    started = time.monotonic()
    try:
        if sha_file(batch / "PLAN.json") != expected_sha:
            raise ValueError("submitted diagnostic plan changed")
        plan = json.loads((batch / "PLAN.json").read_text())
        backend = Backend(batch, plan, worker, output)
        public = json.loads((batch / "PUBLIC.json").read_text())
        checked = set()
        for tid in plan["workers"][worker]["tasks"]:
            task = plan["tasks"][tid]
            if task["kind"] == "state":
                state = state_request(public["traces"][task["trace"]], 0, task["carrier"], None)
            else:
                state = public["static"][task["public_key"]]
            key = (task["kind"], len(state["assets"]))
            if key not in checked:
                slot = output / "preflight" / tid
                slot.mkdir(parents=True)
                backend.preflight(state, slot)
                checked.add(key)
        save(output / "PREFLIGHT.json", {"at": now(), "status": "passed", "generations": 0, "profiles": sorted(checked)})
        for tid in plan["workers"][worker]["tasks"]:
            task = plan["tasks"][tid]
            root = output / "tasks" / tid
            root.mkdir(parents=True, exist_ok=False)
            previous, results = None, []
            steps = 7 if task["kind"] == "state" else 1
            for step in range(steps):
                slot = root / ("step-%02d" % step)
                slot.mkdir(exist_ok=False)
                if time.monotonic() - started >= plan["max_worker_seconds"] - 180:
                    results.append({"step": step, "status": "deadline_not_called", "answer": None})
                    continue
                state = (state_request(public["traces"][task["trace"]], step, task["carrier"], previous)
                         if task["kind"] == "state" else public["static"][task["public_key"]])
                try:
                    raw, ended = backend.call(state, slot)
                    if task["kind"] == "state":
                        answer = parse_state(raw)
                    else:
                        action, kind = parse_action(raw)
                        answer = action if kind == "final" else None
                    status = "final" if ended and answer is not None else "invalid_schema" if ended else "generation_incomplete"
                    if status != "final":
                        answer = None
                    previous = answer
                    results.append({"step": step, "status": status, "answer": answer})
                except Exception as error:
                    save(slot / "ERROR.json", {"at": now(), "type": type(error).__name__, "message": str(error)[:500],
                         "traceback": traceback.format_exc()})
                    results.append({"step": step, "status": "runtime_error", "answer": None})
                    previous = None
            save(root / "FINAL.json", {"task_id": tid, "results": results})
            print(json.dumps({"task": tid, "steps": len(results), "requests": backend.requests}), flush=True)
        save(output / "DONE.json", {"at": now(), "status": "completed", "requests": backend.requests,
             "tasks": len(plan["workers"][worker]["tasks"]), "elapsed_seconds": time.monotonic() - started,
             "peak_allocated_bytes": backend.torch.cuda.max_memory_allocated()})
    except BaseException as error:
        save(output / "FAILED.json", {"at": now(), "type": type(error).__name__, "message": str(error)[:500],
             "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--plan-sha", required=True)
    parser.add_argument("--worker", required=True)
    args = parser.parse_args()
    main(args.batch.resolve(), args.plan_sha, args.worker)
