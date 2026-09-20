"""Tests for episode_compiler.py (W2 task).

Test cases:
a) Normal chain: original -> AMD -> AMD
b) COR correction
c) CNL cancellation
d) Out-of-order arrival (earlier issued_at arriving after later one)
e) Exact duplicate report arriving twice
f) Revision-density audit with hand-computed expected counts
g) End-to-end test feeding compiler output into real ledger.py
"""

import pytest

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
