"""Regressions for reviewed input, dispatch and repeated-replay boundaries."""

import copy
import json

import pytest

from disastertrace.monitoring_v1.feature_tasks import (
    parse_features,
    parse_temperature,
    temperature_ensemble_probability,
)
from disastertrace.monitoring_v1.temperature_postprocess import event_probability


def temperature_row():
    day = 86400_000_000
    return {
        "cutoff": 0,
        "target": {
            "units": "C", "physical_start": day, "physical_end": 2 * day,
            "variable": "daily_max_2m_temperature", "event_operator": "ge", "threshold": 30,
        },
        "common": {"daily_products": [{
            "target_date": "1970-01-02", "day_index": 1,
            "forecast_max_members_C": [31, 20], "forecast_min_members_C": [10, 5],
        }]},
    }


@pytest.mark.parametrize("function", [temperature_ensemble_probability, event_probability])
@pytest.mark.parametrize("failure", [
    "midday", "duplicate", "reversed_duplicate", "nan", "bool_threshold",
    "bool_day", "bool_cutoff", "huge_threshold", "missing_day", "wrong_duration",
])
def test_temperature_contract_rejects_ambiguous_support(function, failure):
    row = temperature_row()
    if failure == "midday":
        row["target"]["physical_start"] += 43200_000_000
        row["target"]["physical_end"] += 43200_000_000
    elif "duplicate" in failure:
        extra = copy.deepcopy(row["common"]["daily_products"][0])
        extra["forecast_max_members_C"] = [35, 35]
        row["common"]["daily_products"].append(extra)
        if failure == "reversed_duplicate":
            row["common"]["daily_products"].reverse()
    elif failure in {"nan", "bool_threshold", "huge_threshold"}:
        row["target"]["threshold"] = {"nan": float("nan"), "bool_threshold": True,
                                     "huge_threshold": 10**400}[failure]
    elif failure == "bool_day":
        row["common"]["daily_products"][0]["day_index"] = True
    elif failure == "bool_cutoff":
        row["cutoff"] = False
    elif failure == "missing_day":
        row["common"]["daily_products"][0]["target_date"] = "1970-01-03"
    else:
        row["target"]["variable"] = "min_of_3_daily_max_2m_temperature"
    with pytest.raises(ValueError):
        function(row)


def test_qualified_max_only_packet_does_not_require_unused_minima():
    row = temperature_row()
    del row["common"]["daily_products"][0]["forecast_min_members_C"]
    assert temperature_ensemble_probability(row) == 0.5


@pytest.mark.parametrize("field", ["lower", "temperature_c", "probability"])
def test_unbounded_lower_and_overflow_are_invalid_responses(field):
    if field == "probability":
        with pytest.raises(ValueError):
            parse_temperature('{"probability":' + str(10**400) + '}')
        return
    slot = {"visibility": {"lower": "+inf", "upper": "+inf",
                           "lower_closed": True, "upper_closed": True},
            "temperature_c": None, "dewpoint_c": None}
    if field == "temperature_c":
        slot["visibility"] = None
        slot["temperature_c"] = 10**400
    with pytest.raises(ValueError):
        parse_features(json.dumps({"slots": {"q": slot}}), ["q"])


@pytest.mark.parametrize("failure", ["stop", "deadline"])
def test_api_gate_is_checked_after_claim_before_transport(tmp_path, monkeypatch, failure):
    from test_monitoring_api_ledger_v2 import setup, valid_response

    api, ledger, messages = setup(tmp_path, monkeypatch, valid_response())
    original = ledger.claim
    sends = []

    def claim(*args):
        value = original(*args)
        if failure == "stop":
            ledger.stop("test stop after reservation")
        else:
            monkeypatch.setattr(api.time, "time_ns", lambda: ledger.contract["deadline_wall_ns"])
        return value

    class Opener:
        def open(self, *args, **kwargs):
            sends.append(1)
            raise RuntimeError("offline transport")

    monkeypatch.setattr(ledger, "claim", claim)
    monkeypatch.setattr(api, "build_opener", lambda *args: Opener())
    with pytest.raises(RuntimeError):
        api.capture(ledger, "0", messages)
    assert not sends
    assert not (ledger.attempt("0") / "dispatch.json").exists()
    assert ledger.reduce()["failed_pre_dispatch"] == 1


def test_formal_scoring_replays_each_arm_once(tmp_path, monkeypatch):
    from test_monitoring_formal_session import setup

    from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
    from disastertrace.monitoring_v1.formal_session import FormalSession, score_formal

    data, bank, config, comparison, files = setup()
    run = FormalSession(data, bank, config, comparison=comparison,
                        bound_files=files, directory=tmp_path / "formal")
    report = run.finish(max_steps=20)
    engine = AdmissionEngine.restore(report["event_replay"])
    journal = run.directory / "admission.jsonl"
    run.export_journal(journal)
    outcomes = [{
        "opportunity_id": oid, "target_contract_hash": o.target.contract_hash,
        "resolution_version": "missing-test.v1", "value": None, "status": "missing",
        "source_revision": "no-observation", "source_sha256": None,
        "physical_start": o.target.physical_start, "physical_end": o.target.physical_end,
        "units": o.target.units, "quality_status": "missing", "observed_at": None,
        "published_at": None, "fetched_at": None, "resolved_at": o.target.physical_end + 1,
        "availability_basis": "declared_archive_scenario",
        "resolution_policy": "h15_routine_archive.v1", "provider": "IEM",
        "provider_version": "native_h15_snapshot.v1",
        "reference_kind": "final_archived_routine_report_not_continuous_physical_truth",
    } for oid, o in engine.opportunities.items()]
    calls = []
    original = AdmissionEngine.from_journal

    def load(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(AdmissionEngine, "from_journal", load)
    refs = {"one": run.directory, "two": run.directory}
    result = score_formal(outcomes, {"one": journal, "two": journal},
                          comparison=comparison, run_references=refs)
    assert result["scores"]
    assert len(calls) == 2
    with pytest.raises(ValueError, match="references"):
        score_formal(outcomes, {"one": journal}, comparison=comparison)
    with pytest.raises(ValueError, match="roster"):
        score_formal(outcomes, {"one": journal}, comparison=comparison, run_references=refs)
    wrong = copy.deepcopy(outcomes)
    wrong[0]["provider"] = "DWD"
    with pytest.raises(ValueError, match="provider"):
        score_formal(wrong, {"one": journal}, comparison=comparison,
                     run_references={"one": run.directory})


def test_formal_restore_rejects_changed_bank_even_if_experiment_shape_matches(tmp_path):
    from test_monitoring_formal_restore import initial

    from disastertrace.monitoring_v1.formal_session import FormalSession

    run, data, bank, path = initial(tmp_path)
    changed = copy.deepcopy(bank)
    changed["v11_extra_identity_field"] = True
    with pytest.raises(ValueError):
        FormalSession.restore(path, data, changed, directory=run.directory)
