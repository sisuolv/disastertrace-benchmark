"""Protocol counterexamples for the new fixed-evidence and typed forecast lane."""

import copy
import json

import pytest
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Forecast,
    ForecastState,
    Target,
    paired_scores,
)


def target(kind="scalar", units="degC"):
    return Target(
        "t",
        "station:A",
        "temperature",
        units,
        kind,
        "point",
        100,
        100,
        "future_physical",
        "native_instant.v1",
    )


def bundle_record():
    t = target()
    base = Forecast(t.contract_hash, "scalar", "degC", -3.5).to_dict()
    return {
        "schema": "disastertrace.frozen_evidence.v1",
        "opportunity_id": "o",
        "target": t.to_dict(),
        "cutoff": 90,
        "baseline": {
            "forecast": base,
            "source_revision": "r1",
            "issued_at": 50,
            "available_at": 60,
            "valid_until": 100,
            "kind": "research",
            "mapping_version": "map1",
            "content": {"raw": "forecast -3.5"},
        },
        "state": {
            "forecast": base,
            "mode": "FOLLOW",
            "protocol": "base_bound_override",
        },
        "assets": [
            {
                "asset_id": "a",
                "source_revision": "a1",
                "raw": "TMP=-4",
                "content": {"value": -4},
                "available_at": 70,
                "observed_at": 65,
                "completed_at": 80,
                "entitlements": ["t"],
                "receipt_ids": ["q1"],
                "parents": [],
                "transform": {"version": "decode.v1", "parameters": {}},
                "reference_kind": "measurement",
                "support_assumption": "bounded_error",
                "visible_information_scope": "policy_after_query",
                "support_rule_version": "temperature.v1",
                "missingness": "present",
            }
        ],
        "receipts": [
            {
                "receipt_id": "q1",
                "owner": "t",
                "asset_ids": ["a"],
                "started_at": 70,
                "completed_at": 80,
                "cost": {"requests": 1, "bytes": 6, "tokens": 0, "compute_ms": 1},
            }
        ],
        "authorization_mode": "target_private",
        "representation": "native_plus_fixed_decode",
        "availability_basis": "declared_archive_scenario",
        "provider_version": "fixture.v1",
    }


def test_scalar_point_is_real_point_and_accepts_negative_temperature():
    t = target()
    t.check_cutoff(99)
    assert Forecast(t.contract_hash, "scalar", "degC", -10).value == -10
    with pytest.raises(ValueError):
        t.check_cutoff(100)
    with pytest.raises(ValueError):
        Target(
            "t",
            "a",
            "temp",
            "degC",
            "scalar",
            "point",
            10,
            11,
            "future_physical",
            "native.v1",
        )


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -0.1, 1.1])
def test_event_probability_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        Forecast("c" * 64, "event_probability", "probability", value)


def test_product_release_and_partial_windows_are_distinct():
    t = Target(
        "t",
        "a",
        "drought",
        "category",
        "event_probability",
        "interval",
        10,
        20,
        "future_product_release",
        "release.v1",
        "ge",
        2,
        30,
    )
    t.check_cutoff(25)
    with pytest.raises(ValueError):
        t.check_cutoff(30)
    p = Target(
        "t",
        "a",
        "rain",
        "mm",
        "scalar",
        "interval",
        10,
        20,
        "partial_window_nowcast",
        "sum.v1",
    )
    p.check_cutoff(10)
    with pytest.raises(ValueError):
        p.check_cutoff(9)


def test_freeze_is_deeply_immutable_and_roundtrips():
    record = bundle_record()
    bundle = EvidenceBundle.freeze(record)
    record["assets"][0]["content"]["value"] = 999
    view = bundle.policy_view()
    view["assets"][0]["content"]["value"] = 999
    assert bundle.policy_view()["assets"][0]["content"]["value"] == -4
    assert EvidenceBundle.restore(bundle.to_dict()).bundle_hash == bundle.bundle_hash


@pytest.mark.parametrize(
    "change", ["hidden", "late", "unauthorized", "receipt", "source", "parent"]
)
def test_bundle_rejects_hidden_late_unauthorized_and_unbound_inputs(change):
    r = bundle_record()
    if change == "hidden":
        r["outcome"] = 1
    elif change == "late":
        r["assets"][0]["available_at"] = 91
    elif change == "unauthorized":
        r["assets"][0]["entitlements"] = ["another-target"]
    elif change == "receipt":
        r["receipts"] = []
    elif change == "source":
        r["assets"][0]["source_revision"] = ""
    else:
        r["assets"][0]["parents"] = ["hidden-parent"]
    with pytest.raises(ValueError):
        EvidenceBundle.freeze(r)


def test_hidden_support_and_private_cross_target_receipts_rejected():
    r = bundle_record()
    r["assets"][0]["visible_information_scope"] = "evaluator_only"
    with pytest.raises(ValueError):
        EvidenceBundle.freeze(r)
    r = bundle_record()
    r["receipts"][0]["owner"] = "other"
    with pytest.raises(ValueError):
        EvidenceBundle.freeze(r)


def test_restore_detects_content_tampering():
    r = EvidenceBundle.freeze(bundle_record()).to_dict()
    r["payload"]["assets"][0]["raw"] = "TMP=999"
    with pytest.raises(ValueError):
        EvidenceBundle.restore(r)


def test_typed_state_roundtrip_revision_expiry_and_target_mismatch():
    t = target()
    baseline = Forecast(t.contract_hash, "scalar", "degC", -3)
    candidate = Forecast(t.contract_hash, "scalar", "degC", -4)
    state = ForecastState(t, "base_bound_override")
    state.update_baseline(baseline, "b1", 10)
    assert state.propose(candidate, "b1", 20, 90) == "accepted"
    state = ForecastState.restore(json.loads(json.dumps(state.to_dict())))
    assert state.effective(30).value == -4
    state.update_baseline(baseline, "b2", 31)
    assert state.effective(32).value == -3
    assert state.propose(candidate, "b1", 32, 90) == "stale_base"
    with pytest.raises(ValueError):
        state.propose(Forecast("c" * 64, "scalar", "degC", -4), "b2", 32, 90)
    with pytest.raises(ValueError):
        state.propose(Forecast(t.contract_hash, "scalar", "K", 270), "b2", 32, 90)


def test_persistent_overrides_survive_base_update_but_not_expiry():
    t = target()
    f = Forecast(t.contract_hash, "scalar", "degC", -3)
    state = ForecastState(t, "persistent_override")
    state.update_baseline(f, "b1", 10)
    state.propose(Forecast(t.contract_hash, "scalar", "degC", -4), "b1", 20, 40)
    state.update_baseline(f, "b2", 30)
    assert state.effective(39).value == -4
    assert state.effective(40).value == -4
    assert state.effective(41).value == -3
    assert state.propose(f, "b2", 41, 40) == "late"


def test_candidate_finishing_at_deadline_counts_before_expiry():
    t = target()
    state = ForecastState(t, "base_bound_override")
    state.update_baseline(Forecast(t.contract_hash, "scalar", "degC", -3), "b1", 10)
    candidate = Forecast(t.contract_hash, "scalar", "degC", -4)
    assert state.propose(candidate, "b1", 40, 40) == "accepted"
    assert state.effective(40).value == -4
    assert state.effective(41).value == -3


@pytest.mark.parametrize(
    "t,at",
    [
        (target(), 100),
        (
            Target(
                "p",
                "a",
                "index",
                "units",
                "scalar",
                "interval",
                10,
                20,
                "future_product_release",
                "release.v1",
                release_event_at=30,
            ),
            30,
        ),
        (
            Target(
                "p",
                "a",
                "rain",
                "mm",
                "scalar",
                "interval",
                10,
                20,
                "partial_window_nowcast",
                "sum.v1",
            ),
            20,
        ),
    ],
)
def test_reducer_does_not_adopt_proposals_outside_target_time_semantics(t, at):
    state = ForecastState(t, "persistent_override")
    base = Forecast(t.contract_hash, "scalar", t.units, 1)
    proposal = Forecast(t.contract_hash, "scalar", t.units, 2)
    state.update_baseline(base, "b1", at - 1)
    assert state.propose(proposal, "b1", at, at + 100) == "invalid_target_time"
    assert state.effective(at).value == 1
    assert ForecastState.restore(state.to_dict()).effective(at).value == 1


def test_reused_baseline_identity_cannot_hide_changed_forecast():
    t = target()
    state = ForecastState(t, "base_bound_override")
    state.update_baseline(Forecast(t.contract_hash, "scalar", "degC", -3), "same", 10)
    with pytest.raises(ValueError):
        state.update_baseline(
            Forecast(t.contract_hash, "scalar", "degC", 9), "same", 11
        )


def test_persistent_inflight_candidate_can_finish_after_known_base_changes():
    t = target()
    f = Forecast(t.contract_hash, "scalar", "degC", -3)
    state = ForecastState(t, "persistent_override")
    state.update_baseline(f, "b1", 10)
    state.update_baseline(f, "b2", 20)
    candidate = Forecast(t.contract_hash, "scalar", "degC", -4)
    assert state.propose(candidate, "b1", 30, 40) == "accepted"
    assert state.effective(31).value == -4
    assert state.propose(candidate, "never_seen", 32, 40) == "stale_base"
    assert ForecastState.restore(state.to_dict()).effective(33).value == -4


def test_common_mask_keeps_missing_outcomes_and_failures():
    t = target()
    rows = [
        {"opportunity_id": "a", "target": t.to_dict(), "outcome": -2},
        {"opportunity_id": "b", "target": t.to_dict(), "outcome": None},
    ]
    f = Forecast(t.contract_hash, "scalar", "degC", -3).to_dict()
    report = paired_scores(rows, {"base": {"a": f, "b": f}, "test": {"a": f, "b": f}})
    assert report["registered"] == 2 and report["settled"] == 1
    assert report["arms"]["test"]["mean_loss"] == 1
    with pytest.raises(ValueError):
        paired_scores(rows, {"bad": {"a": f}})


def test_derived_asset_must_inherit_all_parent_receipts():
    r = bundle_record()
    a = copy.deepcopy(r["assets"][0])
    a.update(asset_id="derived", parents=["a"], receipt_ids=[])
    r["assets"].append(a)
    with pytest.raises(ValueError):
        EvidenceBundle.freeze(r)


def test_derived_asset_cannot_claim_availability_before_its_parent():
    record = bundle_record()
    child = copy.deepcopy(record["assets"][0])
    child.update(asset_id="derived", parents=["a"], available_at=69)
    record["assets"].append(child)
    with pytest.raises(ValueError, match="availability"):
        EvidenceBundle.freeze(record)
    child["available_at"] = 70
    assert EvidenceBundle.freeze(record).policy_view()["assets"][1] == child


@pytest.mark.parametrize("semantics", ["future_physical", "future_product_release", "partial_window_nowcast"])
def test_late_baseline_is_journaled_without_changing_effective_forecast(semantics):
    record = target().to_dict()
    record["temporal_semantics"] = semantics
    if semantics == "future_product_release":
        record["release_event_at"] = 120
    elif semantics == "partial_window_nowcast":
        record.update(support_kind="interval", physical_end=120)
    t = Target(**record)
    end = 100 if semantics == "future_physical" else 120
    state = ForecastState(t, "base_bound_override")
    baseline = Forecast(t.contract_hash, "scalar", t.units, 1)
    state.update_baseline(baseline, "b1", end - 2)
    candidate = Forecast(t.contract_hash, "scalar", t.units, 2)
    state.propose(candidate, "b1", end - 1, end + 10)
    late = Forecast(t.contract_hash, "scalar", t.units, 99)
    assert state.update_baseline(late, "late", end) == "invalid_target_time"
    assert state.base_hash == "b1" and state.baseline == baseline
    assert state.effective(end) == candidate
    assert state.events[-1]["kind"] == "base_rejected"
    assert ForecastState.restore(state.to_dict()).to_dict() == state.to_dict()


def test_partial_window_can_retain_baseline_issued_before_window_start():
    t = Target(
        "p", "a", "rain", "mm", "scalar", "interval", 100, 120,
        "partial_window_nowcast", "sum.v1",
    )
    state = ForecastState(t, "persistent_override")
    baseline = Forecast(t.contract_hash, "scalar", "mm", 1)
    assert state.update_baseline(baseline, "b1", 90) == "accepted"
    assert state.effective(100) == baseline
