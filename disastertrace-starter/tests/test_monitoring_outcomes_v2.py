"""Canonical target outcomes and explicit experiment interventions."""

import pytest
from test_monitoring_admission import bundle

from disastertrace.monitoring_fixed_v1.contracts import Target


def outcome(value=-4):
    target = Target(**bundle().policy_view()["target"])
    return {
        "target_contract_hash": target.contract_hash,
        "resolution_version": "final.v1",
        "value": value,
        "status": "mature",
        "source_revision": "station-report-v1",
        "source_sha256": "a" * 64,
        "physical_start": 100,
        "physical_end": 100,
        "units": "degC",
        "quality_status": "valid",
        "observed_at": 100,
        "published_at": None,
        "fetched_at": 200,
        "resolved_at": 201,
        "availability_basis": "declared_archive_scenario",
    }


def test_target_outcome_cannot_change_between_leads():
    from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry

    registry = OutcomeRegistry([Target(**bundle().policy_view()["target"])])
    registry.register(outcome())
    assert registry.register(outcome()) is False
    with pytest.raises(ValueError, match="conflict"):
        registry.register(outcome(-9))


def test_optional_raw_provenance_is_bound_and_unknown_fields_rejected():
    from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry

    registry = OutcomeRegistry([Target(**bundle().policy_view()["target"])])
    row = dict(outcome(), references=[{"source_line": 10}], reference_kind="native_report")
    registry.register(row)
    with pytest.raises(ValueError, match="conflict"):
        registry.register(dict(row, references=[{"source_line": 11}]))
    with pytest.raises(ValueError, match="fields"):
        registry.register(dict(row, unexplained=1))


@pytest.mark.parametrize(
    "field,value", [("physical_start", 99), ("units", "K"), ("observed_at", True), ("value", True)]
)
def test_outcome_rejects_wrong_physical_or_value_contract(field, value):
    from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry

    registry = OutcomeRegistry([Target(**bundle().policy_view()["target"])])
    row = outcome()
    row[field] = value
    with pytest.raises(ValueError):
        registry.register(row)


def test_comparison_allows_declared_factors_but_rejects_changed_common_contract():
    from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract

    contract = ComparisonContract(
        {"bank": "same", "universe": "same"},
        {
            "allocation_mode": ["fixed_quota", "global_budget"],
            "authorization_mode": ["target_private", "session_shared"],
        },
    )
    contract.validate(
        {"bank": "same", "universe": "same"},
        {"allocation_mode": "fixed_quota", "authorization_mode": "target_private"},
    )
    contract.validate(
        {"bank": "same", "universe": "same"},
        {"allocation_mode": "global_budget", "authorization_mode": "session_shared"},
    )
    with pytest.raises(ValueError):
        contract.validate(
            {"bank": "different", "universe": "same"},
            {"allocation_mode": "global_budget", "authorization_mode": "session_shared"},
        )
    with pytest.raises(ValueError):
        contract.validate(
            {"bank": "same", "universe": "same"},
            {
                "allocation_mode": "global_budget",
                "authorization_mode": "session_shared",
                "undeclared_factor": 1,
            },
        )


def test_real_encoded_journals_allow_factors_and_bind_canonical_results(tmp_path):
    from test_monitoring_policies import ROOT
    from test_monitoring_typed_session import typed_fixture

    from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
    from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, OutcomeRegistry
    from disastertrace.monitoring_v1.dataset import load_session
    from disastertrace.monitoring_v1.journal import EventJournal
    from disastertrace.monitoring_v1.policies import run_session

    arms, engines = {}, []
    for name, allocation, authorization in [
        ("qp", "fixed_quota", "target_private"),
        ("gs", "global_budget", "session_shared"),
    ]:
        data, bank, config = typed_fixture(
            allocation_mode=allocation, authorization_mode=authorization
        )
        data = load_session(ROOT, stations=["KSFO", "KOAK"], hours=3, threshold=1000)
        arms[name] = tmp_path / (name + ".jsonl")
        with EventJournal(arms[name]) as journal:
            run_session(data, bank, config, journal=journal)
        engines.append(AdmissionEngine.from_journal(arms[name]))
    first = engines[0]
    factors = {
        k: list(
            {str(e.active_interventions[k]): e.active_interventions[k] for e in engines}.values()
        )
        for k in first.active_interventions
    }
    comparison = ComparisonContract(first.contract["experiment"]["invariants"], factors)
    registry = OutcomeRegistry(first.targets.values())
    for target in first.targets.values():
        registry.register(
            {
                "target_contract_hash": target.contract_hash,
                "resolution_version": "test.v1",
                "value": 0,
                "status": "mature",
                "source_revision": "synthetic-test-reference",
                "source_sha256": "a" * 64,
                "physical_start": target.physical_start,
                "physical_end": target.physical_end,
                "units": target.units,
                "quality_status": "valid",
                "observed_at": target.physical_start,
                "published_at": None,
                "fetched_at": target.physical_end + 1,
                "resolved_at": target.physical_end + 2,
                "availability_basis": "declared_archive_scenario",
            }
        )
    outcomes = registry.opportunity_rows(
        first.opportunities.values(), {o: "test.v1" for o in first.opportunities}
    )
    result = score_admitted(outcomes, arms, comparison=comparison)
    assert result["scores"]
    import copy

    bad = copy.deepcopy(outcomes)
    from collections import Counter

    counts = Counter(r["target_contract_hash"] for r in bad)
    repeated = next(t for t, count in counts.items() if count > 1)
    same_target = [r for r in bad if r["target_contract_hash"] == repeated]
    same_target[-1]["value"] = 1
    with pytest.raises(ValueError, match="conflict"):
        score_admitted(bad, arms, comparison=comparison)


def test_unlisted_controller_factor_is_frozen():
    from test_monitoring_typed_session import typed_fixture

    from disastertrace.monitoring_fixed_v1.outcomes import experiment_spec

    data, bank, config = typed_fixture()
    one = experiment_spec(data, bank, config)
    two = experiment_spec(data, bank, dict(config, seed=config["seed"] + 1))
    assert one["invariants"] != two["invariants"]
