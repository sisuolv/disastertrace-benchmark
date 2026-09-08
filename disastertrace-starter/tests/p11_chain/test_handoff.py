"""The combined dispatch requires all predecessor releases and zero pending GPUs."""

import importlib.util
from pathlib import Path

import pytest

from disastertrace.cohort_live import acp


def module():
    path = Path(__file__).resolve().parents[2] / "artifacts/p11_cohort_live_v1/run_after_p9.py"
    spec = importlib.util.spec_from_file_location("p11_chain", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def job(name, state="SUCCEEDED", running=1):
    return {"name": name, "state": state, "roles": [{"total_replicas": 1, "resource_spec": [
        {"name": acp.SPEC, "replicas": running, "requests": {"nvidia.com/gpu": "1"},
         "limits": {"nvidia.com/gpu": "1"}}]}]}


def test_only_all_six_released_prerequisites_and_free_capacity_allow_handoff():
    ids = ["p9-" + str(i) for i in range(4)] + ["preflight-qwen", "preflight-deepseek"]
    jobs = [job(name) for name in ids]
    assert module().readiness(jobs, ids) == (True, 0)
    jobs[-1]["state"] = "RUNNING"
    assert module().readiness(jobs, ids) == (False, 1)
    jobs[-1]["state"] = "SUCCEEDED"
    jobs.append(job("another-owned-reservation", "STARTING", 0))
    assert module().readiness(jobs, ids) == (False, 1)


@pytest.mark.parametrize("jobs", [[], [job("a"), job("a")]])
def test_missing_or_duplicate_prerequisites_cannot_release_dispatch(jobs):
    with pytest.raises(ValueError):
        module().readiness(jobs, ["a", "b"])
