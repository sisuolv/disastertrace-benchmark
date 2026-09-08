"""ACP may report zero running replicas during STARTING despite one reserved GPU."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from disastertrace.forecast_task.common import read, strict_json

ROOT = Path(__file__).resolve().parents[2] / "artifacts/p9_forecast_model_v1"


def module():
    spec = importlib.util.spec_from_file_location("p9_observer_v2", ROOT / "watch_live_v2.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixture():
    details = strict_json(read(ROOT / "finalization_01/status/00000-1.json")["stdout"])
    request = read(ROOT / "acp_live_01/worker-1/request.json")
    return details, request


def test_actual_saved_starting_zero_is_pending_not_final_hardware_evidence():
    details, request = fixture()
    assert details["state"] == "STARTING"
    assert details["roles"][0]["resource_spec"][0]["replicas"] == 0
    observed = module().observe_job(details, request)
    assert observed["released"] is False
    assert observed["pending_allocation_metadata"] is True
    assert details["roles"][0]["resource_spec"][0]["replicas"] == 0


@pytest.mark.parametrize("mutation", ["terminal_zero", "wrong_gpu", "wrong_command", "running_zero"])
def test_transient_exception_does_not_weaken_final_or_resource_validation(mutation):
    details, request = fixture()
    details = deepcopy(details)
    if mutation == "terminal_zero":
        details["state"] = "SUCCEEDED"
    elif mutation == "running_zero":
        details["state"] = "RUNNING"
    elif mutation == "wrong_gpu":
        details["roles"][0]["resource_spec"][0]["limits"]["nvidia.com/gpu"] = "4"
    else:
        details["roles"][0]["startup_script"] = "unbound"
    with pytest.raises(ValueError):
        module().observe_job(details, request)
