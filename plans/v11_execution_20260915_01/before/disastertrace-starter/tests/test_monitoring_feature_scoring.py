"""Extraction errors and failed calls must not masquerade as forecast value."""

import copy

from test_monitoring_native_feature_forecast import source

from disastertrace.monitoring_v1.feature_scoring import field_agreement, forecast_controls
from disastertrace.monitoring_v1.native_feature_forecast import native_claims


def setup():
    target, qids, disclosed, at = source()
    bank = {
        "feature_version": "native_h15_features.v1",
        "mapping_version": "test-only",
        "feature_names": ["slot0_temperature_c"],
        "mean": [0],
        "scale": [1],
        "coefficients": [[0.1], [0], [0]],
        "intercepts": [0, 0, 0],
    }
    bundle = {
        "target": target,
        "candidate": None,
        "query_ids": qids,
        "disclosed": disclosed,
        "at": at,
    }
    return bundle, dict.fromkeys(("values", "mask_age", "common"), bank)


def test_failed_reply_uses_same_backend_and_has_identical_masked_control():
    bundle, banks = setup()
    result = forecast_controls(bundle, banks, None)
    assert result["values_model_raw"] == result["values_common_raw"]
    assert result["values_validmask_raw"] == result["values_common_raw"]
    assert result["values_missingmask_raw"] == result["values_common_raw"]


def test_wrong_model_values_are_used_without_hidden_native_correction():
    bundle, banks = setup()
    claims = native_claims(bundle["query_ids"], bundle["disclosed"], at=bundle["at"])
    changed = copy.deepcopy(claims)
    changed[min(changed)]["temperature_c"] = 99
    original = forecast_controls(bundle, banks, claims)
    result = forecast_controls(bundle, banks, changed)
    assert result["values_model_raw"] != original["values_model_raw"]
    assert result["values_validmask_raw"] == original["values_model_raw"]
    assert result["values_missingmask_raw"] == original["values_model_raw"]


def test_infinite_endpoint_flag_is_semantically_irrelevant_but_censoring_is_not():
    ref = {"lower": 9656.064, "upper": "+inf", "lower_closed": False, "upper_closed": True}
    assert field_agreement(dict(ref, upper_closed=False), ref, visibility=True)["semantic_exact"]
    assert not field_agreement(dict(ref, lower_closed=True), ref, visibility=True)["semantic_exact"]
    assert not field_agreement(0, None)["semantic_exact"]
    assert field_agreement(1.0000001, 1)["numeric_tolerance"]
