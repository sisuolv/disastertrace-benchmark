"""The phase handoff cannot overlap four replicas with any active GPU allocation."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[2] / "artifacts/p9_forecast_model_v1/run_after_p8.py"
    spec = importlib.util.spec_from_file_location("registered_p9_chain", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job(name, state="SUCCEEDED", gpus=1):
    return {"name": name, "state": state, "roles": [{"resource_spec": [{"replicas": 1,
            "requests": {"nvidia.com/gpu": str(gpus)}, "limits": {"nvidia.com/gpu": str(gpus)}}]}]}


def test_requires_all_prerequisites_terminal_and_all_capacity_free(module):
    jobs = [job(str(i)) for i in range(4)]
    assert module.available(jobs, [str(i) for i in range(4)]) == (True, 0)
    jobs[0]["state"] = "RUNNING"
    assert module.available(jobs, [str(i) for i in range(4)]) == (False, 1)
    jobs[0]["state"] = "SUCCEEDED"
    jobs.append(job("another-owned-job", "PENDING", 2))
    assert module.available(jobs, [str(i) for i in range(4)]) == (False, 2)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "paginated", "unknown_resources", "bad_replicas"])
def test_ambiguous_resource_inventory_cannot_authorize_dispatch(module, mutation):
    jobs = [job(str(i)) for i in range(4)]
    if mutation == "missing":
        jobs.pop()
    elif mutation == "duplicate":
        jobs.append(jobs[0])
    elif mutation == "paginated":
        jobs.extend(job(str(i)) for i in range(4, 100))
    else:
        jobs[0]["state"] = "RUNNING"
        if mutation == "unknown_resources":
            jobs[0]["roles"] = []
        else:
            jobs[0]["roles"][0]["resource_spec"][0]["replicas"] = True
    with pytest.raises(ValueError):
        module.available(jobs, [str(i) for i in range(4)])
