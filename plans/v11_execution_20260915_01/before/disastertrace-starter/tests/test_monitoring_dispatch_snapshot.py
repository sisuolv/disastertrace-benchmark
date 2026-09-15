"""A real bulletin released at cutoff is not visible to an earlier invocation."""

import json
from pathlib import Path

import pytest

from disastertrace.monitoring_fixed_v1.aviation import AviationProvider

ROOT = Path(__file__).resolve().parents[2]
EXECUTION = ROOT / "plans/v8_measurement_execution_20260913_01"


@pytest.fixture
def provider():
    bank = json.loads((EXECUTION / "contracts/BANK.json").read_text())
    return AviationProvider(EXECUTION / "development_dataset_v2", bank)


def test_dispatch_uses_earlier_real_version_and_retains_cutoff_update(provider):
    oid = "KSJC-2025-02-03T13:00:00Z-vis-lt-5000m-cutoff-2025-02-03T12:00:00Z"
    cutoff = provider.opportunities[oid]["cutoff"]
    at_cutoff = provider.freeze(oid, "common_only").policy_view()
    assert at_cutoff["baseline"]["available_at"] == cutoff
    dispatched = provider.freeze(oid, "all_registered", as_of=cutoff - 60_000_000)
    row = dispatched.policy_view()
    assert row["cutoff"] == cutoff
    assert row["target"] == at_cutoff["target"]
    assert row["baseline"]["source_revision"] != at_cutoff["baseline"]["source_revision"]
    assert (
        max([row["baseline"]["available_at"]] + [a["completed_at"] for a in row["assets"]])
        <= cutoff - 60_000_000
    )
    assert provider.freeze(oid, "common_only").policy_view() == at_cutoff


def test_dispatch_does_not_resurrect_a_covering_old_product(provider):
    oid = "KSJC-2025-02-03T13:00:00Z-vis-lt-5000m-cutoff-2025-02-03T12:00:00Z"
    cutoff = provider.opportunities[oid]["cutoff"]
    latest = provider.bases[oid]["source_id"]
    for row in provider.native_products:
        if row["source_id"] == latest:
            row["valid_end"] = provider.targets[provider.opportunities[oid]["target_id"]][
                "physical_start"
            ]
    with pytest.raises(ValueError, match="current_version_does_not_cover_target"):
        provider.freeze(oid, "common_only", as_of=cutoff)


@pytest.mark.parametrize("offset", [1, 0.5, True])
def test_dispatch_rejects_invalid_or_future_timestamp(provider, offset):
    oid = next(iter(provider.opportunities))
    at = True if offset is True else provider.opportunities[oid]["cutoff"] + offset
    with pytest.raises((ValueError, TypeError)):
        provider.freeze(oid, "common_only", as_of=at)


def test_dispatched_asset_cannot_finish_after_dispatch(provider):
    oid = "KSJC-2025-02-03T13:00:00Z-vis-lt-5000m-cutoff-2025-02-03T12:00:00Z"
    cutoff = provider.opportunities[oid]["cutoff"]
    query = min(provider.pairs[oid]["query_ids"])
    provider.catalog[query]["available_at"] = cutoff
    with pytest.raises(ValueError, match="not complete at snapshot"):
        provider.freeze(oid, "fixed_one", as_of=cutoff - 60_000_000)
