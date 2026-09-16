"""Exact path/value text for shape-valid previous answers and invalid/missing markers."""

from disastertrace.forecast_task.common import canonical, strict_json
from disastertrace.forecast_task.contract import FIELDS, parse_answer

PREFIX = "PREVIOUS_ANSWER_PATH_VALUES_V1"
LEGEND = (
    "The previous-answer carrier below is either JSON or path/value text. "
    "In path/value text each line is a field path, ' = ', and one JSON literal. "
    "The literal object marker declares a nested object. These are two encodings "
    "of the same fallible previous answer, never additional source authority."
)


def validate(carrier):
    if carrier is None:
        return
    if not isinstance(carrier, dict) or set(carrier) != {"checkpoint_id", "kind", "answer"}:
        raise ValueError("exact native structured-state carrier required")
    if type(carrier["checkpoint_id"]) is not str or carrier["kind"] not in (
        "answer",
        "invalid",
        "missing",
    ):
        raise ValueError("invalid carrier identity/kind")
    if carrier["kind"] == "answer":
        parse_answer(canonical(carrier["answer"]))
    elif carrier["answer"] is not None:
        raise ValueError("invalid/missing markers cannot hide an answer")


def to_text(carrier):
    validate(carrier)
    rows = [PREFIX]
    if carrier is None:
        return PREFIX + "\ncarrier = null"
    rows.extend(
        (
            "checkpoint_id = " + canonical(carrier["checkpoint_id"]),
            "kind = " + canonical(carrier["kind"]),
        )
    )
    answer = carrier["answer"]
    if answer is None:
        rows.append("answer = null")
    else:
        rows.append("answer = object")
        for key in ("storm_id", "valid_at", "measurement_kind", "status"):
            rows.append("answer." + key + " = " + canonical(answer[key]))
        for field in FIELDS:
            for key in ("value", "unit"):
                rows.append("answer." + field + "." + key + " = " + canonical(answer[field][key]))
        citation = answer["citation"]
        rows.append("answer.citation = " + ("null" if citation is None else "object"))
        if citation is not None:
            for key in ("source_id", "forecast_line", "wind_line"):
                rows.append("answer.citation." + key + " = " + canonical(citation[key]))
    return "\n".join(rows)


def from_text(text):
    lines = text.split("\n")
    if lines[0] != PREFIX:
        raise ValueError("unknown carrier text encoding")
    values = {}
    for line in lines[1:]:
        key, separator, raw = line.partition(" = ")
        if not separator or key in values:
            raise ValueError("missing separator or duplicate carrier field")
        values[key] = raw
    if values == {"carrier": "null"}:
        return None
    try:
        carrier = {
            "checkpoint_id": strict_json(values["checkpoint_id"]),
            "kind": strict_json(values["kind"]),
            "answer": None,
        }
        if values["answer"] == "object":
            answer = {
                key: strict_json(values["answer." + key])
                for key in ("storm_id", "valid_at", "measurement_kind", "status")
            }
            answer.update(
                {
                    field: {
                        key: strict_json(values["answer." + field + "." + key])
                        for key in ("value", "unit")
                    }
                    for field in FIELDS
                }
            )
            citation = values["answer.citation"]
            if citation == "object":
                answer["citation"] = {
                    key: strict_json(values["answer.citation." + key])
                    for key in ("source_id", "forecast_line", "wind_line")
                }
            elif citation == "null":
                answer["citation"] = None
            else:
                raise ValueError("invalid citation marker")
            carrier["answer"] = answer
        elif values["answer"] != "null":
            raise ValueError("invalid answer marker")
    except KeyError as exc:
        raise ValueError("missing carrier field") from exc
    validate(carrier)
    if to_text(carrier) != text:
        raise ValueError("extra, reordered or noncanonical text fields")
    return carrier


def render(carrier, encoding):
    validate(carrier)
    if encoding == "json":
        return canonical(carrier)
    if encoding == "text":
        encoded = to_text(carrier)
        if canonical(from_text(encoded)) != canonical(carrier):
            raise ValueError("carrier representation lost information")
        return encoded
    raise ValueError("unknown carrier representation")
