import pytest

from disastertrace.monitoring_v1.baseline_registry_v18 import (
    BaselineEntry,
    build_registry,
    persistence_baseline,
)


def test_persistence_baseline_uses_prevailing_period_only():
    evidence = {
        "periods": [
            {"operator": "BASE", "visibility_m": 8000},
            {"operator": "TEMPO", "visibility_m": 400},  # conditional; must be ignored
        ]
    }
    assert persistence_baseline(evidence) == 0.0


def test_persistence_baseline_below_threshold_is_high_probability():
    evidence = {"periods": [{"operator": "FM", "visibility_m": 1200}]}
    assert persistence_baseline(evidence) == 1.0


def test_persistence_baseline_returns_none_without_a_prevailing_period():
    assert persistence_baseline({"periods": [{"operator": "TEMPO", "visibility_m": 100}]}) is None
    assert persistence_baseline({"periods": []}) is None
    assert persistence_baseline({}) is None
    assert persistence_baseline({"periods": "not-a-list"}) is None


def test_persistence_baseline_rejects_non_numeric_visibility_without_crashing():
    assert persistence_baseline({"periods": [{"operator": "BASE", "visibility_m": None}]}) is None
    assert persistence_baseline({"periods": [{"operator": "BASE", "visibility_m": True}]}) is None
    assert persistence_baseline({"periods": [{"operator": "BASE", "visibility_m": "8000"}]}) is None


def test_persistence_baseline_uses_the_last_prevailing_period_not_the_first():
    # A later BASE/FM group in a TAF supersedes an earlier one (see build_v18_dev_episodes.py's
    # own BASE/FM lookahead logic); persistence should follow the same "latest prevailing wins"
    # rule, not accidentally anchor on the first period in the list.
    evidence = {
        "periods": [
            {"operator": "BASE", "visibility_m": 9000},
            {"operator": "FM", "visibility_m": 2000},
        ]
    }
    assert persistence_baseline(evidence) == 1.0


def test_baseline_entry_rejects_a_calibrated_claim_this_round():
    with pytest.raises(ValueError, match="No real Y"):
        BaselineEntry(
            name="x", kind="non_llm_executable", source="s", support="s", units="u",
            threshold=5000.0, lead="l", availability="a", calibration_exposure="CALIBRATED",
            fallback="f",
        )


def test_persistence_reads_the_real_interval_shape_build_v18_dev_episodes_actually_produces():
    # build_v18_dev_episodes.py's real output (confirmed by actually running it against the
    # authorized archive, not assumed) stores visibility_m as an Interval.to_dict(), e.g. a
    # censored "P6SM" report: at least 6 statute miles, unbounded above. A plain-number check
    # would silently return None for every real checkpoint -- this locks in the fix.
    p6sm = {"lower": 9656.064, "upper": "+inf", "lower_closed": False, "upper_closed": True}
    assert persistence_baseline({"periods": [{"operator": "FM", "visibility_m": p6sm}]}) == 0.0

    low_vis = {"lower": 0.0, "upper": 1600.0, "lower_closed": True, "upper_closed": False}
    assert persistence_baseline({"periods": [{"operator": "BASE", "visibility_m": low_vis}]}) == 1.0


def test_persistence_returns_none_not_a_guess_when_the_real_bucket_straddles_the_threshold():
    straddling = {"lower": 3000.0, "upper": 8000.0, "lower_closed": True, "upper_closed": True}
    assert persistence_baseline({"periods": [{"operator": "BASE", "visibility_m": straddling}]}) is None


def test_registry_has_one_executable_non_llm_baseline_and_all_known_llm_arms():
    registry = build_registry()
    non_llm = [e for e in registry if e["kind"] == "non_llm_executable"]
    llm = [e for e in registry if e["kind"] == "llm_arm_registered_not_dispatched"]
    assert [e["name"] for e in non_llm] == ["persistence"]
    assert {e["name"] for e in llm} == {"TRULY_FRESH", "PRIOR_P_ONLY", "PRIOR_P_FACT", "FULL_PREFIX_TRANSCRIPT"}
    assert all(e["calibration_exposure"] == "INTERFACE_READY" for e in registry)
    # Every entry has the full field set the original finding required, no field silently omitted.
    required_fields = {
        "name", "kind", "source", "support", "units", "threshold", "lead",
        "availability", "calibration_exposure", "fallback",
    }
    for entry in registry:
        assert required_fields.issubset(entry.keys())
