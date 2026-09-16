"""A new formal child inherits a verified prefix without reopening its parent."""

import copy

import pytest
from test_monitoring_formal_session import setup

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.formal_session import FormalSession, _verify_run_reference
from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def prepared(tmp_path):
    data, bank, config, comparison, files = setup()
    parent = FormalSession(data, bank, config, comparison=comparison, bound_files=files, directory=tmp_path / "parent")
    parent.step()
    path = tmp_path / "checkpoint.json"
    cp = parent.persist(path)
    parent.finish(max_steps=20)
    parent.export_journal(parent.directory / "admission.jsonl")
    cutoff = sorted({o["cutoff"] for o in data["opportunities"]})[cp["payload"]["next_tick"]]
    oid = next(o["opportunity_id"] for o in data["opportunities"] if o["cutoff"] == cutoff)
    plan = freeze_residual_plan(data, cp, oid, "no_further_paid_query")
    child_comparison = ComparisonContract(comparison.invariants, {**comparison.allowed_interventions, "residual_query_plan": [None, plan]})
    return data, bank, files, parent, path, plan, child_comparison


def test_formal_fork_keeps_stopped_parent_and_scores_registered_prefix(tmp_path):
    data, bank, files, parent, path, plan, comparison = prepared(tmp_path)
    before = digest(parent.directory / "STOP.json")
    child = FormalSession.fork(path, data, bank, parent_directory=parent.directory,
        comparison=comparison, bound_files=files, directory=tmp_path / "child",
        controls={"residual_query_plan": plan})
    child.finish(max_steps=20)
    journal = child.export_journal(child.directory / "admission.jsonl")
    engine = AdmissionEngine.from_journal(journal)
    assert _verify_run_reference(journal, child.directory, engine, comparison) == "h15_routine_archive.v1"
    comparison.validate(**engine.contract["experiment"])
    comparison.validate(engine.contract["experiment"]["invariants"], engine.active_interventions)
    assert digest(parent.directory / "STOP.json") == before
    assert len(child.report["snapshots"]) == len(parent.report["snapshots"])
    assert child.report["source_receipts"] == read(path)["payload"]["controller"]["source_receipts"]
    with pytest.raises(ValueError, match="stopped"):
        FormalSession.restore(path, data, bank, directory=parent.directory)


@pytest.mark.parametrize("fault", ["unbound", "checkpoint", "parent_stop"])
def test_formal_fork_rejects_unbound_or_changed_parent(tmp_path, fault):
    data, bank, files, parent, path, plan, comparison = prepared(tmp_path)
    if fault == "unbound":
        unbound = tmp_path / "unbound.json"
        publish(unbound, read(path))
        path = unbound
    elif fault == "checkpoint":
        cp = copy.deepcopy(read(path)); cp["payload"]["clock"] += 1
        path.write_text(__import__("json").dumps(cp))
    else:
        (parent.directory / "STOP.json").write_text("{}")
    with pytest.raises((ValueError, KeyError)):
        FormalSession.fork(path, data, bank, parent_directory=parent.directory,
            comparison=comparison, bound_files=files, directory=tmp_path / "child",
            controls={"residual_query_plan": plan})
    assert not (tmp_path / "child").exists()
