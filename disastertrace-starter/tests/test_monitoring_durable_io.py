import json

import pytest

from disastertrace.monitoring_v1.journal import EventJournal, read_journal, recover_prefix
from disastertrace.monitoring_v1.range_reader import BoundedRangeReader, RangeResponse
from disastertrace.monitoring_v1.resources import BudgetLedger, Cost


def test_pending_reservation_survives_restart_and_cannot_be_reused(tmp_path):
    path = tmp_path / "ledger.jsonl"
    with EventJournal(path) as journal:
        ledger = BudgetLedger({"tokens": 100}, journal=journal)
        ledger.reserve("a", Cost(tokens=80), "A")
    with EventJournal(path) as journal:
        restored = BudgetLedger.restore(journal)
        assert restored.spent.tokens == 0
        assert restored.reserved.tokens == 80
        with pytest.raises(ValueError, match="hard limits"):
            restored.reserve("b", Cost(tokens=21), "B")
        restored.settle("a", Cost(tokens=30), outcome="invalid_response")
    with EventJournal(path) as journal:
        restored = BudgetLedger.restore(journal)
        assert restored.spent.tokens == 30 and restored.reserved.tokens == 0
        assert restored.entries["a"]["outcome"] == "invalid_response"
        assert restored.settle("a", Cost(tokens=30), outcome="invalid_response") is False
        assert restored.reserve("a", Cost(tokens=80), "A") is False


def test_ledger_write_failure_prevents_in_memory_resource_commit():
    class BrokenJournal:
        records = ()

        def append(self, event_id, payload):
            if event_id != "ledger:contract":
                raise OSError("simulated durable storage failure")

    ledger = BudgetLedger({"requests": 1}, journal=BrokenJournal())
    with pytest.raises(OSError):
        ledger.reserve("request", Cost(requests=1), "A")
    assert ledger.reserved.requests == 0 and not ledger.entries


def test_durable_journal_replay_is_hash_chained_and_idempotent(tmp_path):
    path = tmp_path / "events.jsonl"
    with EventJournal(path) as journal:
        receipt = journal.append("call-start", {"time": 1, "kind": "begin"})
        assert receipt == journal.append("call-start", {"time": 1, "kind": "begin"})
        journal.append("call-complete", {"time": 2, "kind": "candidate", "probability": 0.2})
        with pytest.raises(ValueError):
            journal.append("call-start", {"time": 0})
    replay = read_journal(path)
    assert len(replay.records) == 2 and replay.incomplete_tail == b""
    with EventJournal(path) as restored:
        assert len(restored.records) == 2


def test_partial_completion_is_not_a_durable_receipt_and_original_is_preserved(tmp_path):
    path = tmp_path / "events.jsonl"
    with EventJournal(path) as journal:
        journal.append("begin", {"time": 1})
    original = path.read_bytes() + b'{"event_id":"unfinished"'
    path.write_bytes(original)
    replay = read_journal(path)
    assert len(replay.records) == 1 and replay.incomplete_tail
    with pytest.raises(ValueError, match="partial"):
        EventJournal(path)
    recovered = tmp_path / "recovered.jsonl"
    receipt = recover_prefix(path, recovered)
    assert path.read_bytes() == original
    assert receipt["incomplete_tail_bytes"] > 0
    with EventJournal(recovered) as journal:
        journal.append("new-completion", {"time": 3})
    assert len(read_journal(recovered).records) == 2


def test_complete_line_tampering_is_not_treated_as_recoverable_tail(tmp_path):
    path = tmp_path / "events.jsonl"
    with EventJournal(path) as journal:
        journal.append("start", {"time": 1})
    row = json.loads(path.read_text())
    row["payload"]["time"] = 0
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="hash"):
        read_journal(path)


def test_second_writer_cannot_open_same_journal(tmp_path):
    path = tmp_path / "events.jsonl"
    with EventJournal(path), pytest.raises(BlockingIOError):
        EventJournal(path)


def test_range_budget_is_checked_before_network_call():
    reader = BoundedRangeReader(max_bytes=10, max_requests=2)
    calls = []

    def fetch(start, end, cap):
        calls.append((start, end, cap))
        return RangeResponse(
            206, b"x" * (end - start + 1), f"bytes {start}-{end}/100", etag='"version-1"'
        )

    reader.fetch(0, 5, fetch)
    with pytest.raises(ValueError, match="budget"):
        reader.fetch(6, 10, fetch)
    assert calls == [(0, 5, 6)]
    assert reader.spent_bytes == 6


def test_absent_version_headers_cannot_establish_consistent_ranges():
    reader = BoundedRangeReader(max_bytes=10, max_requests=2)
    with pytest.raises(ValueError, match="version"):
        reader.fetch(0, 3, lambda s, e, cap: RangeResponse(206, b"xxxx", "bytes 0-3/100"))
    assert reader.spent_bytes == 4 and reader.spent_requests == 1


def test_changed_object_version_or_ignored_range_is_rejected_after_accounting():
    reader = BoundedRangeReader(max_bytes=10, max_requests=3)
    reader.fetch(0, 3, lambda s, e, cap: RangeResponse(206, b"xxxx", "bytes 0-3/100", etag="one"))
    with pytest.raises(ValueError, match="version"):
        reader.fetch(
            4, 7, lambda s, e, cap: RangeResponse(206, b"yyyy", "bytes 4-7/100", etag="two")
        )
    assert reader.spent_bytes == 8
    with pytest.raises(ValueError, match="range"):
        reader.fetch(8, 9, lambda s, e, cap: RangeResponse(200, b"zz", "", etag="one"))
    assert reader.spent_bytes == 10
