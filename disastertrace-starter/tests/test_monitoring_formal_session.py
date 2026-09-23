import hashlib

import pytest
from test_monitoring_typed_session import typed_fixture


def setup():
    from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, experiment_spec
    from disastertrace.monitoring_v1.execution import bind_execution
    from disastertrace.monitoring_v1.formal_session import required_source_files
    from disastertrace.monitoring_v1.source_execution import bind_source

    data, bank, config = typed_fixture()
    config.update(execution_mode="production_bound_v1", pending_timing_policy="lifecycle_wall_v1",
                  admission_semantics="measurement.v3", formal_resolution_policy="h15_routine_archive.v1")
    config = bind_source(bind_execution(config, None), None)
    spec = experiment_spec(data, bank, config)
    comparison = ComparisonContract(spec["invariants"], {k: [v] for k, v in spec["interventions"].items()})
    files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in required_source_files()}
    return data, bank, config, comparison, files


def test_formal_program_session_enforces_contract_and_records_stop(tmp_path):
    from disastertrace.monitoring_v1.formal_session import FormalSession

    data, bank, config, comparison, files = setup()
    run = FormalSession(data, bank, config, comparison=comparison, bound_files=files, directory=tmp_path / "formal")
    report = run.finish(max_steps=20)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["event_replay"]["payload"]["contract"]["semantics_version"] == "measurement.v3"
    assert (tmp_path / "formal/STOP.json").exists()
    assert run.contract["outcomes_visible_to_policy"] is False


@pytest.mark.parametrize("key", ["execution_mode", "pending_timing_policy", "formal_resolution_policy", "admission_semantics"])
def test_formal_entry_rejects_omitted_mandatory_configuration(tmp_path, key):
    from disastertrace.monitoring_v1.formal_session import FormalSession

    data, bank, config, comparison, files = setup()
    del config[key]
    with pytest.raises(ValueError):
        FormalSession(data, bank, config, comparison=comparison, bound_files=files, directory=tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_formal_entry_rejects_missing_source_manifest_before_execution(tmp_path):
    from disastertrace.monitoring_v1.formal_session import FormalSession

    data, bank, config, comparison, files = setup()
    files.pop(next(iter(files)))
    with pytest.raises(ValueError, match="source"):
        FormalSession(data, bank, config, comparison=comparison, bound_files=files, directory=tmp_path / "bad")


def test_formal_entry_rejects_future_result_even_nested(tmp_path):
    from disastertrace.monitoring_v1.formal_session import FormalSession

    data, bank, config, comparison, files = setup()
    data["extra"] = {"outcomes": [{"value": 1}]}
    with pytest.raises(ValueError, match="outcome"):
        FormalSession(data, bank, config, comparison=comparison, bound_files=files, directory=tmp_path / "bad")
