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

        Args:
            as_of_us: Explicit timestamp in microseconds (takes precedence).
            year_month: YYYY-MM string to check (used if as_of_us not provided).

        Raises:
            AccessPolicyViolation: If the date falls within the holdout window.
        """
        if as_of_us is not None:
            # Point-in-time check: treat as a zero-width window
            # A point is "in" the holdout if it's >= start and < end
            if self.holdout_start_us <= as_of_us < self.holdout_end_us:
                raise AccessPolicyViolation(
                    f"Timestamp {as_of_us} falls within holdout window "
                    f"[{self.holdout_start_us}, {self.holdout_end_us})"
                )
        elif year_month is not None:
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
        4. Check for holdout window overlap
        5. Check against allowed year-months (if configured)

        Args:
            path: The path to check (will be resolved).
            as_of_us: Optional explicit timestamp for holdout check.
            year_month: Optional explicit YYYY-MM for holdout check.
                If neither as_of_us nor year_month is provided, attempts to
                extract year-month from the path itself.

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

        # Step 4: Determine year_month for holdout check
        effective_year_month = year_month
        if as_of_us is None and effective_year_month is None:
            effective_year_month = self._extract_year_month_from_path(resolved)

        # Step 5: Check holdout window
        if as_of_us is not None or effective_year_month is not None:
            self._check_holdout_window(
                as_of_us=as_of_us,
                year_month=effective_year_month,
            )

        # Step 6: Check allowed year-months (if configured)
        if effective_year_month is not None:
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
