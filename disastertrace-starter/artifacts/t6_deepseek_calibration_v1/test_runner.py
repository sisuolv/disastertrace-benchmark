import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "t6_runner_test_module", Path(__file__).with_name("runner.py")
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_frozen_file_drift_rejected(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("original\n")
    (tmp_path / "launch_manifest.json").write_text(
        json.dumps({"files": {"source.py": RUNNER.sha(source)}})
    )
    RUNNER.validate_files(tmp_path)
    source.write_text("changed\n")
    with pytest.raises(ValueError, match="frozen file mismatch"):
        RUNNER.validate_files(tmp_path)


def test_frozen_path_escape_rejected(tmp_path):
    root = tmp_path / "package"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("outside")
    (root / "launch_manifest.json").write_text(
        json.dumps({"files": {"../outside": RUNNER.sha(outside)}})
    )
    with pytest.raises(ValueError, match="unsafe frozen path"):
        RUNNER.validate_files(root)


def test_no_second_initial_launch_or_credential_read(tmp_path, monkeypatch):
    monkeypatch.setattr(RUNNER, "HERE", tmp_path)
    monkeypatch.setattr(
        RUNNER, "verify", lambda **kwargs: ({"run_output": str(tmp_path / "run")}, {})
    )
    (tmp_path / "runtime").mkdir()

    def forbidden(*args, **kwargs):
        raise AssertionError("must reject before credential or process access")

    monkeypatch.setattr(RUNNER.getpass, "getpass", forbidden)
    monkeypatch.setattr(RUNNER.subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="already claimed"):
        RUNNER.launch()


def test_invalid_package_rejected_before_reading_key(tmp_path, monkeypatch):
    monkeypatch.setattr(RUNNER, "HERE", tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid package must not access credential or network")

    monkeypatch.setattr(RUNNER.getpass, "getpass", forbidden)
    monkeypatch.setattr(RUNNER.subprocess, "Popen", forbidden)
    with pytest.raises(FileNotFoundError):
        RUNNER.launch()
