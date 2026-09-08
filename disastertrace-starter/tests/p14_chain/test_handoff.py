"""Prompt-role handoff permits two replicas only after exact prerequisites release."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest

from disastertrace.qwen_role_live import acp


def module():
    path = Path(__file__).resolve().parents[2] / "artifacts/p14_qwen_prompt_role_v1/run_after_p12_qwen.py"
    spec = importlib.util.spec_from_file_location("p14_chain", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def job(name, state="SUCCEEDED", replicas=1):
    return {"name": name, "state": state, "roles": [{"total_replicas": 1, "resource_spec": [{
        "name": acp.SPEC, "replicas": replicas, "requests": {"nvidia.com/gpu": "1"},
        "limits": {"nvidia.com/gpu": "1"}}]}]}


def test_two_other_pending_gpus_are_allowed_but_a_third_prevents_dispatch():
    ids = ["p12-qwen-0", "p12-qwen-1", "p14-preflight"]
    jobs = [job(i) for i in ids] + [job("deepseek-0", "STARTING", 0), job("deepseek-1", "RUNNING")]
    assert module().readiness(jobs, ids) == (True, 2)
    jobs.append(job("other", "PENDING", 0))
    assert module().readiness(jobs, ids) == (False, 3)
    jobs[0]["state"] = "RUNNING"
    assert module().readiness(jobs, ids) == (False, 4)


def test_prerequisites_cannot_be_missing_or_aliased():
    with pytest.raises(ValueError):
        module().readiness([job("a")], ["a", "a", "a"])
    with pytest.raises(ValueError):
        module().readiness([job("a")], ["a", "b", "c"])


@pytest.mark.parametrize("change", ["none", "settings", "seed", "attempt"])
def test_only_role_placement_may_differ_in_a_comparison(change):
    before = {k: k for k in ("task_package_id", "resource_package_id", "model_identity", "model_profile", "backend_files")}
    before["settings"] = {"context": 32768}
    after = deepcopy(before)
    after["settings"]["prompt_role_policy"] = "system_contract_prepended_to_user_v1"
    slot = {k: k for k in ("slot_id", "seed", "method", "repeat", "episode_id", "opportunity_id", "worker_id", "attempt_id")}
    other = {**slot, "attempt_id": "new"}
    if change == "none":
        assert module().validate_comparison(before, after, [slot], [other])
        return
    if change == "settings":
        after["settings"]["context"] = 16384
    elif change == "seed":
        other["seed"] = "different"
    else:
        other["attempt_id"] = slot["attempt_id"]
    with pytest.raises(ValueError):
        module().validate_comparison(before, after, [slot], [other])
