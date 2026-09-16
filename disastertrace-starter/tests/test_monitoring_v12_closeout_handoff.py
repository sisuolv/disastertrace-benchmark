"""A controlled scoring stop is terminal, but is not a successful process exit."""
import datetime as dt
import importlib.util
import json
from pathlib import Path


def closeout(tmp_path, monkeypatch, platform_state):
    path = Path(__file__).resolve().parents[2] / "plans/v12_execution_20260915_01/closeout.py"
    spec = importlib.util.spec_from_file_location("v12_closeout_handoff", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "REPO", tmp_path)
    monkeypatch.setattr(module, "preservation", lambda: {"passed": True})
    monkeypatch.setattr(module, "tests", lambda: {"passed": True})
    now = dt.datetime.now(dt.timezone.utc)
    files = {
        "EXECUTION_AUTHORIZATION.json": {"at": now.isoformat(),
            "deadline_at": (now + dt.timedelta(hours=1)).isoformat(), "max_model_formal_requests": 288},
        "runtime/original/JOB.json": {"job_id": "old", "gpus": 0},
        "runtime/finalizer/JOB.json": {"job_id": "new", "gpus": 0},
        "runtime/finalizer/EXIT.json": {"exit_code": 0},
        "stage_C_audit_handoff_01/ORIGINAL_JOB_TERMINAL.json": {"job_id": "old", "state": platform_state},
    }
    for name, data in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data))
    return module


def test_controlled_stop_closes_without_claiming_process_exit_zero(tmp_path, monkeypatch):
    result = closeout(tmp_path, monkeypatch, "STOPPED").summary()
    assert result["ready_to_close"] is True
    assert result["all_worker_terminal_states_observed"] is True
    assert result["all_worker_exits_observed"] is False
    original = next(j for j in result["jobs"] if j["job_id"] == "old")
    assert original["exit"] is None
    assert original["controlled_audit_handoff_terminal"]["state"] == "STOPPED"


def test_stop_in_progress_cannot_close_batch(tmp_path, monkeypatch):
    result = closeout(tmp_path, monkeypatch, "SUSPENDING").summary()
    assert result["ready_to_close"] is False
    assert result["all_worker_terminal_states_observed"] is False


def test_unrelated_job_receipt_does_not_hide_active_original(tmp_path, monkeypatch):
    module = closeout(tmp_path, monkeypatch, "STOPPED")
    path = tmp_path / "stage_C_audit_handoff_01/ORIGINAL_JOB_TERMINAL.json"
    path.write_text(json.dumps({"job_id": "unrelated", "state": "STOPPED"}))
    assert module.summary()["ready_to_close"] is False
