import json

import pytest

from disastertrace.monitoring_v1 import api_capture
from disastertrace.monitoring_v1.api_capture import ApiBudget


def budget(tmp_path):
    p = tmp_path / "budget.json"
    p.write_text(json.dumps({"limit_nanodollars": 100, "max_calls": 3, "calls": {}}))
    return ApiBudget(p)


def test_unknown_call_keeps_fee_reservation_and_cannot_be_retried(tmp_path):
    b = budget(tmp_path)
    b.transact("one", 70)
    b.transact("one", outcome="unknown")
    with pytest.raises(ValueError, match="budget"):
        b.transact("two", 40)
    with pytest.raises(ValueError, match="duplicate"):
        b.transact("one", 1)


def test_actual_usage_releases_only_known_unused_reservation(tmp_path):
    b = budget(tmp_path)
    b.transact("one", 70)
    b.transact("one", actual=20)
    b.transact("two", 80)
    with pytest.raises(ValueError, match="budget"):
        b.transact("three", 1)


def test_usage_overrun_stops_all_further_dispatch(tmp_path):
    b = budget(tmp_path)
    b.transact("one", 20)
    b.transact("one", actual=25)
    with pytest.raises(ValueError, match="overrun"):
        b.transact("two", 1)


def test_transient_afs_lock_contention_does_not_create_an_extra_call(tmp_path, monkeypatch):
    original = api_capture.fcntl.flock
    attempts = []

    def intermittent(fd, flags):
        attempts.append(flags)
        if len(attempts) <= 3:
            raise BlockingIOError(11, "AFS lock busy")
        return original(fd, flags)

    monkeypatch.setattr(api_capture.fcntl, "flock", intermittent)
    monkeypatch.setattr(api_capture.time, "sleep", lambda seconds: None)
    b = budget(tmp_path)
    b.transact("original", 20)
    state = json.loads(b.path.read_text())
    assert list(state["calls"]) == ["original"]
    assert len(attempts) == 4
