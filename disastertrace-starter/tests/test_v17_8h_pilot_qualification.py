import hashlib
from datetime import datetime, timezone

import pytest

from disastertrace.revision_v1.pilot_v17.qualification import (
    HOUR, allowed_month, day_relative, iso, legal_target, micros, parse_body,
    parse_frame, qualify_candidate, read_body, reference_state,
)


def stamp(day=10, hour=12, minute=0):
    return micros(datetime(2023, 1, day, hour, minute, tzinfo=timezone.utc))


def bulletin(issue="101100", valid="1012/1112", kind="", station="KSFO", seq="123"):
    return (f"\x01\n{seq}\nFTUS46 KMTR {issue}\nTAFSFO\n"
            f"TAF {kind} {station} {issue}Z {valid} 27010KT P6SM SCT020\n\x03").encode()


def row_for(data):
    return {"station": "KSFO", "year_month": "2023-01",
            "canonical_body_path": "/synthetic/KSFO_202301.body",
            "raw_text_sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def product(issue="101100", valid="1012/1112", kind=""):
    data = bulletin(issue, valid, kind)
    return parse_frame(data, row_for(data))


def test_native_issue_validity_and_lag():
    p = product("101105", kind="AMD")
    assert p["issued_at_us"] == stamp(hour=11, minute=5)
    assert p["available_at_us"] == stamp(hour=11, minute=7)
    assert p["valid_start_us"] == stamp()
    assert p["valid_end_us"] == stamp(day=11)
    assert p["kind"] == "AMD"


def test_frame_offsets_are_exact_bytes():
    first, second = bulletin("100900"), bulletin("101110", kind="COR")
    data = b"\n  \n" + first + b"\n" + second
    products, errors = parse_body(data, row_for(data))
    assert not errors and len(products) == 2
    assert data[products[0]["byte_start"]:products[0]["byte_end"]] == first
    assert data[products[1]["byte_start"]:products[1]["byte_end"]] == second
    assert products[1]["kind"] == "COR"


def test_sequence_number_does_not_create_new_source():
    a, b = bulletin(seq="123"), bulletin(seq="456")
    assert parse_frame(a, row_for(a))["source_id"] == parse_frame(b, row_for(b))["source_id"]


def test_no_future_leak_and_arrival_after_checkpoint():
    old = product("100900")
    new = product("101110", kind="AMD")
    assert reference_state([old, new], stamp(hour=11), stamp(), stamp()+HOUR)["active_source_ids"] == [old["source_id"]]
    assert reference_state([old, new], stamp(hour=11, minute=20), stamp(), stamp()+HOUR)["active_source_ids"] == [new["source_id"]]


def test_same_issue_conflict_fails_closed():
    a, b = product(), product(kind="COR")
    with pytest.raises(ValueError, match="unresolved authority"):
        reference_state([a, b], stamp(), stamp(), stamp()+HOUR)


def test_partial_target_fails_closed():
    a = product(valid="1012/1013")
    with pytest.raises(ValueError, match="partial-target"):
        reference_state([a], stamp(), stamp(), stamp()+2*HOUR)


def test_older_and_duplicate_inputs_do_not_replace_newer():
    old, new = product("100900"), product("101110", kind="AMD")
    expected = reference_state([old, new], stamp(), stamp(), stamp()+HOUR)
    assert reference_state([new, old, old], stamp(), stamp(), stamp()+HOUR) == expected


def test_no_applicable_is_not_a_negative_label():
    with pytest.raises(ValueError, match="no applicable"):
        reference_state([product()], stamp(), stamp(day=12), stamp(day=12)+HOUR)


@pytest.mark.parametrize("ym", ["2025-02", "2026-01", "2023-13", "2023-00", "202502"])
def test_rejected_months(ym):
    assert not allowed_month(ym)


def test_target_month_and_prefix_margin():
    assert legal_target(stamp())
    assert not legal_target(stamp(day=1))
    assert not legal_target(micros(datetime(2025, 2, 1, tzinfo=timezone.utc)))


def test_calendar_rollover_and_hour_24():
    issued = datetime(2023, 1, 31, 23, tzinfo=timezone.utc)
    assert day_relative("0100", issued) == datetime(2023, 2, 1, tzinfo=timezone.utc)
    assert day_relative("3124", issued) == datetime(2023, 2, 1, tzinfo=timezone.utc)


def test_bad_station_and_cancellation_rejected():
    data = bulletin(station="KDEN")
    with pytest.raises(ValueError, match="station mismatch"):
        parse_frame(data, row_for(data))
    data = bulletin().replace(b"SCT020", b"CNL")
    with pytest.raises(ValueError, match="cancellation"):
        parse_frame(data, row_for(data))


def test_integrity_mismatch_prevents_use(tmp_path):
    data = bulletin()
    p = tmp_path / "KSFO_202301.body"
    p.write_bytes(data)
    row = {**row_for(data), "canonical_body_path": str(p)}
    assert read_body(row) == data
    p.write_bytes(data + b"x")
    with pytest.raises(ValueError, match="identity changed"):
        read_body(row)


def test_qualification_routine_arrival_is_a_state_change():
    history = product("091000", valid="0910/1016")
    old = product("100500", valid="1006/1112")
    new = product("101110")
    episode, refs = qualify_candidate("KSFO", stamp(), [history, old, new], [])
    assert episode["category"] == "STATE_CHANGE"
    assert episode["change_subtype"] == "ROUTINE"
    assert refs[0]["active_source_ids"] == [old["source_id"]]
    assert refs[1]["active_source_ids"] == [new["source_id"]]


def test_no_arrival_is_distinct_from_unsupported_history():
    history = product("091000", valid="0910/1016")
    old = product("100500", valid="1006/1112")
    episode, refs = qualify_candidate("KSFO", stamp(), [history, old], [])
    assert episode["category"] == "NO_ARRIVAL"
    assert refs[0] == refs[1] == refs[2]
    with pytest.raises(ValueError, match="insufficient"):
        qualify_candidate("KSFO", stamp(), [old], [])


def test_irrelevant_arrival_preserves_applicable_state():
    history = product("091000", valid="0910/1016")
    old = product("100500", valid="1006/1112")
    future = product("101110", valid="1018/1118")
    episode, refs = qualify_candidate("KSFO", stamp(), [history, old, future], [])
    assert episode["category"] == "ARRIVAL_STATE_STABLE"
    assert refs[0] == refs[1] == refs[2]


def test_rejected_frame_in_history_is_not_silently_dropped():
    history = product("091000", valid="0910/1016")
    old = product("100500", valid="1006/1112")
    with pytest.raises(ValueError, match="unparsed"):
        qualify_candidate("KSFO", stamp(), [history, old], [{"issued_at_us": stamp(hour=10)}])


def test_incomplete_afos_tail_is_reported():
    data = bulletin() + b"\x01\n999\nFTUS46 KMTR 101120\nTAFSFO\nTAF KSFO 101120Z"
    products, errors = parse_body(data, row_for(data))
    assert len(products) == 1
    assert len(errors) == 1
    assert errors[0]["reason"] == "unframed or incomplete AFOS fragment"
    assert errors[0]["byte_end"] == len(data)


def test_nested_afos_start_is_not_silently_accepted():
    data = b"\x01\ntruncated prior message\n" + bulletin()
    products, errors = parse_body(data, row_for(data))
    assert not products
    assert len(errors) == 1
    assert errors[0]["reason"] == "nested AFOS start"


def test_nonwhitespace_preamble_is_retained_as_unknown_input():
    data = b"unexplained text\n" + bulletin()
    products, errors = parse_body(data, row_for(data))
    assert len(products) == 1 and len(errors) == 1
    assert errors[0]["byte_start"] == 0
    assert errors[0]["reason"] == "unframed or incomplete AFOS fragment"
