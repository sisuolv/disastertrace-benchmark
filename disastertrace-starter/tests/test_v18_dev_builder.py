import copy
import csv
import hashlib
from datetime import datetime, timezone

import pytest

from disastertrace.monitoring_v1.targets import utc_us
from scripts import build_v18_dev_episodes as builder
from scripts.build_v18_dev_episodes import (
    ALLOWED_MONTHS,
    CHECKPOINT_OFFSETS_US,
    STATIONS,
    _checkpoint_cutoffs,
    _conditional_window,
    _load_products,
    _normalized_visibility,
    build_roster,
)


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["product_id", "fx_valid", "fx_valid_end", "raw", "is_tempo"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_taf_visibility_is_normalized_to_metres():
    interval = _normalized_visibility("05008KT P6SM FEW060")
    assert interval["lower"] == 9656.064
    assert interval["upper"] == "+inf"
    assert interval["lower_closed"] is False


def test_conditional_window_and_operator_tokens_are_preserved():
    issue = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert _conditional_window("TEMPO 0103/0104 4SM -SHSN", issue) == (
        datetime(2025, 1, 1, 3, tzinfo=timezone.utc),
        datetime(2025, 1, 1, 4, tzinfo=timezone.utc),
    )
    assert _conditional_window("PROB30 0500/0503 1/4SM -SN", issue) == (
        datetime(2025, 1, 5, tzinfo=timezone.utc),
        datetime(2025, 1, 5, 3, tzinfo=timezone.utc),
    )


def test_loaded_products_carry_a_verifiable_body_hash(tmp_path):
    body = tmp_path / "taf" / "synthetic-run" / "KSFO_202501.body"
    rows = [{"product_id": "202501010000-SYNTHETIC", "fx_valid": "2025-01-01 00:00", "raw": "05008KT P6SM FEW060"}]
    _write_csv(body, rows)
    expected_bytes = body.read_bytes()
    products = _load_products(tmp_path, "KSFO", "202501", "synthetic-run")
    identity = products[0]["body_identity"]
    assert identity["raw_sha256"] == hashlib.sha256(expected_bytes).hexdigest()
    assert identity["size_bytes"] == len(expected_bytes)
    assert identity["canonical_path"] == str(body.resolve())


def test_checkpoint_grid_is_t60_t40_t20_earliest_first():
    assert list(CHECKPOINT_OFFSETS_US) == ["T-60", "T-40", "T-20"]
    assert list(CHECKPOINT_OFFSETS_US.values()) == [60 * 60_000_000, 40 * 60_000_000, 20 * 60_000_000]


def test_invalid_checkpoint_cutoffs_are_excluded_with_a_reason_not_coerced():
    # The real grid, on a target 2000 s after the epoch: T-60 and T-40 would
    # fall before the epoch.  They are reported with their computed value, not
    # clamped to 0.
    valid, excluded = _checkpoint_cutoffs(2_000_000_000)
    assert valid == [("T-20", 800_000_000)]
    assert [(row["checkpoint_id"], row["as_of"]) for row in excluded] == [
        ("T-60", -1_600_000_000),
        ("T-40", -400_000_000),
    ]
    assert {row["reason"] for row in excluded} == {"cutoff precedes the Unix epoch (negative utc_us)"}
    # A cutoff that does not strictly precede target_start is excluded too.
    valid, excluded = _checkpoint_cutoffs(100, {"A": 150, "B": 20, "C": 0})
    assert valid == [("B", 80)]
    assert [(row["checkpoint_id"], row["as_of"], row["reason"]) for row in excluded] == [
        ("A", -50, "cutoff precedes the Unix epoch (negative utc_us)"),
        ("C", 100, "cutoff does not strictly precede target_start"),
    ]
    # Grid definition errors are programming errors, not data edge cases.
    with pytest.raises(ValueError, match="strictly decrease"):
        _checkpoint_cutoffs(10_000, {"A": 20, "B": 40})
    with pytest.raises(ValueError, match="integer"):
        _checkpoint_cutoffs(True)


RUN_ID = "synthetic-checkpoint-run"
# (product_id, fx_valid, fx_valid_end, raw).  Target: 06:00-07:00Z, so T-60,
# T-40 and T-20 cut off at 05:00, 05:20 and 05:40 (arrival = issue + 120 s).
CHECKPOINT_SPANNING_TAFS = (
    ("202501100400-SYN-A", "2025-01-10 04:00", "2025-01-10 10:00", "18005KT P6SM FEW060"),  # 04:02, before T-60
    ("202501100505-SYN-B", "2025-01-10 06:00", "2025-01-10 12:00", "18005KT 3SM BR OVC008"),  # 05:07, T-60..T-40
    ("202501100525-SYN-C", "2025-01-10 06:00", "2025-01-10 12:00", "18005KT 1SM BR OVC004"),  # 05:27, T-40..T-20
    ("202501100545-SYN-D", "2025-01-10 06:00", "2025-01-10 12:00", "18005KT 1/2SM FG VV002"),  # 05:47, after T-20
)


def _write_roster_bodies(root, rows):
    for month in ALLOWED_MONTHS:
        for station in STATIONS:
            body_rows = rows if (station, month) == ("KSFO", "202501") else []
            _write_csv(root / "taf" / RUN_ID / f"{station}_{month}.body", body_rows)


def _visible_ids(checkpoint):
    return [
        row["witness"]["source_identity"]["source_id"]
        for row in checkpoint["qualifications"]
        if row["availability"] == "available"
    ]


def test_three_checkpoints_have_increasing_cutoffs_and_visibility_only_grows(tmp_path):
    rows = [
        {"product_id": pid, "fx_valid": start, "fx_valid_end": end, "raw": raw}
        for pid, start, end, raw in CHECKPOINT_SPANNING_TAFS
    ]
    _write_roster_bodies(tmp_path, rows)
    roster = build_roster(tmp_path, limit=24, run_id=RUN_ID)

    assert roster["schema"] == "disastertrace.v18.dev_qualification.v3"
    assert roster["episode_count"] == 1 and roster["checkpoint_count"] == 3
    assert roster["excluded_episodes"] == []
    (episode,) = roster["episodes"]
    # No single episode-level decision time and no flat qualification list.
    assert "as_of" not in episode and "qualifications" not in episode
    target_start = utc_us("2025-01-10T06:00:00+00:00")
    assert (episode["target_start"], episode["target_end"]) == (target_start, target_start + 3_600_000_000)

    checkpoints = episode["checkpoints"]
    assert [c["checkpoint_id"] for c in checkpoints] == ["T-60", "T-40", "T-20"]
    cutoffs = [c["as_of"] for c in checkpoints]
    assert cutoffs == [utc_us(f"2025-01-10T{hhmm}:00+00:00") for hhmm in ("05:00", "05:20", "05:40")]
    assert cutoffs[0] < cutoffs[1] < cutoffs[2] < episode["target_start"]

    # Each checkpoint is its own qualify_stream call over the whole stream,
    # qualified at its own cutoff.
    for checkpoint in checkpoints:
        assert len(checkpoint["qualifications"]) == episode["source_count"] == 4
        assert {row["witness"]["as_of"] for row in checkpoint["qualifications"]} == {checkpoint["as_of"]}

    visible = [_visible_ids(checkpoint) for checkpoint in checkpoints]
    assert visible == [
        ["202501100400-SYN-A"],
        ["202501100400-SYN-A", "202501100505-SYN-B"],
        ["202501100400-SYN-A", "202501100505-SYN-B", "202501100525-SYN-C"],
    ]
    # Monotone: nothing visible at an earlier checkpoint becomes invisible.
    for earlier, later in zip(visible, visible[1:]):
        assert set(earlier) <= set(later)
    # D arrives after T-20 and before target_start, so no checkpoint sees it.
    assert all("202501100545-SYN-D" not in ids for ids in visible)

    # Once visible, a row's qualification is stable at every later checkpoint.
    # Only its own cutoff differs, because earlier arrivals were visible too.
    def without_cutoff(row):
        row = copy.deepcopy(row)
        row["witness"].pop("as_of")
        return row

    for index, checkpoint in enumerate(checkpoints):
        for position, row in enumerate(checkpoint["qualifications"]):
            if row["availability"] == "available":
                for later in checkpoints[index + 1 :]:
                    assert without_cutoff(later["qualifications"][position]) == without_cutoff(row)

    assert [[row["status"] for row in c["qualifications"]] for c in checkpoints] == [
        ["NEW_TARGET_CONTENT", "NOT_YET_AVAILABLE", "NOT_YET_AVAILABLE", "NOT_YET_AVAILABLE"],
        ["NEW_TARGET_CONTENT", "TARGET_CONTENT_CHANGE", "NOT_YET_AVAILABLE", "NOT_YET_AVAILABLE"],
        ["NEW_TARGET_CONTENT", "TARGET_CONTENT_CHANGE", "TARGET_CONTENT_CHANGE", "NOT_YET_AVAILABLE"],
    ]
    # Bookkeeping is per checkpoint; each table covers every evidence row once.
    counts = roster["qualification_status_counts_by_checkpoint"]
    assert list(counts) == ["T-60", "T-40", "T-20"]
    assert counts == {
        "T-60": {"NEW_TARGET_CONTENT": 1, "NOT_YET_AVAILABLE": 3},
        "T-40": {"NEW_TARGET_CONTENT": 1, "NOT_YET_AVAILABLE": 2, "TARGET_CONTENT_CHANGE": 1},
        "T-20": {"NEW_TARGET_CONTENT": 1, "NOT_YET_AVAILABLE": 1, "TARGET_CONTENT_CHANGE": 2},
    }
    assert all(sum(table.values()) == episode["source_count"] for table in counts.values())
    assert "qualification_status_counts" not in roster


def test_episode_missing_a_checkpoint_is_recorded_and_not_admitted(monkeypatch, tmp_path):
    # A target 30 minutes after the epoch: T-60 and T-40 cutoffs would be
    # negative.  The candidate is recorded with its reasons, not padded.
    minute = 60_000_000

    def product(revision, issued, start, vis):
        return {
            "station": "KSFO",
            "source_id": revision,
            "source_revision": revision,
            "kind": "taf",
            "issued_at": issued,
            "available_at": issued + 2 * minute,
            "valid_start": start,
            "valid_end": 180 * minute,
            "content": {"periods": [{"valid_start": start, "valid_end": 180 * minute, "operator": "BASE", "visibility_m": vis}]},
        }

    products = [product("r1", 0, 0, 8000), product("r2", 5 * minute, 30 * minute, 4000)]
    monkeypatch.setattr(
        builder,
        "_load_products",
        lambda root, station, month, run: copy.deepcopy(products) if (station, month) == ("KSFO", "202501") else [],
    )
    roster = build_roster(tmp_path, limit=24, run_id=RUN_ID)
    assert roster["episodes"] == [] and roster["episode_count"] == 0 and roster["checkpoint_count"] == 0
    (excluded,) = roster["excluded_episodes"]
    assert excluded["episode_id"] == "v18-dev-KSFO-1970-01-01"
    assert excluded["target_start"] == 30 * minute
    assert [(row["checkpoint_id"], row["as_of"], row["reason"]) for row in excluded["excluded_checkpoints"]] == [
        ("T-60", -30 * minute, "cutoff precedes the Unix epoch (negative utc_us)"),
        ("T-40", -10 * minute, "cutoff precedes the Unix epoch (negative utc_us)"),
    ]
