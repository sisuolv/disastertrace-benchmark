"""Production transport detects changed configuration and frozen artifacts."""

import hashlib

import pytest

from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.production import ProductionSpoolBackend


def fixture(tmp_path):
    artifact = tmp_path / "reference.json"
    artifact.write_text('{"reference":"frozen evaluator-only test data"}')
    contract = {
        k: {"version": "test"}
        for k in ("model", "weights", "tokenizer", "adapter", "generation", "runtime")
    }
    backend = ProductionSpoolBackend(
        tmp_path,
        contract,
        run_id="test-production",
        bound_files={str(artifact): hashlib.sha256(artifact.read_bytes()).hexdigest()},
    )
    config = {"execution_mode": "production_bound_v1", "pending_timing_policy": "lifecycle_wall_v1"}
    return backend, config, artifact


@pytest.mark.parametrize("changed", ["model", "directory", "run_id", "attribute", "artifact"])
def test_bound_production_rejects_changes_before_new_dispatch(tmp_path, changed):
    backend, config, artifact = fixture(tmp_path)
    config = bind_execution(config, backend)
    if changed == "model":
        backend.execution_contract["model"] = "changed"
    elif changed == "directory":
        backend.directory = tmp_path / "elsewhere"
    elif changed == "run_id":
        backend.run_id = "different"
    elif changed == "attribute":
        backend.hidden_state = 1
    else:
        artifact.write_text("changed reference")
    with pytest.raises(ValueError, match="production"):
        bind_execution(config, backend)
    assert not list(tmp_path.glob("*.request.json"))


def test_declared_export_isolated_and_original_config_unmodified(tmp_path):
    backend, config, _ = fixture(tmp_path)
    bound = bind_execution(config, backend)
    bound["execution_contract"]["declared"]["model"] = "changed copy"
    assert backend.execution_contract["model"] == {"version": "test"}
    assert "execution_contract" not in config


def test_production_cannot_use_receipt_only_timing(tmp_path):
    backend, config, _ = fixture(tmp_path)
    config["pending_timing_policy"] = "backend_receipt_v1"
    with pytest.raises(ValueError, match="lifecycle"):
        bind_execution(config, backend)


def test_repeated_pending_checkpoints_keep_original_worker_release(tmp_path):
    from test_monitoring_typed_session import typed_fixture

    from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator

    backend, mode, _ = fixture(tmp_path)
    data, bank, config = typed_fixture(forecast_call_cap=1, model_call_budget=1)
    config.update(mode)
    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step()
    session.persist(tmp_path / "checkpoint0.json")
    ready = next(tmp_path.glob("*.ready.json"))
    original = ready.read_bytes()
    session.step()
    session.persist(tmp_path / "checkpoint1.json")
    assert ready.read_bytes() == original
    assert (tmp_path / "checkpoint0.json").read_bytes() != (
        tmp_path / "checkpoint1.json"
    ).read_bytes()
