"""Exercise publication gates and an actual local-Git roundtrip without network."""

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def publisher(tmp_path, monkeypatch, request):
    source = Path(__file__).with_name("publish_after_pause.py")
    spec = importlib.util.spec_from_file_location("publisher_under_test", source)
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    remote_directory = tempfile.TemporaryDirectory(prefix="disastertrace-test-remote-")
    request.addfinalizer(remote_directory.cleanup)
    p.test_remote_directory = Path(remote_directory.name)
    repo = tmp_path / "development"
    here = repo / "publication/v9_followup_20260914"
    batch = repo / "plans/v9_followup_execution_20260914_01"
    runtime = batch / "runtime/github_after_pause_01"
    for folder in [here, runtime, batch / "runtime/pause_after_batch_01"]:
        folder.mkdir(parents=True, exist_ok=True)
    for name, value in [("REPO", repo), ("HERE", here), ("BATCH", batch), ("RUNTIME", runtime)]:
        monkeypatch.setattr(p, name, value)
    key = tmp_path / "private.key"
    key.write_text("private test value never exported")
    monkeypatch.setattr(p, "KEY_FILE", key)
    selected = []
    contents = {
        "disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py": "fixture = 1\n",
        "disastertrace-starter/src/disastertrace/monitoring_v1/session_checkpoint.py": "fixture = 2\n",
        "plans/v9_followup_execution_20260914_01/PAUSED_RESULT.json": json.dumps({
            "phase": "PAUSED_FOR_USER_REVIEW", "all_registered_work_verified": False}),
        "plans/v9_followup_execution_20260914_01/PAUSED_SUMMARY_CN.md": "Fixture stopped at a gate.\n",
        "publication/v9_followup_20260914/README_CN.md": "Fixture reading scope.\n",
    }
    for name, text in contents.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        selected.append(target)
    monkeypatch.setattr(p, "selected_files", lambda: (selected, []))
    (batch / "runtime/pause_after_batch_01/COMPLETE.json").write_text('{"paused":true}')
    (here / "AUTHORIZATION.json").write_text(json.dumps({
        "fixed_code": {str(path.relative_to(repo)): p.digest(path) for path in selected[:2]}}))
    return p


def local_remote(p, tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    seed_git = ["git", "--git-dir=" + str(seed / ".git"), "--work-tree=" + str(seed)]
    subprocess.run([*seed_git, "init", str(seed)], capture_output=True, check=True)
    subprocess.run([*seed_git, "config", "user.name", "Test"], check=True)
    subprocess.run([*seed_git, "config", "user.email", "test@localhost"], check=True)
    (seed / "README.md").write_text("Original remote notes.\n")
    (seed / "keep.txt").write_text("Preserve original remote content.\n")
    subprocess.run([*seed_git, "add", "README.md", "keep.txt"], check=True)
    subprocess.run([*seed_git, "commit", "-m", "Fixture baseline"], capture_output=True, check=True)
    subprocess.run([*seed_git, "branch", p.BRANCH], check=True)
    # Simulate the remote on a native filesystem; publish/readback objects remain on AFS.
    remote = p.test_remote_directory / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, check=True)
    subprocess.run([*seed_git, "push", str(remote), "refs/heads/" + p.BRANCH], capture_output=True, check=True)
    monkeypatch.setattr(p, "REMOTE", str(remote))
    return remote, seed


def test_sensitive_paths_and_payloads_are_rejected(publisher):
    p = publisher
    p.inspect_payload("code.py", b"key = os.getenv('API_KEY')")
    for name in ["../private", ".ssh/config", "folder/token.key", ".env"]:
        with pytest.raises(ValueError):
            p.inspect_payload(name, b"text")
    for content in [b"sk-" + b"a" * 32, b"Bearer " + b"a" * 30,
                    b"https://example/?" + b"Signature=fixture"]:
        with pytest.raises(ValueError):
            p.inspect_payload("data.json", content)
    with pytest.raises(ValueError, match="Known private"):
        p.inspect_payload("log.txt", b"an exact private value", [b"private value"])


def test_no_publication_before_final_pause(publisher):
    (publisher.BATCH / "runtime/pause_after_batch_01/COMPLETE.json").unlink()
    with pytest.raises(ValueError, match="Final pause receipt"):
        publisher.publish()
    assert not (publisher.REPO / "review-outputs").exists()


def test_changed_code_stops_before_git(publisher):
    path = publisher.REPO / "disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py"
    path.write_text("modified after preparation\n")
    with pytest.raises(ValueError, match="Code changed"):
        publisher.publish()
    assert not (publisher.REPO / "review-outputs").exists()


def test_actual_git_roundtrip_preserves_history_and_failure_status(publisher, tmp_path, monkeypatch):
    p = publisher
    remote, seed = local_remote(p, tmp_path, monkeypatch)
    index_before = (seed / ".git/index").read_bytes()
    base = subprocess.check_output(["git", "--git-dir=" + str(remote), "rev-parse", p.BRANCH]).decode().strip()
    p.publish()
    receipt = p.read(p.BATCH / "GITHUB_UPLOAD_AFTER_PAUSE.json")
    assert receipt["passed"] and receipt["batch_remains_paused"]
    assert receipt["base"] == base and receipt["commit"] != base
    parent = subprocess.check_output(["git", "--git-dir=" + str(remote), "rev-parse", receipt["commit"] + "^"]).decode().strip()
    assert parent == base
    assert subprocess.check_output(["git", "--git-dir=" + str(remote), "show", receipt["commit"] + ":keep.txt"]) == b"Preserve original remote content.\n"
    assert (seed / ".git/index").read_bytes() == index_before
    snapshot = Path(receipt["snapshot"])
    manifest = p.read(snapshot / p.PUBLICATION / "EXPORT_MANIFEST.json")
    assert manifest["all_registered_work_verified"] is False
    with zipfile.ZipFile(snapshot / p.PUBLICATION / p.REVIEW) as archive:
        for row in manifest["files"]:
            data = archive.read(row["path"])
            assert hashlib.sha256(data).hexdigest() == row["sha256"]
            assert p.KEY_FILE.read_bytes() not in data


def test_remote_advance_prevents_push(publisher, tmp_path, monkeypatch):
    p = publisher
    remote, _ = local_remote(p, tmp_path, monkeypatch)
    base = subprocess.check_output(["git", "--git-dir=" + str(remote), "rev-parse", p.BRANCH])
    original = p.git_runner

    def changed_remote(bare):
        git = original(bare)

        def call(*args, **kwargs):
            if args[0] == "ls-remote":
                return ("0" * 40 + "\trefs/heads/" + p.BRANCH + "\n").encode()
            assert args[0] != "push"
            return git(*args, **kwargs)

        return call

    monkeypatch.setattr(p, "git_runner", changed_remote)
    with pytest.raises(ValueError, match="Remote branch advanced"):
        p.publish()
    assert subprocess.check_output(["git", "--git-dir=" + str(remote), "rev-parse", p.BRANCH]) == base
