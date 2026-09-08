"""Bind actual successful ACP evidence, then create the fresh one-use live package."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval.storage import digest, read, write
from disastertrace.repeat_live import package

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def main():
    preflight = HERE / "acp/preflight_02"
    request = read(preflight / "request.json")
    result = read(preflight / "worker_result.json")
    submitted = read(preflight / "submission.json")
    statuses = [read(p) for p in sorted(preflight.glob("status_*.json"))]
    from disastertrace.automated.common import strict_json

    jobs = [strict_json(s["stdout"]) for s in statuses if s["exit_code"] == 0]
    job = jobs[-1]
    role = job["roles"][0]
    spec = role["resource_spec"][0]
    if (job["name"] != submitted["job_id"] or job["state"] != "SUCCEEDED"
            or job["display_name"] != request["display_name"]
            or job["resource_pool"]["name"] != "computing-cluster-01g-02"
            or len(job["roles"]) != 1 or len(role["resource_spec"]) != 1
            or spec["name"] != "N6lS.Iu.I10.1.8c128g" or spec["replicas"] != 1
            or spec["limits"]["nvidia.com/gpu"] != "1" or role["total_replicas"] != 1
            or role["startup_script"] != request["command"]
            or job["fault_tolerance"]["backoff_limit"] != 0
            or result["request_sha256"] != fingerprint(request)
            or submitted["request_sha256"] != digest(preflight / "request.json")):
        raise ValueError("actual ACP preflight details do not match the submitted scope")
    proof = {"request": request, "result": result, "job_detail": job,
             "job": {"state": job["state"], "job_id": job["name"], "gpu_count": 1,
                     "cluster": job["resource_pool"]["name"]}}
    package.validate_preflight(proof, package.source_inventory())
    write(HERE / "PREFLIGHT_VERIFIED_02.json", proof)
    deadline = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    plan = package.freeze(
        PROJECT / "artifacts/p6_offline_v1/execution", HERE / "execution_live_02",
        PROJECT / "work/p6-live-v1/registry-02", live=True,
        run_path=PROJECT / "work/p6-live-v1/model", deadline_utc=deadline, preflight=proof,
        engine_source="/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/lib/python3.10/site-packages",
    )
    write(HERE / "LIVE_FREEZE_RECEIPT_02.json", {"execution_id": plan["execution_id"],
          "deadline_utc": deadline, "planned_responses": 2160, "model_generations": 0})
    print({"execution_id": plan["execution_id"], "deadline_utc": deadline}, flush=True)


if __name__ == "__main__":
    main()
