import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "p2_runner_test_module", Path(__file__).with_name("runner.py")
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def write(path, value):
    path.write_text(json.dumps(value))


def test_frozen_file_drift_rejected(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("original\n")
    write(tmp_path / "launch_manifest.json", {"files": {"source.py": RUNNER.sha(source)}})
    RUNNER.validate_files(tmp_path)
    source.write_text("changed\n")
    with pytest.raises(ValueError, match="frozen file mismatch"):
        RUNNER.validate_files(tmp_path)


def test_frozen_path_escape_rejected(tmp_path):
    root = tmp_path / "package"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("outside")
    write(root / "launch_manifest.json", {"files": {"../outside": RUNNER.sha(outside)}})
    with pytest.raises(ValueError, match="unsafe frozen path"):
        RUNNER.validate_files(root)


def stub_scope(tmp_path, monkeypatch):
    manifest = {"run_output": str(tmp_path / "run"), "execution_id": RUNNER.EXECUTION_ID}
    plan = {"registry_path": str(tmp_path / "registry"), "execution_id": RUNNER.EXECUTION_ID}
    monkeypatch.setattr(RUNNER, "HERE", tmp_path)
    monkeypatch.setattr(RUNNER, "verify", lambda **kwargs: (manifest, plan))
    return manifest, plan


@pytest.mark.parametrize("existing", ["runtime", "run", "claim"])
def test_no_second_launch_or_credential_read(tmp_path, monkeypatch, existing):
    _, plan = stub_scope(tmp_path, monkeypatch)
    if existing == "claim":
        claim = Path(plan["registry_path"]) / (plan["execution_id"] + ".json")
        claim.parent.mkdir()
        write(claim, {})
    else:
        (tmp_path / existing).mkdir()

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


def test_launch_detaches_and_does_not_persist_credential(tmp_path, monkeypatch):
    stub_scope(tmp_path, monkeypatch)
    monkeypatch.setattr(RUNNER, "frozen_modules", lambda: (None, None, None, write))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-credential")
    monkeypatch.setenv("UNRELATED_API_KEY", "unrelated-fixture")
    monkeypatch.setenv("DISASTERTRACE_OFFLINE", "1")
    observed = []

    def spawn(command, **kwargs):
        observed.append((command, {**kwargs, "env": kwargs["env"].copy()}))
        return SimpleNamespace(pid=123456)

    monkeypatch.setattr(RUNNER.subprocess, "Popen", spawn)
    RUNNER.launch()
    assert len(observed) == 1
    command, options = observed[0]
    assert command[-1] == "worker"
    assert "fixture-credential" not in command
    assert options["start_new_session"] is True
    assert options["stdin"] == RUNNER.subprocess.DEVNULL
    assert options["env"]["DEEPSEEK_API_KEY"] == "fixture-credential"
    assert options["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "UNRELATED_API_KEY" not in options["env"]
    assert "DISASTERTRACE_OFFLINE" not in options["env"]
    for path in (tmp_path / "runtime").iterdir():
        assert "fixture-credential" not in path.read_text()


def test_worker_forwards_attestation_and_requires_model_report(tmp_path, monkeypatch):
    manifest, _ = stub_scope(tmp_path, monkeypatch)
    (tmp_path / "runtime").mkdir()
    write(tmp_path / "runtime/launch_intent.json", manifest)
    write(tmp_path / "authorization.json", {"fixture": "authorization"})
    write(tmp_path / "price_attestation.json", {"fixture": "price"})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-credential")
    seen = {}

    def collect(*args, **kwargs):
        seen.update(kwargs)
        return {"completed": 270}

    def report(*args, **kwargs):
        assert "DEEPSEEK_API_KEY" not in RUNNER.os.environ
        assert kwargs["require_model"] is True
        return dict(
            complete=True,
            mode="model_http",
            attempted=270,
            received=270,
            unsubmitted=0,
            model_calls=270,
            stop_reason=None,
            reliability={},
        )

    modules = (
        SimpleNamespace(collect=collect),
        SimpleNamespace(audit_run=lambda *args: {}),
        SimpleNamespace(report_run=report, verify_report=lambda *args: {"status": "passed"}),
        write,
    )
    monkeypatch.setattr(RUNNER, "frozen_modules", lambda: modules)
    assert RUNNER.execute() == 0
    assert seen["transport"] is None
    assert seen["registry"] is None
    assert seen["authorization"] == {"fixture": "authorization"}
    assert seen["price_attestation"] == {"fixture": "price"}
