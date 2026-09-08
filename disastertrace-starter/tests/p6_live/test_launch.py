"""Submission claims survive CLI failures and cannot be bypassed with another path."""

import pytest

from disastertrace.repeat_live import acp, launch


def test_failed_submission_still_consumes_claim(tmp_path, monkeypatch):
    plan = {
        "fixture": False,
        "generation_authorized": False,
        "execution_id": "a" * 64,
        "registry_path": str(tmp_path / "registry"),
        "implementation_files": {},
    }
    monkeypatch.setattr(launch.package, "verify", lambda path: (plan, {}, []))
    calls = []

    def failed(directory, request):
        calls.append(request)
        raise TimeoutError("uncertain ACP submission")

    monkeypatch.setattr(acp, "submit", failed)
    with pytest.raises(TimeoutError):
        launch.submit(tmp_path / "execution", tmp_path / "first", "preflight")
    with pytest.raises(FileExistsError):
        launch.submit(tmp_path / "execution", tmp_path / "bypass", "preflight")
    assert len(calls) == 1
    assert calls[0]["max_model_attempts"] == 0
    assert calls[0]["worker_seconds"] == 1200


def test_runtime_environment_omits_credentials_and_fixes_multiprocessing(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "do-not-copy")
    monkeypatch.setenv("SERVICE_TOKEN", "do-not-copy")
    env = acp.runtime_env(tmp_path / "source", tmp_path / "cache")
    assert "TEST_API_KEY" not in env and "SERVICE_TOKEN" not in env
    assert env["VLLM_USE_V1"] == "1"
    assert env["VLLM_ENABLE_V1_MULTIPROCESSING"] == "0"
    assert env["HF_HUB_OFFLINE"] == "1"
