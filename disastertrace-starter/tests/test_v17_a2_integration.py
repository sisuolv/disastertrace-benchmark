"""A2-5 end-to-end synthetic counterexample acceptance (V17 batch A2).

Builds ONE synthetic AFOS/TAF bulk archive file pair (KSFO_202301.body/.json,
10 hand-crafted frames) covering seven named scenarios -- initial prefix,
in-episode AMD, late evidence, duplicate, unresolved equal-BBB tie, no-change
target, adjacent-context-only target -- and drives it through the REAL census
entry point (scripts/run_transition_census_v17.run_census), not a
reimplementation or a mock.

Expected values below are hand-derived from the decision trees in
tie_resolution.py, ledger.py and run_transition_census_v17.py (episode
compiler receipt_seq rule, DEFAULT_DECLARED_LAG_US=120s availability lag,
_CHECKPOINT_EXPOSURE_WEIGHT table, _compute_slot_status branches) -- they are
not copied from a prior run of the code under test. See the task's
BATCH_A2_PROGRESS.md A2-5 entry for the full by-hand derivation.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from unittest import mock

import pytest

_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))
sys.path.insert(0, str(_project / "scripts"))

from disastertrace.revision_v1.access_policy import (  # noqa: E402
    AccessPolicy,
    AccessPolicyViolation,
    read_verified_allowed_file,
)
from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream  # noqa: E402
from disastertrace.revision_v1.ledger import compile_ledger, visible_at  # noqa: E402

from run_transition_census_v17 import (  # noqa: E402
    ALLOWED_YEAR_MONTHS,
    STATUS_NO_INPUT,
    STATUS_NO_APPLICABLE_EVIDENCE,
    STATUS_INITIAL_ONLY_NO_CHANGE,
    STATUS_IN_EPISODE_CHANGE,
    STATUS_UNRESOLVED,
    run_census,
)


SOH = "\x01"
ETX = "\x03"
_HOUR_US = 3600_000_000
_JAN5_2023_00Z_US = 1672876800_000_000  # 2023-01-05T00:00:00Z, hand-computed


def _frame(seq: str, wmo_header: str, pil: str, body_line: str) -> str:
    return f"{SOH}{seq}\n{wmo_header}\n{pil}\n{body_line}{ETX}\n"


def _us(day: int, hour: int) -> int:
    """Absolute microseconds for 2023-01-<day> <hour>:00 UTC."""
    return _JAN5_2023_00Z_US + (day - 5) * 24 * _HOUR_US + hour * _HOUR_US


# 10 hand-crafted frames in *file order* (episode_compiler.py:
# receipt_seq = len(frames) - 1 - frame_index, so file position 0 gets the
# highest receipt_seq / "most recently received"). Scenario labels below are
# the same seven scenarios validated against the real entry point in scratch
# testing before this file was written.
_FRAMES = [
    _frame("010", "FTUS41 KSFO 061110", "TAFSFO",
           "TAF KSFO 061110Z 0612/0613 24012KT P6SM SCT025="),          # scenario6 no-change, seq9
    _frame("009", "FTUS41 KSFO 060500", "TAFSFO",
           "TAF KSFO 060500Z 0617/0618 23008KT P6SM FEW030="),          # scenario7 adjacent-only, seq8
    _frame("008", "FTUS41 KSFO 052330 AAA", "TAFSFO",
           "TAF AMD KSFO 052330Z 0600/0601 25012KT P6SM SCT020="),      # scenario5 G (tie), seq7
    _frame("007", "FTUS41 KSFO 052330 AAA", "TAFSFO",
           "TAF AMD KSFO 052330Z 0600/0601 27018KT P5SM BKN030="),      # scenario5 H (tie), seq6
    _frame("006", "FTUS41 KSFO 051150", "TAFSFO",
           "TAF KSFO 051150Z 0512/0513 26014KT P6SM BKN020="),          # scenario3 late, seq5
    _frame("005", "FTUS41 KSFO 051000", "TAFSFO",
           "TAF KSFO 051000Z 0518/0519 25015KT P6SM BKN025="),          # scenario4 C (dup), seq4
    _frame("004", "FTUS41 KSFO 051000", "TAFSFO",
           "TAF KSFO 051000Z 0518/0519 25015KT P6SM BKN025="),          # scenario4 D (dup canonical), seq3
    _frame("003", "FTUS41 KSFO 050510", "TAFSFO",
           "TAF AMD KSFO 050510Z 0506/0507 24016KT P6SM SCT015="),      # scenario2 E (AMD), seq2
    _frame("002", "FTUS41 KSFO 041200", "TAFSFO",
           "TAF KSFO 041200Z 0506/0507 22010KT P6SM SCT025="),          # scenario2 B (baseline), seq1
    _frame("001", "FTUS41 KSFO 030000", "TAFSFO",
           "TAF KSFO 030000Z 0500/0501 25010KT P6SM SCT020="),          # scenario1 A (baseline), seq0
]
STREAM_TEXT = "".join(_FRAMES)

CONFIG = {
    "calendar_start": "2023-01-05T00:00:00Z",
    "calendar_end": "2023-01-08T00:00:00Z",
    "holdout_exclusion": {
        "window_start": "2025-02-17T00:00:00Z",
        "window_end": "2025-02-24T00:00:00Z",
    },
}


def _write_bulk_dir(bulk_dir: Path, station: str = "KSFO", year_month: str = "202301",
                     stream_text: str = STREAM_TEXT) -> str:
    """Write a single verified synthetic (body, receipt) pair; return its sha256."""
    bulk_dir.mkdir(parents=True, exist_ok=True)
    body_bytes = stream_text.encode("utf-8")
    sha = hashlib.sha256(body_bytes).hexdigest()
    (bulk_dir / f"{station}_{year_month}.body").write_bytes(body_bytes)
    (bulk_dir / f"{station}_{year_month}.json").write_text(
        json.dumps({"sha256": sha, "station": station, "year_month": year_month})
    )
    return sha


def _write_config(config_path: Path, config: dict = CONFIG) -> None:
    config_path.write_text(json.dumps(config, indent=2))


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _slot_by_window(slots: list[dict], start_us: int, station: str = "KSFO") -> dict:
    matches = [s for s in slots if s["validity_start_us"] == start_us and s["station"] == station]
    assert len(matches) == 1, (
        f"expected exactly one {station} slot at {start_us}, got {len(matches)}"
    )
    return matches[0]


@pytest.fixture
def census_result(tmp_path):
    bulk_dir = tmp_path / "bulk"
    config_path = tmp_path / "config.json"
    artifacts_dir = tmp_path / "OUT"
    _write_bulk_dir(bulk_dir)
    _write_config(config_path)
    result = run_census(bulk_dir, config_path, artifacts_dir=artifacts_dir)
    return result, artifacts_dir, bulk_dir, config_path


# ---------------------------------------------------------------------------
# Core: seven scenarios via the real run_census() entry point
# ---------------------------------------------------------------------------

class TestSevenScenariosViaRealCensusEntryPoint:
    def test_scenario1_initial_prefix_no_change(self, census_result):
        _, artifacts_dir, *_ = census_result
        slot = _slot_by_window(_load_jsonl(artifacts_dir / "slot_summary.jsonl"), _us(5, 0))
        assert slot["status"] == STATUS_INITIAL_ONLY_NO_CHANGE
        assert slot["flags"] == []
        assert slot["change_types"] == ["INITIAL_BASELINE"]

    def test_scenario2_in_episode_amd(self, census_result):
        _, artifacts_dir, *_ = census_result
        slot = _slot_by_window(_load_jsonl(artifacts_dir / "slot_summary.jsonl"), _us(5, 6))
        assert slot["status"] == STATUS_IN_EPISODE_CHANGE
        assert slot["flags"] == []
        assert sorted(slot["change_types"]) == ["AMD", "INITIAL_BASELINE"]

        changes = _load_jsonl(artifacts_dir / "all_changes.jsonl")
        amd = [c for c in changes
               if c["target_validity_start_us"] == _us(5, 6) and c["change_type"] == "AMD"]
        assert len(amd) == 1
        amd = amd[0]
        assert amd["relation_status"] == "resolved"
        assert amd["relation_reason"] == "strictly_prior"
        assert amd["checkpoint_classification"] == "INTERVAL_1"
        assert len(amd["predecessor_source_ids"]) == 1

    def test_scenario3_late_evidence_excluded_from_scoring(self, census_result):
        _, artifacts_dir, *_ = census_result
        slot = _slot_by_window(_load_jsonl(artifacts_dir / "slot_summary.jsonl"), _us(5, 12))
        assert slot["status"] == STATUS_NO_APPLICABLE_EVIDENCE
        assert slot["flags"] == ["late_evidence_excluded_from_scoring"]

        changes = _load_jsonl(artifacts_dir / "all_changes.jsonl")
        late = [c for c in changes if c["target_validity_start_us"] == _us(5, 12)]
        assert len(late) == 1
        assert late[0]["checkpoint_classification"] == "AFTER_LAST_SCORE"

    def test_scenario4_duplicate_stays_no_change(self, census_result):
        _, artifacts_dir, *_ = census_result
        slot = _slot_by_window(_load_jsonl(artifacts_dir / "slot_summary.jsonl"), _us(5, 18))
        assert slot["status"] == STATUS_INITIAL_ONLY_NO_CHANGE
        assert slot["flags"] == []
        assert sorted(slot["change_types"]) == ["INITIAL_BASELINE", "mirror_duplicate"]

    def test_scenario5_unresolved_equal_bbb_tie(self, census_result):
        _, artifacts_dir, *_ = census_result
        slot = _slot_by_window(_load_jsonl(artifacts_dir / "slot_summary.jsonl"), _us(6, 0))
        assert slot["status"] == STATUS_UNRESOLVED
        assert slot["flags"] == []

        changes = _load_jsonl(artifacts_dir / "all_changes.jsonl")
        amd = [c for c in changes
               if c["target_validity_start_us"] == _us(6, 0) and c["change_type"] == "AMD"]
        assert len(amd) == 1
        amd = amd[0]
        assert amd["relation_status"] == "unresolved"
        assert amd["relation_reason"] == "equal_bbb_no_authority"
        assert amd["predecessor_source_ids"] == []

    def test_scenario6_no_change_target(self, census_result):
        _, artifacts_dir, *_ = census_result
        slot = _slot_by_window(_load_jsonl(artifacts_dir / "slot_summary.jsonl"), _us(6, 12))
        assert slot["status"] == STATUS_INITIAL_ONLY_NO_CHANGE
        assert slot["flags"] == []
        assert slot["change_types"] == ["INITIAL_BASELINE"]

    def test_scenario7_adjacent_context_only(self, census_result):
        _, artifacts_dir, *_ = census_result
        slot = _slot_by_window(_load_jsonl(artifacts_dir / "slot_summary.jsonl"), _us(6, 18))
        assert slot["status"] == STATUS_NO_APPLICABLE_EVIDENCE
        assert slot["flags"] == ["adjacent_only"]
        # The adjacent-context package is still recorded on the slot (it is
        # not dropped), it is simply excluded from status/exposure counting
        # because its relevance_tier is adjacent, not strict overlap.
        assert slot["num_changes"] == 1
        assert slot["change_types"] == ["INITIAL_BASELINE"]

        changes = _load_jsonl(artifacts_dir / "all_changes.jsonl")
        adjacent = [c for c in changes if c["target_validity_start_us"] == _us(6, 18)]
        assert len(adjacent) == 1
        assert adjacent[0]["relevance_tier"] == "adjacent_context"

    def test_background_ksfo_slots_are_no_applicable_evidence(self, census_result):
        _, artifacts_dir, *_ = census_result
        slots = _load_jsonl(artifacts_dir / "slot_summary.jsonl")
        ksfo_slots = [s for s in slots if s["station"] == "KSFO"]
        assert len(ksfo_slots) == 12  # 3 days x 4 routine hours
        background_starts = {_us(6, 6), _us(7, 0), _us(7, 6), _us(7, 12), _us(7, 18)}
        for s in ksfo_slots:
            if s["validity_start_us"] in background_starts:
                assert s["status"] == STATUS_NO_APPLICABLE_EVIDENCE
                assert s["flags"] == []
                assert s["num_changes"] == 0

    def test_other_stations_have_no_input(self, census_result):
        _, artifacts_dir, *_ = census_result
        slots = _load_jsonl(artifacts_dir / "slot_summary.jsonl")
        others = [s for s in slots if s["station"] != "KSFO"]
        assert len(others) == 36  # 3 other stations x 12 slots
        assert all(s["status"] == STATUS_NO_INPUT for s in others)
        assert all(s["flags"] == [] and s["num_changes"] == 0 for s in others)

    def test_full_census_summary_hand_derived(self, census_result):
        result, *_ = census_result
        assert result.total_continuous_calendar_slots == 48
        assert result.slots_by_status == {
            "NO_INPUT": 36,
            "NO_APPLICABLE_EVIDENCE": 7,
            "INITIAL_ONLY_NO_CHANGE": 3,
            "IN_EPISODE_CHANGE": 1,
            "UNRESOLVED": 1,
        }
        assert result.n_unique_sources == 10
        # scenario2's AMD (INTERVAL_1) + scenario5's AMD (INTERVAL_2, unresolved);
        # scenario5's H is new_observation/INITIAL_BASELINE, not change-like.
        assert result.n_target_change_associations == 2
        assert result.n_targets_with_initial_evidence == 3
        assert result.n_targets_with_in_episode_change == 1
        assert result.n_targets_with_unresolved == 1
        # exposure weights: INITIAL_PREFIX=3, INTERVAL_1=2, INTERVAL_2=1, AFTER_LAST_SCORE=0.
        # A=3 (s1 baseline), B=3 + E=2 (s2), late=0 (s3), D=3 + C=3 (s4),
        # G=1 + H=1 (s5, both strict-overlap despite the tie), scenario6=2 (INTERVAL_1).
        # 3 + 3+2 + 0 + 3+3 + 1+1 + 2 = 18
        assert result.n_checkpoint_exposures == 18
        assert result.n_candidate_blocks == 2  # (KSFO, Jan5) and (KSFO, Jan6)
        assert result.changes_by_type == {
            "INITIAL_BASELINE": 7,
            "AMD": 2,
            "mirror_duplicate": 1,
        }
        assert result.total_process_groups == 1
        assert result.total_packages_compiled == 10
        assert result.skipped_frames == 0
        assert result.files_checked == 140
        assert result.files_ok == 1
        assert len(result.files_missing) == 139
        assert result.files_hash_mismatch == []


# ---------------------------------------------------------------------------
# Runtime readset contains only the allowed synthetic input
# ---------------------------------------------------------------------------

class TestReadsetOnlyContainsAllowedSyntheticInput:
    def test_readset_exactly_one_record_scoped_to_tmp_bulk_dir(self, census_result):
        _, artifacts_dir, bulk_dir, _ = census_result
        readset = _load_jsonl(artifacts_dir / "input_readset.jsonl")
        assert len(readset) == 1
        rec = readset[0]
        assert rec["station"] == "KSFO"
        assert rec["year_month"] == "2023-01"
        resolved_bulk_dir = bulk_dir.resolve()
        assert Path(rec["canonical_body_path"]).is_relative_to(resolved_bulk_dir)
        assert Path(rec["canonical_receipt_path"]).is_relative_to(resolved_bulk_dir)

        blob = json.dumps(readset)
        assert "data_real_v16" not in blob
        assert "quarantine_holdout" not in blob

    def test_missing_139_files_reported_not_silently_dropped(self, census_result):
        result, *_ = census_result
        assert len(result.files_missing) == 139
        assert result.files_checked == 140
        assert result.files_ok == 1


# ---------------------------------------------------------------------------
# Rejection before read
# ---------------------------------------------------------------------------

class TestRejectionBeforeRead:
    def test_disallowed_month_path_rejected_before_any_open(self, tmp_path):
        """A file whose path-implied month is outside the 140-file allowlist
        (the protected 2025-02) must be rejected by AccessPolicy before any
        file is opened -- not discovered later via a failed parse. Mirrors
        the open/glob call-counting pattern in
        tests/test_revision_access_policy.py::TestShortCircuitVerification.
        """
        bulk_dir = tmp_path / "bulk"
        bulk_dir.mkdir()
        body_path = bulk_dir / "KSFO_202502.body"
        json_path = bulk_dir / "KSFO_202502.json"
        body_bytes = b"SHOULD NEVER BE READ"
        body_path.write_bytes(body_bytes)
        json_path.write_text(json.dumps({"sha256": hashlib.sha256(body_bytes).hexdigest()}))

        policy = AccessPolicy.from_config(
            CONFIG, allowed_root=bulk_dir, allowed_year_months=ALLOWED_YEAR_MONTHS,
        )

        opens: list[str] = []
        original_open = open

        def tracking_open(file, *args, **kwargs):
            opens.append(str(file))
            return original_open(file, *args, **kwargs)

        with mock.patch("builtins.open", tracking_open):
            with pytest.raises(AccessPolicyViolation):
                read_verified_allowed_file(policy, body_path, json_path)

        assert opens == [], f"expected zero opens before rejection, got {opens}"


# ---------------------------------------------------------------------------
# Order and future-suffix invariants
# ---------------------------------------------------------------------------

class TestOrderAndSuffixInvariants:
    def _packages(self, stream_text: str = STREAM_TEXT) -> list[dict]:
        packages, skipped = compile_afos_taf_stream(
            stream_text, station="KSFO", reference_month="2023-01",
        )
        assert skipped == []
        return packages

    def test_shuffled_input_order_yields_identical_ledger(self):
        packages = self._packages()
        ledger_a = compile_ledger(list(packages))

        shuffled = list(packages)
        rng = random.Random(20260921)
        rng.shuffle(shuffled)
        assert [p["source_id"] for p in shuffled] != [p["source_id"] for p in packages]

        ledger_b = compile_ledger(shuffled)

        by_id_a = {e["source_id"]: e for e in ledger_a}
        by_id_b = {e["source_id"]: e for e in ledger_b}
        assert by_id_a.keys() == by_id_b.keys()
        for source_id, entry_a in by_id_a.items():
            assert entry_a == by_id_b[source_id], (
                f"ledger entry for {source_id} depends on input order"
            )

    def test_appending_future_suffix_preserves_past_view(self):
        packages = self._packages()
        baseline_ledger = compile_ledger(list(packages))

        future_frame = _frame(
            "011", "FTUS41 KSFO 070000", "TAFSFO",
            "TAF KSFO 070000Z 0700/0701 24010KT P6SM SCT020=",
        )
        extended_text = future_frame + STREAM_TEXT
        extended_packages = self._packages(extended_text)
        assert len(extended_packages) == len(packages) + 1

        extended_ledger = compile_ledger(extended_packages)

        baseline_by_id = {e["source_id"]: e for e in baseline_ledger}
        extended_by_id = {e["source_id"]: e for e in extended_ledger}
        for source_id, entry in baseline_by_id.items():
            assert entry == extended_by_id[source_id], (
                f"appending a future frame changed past ledger entry {source_id}"
            )

        cutoff = _us(5, 0) - 60 * 60 * 1_000_000  # scenario1's T-60 checkpoint
        baseline_visible = {e["source_id"] for e in visible_at(baseline_ledger, cutoff=cutoff)}
        extended_visible = {e["source_id"] for e in visible_at(extended_ledger, cutoff=cutoff)}
        assert baseline_visible == extended_visible


# ---------------------------------------------------------------------------
# Missing fields must never be silently defaulted to 0
# ---------------------------------------------------------------------------

class TestMissingFieldsNotDefaultedToZero:
    def test_premise_violation_strips_receipt_fields_entirely(self):
        # frame 0 (file position 0) is issued EARLIER than frame 1 -- this
        # violates the D1 premise (file order must be non-increasing in
        # issued_at); the whole stream must lose receipt_seq/receipt_stream.
        bad_stream = (
            _frame("002", "FTUS41 KSFO 050000", "TAFSFO",
                   "TAF KSFO 050000Z 0500/0501 25010KT P6SM SCT020=")
            + _frame("001", "FTUS41 KSFO 060000", "TAFSFO",
                     "TAF KSFO 060000Z 0600/0601 25010KT P6SM SCT020=")
        )
        packages, skipped = compile_afos_taf_stream(
            bad_stream, station="KSFO", reference_month="2023-01",
        )
        assert skipped == []
        assert len(packages) == 2
        for pkg in packages:
            # Must be entirely ABSENT, never silently defaulted to 0 (which
            # would masquerade as a valid, highest-priority receipt position
            # and corrupt downstream tie resolution).
            assert "receipt_seq" not in pkg
            assert "receipt_stream" not in pkg


# ---------------------------------------------------------------------------
# Conflict positive control penetrates to the top-level summary
# ---------------------------------------------------------------------------

class TestConflictPositiveControlPenetratesToSummary:
    def test_unresolved_tie_reaches_top_level_summary_count(self, census_result):
        result, artifacts_dir, *_ = census_result
        assert result.n_targets_with_unresolved > 0
        assert result.slots_by_status["UNRESOLVED"] == 1

        changes = _load_jsonl(artifacts_dir / "all_changes.jsonl")
        unresolved = [c for c in changes if c["relation_status"] == "unresolved"]
        assert len(unresolved) == 1
        assert unresolved[0]["relation_reason"] == "equal_bbb_no_authority"
        assert unresolved[0]["target_validity_start_us"] == _us(6, 0)


# ---------------------------------------------------------------------------
# Digest reproducibility
# ---------------------------------------------------------------------------

class TestDigestReproducibility:
    def test_readset_fingerprint_reproducible_across_runs(self, tmp_path):
        bulk_dir = tmp_path / "bulk"
        config_path = tmp_path / "config.json"
        _write_bulk_dir(bulk_dir)
        _write_config(config_path)

        artifacts_1 = tmp_path / "OUT1"
        artifacts_2 = tmp_path / "OUT2"
        run_census(bulk_dir, config_path, artifacts_dir=artifacts_1)
        run_census(bulk_dir, config_path, artifacts_dir=artifacts_2)

        fp1 = json.loads((artifacts_1 / "input_fingerprint.json").read_text())
        fp2 = json.loads((artifacts_2 / "input_fingerprint.json").read_text())
        assert fp1["readset_digest_sha256"] == fp2["readset_digest_sha256"]
        assert fp1["n_files"] == fp2["n_files"] == 1
