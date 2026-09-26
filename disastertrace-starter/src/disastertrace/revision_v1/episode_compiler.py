"""Episode compiler: bridge raw TAF/METAR text to ledger-ready evidence packages.

This module provides three data ingestion pathways:

1. TAF from single raw text: compile_raw_taf_to_evidence() parses a single TAF
   report using aviation.py's parse_taf(), computes semantic hash via
   versions.py's taf_semantics(), and emits a ledger-ready evidence package.

2. TAF from AFOS multi-bulletin streams: split_afos_stream() splits NWS AFOS
   archive format (SOH/ETX framed with WMO headers) into individual bulletins,
   and compile_afos_taf_stream() compiles each into evidence packages. This
   handles the raw-text stream format returned by IEM's afos/retrieve.py.

3. METAR observations -> binary outcomes: compile_asos_csv_to_observations()
   parses IEM ASOS CSV format into MetarReport objects, and
   compile_metar_outcomes() evaluates visibility against TargetSpec thresholds
   to produce the dict[str, int|None] outcome shape for trajectory_score_Q.

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

import csv
import io
import re
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from ..monitoring_v1.providers.aviation import (
    MetarReport,
    TafProduct,
    day_time,
    parse_metar,
    parse_taf,
)
from ..monitoring_v1.providers.versions import latest_issuance, taf_semantics
from ..monitoring_v1.support import Interval, classify
from ..monitoring_v1.targets import TargetSpec, canonical_hash, utc_us


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


# ---------------------------------------------------------------------------
# Part 1: METAR observation ingestion and outcome compilation
# ---------------------------------------------------------------------------


def compile_asos_csv_to_observations(
    csv_text: str,
    *,
    station: str,
) -> tuple[list[MetarReport], list[dict]]:
    """Parse IEM ASOS CSV text into MetarReport observations.

    Args:
        csv_text: Full CSV text from IEM ASOS download (includes header row).
            Expected columns: station,valid,lon,lat,elevation,...,metar,snowdepth
            The 'metar' column contains raw METAR text, 'valid' is observation time.
        station: Station ICAO code to filter for (e.g., "KSFO"). Rows not matching
            are silently skipped (allowing multi-station CSV files).

    Returns:
        Tuple of (observations, skipped):
            - observations: List of successfully parsed MetarReport objects
            - skipped: List of dicts describing rows that failed to parse, each with:
                - row_index: 0-based row index in the CSV (excluding header)
                - raw_metar: The raw metar value that failed
                - valid: The valid timestamp string
                - error: Exception message

    Notes:
        - IEM uses 'M' for missing values in numeric columns. The 'metar' column
          itself is typically not 'M' but can be empty/blank for missing reports.
        - Rows with missing/empty metar values are collected in skipped, not raised.
        - The 'valid' column format is "YYYY-MM-DD HH:MM" (naive, assumed UTC).
    """
    observations: list[MetarReport] = []
    skipped: list[dict] = []

    reader = csv.DictReader(io.StringIO(csv_text))

    for row_index, row in enumerate(reader):
        raw_metar = row.get("metar", "")
        valid_str = row.get("valid", "")

        # Skip rows with missing/blank metar
        if not raw_metar or raw_metar.strip() == "" or raw_metar.strip() == "M":
            skipped.append({
                "row_index": row_index,
                "raw_metar": raw_metar,
                "valid": valid_str,
                "error": "Missing or blank metar value",
            })
            continue

        # Check station filter - the station column in IEM ASOS is typically the
        # 3-letter code (e.g., "SFO"), but the metar text starts with ICAO (e.g., "KSFO")
        # We check if the metar contains the requested station code.
        # Note: METAR may start with "SPECI " prefix before the station code.
        raw_stripped = raw_metar.strip()
        metar_station_text = raw_stripped
        if metar_station_text.startswith("SPECI "):
            metar_station_text = metar_station_text[6:]  # Strip "SPECI " prefix
        if not metar_station_text.startswith(station):
            # Row is for a different station, skip silently (not an error)
            continue

        # Parse the valid timestamp - format is "YYYY-MM-DD HH:MM" (naive UTC)
        try:
            if not valid_str or valid_str.strip() == "" or valid_str.strip() == "M":
                raise ValueError("Missing valid timestamp")

            # Parse naive datetime and make it UTC-aware
            obs_dt = datetime.strptime(valid_str.strip(), "%Y-%m-%d %H:%M")
            obs_dt = obs_dt.replace(tzinfo=timezone.utc)
            observation_time_iso = obs_dt.isoformat()
        except Exception as e:
            skipped.append({
                "row_index": row_index,
                "raw_metar": raw_metar,
                "valid": valid_str,
                "error": f"Invalid valid timestamp: {e}",
            })
            continue

        # Parse the METAR using aviation.py's parse_metar
        # Detect SPECI prefix to set correct report_type.
        # Note: Real archived METAR text commonly omits the SPECI prefix even for
        # special observations (this is a known IEM archive characteristic), so
        # report_type on the resulting object should NOT be relied upon by any
        # downstream "is this the routine/hourly report" logic - that determination
        # needs a different, timestamp-based method.
        try:
            raw_stripped = raw_metar.strip()
            if raw_stripped.startswith("SPECI "):
                report_type = "special"
            else:
                report_type = "routine"
            metar_report = parse_metar(
                raw=raw_stripped,
                observation_time=observation_time_iso,
                report_type=report_type,
            )
            observations.append(metar_report)
        except Exception as e:
            skipped.append({
                "row_index": row_index,
                "raw_metar": raw_metar,
                "valid": valid_str,
                "error": str(e),
            })

    return observations, skipped


def compile_metar_outcomes(
    observations: list[MetarReport],
    targets: list[TargetSpec],
) -> dict[str, int | None]:
    """Evaluate METAR observations against target specifications to produce outcomes.

    For each TargetSpec, selects observations whose observation_time falls within
    the target's physical window (physical_start <= observation_time < physical_end)
    and station matches. Evaluates the visibility interval against the operator/threshold
    predicate using ternary logic:
        - 1 if the interval definitively satisfies the predicate
        - 0 if the interval definitively fails the predicate
        - None if the predicate's cutoff falls within the interval (ambiguous) OR
          no observations exist in the window

    Args:
        observations: List of MetarReport objects from compile_asos_csv_to_observations
        targets: List of TargetSpec objects defining evaluation windows and predicates.
            Each target has:
            - target_id: unique identifier
            - entity: station code (e.g., "KSFO")
            - physical_start: window start in microseconds
            - physical_end: window end in microseconds
            - event_operator: one of {lt, le, gt, ge}
            - threshold: value to compare against visibility (in meters)

    Returns:
        Dict mapping target_id -> outcome (int 0, 1, or None).
        Satisfies metrics.py's trajectory_score_Q_with_bounds dict[str, int|None] shape.
        All non-None values are strictly int (not bool, not numpy), per
        _validate_binary_outcome at metrics.py line 188.

    Notes:
        - Uses support.py's classify() function for ternary interval evaluation:
          "supported" -> 1, "refuted" -> 0, "undetermined" -> None
        - If multiple observations fall in a target's window, uses the last one
          (closest to window end) for evaluation.
        - Missing visibility in MetarReport (visibility=None) -> None outcome.
    """
    outcomes: dict[str, int | None] = {}

    for target in targets:
        target_id = target.target_id
        station = target.entity
        physical_start = target.physical_start
        physical_end = target.physical_end
        event_operator = target.event_operator
        threshold = target.threshold

        # Select observations in the target's window for the matching station
        matching_obs = [
            obs for obs in observations
            if obs.station == station
            and physical_start <= obs.observation_time < physical_end
        ]

        if not matching_obs:
            # No observations in window -> outcome is None (missing)
            outcomes[target_id] = None
            continue

        # Use the last observation in the window (sorted by observation_time)
        matching_obs.sort(key=lambda o: o.observation_time)
        obs = matching_obs[-1]

        # Check if visibility is present
        if obs.visibility is None:
            outcomes[target_id] = None
            continue

        # Use classify() from support.py for ternary evaluation
        # classify returns "supported", "refuted", or "undetermined"
        classification = classify(obs.visibility, event_operator, threshold)

        if classification == "supported":
            outcomes[target_id] = int(1)  # Explicit int(), not bool
        elif classification == "refuted":
            outcomes[target_id] = int(0)  # Explicit int(), not bool
        else:  # "undetermined" or "inconsistent"
            outcomes[target_id] = None

    return outcomes


# ---------------------------------------------------------------------------
# Part 2: AFOS raw-text stream ingestion for TAF data
# ---------------------------------------------------------------------------


def split_afos_stream(text: str) -> list[str]:
    """Split an AFOS/NWS text product archive into individual bulletin frames.

    AFOS archives concatenate multiple bulletins, each framed by:
        - \\x01 (SOH, Start of Header) at the beginning
        - \\x03 (ETX, End of Text) at the end

    Each frame contains:
        - Sequence number line (e.g., "878")
        - WMO header line (e.g., "FTUS46 KMTR 072320")
        - PIL line (e.g., "TAFSFO")
        - Product body (e.g., TAF content ending with "=")
        - Optional blank lines

    Args:
        text: Raw AFOS stream text, potentially containing multiple bulletins.

    Returns:
        List of individual bulletin text blocks. Each block includes its WMO
        header (stripping happens in compile_afos_taf_stream). Returns empty
        list for empty/malformed input with no valid frames.

    Notes:
        - Handles the \\x01...\\x03 framing from IEM's afos/retrieve.py endpoint.
        - Gracefully returns [] for empty or header-only streams.
    """
    if not text or not text.strip():
        return []

    # Split on SOH (\\x01) to find frame starts
    # Each frame runs from after SOH until ETX (\\x03)
    SOH = "\x01"
    ETX = "\x03"

    frames: list[str] = []

    # Find all frames by looking for SOH...ETX pairs
    parts = text.split(SOH)

    for part in parts:
        if not part.strip():
            continue

        # Find ETX in this part
        etx_pos = part.find(ETX)
        if etx_pos != -1:
            # Extract content between implicit SOH (start of part) and ETX
            frame_content = part[:etx_pos].strip()
            if frame_content:
                frames.append(frame_content)
        else:
            # No ETX found - might be partial/malformed, but include if has content
            frame_content = part.strip()
            if frame_content:
                frames.append(frame_content)

    return frames


def compile_afos_taf_stream(
    stream_text: str,
    *,
    station: str,
    reference_month: str,
    product_series: str = "default",
    return_parsed: bool = False,
    **passthrough,
) -> tuple[list[dict], list[dict]] | tuple[list[dict], list[dict], list[dict]]:
    """Compile an AFOS multi-bulletin TAF stream into ledger-ready evidence packages.

    Args:
        stream_text: Raw AFOS stream text from IEM's afos/retrieve.py endpoint.
        station: Station ICAO code to filter for (e.g., "KSFO").
        reference_month: Month context for day_time() disambiguation, format "YYYY-MM".
            Used to resolve DDHHMM tokens to full datetimes.
        product_series: Product lineage identifier (default "default").
        **passthrough: Additional kwargs passed to compile_raw_taf_to_evidence
            (e.g., provider, received_at, verified_publication).

    Returns:
        Tuple of (evidence_packages, skipped):
            - evidence_packages: List of dicts ready for compile_ledger, each with:
                - source_id: unique identifier (collision-free within this stream)
                - station, issued_at, valid_start, valid_end, amendment_kind, status
                - native_semantics_sha256: semantic content hash
                - wmo_bbb: WMO amendment/correction indicator (or None)
                - receipt_seq: int position in AFOS archive (higher = newer/later received)
                - receipt_stream: str "{station}:{reference_month}" for cross-stream guard
            - skipped: List of dicts describing frames that failed to parse, each with:
                - frame_index: 0-based index of the frame
                - raw_frame: The raw frame text (truncated for display)
                - error: Exception message

    Direction contract (receipt_seq):
        AFOS .body archives are stored newest-first. receipt_seq increases with
        issuance/receipt time: first frame in file (newest) gets len(frames)-1,
        last frame (oldest) gets 0. This direction is verified at compile time
        via the reverse-chronology premise gate.

    Premise gate (reverse-chronology):
        After compiling all frames, verifies that issued_at is non-increasing in
        file order (ties allowed). If violated, receipt_seq and receipt_stream
        are stripped from ALL packages (all-or-nothing fail-safe), and the legacy
        behavior (no receipt ordering) applies.

    Collision-free source_id:
        When the premise gate passes (packages carry receipt_seq), source_id
        collisions are resolved by suffixing: the earliest-received twin (min
        receipt_seq) keeps the original id; later twins get "-r{seq:06d}" suffix.
        This guarantees uniqueness within one stream; direct callers of
        compile_raw_taf_to_evidence are outside this guarantee.

    Hash safety:
        native_semantics_sha256 is computed from the parsed TafProduct BEFORE
        receipt_seq/receipt_stream are attached, so these keys cannot affect
        the frozen hash contract.

    Notes:
        - Uses split_afos_stream() to extract individual bulletin frames.
        - Strips WMO header lines before passing to parse_taf (the TAF parser).
        - Extracts issued_at from the DDHHMM token in the product header using
          aviation.py's day_time() helper.
        - Reuses compile_raw_taf_to_evidence() for actual TAF parsing - does not
          reimplement TAF parsing logic.
    """
    evidence_packages: list[dict] = []
    parsed_records: list[dict] = []
    skipped: list[dict] = []

    frames = split_afos_stream(stream_text)

    if not frames:
        return [], []

    # Build reference datetime from reference_month
    try:
        ref_year, ref_month = reference_month.split("-")
        reference_dt = datetime(int(ref_year), int(ref_month), 15, 12, 0, tzinfo=timezone.utc)
    except Exception as e:
        # Invalid reference_month format - all frames will fail
        for frame_index, frame in enumerate(frames):
            skipped.append({
                "frame_index": frame_index,
                "raw_frame": frame[:200] + ("..." if len(frame) > 200 else ""),
                "error": f"Invalid reference_month format: {e}",
            })
        return [], skipped

    for frame_index, frame in enumerate(frames):
        try:
            # Parse the frame structure:
            # Line 0: sequence number (e.g., "878")
            # Line 1: WMO header "TTAAII CCCC DDHHMM [BBB]" (e.g., "FTUS46 KMTR 072320" or
            #         "FTUS46 KMTR 312100 AAA" with amendment suffix)
            # Line 2: PIL (e.g., "TAFSFO")
            # Line 3+: Product body (TAF...) ending with "="

            lines = frame.strip().split("\n")

            # Find the WMO header line (pattern: TTAAII CCCC DDHHMM [BBB])
            # BBB is the optional amendment/correction indicator (AAA, AAB, CCA, etc.)
            wmo_header_line = None
            wmo_line_idx = None
            wmo_bbb = None
            wmo_pattern = re.compile(r"^[A-Z]{4}\d{2}\s+[A-Z]{4}\s+(\d{6})(?:\s+([A-Z]{3}))?$")
            for i, line in enumerate(lines):
                match = wmo_pattern.match(line.strip())
                if match:
                    wmo_header_line = line.strip()
                    wmo_line_idx = i
                    wmo_bbb = match.group(2)  # None if no BBB suffix
                    break

            if wmo_header_line is None:
                raise ValueError("WMO header line not found in frame")

            # Extract DDHHMM from WMO header for issued_at
            wmo_match = wmo_pattern.match(wmo_header_line)
            ddhhmm = wmo_match.group(1)
            day = int(ddhhmm[:2])
            hour = int(ddhhmm[2:4])
            minute = int(ddhhmm[4:6])

            # Resolve the DDHHMM to a full timestamp within the known reference_month.
            # We do NOT use day_time() here because its "nearest month" heuristic can
            # resolve day-31 headers into the wrong month when the reference is mid-month
            # (e.g., day 31 with reference Jan 15 would incorrectly resolve to Dec 31).
            # Instead, we construct the datetime directly using the caller-supplied
            # reference_month, which is known to be the actual calendar month these
            # bulletins were retrieved for (see sibling receipt .json for evidence:
            # params_used.sdate/edate confirm the retrieval window).
            try:
                issued_dt = datetime(
                    int(ref_year), int(ref_month), day, hour, minute, tzinfo=timezone.utc
                )
            except ValueError:
                # Day is not valid for this month (e.g., day 31 in a 30-day month,
                # or day 29+ in February of a non-leap year).
                skipped.append({
                    "frame_index": frame_index,
                    "raw_frame": frame[:200] + ("..." if len(frame) > 200 else ""),
                    "error": f"wmo_day_outside_reference_month: day {day} not valid in {ref_year}-{ref_month}",
                })
                continue

            issued_at_us = utc_us(issued_dt.isoformat())
            issued_at_iso = issued_dt.isoformat().replace("+00:00", "Z")

            # Find where the actual TAF body starts
            # The TAF line is typically after the PIL line (TAFSFO, etc.)
            # Look for a line starting with "TAF" or the station code
            taf_start_idx = None
            for i in range(wmo_line_idx + 1, len(lines)):
                line_stripped = lines[i].strip()
                # Skip empty lines and PIL lines (3-5 chars, all alpha)
                if not line_stripped:
                    continue
                if len(line_stripped) <= 6 and line_stripped.isalpha():
                    # Likely PIL line (e.g., "TAFSFO")
                    continue
                if line_stripped.startswith("TAF") or line_stripped.startswith(station):
                    taf_start_idx = i
                    break

            if taf_start_idx is None:
                # Try to find any TAF-ish content
                for i in range(wmo_line_idx + 1, len(lines)):
                    line_stripped = lines[i].strip()
                    if "TAF" in line_stripped or station in line_stripped:
                        taf_start_idx = i
                        break

            if taf_start_idx is None:
                raise ValueError(f"TAF content not found for station {station}")

            # Extract TAF body (from TAF line to end, including "=")
            taf_lines = lines[taf_start_idx:]
            raw_taf_text = " ".join(line.strip() for line in taf_lines if line.strip())

            # Remove trailing "=" if present (parse_taf handles this)
            raw_taf_text = raw_taf_text.rstrip("=").strip()

            # Verify the TAF is for the requested station
            if station not in raw_taf_text:
                raise ValueError(f"TAF does not contain station {station}")

            # Call compile_raw_taf_to_evidence (reuse existing function)
            package = compile_raw_taf_to_evidence(
                raw_taf_text,
                station=station,
                issued_at=issued_at_us,
                product_series=product_series,
                **passthrough,
            )
            # Add WMO BBB (amendment/correction indicator) to the package.
            # This is extracted from the WMO header line (e.g., "AAA" for first
            # amendment, "CCA" for first correction). None if no BBB suffix.
            package["wmo_bbb"] = wmo_bbb

            # Attach receipt ordering keys (D1).
            # receipt_seq: position in archive, computed from total frame count
            # (including skipped frames to preserve monotonicity across gaps).
            # Direction: file's first/newest frame gets highest seq; last/oldest gets 0.
            # receipt_stream: deterministic cross-stream guard.
            package["receipt_seq"] = len(frames) - 1 - frame_index
            package["receipt_stream"] = f"{station}:{reference_month}"

            evidence_packages.append(package)
            if return_parsed:
                parsed_records.append({
                    "source_id": package["source_id"],
                    "product": parse_taf(raw_taf_text, station=station, archive_issue=issued_at_iso),
                    "raw": raw_taf_text,
                    "frame_index": frame_index,
                    "package_ref": package,
                })

        except Exception as e:
            skipped.append({
                "frame_index": frame_index,
                "raw_frame": frame[:200] + ("..." if len(frame) > 200 else ""),
                "error": str(e),
            })

    # -------------------------------------------------------------------------
    # D1 Premise gate: verify reverse-chronology (issued_at non-increasing in file order)
    # -------------------------------------------------------------------------
    premise_violated = False
    if len(evidence_packages) >= 2:
        # Packages were appended in file order, so we check adjacent pairs
        for i in range(1, len(evidence_packages)):
            prev_issued = evidence_packages[i - 1]["issued_at"]
            curr_issued = evidence_packages[i]["issued_at"]
            if curr_issued > prev_issued:
                # Forward-chronological detected - premise violated
                premise_violated = True
                break

    if premise_violated:
        # Strip receipt_seq and receipt_stream from ALL packages (all-or-nothing)
        for pkg in evidence_packages:
            pkg.pop("receipt_seq", None)
            pkg.pop("receipt_stream", None)
    else:
        # -------------------------------------------------------------------------
        # D3 Collision-free source_id: resolve duplicates by receipt_seq
        # -------------------------------------------------------------------------
        # Group packages by source_id
        from collections import defaultdict
        sid_groups: dict[str, list[dict]] = defaultdict(list)
        for pkg in evidence_packages:
            sid_groups[pkg["source_id"]].append(pkg)

        # For collision groups, suffix all but the earliest-received (min receipt_seq)
        for sid, group in sid_groups.items():
            if len(group) > 1:
                # Sort by receipt_seq ascending (earliest-received first)
                group.sort(key=lambda p: p["receipt_seq"])
                # First one (min seq) keeps original id; rest get suffixed
                for pkg in group[1:]:
                    pkg["source_id"] = f"{sid}-r{pkg['receipt_seq']:06d}"

        # Assert uniqueness after suffixing
        all_sids = [pkg["source_id"] for pkg in evidence_packages]
        assert len(set(all_sids)) == len(all_sids), (
            f"source_id collision persists after suffixing: {len(all_sids)} ids, "
            f"{len(set(all_sids))} unique"
        )

    if return_parsed:
        # Keep the parsed sidecar aligned with the final package source_id after
        # receipt-order collision suffixing.  The default two-tuple API and all
        # native semantic hashes remain unchanged.
        for record in parsed_records:
            record["source_id"] = record["package_ref"]["source_id"]
            record.pop("package_ref", None)
        return evidence_packages, skipped, parsed_records
    return evidence_packages, skipped
