"""Exercise publication handoff comparisons and audit output isolation."""

import subprocess
import types

import pytest
from accelerate_f_audit import redirected_audit
from integrate_parallel_audit import compare_prefix, stop_owned_process


def test_serial_prefix_requires_identical_bytes(tmp_path):
    serial, parallel = tmp_path / "serial", tmp_path / "parallel"
    serial.mkdir()
    parallel.mkdir()
    name = "case__CANONICAL_SCORES.json"
    (serial / name).write_text('{"result":1}')
    (parallel / name).write_text('{"result":1}')
    assert len(compare_prefix(serial, parallel)) == 1
    (parallel / name).write_text('{"result":2}')
    with pytest.raises(ValueError, match="mismatch"):
        compare_prefix(serial, parallel)
    assert (serial / name).read_text() == '{"result":1}'


def test_only_audit_output_changes(tmp_path):
    source = tmp_path / "reference.py"
    source.write_text('''def audit_f(pilot="api_pilot_01"):
    out = ROOT / "original"
    out.mkdir(exist_ok=False)
    result = score_admitted(pilot)
    (out / "result.txt").write_text(result)
''')
    module = types.SimpleNamespace(__file__=str(source), ROOT=tmp_path)
    output = tmp_path / "replacement"
    redirected_audit(module, lambda pilot: "validated:" + pilot, output)("existing")
    assert (output / "result.txt").read_text() == "validated:existing"
    assert not (tmp_path / "original").exists()


def test_process_identity_guard_and_exit():
    process = subprocess.Popen(["sleep", "60"])
    try:
        with pytest.raises(ValueError, match="identity"):
            stop_owned_process(process.pid, "wrong-audit-identity")
        assert process.poll() is None
        receipt = stop_owned_process(process.pid, "sleep 60")
        assert receipt["stopped_after_parallel_validation"]
        assert process.wait(timeout=2) != 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=2)
