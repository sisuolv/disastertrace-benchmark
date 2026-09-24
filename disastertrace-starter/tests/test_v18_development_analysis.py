import pytest

from scripts.analyze_v18_development import validate


def spec(**overrides):
    base = {
        "schema": "disastertrace.v19.analysis_spec.v1",
        "analysis_id": "DEV-ANALYSIS-SPEC-001",
        "claims": ["calibration"],
        "evidence_tiers": [],
    }
    base.update(overrides)
    return base


def test_valid_spec_with_no_evidence_is_not_evaluable_for_every_claim():
    result = validate(spec(claims=list(sorted({"forecast_gain", "calibration", "ranking", "live_agent", "generalization"}))))
    assert result["valid"] is True
    for claim, status in result["claim_status"].items():
        assert status["status"] == "NOT_EVALUABLE"
        assert status["missing_evidence"]


def test_calibration_becomes_structurally_evaluable_once_outcome_authorized_is_declared():
    result = validate(spec(claims=["calibration"], evidence_tiers=["outcome_authorized"]))
    assert result["claim_status"]["calibration"] == {"status": "STRUCTURALLY_EVALUABLE", "missing_evidence": []}


def test_forecast_gain_needs_both_baseline_calibrated_and_outcome_authorized():
    only_baseline = validate(spec(claims=["forecast_gain"], evidence_tiers=["baseline_calibrated"]))
    assert only_baseline["claim_status"]["forecast_gain"]["status"] == "NOT_EVALUABLE"
    assert only_baseline["claim_status"]["forecast_gain"]["missing_evidence"] == ["outcome_authorized"]
    both = validate(spec(claims=["forecast_gain"], evidence_tiers=["baseline_calibrated", "outcome_authorized"]))
    assert both["claim_status"]["forecast_gain"]["status"] == "STRUCTURALLY_EVALUABLE"


def test_this_round_actual_state_is_not_evaluable_for_everything():
    # This round's real, current evidence tiers: baseline is INTERFACE_READY (not calibrated),
    # no outcome authorization, no locked cohort, no prospective/live authorization, no executed
    # extension. Every claim must therefore be NOT_EVALUABLE -- this is the actual honest state,
    # not a hypothetical.
    result = validate(spec(
        claims=["forecast_gain", "calibration", "ranking", "live_agent", "generalization"],
        evidence_tiers=["baseline_interface_ready"],
    ))
    assert all(s["status"] == "NOT_EVALUABLE" for s in result["claim_status"].values())


def test_unknown_claim_type_is_rejected():
    with pytest.raises(ValueError, match="claims must be"):
        validate(spec(claims=["not_a_real_claim"]))


def test_unknown_evidence_tier_is_rejected():
    with pytest.raises(ValueError, match="evidence_tiers must be"):
        validate(spec(evidence_tiers=["made_up_tier"]))


def test_credential_like_text_is_rejected():
    with pytest.raises(ValueError, match="Sensitive key"):
        validate(spec(api_key="whatever"))
    with pytest.raises(ValueError, match="Credential-like"):
        validate(spec(note="Authorization: Bearer abc123"))


def test_holdout_or_raw_path_string_is_rejected():
    with pytest.raises(ValueError, match="Raw/holdout paths"):
        validate(spec(input_hint="data_real_v16/taf/somefile.body"))
    with pytest.raises(ValueError, match="Raw/holdout paths"):
        validate(spec(input_hint="quarantine_holdout/x"))


def test_wrong_schema_is_rejected():
    with pytest.raises(ValueError, match="Unsupported analysis-spec schema"):
        validate(spec(schema="disastertrace.v18.run_spec.v1"))
