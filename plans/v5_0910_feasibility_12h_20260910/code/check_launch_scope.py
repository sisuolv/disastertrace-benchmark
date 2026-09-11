"""Count completed calls and reservation proxies against the amended12h scope."""

import argparse
from datetime import datetime
import json
from pathlib import Path

from common import ROOT, dump
from model_adapter import sha_file


def main(batch):
    prior_calls, prior_seconds = 0, 0
    closed = []
    for prior in sorted((ROOT / "gpu").glob("wave*")):
        if prior == batch or not (prior / "submissions").exists():
            continue
        terminal = prior / "ACP_TERMINAL.json"
        if not terminal.exists():
            raise ValueError("prior submitted wave has not been reconciled: " + prior.name)
        jobs = json.loads(terminal.read_text())["jobs"]
        if any(j["state"] not in {"SUCCEEDED", "FAILED", "DELETED"} for j in jobs):
            raise ValueError("prior wave still owns resource slots")
        for job in jobs:
            end = job.get("complete_time")
            if not end:
                raise ValueError("missing terminal time")
            prior_seconds += (datetime.fromisoformat(end.replace("Z", "+00:00")) -
                              datetime.fromisoformat(job["create_time"].replace("Z", "+00:00"))).total_seconds()
        count = len(list((prior / "runs").glob("*/trajectories/*/turn-*/intent.json")))
        count += len(list((prior / "runs").glob("*/tasks/*/step-*/intent.json")))
        prior_calls += count
        closed.append({"wave": prior.name, "intents": count})
    plan = json.loads((batch / "PLAN.json").read_text())
    amendment = json.loads((ROOT / "SCOPE_AMENDMENT_01.json").read_text())
    scope = json.loads((ROOT / "SCOPE.json").read_text())
    cap = amendment["changes"]["max_new_model_requests"]
    new_seconds = len(plan["workers"]) * plan["max_worker_seconds"]
    if prior_calls + plan["max_requests"] > cap or prior_seconds + new_seconds > scope["max_gpu_hours"] * 3600:
        raise ValueError("cumulative resource bound exceeded")
    for rel, expected in plan["bound_files"].items():
        if sha_file(batch / rel) != expected:
            raise ValueError("frozen file changed: " + rel)
    for rel, expected in plan["runtime_files"].items():
        if sha_file(rel) != expected:
            raise ValueError("runtime changed: " + rel)
    result = {"status": "passed", "closed_waves": closed, "prior_intents": prior_calls,
        "new_max_requests": plan["max_requests"], "max_cumulative_requests": prior_calls + plan["max_requests"],
        "request_cap": cap, "prior_create_to_terminal_gpu_seconds": prior_seconds,
        "new_max_worker_gpu_seconds": new_seconds, "gpu_hour_cap": scope["max_gpu_hours"],
        "note": "Create-to-terminal interval is a conservative reservation proxy, not a billing or utilization measurement."}
    dump(batch / "LAUNCH_SCOPE_CHECK.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    main(parser.parse_args().batch.resolve())
