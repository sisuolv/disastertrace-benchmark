import math

import pytest


def test_one_ulp_is_distinct_but_not_new_information():
    from disastertrace.monitoring_v1.forecast_provenance import value_provenance

    p = math.nextafter(.2, 1)
    row = value_provenance(p, current=.2, baseline=.2, outcome=0, effective=.2)
    assert row["proposal_exact_class"] == "numerically_distinct"
    assert row["ulp_distance_current"] == 1
    assert row["within_1e_6"] and row["within_0_005"]
    assert row["effective_delta_loss_vs_baseline"] == 0
    assert row["new_information_established"] is False


def test_exact_program_probability_is_not_misattributed_to_model():
    from disastertrace.monitoring_v1.forecast_provenance import value_provenance

    row = value_provenance(.4, current=.1, baseline=.2, program=.4)
    assert row["proposal_exact_class"] == "exact_program_mapping"
    assert row["loss_delta_vs_baseline"] is None


def test_coherent_projection_is_outcome_blind_and_preserves_valid_cdf():
    from disastertrace.monitoring_v1.regional_calibration_v2 import coherent_cdf

    assert coherent_cdf([.1, .3], ["same", "same"]) == [.1, .3]
    projected = coherent_cdf([.009375, .005952380952380952], ["same", "same"])
    assert projected == pytest.approx([(.009375+.005952380952380952)/2]*2)
    with pytest.raises(ValueError, match="information"):
        coherent_cdf([.2, .1], ["first", "second"])


def test_fixed_total_prior_is_stable_to_irrelevant_score_jitter():
    from disastertrace.monitoring_v1.regional_calibration import apply_monotone
    from disastertrace.monitoring_v1.regional_calibration_v2 import fit_fixed_prior

    same = fit_fixed_prior([(.1, 0, 1)]*100)
    jittered = fit_fixed_prior([(.1+i*1e-12, 0, 1) for i in range(100)])
    assert apply_monotone(same, .1) == pytest.approx(1/102)
    for i in range(100):
        assert apply_monotone(jittered, .1+i*1e-12) == pytest.approx(1/102)


def test_slot_estimates_are_not_promoted_to_product_facts():
    from disastertrace.monitoring_v1.slot_forecast import predict_from_slots

    bank = {"minimum_cell_n": 1, "mapping_version": "test",
            "cells": {'[1000,"no_taf"]': {"n": 98, "positive": 19},
                      '[1000,"pooled"]': {"n": 98, "positive": 19}}}
    result = predict_from_slots(bank, {"threshold": 1000}, None, ["a", "b"], ["a"],
                                {"a": "false", "b": "unknown"})
    assert result["probability"] == .2
    assert result["reference_kind"] == "model_estimate"
    assert result["aggregate_used_by_F"] is False
    with pytest.raises(ValueError, match="unread"):
        predict_from_slots(bank, {"threshold": 1000}, None, ["a", "b"], ["a"],
                           {"a": "false", "b": "true"})
