"""X09 resource/deadline guards never dispatch an extra GPU job in blocked states."""

import datetime
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

GPU = Path(__file__).resolve().parents[2] / "plans/v8_measurement_execution_20260913_01/gpu"


def module(name, monkeypatch):
    monkeypatch.syspath_prepend(str(GPU))
    spec = importlib.util.spec_from_file_location(name, GPU / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def setup_governor(tmp_path, monkeypatch):
    gov = module("govern_joint", monkeypatch)
    batch, out = tmp_path / "batch", tmp_path / "batch/submission_01"
    batch.mkdir()
    monkeypatch.setattr(gov, "BATCH", batch)
    monkeypatch.setattr(gov, "OUT", out)
    monkeypatch.setattr(gov, "HERE", tmp_path)
    return gov, batch, out


def test_late_submission_never_queries_or_creates_a_job(tmp_path, monkeypatch):
    gov, _, out = setup_governor(tmp_path, monkeypatch)
    out.mkdir()
    monkeypatch.setattr(gov, "now", lambda: datetime.datetime(2026, 9, 14, 1, 16, tzinfo=datetime.timezone.utc))
    monkeypatch.setattr(gov.subprocess, "run", lambda *a, **k: pytest.fail("Late submission touched CLI"))
    gov.submit({"last_submission_at": "2026-09-14T01:15:00+00:00"})
    assert (out / "NOT_SUBMITTED.json").exists()
    assert not (out / "SUBMISSION_INTENT.json").exists()


def test_occupied_GPU_envelope_never_creates_a_job(tmp_path, monkeypatch):
    gov, batch, out = setup_governor(tmp_path, monkeypatch)
    out.mkdir()
    plan = {"last_submission_at": "2026-09-14T01:15:00+00:00", "tasks": [None] * 384, "maximum_total_calls": 385, "files": {}}
    write(batch / "EVALUATOR_MANIFEST.json", {})
    plan["evaluator_manifest_sha256"] = gov.sha(batch / "EVALUATOR_MANIFEST.json")
    write(batch / "PLAN.json", plan)
    write(batch / "cpu_preflight_01/VALIDATION.json", {"integrity_passed": True, "dryrun": True, "actual_benchmark_requests": 0, "plan_sha256": gov.sha(batch / "PLAN.json")})
    monkeypatch.setattr(gov, "now", lambda: datetime.datetime(2026, 9, 14, 0, 30, tzinfo=datetime.timezone.utc))
    monkeypatch.setattr(gov, "verify_index", lambda: {"passed": True})
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert "list" in command and "create" not in command
        return SimpleNamespace(stdout=json.dumps([{"ownership": {"user_name": "260010168"}, "state": "RUNNING", "roles": [{"total_replicas": 1, "resource_spec": [{"requests": {"nvidia.com/gpu": 4}}]}]}]))

    monkeypatch.setattr(gov.subprocess, "run", fake_run)
    gov.submit(plan)
    assert len(calls) == 1
    assert json.loads((out / "ACCOUNT_BEFORE.json").read_text())["active_requested_gpus"] == 4
    assert (out / "NOT_SUBMITTED.json").exists()


def test_failed_predecessor_keeps_optional_extension_unsubmitted(tmp_path, monkeypatch):
    gov, batch, out = setup_governor(tmp_path, monkeypatch)
    plan = {"last_submission_at": "2026-09-14T01:15:00+00:00", "predecessor_job": "pt-original"}
    write(batch / "PLAN.json", plan)
    monkeypatch.setattr(gov, "now", lambda: datetime.datetime(2026, 9, 14, 0, 30, tzinfo=datetime.timezone.utc))
    monkeypatch.setattr(gov, "submit", lambda *args: pytest.fail("Failed original job was bypassed"))
    monkeypatch.setattr(gov.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps({"name": "pt-original", "ownership": {"user_name": "260010168"}, "state": "FAILED"})))
    gov.main()
    assert (out / "NOT_SUBMITTED.json").exists()
    assert not (out / "SUBMISSION_INTENT.json").exists()


def test_consumed_governor_directory_cannot_be_restarted(tmp_path, monkeypatch):
    gov, batch, out = setup_governor(tmp_path, monkeypatch)
    write(batch / "PLAN.json", {})
    out.mkdir()
    monkeypatch.setattr(gov.subprocess, "run", lambda *a, **k: pytest.fail("Consumed launch touched CLI"))
    with pytest.raises(FileExistsError):
        gov.main()


def test_worker_dispatch_deadline_keeps_a_durable_stop_receipt(tmp_path, monkeypatch):
    worker = module("joint_worker", monkeypatch)
    assert worker.past_deadline({"last_model_dispatch_at": "2000-01-01T00:00:00+00:00"}, tmp_path, "before_next_batch")
    stop = json.loads((tmp_path / "TIME_LIMIT.json").read_text())
    assert stop["stage"] == "before_next_batch"
