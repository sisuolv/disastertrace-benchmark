"""Tests for revision_v1/access_policy.py access boundary enforcement (V17-01 / F04).

Tests cover:
- Path canonicalization (resolves symlinks and ..)
- Quarantine-holdout segment rejection (segment-based, not substring)
- Holdout window date rejection (with exact boundary tests)
- Root escape rejection
- Short-circuit verification (rejection prevents further filesystem access)
- Integration with load_asos_with_provenance
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

# Add project src to path
_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))

from disastertrace.revision_v1.access_policy import (
    AccessPolicy,
    AccessPolicyViolation,
    make_policy_for_real_v16,
)
from disastertrace.revision_v1.manifest import (
    get_holdout_window,
    windows_overlap,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    """Sample stations_calendar config with holdout window."""
    return {
        "stations": [
            {"icao": "KSFO", "faa": "SFO"},
            {"icao": "KDEN", "faa": "DEN"},
        ],
        "calendar_start": "2023-01-01T00:00:00Z",
        "calendar_end": "2025-12-31T23:59:59Z",
        "holdout_exclusion": {
            "window_start": "2025-02-17T00:00:00Z",
            "window_end": "2025-02-24T00:00:00Z",
        },
    }


@pytest.fixture
def basic_policy(tmp_path, sample_config):
    """Create a basic AccessPolicy with tmp_path as allowed root."""
    return AccessPolicy.from_config(
        sample_config,
        allowed_root=tmp_path,
    )


def us_from_iso(iso_str: str) -> int:
    """Convert ISO string to microseconds."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1_000_000)


# ---------------------------------------------------------------------------
# Test: Quarantine-holdout segment rejection (F04 core fix)
# ---------------------------------------------------------------------------

class TestQuarantineSegmentRejection:
    """Test that quarantine_holdout is rejected as a path SEGMENT, not substring."""

    def test_rejects_literal_quarantine_holdout_segment(self, tmp_path, sample_config):
        """Path containing literal 'quarantine_holdout' segment is rejected."""
        # Create directory structure with quarantine_holdout as a segment
        quarantine_dir = tmp_path / "data" / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)

        test_file = quarantine_dir / "test.body"
        test_file.write_text("test content")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(test_file)

        assert "quarantine_holdout segment" in str(exc_info.value)

    def test_does_not_reject_substring_match(self, tmp_path, sample_config):
        """Path containing 'quarantine_holdout' as SUBSTRING (not segment) is allowed.

        This tests the F04 fix: the old substring check would reject paths like
        'quarantine_holdout_backup' even though they don't have 'quarantine_holdout'
        as a complete path segment.
        """
        # Create directory where quarantine_holdout is part of a longer name
        substring_dir = tmp_path / "quarantine_holdout_backup" / "2023-06"
        substring_dir.mkdir(parents=True)

        test_file = substring_dir / "test.body"
        test_file.write_text("test content")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # This should NOT raise - the segment is "quarantine_holdout_backup", not "quarantine_holdout"
        policy.assert_allowed(test_file)

    def test_rejects_symlink_resolving_to_quarantine(self, tmp_path, sample_config):
        """Symlink that resolves into quarantine_holdout is rejected.

        This is the key F04 fix: we must resolve() BEFORE checking segments.
        """
        # Create the actual quarantine directory
        quarantine_dir = tmp_path / "data" / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)

        quarantine_file = quarantine_dir / "secret.body"
        quarantine_file.write_text("secret data")

        # Create a symlink that doesn't contain "quarantine_holdout" in its name
        safe_looking_dir = tmp_path / "safe_data"
        safe_looking_dir.mkdir()

        symlink = safe_looking_dir / "innocent.body"
        symlink.symlink_to(quarantine_file)

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # The symlink resolves to quarantine_holdout, so it should be rejected
        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(symlink)

        assert "quarantine_holdout segment" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: Path traversal / root escape rejection
# ---------------------------------------------------------------------------

class TestRootEscapeRejection:
    """Test that paths escaping the allowed root are rejected."""

    def test_rejects_path_with_dotdot_escape(self, tmp_path, sample_config):
        """Path containing '..' that escapes root is rejected."""
        # Create allowed root as a subdirectory
        allowed_root = tmp_path / "allowed"
        allowed_root.mkdir()

        # Create a file outside the allowed root
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "secret.body"
        outside_file.write_text("secret")

        policy = AccessPolicy.from_config(sample_config, allowed_root=allowed_root)

        # Try to access outside file via .. traversal
        evil_path = allowed_root / ".." / "outside" / "secret.body"

        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(evil_path)

        assert "escapes allowed root" in str(exc_info.value)

    def test_rejects_symlink_escaping_root(self, tmp_path, sample_config):
        """Symlink pointing outside allowed root is rejected."""
        # Create allowed root
        allowed_root = tmp_path / "allowed"
        allowed_root.mkdir()

        # Create a file outside
        outside_file = tmp_path / "outside.body"
        outside_file.write_text("outside")

        # Create symlink inside allowed root pointing outside
        symlink = allowed_root / "sneaky.body"
        symlink.symlink_to(outside_file)

        policy = AccessPolicy.from_config(sample_config, allowed_root=allowed_root)

        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(symlink)

        assert "escapes allowed root" in str(exc_info.value)

    def test_accepts_path_inside_allowed_root(self, tmp_path, sample_config):
        """Path properly inside allowed root is accepted."""
        allowed_root = tmp_path / "allowed"
        data_dir = allowed_root / "data" / "2023-06"
        data_dir.mkdir(parents=True)

        test_file = data_dir / "test.body"
        test_file.write_text("test")

        policy = AccessPolicy.from_config(sample_config, allowed_root=allowed_root)

        # Should not raise
        policy.assert_allowed(test_file)


# ---------------------------------------------------------------------------
# Test: Holdout window date rejection with exact boundaries
# ---------------------------------------------------------------------------

class TestHoldoutWindowRejection:
    """Test holdout window enforcement with exact boundary timestamps."""

    def test_rejects_timestamp_inside_holdout(self, basic_policy):
        """Timestamp clearly inside holdout is rejected."""
        # Feb 20, 2025 is inside [Feb 17, Feb 24)
        inside_us = us_from_iso("2025-02-20T12:00:00Z")

        with pytest.raises(AccessPolicyViolation) as exc_info:
            basic_policy._check_holdout_window(as_of_us=inside_us)

        assert "holdout window" in str(exc_info.value)

    def test_rejects_timestamp_at_holdout_start_boundary(self, basic_policy):
        """Timestamp exactly at holdout start (inclusive) is rejected."""
        # Holdout starts at 2025-02-17T00:00:00Z
        start_us = us_from_iso("2025-02-17T00:00:00Z")

        with pytest.raises(AccessPolicyViolation) as exc_info:
            basic_policy._check_holdout_window(as_of_us=start_us)

        assert "holdout window" in str(exc_info.value)

    def test_accepts_timestamp_just_before_holdout_start(self, basic_policy):
        """Timestamp 1 microsecond before holdout start is accepted."""
        # One microsecond before 2025-02-17T00:00:00Z
        just_before_us = us_from_iso("2025-02-17T00:00:00Z") - 1

        # Should not raise
        basic_policy._check_holdout_window(as_of_us=just_before_us)

    def test_accepts_timestamp_at_holdout_end_boundary(self, basic_policy):
        """Timestamp exactly at holdout end (exclusive) is accepted."""
        # Holdout ends at 2025-02-24T00:00:00Z (exclusive)
        end_us = us_from_iso("2025-02-24T00:00:00Z")

        # Should not raise - end is exclusive
        basic_policy._check_holdout_window(as_of_us=end_us)

    def test_rejects_timestamp_just_before_holdout_end(self, basic_policy):
        """Timestamp 1 microsecond before holdout end is rejected."""
        # One microsecond before 2025-02-24T00:00:00Z
        just_before_end_us = us_from_iso("2025-02-24T00:00:00Z") - 1

        with pytest.raises(AccessPolicyViolation) as exc_info:
            basic_policy._check_holdout_window(as_of_us=just_before_end_us)

        assert "holdout window" in str(exc_info.value)

    def test_rejects_year_month_overlapping_holdout(self, basic_policy):
        """Year-month that overlaps holdout window is rejected."""
        # Feb 2025 overlaps the holdout window
        with pytest.raises(AccessPolicyViolation) as exc_info:
            basic_policy._check_holdout_window(year_month="2025-02")

        assert "holdout window" in str(exc_info.value)

    def test_accepts_year_month_before_holdout(self, basic_policy):
        """Year-month before holdout is accepted."""
        # Jan 2025 is before holdout
        basic_policy._check_holdout_window(year_month="2025-01")

    def test_accepts_year_month_after_holdout(self, basic_policy):
        """Year-month after holdout is accepted."""
        # Mar 2025 is after holdout
        basic_policy._check_holdout_window(year_month="2025-03")

    def test_extracts_year_month_from_path(self, tmp_path, sample_config):
        """Year-month is correctly extracted from path for holdout check."""
        # Create path with holdout month in it
        holdout_dir = tmp_path / "data" / "KSFO" / "2025-02" / "run123"
        holdout_dir.mkdir(parents=True)
        test_file = holdout_dir / "test.body"
        test_file.write_text("test")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(test_file)

        assert "holdout window" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: Short-circuit verification (rejection prevents filesystem access)
# ---------------------------------------------------------------------------

class TestShortCircuitVerification:
    """Test that rejection prevents further filesystem traversal/read."""

    def test_rejection_prevents_glob_expansion(self, tmp_path, sample_config):
        """When assert_allowed rejects a path, no further glob expansion occurs."""
        # Create quarantine directory structure
        quarantine_dir = tmp_path / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)

        # Create some files that would be found by glob
        for i in range(5):
            (quarantine_dir / f"file{i}.body").write_text(f"content {i}")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # Mock Path.glob to count calls
        glob_calls = []
        original_glob = Path.glob

        def tracking_glob(self, pattern):
            glob_calls.append((self, pattern))
            return original_glob(self, pattern)

        with mock.patch.object(Path, 'glob', tracking_glob):
            # First verify the path - it should be rejected
            quarantine_path = tmp_path / "quarantine_holdout"

            with pytest.raises(AccessPolicyViolation):
                policy.assert_allowed(quarantine_path)

            # Count glob calls AFTER the rejection
            calls_before = len(glob_calls)

        # assert_allowed() itself must never call glob -- it only inspects
        # the single path it was given (Path.parts/resolve), it does not
        # enumerate a directory. This was previously an empty assertion
        # (comment-only); now actually enforced.
        assert calls_before == 0, (
            f"assert_allowed() must not call glob() while rejecting a path, "
            f"but {calls_before} glob call(s) were observed"
        )

    def test_rejection_prevents_file_read(self, tmp_path, sample_config):
        """When assert_allowed rejects, no file read should occur.

        This tests the integration pattern: caller must check BEFORE reading.
        """
        quarantine_dir = tmp_path / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)
        secret_file = quarantine_dir / "secret.body"
        secret_file.write_text("TOP SECRET DATA")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # Track file opens
        opens = []
        original_open = open

        def tracking_open(path, *args, **kwargs):
            opens.append(str(path))
            return original_open(path, *args, **kwargs)

        with mock.patch('builtins.open', tracking_open):
            # The pattern: check first, then open
            with pytest.raises(AccessPolicyViolation):
                policy.assert_allowed(secret_file)

            # After rejection, a well-designed caller should not open
            opens_before_rejection = len(opens)

        # assert_allowed() itself must never open() a file while rejecting a
        # path. This was previously an empty assertion (comment-only); now
        # actually enforced.
        assert opens_before_rejection == 0, (
            f"assert_allowed() must not call open() while rejecting a path, "
            f"but {opens_before_rejection} open() call(s) were observed"
        )


# ---------------------------------------------------------------------------
# Test: Integration with load_asos_with_provenance
# ---------------------------------------------------------------------------

class TestLoadAsosWithProvenanceIntegration:
    """Test that load_asos_with_provenance uses AccessPolicy correctly."""

    def test_rejects_quarantine_with_policy(self, tmp_path, sample_config):
        """load_asos_with_provenance rejects quarantine paths via AccessPolicy."""
        from disastertrace.revision_v1.outcome_wiring import load_asos_with_provenance

        # Create quarantine file
        quarantine_dir = tmp_path / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)
        body_file = quarantine_dir / "asos.body"
        body_file.write_text("secret data")

        # Create receipt
        receipt = {"sha256": "abc123", "finished_at": "2025-02-20T12:00:00Z"}
        (quarantine_dir / "asos.json").write_text(__import__('json').dumps(receipt))

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        with pytest.raises(AccessPolicyViolation) as exc_info:
            load_asos_with_provenance(str(body_file), access_policy=policy)

        assert "quarantine_holdout" in str(exc_info.value)

    def test_legacy_fallback_uses_segment_check(self, tmp_path):
        """Legacy fallback (no policy) still uses segment-based check."""
        from disastertrace.revision_v1.outcome_wiring import load_asos_with_provenance

        # Create quarantine file
        quarantine_dir = tmp_path / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)
        body_file = quarantine_dir / "asos.body"
        body_file.write_text("secret data")

        # Create receipt (won't be read due to early rejection)
        receipt = {"sha256": "abc123", "finished_at": "2025-02-20T12:00:00Z"}
        (quarantine_dir / "asos.json").write_text(__import__('json').dumps(receipt))

        # Without policy, should still reject via legacy segment check
        with pytest.raises(ValueError) as exc_info:
            load_asos_with_provenance(str(body_file))

        assert "quarantine_holdout" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: Allowed year-months filtering
# ---------------------------------------------------------------------------

class TestAllowedYearMonthsFiltering:
    """Test that allowed_year_months restricts which months are accessible."""

    def test_rejects_month_not_in_allowed_set(self, tmp_path, sample_config):
        """Month not in allowed_year_months set is rejected."""
        policy = AccessPolicy.from_config(
            sample_config,
            allowed_root=tmp_path,
            allowed_year_months=frozenset({"2023-06", "2023-07"}),
        )

        # Create path for allowed month
        allowed_dir = tmp_path / "KSFO" / "2023-06"
        allowed_dir.mkdir(parents=True)
        allowed_file = allowed_dir / "test.body"
        allowed_file.write_text("allowed")

        # Should succeed
        policy.assert_allowed(allowed_file)

        # Create path for disallowed month
        disallowed_dir = tmp_path / "KSFO" / "2023-08"
        disallowed_dir.mkdir(parents=True)
        disallowed_file = disallowed_dir / "test.body"
        disallowed_file.write_text("disallowed")

        # Should fail
        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(disallowed_file)

        assert "not in allowed set" in str(exc_info.value)

    def test_accepts_all_months_when_not_configured(self, tmp_path, sample_config):
        """When allowed_year_months is None, all non-holdout months are allowed."""
        policy = AccessPolicy.from_config(
            sample_config,
            allowed_root=tmp_path,
            allowed_year_months=None,
        )

        # Any month outside holdout should work
        for month in ["2023-01", "2024-06", "2025-03"]:
            test_dir = tmp_path / "KSFO" / month
            test_dir.mkdir(parents=True, exist_ok=True)
            test_file = test_dir / "test.body"
            test_file.write_text("test")

            # Should not raise
            policy.assert_allowed(test_file)


# ---------------------------------------------------------------------------
# Test: CE4 regression -- explicit as_of_us/year_month must never override
# what the path itself implies (fail-closed consistency)
# ---------------------------------------------------------------------------

class TestExplicitParameterCannotOverridePath:
    """CE4: a path implying a restricted/holdout month must be rejected even
    when the caller passes an explicit, individually-safe as_of_us or
    year_month. Before the fix, assert_allowed() only ever attempted to
    extract the path-implied month when BOTH explicit parameters were
    absent, so any explicit parameter silently bypassed the path's own
    signal.
    """

    def test_explicit_year_month_disagreeing_with_path_is_rejected(self, tmp_path, sample_config):
        """Path implies one month; caller passes a different, individually-safe year_month."""
        # Path implies 2025-02 (inside holdout) via dashed directory segment
        holdout_dir = tmp_path / "KSFO" / "2025-02"
        holdout_dir.mkdir(parents=True)
        test_file = holdout_dir / "test.body"
        test_file.write_text("test")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # 2023-06 is individually safe (outside holdout), but disagrees with
        # the path's own implied month -- must still be rejected.
        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(test_file, year_month="2023-06")

        assert "disagrees with the path-implied year-month" in str(exc_info.value)

    def test_explicit_as_of_disagreeing_with_path_is_rejected(self, tmp_path, sample_config):
        """Path implies one month; caller passes a different, individually-safe as_of_us."""
        holdout_dir = tmp_path / "KSFO" / "2025-02"
        holdout_dir.mkdir(parents=True)
        test_file = holdout_dir / "test.body"
        test_file.write_text("test")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # An as_of_us in 2023-06 (safe) but the path says 2025-02 -- must
        # still be rejected because the two disagree.
        safe_but_wrong_as_of = us_from_iso("2023-06-15T00:00:00Z")

        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(test_file, as_of_us=safe_but_wrong_as_of)

        assert "disagrees with the path-implied year-month" in str(exc_info.value)

    def test_as_of_us_alone_does_not_bypass_allowlist(self, tmp_path, sample_config):
        """An as_of_us-only call must not skip the allowed_year_months check.

        Before the fix, supplying as_of_us alone (without year_month) caused
        path-month extraction to be skipped entirely, which meant
        effective_year_month stayed None and the allowlist check in step 6
        never ran -- silently admitting a path in a disallowed month.
        """
        # Path implies 2023-08, which is NOT in the allowed set below.
        disallowed_dir = tmp_path / "KSFO" / "2023-08"
        disallowed_dir.mkdir(parents=True)
        test_file = disallowed_dir / "test.body"
        test_file.write_text("test")

        policy = AccessPolicy.from_config(
            sample_config,
            allowed_root=tmp_path,
            allowed_year_months=frozenset({"2023-06", "2023-07"}),
        )

        # A safe, non-holdout as_of_us consistent with the path's own month
        # (2023-08) is used so the consistency check passes and only the
        # allowlist gap is being tested.
        as_of_in_path_month = us_from_iso("2023-08-15T00:00:00Z")

        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(test_file, as_of_us=as_of_in_path_month)

        assert "not in allowed set" in str(exc_info.value)

    def test_consistent_explicit_params_do_not_spuriously_reject(self, tmp_path, sample_config):
        """Explicit params that AGREE with the path-implied month are fine."""
        allowed_dir = tmp_path / "KSFO" / "2023-08"
        allowed_dir.mkdir(parents=True)
        test_file = allowed_dir / "test.body"
        test_file.write_text("test")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # Should not raise: year_month agrees with path
        policy.assert_allowed(test_file, year_month="2023-08")

        # Should not raise: as_of_us agrees with path (same month)
        agreeing_as_of = us_from_iso("2023-08-01T00:00:00Z")
        policy.assert_allowed(test_file, as_of_us=agreeing_as_of)

    def test_allowlist_rejects_when_path_month_unextractable(self, tmp_path, sample_config):
        """When allowlist is configured, an unextractable path month is
        rejected (fail-closed) even with a plausible explicit year_month."""
        # Filename has no extractable year-month pattern at all.
        opaque_dir = tmp_path / "KSFO"
        opaque_dir.mkdir(parents=True)
        opaque_file = opaque_dir / "no_month_here.body"
        opaque_file.write_text("test")

        policy = AccessPolicy.from_config(
            sample_config,
            allowed_root=tmp_path,
            allowed_year_months=frozenset({"2023-06"}),
        )

        with pytest.raises(AccessPolicyViolation) as exc_info:
            policy.assert_allowed(opaque_file, year_month="2023-06")

        assert "could not be extracted" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: read_verified_allowed_file shared entry point
# ---------------------------------------------------------------------------

class TestReadVerifiedAllowedFile:
    """Test the shared verified-read entry point added in A2-1."""

    def _make_pair(self, tmp_path, *, body_text="TAF KSFO ...", month="2023-06"):
        import hashlib
        import json as json_mod

        data_dir = tmp_path / "KSFO" / month
        data_dir.mkdir(parents=True, exist_ok=True)
        body_path = data_dir / "test.body"
        body_path.write_text(body_text)
        receipt_path = data_dir / "test.json"
        receipt_path.write_text(json_mod.dumps({
            "sha256": hashlib.sha256(body_text.encode()).hexdigest(),
        }))
        return body_path, receipt_path

    def test_reads_verified_bytes_matching_receipt(self, tmp_path, sample_config):
        from disastertrace.revision_v1.access_policy import read_verified_allowed_file

        body_path, receipt_path = self._make_pair(tmp_path)
        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        result = read_verified_allowed_file(policy, body_path, receipt_path)

        assert result.body == b"TAF KSFO ..."
        assert result.size_bytes == len(b"TAF KSFO ...")
        assert result.raw_text_sha256 == result.receipt_sha256

    def test_rejection_happens_before_any_read(self, tmp_path, sample_config):
        """A rejected body/receipt pair must never be opened at all."""
        from disastertrace.revision_v1.access_policy import read_verified_allowed_file

        quarantine_dir = tmp_path / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)
        body_path = quarantine_dir / "secret.body"
        body_path.write_text("TOP SECRET")
        receipt_path = quarantine_dir / "secret.json"
        receipt_path.write_text('{"sha256": "deadbeef"}')

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        opens = []
        original_open = open

        def tracking_open(path, *args, **kwargs):
            opens.append(str(path))
            return original_open(path, *args, **kwargs)

        with mock.patch('builtins.open', tracking_open):
            with pytest.raises(AccessPolicyViolation):
                read_verified_allowed_file(policy, body_path, receipt_path)

        assert len(opens) == 0, (
            f"read_verified_allowed_file() must reject before opening either "
            f"file, but observed opens: {opens}"
        )

    def test_body_modified_receipt_unchanged_fails(self, tmp_path, sample_config):
        """A body whose bytes no longer match its receipt's sha256 must fail."""
        from disastertrace.revision_v1.access_policy import (
            read_verified_allowed_file,
            ReadVerificationError,
        )

        body_path, receipt_path = self._make_pair(tmp_path)
        # Tamper with the body after the receipt was written.
        body_path.write_text("TAF KSFO ... TAMPERED")

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        with pytest.raises(ReadVerificationError) as exc_info:
            read_verified_allowed_file(policy, body_path, receipt_path)

        assert "SHA256 mismatch" in str(exc_info.value)

    def test_same_bytes_same_digest(self, tmp_path, sample_config):
        """Reading identical bytes (from different files) yields the same digest."""
        from disastertrace.revision_v1.access_policy import read_verified_allowed_file

        body1, receipt1 = self._make_pair(tmp_path, body_text="IDENTICAL CONTENT", month="2023-06")

        data_dir2 = tmp_path / "KDEN" / "2023-07"
        data_dir2.mkdir(parents=True)
        body2 = data_dir2 / "other.body"
        body2.write_text("IDENTICAL CONTENT")
        receipt2 = data_dir2 / "other.json"
        import hashlib, json as json_mod
        receipt2.write_text(json_mod.dumps({
            "sha256": hashlib.sha256(b"IDENTICAL CONTENT").hexdigest(),
        }))

        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        result1 = read_verified_allowed_file(policy, body1, receipt1)
        result2 = read_verified_allowed_file(policy, body2, receipt2)

        assert result1.raw_text_sha256 == result2.raw_text_sha256


# ---------------------------------------------------------------------------
# Test: is_holdout_month helper
# ---------------------------------------------------------------------------

class TestIsHoldoutMonth:
    """Test the is_holdout_month convenience method."""

    def test_identifies_holdout_month(self, basic_policy):
        """is_holdout_month returns True for Feb 2025."""
        assert basic_policy.is_holdout_month("2025-02") is True

    def test_identifies_non_holdout_month(self, basic_policy):
        """is_holdout_month returns False for months outside holdout."""
        assert basic_policy.is_holdout_month("2025-01") is False
        assert basic_policy.is_holdout_month("2025-03") is False
        assert basic_policy.is_holdout_month("2024-02") is False


# ---------------------------------------------------------------------------
# Test: filter_paths batch filtering
# ---------------------------------------------------------------------------

class TestFilterPaths:
    """Test batch path filtering."""

    def test_separates_allowed_and_rejected(self, tmp_path, sample_config):
        """filter_paths correctly separates allowed from rejected paths."""
        policy = AccessPolicy.from_config(sample_config, allowed_root=tmp_path)

        # Create some allowed paths
        allowed_dir = tmp_path / "KSFO" / "2023-06"
        allowed_dir.mkdir(parents=True)
        allowed1 = allowed_dir / "a.body"
        allowed2 = allowed_dir / "b.body"
        allowed1.write_text("a")
        allowed2.write_text("b")

        # Create rejected path (quarantine)
        quarantine_dir = tmp_path / "quarantine_holdout" / "2025-02"
        quarantine_dir.mkdir(parents=True)
        rejected = quarantine_dir / "c.body"
        rejected.write_text("c")

        # Filter
        paths = [allowed1, allowed2, rejected]
        allowed, rejected_with_reasons = policy.filter_paths(paths)

        assert len(allowed) == 2
        assert allowed1 in allowed
        assert allowed2 in allowed

        assert len(rejected_with_reasons) == 1
        assert rejected_with_reasons[0][0] == rejected
        assert "quarantine_holdout" in rejected_with_reasons[0][1]
