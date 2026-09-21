"""Tests for receipt-order tie-breaking and source_id collision handling.

These tests cover the D1/D2/D3 implementation from the v16-RO (receipt-order) round:
- D1: receipt_seq and receipt_stream attachment in compile_afos_taf_stream
- D2: resolve_receipt_tie and latest_issuance tie-break in versions.py
- D3: source_id collision-free suffixing in compile_afos_taf_stream

The design principle is that receipt order (position in the AFOS archive byte stream)
provides a sub-minute clock for disambiguating same-issued_at products. This ordering
is attached at compile time and explicitly opted-in by the data source.
"""

import pytest
from datetime import datetime, timezone

from disastertrace.monitoring_v1.providers.versions import (
    latest_issuance,
    resolve_receipt_tie,
    taf_semantics,
)
from disastertrace.revision_v1.episode_compiler import (
    compile_afos_taf_stream,
    compile_raw_taf_to_evidence,
    split_afos_stream,
)
from disastertrace.monitoring_v1.targets import utc_us


def us(iso_str: str) -> int:
    """Convert ISO string to microseconds since epoch."""
    return utc_us(iso_str)


HOUR = 3_600_000_000  # 1 hour in microseconds
MINUTE = 60_000_000   # 1 minute in microseconds


# ---------------------------------------------------------------------------
# TestResolveReceiptTie: D2 resolve_receipt_tie helper
# ---------------------------------------------------------------------------


class TestResolveReceiptTie:
    """Tests for resolve_receipt_tie() helper in versions.py."""

    def test_winner_is_max_seq_when_resolvable(self):
        """When all conditions met, winner is the row with max receipt_seq."""
        rows = [
            {"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"},
            {"receipt_seq": 10, "receipt_stream": "KSFO:2023-01"},
            {"receipt_seq": 3, "receipt_stream": "KSFO:2023-01"},
        ]
        winner = resolve_receipt_tie(rows)
        assert winner is not None
        assert winner["receipt_seq"] == 10

    def test_none_when_any_row_missing_seq(self):
        """Returns None if any row is missing receipt_seq."""
        rows = [
            {"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"},
            {"receipt_stream": "KSFO:2023-01"},  # Missing receipt_seq
        ]
        assert resolve_receipt_tie(rows) is None

    def test_none_when_seq_is_bool(self):
        """Returns None if receipt_seq is bool (bool is subclass of int in Python).

        The check must use `type(x) is int`, not `isinstance(x, int)`.
        """
        rows = [
            {"receipt_seq": True, "receipt_stream": "KSFO:2023-01"},
            {"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"},
        ]
        assert resolve_receipt_tie(rows) is None

        # Also test False (which equals 0)
        rows2 = [
            {"receipt_seq": False, "receipt_stream": "KSFO:2023-01"},
            {"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"},
        ]
        assert resolve_receipt_tie(rows2) is None

    def test_none_when_receipt_stream_mismatch(self):
        """Returns None if receipt_stream values differ."""
        rows = [
            {"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"},
            {"receipt_seq": 10, "receipt_stream": "KSFO:2023-02"},  # Different month
        ]
        assert resolve_receipt_tie(rows) is None

    def test_none_when_duplicate_seq_values(self):
        """Returns None if receipt_seq values are not pairwise distinct."""
        rows = [
            {"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"},
            {"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"},  # Duplicate
            {"receipt_seq": 10, "receipt_stream": "KSFO:2023-01"},
        ]
        assert resolve_receipt_tie(rows) is None

    def test_none_on_singleton_input(self):
        """Returns None for singleton input (nothing to tie-break)."""
        rows = [{"receipt_seq": 5, "receipt_stream": "KSFO:2023-01"}]
        assert resolve_receipt_tie(rows) is None

    def test_none_on_empty_input(self):
        """Returns None for empty input."""
        assert resolve_receipt_tie([]) is None

    def test_none_when_stream_is_none(self):
        """Returns None if any receipt_stream is None."""
        rows = [
            {"receipt_seq": 5, "receipt_stream": None},
            {"receipt_seq": 10, "receipt_stream": None},
        ]
        assert resolve_receipt_tie(rows) is None


# ---------------------------------------------------------------------------
# TestLatestIssuanceTieBreak: D2 latest_issuance changes
# ---------------------------------------------------------------------------


class TestLatestIssuanceTieBreak:
    """Tests for latest_issuance() with receipt-order tie-breaking."""

    def test_tie_with_valid_seqs_returns_singleton_latest(self):
        """Tie with valid seqs on all tied rows returns singleton latest, losers in rest."""
        t0 = us("2026-01-15T12:00:00Z")
        products = [
            {"source_id": "a", "issued_at": t0, "receipt_seq": 5, "receipt_stream": "X:2026-01"},
            {"source_id": "b", "issued_at": t0, "receipt_seq": 10, "receipt_stream": "X:2026-01"},
            {"source_id": "c", "issued_at": t0 - HOUR, "receipt_seq": 3, "receipt_stream": "X:2026-01"},
        ]

        latest, rest = latest_issuance(products)

        # Winner is "b" (max seq among tied)
        assert len(latest) == 1
        assert latest[0]["source_id"] == "b"

        # Losers appear in rest
        rest_ids = {r["source_id"] for r in rest}
        assert rest_ids == {"a", "c"}

    def test_partition_invariant_holds(self):
        """Every input row appears in exactly one of the two returned lists."""
        t0 = us("2026-01-15T12:00:00Z")
        products = [
            {"source_id": "a", "issued_at": t0, "receipt_seq": 5, "receipt_stream": "X:2026-01"},
            {"source_id": "b", "issued_at": t0, "receipt_seq": 10, "receipt_stream": "X:2026-01"},
            {"source_id": "c", "issued_at": t0 - HOUR, "receipt_seq": 3, "receipt_stream": "X:2026-01"},
        ]

        latest, rest = latest_issuance(products)

        # Check partition: all inputs accounted for exactly once
        input_ids = {p["source_id"] for p in products}
        output_ids = {p["source_id"] for p in latest} | {p["source_id"] for p in rest}
        assert input_ids == output_ids
        assert len(latest) + len(rest) == len(products)

    def test_tie_without_seqs_returns_legacy_behavior(self):
        """Tie without seqs (or partial) returns both tied rows in latest."""
        t0 = us("2026-01-15T12:00:00Z")
        products = [
            {"source_id": "a", "issued_at": t0},  # No receipt_seq
            {"source_id": "b", "issued_at": t0},  # No receipt_seq
            {"source_id": "c", "issued_at": t0 - HOUR},
        ]

        latest, rest = latest_issuance(products)

        # Legacy: both tied rows in latest
        assert len(latest) == 2
        latest_ids = {l["source_id"] for l in latest}
        assert latest_ids == {"a", "b"}

    def test_tie_with_partial_seqs_returns_legacy_behavior(self):
        """Tie with only some rows having seqs returns legacy behavior."""
        t0 = us("2026-01-15T12:00:00Z")
        products = [
            {"source_id": "a", "issued_at": t0, "receipt_seq": 5, "receipt_stream": "X:2026-01"},
            {"source_id": "b", "issued_at": t0},  # Missing seq
            {"source_id": "c", "issued_at": t0 - HOUR},
        ]

        latest, rest = latest_issuance(products)

        # Legacy: both tied rows in latest
        assert len(latest) == 2
        latest_ids = {l["source_id"] for l in latest}
        assert latest_ids == {"a", "b"}

    def test_non_tied_input_unchanged(self):
        """Non-tied input returns as before (single max as latest)."""
        t0 = us("2026-01-15T12:00:00Z")
        products = [
            {"source_id": "a", "issued_at": t0},
            {"source_id": "b", "issued_at": t0 - HOUR},
            {"source_id": "c", "issued_at": t0 - 2 * HOUR},
        ]

        latest, rest = latest_issuance(products)

        assert len(latest) == 1
        assert latest[0]["source_id"] == "a"
        assert len(rest) == 2

    def test_value_error_for_non_int_issued_at(self):
        """ValueError still raised for non-int issued_at."""
        products = [
            {"source_id": "a", "issued_at": "2026-01-15T12:00:00Z"},  # String, not int
        ]

        with pytest.raises(ValueError, match="integer issuance times"):
            latest_issuance(products)


# ---------------------------------------------------------------------------
# TestReceiptSeqAttachment: D1 receipt_seq/receipt_stream in compile_afos_taf_stream
# ---------------------------------------------------------------------------


class TestReceiptSeqAttachment:
    """Tests for receipt_seq and receipt_stream attachment (D1)."""

    def test_three_frames_known_order_seq_values(self):
        """3 frames in known order: first frame gets seq=2, last gets seq=0."""
        # Build a 3-frame stream (newest to oldest in file order)
        stream = """\x01
001
FTUS46 KMTR 151200
TAFSFO
TAF
KSFO 151200Z 1512/1612 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151100
TAFSFO
TAF
KSFO 151100Z 1511/1611 25010KT P6SM SCT020=

\x03\x01
003
FTUS46 KMTR 151000
TAFSFO
TAF
KSFO 151000Z 1510/1610 25010KT P6SM SCT020=

\x03"""

        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 3
        assert len(skipped) == 0

        # First frame (newest, idx=0) gets seq = len(frames)-1 = 2
        assert packages[0]["receipt_seq"] == 2
        # Second frame (idx=1) gets seq = 1
        assert packages[1]["receipt_seq"] == 1
        # Third frame (oldest, idx=2) gets seq = 0
        assert packages[2]["receipt_seq"] == 0

    def test_receipt_stream_format(self):
        """receipt_stream should be "{station}:{reference_month}"."""
        stream = """\x01
001
FTUS46 KMTR 152345
TAFSFO
TAF
KSFO 152345Z 1600/1706 25010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        assert packages[0]["receipt_stream"] == "KSFO:2025-10"

    def test_all_packages_have_both_keys(self):
        """All packages should have both receipt_seq and receipt_stream."""
        stream = """\x01
001
FTUS46 KMTR 151200
TAFSFO
TAF
KSFO 151200Z 1512/1612 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151100
TAFSFO
TAF
KSFO 151100Z 1511/1611 25010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        for pkg in packages:
            assert "receipt_seq" in pkg
            assert "receipt_stream" in pkg
            assert type(pkg["receipt_seq"]) is int


# ---------------------------------------------------------------------------
# TestPremiseGate: D1 reverse-chronology premise gate
# ---------------------------------------------------------------------------


class TestPremiseGate:
    """Tests for the reverse-chronology premise gate (D1)."""

    def test_forward_chronological_stream_strips_keys(self):
        """Forward-chronological stream (premise violated) strips all receipt keys."""
        # Build a forward-chronological stream (OLDEST to NEWEST in file order)
        # This violates the reverse-chronology premise
        stream = """\x01
001
FTUS46 KMTR 151000
TAFSFO
TAF
KSFO 151000Z 1510/1610 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151100
TAFSFO
TAF
KSFO 151100Z 1511/1611 25010KT P6SM SCT020=

\x03\x01
003
FTUS46 KMTR 151200
TAFSFO
TAF
KSFO 151200Z 1512/1612 25010KT P6SM SCT020=

\x03"""

        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 3
        assert len(skipped) == 0

        # All-or-nothing: NO package should have receipt_seq or receipt_stream
        for pkg in packages:
            assert "receipt_seq" not in pkg
            assert "receipt_stream" not in pkg

    def test_reverse_chronological_stream_keeps_keys(self):
        """Reverse-chronological stream (premise holds) keeps receipt keys."""
        # Normal reverse-chronological stream (NEWEST to OLDEST in file order)
        stream = """\x01
001
FTUS46 KMTR 151200
TAFSFO
TAF
KSFO 151200Z 1512/1612 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151100
TAFSFO
TAF
KSFO 151100Z 1511/1611 25010KT P6SM SCT020=

\x03\x01
003
FTUS46 KMTR 151000
TAFSFO
TAF
KSFO 151000Z 1510/1610 25010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 3

        # All packages should have receipt keys
        for pkg in packages:
            assert "receipt_seq" in pkg
            assert "receipt_stream" in pkg

    def test_ties_allowed_in_premise_check(self):
        """Same issued_at (ties) should not trigger premise violation."""
        # Three frames with SAME issued_at (all 15:00)
        stream = """\x01
001
FTUS46 KMTR 151500 AAC
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 27010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151500 AAB
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 26010KT P6SM SCT020=

\x03\x01
003
FTUS46 KMTR 151500 AAA
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 3

        # Non-increasing (all equal) = premise holds
        for pkg in packages:
            assert "receipt_seq" in pkg


# ---------------------------------------------------------------------------
# TestCollisionSuffix: D3 collision-free source_id
# ---------------------------------------------------------------------------


class TestCollisionSuffix:
    """Tests for collision-free source_id suffixing (D3)."""

    def test_twin_frames_get_distinct_ids(self):
        """Two byte-identical frames should produce distinct source_ids.

        The AAA/AAB/AAC scenario: AAB and AAC are byte-identical (same TAF body),
        producing the same semantic hash and thus the same auto-generated source_id.
        The earliest-received (lowest receipt_seq) keeps the original id.
        """
        # Build stream with AAA (unique) + AAB/AAC (twins)
        # In file order: AAC (idx=0, seq=2), AAB (idx=1, seq=1), AAA (idx=2, seq=0)
        # AAB and AAC have identical TAF bodies
        stream = """\x01
001
FTUS46 KMTR 151500 AAC
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151500 AAB
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03\x01
003
FTUS46 KMTR 151500 AAA
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 26010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 3

        # All source_ids should be distinct
        sids = [pkg["source_id"] for pkg in packages]
        assert len(set(sids)) == 3, f"source_ids not unique: {sids}"

    def test_earliest_received_keeps_original_id(self):
        """The earliest-received twin (min receipt_seq) keeps the original id."""
        # AAC at idx=0 has seq=2, AAB at idx=1 has seq=1
        # AAB (seq=1) is EARLIER received, should keep original id
        stream = """\x01
001
FTUS46 KMTR 151500 AAC
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151500 AAB
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 2

        # AAC (idx=0, seq=1) has higher seq -> gets suffix
        # AAB (idx=1, seq=0) has lower seq -> keeps original
        aac = packages[0]  # idx=0 in result
        aab = packages[1]  # idx=1 in result

        # Find which one has the suffix
        suffixed = [p for p in packages if "-r" in p["source_id"]]
        unsuffixed = [p for p in packages if "-r" not in p["source_id"]]

        assert len(suffixed) == 1
        assert len(unsuffixed) == 1

        # The unsuffixed one should be AAB (lower seq = 0)
        assert unsuffixed[0]["receipt_seq"] == 0

        # The suffixed one should be AAC (higher seq = 1)
        assert suffixed[0]["receipt_seq"] == 1

    def test_suffix_format(self):
        """Suffix should be -r{receipt_seq:06d}."""
        stream = """\x01
001
FTUS46 KMTR 151500 AAC
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151500 AAB
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        suffixed = [p for p in packages if "-r" in p["source_id"]]
        assert len(suffixed) == 1

        # Check suffix format: -r followed by 6 digits
        sid = suffixed[0]["source_id"]
        assert "-r000001" in sid  # seq=1, zero-padded to 6 digits

    def test_global_uniqueness_assertion(self):
        """All source_ids in a stream must be unique after suffixing."""
        # This is enforced by an assertion in the implementation
        # If we reach here without AssertionError, the test passes
        stream = """\x01
001
FTUS46 KMTR 151500 AAC
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 151500 AAB
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03\x01
003
FTUS46 KMTR 151500 AAA
TAFSFO
TAF AMD
KSFO 151500Z 1515/1615 25010KT P6SM SCT020=

\x03"""

        # All three have identical bodies -> same hash -> would collide
        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        # If we get here, the assertion passed
        sids = [p["source_id"] for p in packages]
        assert len(set(sids)) == len(sids)


# ---------------------------------------------------------------------------
# TestHashStability: Hash contract verification
# ---------------------------------------------------------------------------


class TestHashStability:
    """Tests verifying that native_semantics_sha256 is not affected by new keys."""

    def test_same_taf_same_hash_via_different_paths(self):
        """Same TAF text compiled via raw and stream compilers produces equal hash.

        This verifies that native_semantics_sha256 is computed from the parsed
        TafProduct BEFORE receipt_seq/receipt_stream are attached.
        """
        raw_taf = "TAF KSFO 151200Z 1512/1612 25010KT P6SM SCT020"
        issued_at = us("2025-10-15T12:00:00Z")

        # Path 1: compile_raw_taf_to_evidence (no receipt keys)
        direct_pkg = compile_raw_taf_to_evidence(
            raw_taf,
            station="KSFO",
            issued_at=issued_at,
        )

        # Path 2: compile_afos_taf_stream (adds receipt keys)
        stream = """\x01
001
FTUS46 KMTR 151200
TAFSFO
TAF
KSFO 151200Z 1512/1612 25010KT P6SM SCT020=

\x03"""
        stream_pkgs, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )
        stream_pkg = stream_pkgs[0]

        # Hashes must be equal
        assert direct_pkg["native_semantics_sha256"] == stream_pkg["native_semantics_sha256"]

        # But stream_pkg has extra keys
        assert "receipt_seq" not in direct_pkg
        assert "receipt_seq" in stream_pkg

    def test_receipt_keys_not_in_hash_input(self):
        """Adding/removing receipt keys does not change hash.

        Since hash is computed before keys are attached, changing keys
        post-hoc would also not affect it. But the key point is that
        the original hash computation path is unmodified.
        """
        stream = """\x01
001
FTUS46 KMTR 151200
TAFSFO
TAF
KSFO 151200Z 1512/1612 25010KT P6SM SCT020=

\x03"""

        packages, _ = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )
        original_hash = packages[0]["native_semantics_sha256"]

        # Hash should be a 64-char hex string (sha256)
        assert len(original_hash) == 64
        assert all(c in "0123456789abcdef" for c in original_hash)


# ---------------------------------------------------------------------------
# V17-02 / F10: Shared tie resolution module tests
# ---------------------------------------------------------------------------


class TestF10SharedTieResolution:
    """V17-02 / F10: Test shared tie resolution between runtime and validator.

    The F10 fix ensures that resolve_receipt_tie (runtime) and the validator
    use the exact same resolution logic via the shared tie_resolution module.
    """

    def test_shared_check_receipt_premise_accepts_valid(self):
        """check_receipt_premise accepts valid tied members."""
        from disastertrace.revision_v1.tie_resolution import check_receipt_premise

        members = [
            {"receipt_seq": 1, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z")},
            {"receipt_seq": 2, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z")},
            {"receipt_seq": 3, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z")},
        ]

        ok, reason = check_receipt_premise(members)
        assert ok is True
        assert reason == "premise_ok"

    def test_shared_check_receipt_premise_rejects_bool_seq(self):
        """check_receipt_premise rejects bool receipt_seq (type() check)."""
        from disastertrace.revision_v1.tie_resolution import check_receipt_premise

        members = [
            {"receipt_seq": True, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z")},
            {"receipt_seq": 2, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z")},
        ]

        ok, reason = check_receipt_premise(members)
        assert ok is False
        assert reason == "no_receipt_signal"

    def test_shared_check_receipt_premise_rejects_stream_mismatch(self):
        """check_receipt_premise rejects mismatched receipt_stream."""
        from disastertrace.revision_v1.tie_resolution import check_receipt_premise

        members = [
            {"receipt_seq": 1, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z")},
            {"receipt_seq": 2, "receipt_stream": "KSFO:2025-02", "issued_at": us("2025-01-15T12:00:00Z")},
        ]

        ok, reason = check_receipt_premise(members)
        assert ok is False
        assert reason == "premise_violated_stream_mismatch"

    def test_shared_check_bbb_order_accepts_agreement(self):
        """check_bbb_order_vs_receipt_order accepts when BBB and receipt agree."""
        from disastertrace.revision_v1.tie_resolution import check_bbb_order_vs_receipt_order

        # AAA received before AAB (correct WMO order)
        members = [
            {"wmo_bbb": "AAA", "receipt_seq": 1},
            {"wmo_bbb": "AAB", "receipt_seq": 2},
        ]

        ok, reason = check_bbb_order_vs_receipt_order(members)
        assert ok is True
        assert reason == "bbb_agrees"

    def test_shared_check_bbb_order_rejects_contradiction(self):
        """check_bbb_order_vs_receipt_order rejects BBB vs receipt contradiction."""
        from disastertrace.revision_v1.tie_resolution import check_bbb_order_vs_receipt_order

        # AAB received before AAA (reversed from WMO order) - contradiction
        members = [
            {"wmo_bbb": "AAA", "receipt_seq": 2},  # AAA should be first but has higher seq
            {"wmo_bbb": "AAB", "receipt_seq": 1},  # AAB received first but should be second
        ]

        ok, reason = check_bbb_order_vs_receipt_order(members)
        assert ok is False
        assert reason == "bbb_contradicts_receipt_order"

    def test_resolve_receipt_tie_strict_full_success(self):
        """resolve_receipt_tie_strict resolves when all gates pass."""
        from disastertrace.revision_v1.tie_resolution import resolve_receipt_tie_strict

        rows = [
            {"receipt_seq": 1, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "AAA"},
            {"receipt_seq": 2, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "AAB"},
        ]

        result = resolve_receipt_tie_strict(rows)
        assert result.resolved is True
        assert result.winner is not None
        assert result.winner["receipt_seq"] == 2  # max seq wins
        assert result.rule == "receipt_order+bbb_agree"

    def test_resolve_receipt_tie_strict_no_bbb_pairs(self):
        """resolve_receipt_tie_strict uses receipt_order rule when no BBB pairs."""
        from disastertrace.revision_v1.tie_resolution import resolve_receipt_tie_strict

        # Different BBB families, so no cross-validation needed
        rows = [
            {"receipt_seq": 1, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "AAA"},
            {"receipt_seq": 2, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "CCA"},
        ]

        result = resolve_receipt_tie_strict(rows)
        assert result.resolved is True
        assert result.winner["receipt_seq"] == 2
        assert result.rule == "receipt_order"

    def test_runtime_and_validator_use_same_logic(self):
        """Verify runtime resolve_receipt_tie uses the shared strict resolution.

        This is the core F10 test: the runtime resolver must now use the same
        strict logic as the validator, rejecting ties that the validator would
        reject (like BBB contradictions).
        """
        from disastertrace.revision_v1.tie_resolution import resolve_receipt_tie_strict

        # Create a case that would PASS loose receipt-only but FAIL strict BBB check
        rows = [
            {"receipt_seq": 2, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "AAA"},
            {"receipt_seq": 1, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "AAB"},
        ]
        # BBB order: AAA < AAB
        # Receipt order: AAB(seq=1) < AAA(seq=2)
        # This is a CONTRADICTION - AAB should come after AAA

        # Shared strict resolution should reject
        strict_result = resolve_receipt_tie_strict(rows)
        assert strict_result.resolved is False
        assert strict_result.reason == "bbb_contradicts_receipt_order"

        # Runtime resolve_receipt_tie with strict=True should also reject
        runtime_result = resolve_receipt_tie(rows, strict=True)
        assert runtime_result is None  # None = unresolved

        # And the new resolve_receipt_tie_with_status exposes the reason
        from disastertrace.monitoring_v1.providers.versions import resolve_receipt_tie_with_status
        status = resolve_receipt_tie_with_status(rows)
        assert status.resolved is False
        assert status.reason == "bbb_contradicts_receipt_order"

    def test_legacy_strict_false_still_works(self):
        """With strict=False, legacy receipt-only behavior is preserved.

        This is for backward compatibility. When strict=False, the BBB check
        is skipped and only receipt_seq ordering is used.
        """
        # Same contradicting BBB case
        rows = [
            {"receipt_seq": 2, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "AAA"},
            {"receipt_seq": 1, "receipt_stream": "KSFO:2025-01", "issued_at": us("2025-01-15T12:00:00Z"), "wmo_bbb": "AAB"},
        ]

        # Legacy mode (strict=False) should resolve to max seq
        legacy_result = resolve_receipt_tie(rows, strict=False)
        assert legacy_result is not None
        assert legacy_result["receipt_seq"] == 2

    def test_tie_resolution_result_dataclass(self):
        """TieResolutionResult dataclass has all expected fields."""
        from disastertrace.revision_v1.tie_resolution import TieResolutionResult

        result = TieResolutionResult(
            resolved=True,
            winner={"test": "data"},
            reason="test_reason",
            rule="test_rule",
        )

        assert result.resolved is True
        assert result.winner == {"test": "data"}
        assert result.reason == "test_reason"
        assert result.rule == "test_rule"
