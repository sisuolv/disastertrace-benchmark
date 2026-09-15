"""The diagnostic changes only exact time encoding, including boundary cases."""

import json

import pytest

from disastertrace.monitoring_fixed_v1.time_representation import (
    decode_time,
    encode_time,
    transform,
)


@pytest.mark.parametrize("value", [0, -1, 1709251199999999, 1709251200000000, 2147483647000001])
def test_exact_time_roundtrip(value):
    assert decode_time(encode_time(value)) == value


def test_raw_native_text_and_non_time_numbers_are_unchanged():
    row = {
        "as_of": 1709251199999999,
        "target": {
            "physical_start": 1709251200000000,
            "physical_end": 1709254800000000,
            "threshold": 5000,
            "release_event_at": None,
        },
        "products": [{"issued_at": 1709250000000000, "raw": "TAF KAAA 292359Z 0100/0200 9999"}],
    }
    encoded = transform(row)
    assert transform(encoded, decode=True) == row
    assert encoded["products"][0]["raw"] == row["products"][0]["raw"]
    assert encoded["target"]["threshold"] == 5000
    assert json.loads(json.dumps(encoded)) == encoded
