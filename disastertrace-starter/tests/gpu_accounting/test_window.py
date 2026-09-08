import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1/account_gpu_window.py"
SPEC = importlib.util.spec_from_file_location("gpu_window", SCRIPT)
gpu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gpu)


def time(hour):
    return gpu.stamp(f"2026-09-08T{hour:02d}:00:00+00:00")


def test_release_and_new_reservation_at_same_time_are_not_eight_gpus():
    result = gpu.timeline([(time(16), time(17), 4), (time(17), time(18), 4)], time(16), time(18))
    assert result["maximum_concurrent_gpus"] == 4
    assert result["gpu_hours"] == 8


def test_inherited_job_is_clipped_to_original_window():
    result = gpu.timeline([(time(15), time(19), 1)], time(16), time(18))
    assert result["gpu_hours"] == 2
    assert result["intervals"] == [{"start": time(16).isoformat(), "end": time(18).isoformat(), "gpus": 1, "seconds": 7200}]


def test_pending_job_with_zero_running_replicas_uses_capacity():
    window = {"received_at": time(16).isoformat(), "autonomous_work_deadline": time(20).isoformat(), "max_parallel_h100": 4}
    job = {"name": "pending", "display_name": "pending", "state": "STARTING", "create_time": time(17).isoformat(),
           "roles": [{"total_replicas": 1, "resource_spec": [{"replicas": 0, "requests": {"nvidia.com/gpu": "1"}, "limits": {"nvidia.com/gpu": "1"}}]}]}
    snapshot = {"exit_code": 0, "at": time(18).isoformat(), "stdout": json.dumps([job])}
    result = gpu.account(window, snapshot)
    assert result["reserved_including_pending"]["maximum_concurrent_gpus"] == 1
    assert result["reserved_including_pending"]["gpu_hours"] == 1
    assert result["running_allocation"]["gpu_hours"] == 0
    assert result["all_observed_jobs_released"] is False


def test_reserved_overlap_over_cap_is_reported_as_failure():
    window = {"received_at": time(16).isoformat(), "autonomous_work_deadline": time(20).isoformat(), "max_parallel_h100": 4}
    jobs = [{"name": str(n), "display_name": str(n), "state": "INIT", "create_time": time(17).isoformat(),
             "roles": [{"total_replicas": 1, "resource_spec": [{"replicas": 0, "requests": {"nvidia.com/gpu": "1"}, "limits": {"nvidia.com/gpu": "1"}}]}]} for n in range(5)]
    result = gpu.account(window, {"exit_code": 0, "at": time(18).isoformat(), "stdout": json.dumps(jobs)})
    assert result["within_four_gpu_cap"] is False
