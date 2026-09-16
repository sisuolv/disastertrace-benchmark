"""Describe actual consumers and changed factors without method-name heuristics."""

from .targets import canonical_hash

PREDICTOR_FIELDS = {"consumer_kind", "consumer_code_sha256", "bank_sha256", "feature_schema",
                    "calibration_mode", "baseline_mapping_sha256"}


def fingerprint(config, *, baseline_bank, consumer_code_sha256, source_contract_sha256=None):
    predicting = config.get("predict", True)
    kind = config.get("program_prediction", "frequency_mapping") if predicting else "baseline_follow"
    native = predicting and kind in {"native_feature_raw", "native_feature_calibrated"}
    bank = config.get("native_feature_bank") if native else baseline_bank if predicting else None
    return {
        "consumer_kind": kind, "consumer_code_sha256": consumer_code_sha256,
        "bank_sha256": None if bank is None else canonical_hash(bank),
        "feature_schema": bank.get("feature_version") if native and bank else None,
        "calibration_mode": "calibrated" if kind == "native_feature_calibrated" else "raw" if native else "research_mapping",
        "baseline_mapping_sha256": canonical_hash(baseline_bank),
        "source_contract_sha256": source_contract_sha256,
        "forecast_schedule": config.get("forecast_schedule"),
        "protocol": config.get("protocol"), "adoption_policy": config.get("adoption_policy", {"kind": "always"}),
        "failure_continuation_policy": config.get("failure_continuation_policy", "fail_session_v1"),
        "allocation_mode": config.get("allocation_mode"), "authorization_mode": config.get("authorization_mode"),
        "source_budget": config.get("request_budget"), "selector_kind": config.get("selector_kind"),
        "resource_limits": {k: config.get(k) for k in ("request_budget", "token_cap", "compute_ms_cap",
            "model_call_budget", "forecast_call_cap", "per_tick_forecast_cap", "call_compute_cap_ms",
            "input_token_cap", "output_token_cap", "query_limit_per_tick")},
        "common_information": "full legal baseline stream plus mapping",
        "acquire": config.get("acquire", True), "isolation_mode": config.get("isolation_mode", "actual_cost_clock"),
    }


def compare(left, right):
    differing = sorted(k for k in left.keys() | right.keys() if left.get(k) != right.get(k))
    return {
        "same_predictor": not PREDICTOR_FIELDS.intersection(differing),
        "differing_factors": differing,
        "left_sha256": canonical_hash(left), "right_sha256": canonical_hash(right),
        "same_schedule": left.get("forecast_schedule") == right.get("forecast_schedule"),
        "same_source_contract": left.get("source_contract_sha256") == right.get("source_contract_sha256"),
        "qualification": "factor_identity; not a causal or statistical guarantee",
    }
