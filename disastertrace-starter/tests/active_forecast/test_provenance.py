import hashlib
import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from disastertrace.active_forecast.legacy import FrozenPilotImporter
from disastertrace.active_forecast.provenance import SourceReader, load_json, write_json
from disastertrace.active_forecast.schema import SourceLocator


def bound(path, **kwargs):
    return SourceLocator(
        path=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        role="source_bytes",
        **kwargs,
    )


def test_locators_resolve_escaped_keys_and_exact_decimals(tmp_path):
    path = tmp_path / "source.json"
    path.write_text('{"a/b":{"~field":[0.1,0.3]}}')
    loc = bound(path, kind="json_pointer", pointer="/a~1b/~0field/1")
    assert SourceReader(tmp_path).resolve(loc) == Decimal("0.3")
    assert load_json(path)["a/b"]["~field"][0] == Decimal("0.1")


def test_changed_byte_invalidates_source_binding(tmp_path):
    path = tmp_path / "source.json"
    path.write_text("[1,2]")
    loc = bound(path, kind="json_pointer", pointer="/0")
    path.write_text("[9,2]")
    with pytest.raises(ValueError, match="hash mismatch"):
        SourceReader(tmp_path).resolve(loc)


def test_raw_uint8_frame_tile_locator(tmp_path):
    path = tmp_path / "event.bin"
    path.write_bytes(bytes(range(24)))  # C-order [2, 3, 4], frame is the final axis.
    loc = bound(path, kind="uint8_tile", array_shape=[2, 3, 4], frame=2, box=[0, 2, 1, 3])
    assert SourceReader(tmp_path).resolve(loc) == bytes([6, 10, 18, 22])
    path.write_bytes(bytes(range(23)))
    with pytest.raises(ValueError, match="shape"):
        SourceReader(tmp_path).resolve(
            bound(path, kind="uint8_tile", array_shape=[2, 3, 4], frame=2, box=[0, 2, 1, 3])
        )


@pytest.mark.parametrize("pointer", ["/absent", "/items/01", "/items/-", "/items/9", "/bad~2key"])
def test_nonexistent_or_ambiguous_pointer_rejected(tmp_path, pointer):
    path = tmp_path / "source.json"
    path.write_text(json.dumps({"items": [1, 2]}))
    with pytest.raises(ValueError):
        SourceReader(tmp_path).resolve(bound(path, kind="json_pointer", pointer=pointer))


def test_byte_range_and_escape_checks(tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes(b"012345")
    assert SourceReader(tmp_path).resolve(bound(path, kind="byte_range", start=2, end=4)) == b"23"
    with pytest.raises(ValueError):
        SourceReader(tmp_path).resolve(bound(path, kind="byte_range", start=2, end=9))
    with pytest.raises(ValidationError):
        SourceLocator(kind="whole_file", path="../secret", sha256="a" * 64, role="source_bytes")
    outside = tmp_path.parent / (tmp_path.name + "-outside.json")
    outside.write_text("[]")
    link = tmp_path / "linked.json"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="outside"):
        SourceReader(tmp_path).resolve(bound(link, kind="whole_file"))


@pytest.mark.parametrize("text", ['{"x": 1, "x": 2}', "[NaN]", "[Infinity]"])
def test_json_ambiguity_rejected(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        load_json(path)


def test_frozen_comparison_keeps_the_prototypes_numeric_semantics(tmp_path):
    path = tmp_path / "frozen.json"
    original = {"decision": "unknown", "lower": 1 / 100, "upper": 1 - 2 / 3}
    path.write_text(json.dumps(original))
    importer = FrozenPilotImporter.__new__(FrozenPilotImporter)
    importer.bundle = tmp_path
    importer.reader = SourceReader(tmp_path)
    replay_input = importer.read_prototype_json("frozen.json")
    assert replay_input == original
    assert importer.read("frozen.json")["lower"] == Decimal("0.01")
    assert importer.read("frozen.json") != original
    write_json(tmp_path / "report.json", {"expected": replay_input, "actual": original})
    assert json.loads((tmp_path / "report.json").read_text())["expected"] == original
    importer.reader.verify_unchanged()


def test_encoding_failure_does_not_leave_a_partial_json_report(tmp_path):
    path = tmp_path / "report.json"
    with pytest.raises(TypeError):
        write_json(path, {"unserializable": Decimal("0.1")})
    assert not path.exists()
