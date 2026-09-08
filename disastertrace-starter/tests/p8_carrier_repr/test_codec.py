"""Round-trip guarantees, including semantic mistakes and explicit failure markers."""

from copy import deepcopy

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from disastertrace.carrier_repr.codec import from_text, render, to_text
from disastertrace.forecast_task.common import canonical
from disastertrace.forecast_task.contract import empty_answer


def carrier():
    return {
        "checkpoint_id": "checkpoint-1",
        "kind": "answer",
        "answer": empty_answer({"storm_id": "AL062024", "valid_at": "2024-09-11T06:00:00+00:00"}),
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        {"checkpoint_id": "c", "kind": "missing", "answer": None},
        {"checkpoint_id": "c", "kind": "invalid", "answer": None},
    ],
)
def test_missing_and_invalid_markers_remain_explicit(value):
    assert from_text(to_text(value)) == value
    assert render(value, "json") == canonical(value)


@pytest.mark.parametrize("number", [0, -0.0, 65, 65.0, -90.25, 1.5e25, 10**100])
def test_values_and_numeric_types_are_exact(number):
    value = carrier()
    value["answer"]["latitude"]["value"] = number
    encoded = to_text(value)
    assert canonical(from_text(encoded)) == canonical(value)


@settings(max_examples=100)
@given(st.text(max_size=100), st.floats(allow_nan=False, allow_infinity=False))
def test_arbitrary_strings_and_finite_numbers_roundtrip(text, number):
    value = carrier()
    value["answer"]["storm_id"] = text
    value["answer"]["max_sustained_wind"] = {"value": number, "unit": text}
    value["answer"]["citation"] = {"source_id": text, "forecast_line": 999999, "wind_line": None}
    assert canonical(from_text(render(value, "text"))) == canonical(value)


def test_semantic_errors_are_not_corrected_or_dropped():
    value = carrier()
    value["answer"].update(
        storm_id="wrong-storm",
        valid_at="not-a-time",
        measurement_kind="pressure",
        status="DISSIPATED",
        citation={"source_id": "superseded", "forecast_line": 777, "wind_line": 12},
    )
    value["answer"]["longitude"] = {"value": 181, "unit": "wrong-unit"}
    assert canonical(from_text(to_text(value))) == canonical(value)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "extra", "reorder"])
def test_ambiguous_or_incomplete_text_is_rejected(mutation):
    lines = to_text(carrier()).split("\n")
    if mutation == "duplicate":
        lines.append(lines[1])
    elif mutation == "missing":
        lines.pop(2)
    elif mutation == "extra":
        lines.append('unbound_hint = "correct"')
    else:
        lines[1], lines[2] = lines[2], lines[1]
    with pytest.raises(ValueError):
        from_text("\n".join(lines))


def test_invalid_kind_cannot_contain_a_hidden_answer():
    value = deepcopy(carrier())
    value["kind"] = "invalid"
    with pytest.raises(ValueError):
        to_text(value)
