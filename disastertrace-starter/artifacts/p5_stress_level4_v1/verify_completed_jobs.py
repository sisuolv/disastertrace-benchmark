"""Verify the three actual terminal ACP jobs against captured model reports."""

from acp_common import FACTORS, HERE
from inspect_acp import observe

from disastertrace.local_eval.storage import digest, now, read, write


def main():
    outcomes = {}
    for factor in FACTORS:
        directory = HERE / "acp/phase_001" / factor
        job, observation = observe(directory)
        worker = read(directory / "worker_result.json")
        request = read(directory / "request.json")
        plan = read(HERE / "units" / factor / "execution_live/execution.json")
        report = read(HERE / "units" / factor / "model_report/report.json")
        if (
            job["state"] != "SUCCEEDED"
            or job["lme"]["current_retries"] != 0
            or worker["status"] != "passed"
            or not worker["all_commands_exit_zero"]
            or worker["request_sha256"] != digest(directory / "request.json")
            or worker["worker_sha256"] != request["worker_sha256"]
            or worker["audit_id"] != report["audit_id"]
            or worker["execution_id"] != plan["execution_id"]
        ):
            raise ValueError("completed independently audited ACP factor required: " + factor)
        if (
            not report["complete"]
            or report["received"] != 540
            or report["attempted"] != 540
            or report["local_model_calls"] != 540
            or report["origin"] != "local_model_vllm_stress_constrained_v1"
        ):
            raise ValueError("full actual factor matrix required: " + factor)
        outcomes[factor] = {
            "job_id": job["name"],
            "state": job["state"],
            "gpu_count": 1,
            "execution_id": plan["execution_id"],
            "audit_id": report["audit_id"],
            "received": report["received"],
            "attempted": report["attempted"],
            "worker_result_sha256": digest(directory / "worker_result.json"),
            "job_observation": str(observation.relative_to(HERE)),
            "job_observation_sha256": digest(observation),
            "platform_retries": job["lme"]["current_retries"],
        }
    if len({v["job_id"] for v in outcomes.values()}) != 3:
        raise ValueError("three distinct ACP jobs required")
    result = {
        "status": "passed",
        "at": now(),
        "units": outcomes,
        "received_total": sum(v["received"] for v in outcomes.values()),
        "attempted_total": sum(v["attempted"] for v in outcomes.values()),
        "phase_launch_consumed": True,
        "all_acp_jobs_succeeded": True,
        "gpu_resources_released_per_acp_terminal_state": True,
        "new_model_calls_from_verification": 0,
    }
    write(HERE / "completed_jobs_verified.json", result)
    print(result)


if __name__ == "__main__":
    main()
