import math

import pytest

from disastertrace.monitoring_v1.support import (
    EvidenceFact,
    Interval,
    area_support,
    classify,
    public_support,
    sum_intervals,
)
from disastertrace.monitoring_v1.targets import Opportunity, TargetSpec


def fact(
    value, *, version=1, reference_kind="product_label", scope="policy", series="station", release=0
):
    return EvidenceFact(
        series_id=series,
        version=version,
        released_at=release,
        field="visibility",
        units="m",
        interval=Interval(value, value),
        reference_kind=reference_kind,
        visible_information_scope=scope,
        support_assumption="product_exact",
        support_rule_version="test.v1",
    )


def test_empty_support_is_inconsistent_before_quantification():
    assert classify(None, "ge", 20) == "inconsistent"
    assert classify(Interval(12, 42), "ge", 20) == "undetermined"


def test_missing_nonnegative_quantity_has_unbounded_upper_support():
    support = sum_intervals([Interval(10, 10), Interval(0, math.inf)])
    assert support == Interval(10, math.inf)
    assert classify(support, "ge", 50) == "undetermined"


def test_censored_native_bound_preserves_open_endpoint():
    assert classify(Interval(0, 400, upper_closed=False), "lt", 400) == "supported"
    assert classify(Interval(0, 400), "lt", 400) == "undetermined"
    assert classify(Interval(16093.44, math.inf, lower_closed=False), "gt", 16093.44) == "supported"


def test_label_not_visible_to_policy_cannot_narrow_support():
    domain = Interval(0, 100)
    left = [fact(0, reference_kind="evaluator_label", scope="evaluator")]
    right = [fact(100, reference_kind="evaluator_label", scope="evaluator")]
    assert public_support(left, "visibility", "m", domain, 1) == domain
    assert public_support(right, "visibility", "m", domain, 1) == domain


def test_model_estimate_does_not_become_certified_product_fact():
    model = EvidenceFact(
        series_id="model",
        version=1,
        released_at=0,
        field="visibility",
        units="m",
        interval=Interval(0, 0),
        reference_kind="model_estimate",
        visible_information_scope="policy",
        support_assumption="model_estimate",
        support_rule_version="test.v1",
    )
    assert public_support([model], "visibility", "m", Interval(0, 100), 1) == Interval(0, 100)


def test_true_revision_rebuilds_instead_of_intersecting_old_value():
    assert public_support(
        [fact(8), fact(2, version=2, release=5)], "visibility", "m", Interval(0, 10), 4
    ) == Interval(8, 8)
    assert public_support(
        [fact(8), fact(2, version=2, release=5)], "visibility", "m", Interval(0, 10), 5
    ) == Interval(2, 2)


def test_independent_conflict_and_same_version_conflict_remain_inconsistent():
    assert (
        public_support([fact(8), fact(2, series="other")], "visibility", "m", Interval(0, 10), 1)
        is None
    )
    assert public_support([fact(8), fact(2)], "visibility", "m", Interval(0, 10), 1) is None


def test_overlap_union_and_unequal_area_weights():
    weights = {"a": 12.0, "b": 58.0, "c": 30.0}
    tiles = [{"a": Interval(1, 1), "b": Interval(0, 0)}, {"a": Interval(1, 1)}]
    assert area_support(weights, tiles) == Interval(12, 42)
    assert area_support(weights, tiles + tiles) == Interval(12, 42)


def test_area_conflict_or_unknown_cell_does_not_silently_double_count():
    assert area_support({"a": 1.0}, [{"a": Interval(0, 0)}, {"a": Interval(1, 1)}]) is None
    with pytest.raises(ValueError):
        area_support({"a": 1.0}, [{"b": Interval(1, 1)}])


def target(**kwargs):
    return TargetSpec(
        target_id=kwargs.pop("target_id", "A"),
        entity="KSFO",
        variable="visibility",
        units="m",
        event_operator="lt",
        threshold=1000,
        spatial_support="station:KSFO",
        physical_start=kwargs.pop("physical_start", 100),
        physical_end=kwargs.pop("physical_end", 110),
        report_policy="routine_slots.v1",
        outcome_kind="native_report",
        temporal_semantics=kwargs.pop("temporal_semantics", "future_physical"),
        **kwargs,
    )


def test_future_physical_cutoff_is_strictly_before_support():
    Opportunity("o1", target(), 99)
    with pytest.raises(ValueError):
        Opportunity("o2", target(), 100)


def test_product_release_can_forecast_a_past_physical_period():
    product = target(
        physical_start=1,
        physical_end=2,
        temporal_semantics="future_product_release",
        release_event_at=10,
    )
    Opportunity("wed", product, 5)
    with pytest.raises(ValueError):
        Opportunity("late", product, 10)


def test_partial_window_nowcast_requires_an_actually_partial_window():
    partial = target(temporal_semantics="partial_window_nowcast")
    Opportunity("inside", partial, 105)
    with pytest.raises(ValueError):
        Opportunity("before", partial, 99)


def test_different_full_windows_are_different_targets_even_if_end_matches():
    assert (
        target(physical_start=12, physical_end=36).contract_hash
        != target(physical_start=20, physical_end=36).contract_hash
    )
    assert target(target_id="alias").contract_hash == target().contract_hash


@pytest.mark.parametrize("bounds", [(math.nan, 1), (2, 1), (0, math.nan)])
def test_malformed_interval_is_rejected(bounds):
    with pytest.raises(ValueError):
        Interval(*bounds)
