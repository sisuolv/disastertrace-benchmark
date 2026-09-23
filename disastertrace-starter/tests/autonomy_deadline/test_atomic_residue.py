import importlib.util
import os
from pathlib import Path
import sys

import pytest

from disastertrace.forecast_task.common import digest, fingerprint, read, write

ROOT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(ROOT))
version = os.environ.get("DISPATCH_CHECK_TEST_VERSION", "v2")
source = ROOT / ("check_dispatch_deadlines.py" if version == "v1" else "check_dispatch_deadlines_v2.py")
spec = importlib.util.spec_from_file_location("atomic_cutoff_check", source)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def make_case_fixture(project, monkeypatch):
    root = project / "artifacts/autonomy_10h_v1"
    monkeypatch.setattr(check, "ROOT", root)
    monkeypatch.setattr(check, "PROJECT", project)
    write(project / "artifacts/p7_forecast_live_v1/AUTONOMY_WINDOW.json", {
        "received_at": "2026-09-08T16:05:16+00:00", "autonomous_work_deadline": "2026-09-09T02:05:16+00:00"})
    keys = [(p, m) for p in ("p11", "p12") for m in ("qwen3", "deepseek_r1")]
    keys += [("p13", "deepseek_r1"), ("p14", "qwen3")]
    completed = {}
    for phase, profile in keys:
        key = phase + "_" + profile
        bundle, _, run_label, *_ = check.PHASES[phase]
        plan = {"deadline_utc": "2026-09-09T02:05:16+00:00", "fixture_case": key}
        plan["execution_id"] = fingerprint(plan)
        write(project / "artifacts" / bundle / ("execution_" + profile + "_live_01/execution.json"), plan)
        analysis = {"execution_id": plan["execution_id"], "report_id": "fixture-" + key,
                    "counts": {"attempted": 0, "raw_returned": 0, "unknown_outcomes": 0}}
        analysis["analysis_id"] = fingerprint(analysis)
        path = root / "reviews_continuation_v2" / (key + ".json")
        write(path, analysis)
        location = {"phase": phase, "model_profile": profile, "review_directory": "artifacts/autonomy_10h_v1/reviews_continuation_v2",
                    "analysis_id": analysis["analysis_id"], "analysis_sha256": digest(path)}
        write(path.with_name("LOCATION_" + key + ".json"), location)
        completed[key] = location
        for worker in (0, 1):
            (project / "work" / (phase + "-" + run_label + "-" + profile + "-model-v1") /
             f"worker-{worker}/batches").mkdir(parents=True)
    write(root / "reviews_continuation_v2/FINAL_STATUS.json", {"status": "passed", "completed": completed})
    folder = project / "work/p14-role-qwen3-model-v1/worker-1/batches/000000"
    folder.mkdir()
    return folder


def test_atomic_intent_residue_is_preserved_without_inventing_attempts(tmp_path, monkeypatch):
    folder = make_case_fixture(tmp_path, monkeypatch)
    residue = folder / (".intent.json." + "a" * 32 + ".tmp")
    residue.write_bytes(b"")
    value = check.build()
    worker = value["cases"]["p14_qwen3"]["workers"][1]
    assert worker["attempted"] == worker["unknown_outcomes"] == worker["prepared_without_dispatch"] == 0
    assert value["input_files_sha256"][residue.relative_to(tmp_path).as_posix()] == digest(residue)
    assert worker["unpublished_batch_files"][0]["bytes"] == 0
    assert worker["unpublished_batch_files"][0]["published_record_present"] is False


@pytest.mark.parametrize("filename", ["started.json", "raw.json", ".started.json." + "b" * 32 + ".tmp"])
def test_dispatch_or_return_without_intent_is_rejected(tmp_path, monkeypatch, filename):
    folder = make_case_fixture(tmp_path, monkeypatch)
    (folder / filename).write_bytes(b"{}")
    with pytest.raises(ValueError, match="without published intent"):
        check.build()


def test_unexplained_batch_file_is_rejected(tmp_path, monkeypatch):
    folder = make_case_fixture(tmp_path, monkeypatch)
    (folder / "unexplained.txt").write_text("fixture")
    with pytest.raises(ValueError, match="unexplained"):
        check.build()


def test_empty_directory_does_not_change_file_based_check(tmp_path, monkeypatch):
    folder = make_case_fixture(tmp_path, monkeypatch)
    first = check.build()
    folder.rmdir()
    assert check.build() == first


def test_temporary_raw_is_not_promoted_to_an_answer(tmp_path):
    folder = tmp_path / "000000"
    folder.mkdir()
    intent = {"at": "2026-09-09T02:00:00+00:00", "prepared": [{"attempt_id": "a"}]}
    write(folder / "intent.json", intent)
    write(folder / "started.json", {"at": "2026-09-09T02:00:01+00:00", "intent_sha256": fingerprint(intent)})
    (folder / (".raw.json." + "c" * 32 + ".tmp")).write_text('{"partial":')
    records, temporary = check.load_batches(tmp_path, read, lambda path: digest(path))
    result = check.summarize_batches(records, "2026-09-08T16:00:00+00:00", "2026-09-09T02:05:16+00:00")
    assert result["attempted"] == result["unknown_outcomes"] == 1
    assert result["raw_returned"] == 0
    assert temporary[0]["record_kind"] == "raw"
