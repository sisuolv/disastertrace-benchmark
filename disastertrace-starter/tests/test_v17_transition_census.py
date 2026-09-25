"""R1-R4 negative-case witnesses for scripts/run_transition_census_v17.py.

Each class pins one of the four defects found in the A2 transition census and
proves the corrected behaviour, both at unit level and (where the defect was
only visible end-to-end) through the real run_census()/main() entry points
with a synthetic, tmp_path-scoped bulk archive.

Expected values are hand-derived from the documented contracts, NOT copied
from a run of the code under test:
  - ledger.DEFAULT_DECLARED_LAG_US = 120 s, so available_at = issued_at + 2 min
  - visible_at() is an inclusive `<=` cutoff
  - checkpoints T-60/T-40/T-20 relative to the slot's validity_start
  - INITIAL_PREFIX: available <= T-60; INTERVAL_1: (T-60, T-40];
    INTERVAL_2: (T-40, T-20]; AFTER_LAST_SCORE: > T-20

No real data is read: every archive is synthetic and lives under tmp_path.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))
sys.path.insert(0, str(_project / "scripts"))

import run_transition_census_v17 as census  # noqa: E402
from disastertrace.monitoring_v1.targets import utc_us  # noqa: E402
from disastertrace.revision_v1.ledger import compile_ledger  # noqa: E402


MIN_US = 60 * 1_000_000
HOUR_US = 60 * MIN_US
LAG_US = 2 * MIN_US  # ledger.DEFAULT_DECLARED_LAG_US
DAY = 24 * HOUR_US


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _slot(validity_start_us: int = 0, station: str = "KSFO") -> census.CandidateSlot:
    return census.CandidateSlot(
        station=station,
        validity_start_us=validity_start_us,
        validity_end_us=validity_start_us + HOUR_US,
        checkpoint_t60_us=validity_start_us - 60 * MIN_US,
        checkpoint_t40_us=validity_start_us - 40 * MIN_US,
        checkpoint_t20_us=validity_start_us - 20 * MIN_US,
    )


def _pkg(*, source_id, issued_at, semantic_hash, valid_start=0, valid_end=HOUR_US,
         amendment_kind="original", station="KSFO", provider="prov1"):
    return {
        "source_id": source_id,
        "station": station,
        "issued_at": issued_at,
        "valid_start": valid_start,
        "valid_end": valid_end,
        "amendment_kind": amendment_kind,
        "status": "active",
        "native_semantics_sha256": semantic_hash,
        "provider": provider,
        "_source_raw_text_sha256": f"raw_{source_id}",
    }


def _classify(slot, packages):
    changes = census.classify_changes_for_slot(slot, {slot.station: packages})
    status, flags = census._compute_slot_status(
        changes, station_earliest_available_us=None, checkpoint_t60_us=slot.checkpoint_t60_us,
    )
    return changes, status, flags, census.compute_slot_signals(changes)


# Synthetic AFOS stream helpers (same frame shape as the real DL-3R bodies).
SOH, ETX = "\x01", "\x03"


def _frame(seq: str, wmo_header: str, pil: str, body_line: str) -> str:
    return f"{SOH}{seq}\n{wmo_header}\n{pil}\n{body_line}{ETX}\n"


def _write_pair(bulk_dir: Path, station: str, year_month: str, stream_text: str) -> None:
    bulk_dir.mkdir(parents=True, exist_ok=True)
    body = stream_text.encode("utf-8")
    (bulk_dir / f"{station}_{year_month}.body").write_bytes(body)
    (bulk_dir / f"{station}_{year_month}.json").write_text(
        json.dumps({"sha256": hashlib.sha256(body).hexdigest()})
    )


def _config(calendar_start: str, calendar_end: str) -> dict:
    return {
        "calendar_start": calendar_start,
        "calendar_end": calendar_end,
        "holdout_exclusion": {
            "window_start": "2025-02-17T00:00:00Z",
            "window_end": "2025-02-24T00:00:00Z",
        },
    }


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# R1 -- routine new evidence in the scoring window must be counted
# ---------------------------------------------------------------------------

class TestR1RoutineArrivalCounted:
    def test_routine_new_baseline_in_interval_1_counts_as_new_arrival(self):
        """(witness a) A routine (non-AMD/COR/CNL) TAF that first becomes
        visible in INTERVAL_1 is a genuine new arrival. The mutually-exclusive
        status stays INITIAL_ONLY_NO_CHANGE (IN_EPISODE_CHANGE definition is
        unchanged), but the independent any_new_arrival signal must be True.
        Before R1 this arrival was invisible in every output count."""
        slot = _slot(0)
        baseline = _pkg(source_id="base", issued_at=-3 * HOUR_US, semantic_hash="hA")
        # available_at = -52min + 2min = -50min: in (T-60, T-40] -> INTERVAL_1
        routine = _pkg(source_id="routine", issued_at=-52 * MIN_US, semantic_hash="hB")

        changes, status, flags, signals = _classify(slot, [baseline, routine])
        by_id = {c.current_source_id: c for c in changes}

        assert by_id["routine"].change_type == "INITIAL_BASELINE"
        assert by_id["routine"].available_at_us == -50 * MIN_US
        assert by_id["routine"].checkpoint_classification == census.AVAIL_INTERVAL_1
        assert by_id["base"].checkpoint_classification == census.AVAIL_INITIAL_PREFIX

        assert status == census.STATUS_INITIAL_ONLY_NO_CHANGE
        assert flags == []
        assert signals["any_new_arrival_in_scoring_window"] is True
        assert signals["n_new_arrivals_in_scoring_window"] == 1
        assert signals["scoring_window_arrival_change_types"] == ["INITIAL_BASELINE"]
        assert signals["new_semantic_arrival_in_scoring_window"] is True
        assert signals["change_like_arrival_in_scoring_window"] is False
        assert signals["target_content_change"] == "UNASSESSED"

    def test_no_change_control_has_no_arrival_signals(self):
        """(witness b) Correct no-change control: only prefix evidence, nothing
        new visible between T-60 and T-20 -> every arrival signal False."""
        slot = _slot(0)
        baseline = _pkg(source_id="base", issued_at=-3 * HOUR_US, semantic_hash="hA")
        # A late product (available after T-20) must not count either:
        # available_at = -12min + 2min = -10min > T-20.
        late = _pkg(source_id="late", issued_at=-12 * MIN_US, semantic_hash="hB")

        changes, status, flags, signals = _classify(slot, [baseline, late])
        by_id = {c.current_source_id: c for c in changes}
        assert by_id["late"].checkpoint_classification == census.AVAIL_AFTER_LAST_SCORE

        assert status == census.STATUS_INITIAL_ONLY_NO_CHANGE
        assert flags == []
        assert signals["any_new_arrival_in_scoring_window"] is False
        assert signals["n_new_arrivals_in_scoring_window"] == 0
        assert signals["new_semantic_arrival_in_scoring_window"] is False
        assert signals["change_like_arrival_in_scoring_window"] is False
        assert signals["unresolved_in_initial_prefix"] is False
        assert signals["unresolved_in_scoring_window"] is False

    def test_duplicate_arrival_is_arrival_but_not_new_semantics(self):
        """Layer separation: a same-semantics mirror arriving in the window is
        a source arrival but not a whole-report semantics change."""
        slot = _slot(0)
        baseline = _pkg(source_id="base", issued_at=-3 * HOUR_US, semantic_hash="hA")
        # Different provider, identical semantics hash -> ledger kind "mirror".
        # available_at = -32min + 2min = -30min -> INTERVAL_2.
        mirror = _pkg(source_id="mirror", issued_at=-32 * MIN_US, semantic_hash="hA",
                      provider="prov2")

        changes, status, _flags, signals = _classify(slot, [baseline, mirror])
        by_id = {c.current_source_id: c for c in changes}
        assert by_id["mirror"].change_type == "mirror_duplicate"
        assert by_id["mirror"].checkpoint_classification == census.AVAIL_INTERVAL_2

        assert status == census.STATUS_INITIAL_ONLY_NO_CHANGE
        assert signals["any_new_arrival_in_scoring_window"] is True
        assert signals["new_semantic_arrival_in_scoring_window"] is False
        assert signals["change_like_arrival_in_scoring_window"] is False

    def test_amd_in_window_keeps_original_in_episode_definition(self):
        """(b) The AMD/COR/CNL-only definition is preserved exactly."""
        slot = _slot(0)
        baseline = _pkg(source_id="base", issued_at=-3 * HOUR_US, semantic_hash="hA")
        amd = _pkg(source_id="amd", issued_at=-52 * MIN_US, semantic_hash="hB",
                   amendment_kind="AMD")
        _changes, status, _flags, signals = _classify(slot, [baseline, amd])
        assert status == census.STATUS_IN_EPISODE_CHANGE
        assert signals["any_new_arrival_in_scoring_window"] is True
        assert signals["change_like_arrival_in_scoring_window"] is True

    def test_routine_arrival_reaches_top_level_summary(self, tmp_path):
        """(witness a, end-to-end) Through the real run_census() entry point:
        KSFO 2023-01-05 06Z slot has a prefix baseline (issued 04/1200Z) and
        a ROUTINE (no AMD) TAF issued 05/0510Z -> available 05:12Z, in
        (T-60=05:00, T-40=05:20] -> INTERVAL_1."""
        stream = (
            _frame("002", "FTUS41 KSFO 050510", "TAFSFO",
                   "TAF KSFO 050510Z 0506/0507 24016KT P6SM SCT015=")
            + _frame("001", "FTUS41 KSFO 041200", "TAFSFO",
                     "TAF KSFO 041200Z 0506/0507 22010KT P6SM SCT025=")
        )
        bulk = tmp_path / "bulk"
        _write_pair(bulk, "KSFO", "202301", stream)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(_config("2023-01-05T00:00:00Z", "2023-01-06T00:00:00Z")))
        out = tmp_path / "OUT"

        result = census.run_census(bulk, cfg, artifacts_dir=out)

        slot = [s for s in _load_jsonl(out / "slot_summary.jsonl")
                if s["station"] == "KSFO" and s["validity_start_us"] == utc_us("2023-01-05T06:00:00Z")]
        assert len(slot) == 1
        slot = slot[0]
        assert slot["status"] == census.STATUS_INITIAL_ONLY_NO_CHANGE
        assert slot["signals"]["any_new_arrival_in_scoring_window"] is True
        assert slot["signals"]["change_like_arrival_in_scoring_window"] is False

        assert result.slots_by_status[census.STATUS_IN_EPISODE_CHANGE] == 0
        assert result.n_targets_with_change_like_arrival == 0
        assert result.n_targets_with_any_new_arrival == 1
        assert result.n_targets_with_new_semantic_arrival == 1
        assert result.n_initial_only_status_with_any_new_arrival == 1


# ---------------------------------------------------------------------------
# R2 -- months outside ALLOWED_YEAR_MONTHS never become candidate slots
# ---------------------------------------------------------------------------

class TestR2UnallowedMonthExcluded:
    HOLDOUT = (utc_us("2025-02-17T00:00:00Z"), utc_us("2025-02-24T00:00:00Z"))

    def test_allowed_year_months_is_required_keyword(self):
        with pytest.raises(TypeError):
            census.generate_continuous_calendar_slots(0, DAY, 0, 0)  # type: ignore[call-arg]

    def test_feb_2025_slots_are_unallowed_month_exclusions(self):
        """(witness c) Calendar 2025-01-31 .. 2025-03-02 with the real
        allowlist. Hand-derived: Feb has 28 days x 4 stations x 4 hours = 448
        candidates. Protected window [Feb17, Feb24) covers 7 days x 16 = 112,
        plus the 4 Feb-24 00Z slots whose T-60 (Feb-23 23:00Z) is in the
        window = 116 protected_window. The remaining 448 - 116 = 332 are
        unallowed_month. Kept slots: Jan 31 + Mar 1 = 2 x 16 = 32."""
        slots, exclusions = census.generate_continuous_calendar_slots(
            utc_us("2025-01-31T00:00:00Z"), utc_us("2025-03-02T00:00:00Z"),
            *self.HOLDOUT, allowed_year_months=census.ALLOWED_YEAR_MONTHS,
        )
        reasons: dict[str, int] = {}
        for e in exclusions:
            reasons[e.reason] = reasons.get(e.reason, 0) + 1
        assert reasons == {"protected_window": 116, "unallowed_month": 332}
        assert len(slots) == 32
        feb_start, mar_start = utc_us("2025-02-01T00:00:00Z"), utc_us("2025-03-01T00:00:00Z")
        assert not [s for s in slots if feb_start <= s.validity_start_us < mar_start]
        for e in exclusions:
            if e.reason == "unallowed_month":
                assert e.detail["year_month"] == "2025-02"
            else:
                assert e.detail["year_month_allowed"] is False

    def test_without_month_filter_old_behaviour_is_reproduced(self):
        """Control: with the filter explicitly disabled, the 332 Feb slots
        come back as candidate slots -- i.e. the parameter is what excludes
        them (this is exactly the pre-R2 behaviour)."""
        slots, exclusions = census.generate_continuous_calendar_slots(
            utc_us("2025-01-31T00:00:00Z"), utc_us("2025-03-02T00:00:00Z"),
            *self.HOLDOUT, allowed_year_months=None,
        )
        assert len(slots) == 32 + 332
        assert {e.reason for e in exclusions} == {"protected_window"}

    def test_unallowed_month_via_run_census_is_excluded_not_no_evidence(self, tmp_path):
        """(witness c, end-to-end) Calendar 2025-02-27 .. 2025-03-02 (outside
        the protected window but inside unallowed 2025-02 for Feb 27/28).
        Before R2 these 2 days x 16 = 32 slots were generated and, since no
        file can be read for 2025-02, landed as NO_APPLICABLE_EVIDENCE/NO_INPUT.
        Now they are unallowed_month exclusions and never appear as slots.
        No 2025-02 file exists or is read: only a 2025-03 pair is written."""
        stream = _frame("001", "FTUS41 KSFO 010500", "TAFSFO",
                        "TAF KSFO 010500Z 0106/0107 22010KT P6SM SCT025=")
        bulk = tmp_path / "bulk"
        _write_pair(bulk, "KSFO", "202503", stream)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(_config("2025-02-27T00:00:00Z", "2025-03-02T00:00:00Z")))
        out = tmp_path / "OUT"

        result = census.run_census(bulk, cfg, artifacts_dir=out)

        # calendar_end is exclusive at 2025-03-02T00Z -> only Mar 1 kept: 16.
        assert result.total_continuous_calendar_slots == 16
        slots = _load_jsonl(out / "slot_summary.jsonl")
        mar_start = utc_us("2025-03-01T00:00:00Z")
        assert all(s["validity_start_us"] >= mar_start for s in slots)
        excl = _load_jsonl(out / "exclusions.jsonl")
        assert [e["reason"] for e in excl] == ["unallowed_month"] * 32
        assert {e["detail"]["year_month"] for e in excl} == {"2025-02"}
        assert sum(result.slots_by_status.values()) == result.total_continuous_calendar_slots


# ---------------------------------------------------------------------------
# R3 -- station-wide ledger compile failure must fail closed
# ---------------------------------------------------------------------------

class TestR3LedgerCompileFailureFailsClosed:
    STREAM = _frame("001", "FTUS41 KSFO 041200", "TAFSFO",
                    "TAF KSFO 041200Z 0506/0507 22010KT P6SM SCT025=")

    def _setup(self, tmp_path):
        bulk = tmp_path / "bulk"
        _write_pair(bulk, "KSFO", "202301", self.STREAM)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(_config("2023-01-05T00:00:00Z", "2023-01-06T00:00:00Z")))
        return bulk, cfg

    @staticmethod
    def _boom(*_a, **_k):
        raise ValueError("injected ledger failure")

    def test_run_census_raises_instead_of_empty_ledger(self, tmp_path, monkeypatch):
        """(witness d) Inject a compile_ledger failure at the top-level entry
        point. Pre-R3 this printed a WARNING, cached ledger=[] and returned a
        census whose KSFO slots were all NO_APPLICABLE_EVIDENCE."""
        bulk, cfg = self._setup(tmp_path)
        out = tmp_path / "OUT"
        monkeypatch.setattr(census, "compile_ledger", self._boom)

        with pytest.raises(census.LedgerCompilationError) as info:
            census.run_census(bulk, cfg, artifacts_dir=out)
        assert info.value.station == "KSFO"
        assert isinstance(info.value.cause, ValueError)
        # No slot summary claiming "no evidence" was ever written.
        assert not (out / "slot_summary.jsonl").exists()

    def test_main_maps_failure_to_hard_gate_exit_code_2(self, tmp_path, monkeypatch):
        bulk, cfg = self._setup(tmp_path)
        monkeypatch.setattr(census, "compile_ledger", self._boom)
        monkeypatch.setattr(sys, "argv", [
            "run_transition_census_v17.py", "--bulk-dir", str(bulk), "--config", str(cfg),
            "--out", str(tmp_path / "summary.json"),
        ])
        assert census.main() == 2
        assert not (tmp_path / "summary.json").exists()

    def test_per_slot_fallback_is_unresolved_not_no_evidence(self, monkeypatch):
        """The per-slot fallback (callers without station_ledgers) records
        compilation_error entries. Pre-R3 those AVAIL_UNKNOWN records fell
        through to NO_APPLICABLE_EVIDENCE + 'late_evidence_excluded_from_scoring'."""
        slot = _slot(0)
        baseline = _pkg(source_id="base", issued_at=-3 * HOUR_US, semantic_hash="hA")
        monkeypatch.setattr(census, "compile_ledger", self._boom)

        changes, status, flags, signals = _classify(slot, [baseline])
        assert [c.change_type for c in changes] == [census.CHANGE_TYPE_COMPILATION_ERROR]
        assert status == census.STATUS_UNRESOLVED
        assert flags == [census.FLAG_LEDGER_COMPILATION_ERROR]
        assert "late_evidence_excluded_from_scoring" not in flags
        assert signals["ledger_compilation_error"] is True
        assert signals["any_new_arrival_in_scoring_window"] is False


# ---------------------------------------------------------------------------
# R4 -- prefix-unresolved vs scoring-window-unresolved are distinct findings
# ---------------------------------------------------------------------------

class TestR4UnresolvedSplit:
    """Two same-instant AMDs with no receipt signal: each sees the other as
    its latest prior candidate, so resolve_receipt_tie_strict cannot pick a
    winner -> relation_status 'unresolved' on both (ledger A2-2 contract)."""

    def _tie_pair(self, issued_at):
        return [
            _pkg(source_id="amdG", issued_at=issued_at, semantic_hash="hG", amendment_kind="AMD"),
            _pkg(source_id="amdH", issued_at=issued_at, semantic_hash="hH", amendment_kind="AMD"),
        ]

    def test_unresolved_only_in_initial_prefix(self):
        """(witness e, prefix) Tie issued T-2h -> available T-118min <= T-60
        -> INITIAL_PREFIX. Nothing arrives in the window."""
        slot = _slot(0)
        base = _pkg(source_id="base", issued_at=-5 * HOUR_US, semantic_hash="hA")
        changes, status, flags, signals = _classify(slot, [base] + self._tie_pair(-2 * HOUR_US))

        tie = [c for c in changes if c.current_source_id in ("amdG", "amdH")]
        assert {c.relation_status for c in tie} == {"unresolved"}
        assert {c.checkpoint_classification for c in tie} == {census.AVAIL_INITIAL_PREFIX}

        assert status == census.STATUS_UNRESOLVED  # documented fail-closed scope
        assert flags == [census.FLAG_UNRESOLVED_IN_INITIAL_PREFIX]
        assert signals["unresolved_in_initial_prefix"] is True
        assert signals["unresolved_in_scoring_window"] is False
        assert signals["any_new_arrival_in_scoring_window"] is False

    def test_unresolved_only_in_scoring_window(self):
        """(witness e, window) Tie issued T-27min -> available T-25min, in
        (T-40, T-20] -> INTERVAL_2."""
        slot = _slot(0)
        base = _pkg(source_id="base", issued_at=-5 * HOUR_US, semantic_hash="hA")
        changes, status, flags, signals = _classify(slot, [base] + self._tie_pair(-27 * MIN_US))

        tie = [c for c in changes if c.current_source_id in ("amdG", "amdH")]
        assert {c.relation_status for c in tie} == {"unresolved"}
        assert {c.checkpoint_classification for c in tie} == {census.AVAIL_INTERVAL_2}

        assert status == census.STATUS_UNRESOLVED
        assert flags == [census.FLAG_UNRESOLVED_IN_SCORING_WINDOW]
        assert signals["unresolved_in_initial_prefix"] is False
        assert signals["unresolved_in_scoring_window"] is True
        assert signals["any_new_arrival_in_scoring_window"] is True
        assert signals["change_like_arrival_in_scoring_window"] is True

    def test_prefix_unresolved_does_not_hide_window_change(self):
        """Fail-closed status does not lose information: prefix tie + a clean
        AMD in the window -> status UNRESOLVED, but the change-like arrival is
        still reported by the independent signal and the flag says prefix."""
        slot = _slot(0)
        base = _pkg(source_id="base", issued_at=-5 * HOUR_US, semantic_hash="hA")
        clean_amd = _pkg(source_id="amdX", issued_at=-52 * MIN_US, semantic_hash="hX",
                         amendment_kind="AMD")
        changes, status, flags, signals = _classify(
            slot, [base, clean_amd] + self._tie_pair(-2 * HOUR_US),
        )
        by_id = {c.current_source_id: c for c in changes}
        assert by_id["amdX"].relation_status == "resolved"
        assert by_id["amdX"].checkpoint_classification == census.AVAIL_INTERVAL_1

        assert status == census.STATUS_UNRESOLVED
        assert flags == [census.FLAG_UNRESOLVED_IN_INITIAL_PREFIX]
        assert signals["change_like_arrival_in_scoring_window"] is True
        assert signals["unresolved_in_scoring_window"] is False


# ---------------------------------------------------------------------------
# Output wiring
# ---------------------------------------------------------------------------

class TestUncaughtFailureIsNotConflatedWithCompletedUnresolved:
    """A crash unrelated to ledger compilation must not silently collapse
    into exit 1 ('completed with UNRESOLVED slots') -- that would hide a
    real failure inside what looks like an ordinary, if imperfect, run."""

    STREAM = TestR3LedgerCompileFailureFailsClosed.STREAM

    def _setup(self, tmp_path):
        bulk = tmp_path / "bulk"
        _write_pair(bulk, "KSFO", "202301", self.STREAM)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(_config("2023-01-05T00:00:00Z", "2023-01-06T00:00:00Z")))
        return bulk, cfg

    def test_non_ledger_exception_returns_exit_code_3_not_1(self, tmp_path, monkeypatch):
        bulk, cfg = self._setup(tmp_path)

        def _boom(*_a, **_k):
            raise RuntimeError("injected unrelated crash")

        monkeypatch.setattr(census, "generate_continuous_calendar_slots", _boom)
        monkeypatch.setattr(sys, "argv", [
            "run_transition_census_v17.py", "--bulk-dir", str(bulk), "--config", str(cfg),
            "--out", str(tmp_path / "summary.json"),
        ])
        assert census.main() == 3
        assert not (tmp_path / "summary.json").exists()

    def test_crash_writing_the_summary_after_run_census_succeeds_also_returns_3(self, tmp_path, monkeypatch):
        """The first version of this fix only wrapped the run_census() call
        itself -- a crash anywhere AFTER it (here: --out pointing at a
        directory that doesn't exist, so the summary write raises
        FileNotFoundError) still fell through to Python's default exit 1,
        colliding with 'completed with UNRESOLVED slots'. Independent review
        proved this with exactly this reproduction."""
        bulk, cfg = self._setup(tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "run_transition_census_v17.py", "--bulk-dir", str(bulk), "--config", str(cfg),
            "--out", str(tmp_path / "does_not_exist_dir" / "summary.json"),
        ])
        assert census.main() == 3


class TestSummaryWiring:
    def test_run_status_field_reflects_clean_vs_unresolved(self, tmp_path, monkeypatch):
        bulk = tmp_path / "bulk"
        _write_pair(bulk, "KSFO", "202301", TestR3LedgerCompileFailureFailsClosed.STREAM)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(_config("2023-01-05T00:00:00Z", "2023-01-06T00:00:00Z")))
        out = tmp_path / "summary.json"
        monkeypatch.setattr(sys, "argv", [
            "run_transition_census_v17.py", "--bulk-dir", str(bulk), "--config", str(cfg),
            "--out", str(out),
        ])
        exit_code = census.main()
        summary = json.loads(out.read_text())
        # This fixture only ever writes 1 of the 140 allow-listed files, so the
        # file-integrity gate legitimately fires (exit 2) -- the point of this
        # test is only that run_status mirrors whichever exit code actually
        # happened, not to force a specific one.
        expected_by_exit_code = {
            2: "HARD_FAILURE_FILE_INTEGRITY",
            1: "COMPLETED_WITH_UNRESOLVED",
            0: "COMPLETED_CLEAN",
        }
        assert "run_status" in summary
        assert summary["run_status"] == expected_by_exit_code[exit_code]

    def test_run_status_field_covers_clean_and_unresolved_not_just_file_integrity(self, tmp_path, monkeypatch):
        """The test above only ever exercises the file-integrity branch
        (exit 2), since its fixture is deliberately incomplete -- a
        realistic all-140-files fixture is too heavy to build just to reach
        the other two branches. Get a real CensusResult once, then use
        dataclasses.replace to reach the other two run_status values
        directly, so all three are actually exercised (independent review
        finding)."""
        from dataclasses import replace

        bulk = tmp_path / "bulk"
        _write_pair(bulk, "KSFO", "202301", TestR3LedgerCompileFailureFailsClosed.STREAM)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(_config("2023-01-05T00:00:00Z", "2023-01-06T00:00:00Z")))
        real_result = census.run_census(bulk, cfg, artifacts_dir=None)

        for unresolved_count, expected_status, expected_exit in (
            (0, "COMPLETED_CLEAN", 0),
            (1, "COMPLETED_WITH_UNRESOLVED", 1),
        ):
            fake_result = replace(
                real_result, files_missing=[], files_hash_mismatch=[],
                n_targets_with_unresolved=unresolved_count,
            )
            monkeypatch.setattr(census, "run_census", lambda *a, **k: fake_result)
            out = tmp_path / f"summary_{expected_exit}.json"
            monkeypatch.setattr(sys, "argv", [
                "run_transition_census_v17.py", "--bulk-dir", str(bulk), "--config", str(cfg),
                "--out", str(out),
            ])
            assert census.main() == expected_exit
            assert json.loads(out.read_text())["run_status"] == expected_status
    def test_ledger_shared_across_slots_matches_per_slot_fallback(self):
        """Signals are identical whether run_census's shared station ledger
        or the per-slot fallback compile is used."""
        slot = _slot(0)
        pkgs = [
            _pkg(source_id="base", issued_at=-3 * HOUR_US, semantic_hash="hA"),
            _pkg(source_id="routine", issued_at=-52 * MIN_US, semantic_hash="hB"),
        ]
        shared = census.classify_changes_for_slot(
            slot, {"KSFO": pkgs}, station_ledgers={"KSFO": compile_ledger(pkgs)},
        )
        fallback = census.classify_changes_for_slot(slot, {"KSFO": pkgs})
        assert census.compute_slot_signals(shared) == census.compute_slot_signals(fallback)
