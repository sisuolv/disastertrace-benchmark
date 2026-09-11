import importlib.util
import inspect
import os
from pathlib import Path
import sys

import pytest

from disastertrace.forecast_task.common import digest, fingerprint, read, write

ROOT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(ROOT))
version = os.environ.get("DISPATCH_PARSED_TEST_VERSION", "v3")
spec = importlib.util.spec_from_file_location("parsed_cutoff_check", ROOT / ("check_dispatch_deadlines_" + version + ".py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def saved_batch(tmp_path, *, raw=True):
    folder = tmp_path / "000000"
    folder.mkdir()
    attempt = "a" * 64
    intent = {"at": "2026-09-09T02:00:00+00:00", "prepared": [{"attempt_id": attempt}]}
    write(folder / "intent.json", intent)
    write(folder / "started.json", {"at": "2026-09-09T02:00:01+00:00", "intent_sha256": fingerprint(intent)})
    if raw:
        write(folder / "raw.json", {"at": "2026-09-09T02:00:02+00:00", "intent_sha256": fingerprint(intent),
                                   "results": [{"attempt_id": attempt}]})
    return folder, attempt


def test_real_batch_layout_binds_cache_but_counts_raw_only(tmp_path):
    folder, attempt = saved_batch(tmp_path)
    cached = folder / "parsed" / (attempt + ".json")
    write(cached, {"fixture": "cache does not supply dispatch or return evidence"})
    bound = {}

    def bind(path):
        bound[str(path)] = digest(path)
        return bound[str(path)]

    rows, temporary = check.load_batches(tmp_path, read, bind)
    result = check.summarize_batches(rows, "2026-09-08T16:00:00+00:00", "2026-09-09T02:05:16+00:00")
    assert result["attempted"] == result["raw_returned"] == 1
    assert result["unknown_outcomes"] == 0 and temporary == []
    assert bound[str(cached)] == digest(cached)


def test_parsed_cache_cannot_resolve_missing_raw(tmp_path):
    folder, attempt = saved_batch(tmp_path, raw=False)
    write(folder / "parsed" / (attempt + ".json"), {"fixture": "not authoritative"})
    with pytest.raises(ValueError):
        check.load_batches(tmp_path, read, digest)


def test_cache_for_unreturned_attempt_rejected(tmp_path):
    folder, _ = saved_batch(tmp_path)
    write(folder / "parsed" / ("b" * 64 + ".json"), {})
    with pytest.raises(ValueError):
        check.load_batches(tmp_path, read, digest)


@pytest.mark.parametrize("kind", ["directory_link", "cache_link", "unknown_file"])
def test_cache_layout_does_not_hide_unexplained_evidence(tmp_path, kind):
    batches = tmp_path / "batches"
    batches.mkdir()
    folder, attempt = saved_batch(batches)
    outside = tmp_path / "outside"
    outside.mkdir()
    write(outside / (attempt + ".json"), {})
    parsed = folder / "parsed"
    if kind == "directory_link":
        parsed.symlink_to(outside, target_is_directory=True)
    else:
        parsed.mkdir()
        if kind == "cache_link":
            (parsed / (attempt + ".json")).symlink_to(outside / (attempt + ".json"))
        else:
            (parsed / "unexplained.txt").write_text("fixture")
    with pytest.raises(ValueError):
        check.load_batches(batches, read, digest)


def test_zero_byte_unpublished_intent_stays_unattempted(tmp_path):
    folder = tmp_path / "000000"
    folder.mkdir()
    residue = folder / (".intent.json." + "c" * 32 + ".tmp")
    residue.write_bytes(b"")
    rows, temporary = check.load_batches(tmp_path, read, digest)
    result = check.summarize_batches(rows, "2026-09-08T16:00:00+00:00", "2026-09-09T02:05:16+00:00")
    assert result["attempted"] == result["raw_returned"] == result["unknown_outcomes"] == 0
    assert temporary[0]["sha256"] == digest(residue) and temporary[0]["bytes"] == 0


def test_published_intent_with_temporary_raw_retains_unknown(tmp_path):
    folder, _ = saved_batch(tmp_path, raw=False)
    (folder / (".raw.json." + "d" * 32 + ".tmp")).write_bytes(b'{"partial":')
    rows, temporary = check.load_batches(tmp_path, read, digest)
    result = check.summarize_batches(rows, "2026-09-08T16:00:00+00:00", "2026-09-09T02:05:16+00:00")
    assert result["attempted"] == result["unknown_outcomes"] == 1
    assert result["raw_returned"] == 0 and temporary[0]["record_kind"] == "raw"


def test_temporal_rules_match_tested_v2():
    spec = importlib.util.spec_from_file_location("prior_cutoff_check", ROOT / "check_dispatch_deadlines_v2.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    for name in ("stamp", "summarize_batches"):
        assert inspect.getsource(getattr(check, name)) == inspect.getsource(getattr(prior, name))
