import importlib.util
from pathlib import Path
import sys

import pytest

from disastertrace.forecast_task.common import fingerprint

ROOT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("cutoff_check", ROOT / "check_dispatch_deadlines.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

BEGIN = "2026-09-08T16:05:16+00:00"
END = "2026-09-09T02:05:16+00:00"


def batch(name, *, started="2026-09-09T02:05:15+00:00", raw_at=None, returned=0):
    intent = {"at": "2026-09-09T02:05:14+00:00", "prepared": [{"attempt_id": name + str(i)} for i in range(2)]}
    return {"batch": name, "intent": intent,
            "started": {"at": started, "intent_sha256": fingerprint(intent)} if started else None,
            "raw": {"at": raw_at, "intent_sha256": fingerprint(intent),
                    "results": [{"attempt_id": name + str(i)} for i in range(returned)]} if raw_at else None}


def test_prepared_only_requests_are_not_dispatched():
    result = check.summarize_batches([batch("0", started=None)], BEGIN, END)
    assert result["attempted"] == result["unknown_outcomes"] == 0
    assert result["prepared_without_dispatch"] == 2


def test_late_return_is_distinct_from_outside_window_dispatch_and_unknown():
    rows = [batch("0", raw_at="2026-09-09T02:05:17+00:00", returned=2), batch("1")]
    result = check.summarize_batches(rows, BEGIN, END)
    assert result["attempted"] == 4 and result["raw_returned"] == 2
    assert result["unknown_outcomes"] == 2
    assert result["outside_window_dispatch_batches"] == []
    assert result["raw_returns_at_or_after_deadline"][0]["batch"] == "0"
    assert result["incomplete_dispatched_batches"][0]["batch"] == "1"


def test_dispatch_at_exact_deadline_is_outside_window():
    result = check.summarize_batches([batch("0", started=END)], BEGIN, END)
    assert result["outside_window_dispatch_batches"] == ["0"]


def test_partial_batch_retains_unknown_attempt():
    result = check.summarize_batches([batch("0", raw_at=END, returned=1)], BEGIN, END)
    assert result["unknown_outcomes"] == 1
    assert result["incomplete_dispatched_batches"][0]["raw_wrapper_present"] is True


def test_raw_without_dispatch_is_rejected():
    with pytest.raises(ValueError, match="without a dispatch marker"):
        check.summarize_batches([batch("0", started=None, raw_at=END, returned=2)], BEGIN, END)


def test_unplanned_return_is_rejected():
    row = batch("0", raw_at=END, returned=2)
    row["raw"]["results"][0]["attempt_id"] = "unplanned"
    with pytest.raises(ValueError, match="unplanned returns"):
        check.summarize_batches([row], BEGIN, END)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        check.summarize_batches([batch("0", started="2026-09-09T02:05:15")], BEGIN, END)
