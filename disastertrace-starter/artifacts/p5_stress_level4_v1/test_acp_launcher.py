"""No-model regression tests for phase limits, durable submission and prefix reporting."""

import subprocess
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import acp_common
import acp_worker
import launch_p5
import pytest

from disastertrace.local_eval.storage import digest, fingerprint, read, write
from disastertrace.stress_eval import execution


def plans_for(project):
    deadline = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    return {
        factor: {
            "max_attempts": 540,
            "planned_responses": 540,
            "repeats": 1,
            "retries": 0,
            "diagnostic_probes": 0,
            "deadline_utc": deadline,
            "run_path": str(project / "work" / ("p5-qwen3-" + factor.replace("_", "-") + "-v1")),
        }
        for factor in acp_common.FACTORS
    }


def test_exact_phase_budget(tmp_path):
    launch_p5.validate_budget(plans_for(tmp_path), tmp_path)


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_attempts", 541),
        ("planned_responses", 539),
        ("repeats", 2),
        ("retries", 1),
        ("diagnostic_probes", 1),
    ],
)
def test_refuse_scope_expansion(tmp_path, key, value):
    plans = plans_for(tmp_path)
    plans["revision_chain"][key] = value
    with pytest.raises(ValueError, match="scope"):
        launch_p5.validate_budget(plans, tmp_path)


def test_missing_factor_and_reused_run_rejected(tmp_path):
    plans = plans_for(tmp_path)
    with pytest.raises(ValueError, match="three"):
        launch_p5.validate_budget({"revision_chain": plans["revision_chain"]}, tmp_path)
    plans["revision_chain"]["run_path"] = plans["irrelevant_scope"]["run_path"]
    with pytest.raises(ValueError, match="canonical"):
        launch_p5.validate_budget(plans, tmp_path)


@pytest.mark.parametrize("deadline", ["2020-01-01T00:00:00+00:00", "2099-01-01T00:00:00"])
def test_expired_or_naive_deadline_rejected(tmp_path, deadline):
    plans = plans_for(tmp_path)
    plans["revision_chain"]["deadline_utc"] = deadline
    with pytest.raises(ValueError, match="deadline"):
        launch_p5.validate_budget(plans, tmp_path)


def test_pair_binds_all_frozen_inputs():
    offline = {k: {"version": k} for k in launch_p5.PAIR_KEYS}
    offline.update(scope=execution.SCOPE, stress_profile={"factor": "revision_chain", "level": 4})
    live = deepcopy(offline)
    live["scope"] = execution.LIVE_SCOPE
    launch_p5.validate_pair(live, offline, "revision_chain")
    for key in launch_p5.PAIR_KEYS:
        changed = deepcopy(live)
        changed[key] = {"changed": True}
        with pytest.raises(ValueError, match="differs"):
            launch_p5.validate_pair(changed, offline, "revision_chain")


def test_acceptance_identity_and_file_tamper(tmp_path):
    p = tmp_path / "bound.json"
    write(p, {"scope": 540})
    accepted = {"status": "passed", "evidence_sha256": {"bound.json": digest(p)}}
    accepted["acceptance_id"] = fingerprint(accepted)
    launch_p5.verify_bound_files(accepted, tmp_path)
    p.write_text('{"scope":541}\n')
    with pytest.raises(ValueError, match="evidence changed"):
        launch_p5.verify_bound_files(accepted, tmp_path)
    accepted["status"] = "failed"
    with pytest.raises(ValueError, match="identity"):
        launch_p5.verify_bound_files(accepted, tmp_path)


def test_duplicate_submission_never_reaches_cli(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(acp_common, "check_mount", lambda: None)

    def cli(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            returncode=0, stdout="job pt-fixture submitted successfully", stderr=""
        )

    monkeypatch.setattr(acp_common.subprocess, "run", cli)
    directory = tmp_path / "job"
    request = {"display_name": "offline-fixture", "command": "python fixture.py"}
    acp_common.submit(directory, request)
    with pytest.raises(FileExistsError):
        acp_common.submit(directory, request)
    assert len(calls) == 1
    assert "--retry-times=0" in calls[0]
    assert "--worker-nodes=1" in calls[0]
    assert read(directory / "submission.json")["gpu_count"] == 1


def test_ambiguous_submission_consumed_without_retry(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(acp_common, "check_mount", lambda: None)

    def cli(args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args, 90)

    monkeypatch.setattr(acp_common.subprocess, "run", cli)
    directory = tmp_path / "job"
    request = {"display_name": "offline-fixture", "command": "python fixture.py"}
    with pytest.raises(subprocess.TimeoutExpired):
        acp_common.submit(directory, request)
    assert (directory / "submission_unknown.json").exists()
    with pytest.raises(FileExistsError):
        acp_common.submit(directory, request)
    assert len(calls) == 1


def test_failed_submission_is_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(acp_common, "check_mount", lambda: None)
    monkeypatch.setattr(
        acp_common.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="fixture rejection"),
    )
    directory = tmp_path / "job"
    with pytest.raises(RuntimeError, match="never automatically"):
        acp_common.submit(directory, {"display_name": "fixture", "command": "python fixture.py"})
    assert read(directory / "submission_response.json")["returncode"] == 1
    assert not (directory / "submission.json").exists()


def test_failed_collector_still_gets_prefix_reports(tmp_path):
    observed = []
    commands = [(name, [name]) for name in ("collect", "report", "verify_report")]

    def runner(command, **kwargs):
        observed.append(command[0])
        return SimpleNamespace(returncode=1 if command[0] == "collect" else 0)

    outcomes = acp_worker.run_commands(commands, tmp_path, {}, runner=runner)
    assert observed == ["collect", "report", "verify_report"]
    assert [r["exit_code"] for r in outcomes] == [1, 0, 0]
    with pytest.raises(FileExistsError):
        acp_worker.run_commands(commands, tmp_path, {}, runner=runner)
    assert len(observed) == 3


def test_failed_audit_does_not_claim_verified_report(tmp_path):
    commands = [(name, [name]) for name in ("collect", "report", "verify_report")]

    def runner(command, **kwargs):
        return SimpleNamespace(returncode=1 if command[0] == "report" else 0)

    outcomes = acp_worker.run_commands(commands, tmp_path, {}, runner=runner)
    assert [r["step"] for r in outcomes] == ["collect", "report"]
    assert not (tmp_path / "verify_report_result.json").exists()


def test_only_collection_uses_gpu_python():
    commands = acp_worker.commands_for(Path("execution"), Path("run"), Path("report"))
    assert commands[0][1][0] == acp_common.GPU_PYTHON
    assert all(command[0] == acp_common.CPU_PYTHON for _, command in commands[1:])
    assert all("--require-model" in command for _, command in commands[1:])
    assert "--verify" in commands[2][1]


def test_phase_marker_blocks_second_launch(tmp_path, monkeypatch):
    (tmp_path / "acp/phase_001").mkdir(parents=True)
    monkeypatch.setattr(launch_p5, "HERE", tmp_path)
    monkeypatch.setattr(launch_p5, "validate", lambda: ({}, {}))
    monkeypatch.setattr(launch_p5, "submit", lambda *a, **k: pytest.fail("duplicate dispatch"))
    with pytest.raises(FileExistsError):
        launch_p5.launch()
