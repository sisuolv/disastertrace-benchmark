"""J1a synthetic-only contract tests; no real weather file access."""

from datetime import datetime, timezone

import pytest

from disastertrace.monitoring_v1.providers.versions import latest_issuance
from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream
from disastertrace.revision_v1.v23_contracts import (
    LEAD_LABELS,
    METAR_AVAILABLE_DELAY_S,
    checkpoint_rows,
    metar_available_at,
    month_hour_starts,
    routine_window_for_observation,
    target_contract,
    validate_exact_read_path,
    visible_metar,
)


def _us(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000)


def test_calendar_has_frozen_5952_targets_and_four_checkpoints():
    targets = month_hour_starts()
    assert len(targets) == 5952
    assert len({row["target_id"] for row in targets}) == 5952
    assert sum(len(checkpoint_rows(row)) for row in targets) == 23808
    assert [row["checkpoint_id"] for row in checkpoint_rows(targets[0])] == list(LEAD_LABELS)


def test_metar_available_at_cutoff_boundary_is_closed():
    valid = _us(datetime(2025, 1, 1, 10, 50, tzinfo=timezone.utc))
    cutoff = valid + METAR_AVAILABLE_DELAY_S * 1_000_000
    assert metar_available_at(valid) == cutoff
    assert visible_metar(valid, cutoff)
    assert not visible_metar(valid, cutoff - 1)


def test_actual_1151_timestamp_belongs_to_1100_window():
    obs = _us(datetime(2025, 1, 1, 11, 51, tzinfo=timezone.utc))
    start, end = routine_window_for_observation(obs)
    assert datetime.fromtimestamp(start / 1_000_000, tz=timezone.utc).hour == 11
    assert end - start == 3_600_000_000


def test_contract_hash_binds_event_and_availability_rules():
    target = month_hour_starts(stations=("KSFO",), months=("2025-01",))[0]
    contract = target_contract(target)
    assert len(contract.contract_hash) == 64
    assert contract.to_dict()["report_policy"] == "iem_routine_unique_hour.v1"
    assert contract.to_dict()["available_at_delay_s"] == 600


def test_revision_v1_is_the_only_taf_parser_and_receipt_order_is_preserved():
    stream = """\x01
001
FTUS46 KMTR 011200
TAFSFO
TAF
KSFO 011200Z 0112/0212 25010KT P6SM SCT020=
\x03\x01
002
FTUS46 KMTR 011100
TAFSFO
TAF
KSFO 011100Z 0111/0211 25010KT P6SM SCT020=
\x03"""
    packages, skipped = compile_afos_taf_stream(stream, station="KSFO", reference_month="2025-01")
    assert not skipped
    assert len(packages) == 2
    assert all(package["receipt_stream"] == "KSFO:2025-01" for package in packages)
    assert packages[0]["receipt_seq"] > packages[1]["receipt_seq"]
    latest, rest = latest_issuance([
        {"source_id": "a", "issued_at": 1, "receipt_seq": 1, "receipt_stream": "x"},
        {"source_id": "b", "issued_at": 1, "receipt_seq": 2, "receipt_stream": "x"},
    ])
    assert latest[0]["source_id"] == "b"
    assert {row["source_id"] for row in rest} == {"a"}


def test_exact_read_guard_rejects_unlisted_and_symlink_paths(tmp_path):
    allowed = tmp_path / "allowed.body"
    allowed.write_text("synthetic")
    assert validate_exact_read_path(allowed, [str(allowed)]) == allowed.resolve()
    with pytest.raises(PermissionError):
        validate_exact_read_path(tmp_path / "other.body", [str(allowed)])
    link = tmp_path / "link.body"
    link.symlink_to(allowed)
    with pytest.raises(PermissionError):
        validate_exact_read_path(link, [str(allowed)])
