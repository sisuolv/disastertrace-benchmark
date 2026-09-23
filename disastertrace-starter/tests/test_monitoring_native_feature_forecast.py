"""Evidence content remains usable without TAF and cannot leak future records."""

import copy

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.native_feature_forecast import (
    feature_vector,
    native_claims,
    predict_features,
)


def source():
    data, _, _ = typed_fixture()
    o = data["opportunities"][0]
    t = next(t for t in data["targets"] if t["target_id"] == o["target_id"])
    ids = next(p for p in data["e_f_pairs"] if p["opportunity_id"] == o["opportunity_id"])[
        "query_ids"
    ]
    products = {p["query_id"]: p for p in data["query_results"] if p["query_id"] in ids}
    return t, ids, products, o["cutoff"] - 600_000_000


def test_no_taf_does_not_disable_numeric_evidence_and_mask_control_is_explicit():
    target, ids, products, at = source()
    claims = native_claims(ids, products, at=at)
    original = feature_vector(target, None, ids, products, at=at, claims=claims)
    for value in claims.values():
        value["temperature_c"], value["dewpoint_c"] = 50.0, 45.0
    changed = feature_vector(target, None, ids, products, at=at, claims=claims)
    assert original != changed and original["taf_present"] == changed["taf_present"] == 0
    mask = feature_vector(target, None, ids, products, at=at, mode="mask_age", claims=claims)
    assert not any(k.endswith(("dewpoint_depression_c", "temperature_c")) for k in mask)


def test_future_native_observation_and_unread_claim_are_rejected():
    target, ids, products, at = source()
    future = copy.deepcopy(products)
    next(p for p in future.values() if p["reports"])["reports"][0]["observation_time"] = at + 1
    with pytest.raises(ValueError, match="Future"):
        native_claims(ids, future, at=at)
    with pytest.raises(ValueError, match="disclosed"):
        feature_vector(target, None, ids, {}, at=at, claims={"unread": {}})


def test_same_information_has_identical_features_for_nested_thresholds():
    target, ids, products, at = source()
    one = feature_vector(dict(target, threshold=1000), None, ids, products, at=at)
    five = feature_vector(dict(target, threshold=5000), None, ids, products, at=at)
    assert one == five


def test_report_temperature_sign_and_censoring_are_retained_from_native_text():
    _target, ids, products, at = source()
    altered = copy.deepcopy(products)
    product = next(p for p in altered.values() if p["reports"])
    report = product["reports"][0]
    stamp = __import__("datetime").datetime.fromtimestamp(
        report["observation_time"] / 1_000_000, __import__("datetime").timezone.utc
    )
    report["raw"] = (
        report["station"] + " " + stamp.strftime("%d%H%MZ") + " 00000KT P6SM CLR M05/M10 A3000"
    )
    report["visibility"] = {
        "lower": 9656.064,
        "upper": "+inf",
        "lower_closed": False,
        "upper_closed": True,
    }
    claims = native_claims(ids, altered, at=at)
    assert claims[product["query_id"]]["temperature_c"] == -5
    assert claims[product["query_id"]]["dewpoint_c"] == -10
    assert claims[product["query_id"]]["visibility"]["upper"] == "+inf"


def test_coherent_three_bin_model_handles_extreme_logits_without_overflow():
    bank = {
        "feature_version": "native_h15_features.v1",
        "mapping_version": "test-only",
        "feature_names": ["x"],
        "mean": [0],
        "scale": [1],
        "coefficients": [[1000], [1001], [-1000]],
        "intercepts": [0, 0, 0],
    }
    p = predict_features(bank, {"x": 1})
    assert 0 <= p["1000"] <= p["5000"] <= 1 and sum(p["classes"]) == pytest.approx(1)
