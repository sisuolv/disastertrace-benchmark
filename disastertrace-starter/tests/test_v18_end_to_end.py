"""V4 independent V1 offline synthetic end-to-end gate.

This file is deliberately separate from every fixture already used by the
existing v18 unit tests, the reviewer's review_tests package, and Codex's
build_v19_offline_gate.py script. Every expected number below was computed
by hand *before* this file was ever run, using the formulas documented in
scoring.py/grid_scoring_v18.py's own docstrings and comments -- not derived
by calling the functions and copying their output. Where a number could be
sanity-cross-checked two different ways (e.g. gain == base_brier - system_brier),
that cross-check is written out explicitly so a reader can audit the algebra,
not just trust the literal.

No network, no real weather/Y/holdout data, no API keys, no GPU. Everything
here is synthetic. This test only imports offline, pure-Python modules.
"""

from __future__ import annotations

import json

import pytest

from disastertrace.monitoring_v1.grid_scoring_v18 import score_complete_grid
from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.run_journal_v18 import RunJournal


# ---------------------------------------------------------------------------
# Part 1: one grid covering valid / invalid(carry-forward) / late(carry-forward)
# / not_dispatched(fallback) / stop(fallback) / missing(shared-Y, joint bounds)
# / a genuine settled-Y conflict (post-C2-fix isolation), in one report.
#
# Four targets, chosen so that every target's outcome is internally
# consistent across every method/checkpoint that shares its target_id
# (scoring.py groups strictly by target_id, across methods) -- except G4,
# which is deliberately inconsistent on purpose.
#
# G1 (method "raw", 2 checkpoints, weight 1:1 -> normalized 0.5:0.5, outcome 0):
#   c0: valid, p=0.0, base=0.5           -> loss=0,    base_loss=0.25, gain=0.25
#   c1: invalid (no usable probability)  -> carries forward c0's 0.0
#                                            loss=0,    base_loss=0.25, gain=0.25
#
# G2 (methods "raw" and "tool", 1 checkpoint each, outcome 1, base=fallback=0.4):
#   raw/c0:  not_dispatched -> no valid submission anywhere in this 1-point
#            trajectory, so prediction falls back to 0.4 (== base)
#                                          -> loss=0.36, base_loss=0.36, gain=0
#   tool/c0: stop           -> same fallback reasoning
#                                          -> loss=0.36, base_loss=0.36, gain=0
#
# G3 (method "raw", 2 checkpoints, weight 1:1 -> 0.5:0.5, BOTH outcomes
#     unresolved/None -> shared-Y joint-completion bounds, base=0.5 both):
#   c0: valid, p=0.2
#   c1: valid, p=0.6
#   Neither is "settled" (outcome is None for both), so neither enters the
#   settled gains/losses lists; this target only ever contributes through the
#   missing-outcome joint-completion increment (see below).
#
# G4 (method "raw", 2 checkpoints, weight 1:1 -> 0.5:0.5, outcome [0, 1] --
#     an intentional settled-Y conflict, predictions matching each outcome,
#     base=0.5 both, exercising the C2 fix's isolation inside this gate too):
#   c0: valid, p=0.0, outcome=0 -> loss=0, base_loss=0.25, gain=0.25
#   c1: valid, p=1.0, outcome=1 -> loss=0, base_loss=0.25, gain=0.25
#   G4's two settled outcomes disagree (0 vs 1), so both rows must be excluded
#   from every qualified/primary field and retained only under
#   legacy_all_rows_including_conflicts.
# ---------------------------------------------------------------------------


def _reg(target, method, cid, index, base, fallback, outcome, weight=1):
    return {
        "target_id": target,
        "method": method,
        "checkpoint_id": cid,
        "checkpoint_index": index,
        "checkpoint_weight": weight,
        "base": base,
        "fallback": fallback,
        "outcome": outcome,
    }


def _grid_scenario():
    registrations = [
        _reg("G1", "raw", "c0", 0, 0.5, 0.5, 0),
        _reg("G1", "raw", "c1", 1, 0.5, 0.5, 0),
        _reg("G2", "raw", "c0", 0, 0.4, 0.4, 1),
        _reg("G2", "tool", "c0", 0, 0.4, 0.4, 1),
        _reg("G3", "raw", "c0", 0, 0.5, 0.5, None),
        _reg("G3", "raw", "c1", 1, 0.5, 0.5, None),
        _reg("G4", "raw", "c0", 0, 0.5, 0.5, 0),
        _reg("G4", "raw", "c1", 1, 0.5, 0.5, 1),
    ]
    submissions = [
        {"target_id": "G1", "method": "raw", "checkpoint_id": "c0", "status": "valid", "probability": 0.0},
        {"target_id": "G1", "method": "raw", "checkpoint_id": "c1", "status": "invalid", "probability": "not-a-number"},
        {"target_id": "G2", "method": "raw", "checkpoint_id": "c0", "status": "not_dispatched"},
        {"target_id": "G2", "method": "tool", "checkpoint_id": "c0", "status": "stop"},
        {"target_id": "G3", "method": "raw", "checkpoint_id": "c0", "status": "valid", "probability": 0.2},
        {"target_id": "G3", "method": "raw", "checkpoint_id": "c1", "status": "valid", "probability": 0.6},
        {"target_id": "G4", "method": "raw", "checkpoint_id": "c0", "status": "valid", "probability": 0.0},
        {"target_id": "G4", "method": "raw", "checkpoint_id": "c1", "status": "valid", "probability": 1.0},
    ]
    return registrations, submissions


def test_end_to_end_grid_matches_independent_hand_calculation():
    registrations, submissions = _grid_scenario()
    result = score_complete_grid(registrations, submissions)
    report = result["report"]

    # -- process/status accounting (materialize_grid side) --
    assert result["registered"] == 8
    assert result["submission_status_counts"] == {
        "invalid": 1,
        "not_dispatched": 1,
        "stop": 1,
        "valid": 5,
    }
    assert result["carry_forward"] == 1  # only G1/c1
    assert result["fallback"] == 2  # G2 raw/c0 and G2 tool/c0

    # -- qualified (primary/main) report: G4's 2 rows excluded --
    assert report["opportunities"] == 8
    assert report["inconsistent_target_groups"] == 1
    assert report["inconsistent_target_group_rows_excluded"] == 2
    assert report["settled"] == 4  # G1 x2, G2 x2 (G3 missing, G4 excluded)
    assert report["missing"] == 2  # G3 x2
    assert report["missing_target_groups"] == 1  # G3 only

    assert report["qualified_score_weight_total"] == pytest.approx(4.0)
    assert report["score_weight_total"] == pytest.approx(5.0)

    # settled-row means, weighted over settled qualified rows only (weight 3.0):
    #   base_brier = (0.25*0.5 + 0.25*0.5 + 0.36*1 + 0.36*1) / 3.0 = 0.97/3
    #   system_brier = (0 + 0 + 0.36 + 0.36) / 3.0 = 0.72/3 = 0.24
    #   net_realized_gain = (0.25*0.5 + 0.25*0.5 + 0 + 0) / 3.0 = 0.25/3
    #   cross-check: base_brier - system_brier == net_realized_gain
    assert report["base_brier"] == pytest.approx(0.97 / 3.0)
    assert report["system_brier"] == pytest.approx(0.24)
    assert report["net_realized_gain"] == pytest.approx(0.25 / 3.0)
    assert report["base_brier"] - report["system_brier"] == pytest.approx(report["net_realized_gain"])
    assert report["g_plus"] == pytest.approx(0.25 / 3.0)
    assert report["g_minus"] == pytest.approx(0.0)

    # bounds: settled contribute a fixed weight*gain point to both lower/upper
    # (0.125 + 0.125 + 0 + 0 = 0.25); G3's joint-completion increment for the
    # y in (0, 1) endpoints is:
    #   y=0: 0.5*((0.5-0)^2-(0.2-0)^2) + 0.5*((0.5-0)^2-(0.6-0)^2)
    #      = 0.5*(0.25-0.04) + 0.5*(0.25-0.36) = 0.105 - 0.055 = 0.05
    #   y=1: 0.5*((0.5-1)^2-(0.2-1)^2) + 0.5*((0.5-1)^2-(0.6-1)^2)
    #      = 0.5*(0.25-0.64) + 0.5*(0.25-0.16) = -0.195 + 0.045 = -0.15
    #   lower_inc, upper_inc = min(0.05, -0.15), max(0.05, -0.15) = -0.15, 0.05
    # totals: lower = 0.25 - 0.15 = 0.10, upper = 0.25 + 0.05 = 0.30
    # divided by qualified weight 4.0 -> [0.025, 0.075]
    assert report["full_population_gain_bounds"] == pytest.approx([0.025, 0.075])

    # -- legacy (audit-only) view: G4's rows included --
    legacy = report["legacy_all_rows_including_conflicts"]
    assert legacy["audit_only"] is True and legacy["qualified"] is False
    assert legacy["settled"] == 6  # G1 x2, G2 x2, G4 x2
    assert legacy["missing"] == 2  # G3 x2, same as qualified
    assert legacy["missing_target_groups"] == 1
    # settled weight now 4.0 (adds G4's 0.5+0.5); weighted gain sum
    # 0.125+0.125+0+0+0.125+0.125 = 0.5 -> net_realized_gain 0.5/4 = 0.125
    # weighted loss sum 0+0+0.36+0.36+0+0 = 0.72 -> system_brier 0.72/4 = 0.18
    assert legacy["net_realized_gain"] == pytest.approx(0.125)
    assert legacy["system_brier"] == pytest.approx(0.18)
    assert legacy["base_brier"] - legacy["system_brier"] == pytest.approx(legacy["net_realized_gain"])
    # bounds: settled pass sum = 0.125*4 methods... recomputed directly:
    #   G1 0.125+0.125, G2 0+0, G4 0.125+0.125 = 0.5 (both lower/upper)
    #   plus G3's same increment (-0.15, +0.05) -> lower 0.35, upper 0.55
    #   denominator is the full unconditional weight, 5.0
    assert legacy["full_population_gain_bounds"] == pytest.approx([0.35 / 5.0, 0.55 / 5.0])


# ---------------------------------------------------------------------------
# Part 2: crash-recovery / interruption. A dispatch is journaled, then the
# process is modeled as crashing before any response arrives. The journal
# alone (not the in-memory report the caller never got to build) must be
# enough to reconstruct "1 attempt was dispatched, 0 completed" -- and the
# run must refuse a second dispatch/response after it is later closed.
# ---------------------------------------------------------------------------


def test_interrupted_run_leaves_an_auditable_incomplete_unit(tmp_path):
    journal_path = tmp_path / "e2e-run"
    journal = RunJournal(
        journal_path,
        run_id="E2E-INTERRUPT-001",
        scope="CODE",
        config={"model": "stub-model", "max_tokens": 64},
    )
    journal.dispatch(
        request_id="req-0",
        request_sha256="a" * 64,
        model="stub-model",
        settings={"max_tokens": 64},
    )
    # Modeled crash: the process stops here. No .response() call ever
    # happens for req-0. Re-open from disk as a fresh process would.
    reopened = RunJournal.open_existing(journal_path)
    assert reopened.run_id == "E2E-INTERRUPT-001"
    assert reopened.is_closed() is False

    events = [json.loads(line) for line in (journal_path / "events.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events] == ["REGISTERED", "DISPATCH_INTENT"]
    dispatched_ids = {event["request_id"] for event in events if event["event"] == "DISPATCH_INTENT"}
    responded_ids = {event["request_id"] for event in events if event["event"] == "RESPONSE_RECEIVED"}
    # The denominator is reconstructable from the journal alone: exactly one
    # attempt was dispatched, and it is still outstanding (not completed,
    # not silently dropped, not double-counted).
    assert dispatched_ids == {"req-0"}
    assert responded_ids == set()

    journal.close(reason="synthetic_interruption_modeled")
    with pytest.raises(ValueError):
        journal.dispatch(request_id="req-1", request_sha256="b" * 64, model="stub-model", settings={})
    with pytest.raises(ValueError):
        journal.close(reason="already_closed")


# ---------------------------------------------------------------------------
# Part 3: Natural typed kernel -- RETRIEVE-before-available (unavailable,
# and hidden since not a public schedule) -> WAIT to availability -> RETRIEVE
# (available) -> UPDATE (formal prediction) -> STOP; then confirm STOP is
# terminal and does not cancel the scoring opportunity (the kernel itself
# has no scoring hook -- that absence is exactly what C6/C7's still-open
# gap is; this only confirms the typed actions behave to spec).
# ---------------------------------------------------------------------------


def test_natural_kernel_full_lifecycle_and_oracle_leak_guard():
    env = NaturalKernel(
        [NaturalSource("q1", available_at=20, content={"visibility_m": 3000})],
        start=0,
        deadline=100,
    )
    first = env.step(NaturalAction("RETRIEVE", 0, query_id="q1"))
    assert first["status"] == "unavailable"
    assert "available_at" not in first  # not a public schedule: no leak

    env.step(NaturalAction("WAIT", 0, wake_at=20))
    second = env.step(NaturalAction("RETRIEVE", 20, query_id="q1"))
    assert second["status"] == "available"
    assert second["content"] == {"visibility_m": 3000}

    updated = env.step(NaturalAction("UPDATE", 20, probability=0.35))
    assert updated == {"status": "updated", "probability": 0.35, "read_query_ids": ["q1"]}

    stopped = env.step(NaturalAction("STOP", 20))
    assert stopped["status"] == "stopped"
    assert "outcome" not in stopped

    state = env.public_state()
    assert state["terminal"] is True
    assert state["stopped"] is True
    assert state["action_count"] == 5  # RETRIEVE, WAIT, RETRIEVE, UPDATE, STOP
    assert state["read_query_ids"] == ["q1"]
    with pytest.raises(ValueError, match="after STOP"):
        env.step(NaturalAction("WAIT", 20, wake_at=21))


# ---------------------------------------------------------------------------
# Part 4: whole-gate boundary discipline -- nothing above touched real
# weather data, a real API, or holdout data. This is a structural assertion
# about this test module itself, not a claim about the whole repository.
# ---------------------------------------------------------------------------


def test_gate_never_imports_outcome_or_provider_transport_modules():
    # A sys.modules scan is contaminated by whatever else a shared pytest
    # process happens to have imported (e.g. a sibling test file literally
    # named test_monitoring_siliconflow_transport.py) -- that is an artifact
    # of test-run order, not a fact about this file's own import graph.
    # Check this module's own source text instead, which is order-independent.
    import inspect

    source = inspect.getsource(inspect.getmodule(test_gate_never_imports_outcome_or_provider_transport_modules))
    import_lines = [line for line in source.splitlines() if line.strip().startswith(("import ", "from "))]
    forbidden_substrings = ("siliconflow", "outcome_wiring", "quarantine_holdout", "run_v18_controlled_api")
    offending = [line for line in import_lines if any(part in line for part in forbidden_substrings)]
    assert offending == []
