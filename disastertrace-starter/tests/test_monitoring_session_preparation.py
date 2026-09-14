"""Preparation survives original pending transports on the shared event clock."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_monitoring_pending_predictor import PendingFixtureBackend
from test_monitoring_pending_predictor import reply as predictor_reply
from test_monitoring_pending_selector import SelectorFixtureBackend
from test_monitoring_pending_selector import reply as selector_reply
from test_monitoring_pending_source import PendingSource
from test_monitoring_pending_source import reply as source_reply
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.targets import canonical_hash


def preparation_config(data, config):
    first = min(o["cutoff"] for o in data["opportunities"])
    wake = first - config["wakeup_seconds"] * 1_000_000
    card = {
        "schema": "disastertrace.preparation_scenario.v1",
        "kind": "research_assumption",
        "capacity": 1,
        "budget": 10,
        "units": "synthetic_cost_units",
        "jobs": [
            {
                "job_id": "preparation-a",
                "target_id": data["opportunities"][0]["target_id"],
                "deadline": first,
                "duration": 40_000_000,
                "expires_at": first + 100_000_000,
                "cost": 3,
                "cleanup_duration": 5_000_000,
                "cleanup_cost": 1,
            }
        ],
    }
    return {
        "schema": "disastertrace.session_preparation_schedule.v1",
        "decision_basis": "frozen_exogenous_schedule",
        "scenario": card,
        "events": [
            {
                "event_id": "D-start",
                "time": wake - 2,
                "kind": "prepare",
                "payload": {"job_id": "preparation-a"},
            },
            {
                "event_id": "D-cancel",
                "time": wake + 10_000_000,
                "kind": "cancel_preparation",
                "payload": {"job_id": "preparation-a"},
            },
        ],
    }


def make_pending(directory, role):
    data, bank, config = typed_fixture(
        isolation_mode="actual_cost_clock",
        authorization_mode="session_shared",
        forecast_call_cap=1,
        per_tick_forecast_cap=1,
        model_call_budget=1,
        request_budget=1,
    )
    if role == "source":
        first = min(o["cutoff"] for o in data["opportunities"])
        data["opportunities"] = [o for o in data["opportunities"] if o["cutoff"] == first]
        tids = {o["target_id"] for o in data["opportunities"]}
        oids = {o["opportunity_id"] for o in data["opportunities"]}
        data["targets"] = [t for t in data["targets"] if t["target_id"] in tids]
        data["baseline_candidates"] = [
            b for b in data["baseline_candidates"] if b["target_id"] in tids
        ]
        data["e_f_pairs"] = [p for p in data["e_f_pairs"] if p["opportunity_id"] in oids]
    config["preparation_schedule"] = preparation_config(data, config)
    backend, source_backend = None, None
    if role == "selector":
        config.update(selector_kind="llm", predict=False, acquire=False)
        backend = SelectorFixtureBackend(directory)
    elif role == "predictor":
        config.update(acquire=False)
        backend = PendingFixtureBackend(directory)
    else:
        config.update(predict=False)
        source_backend = PendingSource(directory, data["query_results"])
    session = SessionCoordinator(data, bank, config, backend=backend, source_backend=source_backend)
    session.step()
    return data, bank, session


def preparation(checkpoint):
    return AdmissionEngine.restore(checkpoint["payload"]["runtime"]).preparation


@pytest.mark.parametrize("role", ["selector", "predictor", "source"])
def test_pending_preparation_is_idempotent_and_restores_in_another_process(tmp_path, role):
    data, bank, session = make_pending(tmp_path, role)
    original = session.snapshot()
    assert "pending_" + role in original["payload"]
    reducer = preparation(original)
    assert reducer is not None
    assert reducer.states["preparation-a"]["status"] == "running"
    assert reducer.spent == 3 and reducer.reserved == 1
    session.step()
    assert session.snapshot() == original
    if role == "selector":
        selector_reply(tmp_path, elapsed_seconds=30)
    elif role == "predictor":
        predictor_reply(tmp_path)
        p = tmp_path / "forecast-0-reply.json"
        row = json.loads(p.read_text())
        row["details"]["elapsed_seconds"] = 30
        p.write_text(json.dumps(row))
    else:
        source_reply(tmp_path, data, session, elapsed_seconds=30)
    session.finish()
    assert session.done
    expected = session.snapshot()
    reducer = preparation(expected)
    assert reducer.states["preparation-a"]["status"] == "canceled"
    assert reducer.spent == 4 and reducer.reserved == 0
    assert [r["status"] for r in reducer.history].count("started") == 1
    assert [r["status"] for r in reducer.history].count("cleanup_complete") == 1
    spec = tmp_path / "SPEC.json"
    spec.write_text(json.dumps({"data": data, "bank": bank, "checkpoint": original, "role": role}))
    code = """
import json,sys
from pathlib import Path
from test_monitoring_pending_predictor import PendingFixtureBackend
from test_monitoring_pending_selector import SelectorFixtureBackend
from test_monitoring_pending_source import PendingSource
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
d=Path(sys.argv[1]);s=json.loads((d/'SPEC.json').read_text());role=s['role']
backend=SelectorFixtureBackend(d) if role=='selector' else PendingFixtureBackend(d) if role=='predictor' else None
source=PendingSource(d,s['data']['query_results']) if role=='source' else None
c=SessionCoordinator.restore(s['checkpoint'],s['data'],s['bank'],backend=backend,source_backend=source)
c.finish();assert c.done
(d/'RESTORED.json').write_text(json.dumps(c.snapshot()))
"""
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join(
            [
                str(Path(__file__).parent),
                str(Path(__file__).parents[1] / "src"),
            ]
        ),
    )
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=env, check=True)
    assert json.loads((tmp_path / "RESTORED.json").read_text()) == expected
    assert (
        len(list(tmp_path.glob("*-request.json"))) + len(list(tmp_path.glob("*.request.json"))) == 1
    )


def test_preparation_changes_no_f_predictions_or_source_costs():
    data, bank, config = typed_fixture()
    plain = run_session(data, bank, config)
    config["preparation_schedule"] = preparation_config(data, config)
    prepared = run_session(data, bank, config)
    assert prepared["resource_spent"] == plain["resource_spent"]
    for a, b in zip(plain["snapshots"], prepared["snapshots"], strict=True):
        assert a["forecast"] == b["forecast"] and a["base_forecast"] == b["base_forecast"]
    assert AdmissionEngine.restore(prepared["event_replay"]).preparation.spent == 4


@pytest.mark.parametrize("damage", ["kind", "job", "duplicate", "decision_basis", "legacy"])
def test_preparation_schedule_rejects_unregistered_controls(damage):
    data, bank, config = typed_fixture()
    schedule = preparation_config(data, config)
    if damage == "kind":
        schedule["events"][0]["kind"] = "baseline"
    elif damage == "job":
        schedule["events"][0]["payload"]["job_id"] = "unknown-job"
    elif damage == "duplicate":
        schedule["events"].append(copy.deepcopy(schedule["events"][0]))
    elif damage == "decision_basis":
        schedule["decision_basis"] = "future_label_oracle"
    else:
        config["session_runtime"] = "legacy_probability_v1"
    config["preparation_schedule"] = schedule
    with pytest.raises(ValueError, match="preparation|Preparation"):
        run_session(data, bank, config)


def test_rehashed_checkpoint_cannot_change_preparation_contract(tmp_path):
    data, bank, session = make_pending(tmp_path, "predictor")
    changed = session.snapshot()
    changed["payload"]["config"]["preparation_schedule"]["scenario"]["budget"] += 1
    changed["sha256"] = canonical_hash(changed["payload"])
    with pytest.raises(ValueError, match="contract|config"):
        SessionCoordinator.restore(changed, data, bank, backend=PendingFixtureBackend(tmp_path))
