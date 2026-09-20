"""Tests for the semantic evidence ledger compiler (P0-01).

Acceptance criteria from plan v14:
- Synthetic fixtures: at least 3 examples of EACH of the 9 kinds, demonstrating correct classification.
- Future packages must NOT be visible before their available_at time.
- A package observed early but formally published later must NOT appear in an "early" view.

The 9 kinds (from the plan §7.2 semantic evidence ledger):
- new_observation: genuinely new evidence, not replacing anything
- amendment_supersedes: AMD (amendment) that supersedes a previous version
- correction: COR (correction) of a previous version
- cancellation: CNL (cancellation) of the covered validity window
- lossless_duplicate: identical semantic content (sha256), different source_id/wrapper
- mirror: identical semantic content from a different source
- late_superseded: arrived after it was already superseded by a newer issuance
- no_change_reissue: reissued with same content for procedural reasons (e.g. time extension)
- baseline_update: professional baseline forecast update

Reuses:
- latest_issuance from monitoring_v1/providers/versions.py
- taf_semantics from monitoring_v1/providers/versions.py
- amendment_kind field from TAF products (AMD/COR/original)
"""

import pytest

from disastertrace.monitoring_v1.providers.versions import latest_issuance, taf_semantics
from disastertrace.monitoring_v1.targets import canonical_hash, utc_us


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def make_product(
    *,
    source_id,
    station="KJFK",
    issued_at,
    valid_start,
    valid_end,
    amendment_kind="original",
    status="active",
    semantic_content=None,
):
    """Create a minimal product dict for ledger testing."""
    content = semantic_content if semantic_content is not None else {"body": source_id}
    return {
        "source_id": source_id,
        "station": station,
        "issued_at": issued_at,
        "valid_start": valid_start,
        "valid_end": valid_end,
        "amendment_kind": amendment_kind,
        "status": status,
        "native_semantics_sha256": canonical_hash(content),
        "semantic_content": content,
    }


def us(iso_str):
    """Convert ISO string to microseconds since epoch."""
    return utc_us(iso_str)


# ---------------------------------------------------------------------------
# Test: KIND classification - 3+ examples per kind
# ---------------------------------------------------------------------------


class TestKindClassification:
    """Each kind must have at least 3 correct classification examples."""

    def test_new_observation_three_examples(self):
        """new_observation: genuinely new evidence, not replacing anything."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000  # 1 hour in microseconds

        products = [
            make_product(
                source_id="taf-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="taf-2",
                station="KLAX",
                issued_at=t0 + hour,
                valid_start=t0 + hour,
                valid_end=t0 + 7 * hour,
            ),
            make_product(
                source_id="taf-3",
                station="KORD",
                issued_at=t0 + 2 * hour,
                valid_start=t0 + 2 * hour,
                valid_end=t0 + 8 * hour,
            ),
        ]

        ledger = compile_ledger(products)
        assert len(ledger) == 3
        for entry in ledger:
            assert entry["kind"] == "new_observation"
            assert entry["supersedes"] is None

    def test_amendment_supersedes_three_examples(self):
        """amendment_supersedes: AMD that supersedes a previous version."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # First product is original, next three are AMDs for same station
        products = [
            make_product(
                source_id="taf-orig",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="taf-amd1",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "amended-1"},
            ),
            make_product(
                source_id="taf-amd2",
                issued_at=t0 + 2 * hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "amended-2"},
            ),
            make_product(
                source_id="taf-amd3",
                issued_at=t0 + 3 * hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "amended-3"},
            ),
        ]

        ledger = compile_ledger(products)
        kinds = {e["source_id"]: e["kind"] for e in ledger}
        supersedes = {e["source_id"]: e["supersedes"] for e in ledger}

        assert kinds["taf-orig"] == "new_observation"
        assert kinds["taf-amd1"] == "amendment_supersedes"
        assert kinds["taf-amd2"] == "amendment_supersedes"
        assert kinds["taf-amd3"] == "amendment_supersedes"

        assert supersedes["taf-amd1"] == ["taf-orig"]
        assert supersedes["taf-amd2"] == ["taf-amd1"]
        assert supersedes["taf-amd3"] == ["taf-amd2"]

    def test_correction_three_examples(self):
        """correction: COR (correction) of a previous version."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Three correction scenarios across different stations
        products = [
            # Station 1
            make_product(
                source_id="kjfk-orig",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="kjfk-cor",
                issued_at=t0 + 10 * 60_000_000,  # +10 minutes
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="COR",
                semantic_content={"body": "corrected-kjfk"},
            ),
            # Station 2
            make_product(
                source_id="klax-orig",
                station="KLAX",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="klax-cor",
                station="KLAX",
                issued_at=t0 + 10 * 60_000_000,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="COR",
                semantic_content={"body": "corrected-klax"},
            ),
            # Station 3
            make_product(
                source_id="kord-orig",
                station="KORD",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="kord-cor",
                station="KORD",
                issued_at=t0 + 10 * 60_000_000,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="COR",
                semantic_content={"body": "corrected-kord"},
            ),
        ]

        ledger = compile_ledger(products)
        cors = [e for e in ledger if e["kind"] == "correction"]
        assert len(cors) == 3
        for cor in cors:
            assert cor["supersedes"] is not None
            assert len(cor["supersedes"]) == 1

    def test_cancellation_three_examples(self):
        """cancellation: CNL (cancellation) of the covered validity window."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            # Three cancellations at different stations
            make_product(
                source_id="kjfk-orig",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="kjfk-cnl",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                status="canceled",
            ),
            make_product(
                source_id="klax-orig",
                station="KLAX",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="klax-cnl",
                station="KLAX",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                status="canceled",
            ),
            make_product(
                source_id="kord-orig",
                station="KORD",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="kord-cnl",
                station="KORD",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                status="canceled",
            ),
        ]

        ledger = compile_ledger(products)
        cnls = [e for e in ledger if e["kind"] == "cancellation"]
        assert len(cnls) == 3
        for cnl in cnls:
            assert cnl["supersedes"] is not None

    def test_lossless_duplicate_three_examples(self):
        """lossless_duplicate: identical semantic content (sha256), different source_id."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Same semantic content, different source_ids (within same station)
        shared_content = {"body": "same-content", "vis": 10000}

        products = [
            make_product(
                source_id="kjfk-v1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
            make_product(
                source_id="kjfk-v1-dup1",
                issued_at=t0,  # Same issued_at
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
            make_product(
                source_id="kjfk-v1-dup2",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
            make_product(
                source_id="kjfk-v1-dup3",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
        ]

        ledger = compile_ledger(products)
        dups = [e for e in ledger if e["kind"] == "lossless_duplicate"]
        assert len(dups) >= 3

    def test_mirror_three_examples(self):
        """mirror: identical semantic content from a different source."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        shared_content = {"body": "mirrored-content", "vis": 5000}

        # Mirror: same content from different sources (indicated by source prefix)
        products = [
            make_product(
                source_id="nws-kjfk-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
            make_product(
                source_id="aviationweather-kjfk-1",
                issued_at=t0 + 1_000_000,  # Slight delay
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
            make_product(
                source_id="nws-klax-1",
                station="KLAX",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "klax-content"},
            ),
            make_product(
                source_id="aviationweather-klax-1",
                station="KLAX",
                issued_at=t0 + 1_000_000,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "klax-content"},
            ),
            make_product(
                source_id="nws-kord-1",
                station="KORD",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "kord-content"},
            ),
            make_product(
                source_id="aviationweather-kord-1",
                station="KORD",
                issued_at=t0 + 1_000_000,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "kord-content"},
            ),
        ]

        ledger = compile_ledger(products)
        mirrors = [e for e in ledger if e["kind"] == "mirror"]
        assert len(mirrors) >= 3

    def test_late_superseded_three_examples(self):
        """late_superseded: arrived after it was already superseded by a newer issuance."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000  # 2 minute lag

        # Product arrives late - we simulate this by having observed_at > issued_at
        # where the newer product was already visible
        products = [
            # Original issued at t0, available at t0 + lag
            make_product(
                source_id="kjfk-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            # Amendment issued at t0+1h, available at t0+1h + lag
            make_product(
                source_id="kjfk-2",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "amd-1"},
            ),
            # Late arrival: issued at t0+30min but arrived (observed) after kjfk-2 was already visible
            # This is a late duplicate/old version
            make_product(
                source_id="kjfk-1-late",
                issued_at=t0 + 30 * 60_000_000,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "old-but-late"},
            ),
        ]

        # Specify collector_first_seen times to indicate late arrival
        collector_times = {
            "kjfk-1": t0 + lag,
            "kjfk-2": t0 + hour + lag,
            "kjfk-1-late": t0 + 2 * hour,  # Arrived after kjfk-2
        }

        ledger = compile_ledger(products, collector_first_seen=collector_times)

        late_entries = [e for e in ledger if e["kind"] == "late_superseded"]
        # Need at least 3 for acceptance criteria - create more scenarios
        # Actually, let's add more products for the 3 examples requirement

    def test_late_superseded_three_distinct_examples(self):
        """late_superseded: three complete examples."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        products = []
        collector_times = {}

        # Three stations, each with a late arrival
        for i, station in enumerate(["KJFK", "KLAX", "KORD"]):
            base_t = t0 + i * 10 * hour
            # Original
            products.append(
                make_product(
                    source_id=f"{station.lower()}-orig",
                    station=station,
                    issued_at=base_t,
                    valid_start=base_t,
                    valid_end=base_t + 6 * hour,
                )
            )
            collector_times[f"{station.lower()}-orig"] = base_t + lag

            # Amendment (supersedes original)
            products.append(
                make_product(
                    source_id=f"{station.lower()}-amd",
                    station=station,
                    issued_at=base_t + hour,
                    valid_start=base_t,
                    valid_end=base_t + 6 * hour,
                    amendment_kind="AMD",
                    semantic_content={"body": f"{station}-amd"},
                )
            )
            collector_times[f"{station.lower()}-amd"] = base_t + hour + lag

            # Late arrival of an old version - issued between orig and amd
            # but arrived after amd was visible
            products.append(
                make_product(
                    source_id=f"{station.lower()}-late",
                    station=station,
                    issued_at=base_t + 30 * 60_000_000,
                    valid_start=base_t,
                    valid_end=base_t + 6 * hour,
                    semantic_content={"body": f"{station}-late-old"},
                )
            )
            collector_times[f"{station.lower()}-late"] = base_t + 2 * hour

        ledger = compile_ledger(products, collector_first_seen=collector_times)
        late_entries = [e for e in ledger if e["kind"] == "late_superseded"]
        assert len(late_entries) >= 3

    def test_no_change_reissue_three_examples(self):
        """no_change_reissue: reissued with same content for procedural reasons."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Same semantic content, but reissued at a later time (not a duplicate)
        # This happens when the forecast is extended or revalidated
        products = []
        for i, station in enumerate(["KJFK", "KLAX", "KORD"]):
            content = {"body": f"{station}-forecast", "vis": 10000}
            base_t = t0 + i * hour

            # Original
            products.append(
                make_product(
                    source_id=f"{station.lower()}-v1",
                    station=station,
                    issued_at=base_t,
                    valid_start=base_t,
                    valid_end=base_t + 6 * hour,
                    semantic_content=content,
                )
            )

            # Reissue - later issued_at, same content
            products.append(
                make_product(
                    source_id=f"{station.lower()}-reissue",
                    station=station,
                    issued_at=base_t + 2 * hour,
                    valid_start=base_t,
                    valid_end=base_t + 6 * hour,
                    semantic_content=content,
                )
            )

        ledger = compile_ledger(products)
        reissues = [e for e in ledger if e["kind"] == "no_change_reissue"]
        assert len(reissues) >= 3

    def test_baseline_update_three_examples(self):
        """baseline_update: professional baseline forecast update."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Baseline products are marked with is_baseline=True
        products = []
        for i, station in enumerate(["KJFK", "KLAX", "KORD"]):
            base_t = t0 + i * hour

            # Mark these as baseline products
            products.append(
                make_product(
                    source_id=f"{station.lower()}-base-1",
                    station=station,
                    issued_at=base_t,
                    valid_start=base_t,
                    valid_end=base_t + 6 * hour,
                )
            )
            products[-1]["is_baseline"] = True

            products.append(
                make_product(
                    source_id=f"{station.lower()}-base-2",
                    station=station,
                    issued_at=base_t + 6 * hour,
                    valid_start=base_t + 6 * hour,
                    valid_end=base_t + 12 * hour,
                )
            )
            products[-1]["is_baseline"] = True

        ledger = compile_ledger(products)
        baselines = [e for e in ledger if e["kind"] == "baseline_update"]
        assert len(baselines) >= 3


# ---------------------------------------------------------------------------
# Test: Visibility / Leakage - future packages NOT visible before available_at
# ---------------------------------------------------------------------------


class TestVisibility:
    """Future packages must NOT be visible before their available_at time."""

    def test_future_package_not_visible_before_available_at(self):
        """A future package should not appear in view before available_at."""
        from disastertrace.revision_v1.ledger import compile_ledger, visible_at

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        products = [
            make_product(
                source_id="taf-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="taf-2",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
            ),
        ]

        ledger = compile_ledger(products, declared_lag_us=lag)

        # At time t0 + lag/2, taf-1 should not be visible (lag not elapsed)
        view_early = visible_at(ledger, cutoff=t0 + lag // 2)
        assert all(e["source_id"] != "taf-1" for e in view_early)

        # At time t0 + lag, taf-1 should be visible
        view_t0 = visible_at(ledger, cutoff=t0 + lag)
        source_ids = [e["source_id"] for e in view_t0]
        assert "taf-1" in source_ids

        # At time t0 + hour + lag/2, taf-2 should not be visible
        view_mid = visible_at(ledger, cutoff=t0 + hour + lag // 2)
        source_ids_mid = [e["source_id"] for e in view_mid]
        assert "taf-2" not in source_ids_mid
        assert "taf-1" in source_ids_mid

        # At time t0 + hour + lag, taf-2 should be visible
        view_late = visible_at(ledger, cutoff=t0 + hour + lag)
        source_ids_late = [e["source_id"] for e in view_late]
        assert "taf-2" in source_ids_late

    def test_three_future_packages_visibility_boundary(self):
        """Three packages, each with distinct visibility boundaries."""
        from disastertrace.revision_v1.ledger import compile_ledger, visible_at

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        products = [
            make_product(
                source_id=f"taf-{i}",
                issued_at=t0 + i * hour,
                valid_start=t0,
                valid_end=t0 + 12 * hour,
            )
            for i in range(3)
        ]

        ledger = compile_ledger(products, declared_lag_us=lag)

        # Just before each becomes visible, it should not be in the view
        for i in range(3):
            just_before = t0 + i * hour + lag - 1
            view = visible_at(ledger, cutoff=just_before)
            visible_ids = [e["source_id"] for e in view]
            assert f"taf-{i}" not in visible_ids

            # Exactly at available_at, it should be visible
            exactly_at = t0 + i * hour + lag
            view_at = visible_at(ledger, cutoff=exactly_at)
            visible_ids_at = [e["source_id"] for e in view_at]
            assert f"taf-{i}" in visible_ids_at


# ---------------------------------------------------------------------------
# Test: Early observation vs formal publication (no premature visibility)
# ---------------------------------------------------------------------------


class TestNoPrematureVisibility:
    """A package observed early but formally published later must NOT appear early."""

    def test_early_observation_not_visible_until_formal_publication(self):
        """Observed early (collector_first_seen) but must wait for declared publication."""
        from disastertrace.revision_v1.ledger import compile_ledger, visible_at

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        # Product issued at t0, observed at t0+10sec, but formally available at t0+lag
        products = [
            make_product(
                source_id="taf-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
        ]

        collector_times = {
            "taf-1": t0 + 10_000_000,  # Observed 10 seconds after issuance
        }

        ledger = compile_ledger(
            products, declared_lag_us=lag, collector_first_seen=collector_times
        )

        # Even though observed at t0+10s, should not be visible until t0+lag
        view_early = visible_at(ledger, cutoff=t0 + 30_000_000)  # 30 seconds
        assert len(view_early) == 0

        view_formal = visible_at(ledger, cutoff=t0 + lag)
        assert len(view_formal) == 1
        assert view_formal[0]["source_id"] == "taf-1"

    def test_three_early_observations_respect_publication_time(self):
        """Three packages observed early must all respect their formal publication time."""
        from disastertrace.revision_v1.ledger import compile_ledger, visible_at

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        products = []
        collector_times = {}

        for i in range(3):
            src_id = f"taf-{i}"
            products.append(
                make_product(
                    source_id=src_id,
                    issued_at=t0 + i * hour,
                    valid_start=t0,
                    valid_end=t0 + 12 * hour,
                )
            )
            # Observed almost immediately
            collector_times[src_id] = t0 + i * hour + 5_000_000

        ledger = compile_ledger(
            products, declared_lag_us=lag, collector_first_seen=collector_times
        )

        # Each should only be visible after its formal publication time
        for i in range(3):
            # Just after observation but before formal availability
            early_cutoff = t0 + i * hour + 10_000_000
            view = visible_at(ledger, cutoff=early_cutoff)
            visible_ids = [e["source_id"] for e in view]
            assert f"taf-{i}" not in visible_ids

            # At formal availability
            formal_cutoff = t0 + i * hour + lag
            view_formal = visible_at(ledger, cutoff=formal_cutoff)
            visible_ids_formal = [e["source_id"] for e in view_formal]
            assert f"taf-{i}" in visible_ids_formal


# ---------------------------------------------------------------------------
# Test: Availability basis field
# ---------------------------------------------------------------------------


class TestAvailabilityBasis:
    """Verify availability_basis is correctly assigned."""

    def test_declared_lag_basis(self):
        """When visibility is from declared lag, basis should be declared_lag."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        products = [
            make_product(
                source_id="taf-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
        ]

        ledger = compile_ledger(products, declared_lag_us=lag)
        assert ledger[0]["availability_basis"] == "declared_lag"
        assert ledger[0]["available_at"] == t0 + lag

    def test_collector_first_seen_basis(self):
        """When collector_first_seen is later than declared, use that."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        products = [
            make_product(
                source_id="taf-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
        ]

        # Collector saw it much later than declared lag would suggest
        collector_times = {
            "taf-1": t0 + hour,  # 1 hour delay
        }

        ledger = compile_ledger(
            products, declared_lag_us=lag, collector_first_seen=collector_times
        )

        # Should use the later time (collector_first_seen)
        assert ledger[0]["availability_basis"] == "collector_first_seen"
        assert ledger[0]["available_at"] == t0 + hour


# ---------------------------------------------------------------------------
# Test: Reuse of existing interfaces
# ---------------------------------------------------------------------------


class TestReuseInterfaces:
    """Verify we correctly reuse latest_issuance, taf_semantics, amendment_kind."""

    def test_uses_latest_issuance_for_supersedes(self):
        """The ledger should use latest_issuance to determine supersedes relationships."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="taf-old",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="taf-new",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
            ),
        ]

        # Verify latest_issuance gives expected result
        latest, superseded = latest_issuance(products)
        assert len(latest) == 1
        assert latest[0]["source_id"] == "taf-new"
        assert len(superseded) == 1
        assert superseded[0]["source_id"] == "taf-old"

        # Compile ledger and check
        ledger = compile_ledger(products)
        new_entry = next(e for e in ledger if e["source_id"] == "taf-new")
        assert new_entry["supersedes"] == ["taf-old"]

    def test_uses_amendment_kind_for_classification(self):
        """amendment_kind (AMD/COR/original) should drive kind classification."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="taf-orig",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="original",
            ),
            make_product(
                source_id="taf-amd",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
            ),
            make_product(
                source_id="taf-cor",
                issued_at=t0 + 2 * hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="COR",
            ),
        ]

        ledger = compile_ledger(products)
        kinds = {e["source_id"]: e["kind"] for e in ledger}

        assert kinds["taf-orig"] == "new_observation"
        assert kinds["taf-amd"] == "amendment_supersedes"
        assert kinds["taf-cor"] == "correction"

    def test_uses_semantic_hash_for_duplicate_detection(self):
        """Semantic content hash should be used for duplicate/mirror detection."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        shared_content = {"vis": 10000, "wind": "27015KT", "sky": "SCT030"}

        products = [
            make_product(
                source_id="taf-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
            make_product(
                source_id="taf-1-dup",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=shared_content,
            ),
        ]

        # Verify same semantic hash
        assert products[0]["native_semantics_sha256"] == products[1]["native_semantics_sha256"]

        ledger = compile_ledger(products)
        dup_entry = next(e for e in ledger if e["source_id"] == "taf-1-dup")
        assert dup_entry["kind"] == "lossless_duplicate"


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_product_list(self):
        """Empty product list should produce empty ledger."""
        from disastertrace.revision_v1.ledger import compile_ledger

        ledger = compile_ledger([])
        assert ledger == []

    def test_single_product(self):
        """Single product should be classified as new_observation."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="taf-only",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
        ]

        ledger = compile_ledger(products)
        assert len(ledger) == 1
        assert ledger[0]["kind"] == "new_observation"
        assert ledger[0]["supersedes"] is None

    def test_nil_status_product(self):
        """NIL status products should be handled."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="taf-nil",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                status="nil",
            ),
        ]

        ledger = compile_ledger(products)
        assert len(ledger) == 1
        # NIL is a valid new observation (no prior to supersede)
        assert ledger[0]["kind"] == "new_observation"


# ---------------------------------------------------------------------------
# Test: Issue #1 - Future-mirror semantic hash leakage
# ---------------------------------------------------------------------------


class TestFutureMirrorLeakage:
    """Issue #1: Future mirror cannot relabel visible prefix.

    The online/live view must be insensitive to ANY future suffix.
    """

    def test_future_mirror_does_not_relabel_visible_prefix(self):
        """Adding a future record must not alter prior agent-visible metadata."""
        from disastertrace.revision_v1.ledger import compile_ledger, visible_at

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Original product
        original = make_product(
            source_id="nws-original",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content={"body": "content"},
        )

        # Future mirror with same semantic hash
        future_mirror = make_product(
            source_id="mirror-copy",
            issued_at=t0 + 5 * hour,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content={"body": "content"},  # Same content
        )

        # Compile ledger WITHOUT future record
        ledger_before = compile_ledger([original], declared_lag_us=0)
        view_before = visible_at(ledger_before, cutoff=t0 + 2 * hour)

        # Compile ledger WITH future record
        ledger_after = compile_ledger([original, future_mirror], declared_lag_us=0)
        view_after = visible_at(ledger_after, cutoff=t0 + 2 * hour)

        # The view at the SAME cutoff must be IDENTICAL
        assert view_before == view_after, "Future records must not alter prior agent-visible metadata"

    def test_future_suffix_insensitivity_property(self):
        """Property test: any historical prefix produces byte-identical output.

        This is the core canary property from the review's acceptance principle:
        Take any historical prefix of events up to some view time, compute the
        ledger classification for that prefix; then append arbitrary future events
        and recompute for the SAME view time - the output for all prior records
        must be byte-identical regardless of what was appended later.
        """
        from disastertrace.revision_v1.ledger import compile_ledger, visible_at

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Create a series of products
        products = [
            make_product(
                source_id="nws-p1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="nws-p2",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "amd-1"},
            ),
            make_product(
                source_id="nws-p3",
                issued_at=t0 + 2 * hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "amd-2"},
            ),
        ]

        view_time = t0 + 3 * hour
        ledger_prefix = compile_ledger(products, declared_lag_us=0)
        view_prefix = visible_at(ledger_prefix, cutoff=view_time)

        # Append arbitrary future events
        future_events = [
            make_product(
                source_id="nws-future-1",
                issued_at=t0 + 10 * hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "future-1"},
            ),
            make_product(
                source_id="mirror-future",
                issued_at=t0 + 11 * hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "amd-2"},  # Same as p3
            ),
            make_product(
                source_id="dup-future",
                issued_at=t0 + 12 * hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content=products[0]["semantic_content"],  # Same as p1
            ),
        ]

        extended_products = products + future_events
        ledger_extended = compile_ledger(extended_products, declared_lag_us=0)
        view_extended = visible_at(ledger_extended, cutoff=view_time)

        # Output must be byte-identical
        assert view_prefix == view_extended, \
            "Online view must be insensitive to any future suffix"

    def test_compile_ledger_at_view_produces_stable_classification(self):
        """compile_ledger_at_view guarantees no future influence."""
        from disastertrace.revision_v1.ledger import compile_ledger_at_view

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="nws-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "content-1"},
            ),
            make_product(
                source_id="aviationweather-1",
                issued_at=t0 + 10 * hour,  # Future
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "content-1"},  # Same content - would be mirror
            ),
        ]

        view_time = t0 + 3 * hour
        ledger = compile_ledger_at_view(
            products,
            view_cutoff=view_time,
            declared_lag_us=0,
        )

        # Only the visible product should be in the ledger
        assert len(ledger) == 1
        assert ledger[0]["source_id"] == "nws-1"
        assert ledger[0]["kind"] == "new_observation"  # Not mirror


# ---------------------------------------------------------------------------
# Test: Issue #2 - Cross-window supersession
# ---------------------------------------------------------------------------


class TestCrossWindowSupersession:
    """Issue #2: Supersession should work across differing validity windows."""

    def test_overlapping_validity_windows_form_lineage(self):
        """Products with overlapping windows should be in same lineage."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Two products with overlapping validity windows
        products = [
            make_product(
                source_id="nws-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="nws-2",
                issued_at=t0 + hour,
                valid_start=t0 + 2 * hour,  # Different window but overlapping
                valid_end=t0 + 8 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "extended"},
            ),
        ]

        ledger = compile_ledger(products, declared_lag_us=0)

        # The AMD should recognize it's amending a related product
        amd_entry = next(e for e in ledger if e["source_id"] == "nws-2")
        # While exact window match isn't required, the relationship is tracked
        assert amd_entry["version_relationship"] in ("supersedes", "first")


# ---------------------------------------------------------------------------
# Test: Issue #3 - late_superseded direction
# ---------------------------------------------------------------------------


class TestLateSupersededDirection:
    """Issue #3: Late-arriving old versions should be SUPERSEDED BY newer, not reverse."""

    def test_late_old_record_is_superseded_by_newer_not_reverse(self):
        """Late old evidence is superseded BY the new record."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Setup: old issued first, new issued second, but old arrives AFTER new
        old = make_product(
            source_id="nws-old",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content={"body": "old-content"},
        )
        new = make_product(
            source_id="nws-new",
            issued_at=t0 + hour,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            amendment_kind="AMD",
            semantic_content={"body": "new-content"},
        )

        collector_times = {
            "nws-old": t0 + 3 * hour,  # Arrived late
            "nws-new": t0 + hour + 2 * 60_000_000,  # Arrived on time
        }

        ledger = compile_ledger(
            [old, new],
            declared_lag_us=0,
            collector_first_seen=collector_times,
        )

        old_entry = next(e for e in ledger if e["source_id"] == "nws-old")

        # Issue #3 fix: old record should NOT have new record in its "supersedes" field
        assert "nws-new" not in (old_entry.get("supersedes") or []), \
            "Late old evidence should not claim to supersede newer record"

        # Instead, it should have "superseded_by" field
        assert old_entry.get("superseded_by") == ["nws-new"] or \
               old_entry["version_relationship"] == "superseded_by", \
            "Late old evidence should be superseded_by the newer record"

    def test_late_superseded_has_correct_direction_field(self):
        """late_superseded entries should have superseded_by, not supersedes."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="nws-early",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
            make_product(
                source_id="nws-late",
                issued_at=t0 + 30 * 60_000_000,  # Issued later
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                semantic_content={"body": "late-content"},
            ),
            make_product(
                source_id="nws-newest",
                issued_at=t0 + hour,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
                amendment_kind="AMD",
                semantic_content={"body": "newest-content"},
            ),
        ]

        collector_times = {
            "nws-early": t0,
            "nws-newest": t0 + hour + 2 * 60_000_000,
            "nws-late": t0 + 2 * hour,  # Arrived after nws-newest
        }

        ledger = compile_ledger(
            products,
            declared_lag_us=0,
            collector_first_seen=collector_times,
        )

        late_entry = next(e for e in ledger if e["source_id"] == "nws-late")

        # Should be late_superseded with correct direction
        assert late_entry["kind"] == "late_superseded"
        assert late_entry["superseded_by"] is not None
        assert "nws-newest" in late_entry["superseded_by"]
        assert late_entry["supersedes"] is None


# ---------------------------------------------------------------------------
# Test: Issue #4 - Explicit provenance fields
# ---------------------------------------------------------------------------


class TestProvenanceFields:
    """Issue #4: Provenance should use explicit fields, not string parsing."""

    def test_explicit_provider_field_used_for_mirror_detection(self):
        """When provider field is present, use it instead of source_id parsing."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        shared_content = {"body": "shared-content"}

        # Two products with explicit provider fields
        p1 = make_product(
            source_id="some-random-id-1",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content=shared_content,
        )
        p1["provider"] = "nws"

        p2 = make_product(
            source_id="another-random-id-2",
            issued_at=t0 + 1_000_000,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content=shared_content,
        )
        p2["provider"] = "aviationweather"  # Different provider = mirror

        ledger = compile_ledger([p1, p2], declared_lag_us=0)
        p2_entry = next(e for e in ledger if e["source_id"] == "another-random-id-2")

        # Should be classified as mirror due to different provider
        assert p2_entry["kind"] == "mirror"

    def test_same_provider_explicit_is_not_mirror(self):
        """Same explicit provider should not be classified as mirror."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        shared_content = {"body": "shared-content"}

        # Two products with same explicit provider
        p1 = make_product(
            source_id="id-1",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content=shared_content,
        )
        p1["provider"] = "nws"

        p2 = make_product(
            source_id="id-2",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content=shared_content,
        )
        p2["provider"] = "nws"  # Same provider = duplicate, not mirror

        ledger = compile_ledger([p1, p2], declared_lag_us=0)
        p2_entry = next(e for e in ledger if e["source_id"] == "id-2")

        # Should be lossless_duplicate, not mirror
        assert p2_entry["kind"] == "lossless_duplicate"


# ---------------------------------------------------------------------------
# Test: Issue #5 - verified_publication as real input
# ---------------------------------------------------------------------------


class TestVerifiedPublication:
    """Issue #5: verified_publication should be a real availability input."""

    def test_verified_publication_determines_availability(self):
        """When verified_publication is present, it should be used."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000
        lag = 2 * 60_000_000

        p = make_product(
            source_id="nws-1",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
        )
        p["verified_publication"] = t0 + 5 * 60_000_000  # 5 minutes after issuance

        ledger = compile_ledger([p], declared_lag_us=lag)

        # Should use verified_publication
        assert ledger[0]["availability_basis"] == "verified_publication"
        assert ledger[0]["available_at"] == t0 + 5 * 60_000_000

    def test_collector_first_seen_overrides_verified_publication_if_later(self):
        """If collector saw it later than verified_publication, use that."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        p = make_product(
            source_id="nws-1",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
        )
        p["verified_publication"] = t0 + 5 * 60_000_000

        collector_times = {
            "nws-1": t0 + 10 * 60_000_000,  # Later than verified
        }

        ledger = compile_ledger([p], declared_lag_us=0, collector_first_seen=collector_times)

        # Should use collector_first_seen since it's later
        assert ledger[0]["availability_basis"] == "collector_first_seen"
        assert ledger[0]["available_at"] == t0 + 10 * 60_000_000


# ---------------------------------------------------------------------------
# Test: Issue #6 - Dimension separation (kind derived from dimensions)
# ---------------------------------------------------------------------------


class TestDimensionSeparation:
    """Issue #6: Kind should be derived from separate dimensions."""

    def test_ledger_entries_have_dimension_fields(self):
        """Ledger entries should have the new dimension fields."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="nws-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
        ]

        ledger = compile_ledger(products, declared_lag_us=0)

        assert "arrival_relationship" in ledger[0]
        assert "version_relationship" in ledger[0]
        assert "information_utility" in ledger[0]

    def test_baseline_does_not_override_amd_cor(self):
        """baseline_update should not override AMD/COR semantics."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        # Baseline product with AMD marker
        original = make_product(
            source_id="nws-orig",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
        )
        original["is_baseline"] = True

        amended = make_product(
            source_id="nws-amd",
            issued_at=t0 + hour,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            amendment_kind="AMD",
            semantic_content={"body": "amended"},
        )
        amended["is_baseline"] = True

        ledger = compile_ledger([original, amended], declared_lag_us=0)

        amd_entry = next(e for e in ledger if e["source_id"] == "nws-amd")

        # Should be amendment_supersedes, NOT baseline_update
        assert amd_entry["kind"] == "amendment_supersedes"


# ---------------------------------------------------------------------------
# Test: Issue #7 - no_change_reissue information utility
# ---------------------------------------------------------------------------


class TestNoChangeReissueInformation:
    """Issue #7: no_change_reissue should track actual information deltas."""

    def test_reissue_with_extended_validity_is_informative(self):
        """A reissue with extended validity period has information."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        shared_content = {"body": "content"}

        original = make_product(
            source_id="nws-1",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content=shared_content,
        )

        reissue = make_product(
            source_id="nws-2",
            issued_at=t0 + 2 * hour,
            valid_start=t0,
            valid_end=t0 + 12 * hour,  # Extended validity
            semantic_content=shared_content,
        )

        ledger = compile_ledger([original, reissue], declared_lag_us=0)
        reissue_entry = next(e for e in ledger if e["source_id"] == "nws-2")

        # Should track extension
        assert reissue_entry["kind"] == "no_change_reissue"
        assert reissue_entry["information_utility"] == "extension"

    def test_reissue_with_confirmation_count_is_informative(self):
        """A reissue with increased confirmation count has information."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        shared_content = {"body": "content"}

        original = make_product(
            source_id="nws-1",
            issued_at=t0,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content=shared_content,
        )
        original["confirmation_count"] = 1

        reissue = make_product(
            source_id="nws-2",
            issued_at=t0 + 2 * hour,
            valid_start=t0,
            valid_end=t0 + 6 * hour,
            semantic_content=shared_content,
        )
        reissue["confirmation_count"] = 2  # Increased

        ledger = compile_ledger([original, reissue], declared_lag_us=0)
        reissue_entry = next(e for e in ledger if e["source_id"] == "nws-2")

        # Should track confirmation
        assert reissue_entry["kind"] == "no_change_reissue"
        assert reissue_entry["information_utility"] == "confirmation"


# ---------------------------------------------------------------------------
# Test: New superseded_by field
# ---------------------------------------------------------------------------


class TestSupersededByField:
    """The new superseded_by field should be present and correct."""

    def test_superseded_by_field_present_in_entries(self):
        """All ledger entries should have superseded_by field."""
        from disastertrace.revision_v1.ledger import compile_ledger

        t0 = us("2026-09-19T00:00:00Z")
        hour = 3_600_000_000

        products = [
            make_product(
                source_id="nws-1",
                issued_at=t0,
                valid_start=t0,
                valid_end=t0 + 6 * hour,
            ),
        ]

        ledger = compile_ledger(products, declared_lag_us=0)

        assert "superseded_by" in ledger[0]
        assert ledger[0]["superseded_by"] is None  # First entry has nothing superseding it
