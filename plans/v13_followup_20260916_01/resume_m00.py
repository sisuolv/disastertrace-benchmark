"""One-owner handoff before any case dispatch; original frozen M00 stays intact."""
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import m00
from disastertrace.monitoring_v1.spool_backend import read, publish, digest


def main():
    terminal = read(m00.RUN / "runtime/c00_m00/STATUS_AFTER_STOP.json")
    stopped = terminal.get("state") == "STOPPED" or (
        terminal.get("state") == "SUSPENDED" and terminal.get("suspend_time"))
    if not stopped or terminal.get("name") != "pt-ol1i47dv":
        raise ValueError("Prior authority is not terminal")
    reg = read(m00.OUT / "REGISTRATION.json")
    m00.verify(reg["source_files"])
    m00.verify(read(m00.OUT / "FREEZE.json")["files"])
    if any((m00.OUT / name / "CLAIM.json").exists() for name in reg["cases"]):
        raise ValueError("Pre-dispatch handoff cannot duplicate a case claim")
    if list(m00.OUT.glob("*/spool/*.request.json")):
        raise ValueError("Original authority already dispatched")
    publish(m00.OUT / "HANDOFF_CLAIM.json", {"at": m00.now(), "previous_job": "pt-ol1i47dv",
        "original_claim_sha256": digest(m00.OUT / "CLAIM.json"),
        "terminal_receipt_sha256": digest(m00.RUN / "runtime/c00_m00/STATUS_AFTER_STOP.json"),
        "runner_sha256": digest(Path(__file__)), "frozen_inputs_unchanged": True,
        "original_requests_before_handoff": 0, "max_new_requests": 12})
    deadline = read(m00.OUT / "MODEL_CONTRACT.json")["api_transport_v2"]["deadline_wall_ns"]
    while not (m00.B00 / "QUALIFICATION.json").exists() and time.time_ns() < deadline:
        time.sleep(30)
    if not (m00.B00 / "QUALIFICATION.json").exists() or not read(m00.B00 / "QUALIFICATION.json")["passed"]:
        publish(m00.OUT / "RESULT.json", {"passed":False,"status":"program_qualification_blocked","http_attempts":0})
        return 1
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(m00.one, name):name for name in reg["cases"]}
        for future in as_completed(tasks):
            try: results.append(future.result())
            except Exception as exc:
                results.append({"case":tasks[future],"passed":False,"error":type(exc).__name__})
    passed = len(results)==12 and all(r["passed"] for r in results)
    publish(m00.OUT / "RESULT.json", {"passed":passed,"results":results,"finished_at":m00.now(),
        "registered_requests":12,"http_attempts":sum(r.get("http_attempts",0) for r in results),
        "valid_outputs":sum(r.get("contract_valid",False) for r in results),
        "provider_tokens":sum(r.get("provider_tokens",0) for r in results),
        "claim":"transport/schema/actual-consumer smoke only, no forecast skill claim",
        "formal_288_batch_launched":False,"confirmation_opened":False,
        "handoff_before_any_original_dispatch":True})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
