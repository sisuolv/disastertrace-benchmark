import json
from decimal import Decimal

import pytest

from disastertrace.automated.budget_ledger import BudgetLedger, default_policy
from disastertrace.automated.run_store import RunStore, read_events


def test_budget_boundary_and_unknown_is_not_free():
    policy = default_policy()
    policy["allowance"] = "0.46678016"
    ledger = BudgetLedger(policy)
    row = ledger.reserve("a1", 4096)
    assert Decimal(row["reservation"]) == Decimal("0.46678016")
    ledger.unknown("a1")
    with pytest.raises(ValueError):
        ledger.reserve("a2", 4096)
    assert ledger.snapshot()["pending"] == "0.46678016"


def test_settlement_does_not_count_reasoning_twice():
    ledger = BudgetLedger(default_policy())
    ledger.reserve("a1", 8192)
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "total_tokens": 110,
        "completion_tokens_details": {"reasoning_tokens": 9},
    }
    first = ledger.settle("a1", usage)
    assert first == ledger.settle("a1", usage)
    assert Decimal(ledger.snapshot()["settled"]) == Decimal("0.0000572")
    with pytest.raises(ValueError):
        ledger.settle("a1", {**usage, "completion_tokens": 11, "total_tokens": 111})


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"prompt_tokens": -1},
        {"prompt_tokens": 1, "completion_tokens": 9000, "total_tokens": 9001},
        {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2},
    ],
)
def test_invalid_usage_retains_reservation(usage):
    ledger = BudgetLedger(default_policy())
    ledger.reserve("a1", 4096)
    with pytest.raises(ValueError):
        ledger.settle("a1", usage)
    assert Decimal(ledger.snapshot()["pending"]) > 0


def test_store_binding_lock_and_damaged_tail(tmp_path):
    output, registry = tmp_path / "run", tmp_path / "claims"
    with RunStore(output, "e" * 64, registry) as store:
        store.append("reserved", {"attempt": "a1"})
        with pytest.raises(ValueError):
            with RunStore(output, "e" * 64, registry, resume=True):
                pass
    assert read_events(output)[0]["kind"] == "reserved"
    with pytest.raises(ValueError):
        with RunStore(tmp_path / "other", "e" * 64, registry):
            pass
    with RunStore(output, "e" * 64, registry, resume=True) as store:
        store.append("send_intent", {"attempt": "a1"})
    with (output / "journal.jsonl").open("ab") as stream:
        stream.write(b'{"unfinished":')
    with pytest.raises(ValueError, match="incomplete"):
        read_events(output)


def test_hash_chain_rejects_middle_corruption(tmp_path):
    output = tmp_path / "run"
    with RunStore(output, "f" * 64, tmp_path / "claims") as store:
        store.append("one", {"value": 1})
        store.append("two", {"value": 2})
    rows = [json.loads(x) for x in (output / "journal.jsonl").read_text().splitlines()]
    rows[0]["data"]["value"] = 9
    (output / "journal.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
    with pytest.raises(ValueError, match="chain"):
        read_events(output)


def test_independent_process_cannot_claim_same_experiment(tmp_path):
    import subprocess
    import sys

    output, registry = tmp_path / "run", tmp_path / "claims"
    with RunStore(output, "b" * 64, registry):
        code = (
            "from disastertrace.automated.run_store import RunStore; "
            "from pathlib import Path; "
            'RunStore(Path(__import__("sys").argv[1]), "b" * 64, '
            'Path(__import__("sys").argv[2]), resume=True).__enter__()'
        )
        process = subprocess.run(
            [sys.executable, "-c", code, str(output), str(registry)], capture_output=True, text=True
        )
        assert process.returncode != 0
        assert "already has a writer" in process.stderr


def test_fsync_failure_is_not_silently_accepted(tmp_path, monkeypatch):
    import os

    output = tmp_path / "run"
    with RunStore(output, "c" * 64, tmp_path / "claims") as store:

        def broken(fd):
            raise OSError("injected durability failure")

        monkeypatch.setattr(os, "fsync", broken)
        with pytest.raises(OSError, match="durability"):
            store.append("reserved", {"slot": 0})


def test_abrupt_process_exit_releases_lock_preserves_prefix(tmp_path):
    import subprocess
    import sys

    output, registry = tmp_path / "run", tmp_path / "claims"
    code = """
import os, sys
from pathlib import Path
from disastertrace.automated.run_store import RunStore
with RunStore(Path(sys.argv[1]), 'd' * 64, Path(sys.argv[2])) as store:
    store.append('send_intent', {'slot': 0})
    os._exit(17)
"""
    result = subprocess.run([sys.executable, "-c", code, str(output), str(registry)])
    assert result.returncode == 17
    with RunStore(output, "d" * 64, registry, resume=True):
        assert read_events(output)[0]["kind"] == "send_intent"
