"""Verify the one-use observer and stopped-prefix reporting without dispatch."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from disastertrace.local_eval.storage import digest, read, write


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    script = Path(__file__).with_name("run_model.py")
    spec = importlib.util.spec_from_file_location("p4_launcher_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = tmp_path / "bundle"
    module.HERE.mkdir()
    module.PROJECT = tmp_path
    plan = {"execution_id": "test-only", "run_path": str(tmp_path / "production")}
    monkeypatch.setattr(module, "validate", lambda: plan)
    monkeypatch.setattr(module.sys, "argv", [str(script)])
    return module, plan


@pytest.mark.parametrize("consumed", ["canonical-run", "observer-runtime"])
def test_consumed_launch_never_spawns(launcher, monkeypatch, consumed):
    module, plan = launcher
    if consumed == "canonical-run":
        Path(plan["run_path"]).mkdir()
    else:
        (module.HERE / "runtime").mkdir()

    def forbidden(*args, **kwargs):
        raise AssertionError("consumed launcher must not spawn")

    monkeypatch.setattr(module.subprocess, "Popen", forbidden)
    with pytest.raises((ValueError, FileExistsError)):
        module.main()


def test_launch_is_exclusive_and_binds_worker(launcher, monkeypatch):
    module, plan = launcher
    write(module.HERE / "frozen_acceptance.json", {"status": "test-only"})
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    module.main()
    assert len(calls) == 1 and calls[0][1]["start_new_session"] is True
    launch = read(module.HERE / "runtime/launch.json")
    assert launch["execution_id"] == plan["execution_id"]
    assert launch["worker_sha256"] == digest(module.__file__)
    with pytest.raises(FileExistsError):
        module.main()
    assert len(calls) == 1


@pytest.mark.parametrize("codes", [(0, 0, 0), (1, 0, 0), (0, 1)])
def test_observer_uses_frozen_v1_and_reports_stopped_collection(launcher, monkeypatch, codes):
    module, plan = launcher
    write(
        module.HERE / "runtime/launch.json",
        {"execution_id": plan["execution_id"], "worker_sha256": digest(module.__file__)},
    )
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=codes[len(calls) - 1])

    monkeypatch.setattr(module.subprocess, "run", run)
    result = module.worker()
    assert result == (0 if codes == (0, 0, 0) else 1)
    assert len(calls) == len(codes)
    assert calls[0][0][-2:] == ["--output", plan["run_path"]]
    for command, kwargs in calls:
        assert "disastertrace.constrained_eval.cli" in command
        assert kwargs["env"]["VLLM_USE_V1"] == "1"
        assert kwargs["env"]["PYTHONPATH"].endswith("execution_live/implementation_source/src")
        assert "--diagnostic" not in command
    assert "--require-model" in calls[1][0]
    if len(calls) == 3:
        assert calls[2][0][-1] == "--verify"
    observed = read(module.HERE / "runtime/observer_completion.json")
    assert [row["exit_code"] for row in observed["outcomes"]] == list(codes)
