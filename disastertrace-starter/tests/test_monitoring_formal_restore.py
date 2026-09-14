"""Formal recovery must retain the original source, comparison, and stop boundary."""

import json

import pytest
from test_monitoring_formal_session import setup

from disastertrace.monitoring_v1.formal_session import FormalSession
from disastertrace.monitoring_v1.spool_backend import digest
from disastertrace.monitoring_v1.targets import canonical_hash


def initial(tmp_path):
    data, bank, config, comparison, files = setup()
    run = FormalSession(
        data, bank, config, comparison=comparison, bound_files=files, directory=tmp_path / "run"
    )
    run.step()
    checkpoint = tmp_path / "checkpoint.json"
    run.persist(checkpoint)
    return run, data, bank, checkpoint


def test_formal_serial_restore_keeps_production_qualification_and_original_contract(tmp_path):
    run, data, bank, path = initial(tmp_path)
    restored = FormalSession.restore(path, data, bank, directory=run.directory)
    assert restored.snapshot() == run.snapshot()
    result = restored.finish(max_steps=20)
    assert len(result["snapshots"]) == len(data["opportunities"])
    assert restored.contract == run.contract


def test_stopped_formal_run_cannot_be_reopened_by_a_valid_checkpoint(tmp_path):
    run, data, bank, path = initial(tmp_path)
    run.stop("predeclared_stop")
    with pytest.raises(ValueError, match="stopped"):
        FormalSession.restore(path, data, bank, directory=run.directory)


def test_formal_recovery_rejects_changed_binding_and_cross_run_checkpoint(tmp_path):
    run, data, bank, path = initial(tmp_path)
    marker = path.with_name(path.name + ".formal.json")
    value = json.loads(marker.read_text())
    value["formal_directory"] = str(tmp_path / "other")
    marker.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="binding"):
        FormalSession.restore(path, data, bank, directory=run.directory)


def test_an_ordinary_unbound_coordinator_checkpoint_cannot_bypass_formal_restore(tmp_path):
    run, data, bank, path = initial(tmp_path)
    unbound = tmp_path / "ordinary.json"
    unbound.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="binding"):
        FormalSession.restore(unbound, data, bank, directory=run.directory)


@pytest.mark.parametrize(
    "key",
    [
        "execution_mode",
        "pending_timing_policy",
        "admission_semantics",
        "session_runtime",
        "formal_resolution_policy",
    ],
)
def test_restore_rechecks_formal_requirements_even_with_self_consistent_binding(tmp_path, key):
    run, data, bank, path = initial(tmp_path)
    checkpoint = json.loads(path.read_text())
    checkpoint["payload"]["config"][key] = "not_formal"
    checkpoint["sha256"] = canonical_hash(checkpoint["payload"])
    path.write_text(json.dumps(checkpoint))
    marker = path.with_name(path.name + ".formal.json")
    binding = json.loads(marker.read_text())
    binding.update(
        checkpoint_file_sha256=digest(path), checkpoint_payload_sha256=checkpoint["sha256"]
    )
    marker.write_text(json.dumps(binding))
    with pytest.raises(ValueError, match="Formal session requires"):
        FormalSession.restore(path, data, bank, directory=run.directory)


def test_finish_cannot_overwrite_stop_after_successful_completion(tmp_path):
    run, _, _, _ = initial(tmp_path)
    run.finish(max_steps=20)
    original = (run.directory / "STOP.json").read_bytes()
    with pytest.raises(ValueError, match="already stopped"):
        run.finish(max_steps=20)
    assert (run.directory / "STOP.json").read_bytes() == original
