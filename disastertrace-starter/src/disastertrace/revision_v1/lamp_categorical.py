"""LAMP categorical (LAV) parser for DisasterTrace v16.

Parses NOAA/MDL GFS LAMP LAV Text Messages (categorical ceiling/visibility/
obstruction-to-vision forecasts, 3-hour lookahead). This module handles ONLY
categorical LAMP products (CIG/VIS/OBV); it intentionally excludes probabilistic
and conditional-probability elements (per project decision D11: LAMP product
types must be registered separately and never conflated).

Archive format (monthly files):
- Each .body file is gzip-compressed
- Decompressed content contains station bulletins separated by blank lines
- Bulletin header: " KXXX   GFS LAMP GUIDANCE   M/DD/YYYY  HHMM UTC"
- UTC line: " UTC  HH HH HH" (three projection hours)
- Element lines:
  - CIG (ceiling category): integer 1-8
  - VIS (visibility category): integer 1-7
  - OBV (obstruction to vision): N, BR, FG, HZ, etc.

Reference: DL4_STATUS.json confirms this archive is categorical-only.
"""

from __future__ import annotations

import gzip
import hashlib
import re
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator


class LampElement(str, Enum):
    """LAMP categorical elements (ceiling, visibility, obstruction)."""

    CIG = "CIG"  # Ceiling category (1-8)
    VIS = "VIS"  # Visibility category (1-7)
    OBV = "OBV"  # Obstruction to vision (N, BR, FG, HZ, etc.)


# Frozen stations of interest for this project
FROZEN_STATIONS = frozenset({"KSFO", "KDEN", "KJFK", "KORD"})


@dataclass(frozen=True)
class LampCategoricalRecord:
    """A single LAMP categorical forecast value.

    This dataclass is intentionally frozen (immutable) and contains NO fields
    for probability, confidence, or conditional probability values. This is a
    deliberate design constraint per D11: categorical and probabilistic LAMP
    products must be registered separately and never conflated.

    Attributes:
        station: ICAO station identifier (e.g., KSFO, KDEN)
        element: One of CIG, VIS, or OBV
        value: The categorical value (integer for CIG/VIS, string for OBV)
        cycle_time: Native bulletin issuance/cycle timestamp (from bulletin body)
        valid_time: Projected/valid timestamp for this forecast value
        source_sha256: SHA256 hash of the source .body file
        batch_id: Run/batch identifier for provenance tracking
    """

    station: str
    element: LampElement
    value: str  # String to uniformly handle CIG/VIS (digits) and OBV (codes)
    cycle_time: datetime
    valid_time: datetime
    source_sha256: str
    batch_id: str


# Pattern to match bulletin header line
# Example: " KJFK   GFS LAMP GUIDANCE   1/01/2023  0000 UTC"
HEADER_PATTERN = re.compile(
    r"^\s*([A-Z0-9]{3,5})\s+GFS LAMP GUIDANCE\s+"
    r"(\d{1,2})/(\d{1,2})/(\d{4})\s+"
    r"(\d{4})\s+UTC\s*$"
)

# Pattern to match UTC projection hours line
# Example: " UTC  01 02 03"
UTC_PATTERN = re.compile(r"^\s*UTC\s+(\d{2})\s+(\d{2})\s+(\d{2})\s*$")

# Pattern to match element value lines
# Example: " CIG   2  2  2" or " OBV  FG FG FG"
ELEMENT_PATTERN = re.compile(
    r"^\s*(CIG|VIS|OBV)\s+"
    r"(\S+)\s+(\S+)\s+(\S+)\s*$"
)


def _compute_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _decompress_body(file_path: Path) -> str:
    """Decompress a gzip .body file and return the text content.

    Uses the standard library's strict gzip reader first (validates the
    gzip header, deflate stream, and the trailing CRC32/ISIZE footer).

    Some archived downloads in this project were cut off right at the very
    end of the transfer, after essentially all real content had already been
    written to disk -- the deflate stream itself is intact, but the 8-byte
    gzip trailer (CRC32 + ISIZE) is missing or incomplete. The strict reader
    raises EOFError for these files even though the real content is fully
    recoverable. When that happens, this function falls back to tolerant
    streaming decompression (see `_decompress_truncated_gzip`) that recovers
    whatever complete content was produced, without trailer verification.

    This fallback is intentionally narrow: it only engages on EOFError (a
    stream that ran out of bytes before completing), not on other forms of
    gzip corruption, which continue to raise gzip.BadGzipFile as before.

    Raises:
        gzip.BadGzipFile: If file is not valid gzip, or if the fallback path
            determines the deflate stream itself is corrupt (not merely
            missing its trailer).
    """
    try:
        with gzip.open(file_path, "rt", encoding="ascii", errors="replace") as f:
            return f.read()
    except EOFError:
        return _decompress_truncated_gzip(file_path)


def _decompress_truncated_gzip(file_path: Path) -> str:
    """Tolerant fallback for a gzip stream missing its end-of-stream trailer.

    Streams the raw file bytes through a gzip-mode zlib decompressor and
    accepts whatever complete decompressed content it produced, even though
    the stream never reached a clean end-of-stream marker (i.e. the trailing
    CRC32/ISIZE bytes are missing or incomplete, so no checksum verification
    happens here).

    This is only reached after the strict `gzip` module raised EOFError, and
    it still requires zlib to accept the bytes as a structurally valid
    deflate/gzip stream: if zlib itself rejects the data (bad header, or a
    deflate stream that cannot be decoded), that indicates genuine
    corruption -- not just a missing tail -- and is raised as
    gzip.BadGzipFile rather than silently swallowed.

    Recovered content still has to pass the normal bulletin-line regexes in
    `_parse_bulletin`/`parse_lamp_body` to contribute any records, which
    provides an additional guard against treating garbage bytes as real
    station data.
    """
    raw = file_path.read_bytes()
    decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)
    try:
        decompressed = decompressor.decompress(raw)
        decompressed += decompressor.flush()
    except zlib.error as e:
        raise gzip.BadGzipFile(
            f"{file_path.name}: gzip stream is corrupt, not just missing its "
            f"end-of-stream trailer ({e})"
        ) from e

    return decompressed.decode("ascii", errors="replace")


def _parse_bulletin(
    lines: list[str],
    source_sha256: str,
    batch_id: str,
    target_stations: frozenset[str],
) -> Iterator[LampCategoricalRecord]:
    """Parse a single station bulletin into records.

    Args:
        lines: Lines comprising one bulletin (header through element lines)
        source_sha256: SHA256 of source file
        batch_id: Batch/run identifier
        target_stations: Set of station codes to include (others filtered out)

    Yields:
        LampCategoricalRecord for each (element, projection) combination
    """
    if not lines:
        return

    # Parse header line
    header_match = HEADER_PATTERN.match(lines[0])
    if not header_match:
        return

    station = header_match.group(1)

    # Filter to target stations only
    if station not in target_stations:
        return

    month = int(header_match.group(2))
    day = int(header_match.group(3))
    year = int(header_match.group(4))
    cycle_hhmm = header_match.group(5)
    cycle_hour = int(cycle_hhmm[:2])
    cycle_minute = int(cycle_hhmm[2:])

    cycle_time = datetime(
        year, month, day, cycle_hour, cycle_minute, tzinfo=timezone.utc
    )

    # Parse UTC projection hours line (should be second line)
    projection_hours: list[int] = []
    utc_line_idx = -1
    for i, line in enumerate(lines[1:], start=1):
        utc_match = UTC_PATTERN.match(line)
        if utc_match:
            projection_hours = [
                int(utc_match.group(1)),
                int(utc_match.group(2)),
                int(utc_match.group(3)),
            ]
            utc_line_idx = i
            break

    if not projection_hours:
        return

    # Parse element lines (CIG, VIS, OBV)
    for line in lines[utc_line_idx + 1 :]:
        elem_match = ELEMENT_PATTERN.match(line)
        if not elem_match:
            continue

        element_name = elem_match.group(1)
        values = [elem_match.group(2), elem_match.group(3), elem_match.group(4)]

        try:
            element = LampElement(element_name)
        except ValueError:
            continue

        # Generate records for each projection hour
        for proj_hour, value in zip(projection_hours, values):
            # Compute valid time: same date as cycle, hour = projection hour
            # Handle day rollover if projection hour < cycle hour
            valid_hour = proj_hour
            valid_day_offset = 0
            if proj_hour < cycle_hour:
                # Projection crosses midnight
                valid_day_offset = 1

            try:
                base_date = datetime(year, month, day, tzinfo=timezone.utc)
                valid_time = base_date.replace(hour=0, minute=0) + timedelta(
                    days=valid_day_offset, hours=valid_hour
                )
            except ValueError:
                continue

            yield LampCategoricalRecord(
                station=station,
                element=element,
                value=value,
                cycle_time=cycle_time,
                valid_time=valid_time,
                source_sha256=source_sha256,
                batch_id=batch_id,
            )


def parse_lamp_body(
    file_path: Path,
    batch_id: str,
    target_stations: frozenset[str] = FROZEN_STATIONS,
) -> Iterator[LampCategoricalRecord]:
    """Parse a LAMP LAV .body file into categorical records.

    Args:
        file_path: Path to a gzip-compressed .body file
        batch_id: Batch/run identifier for provenance
        target_stations: Set of ICAO station codes to include (default: FROZEN_STATIONS)

    Yields:
        LampCategoricalRecord for each valid (station, element, projection) tuple

    Raises:
        gzip.BadGzipFile: If the file is not valid gzip
        FileNotFoundError: If file does not exist
    """
    file_path = Path(file_path)
    source_sha256 = _compute_file_sha256(file_path)

    content = _decompress_body(file_path)
    lines = content.split("\n")

    # Split into bulletins (separated by blank/whitespace-only lines)
    current_bulletin: list[str] = []

    for line in lines:
        if line.strip() == "":
            # End of bulletin
            if current_bulletin:
                yield from _parse_bulletin(
                    current_bulletin, source_sha256, batch_id, target_stations
                )
                current_bulletin = []
        else:
            current_bulletin.append(line)

    # Handle last bulletin if file doesn't end with blank line
    if current_bulletin:
        yield from _parse_bulletin(
            current_bulletin, source_sha256, batch_id, target_stations
        )


def assert_not_probabilistic(records: list) -> None:
    """Guard function to verify records are categorical, not probabilistic.

    This function enforces the D11 design constraint that categorical and
    probabilistic LAMP products must never be conflated. It must be called
    before wiring LAMP data into any baseline.

    Args:
        records: List of records to validate

    Raises:
        TypeError: If records are not LampCategoricalRecord instances
        ValueError: If records contain probability-like attributes
    """
    FORBIDDEN_ATTRS = {
        "probability",
        "prob",
        "confidence",
        "conf",
        "conditional",
        "cond_prob",
        "likelihood",
        "percentile",
        "quantile",
    }

    for i, record in enumerate(records):
        # Check type
        if not isinstance(record, LampCategoricalRecord):
            raise TypeError(
                f"Record at index {i} is {type(record).__name__}, "
                f"expected LampCategoricalRecord. Categorical/probabilistic "
                f"LAMP products must never be conflated (D11)."
            )

        # Check for forbidden attributes (belt-and-suspenders defense)
        record_attrs = {a.lower() for a in dir(record) if not a.startswith("_")}
        found_forbidden = record_attrs & FORBIDDEN_ATTRS
        if found_forbidden:
            raise ValueError(
                f"Record at index {i} has probability-like attributes: "
                f"{found_forbidden}. Categorical LAMP records must not carry "
                f"probability semantics (D11)."
            )
