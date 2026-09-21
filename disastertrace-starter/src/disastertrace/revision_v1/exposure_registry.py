"""Exposure registry for pre-registration enforcement (V17-01 / F07).

This module provides an append-only ledger that tracks:
- When a logical_id was frozen (register_freeze)
- When a logical_id was disclosed (register_disclosure)

The key invariants:
1. A logical_id can only be frozen ONCE, regardless of output filename.
2. Disclosure can only happen for a logical_id that was frozen.
3. The registry file is append-only: writes never drop or alter prior entries.

This closes the F07 "rename and refreeze" gap: even if someone deletes the
output file and runs freeze with a new filename, the registry will reject
the re-freeze because the logical_id is already registered.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class ExposureRegistryError(Exception):
    """Base exception for exposure registry errors."""
    pass


class AlreadyFrozenError(ExposureRegistryError):
    """Raised when attempting to re-freeze an already-frozen logical_id."""
    pass


class NotFrozenError(ExposureRegistryError):
    """Raised when attempting to disclose a logical_id that was never frozen."""
    pass


class IntegrityError(ExposureRegistryError):
    """Raised when the registry file integrity check fails."""
    pass


class ManifestMismatchError(ExposureRegistryError):
    """Raised when disclosure sha256 doesn't match frozen expected sha256."""
    pass


@dataclass
class RegistryEntry:
    """A single entry in the exposure registry.

    Attributes:
        logical_id: Unique identifier for the frozen artifact (e.g., run/cohort ID).
        expected_manifest_sha256: The sha256 of the frozen manifest (set at freeze).
        frozen_at: ISO timestamp when the freeze was registered.
        exposed_at: ISO timestamp when disclosure was registered (None if not disclosed).
        entry_type: Either "freeze" or "disclosure".
    """
    logical_id: str
    expected_manifest_sha256: str
    frozen_at: str
    exposed_at: str | None
    entry_type: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RegistryEntry":
        return cls(
            logical_id=d["logical_id"],
            expected_manifest_sha256=d["expected_manifest_sha256"],
            frozen_at=d["frozen_at"],
            exposed_at=d.get("exposed_at"),
            entry_type=d["entry_type"],
        )


class ExposureRegistry:
    """Append-only ledger for tracking freeze/disclosure events.

    Thread-safety: This class is NOT thread-safe. External synchronization
    is required if multiple processes/threads may write to the same registry.

    File format: JSON array of RegistryEntry dicts, one entry per operation.
    New entries are appended; existing entries are never modified or removed.
    """

    def __init__(self, registry_path: Path):
        """Initialize the registry.

        Args:
            registry_path: Path to the registry JSON file. Will be created
                if it doesn't exist.
        """
        self.registry_path = registry_path
        self._entries: list[RegistryEntry] = []
        self._frozen_ids: dict[str, RegistryEntry] = {}  # logical_id -> freeze entry
        self._disclosed_ids: set[str] = set()

        if self.registry_path.exists():
            self._load()

    def _load(self) -> None:
        """Load existing entries from the registry file."""
        with open(self.registry_path, "r") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise IntegrityError(
                f"Registry file must be a JSON array: {self.registry_path}"
            )

        self._entries = []
        self._frozen_ids = {}
        self._disclosed_ids = set()

        for item in data:
            entry = RegistryEntry.from_dict(item)
            self._entries.append(entry)

            if entry.entry_type == "freeze":
                self._frozen_ids[entry.logical_id] = entry
            elif entry.entry_type == "disclosure":
                self._disclosed_ids.add(entry.logical_id)

    def _save(self, new_entry: RegistryEntry) -> None:
        """Append a new entry to the registry file with integrity check.

        This implements the append-only guarantee: we read the current file,
        verify it's a strict prefix of what we expect, then write back with
        the new entry appended.
        """
        # Read current content (if exists)
        current_entries = []
        if self.registry_path.exists():
            with open(self.registry_path, "r") as f:
                current_entries = json.load(f)

        # Verify current content is a prefix of our in-memory entries
        # (excluding the new entry we're about to add)
        expected_prefix = [e.to_dict() for e in self._entries[:-1]]
        if current_entries != expected_prefix:
            # Could be concurrent modification or corruption
            raise IntegrityError(
                f"Registry file has been modified externally or is corrupt. "
                f"Expected {len(expected_prefix)} entries, found {len(current_entries)}."
            )

        # Append new entry
        new_entries = current_entries + [new_entry.to_dict()]

        # Write atomically by writing to temp file then renaming
        # (but for simplicity here, we just write directly)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w") as f:
            json.dump(new_entries, f, indent=2)
            f.write("\n")

    def _now_iso(self) -> str:
        """Get current UTC time as ISO string."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def is_frozen(self, logical_id: str) -> bool:
        """Check if a logical_id has been frozen."""
        return logical_id in self._frozen_ids

    def is_disclosed(self, logical_id: str) -> bool:
        """Check if a logical_id has been disclosed."""
        return logical_id in self._disclosed_ids

    def get_freeze_entry(self, logical_id: str) -> RegistryEntry | None:
        """Get the freeze entry for a logical_id, or None if not frozen."""
        return self._frozen_ids.get(logical_id)

    def register_freeze(
        self,
        logical_id: str,
        manifest_sha256: str,
    ) -> RegistryEntry:
        """Register a freeze event for a logical_id.

        This records that a manifest with the given sha256 was frozen under
        the given logical_id. Any subsequent attempt to freeze the same
        logical_id (regardless of output filename) will be rejected.

        Args:
            logical_id: Unique identifier for this frozen artifact.
            manifest_sha256: SHA256 of the frozen manifest content.

        Returns:
            The created RegistryEntry.

        Raises:
            AlreadyFrozenError: If logical_id was already frozen.
        """
        if logical_id in self._frozen_ids:
            existing = self._frozen_ids[logical_id]
            raise AlreadyFrozenError(
                f"Logical ID '{logical_id}' was already frozen at {existing.frozen_at}. "
                f"Re-freezing the same logical_id under a different filename is not allowed. "
                f"Expected manifest SHA256: {existing.expected_manifest_sha256}"
            )

        entry = RegistryEntry(
            logical_id=logical_id,
            expected_manifest_sha256=manifest_sha256,
            frozen_at=self._now_iso(),
            exposed_at=None,
            entry_type="freeze",
        )

        self._entries.append(entry)
        self._frozen_ids[logical_id] = entry
        self._save(entry)

        return entry

    def register_disclosure(
        self,
        logical_id: str,
        actual_sha256: str,
    ) -> RegistryEntry:
        """Register a disclosure event for a logical_id.

        This records that the frozen manifest was disclosed (outcomes were read).
        The actual_sha256 is cross-checked against the expected_manifest_sha256
        recorded at freeze time.

        Args:
            logical_id: The logical_id that was frozen.
            actual_sha256: The SHA256 of the manifest being disclosed.

        Returns:
            The created RegistryEntry.

        Raises:
            NotFrozenError: If logical_id was never frozen.
            ManifestMismatchError: If actual_sha256 doesn't match expected.
        """
        if logical_id not in self._frozen_ids:
            raise NotFrozenError(
                f"Cannot disclose '{logical_id}': it was never frozen. "
                f"Run freeze phase first."
            )

        freeze_entry = self._frozen_ids[logical_id]

        # Cross-check sha256
        if actual_sha256 != freeze_entry.expected_manifest_sha256:
            raise ManifestMismatchError(
                f"Manifest SHA256 mismatch for '{logical_id}'. "
                f"Expected: {freeze_entry.expected_manifest_sha256}, "
                f"Actual: {actual_sha256}. "
                f"The manifest may have been modified after freeze."
            )

        entry = RegistryEntry(
            logical_id=logical_id,
            expected_manifest_sha256=actual_sha256,
            frozen_at=freeze_entry.frozen_at,
            exposed_at=self._now_iso(),
            entry_type="disclosure",
        )

        self._entries.append(entry)
        self._disclosed_ids.add(logical_id)
        self._save(entry)

        return entry

    def list_entries(self) -> list[RegistryEntry]:
        """Return all entries in chronological order."""
        return list(self._entries)

    def list_frozen_ids(self) -> list[str]:
        """Return all frozen logical_ids."""
        return list(self._frozen_ids.keys())

    def list_disclosed_ids(self) -> list[str]:
        """Return all disclosed logical_ids."""
        return list(self._disclosed_ids)


def compute_manifest_logical_id(
    selection_rule_version: str,
    taf_archive_summary: str,
    config_sha256: str,
) -> str:
    """Compute a deterministic logical_id for a manifest.

    The logical_id is derived from the inputs to the selection process,
    ensuring that re-running with identical inputs produces the same ID.
    This allows the registry to detect "rename and refreeze" attempts.

    Args:
        selection_rule_version: The manifest.SELECTION_RULE_VERSION.
        taf_archive_summary: The TAF archive fingerprint.
        config_sha256: The stations_calendar config SHA256.

    Returns:
        A deterministic logical_id string.
    """
    # Combine the key inputs deterministically
    combined = f"{selection_rule_version}:{taf_archive_summary}:{config_sha256}"

    # Use first 16 chars of SHA256 for brevity
    digest = hashlib.sha256(combined.encode()).hexdigest()[:16]

    return f"manifest_v16_{digest}"
