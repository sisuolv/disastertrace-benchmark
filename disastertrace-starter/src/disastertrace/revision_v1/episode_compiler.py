"""Episode compiler: bridge raw TAF/METAR text to ledger-ready evidence packages.

This module converts raw TAF/METAR report text (with real-world metadata like
station, issued_at, received_at/collector timestamp) into the evidence package
format expected by ledger.py's compile_ledger function.

The compiler:
1. Parses raw reports using the existing aviation.py parser
2. Computes semantic hashes using versions.py's taf_semantics pattern
3. Determines availability_basis based on timestamp information present
4. Emits evidence packages matching ledger.py's expected input shape

Also provides a revision-density audit function for counting AMD/COR/CNL/
supersession events per station per month, as specified in
DATA_ACQUISITION_PLAN_v16_CN.md section 5.3.

Expected input shape for ledger.py (from compile_ledger docstring, lines 397-410):
    - source_id: unique identifier
    - station: station code
    - issued_at: issuance time in microseconds
    - valid_start: validity window start in microseconds
    - valid_end: validity window end in microseconds
    - amendment_kind: 'original', 'AMD', or 'COR'
    - status: 'active', 'nil', 'canceled', 'unparsed'
    - native_semantics_sha256: semantic content hash
    - is_baseline: (optional) True if this is a baseline product
    - verified_publication: (optional) verified publication time
    - provider: (optional) explicit provider identity
    - product_series: (optional) product lineage identifier
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from ..monitoring_v1.providers.aviation import TafProduct, parse_taf
from ..monitoring_v1.providers.versions import latest_issuance, taf_semantics
from ..monitoring_v1.targets import canonical_hash, utc_us


def _datetime_to_us(dt: datetime | str | int) -> int:
    """Convert datetime/ISO string/int to microseconds since epoch."""
    if isinstance(dt, int):
        return dt
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    return utc_us(dt.astimezone(timezone.utc).isoformat())


def _us_to_yearmonth(timestamp_us: int) -> str:
    """Convert microseconds timestamp to YYYY-MM string for grouping."""
    dt = datetime.fromtimestamp(timestamp_us / 1_000_000, tz=timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}"


def compile_raw_taf_to_evidence(
    raw_text: str,
    *,
    station: str,
    issued_at: datetime | str | int,
    received_at: datetime | str | int | None = None,
    verified_publication: datetime | str | int | None = None,
    source_id: str | None = None,
    provider: str | None = None,
    product_series: str = "default",
) -> dict[str, Any]:
    """Convert a single raw TAF text report to a ledger-ready evidence package.

    Args:
        raw_text: The raw TAF report text (e.g., "TAF KJFK 191200Z 1912/2012...")
        station: Station ICAO code (e.g., "KJFK")
        issued_at: Official issuance time (datetime, ISO string, or microseconds)
        received_at: When the collector first observed this report (optional)
        verified_publication: Verified publication time from source (optional)
        source_id: Unique identifier for this report (auto-generated if None)
        provider: Provider identity for mirror/duplicate detection (optional)
        product_series: Product lineage identifier (default "default")

    Returns:
        Evidence package dict ready for ledger.compile_ledger():
            - source_id
            - station
            - issued_at (microseconds)
            - valid_start (microseconds)
            - valid_end (microseconds)
            - amendment_kind ('original', 'AMD', or 'COR')
            - status ('active', 'nil', 'canceled')
            - native_semantics_sha256 (content hash)
            - availability_basis ('verified_publication', 'declared_lag', or
              'collector_first_seen')
            - collector_first_seen (microseconds, if received_at provided)
            - verified_publication (microseconds, if provided)
            - provider (if provided)
            - product_series

    Raises:
        ValueError: If the raw text cannot be parsed.
    """
    # Convert timestamps to microseconds
    issued_at_us = _datetime_to_us(issued_at)
    issued_at_iso = datetime.fromtimestamp(
        issued_at_us / 1_000_000, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")

    # Parse the raw TAF using the existing aviation.py parser
    product: TafProduct = parse_taf(
        raw_text,
        station=station,
        archive_issue=issued_at_iso,
    )

    # Compute semantic hash using versions.py pattern
    semantic_hash = taf_semantics(product)

    # Generate source_id if not provided
    if source_id is None:
        source_id = f"{station}-{issued_at_us}-{semantic_hash[:12]}"

    # Determine availability_basis based on what timestamp info is present
    # Pattern from ledger.py _compute_available_at (lines 137-170):
    # Priority: verified_publication > collector_first_seen > declared_lag
    if verified_publication is not None:
        availability_basis = "verified_publication"
    elif received_at is not None:
        availability_basis = "collector_first_seen"
    else:
        availability_basis = "declared_lag"

    # Build the evidence package
    package = {
        "source_id": source_id,
        "station": product.station,
        "issued_at": product.issued_at,
        "valid_start": product.valid_start,
        "valid_end": product.valid_end,
        "amendment_kind": product.amendment_kind,
        "status": product.status,
        "native_semantics_sha256": semantic_hash,
        "product_series": product_series,
    }

    # Add optional timestamp fields
    if received_at is not None:
        package["collector_first_seen"] = _datetime_to_us(received_at)

    if verified_publication is not None:
        package["verified_publication"] = _datetime_to_us(verified_publication)

    if provider is not None:
        package["provider"] = provider

    return package


def compile_raw_reports_to_episode(
    reports: list[dict[str, Any]],
    *,
    default_product_series: str = "default",
) -> tuple[list[dict[str, Any]], dict[str, int] | None]:
    """Compile multiple raw TAF reports into ledger-ready evidence packages.

    Args:
        reports: List of raw report dicts, each containing:
            - raw_text: The raw TAF text
            - station: Station ICAO code
            - issued_at: Issuance time
            - received_at: (optional) Collector observation time
            - verified_publication: (optional) Verified publication time
            - source_id: (optional) Unique identifier
            - provider: (optional) Provider identity
            - product_series: (optional) Product lineage identifier
        default_product_series: Default product_series value for reports
            that don't specify one

    Returns:
        Tuple of (products, collector_first_seen):
            - products: List of evidence packages ready for compile_ledger
            - collector_first_seen: Dict mapping source_id to observation time
              in microseconds (None if no reports have received_at)

    Raises:
        ValueError: If any report cannot be parsed.
    """
    products = []
    collector_first_seen = {}

    for report in reports:
        package = compile_raw_taf_to_evidence(
            report["raw_text"],
            station=report["station"],
            issued_at=report["issued_at"],
            received_at=report.get("received_at"),
            verified_publication=report.get("verified_publication"),
            source_id=report.get("source_id"),
            provider=report.get("provider"),
            product_series=report.get("product_series", default_product_series),
        )
        products.append(package)

        # Build collector_first_seen dict for reports with received_at
        if "collector_first_seen" in package:
            collector_first_seen[package["source_id"]] = package["collector_first_seen"]

    return products, collector_first_seen if collector_first_seen else None


def compute_revision_density(
    products: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, int]]]:
    """Compute revision density statistics per station per month.

    Implements the revision-density audit logic specified in
    DATA_ACQUISITION_PLAN_v16_CN.md section 5.3:
        - AMD events: amendment_kind == "AMD"
        - COR events: amendment_kind == "COR"
        - CNL events: status == "canceled"
        - supersession events: newer issuance in same validity window

    Args:
        products: List of evidence packages (from compile_raw_reports_to_episode
            or directly from synthetic fixtures). Each must have:
            - station
            - issued_at (microseconds)
            - valid_start (microseconds)
            - valid_end (microseconds)
            - amendment_kind ('original', 'AMD', 'COR')
            - status ('active', 'nil', 'canceled')

    Returns:
        Nested dict: {station: {year_month: {amd: N, cor: N, cnl: N, supersession: N}}}
        Example:
            {
                "KJFK": {
                    "2023-01": {"amd": 5, "cor": 2, "cnl": 1, "supersession": 8},
                    "2023-02": {"amd": 3, "cor": 0, "cnl": 0, "supersession": 4},
                },
                "KLAX": {
                    "2023-01": {"amd": 2, "cor": 1, "cnl": 0, "supersession": 3},
                },
            }
    """
    # Group products by station and validity window for supersession analysis
    # Key: (station, valid_start, valid_end) -> list of products
    by_station_window = defaultdict(list)
    for p in products:
        key = (p["station"], p.get("valid_start"), p.get("valid_end"))
        by_station_window[key].append(p)

    # Result structure
    result: dict[str, dict[str, dict[str, int]]] = {}

    # Helper to ensure station/month entry exists
    def ensure_entry(station: str, year_month: str) -> dict[str, int]:
        if station not in result:
            result[station] = {}
        if year_month not in result[station]:
            result[station][year_month] = {
                "amd": 0,
                "cor": 0,
                "cnl": 0,
                "supersession": 0,
            }
        return result[station][year_month]

    # Count AMD, COR, CNL events
    for p in products:
        station = p["station"]
        issued_at = p["issued_at"]
        year_month = _us_to_yearmonth(issued_at)
        entry = ensure_entry(station, year_month)

        if p["amendment_kind"] == "AMD":
            entry["amd"] += 1
        elif p["amendment_kind"] == "COR":
            entry["cor"] += 1

        if p.get("status") == "canceled":
            entry["cnl"] += 1

    # Count supersession events
    # A supersession occurs when a newer issuance exists for the same
    # (station, valid_start, valid_end) window
    for key, group in by_station_window.items():
        if len(group) < 2:
            continue  # No supersession possible with only one product

        station = key[0]

        # Sort by issued_at to find supersession chains
        sorted_group = sorted(group, key=lambda p: p["issued_at"])

        # Each product after the first supersedes the previous one
        for i in range(1, len(sorted_group)):
            superseded_product = sorted_group[i - 1]
            superseding_product = sorted_group[i]

            # Count in the month of the superseding product
            year_month = _us_to_yearmonth(superseding_product["issued_at"])
            entry = ensure_entry(station, year_month)
            entry["supersession"] += 1

    return dict(result)


def identify_stress_and_natural_subsets(
    density: dict[str, dict[str, dict[str, int]]],
    *,
    stress_threshold_factor: float = 1.5,
) -> dict[str, dict[str, str]]:
    """Classify station-months into stress or natural subsets.

    Per DATA_ACQUISITION_PLAN_v16_CN.md section 5.3:
        - Stress subset: months with revision density significantly higher
          than the station's mean
        - Natural subset: months at or near natural frequency distribution

    Args:
        density: Output from compute_revision_density()
        stress_threshold_factor: A month is "stress" if its total revision
            events (AMD+COR+CNL+supersession) exceed the station mean by
            this factor (default 1.5x)

    Returns:
        Nested dict: {station: {year_month: "stress" | "natural"}}
    """
    result: dict[str, dict[str, str]] = {}

    for station, months in density.items():
        # Compute total events per month and station mean
        totals = []
        for year_month, counts in months.items():
            total = counts["amd"] + counts["cor"] + counts["cnl"] + counts["supersession"]
            totals.append((year_month, total))

        if not totals:
            continue

        mean_total = sum(t[1] for t in totals) / len(totals)

        # Classify each month
        result[station] = {}
        for year_month, total in totals:
            if total > mean_total * stress_threshold_factor:
                result[station][year_month] = "stress"
            else:
                result[station][year_month] = "natural"

    return result
