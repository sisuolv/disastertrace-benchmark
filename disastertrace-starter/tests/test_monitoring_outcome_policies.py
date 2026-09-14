"""Provider-specific result chronology, without inventing publication dates."""

import pytest

from disastertrace.monitoring_fixed_v1.contracts import Target
from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry


def fixture(policy="h15_routine_archive.v1"):
    h15 = policy.startswith("h15")
    target = Target(
        "t",
        "station:A",
        "visibility" if h15 else "daily_max_2m_temperature",
        "m" if h15 else "C",
        "event_probability",
        "interval",
        100,
        200,
        "future_physical",
        "iem_routine_unique_hour.v1" if h15 else "DWD_daily_product.v1",
        "lt" if h15 else "ge",
        1000 if h15 else 30,
    )
    record = {
        "target_contract_hash": target.contract_hash,
        "resolution_version": "test.v1",
        "value": 0,
        "status": "mature",
        "source_revision": "native-v1",
        "source_sha256": "a" * 64,
        "physical_start": 100,
        "physical_end": 200,
        "units": target.units,
        "quality_status": "settled_final_archived_report" if h15 else "native_QN_4:9",
        "observed_at": 190 if h15 else None,
        "published_at": None,
        "fetched_at": 300,
        "resolved_at": 301,
        "availability_basis": "declared_archive_scenario",
        "reference_kind": "final_archived_routine_report_not_continuous_physical_truth"
        if h15
        else "native_DWD_daily_product_predicate",
        "references": [{"source_sha256": "a" * 64}],
        "resolution_policy": policy,
    }
    return target, record


@pytest.mark.parametrize("policy", ["h15_routine_archive.v1", "dwd_daily_archive.v1"])
def test_archived_provider_can_qualify_without_fabricated_published_time(policy):
    target, row = fixture(policy)
    registry = OutcomeRegistry([target])
    registry.register(row)
    assert registry.export()["payload"]["records"][0]["published_at"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_at", None),
        ("observed_at", 200),
        ("fetched_at", None),
        ("resolved_at", None),
        ("published_at", 180),
        ("fetched_at", 180),
        ("quality_status", "unregistered"),
        ("status", "missing"),
    ],
)
def test_h15_rejects_unsupported_maturity_and_impossible_chronology(field, value):
    target, row = fixture()
    row[field] = value
    with pytest.raises(ValueError):
        OutcomeRegistry([target]).register(row)


def test_dwd_missing_fetch_receipt_is_not_a_mature_strict_policy_record():
    target, row = fixture("dwd_daily_archive.v1")
    row["fetched_at"] = None
    with pytest.raises(ValueError, match="fetched"):
        OutcomeRegistry([target]).register(row)


def test_missing_result_can_retain_unknown_provider_times():
    target, row = fixture()
    row.update(status="missing", value=None, observed_at=None, fetched_at=None, references=[])
    OutcomeRegistry([target]).register(row)


@pytest.mark.parametrize("policy", ["unknown.v1", {}, [], None])
def test_unknown_provider_policy_cannot_silently_use_legacy_rules(policy):
    target, row = fixture()
    row["resolution_policy"] = policy
    with pytest.raises(ValueError, match="policy"):
        OutcomeRegistry([target]).register(row)
