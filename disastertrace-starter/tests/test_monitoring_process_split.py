import pytest

from disastertrace.monitoring_v1.process_split import chronological_roles, process_components


def row(key, lo, hi, *versions):
    return {"opportunity_id": key, "footprint_start": lo, "footprint_end": hi, "native_versions": list(versions)}


def test_overlapping_lookback_merges_different_days_and_stations():
    rows = [row("station_a_day1", 0, 10), row("station_b_day2", 9, 20), row("later", 30, 40)]
    groups = process_components(rows)
    assert groups["station_a_day1"] == groups["station_b_day2"]
    assert groups["later"] != groups["station_a_day1"]


def test_shared_revision_merges_disjoint_time_blocks():
    groups = process_components([row("a", 0, 10, "rev"), row("b", 30, 40, "rev")])
    assert groups["a"] == groups["b"]


def test_future_reference_crossing_role_boundary_is_purged():
    rows = [row("fit", 0, 8), row("crossing", 9, 11), row("cal", 21, 29)]
    roles = chronological_roles(rows, {"fit": (0, 10), "calibration": (20, 30)})
    assert roles == {"fit": "fit", "crossing": "purged", "cal": "calibration"}


def test_shared_native_version_cannot_leak_across_roles():
    with pytest.raises(ValueError, match="native version"):
        chronological_roles(
            [row("a", 0, 8, "same"), row("b", 21, 29, "same")],
            {"fit": (0, 10), "calibration": (20, 30)},
        )


def test_process_membership_stable_under_row_order():
    rows = [row("a", 0, 10), row("b", 8, 20), row("c", 40, 50)]
    assert process_components(rows) == process_components(list(reversed(rows)))
