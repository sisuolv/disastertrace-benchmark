"""Tests for episode_compiler.py (W2 task).

Test cases:
a) Normal chain: original -> AMD -> AMD
b) COR correction
c) CNL cancellation
d) Out-of-order arrival (earlier issued_at arriving after later one)
e) Exact duplicate report arriving twice
f) Revision-density audit with hand-computed expected counts
g) End-to-end test feeding compiler output into real ledger.py

T2 additions:
h) METAR observation parsing from ASOS CSV
i) METAR outcomes compilation with ternary logic
j) AFOS raw-text stream splitting and TAF compilation
k) Integration tests against real downloaded data
"""

import pytest
from datetime import datetime, timezone

from disastertrace.monitoring_v1.targets import utc_us
from disastertrace.revision_v1.episode_compiler import (
    compile_raw_reports_to_episode,
    compile_raw_taf_to_evidence,
    compute_revision_density,
    identify_stress_and_natural_subsets,
)
from disastertrace.revision_v1.ledger import compile_ledger


def us(iso_str: str) -> int:
    """Convert ISO string to microseconds since epoch."""
    return utc_us(iso_str)


HOUR = 3_600_000_000  # 1 hour in microseconds
MINUTE = 60_000_000   # 1 minute in microseconds


# ---------------------------------------------------------------------------
# Synthetic raw TAF text fixtures
# These match the format expected by aviation.py parse_taf
# ---------------------------------------------------------------------------


def make_taf_text(
    station: str,
    issue_ddhhmm: str,
    valid_start: str,
    valid_end: str,
    *,
    prefix: str = "",
    body: str = "27015KT 9999 SCT030",
    cnl: bool = False,
    nil: bool = False,
) -> str:
    """Generate synthetic TAF text in standard format.

    Args:
        station: ICAO station code (e.g., "KJFK")
        issue_ddhhmm: Issuance time as DDHHMM (e.g., "191200")
        valid_start: Validity start as DDHH (e.g., "1912")
        valid_end: Validity end as DDHH (e.g., "2012")
        prefix: Optional prefix ("AMD", "COR", or "")
        body: Forecast body text
        cnl: If True, generate a CNL (cancellation) TAF
        nil: If True, generate a NIL TAF

    Returns:
        TAF text string ready for parse_taf()
    """
    header = f"TAF {prefix} {station} {issue_ddhhmm}Z" if prefix else f"TAF {station} {issue_ddhhmm}Z"
    header = " ".join(header.split())  # Normalize whitespace

    if cnl:
        return f"{header} {valid_start}/{valid_end} CNL"
    if nil:
        return f"{header} {valid_start}/{valid_end} NIL"

    return f"{header} {valid_start}/{valid_end} {body}"


# ---------------------------------------------------------------------------
# Test: Normal chain (original -> AMD -> AMD)
# ---------------------------------------------------------------------------


class TestNormalAmendmentChain:
    """Test case (a): Normal chain of original -> AMD -> AMD."""

    def test_parse_original_taf(self):
        """Original TAF should parse correctly."""
        raw = make_taf_text("KJFK", "191200", "1912", "2012")
        issued_at = us("2026-09-19T12:00:00Z")

        package = compile_raw_taf_to_evidence(
            raw,
            station="KJFK",
            issued_at=issued_at,
        )

        assert package["station"] == "KJFK"
        assert package["issued_at"] == issued_at
        assert package["amendment_kind"] == "original"
        assert package["status"] == "active"
        assert "native_semantics_sha256" in package

    def test_parse_amd_taf(self):
        """AMD TAF should parse with amendment_kind='AMD'."""
        raw = make_taf_text("KJFK", "191300", "1912", "2012", prefix="AMD",
                           body="27020KT 8000 BKN020")
        issued_at = us("2026-09-19T13:00:00Z")

        package = compile_raw_taf_to_evidence(
            raw,
            station="KJFK",
            issued_at=issued_at,
        )

        assert package["station"] == "KJFK"
        assert package["amendment_kind"] == "AMD"
        assert package["status"] == "active"

    def test_three_report_chain_compiles_correctly(self):
        """A chain of original -> AMD -> AMD should compile to 3 packages."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KJFK", "191200", "1912", "2012"),
                "station": "KJFK",
                "issued_at": t0,
                "source_id": "kjfk-orig",
            },
            {
                "raw_text": make_taf_text("KJFK", "191300", "1912", "2012",
                                          prefix="AMD", body="27020KT 8000 BKN020"),
                "station": "KJFK",
                "issued_at": t0 + HOUR,
                "source_id": "kjfk-amd1",
            },
            {
                "raw_text": make_taf_text("KJFK", "191400", "1912", "2012",
                                          prefix="AMD", body="27025KT 6000 OVC015"),
                "station": "KJFK",
                "issued_at": t0 + 2 * HOUR,
                "source_id": "kjfk-amd2",
            },
        ]

        products, collector_times = compile_raw_reports_to_episode(reports)

        assert len(products) == 3
        assert products[0]["amendment_kind"] == "original"
        assert products[1]["amendment_kind"] == "AMD"
        assert products[2]["amendment_kind"] == "AMD"
        assert collector_times is None  # No received_at provided


# ---------------------------------------------------------------------------
# Test: COR correction
# ---------------------------------------------------------------------------


class TestCorrectionTaf:
    """Test case (b): COR correction."""

    def test_parse_cor_taf(self):
        """COR TAF should parse with amendment_kind='COR'."""
        raw = make_taf_text("KLAX", "191210", "1912", "2012", prefix="COR",
                           body="25010KT 9999 FEW025")
        issued_at = us("2026-09-19T12:10:00Z")

        package = compile_raw_taf_to_evidence(
            raw,
            station="KLAX",
            issued_at=issued_at,
        )

        assert package["amendment_kind"] == "COR"
        assert package["status"] == "active"

    def test_original_and_correction_chain(self):
        """Original followed by COR should have different semantic hashes."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KLAX", "191200", "1912", "2012",
                                          body="25010KT 9999 SCT030"),
                "station": "KLAX",
                "issued_at": t0,
                "source_id": "klax-orig",
            },
            {
                "raw_text": make_taf_text("KLAX", "191210", "1912", "2012",
                                          prefix="COR", body="25010KT 9999 FEW025"),
                "station": "KLAX",
                "issued_at": t0 + 10 * MINUTE,
                "source_id": "klax-cor",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)

        assert len(products) == 2
        assert products[0]["amendment_kind"] == "original"
        assert products[1]["amendment_kind"] == "COR"
        # Different body -> different semantic hash
        assert (products[0]["native_semantics_sha256"] !=
                products[1]["native_semantics_sha256"])


# ---------------------------------------------------------------------------
# Test: CNL cancellation
# ---------------------------------------------------------------------------


class TestCancellationTaf:
    """Test case (c): CNL cancellation."""

    def test_parse_cnl_taf(self):
        """CNL TAF should parse with status='canceled'."""
        raw = make_taf_text("KORD", "191300", "1912", "2012", cnl=True)
        issued_at = us("2026-09-19T13:00:00Z")

        package = compile_raw_taf_to_evidence(
            raw,
            station="KORD",
            issued_at=issued_at,
        )

        assert package["status"] == "canceled"
        # CNL has no clauses, so amendment_kind should still be detected
        # from the prefix (if any). Without AMD/COR prefix, it's original.
        assert package["amendment_kind"] == "original"

    def test_original_followed_by_cancellation(self):
        """Original followed by CNL should mark second as canceled."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KORD", "191200", "1912", "2012"),
                "station": "KORD",
                "issued_at": t0,
                "source_id": "kord-orig",
            },
            {
                "raw_text": make_taf_text("KORD", "191300", "1912", "2012", cnl=True),
                "station": "KORD",
                "issued_at": t0 + HOUR,
                "source_id": "kord-cnl",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)

        assert len(products) == 2
        assert products[0]["status"] == "active"
        assert products[1]["status"] == "canceled"


# ---------------------------------------------------------------------------
# Test: Out-of-order arrival
# ---------------------------------------------------------------------------


class TestOutOfOrderArrival:
    """Test case (d): Out-of-order arrival (earlier issued_at arriving later)."""

    def test_collector_first_seen_populated_for_late_arrival(self):
        """Reports with received_at should populate collector_first_seen."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KJFK", "191200", "1912", "2012"),
                "station": "KJFK",
                "issued_at": t0,
                "received_at": t0 + 2 * MINUTE,
                "source_id": "kjfk-orig",
            },
            {
                # AMD issued later but arrives "on time"
                "raw_text": make_taf_text("KJFK", "191300", "1912", "2012",
                                          prefix="AMD", body="27020KT 8000 BKN020"),
                "station": "KJFK",
                "issued_at": t0 + HOUR,
                "received_at": t0 + HOUR + 2 * MINUTE,
                "source_id": "kjfk-amd",
            },
            {
                # Older report arriving AFTER the AMD (out-of-order)
                "raw_text": make_taf_text("KJFK", "191230", "1912", "2012",
                                          body="27018KT 9000 SCT025"),
                "station": "KJFK",
                "issued_at": t0 + 30 * MINUTE,
                "received_at": t0 + 2 * HOUR,  # Arrives very late
                "source_id": "kjfk-late",
            },
        ]

        products, collector_times = compile_raw_reports_to_episode(reports)

        assert len(products) == 3
        assert collector_times is not None
        assert len(collector_times) == 3

        # Verify the late arrival has a later collector_first_seen
        # than the AMD even though its issued_at is earlier
        assert collector_times["kjfk-late"] > collector_times["kjfk-amd"]
        # But its issued_at is between orig and amd
        assert products[2]["issued_at"] < products[1]["issued_at"]

    def test_availability_basis_is_collector_first_seen(self):
        """When received_at is provided, availability_basis should be collector_first_seen."""
        raw = make_taf_text("KJFK", "191200", "1912", "2012")
        t0 = us("2026-09-19T12:00:00Z")

        package = compile_raw_taf_to_evidence(
            raw,
            station="KJFK",
            issued_at=t0,
            received_at=t0 + 5 * MINUTE,
        )

        assert "collector_first_seen" in package
        assert package["collector_first_seen"] == t0 + 5 * MINUTE


# ---------------------------------------------------------------------------
# Test: Exact duplicate arriving twice
# ---------------------------------------------------------------------------


class TestExactDuplicate:
    """Test case (e): Exact duplicate report arriving twice."""

    def test_identical_reports_produce_same_semantic_hash(self):
        """Two identical reports should produce the same semantic hash."""
        t0 = us("2026-09-19T12:00:00Z")
        raw = make_taf_text("KJFK", "191200", "1912", "2012")

        reports = [
            {
                "raw_text": raw,
                "station": "KJFK",
                "issued_at": t0,
                "received_at": t0 + 2 * MINUTE,
                "source_id": "kjfk-copy1",
            },
            {
                # Same raw text, same issued_at, different source_id
                "raw_text": raw,
                "station": "KJFK",
                "issued_at": t0,
                "received_at": t0 + 5 * MINUTE,  # Arrived slightly later
                "source_id": "kjfk-copy2",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)

        assert len(products) == 2
        # Same semantic content -> same hash
        assert (products[0]["native_semantics_sha256"] ==
                products[1]["native_semantics_sha256"])
        # But different source_ids
        assert products[0]["source_id"] != products[1]["source_id"]


# ---------------------------------------------------------------------------
# Test: Revision-density audit with hand-computed expected counts
# ---------------------------------------------------------------------------


class TestRevisionDensityAudit:
    """Test case (f): Revision-density audit with hand-computed counts."""

    def test_empty_products_returns_empty_dict(self):
        """Empty product list should return empty density dict."""
        result = compute_revision_density([])
        assert result == {}

    def test_single_original_no_revisions(self):
        """Single original TAF should have zero revision counts."""
        t0 = us("2026-01-15T12:00:00Z")

        products = [
            {
                "station": "KJFK",
                "issued_at": t0,
                "valid_start": t0,
                "valid_end": t0 + 6 * HOUR,
                "amendment_kind": "original",
                "status": "active",
            }
        ]

        result = compute_revision_density(products)

        assert "KJFK" in result
        assert "2026-01" in result["KJFK"]
        counts = result["KJFK"]["2026-01"]
        assert counts["amd"] == 0
        assert counts["cor"] == 0
        assert counts["cnl"] == 0
        assert counts["supersession"] == 0

    def test_hand_computed_density_fixture(self):
        """Verify density counts against hand-computed expectations.

        Fixture:
        - KJFK 2026-01:
            - 1 original (t0)
            - 2 AMDs (t0+1h, t0+2h) for same validity window
            - 1 COR (t0+3h) for same validity window
        - KLAX 2026-01:
            - 1 original (t0)
            - 1 AMD (t0+1h)
            - 1 CNL (t0+2h)

        Hand-computed expectations:
        - KJFK 2026-01:
            - amd: 2 (two AMDs)
            - cor: 1 (one COR)
            - cnl: 0
            - supersession: 3 (orig->AMD1, AMD1->AMD2, AMD2->COR)
        - KLAX 2026-01:
            - amd: 1
            - cor: 0
            - cnl: 1
            - supersession: 2 (orig->AMD, AMD->CNL)
        """
        t0 = us("2026-01-15T12:00:00Z")
        validity_start = t0
        validity_end = t0 + 6 * HOUR

        products = [
            # KJFK chain: orig -> AMD -> AMD -> COR
            {
                "station": "KJFK",
                "issued_at": t0,
                "valid_start": validity_start,
                "valid_end": validity_end,
                "amendment_kind": "original",
                "status": "active",
            },
            {
                "station": "KJFK",
                "issued_at": t0 + HOUR,
                "valid_start": validity_start,
                "valid_end": validity_end,
                "amendment_kind": "AMD",
                "status": "active",
            },
            {
                "station": "KJFK",
                "issued_at": t0 + 2 * HOUR,
                "valid_start": validity_start,
                "valid_end": validity_end,
                "amendment_kind": "AMD",
                "status": "active",
            },
            {
                "station": "KJFK",
                "issued_at": t0 + 3 * HOUR,
                "valid_start": validity_start,
                "valid_end": validity_end,
                "amendment_kind": "COR",
                "status": "active",
            },
            # KLAX chain: orig -> AMD -> CNL
            {
                "station": "KLAX",
                "issued_at": t0,
                "valid_start": validity_start,
                "valid_end": validity_end,
                "amendment_kind": "original",
                "status": "active",
            },
            {
                "station": "KLAX",
                "issued_at": t0 + HOUR,
                "valid_start": validity_start,
                "valid_end": validity_end,
                "amendment_kind": "AMD",
                "status": "active",
            },
            {
                "station": "KLAX",
                "issued_at": t0 + 2 * HOUR,
                "valid_start": validity_start,
                "valid_end": validity_end,
                "amendment_kind": "original",  # CNL doesn't have AMD/COR prefix
                "status": "canceled",
            },
        ]

        result = compute_revision_density(products)

        # KJFK assertions (hand-computed)
        kjfk = result["KJFK"]["2026-01"]
        assert kjfk["amd"] == 2, f"KJFK AMD count: expected 2, got {kjfk['amd']}"
        assert kjfk["cor"] == 1, f"KJFK COR count: expected 1, got {kjfk['cor']}"
        assert kjfk["cnl"] == 0, f"KJFK CNL count: expected 0, got {kjfk['cnl']}"
        assert kjfk["supersession"] == 3, f"KJFK supersession: expected 3, got {kjfk['supersession']}"

        # KLAX assertions (hand-computed)
        klax = result["KLAX"]["2026-01"]
        assert klax["amd"] == 1, f"KLAX AMD count: expected 1, got {klax['amd']}"
        assert klax["cor"] == 0, f"KLAX COR count: expected 0, got {klax['cor']}"
        assert klax["cnl"] == 1, f"KLAX CNL count: expected 1, got {klax['cnl']}"
        assert klax["supersession"] == 2, f"KLAX supersession: expected 2, got {klax['supersession']}"

    def test_multiple_months_grouped_correctly(self):
        """Events should be grouped by the correct month based on issued_at."""
        # January and February events
        jan_t = us("2026-01-15T12:00:00Z")
        feb_t = us("2026-02-15T12:00:00Z")
        validity_window = 6 * HOUR

        products = [
            # January original
            {
                "station": "KJFK",
                "issued_at": jan_t,
                "valid_start": jan_t,
                "valid_end": jan_t + validity_window,
                "amendment_kind": "original",
                "status": "active",
            },
            # February AMD (different validity window, so no supersession)
            {
                "station": "KJFK",
                "issued_at": feb_t,
                "valid_start": feb_t,
                "valid_end": feb_t + validity_window,
                "amendment_kind": "AMD",
                "status": "active",
            },
        ]

        result = compute_revision_density(products)

        assert "2026-01" in result["KJFK"]
        assert "2026-02" in result["KJFK"]

        # January: only original, no revisions
        assert result["KJFK"]["2026-01"]["amd"] == 0
        assert result["KJFK"]["2026-01"]["supersession"] == 0

        # February: one AMD, but no supersession (different validity window)
        assert result["KJFK"]["2026-02"]["amd"] == 1
        assert result["KJFK"]["2026-02"]["supersession"] == 0

    def test_stress_natural_subset_classification(self):
        """High-revision months should be classified as stress."""
        t0 = us("2026-01-15T12:00:00Z")
        validity_window = 6 * HOUR

        products = []
        # January: 1 original only (low density)
        products.append({
            "station": "KJFK",
            "issued_at": t0,
            "valid_start": t0,
            "valid_end": t0 + validity_window,
            "amendment_kind": "original",
            "status": "active",
        })

        # February: 10 AMDs for same validity window (high density)
        feb_t = us("2026-02-15T12:00:00Z")
        for i in range(10):
            products.append({
                "station": "KJFK",
                "issued_at": feb_t + i * HOUR,
                "valid_start": feb_t,
                "valid_end": feb_t + 24 * HOUR,
                "amendment_kind": "AMD" if i > 0 else "original",
                "status": "active",
            })

        density = compute_revision_density(products)
        subsets = identify_stress_and_natural_subsets(density)

        # January should be natural (low density)
        # February should be stress (high density: 9 AMDs + 9 supersessions)
        assert subsets["KJFK"]["2026-01"] == "natural"
        assert subsets["KJFK"]["2026-02"] == "stress"


# ---------------------------------------------------------------------------
# Test: End-to-end with real ledger.py
# ---------------------------------------------------------------------------


class TestEndToEndLedgerIntegration:
    """Test case (g): End-to-end test feeding compiler output to real ledger.py."""

    def test_compiler_output_accepted_by_ledger(self):
        """Compiler output should be accepted by ledger.compile_ledger()."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KJFK", "191200", "1912", "2012"),
                "station": "KJFK",
                "issued_at": t0,
                "source_id": "kjfk-orig",
            },
            {
                "raw_text": make_taf_text("KJFK", "191300", "1912", "2012",
                                          prefix="AMD", body="27020KT 8000 BKN020"),
                "station": "KJFK",
                "issued_at": t0 + HOUR,
                "source_id": "kjfk-amd",
            },
        ]

        products, collector_times = compile_raw_reports_to_episode(reports)

        # This should NOT raise - proves the shape is correct
        ledger = compile_ledger(products, collector_first_seen=collector_times)

        assert len(ledger) == 2
        # Verify ledger has expected structure
        for entry in ledger:
            assert "source_id" in entry
            assert "kind" in entry
            assert "available_at" in entry
            assert "availability_basis" in entry

    def test_ledger_classifies_amd_as_amendment_supersedes(self):
        """Ledger should classify AMD as amendment_supersedes."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KJFK", "191200", "1912", "2012"),
                "station": "KJFK",
                "issued_at": t0,
                "source_id": "kjfk-orig",
            },
            {
                "raw_text": make_taf_text("KJFK", "191300", "1912", "2012",
                                          prefix="AMD", body="27020KT 8000 BKN020"),
                "station": "KJFK",
                "issued_at": t0 + HOUR,
                "source_id": "kjfk-amd",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)
        ledger = compile_ledger(products)

        kinds = {e["source_id"]: e["kind"] for e in ledger}
        assert kinds["kjfk-orig"] == "new_observation"
        assert kinds["kjfk-amd"] == "amendment_supersedes"

    def test_ledger_classifies_cor_as_correction(self):
        """Ledger should classify COR as correction."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KLAX", "191200", "1912", "2012"),
                "station": "KLAX",
                "issued_at": t0,
                "source_id": "klax-orig",
            },
            {
                "raw_text": make_taf_text("KLAX", "191210", "1912", "2012",
                                          prefix="COR", body="25015KT 8000 FEW020"),
                "station": "KLAX",
                "issued_at": t0 + 10 * MINUTE,
                "source_id": "klax-cor",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)
        ledger = compile_ledger(products)

        kinds = {e["source_id"]: e["kind"] for e in ledger}
        assert kinds["klax-orig"] == "new_observation"
        assert kinds["klax-cor"] == "correction"

    def test_ledger_classifies_cnl_as_cancellation(self):
        """Ledger should classify CNL as cancellation."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KORD", "191200", "1912", "2012"),
                "station": "KORD",
                "issued_at": t0,
                "source_id": "kord-orig",
            },
            {
                "raw_text": make_taf_text("KORD", "191300", "1912", "2012", cnl=True),
                "station": "KORD",
                "issued_at": t0 + HOUR,
                "source_id": "kord-cnl",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)
        ledger = compile_ledger(products)

        kinds = {e["source_id"]: e["kind"] for e in ledger}
        assert kinds["kord-orig"] == "new_observation"
        assert kinds["kord-cnl"] == "cancellation"

    def test_ledger_classifies_duplicate_as_lossless_duplicate(self):
        """Ledger should classify exact duplicates as lossless_duplicate."""
        t0 = us("2026-09-19T12:00:00Z")
        raw = make_taf_text("KJFK", "191200", "1912", "2012")

        reports = [
            {
                "raw_text": raw,
                "station": "KJFK",
                "issued_at": t0,
                "source_id": "kjfk-copy1",
            },
            {
                "raw_text": raw,
                "station": "KJFK",
                "issued_at": t0,  # Same issued_at
                "source_id": "kjfk-copy2",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)
        ledger = compile_ledger(products)

        kinds = {e["source_id"]: e["kind"] for e in ledger}
        # First should be new_observation, second should be lossless_duplicate
        assert kinds["kjfk-copy1"] == "new_observation"
        assert kinds["kjfk-copy2"] == "lossless_duplicate"

    def test_ledger_classifies_late_arrival_as_late_superseded(self):
        """Ledger should classify late-arriving old version as late_superseded."""
        t0 = us("2026-09-19T12:00:00Z")

        reports = [
            {
                "raw_text": make_taf_text("KJFK", "191200", "1912", "2012"),
                "station": "KJFK",
                "issued_at": t0,
                "received_at": t0 + 2 * MINUTE,
                "source_id": "kjfk-orig",
            },
            {
                # AMD issued at t0+1h, received on time
                "raw_text": make_taf_text("KJFK", "191300", "1912", "2012",
                                          prefix="AMD", body="27020KT 8000 BKN020"),
                "station": "KJFK",
                "issued_at": t0 + HOUR,
                "received_at": t0 + HOUR + 2 * MINUTE,
                "source_id": "kjfk-amd",
            },
            {
                # Old version issued at t0+30min but arrives after AMD
                "raw_text": make_taf_text("KJFK", "191230", "1912", "2012",
                                          body="27018KT 9000 SCT025"),
                "station": "KJFK",
                "issued_at": t0 + 30 * MINUTE,
                "received_at": t0 + 2 * HOUR,  # Late arrival
                "source_id": "kjfk-late",
            },
        ]

        products, collector_times = compile_raw_reports_to_episode(reports)
        ledger = compile_ledger(products, collector_first_seen=collector_times)

        kinds = {e["source_id"]: e["kind"] for e in ledger}
        assert kinds["kjfk-orig"] == "new_observation"
        assert kinds["kjfk-amd"] == "amendment_supersedes"
        assert kinds["kjfk-late"] == "late_superseded"

    def test_verified_publication_availability_basis(self):
        """verified_publication should set availability_basis correctly."""
        t0 = us("2026-09-19T12:00:00Z")

        package = compile_raw_taf_to_evidence(
            make_taf_text("KJFK", "191200", "1912", "2012"),
            station="KJFK",
            issued_at=t0,
            verified_publication=t0 + 5 * MINUTE,
        )

        # Package should have verified_publication timestamp
        assert "verified_publication" in package
        assert package["verified_publication"] == t0 + 5 * MINUTE

        # Run through ledger to verify availability_basis
        ledger = compile_ledger([package])
        assert len(ledger) == 1
        assert ledger[0]["availability_basis"] == "verified_publication"

    def test_provider_field_propagates_correctly(self):
        """Provider field should propagate from raw reports to evidence packages."""
        t0 = us("2026-09-19T12:00:00Z")

        # Two different TAFs from different providers
        raw_nws = make_taf_text("KJFK", "191200", "1912", "2012")
        raw_aw = make_taf_text("KJFK", "191201", "1912", "2012")  # 1 minute later

        reports = [
            {
                "raw_text": raw_nws,
                "station": "KJFK",
                "issued_at": t0,
                "source_id": "nws-kjfk",
                "provider": "nws",
            },
            {
                "raw_text": raw_aw,
                "station": "KJFK",
                "issued_at": t0 + MINUTE,
                "source_id": "aw-kjfk",
                "provider": "aviationweather",
            },
        ]

        products, _ = compile_raw_reports_to_episode(reports)

        # Verify provider field is present
        assert products[0].get("provider") == "nws"
        assert products[1].get("provider") == "aviationweather"

        # Run through ledger to ensure no errors
        ledger = compile_ledger(products)
        assert len(ledger) == 2

    def test_mirror_detection_with_synthetic_products(self):
        """Mirror detection requires same semantic hash from different providers.

        Note: Since taf_semantics() includes issued_at in the hash, we cannot
        easily create two raw TAF texts that parse to the same semantic hash
        with different timestamps. This test uses synthetic products directly
        to verify the mirror detection logic.
        """
        from disastertrace.monitoring_v1.targets import canonical_hash

        t0 = us("2026-09-19T12:00:00Z")

        # Create synthetic products with same semantic hash but different providers
        shared_content = {"station": "KJFK", "body": "shared-content"}
        shared_hash = canonical_hash(shared_content)

        products = [
            {
                "source_id": "nws-kjfk",
                "station": "KJFK",
                "issued_at": t0,
                "valid_start": t0,
                "valid_end": t0 + 6 * HOUR,
                "amendment_kind": "original",
                "status": "active",
                "native_semantics_sha256": shared_hash,
                "provider": "nws",
            },
            {
                "source_id": "aw-kjfk",
                "station": "KJFK",
                "issued_at": t0 + MINUTE,  # Slightly later
                "valid_start": t0,
                "valid_end": t0 + 6 * HOUR,
                "amendment_kind": "original",
                "status": "active",
                "native_semantics_sha256": shared_hash,  # Same hash!
                "provider": "aviationweather",  # Different provider
            },
        ]

        ledger = compile_ledger(products)
        kinds = {e["source_id"]: e["kind"] for e in ledger}

        # First is new_observation, second is mirror (same hash, different provider)
        assert kinds["nws-kjfk"] == "new_observation"
        assert kinds["aw-kjfk"] == "mirror"


# ---------------------------------------------------------------------------
# Test: Availability basis determination
# ---------------------------------------------------------------------------


class TestAvailabilityBasis:
    """Test availability_basis determination logic."""

    def test_declared_lag_when_no_timestamps(self):
        """Default to declared_lag when no timestamps provided."""
        package = compile_raw_taf_to_evidence(
            make_taf_text("KJFK", "191200", "1912", "2012"),
            station="KJFK",
            issued_at=us("2026-09-19T12:00:00Z"),
        )

        # Run through ledger with default lag
        ledger = compile_ledger([package])
        assert ledger[0]["availability_basis"] == "declared_lag"

    def test_collector_first_seen_when_received_at_provided(self):
        """Use collector_first_seen when received_at provided."""
        t0 = us("2026-09-19T12:00:00Z")

        package = compile_raw_taf_to_evidence(
            make_taf_text("KJFK", "191200", "1912", "2012"),
            station="KJFK",
            issued_at=t0,
            received_at=t0 + 3 * HOUR,  # Much later than declared lag
        )

        # Run through ledger
        collector_first_seen = {package["source_id"]: package["collector_first_seen"]}
        ledger = compile_ledger([package], collector_first_seen=collector_first_seen)

        assert ledger[0]["availability_basis"] == "collector_first_seen"

    def test_verified_publication_used_when_later_than_collector(self):
        """verified_publication used when it is later than collector_first_seen.

        Per ledger.py _compute_available_at: whichever timestamp is LATER
        between verified_publication and collector_first_seen is used.
        """
        t0 = us("2026-09-19T12:00:00Z")

        package = compile_raw_taf_to_evidence(
            make_taf_text("KJFK", "191200", "1912", "2012"),
            station="KJFK",
            issued_at=t0,
            received_at=t0 + 5 * MINUTE,   # Collector saw it earlier
            verified_publication=t0 + 10 * MINUTE,  # But verified later
        )

        # Run through ledger
        collector_first_seen = {package["source_id"]: package["collector_first_seen"]}
        ledger = compile_ledger([package], collector_first_seen=collector_first_seen)

        # verified_publication is LATER, so it should be used
        assert ledger[0]["availability_basis"] == "verified_publication"

    def test_collector_first_seen_used_when_later_than_verified(self):
        """collector_first_seen used when it is later than verified_publication.

        Per ledger.py _compute_available_at: whichever timestamp is LATER
        between verified_publication and collector_first_seen is used.
        """
        t0 = us("2026-09-19T12:00:00Z")

        package = compile_raw_taf_to_evidence(
            make_taf_text("KJFK", "191200", "1912", "2012"),
            station="KJFK",
            issued_at=t0,
            received_at=t0 + 10 * MINUTE,  # Collector saw it later
            verified_publication=t0 + 5 * MINUTE,  # But verified earlier
        )

        # Run through ledger
        collector_first_seen = {package["source_id"]: package["collector_first_seen"]}
        ledger = compile_ledger([package], collector_first_seen=collector_first_seen)

        # collector_first_seen is LATER, so it should be used
        assert ledger[0]["availability_basis"] == "collector_first_seen"


# ---------------------------------------------------------------------------
# T2: METAR observation compilation tests
# ---------------------------------------------------------------------------


from disastertrace.monitoring_v1.providers.aviation import MetarReport
from disastertrace.monitoring_v1.support import Interval
from disastertrace.monitoring_v1.targets import TargetSpec
from disastertrace.revision_v1.episode_compiler import (
    compile_asos_csv_to_observations,
    compile_metar_outcomes,
    split_afos_stream,
    compile_afos_taf_stream,
)


# Real ASOS CSV header as observed in data_real_v16
ASOS_CSV_HEADER = "station,valid,lon,lat,elevation,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust,skyc1,skyc2,skyc3,skyc4,skyl1,skyl2,skyl3,skyl4,wxcodes,ice_accretion_1hr,ice_accretion_3hr,ice_accretion_6hr,peak_wind_gust,peak_wind_drct,peak_wind_time,feel,metar,snowdepth"


def make_asos_row(
    station: str = "SFO",
    valid: str = "2025-10-01 00:56",
    vsby: str = "10.00",
    metar: str = "KSFO 010056Z 21010KT 10SM FEW018 BKN090 BKN120 20/14 A2999 RMK AO2 SLP156 T02000144 $",
) -> str:
    """Generate a synthetic ASOS CSV row matching real format."""
    return f"{station},{valid},-122.3749,37.6190,5.00,68.00,58.00,70.38,210.00,10.00,0.00,29.99,1015.60,{vsby},M,FEW,BKN,BKN,M,1800.00,9000.00,12000.00,M,M,M,M,M,M,M,M,68.00,{metar},M"


class TestCompileAsosCsvToObservations:
    """Tests for compile_asos_csv_to_observations()."""

    def test_parse_single_valid_row(self):
        """A single valid ASOS CSV row should parse successfully."""
        csv_text = ASOS_CSV_HEADER + "\n" + make_asos_row()
        observations, skipped = compile_asos_csv_to_observations(csv_text, station="KSFO")

        assert len(observations) == 1
        assert len(skipped) == 0
        assert observations[0].station == "KSFO"
        assert observations[0].visibility is not None

    def test_parse_multiple_rows(self):
        """Multiple valid rows should all be parsed."""
        rows = [
            make_asos_row(valid="2025-10-01 00:56", metar="KSFO 010056Z 21010KT 10SM FEW018 BKN090 BKN120 20/14 A2999 RMK AO2 SLP156 T02000144 $"),
            make_asos_row(valid="2025-10-01 01:56", metar="KSFO 010156Z 22008KT 10SM FEW018 BKN085 BKN120 19/14 A2999 RMK AO2 SLP156 T01940144 $"),
            make_asos_row(valid="2025-10-01 02:56", metar="KSFO 010256Z 22009KT 10SM FEW018 SCT075 BKN090 19/14 A2999 RMK AO2 SLP157 53001 $"),
        ]
        csv_text = ASOS_CSV_HEADER + "\n" + "\n".join(rows)
        observations, skipped = compile_asos_csv_to_observations(csv_text, station="KSFO")

        assert len(observations) == 3
        assert len(skipped) == 0
        # Verify timestamps are in order
        times = [obs.observation_time for obs in observations]
        assert times == sorted(times)

    def test_missing_metar_collected_in_skipped(self):
        """Rows with missing/blank metar should be collected in skipped, not crash."""
        rows = [
            make_asos_row(metar="KSFO 010056Z 21010KT 10SM FEW018 BKN090 BKN120 20/14 A2999 RMK AO2 $"),
            make_asos_row(valid="2025-10-01 01:56", metar=""),  # Blank
            make_asos_row(valid="2025-10-01 02:56", metar="M"),  # IEM 'M' missing marker
        ]
        csv_text = ASOS_CSV_HEADER + "\n" + "\n".join(rows)
        observations, skipped = compile_asos_csv_to_observations(csv_text, station="KSFO")

        assert len(observations) == 1
        assert len(skipped) == 2
        # Skipped entries have diagnostic info
        assert skipped[0]["row_index"] == 1
        assert skipped[1]["row_index"] == 2
        assert "Missing" in skipped[0]["error"]

    def test_unparseable_metar_collected_in_skipped(self):
        """Rows with invalid metar text should be collected in skipped."""
        rows = [
            make_asos_row(metar="KSFO 010056Z 21010KT 10SM FEW018 BKN090 BKN120 20/14 A2999 RMK AO2 $"),
            # Garbled metar - timestamp mismatch or bad format
            make_asos_row(valid="2025-10-01 01:56", metar="KSFO BADFORMAT NOTREAL"),
        ]
        csv_text = ASOS_CSV_HEADER + "\n" + "\n".join(rows)
        observations, skipped = compile_asos_csv_to_observations(csv_text, station="KSFO")

        assert len(observations) == 1
        assert len(skipped) == 1
        assert skipped[0]["row_index"] == 1
        assert "error" in skipped[0]

    def test_station_filter_works(self):
        """Only rows matching the station filter should be included."""
        rows = [
            make_asos_row(valid="2025-10-01 00:56", metar="KSFO 010056Z 21010KT 10SM FEW018 BKN090 BKN120 20/14 A2999 RMK AO2 $"),
            # Note: KJFK METAR has 010156Z = 01:56, so valid must match
            make_asos_row(valid="2025-10-01 01:56", metar="KJFK 010156Z 25010KT 10SM SCT025 19/12 A3000 RMK AO2 $"),
        ]
        csv_text = ASOS_CSV_HEADER + "\n" + "\n".join(rows)

        # Filter for KSFO
        obs_sfo, skipped_sfo = compile_asos_csv_to_observations(csv_text, station="KSFO")
        assert len(obs_sfo) == 1
        assert obs_sfo[0].station == "KSFO"

        # Filter for KJFK
        obs_jfk, skipped_jfk = compile_asos_csv_to_observations(csv_text, station="KJFK")
        assert len(obs_jfk) == 1
        assert obs_jfk[0].station == "KJFK"

    def test_visibility_extracted_correctly(self):
        """Visibility should be extracted from metar text."""
        row = make_asos_row(metar="KSFO 010056Z 21010KT 3SM BR FEW018 20/14 A2999 RMK AO2 $")
        csv_text = ASOS_CSV_HEADER + "\n" + row
        observations, _ = compile_asos_csv_to_observations(csv_text, station="KSFO")

        assert len(observations) == 1
        vis = observations[0].visibility
        assert vis is not None
        # 3SM = 3 statute miles = 4828.032 meters (approx)
        assert 4800 < vis.lower < 4900


class TestCompileMetarOutcomes:
    """Tests for compile_metar_outcomes() with full ternary logic coverage."""

    def _make_target(
        self,
        target_id: str,
        station: str,
        physical_start: int,
        physical_end: int,
        event_operator: str,
        threshold: float,
    ) -> TargetSpec:
        """Create a TargetSpec for testing."""
        return TargetSpec(
            target_id=target_id,
            entity=station,
            variable="visibility",
            units="m",
            event_operator=event_operator,
            threshold=threshold,
            spatial_support="point",
            physical_start=physical_start,
            physical_end=physical_end,
            report_policy="first_available",
            outcome_kind="binary",
            temporal_semantics="future_physical",
        )

    def _make_metar(
        self,
        station: str,
        observation_time: int,
        visibility_lower: float,
        visibility_upper: float | None = None,
    ) -> MetarReport:
        """Create a MetarReport with specified visibility interval."""
        if visibility_upper is None:
            visibility_upper = visibility_lower
        return MetarReport(
            station=station,
            observation_time=observation_time,
            report_type="routine",
            visibility=Interval(visibility_lower, visibility_upper),
            temperature_c=20.0,
            dewpoint_c=14.0,
            weather=(),
            quality_flags=(),
            raw=f"{station} 010056Z 21010KT 10SM FEW018 20/14 A2999",
        )

    def test_no_observations_returns_none(self):
        """No observations in window -> outcome is None."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "lt", 1000.0)

        outcomes = compile_metar_outcomes([], [target])

        assert outcomes["t1"] is None

    def test_gt_fully_above_threshold_returns_1(self):
        """Interval fully > threshold with gt operator -> 1."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "gt", 5000.0)
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 10000.0, 10000.0)

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] == 1
        assert type(outcomes["t1"]) is int  # Strict int, not bool

    def test_gt_fully_below_threshold_returns_0(self):
        """Interval fully <= threshold with gt operator -> 0."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "gt", 5000.0)
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 3000.0, 3000.0)

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] == 0
        assert type(outcomes["t1"]) is int

    def test_gt_straddling_threshold_returns_none(self):
        """Interval straddling threshold with gt operator -> None."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "gt", 5000.0)
        # Interval [4000, 6000] straddles 5000
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 4000.0, 6000.0)

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] is None

    def test_ge_at_boundary_returns_1(self):
        """Interval exactly at threshold with ge operator -> 1."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "ge", 5000.0)
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 5000.0, 5000.0)

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] == 1
        assert type(outcomes["t1"]) is int

    def test_lt_fully_below_threshold_returns_1(self):
        """Interval fully < threshold with lt operator -> 1."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "lt", 5000.0)
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 3000.0, 3000.0)

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] == 1

    def test_lt_fully_above_threshold_returns_0(self):
        """Interval fully >= threshold with lt operator -> 0."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "lt", 5000.0)
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 10000.0, 10000.0)

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] == 0

    def test_le_at_boundary_returns_1(self):
        """Interval exactly at threshold with le operator -> 1."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "le", 5000.0)
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 5000.0, 5000.0)

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] == 1

    def test_multiple_targets_independent(self):
        """Multiple targets should be evaluated independently."""
        t0 = us("2025-10-01T00:00:00Z")
        targets = [
            self._make_target("t1", "KSFO", t0, t0 + HOUR, "gt", 5000.0),
            self._make_target("t2", "KSFO", t0, t0 + HOUR, "lt", 5000.0),
        ]
        obs = self._make_metar("KSFO", t0 + 30 * MINUTE, 10000.0, 10000.0)

        outcomes = compile_metar_outcomes([obs], targets)

        assert outcomes["t1"] == 1  # > 5000 is satisfied
        assert outcomes["t2"] == 0  # < 5000 is not satisfied

    def test_missing_visibility_returns_none(self):
        """MetarReport with visibility=None -> outcome is None."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + HOUR, "gt", 5000.0)
        obs = MetarReport(
            station="KSFO",
            observation_time=t0 + 30 * MINUTE,
            report_type="routine",
            visibility=None,  # Missing visibility
            temperature_c=20.0,
            dewpoint_c=14.0,
            weather=(),
            quality_flags=("visibility_missing",),
            raw="KSFO 010056Z 21010KT M FEW018 20/14 A2999",
        )

        outcomes = compile_metar_outcomes([obs], [target])

        assert outcomes["t1"] is None

    def test_uses_last_observation_in_window(self):
        """When multiple observations in window, uses the last one."""
        t0 = us("2025-10-01T00:00:00Z")
        target = self._make_target("t1", "KSFO", t0, t0 + 2 * HOUR, "gt", 5000.0)
        # First obs: visibility 10000 (would satisfy gt 5000)
        obs1 = self._make_metar("KSFO", t0 + 30 * MINUTE, 10000.0, 10000.0)
        # Second obs (later): visibility 3000 (would NOT satisfy gt 5000)
        obs2 = self._make_metar("KSFO", t0 + 90 * MINUTE, 3000.0, 3000.0)

        outcomes = compile_metar_outcomes([obs1, obs2], [target])

        # Should use obs2 (later), which has vis 3000, not satisfying gt 5000
        assert outcomes["t1"] == 0


# ---------------------------------------------------------------------------
# T2: AFOS stream ingestion tests
# ---------------------------------------------------------------------------


class TestSplitAfosStream:
    """Tests for split_afos_stream()."""

    def test_empty_stream_returns_empty_list(self):
        """Empty input should return empty list."""
        assert split_afos_stream("") == []
        assert split_afos_stream("   ") == []

    def test_single_frame(self):
        """Single framed bulletin should be extracted."""
        frame = """\x01
878
FTUS46 KMTR 072320
TAFSFO
TAF
KSFO 072320Z 0800/0906 31015G20KT P6SM FEW200
     FM081000 VRB05KT P6SM FEW200=

\x03"""
        frames = split_afos_stream(frame)

        assert len(frames) == 1
        assert "FTUS46 KMTR 072320" in frames[0]
        assert "KSFO" in frames[0]

    def test_multiple_frames(self):
        """Multiple framed bulletins should all be extracted."""
        stream = """\x01
001
FTUS46 KMTR 071200
TAFSFO
TAF
KSFO 071200Z 0712/0812 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 071500
TAFSFO
TAF AMD
KSFO 071500Z 0715/0812 27015KT P6SM FEW020=

\x03"""
        frames = split_afos_stream(stream)

        assert len(frames) == 2
        assert "071200Z" in frames[0]
        assert "071500Z" in frames[1]
        assert "AMD" in frames[1]

    def test_handles_missing_etx(self):
        """Frame without ETX should still be captured if it has content."""
        partial = """\x01
001
FTUS46 KMTR 071200
TAF
KSFO 071200Z 0712/0812 25010KT P6SM SCT020"""
        frames = split_afos_stream(partial)

        assert len(frames) == 1
        assert "KSFO" in frames[0]


class TestCompileAfosTafStream:
    """Tests for compile_afos_taf_stream()."""

    def test_single_taf_bulletin(self):
        """Single TAF bulletin should compile to one evidence package."""
        stream = """\x01
878
FTUS46 KMTR 072320
TAFSFO
TAF
KSFO 072320Z 0800/0906 31015G20KT P6SM FEW200
     FM081000 VRB05KT P6SM FEW200
     FM090000 29009KT P6SM VCSH SCT030 BKN050=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        assert len(skipped) == 0
        assert packages[0]["station"] == "KSFO"
        assert packages[0]["amendment_kind"] == "original"
        assert packages[0]["status"] == "active"

    def test_amd_bulletin_detected(self):
        """AMD bulletin should have amendment_kind='AMD'."""
        stream = """\x01
002
FTUS46 KMTR 071500
TAFSFO
TAF AMD
KSFO 071500Z 0715/0812 27015KT P6SM FEW020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        assert packages[0]["amendment_kind"] == "AMD"

    def test_multiple_bulletins_compiled(self):
        """Multiple bulletins in stream should all be compiled."""
        stream = """\x01
001
FTUS46 KMTR 071200
TAFSFO
TAF
KSFO 071200Z 0712/0812 25010KT P6SM SCT020=

\x03\x01
002
FTUS46 KMTR 071500
TAFSFO
TAF AMD
KSFO 071500Z 0715/0812 27015KT P6SM FEW020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 2
        assert packages[0]["amendment_kind"] == "original"
        assert packages[1]["amendment_kind"] == "AMD"

    def test_malformed_frame_in_skipped(self):
        """Malformed frame should go to skipped, not crash."""
        stream = """\x01
001
FTUS46 KMTR 071200
TAFSFO
TAF
KSFO 071200Z 0712/0812 25010KT P6SM SCT020=

\x03\x01
GARBAGE FRAME WITHOUT PROPER STRUCTURE
\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        assert len(skipped) == 1
        assert "error" in skipped[0]

    def test_empty_stream_returns_empty(self):
        """Empty stream should return empty lists."""
        packages, skipped = compile_afos_taf_stream(
            "", station="KSFO", reference_month="2025-10"
        )

        assert packages == []
        assert skipped == []

    def test_issued_at_extracted_from_wmo_header(self):
        """issued_at should be extracted from WMO header DDHHMM."""
        stream = """\x01
001
FTUS46 KMTR 152345
TAFSFO
TAF
KSFO 152345Z 1600/1706 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        # issued_at should correspond to 2025-10-15 23:45Z
        issued_dt = datetime.fromtimestamp(
            packages[0]["issued_at"] / 1_000_000, tz=timezone.utc
        )
        assert issued_dt.day == 15
        assert issued_dt.hour == 23
        assert issued_dt.minute == 45


# ---------------------------------------------------------------------------
# T2: Integration tests against real data files
# ---------------------------------------------------------------------------


import os

REAL_ASOS_PATH = "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/asos/KSFO/2025-10/20260920T084508Z_9e9bfff606c8/asos-sfo-202510.body"
REAL_AFOS_PATH = "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/config/20260920T083047Z_99c64d8d2cfe/probe1-afos-retrieve.body"


@pytest.mark.skipif(
    not os.path.exists(REAL_ASOS_PATH),
    reason=f"Real ASOS data file not found: {REAL_ASOS_PATH}"
)
class TestRealAsosIntegration:
    """Integration tests against real downloaded ASOS data."""

    def test_real_asos_csv_parses_successfully(self):
        """Real ASOS CSV should parse with many successful observations."""
        with open(REAL_ASOS_PATH, "r") as f:
            csv_text = f.read()

        observations, skipped = compile_asos_csv_to_observations(csv_text, station="KSFO")

        # Should have many successful parses
        assert len(observations) > 100, f"Expected >100 observations, got {len(observations)}"
        # Should have few skipped (ideally zero or very small)
        skip_rate = len(skipped) / (len(observations) + len(skipped)) if observations else 1
        assert skip_rate < 0.1, f"Skip rate too high: {skip_rate:.1%}"

        # All observations should be for KSFO
        for obs in observations:
            assert obs.station == "KSFO"

        # Observations should have visibility (most of them)
        vis_present = sum(1 for obs in observations if obs.visibility is not None)
        assert vis_present / len(observations) > 0.9, "Most observations should have visibility"


@pytest.mark.skipif(
    not os.path.exists(REAL_AFOS_PATH),
    reason=f"Real AFOS data file not found: {REAL_AFOS_PATH}"
)
class TestRealAfosIntegration:
    """Integration tests against real downloaded AFOS data."""

    def test_real_afos_stream_parses_successfully(self):
        """Real AFOS stream should parse to 1 evidence package (known to have 1 bulletin)."""
        with open(REAL_AFOS_PATH, "r") as f:
            stream_text = f.read()

        # DL0_VERDICTS.json records this probe's request URL as
        # sdate=2024-01-01T00:00Z&edate=2024-01-08T00:00Z, and the bulletin's
        # own header is "KSFO 072320Z" (day 07, 23:20Z) - so the true issuance
        # date is 2024-01-07T23:20Z, not any 2025 date. reference_month must
        # match the real request window since AFOS bulletins carry no year.
        packages, skipped = compile_afos_taf_stream(
            stream_text, station="KSFO", reference_month="2024-01"
        )

        # Known to have exactly 1 bulletin
        assert len(packages) == 1, f"Expected 1 package, got {len(packages)}"
        assert len(skipped) == 0, f"Unexpected skipped frames: {skipped}"

        # Verify package contents
        pkg = packages[0]
        assert pkg["station"] == "KSFO"
        assert pkg["amendment_kind"] in ("original", "AMD", "COR")
        assert pkg["status"] in ("active", "nil", "canceled")
        assert "native_semantics_sha256" in pkg
        assert pkg["issued_at"] > 0

        # Verify issued_at matches the real bulletin header exactly:
        # KSFO 072320Z within the 2024-01-01..2024-01-08 probe window
        # => 2024-01-07T23:20:00Z
        issued_dt = datetime.fromtimestamp(pkg["issued_at"] / 1_000_000, tz=timezone.utc)
        assert issued_dt == datetime(2024, 1, 7, 23, 20, tzinfo=timezone.utc), (
            f"Expected 2024-01-07T23:20:00Z, got {issued_dt.isoformat()}"
        )


# ---------------------------------------------------------------------------
# T1 measure-prep: Tests for D1 (BBB suffix), D2 (day-31), D3 (SPECI prefix)
# ---------------------------------------------------------------------------


class TestWmoBbbSuffix:
    """Test case for D1: WMO header BBB amendment suffix support."""

    def test_bbb_aaa_suffix_compiles_successfully(self):
        """WMO header with AAA suffix should compile and populate wmo_bbb field."""
        # AAA is the standard first-amendment suffix
        stream = """\x01
001
FTUS46 KMTR 152345 AAA
TAFSFO
TAF AMD
KSFO 152345Z 1600/1706 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        assert len(skipped) == 0
        assert packages[0]["wmo_bbb"] == "AAA"
        # AAA suffix correlates with AMD amendment kind
        assert packages[0]["amendment_kind"] == "AMD"

    def test_bbb_cca_suffix_compiles_successfully(self):
        """WMO header with CCA suffix should compile and populate wmo_bbb field."""
        # CCA is the standard first-correction suffix
        stream = """\x01
001
FTUS46 KMTR 152345 CCA
TAFSFO
TAF COR
KSFO 152345Z 1600/1706 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        assert len(skipped) == 0
        assert packages[0]["wmo_bbb"] == "CCA"
        # CCA suffix correlates with COR amendment kind
        assert packages[0]["amendment_kind"] == "COR"

    def test_no_bbb_suffix_has_none(self):
        """WMO header without BBB suffix should have wmo_bbb=None."""
        stream = """\x01
001
FTUS46 KMTR 152345
TAFSFO
TAF
KSFO 152345Z 1600/1706 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2025-10"
        )

        assert len(packages) == 1
        assert len(skipped) == 0
        assert packages[0]["wmo_bbb"] is None
        assert packages[0]["amendment_kind"] == "original"


class TestDay31Resolution:
    """Test case for D2: Day-31 WMO header date resolution within reference_month."""

    def test_day31_resolves_to_reference_month_january(self):
        """Day-31 header with reference_month=2023-01 should resolve to 2023-01-31.

        Regression test: The old day_time() helper with mid-month reference would
        incorrectly resolve to 2022-12-31 because Dec 31 is closer to Jan 15 than
        Jan 31 (15 days vs 16 days). The fix constructs the datetime directly
        within the known reference month.
        """
        # Day 31 at 21:00Z
        stream = """\x01
001
FTUS46 KMTR 312100
TAFSFO
TAF
KSFO 312100Z 0100/0206 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2023-01"
        )

        assert len(packages) == 1
        assert len(skipped) == 0

        issued_dt = datetime.fromtimestamp(
            packages[0]["issued_at"] / 1_000_000, tz=timezone.utc
        )
        # Should be January 31, 2023, NOT December 31, 2022
        assert issued_dt.year == 2023, f"Wrong year: {issued_dt.year}"
        assert issued_dt.month == 1, f"Wrong month: {issued_dt.month}"
        assert issued_dt.day == 31, f"Wrong day: {issued_dt.day}"

    def test_day31_invalid_in_april_goes_to_skipped(self):
        """Day-31 header with reference_month=2023-04 should be skipped (April has 30 days).

        The fix routes frames with invalid days to skipped with a descriptive
        error class 'wmo_day_outside_reference_month'.
        """
        # Day 31 - invalid for April
        stream = """\x01
001
FTUS46 KMTR 312100
TAFSFO
TAF
KSFO 312100Z 0100/0206 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2023-04"
        )

        assert len(packages) == 0
        assert len(skipped) == 1
        assert "wmo_day_outside_reference_month" in skipped[0]["error"]

    def test_day29_invalid_in_non_leap_february(self):
        """Day-29 header with reference_month=2023-02 should be skipped (non-leap year).

        2023 is not a leap year, so February only has 28 days.
        """
        stream = """\x01
001
FTUS46 KMTR 291200
TAFSFO
TAF
KSFO 291200Z 0100/0206 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2023-02"
        )

        assert len(packages) == 0
        assert len(skipped) == 1
        assert "wmo_day_outside_reference_month" in skipped[0]["error"]

    def test_day29_valid_in_leap_february(self):
        """Day-29 header with reference_month=2024-02 should compile (leap year)."""
        stream = """\x01
001
FTUS46 KMTR 291200
TAFSFO
TAF
KSFO 291200Z 2912/0112 25010KT P6SM SCT020=

\x03"""
        packages, skipped = compile_afos_taf_stream(
            stream, station="KSFO", reference_month="2024-02"
        )

        assert len(packages) == 1
        assert len(skipped) == 0
        issued_dt = datetime.fromtimestamp(
            packages[0]["issued_at"] / 1_000_000, tz=timezone.utc
        )
        assert issued_dt == datetime(2024, 2, 29, 12, 0, tzinfo=timezone.utc)


class TestSpeciPrefixDetection:
    """Test case for D3: SPECI prefix detection in METAR parsing."""

    def test_speci_prefix_parsed_with_special_report_type(self):
        """METAR row with literal 'SPECI ' prefix should parse with report_type='special'.

        Previously this would raise ValueError because report_type='routine' was
        hardcoded, conflicting with the SPECI prefix in the raw text.
        """
        # Note the SPECI prefix in the metar column
        row = make_asos_row(
            valid="2025-10-01 01:56",
            metar="SPECI KSFO 010156Z 21010KT 1/2SM FG VV002 18/17 A2999 RMK AO2 $"
        )
        csv_text = ASOS_CSV_HEADER + "\n" + row
        observations, skipped = compile_asos_csv_to_observations(csv_text, station="KSFO")

        # Should parse successfully, not go to skipped
        assert len(observations) == 1
        assert len(skipped) == 0
        assert observations[0].report_type == "special"
        assert observations[0].station == "KSFO"

    def test_routine_metar_has_routine_report_type(self):
        """Normal METAR (no SPECI prefix) should have report_type='routine'."""
        row = make_asos_row(
            valid="2025-10-01 00:56",
            metar="KSFO 010056Z 21010KT 10SM FEW018 BKN090 BKN120 20/14 A2999 RMK AO2 $"
        )
        csv_text = ASOS_CSV_HEADER + "\n" + row
        observations, skipped = compile_asos_csv_to_observations(csv_text, station="KSFO")

        assert len(observations) == 1
        assert observations[0].report_type == "routine"


# ---------------------------------------------------------------------------
# T1 measure-prep: Real-data integration test against KSFO_202301 TAF data
# ---------------------------------------------------------------------------


REAL_TAF_DL3R_PATH = "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/20260920T134949Z_1bbe63aedc00_dl3rbulk/KSFO_202301.body"
REAL_TAF_DL3R_RECEIPT = "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/20260920T134949Z_1bbe63aedc00_dl3rbulk/KSFO_202301.json"


@pytest.mark.skipif(
    not os.path.exists(REAL_TAF_DL3R_PATH),
    reason=f"Real TAF data file not found: {REAL_TAF_DL3R_PATH}"
)
class TestRealDl3rKsfoIntegration:
    """Integration tests against real downloaded KSFO 2023-01 TAF data (DL-3R bulk).

    Real-data-derived constants (run by T1 agent on 2026-09-20, do not edit without re-running):
    - frame_count_etx from receipt: 303
    - frames with BBB suffix: 179 (discovered via grep)
    - reference_month for this file: 2023-01 (from receipt params_used.sdate)
    """

    def test_frame_count_matches_receipt(self):
        """Total frame count should match the sibling receipt's frame_count_etx field."""
        import json

        with open(REAL_TAF_DL3R_RECEIPT, "r") as f:
            receipt = json.load(f)

        with open(REAL_TAF_DL3R_PATH, "r") as f:
            stream_text = f.read()

        frames = split_afos_stream(stream_text)
        expected_count = receipt["frame_count_etx"]

        assert len(frames) == expected_count, (
            f"Frame count mismatch: got {len(frames)}, expected {expected_count}"
        )

    def test_all_frames_compile_zero_skipped(self):
        """All frames should compile successfully with zero frames in skipped.

        This validates the D1 fix (BBB suffix) and D2 fix (day-31 resolution)
        against real production data.
        """
        with open(REAL_TAF_DL3R_PATH, "r") as f:
            stream_text = f.read()

        packages, skipped = compile_afos_taf_stream(
            stream_text, station="KSFO", reference_month="2023-01"
        )

        # Real-data-derived constant: 303 frames total, zero skipped
        assert len(skipped) == 0, f"Unexpected skipped frames: {skipped[:3]}"
        assert len(packages) == 303, f"Expected 303 packages, got {len(packages)}"

    def test_amendment_kind_distribution(self):
        """Verify the amendment/correction kind distribution matches real data.

        Real-data-derived constants (observed from KSFO 2023-01 on 2026-09-20):
        - original: 124 (frames without BBB suffix)
        - AMD: 171 (frames with BBB suffix starting with 'AA')
        - COR: 8 (frames with BBB suffix starting with 'CC')
        Total: 303 = 124 + 171 + 8
        """
        with open(REAL_TAF_DL3R_PATH, "r") as f:
            stream_text = f.read()

        packages, _ = compile_afos_taf_stream(
            stream_text, station="KSFO", reference_month="2023-01"
        )

        kind_counts = {}
        for pkg in packages:
            k = pkg["amendment_kind"]
            kind_counts[k] = kind_counts.get(k, 0) + 1

        # Real-data-derived constants
        assert kind_counts.get("original", 0) == 124, f"original count: {kind_counts}"
        assert kind_counts.get("AMD", 0) == 171, f"AMD count: {kind_counts}"
        assert kind_counts.get("COR", 0) == 8, f"COR count: {kind_counts}"

    def test_all_dates_within_reference_month(self):
        """All resolved issued_at dates should fall within 2023-01.

        This specifically validates the D2 fix: no dates should incorrectly
        resolve to December 2022 due to the old day_time() nearest-month bug.
        """
        with open(REAL_TAF_DL3R_PATH, "r") as f:
            stream_text = f.read()

        packages, _ = compile_afos_taf_stream(
            stream_text, station="KSFO", reference_month="2023-01"
        )

        for pkg in packages:
            issued_dt = datetime.fromtimestamp(
                pkg["issued_at"] / 1_000_000, tz=timezone.utc
            )
            assert issued_dt.year == 2023, f"Wrong year: {issued_dt}"
            assert issued_dt.month == 1, f"Wrong month: {issued_dt}"

    def test_wmo_bbb_distribution(self):
        """Verify wmo_bbb field distribution matches BBB suffix counts from real data.

        Real-data-derived constants (discovered via grep):
        - Frames with BBB suffix: 179
        - Frames without BBB suffix: 124 (303 - 179)
        """
        with open(REAL_TAF_DL3R_PATH, "r") as f:
            stream_text = f.read()

        packages, _ = compile_afos_taf_stream(
            stream_text, station="KSFO", reference_month="2023-01"
        )

        with_bbb = sum(1 for pkg in packages if pkg.get("wmo_bbb") is not None)
        without_bbb = sum(1 for pkg in packages if pkg.get("wmo_bbb") is None)

        # Real-data-derived constants
        assert with_bbb == 179, f"Packages with wmo_bbb: {with_bbb}"
        assert without_bbb == 124, f"Packages without wmo_bbb: {without_bbb}"

    def test_duplicate_source_id_count(self):
        """Count duplicate source_ids in the real data (if any).

        source_id is auto-generated as station-issued_at-hash_prefix, so
        duplicates would indicate multiple TAFs with identical issuance time
        and semantic content (true duplicates in the archive).

        Real-data-derived constant (observed from KSFO 2023-01 on 2026-09-20):
        1 duplicate source_id found - two TAFs with identical issuance timestamp
        and semantic hash: 'KSFO-1673880900000000-8cdfa38768c2' (appears twice).
        This represents a legitimate archive duplicate (same bulletin recorded
        twice), not a parsing error.
        """
        with open(REAL_TAF_DL3R_PATH, "r") as f:
            stream_text = f.read()

        packages, _ = compile_afos_taf_stream(
            stream_text, station="KSFO", reference_month="2023-01"
        )

        source_ids = [pkg["source_id"] for pkg in packages]
        unique_count = len(set(source_ids))
        duplicate_count = len(source_ids) - unique_count

        # Real-data-derived constant: 1 exact duplicate in this file
        assert duplicate_count == 1, (
            f"Expected 1 duplicate source_id, found {duplicate_count}"
        )
