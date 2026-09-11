"""Actual ACP QUEUEING/INIT snapshots must not relax terminal resource checks."""

from copy import deepcopy
import importlib.util
import os
from pathlib import Path

import pytest

from disastertrace.forecast_task.common import read, strict_json

PROJECT = Path(__file__).resolve().parents[2]
BUNDLE = PROJECT / "artifacts/p12_compact_grammar_v1"


def load(path):
    spec = importlib.util.spec_from_file_location("pending_state_test_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observe(details, request):
    original = load(BUNDLE / "watch_live.py")
    if os.environ.get("DT_TEST_ORIGINAL_OBSERVER") == "1":
        return original.observe_job(details, request)
    current = load(PROJECT / "artifacts/autonomy_10h_v1/continue_live_observer_v2.py")
    return current.observe_job(details, request, original.provenance.job_record)


def fixture(profile):
    snapshot = BUNDLE / ("finalization_" + profile + "_01/status/00000-0.json")
    request = BUNDLE / ("acp_" + profile + "_live_01/worker-0/request.json")
    return strict_json(read(snapshot)["stdout"]), read(request)


@pytest.mark.parametrize("profile,state", [("qwen3", "QUEUEING"), ("deepseek_r1", "INIT")])
def test_actual_pending_snapshots_keep_original_metadata_and_reserved_allocation(profile, state):
    details, request = fixture(profile)
    before = deepcopy(details)
    assert details["state"] == state
    assert details["roles"][0]["resource_spec"][0]["replicas"] == 0
    assert observe(details, request) == {
        "state": state, "released": False, "pending_allocation_metadata": True,
    }
    assert details == before


@pytest.mark.parametrize("profile", ["qwen3", "deepseek_r1"])
@pytest.mark.parametrize("mutation", ["running_zero", "succeeded_zero", "failed_zero", "unknown_state",
                                     "wrong_gpu", "wrong_request", "wrong_command", "wrong_total", "retry"])
def test_pending_exception_does_not_accept_wrong_identity_resources_or_terminal_metadata(profile, mutation):
    details, request = fixture(profile)
    role = details["roles"][0]
    if mutation in {"running_zero", "succeeded_zero", "failed_zero"}:
        details["state"] = mutation.split("_")[0].upper()
    elif mutation == "unknown_state":
        details["state"] = "UNREGISTERED"
    elif mutation == "wrong_gpu":
        role["resource_spec"][0]["limits"]["nvidia.com/gpu"] = "4"
    elif mutation == "wrong_request":
        role["resource_spec"][0]["requests"]["nvidia.com/gpu"] = "4"
    elif mutation == "wrong_command":
        role["startup_script"] = "unbound"
    elif mutation == "wrong_total":
        role["total_replicas"] = 2
    else:
        details["lme"]["current_retries"] = 1
    with pytest.raises(ValueError):
        observe(details, request)


@pytest.mark.parametrize("profile", ["qwen3", "deepseek_r1"])
def test_normal_terminal_allocation_uses_original_strict_validator(profile):
    details, request = fixture(profile)
    details["state"] = "SUCCEEDED"
    details["roles"][0]["resource_spec"][0]["replicas"] = 1
    original = load(BUNDLE / "watch_live.py")
    assert observe(details, request) == original.provenance.job_record(details, request)
