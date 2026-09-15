"""The richer same-information predictor must use the real paid session cache."""

import copy

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.native_feature import NativeFeaturePredictor
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def setup(**changes):
    native = {
        "mode": "values",
        "feature_version": "native_h15_features.v1",
        "mapping_version": "test-only",
        "feature_names": ["slot0_read"],
        "mean": [0],
        "scale": [1],
        "coefficients": [[1], [0], [0]],
        "intercepts": [0, 0, 0],
        "post_calibration": {
            "1000": [{"lower": 0, "upper": 1, "value": 0.1}],
            "5000": [{"lower": 0, "upper": 1, "value": 0.2}],
        },
    }
    return typed_fixture(
        predictor_kind="program",
        program_prediction="native_feature_raw",
        native_feature_bank=native,
        admission_semantics="measurement.v3",
        **changes,
    )


def test_program_session_and_restore_use_only_disclosed_paid_native_assets():
    data, bank, config = setup()
    session = SessionCoordinator(data, bank, config)
    session.step()
    report = SessionCoordinator.restore(session.snapshot(), data, bank).finish()
    assert report == run_session(data, bank, config)
    assert report["actual_model_calls"] == 0 and report["resource_spent"]["tokens"] == 0
    for call in report["calls"]:
        bundle = EvidenceBundle.restore(call["bundle"])
        p = NativeFeaturePredictor(config["native_feature_bank"], at=call["started_at"]).predict(
            bundle
        )
        assert p.value == call["proposed_probability"]
        assert call["receipt"]["executor"] == "native_feature_raw.v1"


def test_calibrated_program_is_explicit_and_has_a_distinct_identity():
    data, bank, config = setup()
    calibrated = dict(config, program_prediction="native_feature_calibrated")
    report = run_session(data, bank, calibrated)
    assert all(c["proposed_probability"] in {0.1, 0.2} for c in report["calls"])
    assert bind_execution(config, None) != bind_execution(calibrated, None)
    changed = copy.deepcopy(config)
    changed["native_feature_bank"]["intercepts"][0] = 1
    assert bind_execution(changed, None) != bind_execution(config, None)


def test_missing_or_wrong_feature_bank_is_rejected_before_a_session():
    data, bank, config = setup()
    del config["native_feature_bank"]
    with pytest.raises(ValueError, match="feature"):
        run_session(data, bank, config)
