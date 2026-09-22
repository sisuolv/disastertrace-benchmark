"""Access boundary enforcement for real data paths (V17-01 / F04).

This module provides centralized access-boundary enforcement that MUST be called
BEFORE any glob/open of real data files. It enforces:

1. Path canonicalization (defeats symlinks and `..` traversal)
2. Quarantine-holdout segment rejection (segment-based, not substring)
3. Holdout window date rejection (date implied by path or explicit as_of)
4. Allowed root escape rejection

Design rationale (from Codex audit F04):
- The holdout window is sacrosanct; no code path should access it.
- Path checks must happen AFTER resolve() to defeat symlink/traversal attacks.
- A "quarantine_holdout" check must be segment-based (Path.parts), not substring.
- Date checks must use windows_overlap with the holdout window.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .manifest import get_holdout_window, windows_overlap

if TYPE_CHECKING:
    from typing import Callable


class AccessPolicyViolation(Exception):
    """Raised when an access policy check fails.

    This exception indicates that a path or date falls within a protected
    boundary and access is denied. The exception message describes the
    specific violation.
    """
    pass


class ReadVerificationError(Exception):
    """Raised when a read-time content-integrity check fails.

    Distinct from AccessPolicyViolation: this is raised AFTER a path has
    already passed assert_allowed(), when the body bytes do not match the
    sha256 recorded in the corresponding receipt. Callers can use the
    distinct exception types to tell a boundary rejection apart from a
    content-integrity failure.
    """
    pass


@dataclass(frozen=True)
class AccessPolicy:
    """Immutable access policy configuration.

    Encapsulates:
    - allowed_root: The canonical root directory for all allowed paths
    - holdout_start_us / holdout_end_us: The holdout window in microseconds
    - allowed_year_months: Optional set of allowed YYYY-MM strings (if None, all non-holdout months allowed)

    Use assert_allowed() to validate a path before any file access.
    """

    allowed_root: Path
    holdout_start_us: int
    holdout_end_us: int
    allowed_year_months: frozenset[str] | None = None

    def __post_init__(self):
        # Ensure allowed_root is resolved at construction time
        if not self.allowed_root.is_absolute():
            raise ValueError(f"allowed_root must be absolute: {self.allowed_root}")

    @classmethod
    def from_config(
        cls,
        config: dict,
        allowed_root: Path,
        *,
        allowed_year_months: frozenset[str] | None = None,
    ) -> "AccessPolicy":
        """Create an AccessPolicy from a stations_calendar config.

        Args:
            config: The stations_calendar config dict (must have holdout_exclusion).
            allowed_root: The canonical root for all allowed paths.
            allowed_year_months: Optional explicit allowlist of YYYY-MM strings.

        Returns:
            A configured AccessPolicy instance.
        """
        holdout_start_us, holdout_end_us = get_holdout_window(config)

        return cls(
            allowed_root=allowed_root.resolve(),
            holdout_start_us=holdout_start_us,
            holdout_end_us=holdout_end_us,
            allowed_year_months=allowed_year_months,
        )

    def _check_quarantine_segment(self, resolved_path: Path) -> None:
        """Check for quarantine_holdout segment in path parts (not substring).

        This is the F04-compliant check: we examine Path.parts, not a substring.
        A path like '/data/quarantine_holdout_backup/foo' would match via substring
        but not via this segment check (unless 'quarantine_holdout' is an exact segment).
        """
        for part in resolved_path.parts:
            if part == "quarantine_holdout":
                raise AccessPolicyViolation(
                    f"Path contains quarantine_holdout segment: {resolved_path}"
                )

    def _check_root_escape(self, resolved_path: Path) -> None:
        """Check that resolved path is within allowed_root."""
        try:
            resolved_path.relative_to(self.allowed_root)
        except ValueError:
            raise AccessPolicyViolation(
                f"Path escapes allowed root {self.allowed_root}: {resolved_path}"
            )

    def _check_holdout_window(
        self,
        *,
        as_of_us: int | None = None,
        year_month: str | None = None,
    ) -> None:
        """Check that a date doesn't fall within the holdout window.

        Both checks are independent and both run whenever the corresponding
        argument is provided (this is NOT an as_of-takes-precedence check):
        an explicit as_of_us that is safe does not excuse a year_month that
        overlaps holdout, and vice versa. Callers that want a single
        consistent check should pass a mutually-consistent (as_of_us,
        year_month) pair; assert_allowed() enforces that consistency before
        calling here.

        Args:
            as_of_us: Explicit timestamp in microseconds.
            year_month: YYYY-MM string to check.

        Raises:
            AccessPolicyViolation: If either date falls within the holdout window.
        """
        if as_of_us is not None:
            # Point-in-time check: treat as a zero-width window
            # A point is "in" the holdout if it's >= start and < end
            if self.holdout_start_us <= as_of_us < self.holdout_end_us:
                raise AccessPolicyViolation(
                    f"Timestamp {as_of_us} falls within holdout window "
                    f"[{self.holdout_start_us}, {self.holdout_end_us})"
                )
        if year_month is not None:
            # Month check: parse YYYY-MM and check if month window overlaps holdout
            match = re.match(r"^(\d{4})-(\d{2})$", year_month)
            if not match:
                raise ValueError(f"Invalid year_month format (expected YYYY-MM): {year_month}")

            year = int(match.group(1))
            month = int(match.group(2))

            # Month window: first instant of month to first instant of next month
            month_start = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

            month_start_us = int(month_start.timestamp() * 1_000_000)
            month_end_us = int(month_end.timestamp() * 1_000_000)

            if windows_overlap(
                month_start_us, month_end_us,
                self.holdout_start_us, self.holdout_end_us
            ):
                raise AccessPolicyViolation(
                    f"Year-month {year_month} overlaps holdout window "
                    f"[{self.holdout_start_us}, {self.holdout_end_us})"
                )

    def _check_allowed_year_months(self, year_month: str) -> None:
        """Check that year_month is in the allowed set (if configured)."""
        if self.allowed_year_months is not None:
            if year_month not in self.allowed_year_months:
                raise AccessPolicyViolation(
                    f"Year-month {year_month} not in allowed set"
                )

    def _extract_year_month_from_path(self, resolved_path: Path) -> str | None:
        """Attempt to extract YYYY-MM from path components.

        Looks for patterns like:
        - /data/station/2023-08/... (dashed)
        - /data/station_202308.body (underscore-concatenated)

        Returns:
            YYYY-MM string if found, None otherwise.
        """
        # Check for dashed format in path parts
        for part in resolved_path.parts:
            match = re.match(r"^(\d{4})-(\d{2})$", part)
            if match:
                return f"{match.group(1)}-{match.group(2)}"

        # Check for underscore format in filename
        filename = resolved_path.name
        match = re.search(r"_(\d{4})(\d{2})", filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

        # Check for lav-YYYYMM format (LAMP files)
        match = re.search(r"lav-(\d{4})(\d{2})", filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

        return None

    def _year_month_from_us(self, as_of_us: int) -> str:
        """Convert a UTC microsecond timestamp to a YYYY-MM string."""
        dt = datetime.fromtimestamp(as_of_us / 1_000_000, tz=timezone.utc)
        return f"{dt.year:04d}-{dt.month:02d}"

    def assert_allowed(
        self,
        path: str | Path,
        *,
        as_of_us: int | None = None,
        year_month: str | None = None,
    ) -> None:
        """Assert that a path is allowed for access.

        This method MUST be called BEFORE any glob or open operation on real data.
        It performs all checks in the correct order:

        1. Resolve the path (canonicalize, follow symlinks)
        2. Check for quarantine_holdout segment
        3. Check for root escape
        4. Always attempt to extract year-month from the path itself
        5. Fail closed if any explicit as_of_us/year_month disagrees with the
           path-implied month (CE4: an explicit "safe" parameter must never be
           able to override what the path itself says)
        6. Check holdout window for as_of_us and year_month independently
        7. Check against allowed year-months (if configured), using the
           path-implied month when available; fail closed if the allowlist is
           configured but the path's month cannot be determined at all

        Args:
            path: The path to check (will be resolved).
            as_of_us: Optional explicit timestamp for holdout check. Must be
                consistent with the path's own implied month, if any.
            year_month: Optional explicit YYYY-MM for holdout check. Must be
                consistent with the path's own implied month, if any.

        Raises:
            AccessPolicyViolation: If any check fails.
        """
        # Step 1: Resolve the path FIRST (defeats symlinks and ..)
        path_obj = Path(path)
        resolved = path_obj.resolve()

        # Step 2: Check for quarantine_holdout segment (segment-based, not substring)
        self._check_quarantine_segment(resolved)

        # Step 3: Check for root escape
        self._check_root_escape(resolved)

        # Step 4: ALWAYS extract the path-implied month. This is unconditional
        # (unlike the prior implementation, which only attempted extraction
        # when both explicit parameters were absent) so that an explicit
        # parameter can never silently bypass what the path itself implies.
        path_year_month = self._extract_year_month_from_path(resolved)

        as_of_year_month = (
            self._year_month_from_us(as_of_us) if as_of_us is not None else None
        )

        # Step 5: Fail-closed consistency check. Any explicit signal that
        # disagrees with the path-implied month is rejected outright -- this
        # closes CE4 (explicit as_of_us/year_month overriding a
        # differently-monthed path).
        for label, candidate in (("year_month", year_month), ("as_of_us", as_of_year_month)):
            if path_year_month is not None and candidate is not None and candidate != path_year_month:
                raise AccessPolicyViolation(
                    f"Explicit {label} implies {candidate}, which disagrees with "
                    f"the path-implied year-month {path_year_month} for {resolved}. "
                    f"Refusing (fail-closed): an explicit parameter must never "
                    f"override the path's own implied date."
                )

        effective_year_month = path_year_month or year_month or as_of_year_month

        # Step 6: Check holdout window. Run both checks whenever the
        # corresponding value is available -- _check_holdout_window no longer
        # treats as_of_us as taking precedence over year_month.
        if as_of_us is not None or effective_year_month is not None:
            self._check_holdout_window(
                as_of_us=as_of_us,
                year_month=effective_year_month,
            )

        # Step 7: Check allowed year-months (if configured). Fail closed when
        # the allowlist is enabled but the path's own month could not be
        # extracted -- an explicit parameter alone is not sufficient to admit
        # a path whose real month is unknown.
        if self.allowed_year_months is not None:
            if path_year_month is None:
                raise AccessPolicyViolation(
                    f"Year-month allowlist is configured but the path's month "
                    f"could not be extracted: {resolved}. Refusing (fail-closed)."
                )
            self._check_allowed_year_months(path_year_month)
        elif effective_year_month is not None:
            self._check_allowed_year_months(effective_year_month)

    def filter_paths(
        self,
        paths: list[Path],
        *,
        as_of_us: int | None = None,
    ) -> tuple[list[Path], list[tuple[Path, str]]]:
        """Filter a list of paths, returning allowed and rejected paths.

        Args:
            paths: List of paths to filter.
            as_of_us: Optional explicit timestamp for holdout check.

        Returns:
            Tuple of (allowed_paths, rejected_with_reasons).
        """
        allowed = []
        rejected = []

        for path in paths:
            try:
                self.assert_allowed(path, as_of_us=as_of_us)
                allowed.append(path)
            except AccessPolicyViolation as e:
                rejected.append((path, str(e)))

        return allowed, rejected

    def is_holdout_month(self, year_month: str) -> bool:
        """Check if a year-month overlaps the holdout window.

        Args:
            year_month: YYYY-MM string to check.

        Returns:
            True if the month overlaps holdout, False otherwise.
        """
        try:
            self._check_holdout_window(year_month=year_month)
            return False
        except AccessPolicyViolation:
            return True


@dataclass(frozen=True)
class VerifiedInput:
    """Result of a successful read_verified_allowed_file() call.

    Carries the verified body bytes plus a readset record sufficient to
    reconstruct exactly what was read, from where, and with what identity --
    without callers needing to re-open the file themselves.
    """

    canonical_body_path: str
    canonical_receipt_path: str
    size_bytes: int
    raw_text_sha256: str
    receipt_sha256: str
    body: bytes

    def readset_record(self) -> dict:
        """A JSON-serializable readset entry (excludes raw body bytes)."""
        return {
            "canonical_body_path": self.canonical_body_path,
            "canonical_receipt_path": self.canonical_receipt_path,
            "size_bytes": self.size_bytes,
            "raw_text_sha256": self.raw_text_sha256,
            "receipt_sha256": self.receipt_sha256,
        }


def read_verified_allowed_file(
    policy: AccessPolicy,
    body_path: str | Path,
    receipt_path: str | Path,
    *,
    year_month: str | None = None,
) -> VerifiedInput:
    """The single shared entry point for reading a real archive file pair.

    MUST be used instead of a direct open() for any (body, receipt) pair
    under an AccessPolicy-governed root. Order of operations:

    1. assert_allowed() on the body path (boundary/holdout/allowlist checks,
       fail-closed, run BEFORE any glob or open of either file).
    2. assert_allowed() on the receipt path (same checks).
    3. Read the receipt JSON and take its declared sha256.
    4. Read the body bytes and recompute sha256.
    5. Raise ReadVerificationError if the recomputed hash does not match the
       receipt's declared hash (content-integrity failure, distinct from a
       boundary violation).

    Returns:
        A VerifiedInput with the body bytes and a readset record.

    Raises:
        AccessPolicyViolation: If either path fails the access policy.
        ReadVerificationError: If body bytes do not match the receipt's
            declared sha256, or the receipt is missing a sha256 field.
    """
    policy.assert_allowed(body_path, year_month=year_month)
    policy.assert_allowed(receipt_path, year_month=year_month)

    body_resolved = Path(body_path).resolve()
    receipt_resolved = Path(receipt_path).resolve()

    with open(receipt_resolved, "r") as f:
        receipt = json.load(f)

    expected_sha = receipt.get("sha256")
    if not expected_sha:
        raise ReadVerificationError(
            f"Receipt is missing a sha256 field: {receipt_resolved}"
        )

    with open(body_resolved, "rb") as f:
        body_bytes = f.read()

    actual_sha = hashlib.sha256(body_bytes).hexdigest()
    if actual_sha != expected_sha:
        raise ReadVerificationError(
            f"Body SHA256 mismatch for {body_resolved}: "
            f"receipt declares {expected_sha}, actual content hashes to {actual_sha}"
        )

    return VerifiedInput(
        canonical_body_path=str(body_resolved),
        canonical_receipt_path=str(receipt_resolved),
        size_bytes=len(body_bytes),
        raw_text_sha256=actual_sha,
        receipt_sha256=expected_sha,
        body=body_bytes,
    )


def make_policy_for_real_v16(
    config: dict,
    *,
    allowed_year_months: frozenset[str] | None = None,
) -> AccessPolicy:
    """Create an AccessPolicy for the real v16 data archive.

    This is a convenience factory that uses the standard data_real_v16 path.

    Args:
        config: The stations_calendar config dict.
        allowed_year_months: Optional explicit allowlist of YYYY-MM strings.

    Returns:
        A configured AccessPolicy for data_real_v16.
    """
    data_root = Path("/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16")

    return AccessPolicy.from_config(
        config,
        allowed_root=data_root,
        allowed_year_months=allowed_year_months,
    )
