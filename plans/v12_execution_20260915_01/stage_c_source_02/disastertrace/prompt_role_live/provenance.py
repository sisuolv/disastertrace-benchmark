"""Bind model journals to actual one-use ACP submissions and terminal platform records."""

from pathlib import Path

from disastertrace.forecast_task.common import fingerprint, read

from . import acp

TERMINAL = {"SUCCEEDED", "FAILED", "DELETED", "SUSPENDED"}


def job_record(details, request):
    if (
        details["display_name"] != request["display_name"]
        or details["resource_pool"]["name"] != acp.CLUSTER
        or details["fault_tolerance"]["backoff_limit"] != 0
        or details.get("lme", {}).get("current_retries", 0) != 0
        or len(details["roles"]) != 1
    ):
        raise ValueError("actual ACP job identity/cluster/retries differ")
    role = details["roles"][0]
    if (
        role["startup_script"] != request["command"]
        or role["image_path"] != acp.IMAGE
        or role["total_replicas"] != 1
        or len(role["resource_spec"]) != 1
    ):
        raise ValueError("actual ACP command/image/replicas differ")
    spec = role["resource_spec"][0]
    if (
        spec["name"] != acp.SPEC
        or spec["replicas"] != 1
        or spec["limits"]["nvidia.com/gpu"] != "1"
        or spec["requests"]["nvidia.com/gpu"] != "1"
    ):
        raise ValueError("actual ACP allocation differs from one full H100")
    if not any(
        m["mount_path"] == "/mnt/afs" and m["id"] == "01a04263-91e5-7603-bc01-c67e503da6b5"
        for m in details["mount"]
    ):
        raise ValueError("actual AFS volume differs")
    return {
        "job_id": details["name"],
        "display_name": details["display_name"],
        "state": details["state"],
        "cluster": acp.CLUSTER,
        "gpu_count": 1,
        "released": details["state"] in TERMINAL,
        "start_time": details.get("start_time"),
        "complete_time": details.get("complete_time"),
        "raw_details_sha256": fingerprint(details),
    }


def validate_request(request_path, plan, worker):
    request_path = Path(request_path).resolve()
    request = read(request_path)
    phase = read(request["phase_claim"])
    if (
        request["execution_id"] != plan["execution_id"]
        or request["phase_id"] != plan["phase_id"]
        or request["worker_id"] != worker
        or type(worker) is not int
        or worker not in range(2)
        or request["source_files"] != plan["source_files"]
        or request["kind"] != plan["kind"]
        or fingerprint(phase) != request["phase_claim_sha256"]
        or phase["execution_id"] != plan["execution_id"]
        or str(request_path.parent.parent) != phase["submission_directory"]
        or request_path.parent.name != f"worker-{worker}"
        or str(Path(request["phase_claim"]))
        != str(Path(plan["launch_registry"]) / "phase_submit.json")
    ):
        raise ValueError("model request is not the bound one-use phase submission")
    started = read(request_path.parent / "worker_started.json")
    if (
        started["request_sha256"] != fingerprint(request)
        or started["hostname"] == request["source_cci_hostname"]
    ):
        raise ValueError("missing actual ACP worker start")
    return request, phase, started


def validate_phase(proof, plan, audits, slots):
    if proof["execution_id"] != plan["execution_id"] or proof["phase_id"] != plan["phase_id"]:
        raise ValueError("ACP provenance belongs to another execution")
    phase = proof["phase_claim"]
    if (
        phase["execution_id"] != plan["execution_id"]
        or phase["source_files"] != plan["source_files"]
        or phase["kind"] != "model"
        or phase["workers"] != 2
    ):
        raise ValueError("ACP phase claim differs")
    workers = proof["workers"]
    if [w["worker_id"] for w in workers] != list(range(2)):
        raise ValueError("ACP provenance must retain both workers")
    job_ids, records = [], []
    for row, audit in zip(workers, audits):
        wid = row["worker_id"]
        request = row.get("request")
        if request is None:
            if audit["attempted"] or audit["raw_returned"] or audit["claim_present"]:
                raise ValueError("model collection without a submission request")
            records.append({"worker_id": wid, "state": "unsubmitted", "gpu_count": 0})
            continue
        if (
            request["execution_id"] != plan["execution_id"]
            or request["phase_id"] != plan["phase_id"]
            or request["source_files"] != plan["source_files"]
            or request["kind"] != "model"
            or request["worker_id"] != wid
            or request["phase_claim_sha256"] != fingerprint(phase)
            or request["max_model_attempts"] != sum(s["worker_id"] == wid for s in slots)
        ):
            raise ValueError("worker submission scope differs")
        job = row.get("job_details")
        if job is None:
            if audit["attempted"] or audit.get("runtime_observation"):
                raise ValueError("model output lacks actual platform job evidence")
            records.append({"worker_id": wid, "state": "submission_unknown", "gpu_count": None})
            continue
        record = job_record(job, request)
        if not record["released"]:
            raise ValueError("final model audit requires a terminal platform job")
        job_ids.append(record["job_id"])
        started, result = row.get("worker_started"), row.get("worker_result")
        if audit.get("runtime_observation") and (
            not started
            or started["request_sha256"] != fingerprint(request)
            or started["hostname"] == request["source_cci_hostname"]
            or started["hostname"] != audit["runtime_observation"]["hostname"]
        ):
            raise ValueError("collector runtime not bound to actual ACP worker")
        if result is not None and (
            result["request_sha256"] != fingerprint(request)
            or result["generate_disabled"] is not False
        ):
            raise ValueError("worker result identity differs")
        if audit["status"] == "complete" and (
            not result or result["status"] != "passed" or result["collector_exit_code"] != 0
        ):
            raise ValueError("complete collector missing successful worker exit")
        records.append({"worker_id": wid, **record})
    if len(job_ids) != len(set(job_ids)):
        raise ValueError("same ACP job assigned to multiple workers")
    return records
