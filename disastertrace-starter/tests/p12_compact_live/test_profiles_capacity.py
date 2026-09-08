from copy import deepcopy

import pytest

from disastertrace.compact_live import acp, capacity, profiles


def test_switching_profiles_never_mutates_frozen_adapters():
    original = {name: deepcopy(adapter.SETTINGS) for name, adapter in profiles.ADAPTERS.items()}
    for name in ("qwen3", "deepseek_r1", "qwen3"):
        plan = {"model_profile": name, "settings": original[name]}
        assert profiles.adapter_for(plan) is profiles.ADAPTERS[name]
        assert profiles.decoder_for(plan)["reasoning_backend"] == name
    assert original == {name: adapter.SETTINGS for name, adapter in profiles.ADAPTERS.items()}
    with pytest.raises(ValueError):
        profiles.adapter_for({"model_profile": "deepseek_r1", "settings": original["qwen3"]})
    with pytest.raises(ValueError):
        profiles.adapter_for({"model_profile": "unregistered", "settings": {}})


def job(name, state="RUNNING", replicas=1):
    return {
        "name": name,
        "state": state,
        "roles": [
            {
                "total_replicas": 1,
                "resource_spec": [
                    {
                        "name": acp.SPEC,
                        "replicas": replicas,
                        "requests": {"nvidia.com/gpu": "1"},
                        "limits": {"nvidia.com/gpu": "1"},
                    }
                ],
            }
        ],
    }


def test_starting_zero_running_replicas_still_consumes_reserved_capacity():
    assert capacity.occupied([job("a", "STARTING", 0), job("b")]) == 2
    assert capacity.occupied([job("a", "SUCCEEDED"), job("b", "PENDING", 0)]) == 1
    assert capacity.occupied([job(str(i), "STARTING", 0) for i in range(4)]) == 4


@pytest.mark.parametrize(
    "mutation", ["duplicate", "pagination", "missing_roles", "bad_type", "inconsistent_spec"]
)
def test_uncertain_capacity_cannot_authorize_more_gpus(mutation):
    jobs = [job("a")]
    if mutation == "duplicate":
        jobs.append(jobs[0])
    elif mutation == "pagination":
        jobs = [job(str(i)) for i in range(100)]
    elif mutation == "missing_roles":
        jobs[0]["roles"] = []
    elif mutation == "bad_type":
        jobs[0]["roles"][0]["total_replicas"] = True
    else:
        jobs[0]["roles"][0]["resource_spec"][0]["limits"]["nvidia.com/gpu"] = "0"
        jobs[0]["roles"][0]["resource_spec"][0]["requests"]["nvidia.com/gpu"] = "0"
    with pytest.raises(ValueError):
        capacity.occupied(jobs)
