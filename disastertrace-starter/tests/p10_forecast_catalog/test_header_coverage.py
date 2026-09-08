"""Regressions for actual abbreviated potential-cyclone headers, without changing old Gold."""

from pathlib import Path

import pytest

from disastertrace.forecast_catalog import parser_a
from disastertrace.forecast_source import parser_a as legacy_a
from disastertrace.forecast_source import parser_b
from disastertrace.forecast_task.common import read

PROJECT = Path(__file__).resolve().parents[2]
SOURCES = PROJECT / "artifacts/p10_source_catalog_v1/sources"


@pytest.mark.parametrize("storm,number", [("al092020", n) for n in range(1, 7)] + [("al092024", n) for n in range(1, 5)])
def test_real_nhc_abbreviated_potential_cyclone_headers_match_independent_parser(storm, number):
    raw = (SOURCES / f"{storm}-fstadv-{number:03d}" / "raw.html").read_bytes()
    assert b"POTENTIAL TROP CYCLONE CENTER LOCATED" in raw
    with pytest.raises(ValueError, match="unique issue"):
        legacy_a.parse(raw)
    assert parser_a.parse(raw) == parser_b.parse(raw)


def test_all_previously_admitted_natural_products_remain_byte_equivalent():
    checked = 0
    for result_path in SOURCES.glob("*/result.json"):
        result = read(result_path)
        if result["status"] == "admitted":
            raw = (result_path.parent / "raw.html").read_bytes()
            assert parser_a.parse(raw) == legacy_a.parse(raw) == parser_b.parse(raw)
            checked += 1
    assert checked == 26


@pytest.mark.parametrize("replacement", [b"POTENTIAL UNKNOWN CYCLONE CENTER LOCATED", b"REPEAT...CENTER LOCATED"])
def test_unrecognized_or_repeat_only_center_is_not_promoted_to_primary_header(replacement):
    raw = (SOURCES / "al092024-fstadv-004/raw.html").read_bytes()
    raw = raw.replace(b"POTENTIAL TROP CYCLONE CENTER LOCATED", replacement)
    with pytest.raises(ValueError, match="unique issue"):
        parser_a.parse(raw)


def test_duplicate_primary_center_still_fails_closed():
    raw = (SOURCES / "al092024-fstadv-004/raw.html").read_bytes()
    line = next(line for line in raw.splitlines() if line.startswith(b"POTENTIAL TROP CYCLONE CENTER LOCATED"))
    with pytest.raises(ValueError, match="unique issue"):
        parser_a.parse(raw.replace(line, line + b"\n" + line))
