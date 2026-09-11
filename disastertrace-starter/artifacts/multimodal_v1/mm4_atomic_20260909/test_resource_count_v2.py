"""Regression for the observed STARTING replica count, without submitting jobs."""

import copy
import json
from pathlib import Path

import pytest

from resource_count_v2 import requested_h100


def observed():
    data = json.loads((Path(__file__).parent / "acp/1/account_before.json").read_text())
    return next(j for j in data if j["name"] == "pt-qrght4j8")


@pytest.mark.parametrize("realized", [0, 1])
def test_reserved_before_realized(realized):
    job = observed()
    job["roles"][0]["resource_spec"][0]["replicas"] = realized
    assert requested_h100(job) == 1


@pytest.mark.parametrize("field,value", [("total_replicas", 2), ("gpu", 2), ("replicas", 2)])
def test_reject_unknown_capacity(field, value):
    job = copy.deepcopy(observed())
    role = job["roles"][0]
    if field == "total_replicas":
        role[field] = value
    elif field == "gpu":
        role["resource_spec"][0]["requests"]["nvidia.com/gpu"] = str(value)
    else:
        role["resource_spec"][0][field] = value
    with pytest.raises(ValueError):
        requested_h100(job)
