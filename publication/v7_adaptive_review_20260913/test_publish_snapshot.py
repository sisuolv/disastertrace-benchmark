"""Exercise a real local Git publication without touching the user's repository."""

import hashlib
import json
import subprocess
import zipfile
from argparse import Namespace

import publish_snapshot


def test_publication_preserves_dirty_head_index_and_exact_export_bytes(tmp_path, monkeypatch):
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(name, raising=False)
    working = tmp_path / "working"
    working.mkdir()
    remote = tmp_path / "remote.git"

    def git(*args, where=working):
        return subprocess.check_output(["git", *map(str, args)], cwd=where, stderr=subprocess.PIPE)

    git("init", "--quiet")
    git("config", "user.name", "Publication Test")
    git("config", "user.email", "publication-test@example.invalid")
    (working / "README.md").write_text("Remote base\n")
    (working / ".gitattributes").write_text("*.txt text eol=lf\n")
    git("add", "README.md", ".gitattributes")
    git("commit", "--quiet", "-m", "remote base")
    base = git("rev-parse", "HEAD").decode().strip()
    git("init", "--bare", "--quiet", remote)
    git("push", remote, "HEAD:refs/heads/next-phase-v1")

    (working / "local_only.txt").write_text("Keep this local commit\n")
    git("add", "local_only.txt")
    git("commit", "--quiet", "-m", "unpublished local work")
    (working / "README.md").write_text("Keep this unstaged edit\n")
    (working / "staged.txt").write_text("Keep this staged content\n")
    git("add", "staged.txt")
    head = git("rev-parse", "HEAD").decode().strip()
    index = working / ".git/index"
    index_bytes = index.read_bytes()

    relative = publish_snapshot.PUBLICATION
    local_publication = working / relative
    local_publication.mkdir(parents=True)
    (local_publication / "GIT_START.json").write_text(json.dumps({
        "local_HEAD": head, "real_index_path": str(index),
        "real_index_sha256": hashlib.sha256(index_bytes).hexdigest(),
    }))
    snapshot = tmp_path / "snapshot"
    publication = snapshot / relative
    publication.mkdir(parents=True)
    payloads = {"README.md": b"Verified publication\n", "windows.txt": b"Keep exact CRLF\r\n"}
    files = []
    for name, raw in payloads.items():
        (snapshot / name).write_bytes(raw)
        files.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    (publication / "EXPORT_MANIFEST.json").write_text(json.dumps({"base_commit": base, "files": files}))
    with zipfile.ZipFile(publication / "DisasterTrace_V7_Adaptive_Review_20260913.zip", "w") as archive:
        archive.writestr("README.md", payloads["README.md"])

    monkeypatch.setattr(publish_snapshot, "REPO", working)
    monkeypatch.setattr(publish_snapshot, "HERE", local_publication)
    monkeypatch.setattr(publish_snapshot, "REMOTE", str(remote))
    monkeypatch.setattr(publish_snapshot, "SSH", "false")
    receipt = tmp_path / "PUBLISHED.json"
    publish_snapshot.main(Namespace(snapshot=snapshot, receipt=receipt))

    record = json.loads(receipt.read_text())
    remote_head = git("--git-dir", remote, "rev-parse", "refs/heads/next-phase-v1").decode().strip()
    assert record["remote_verified"] and not record["force_push"]
    assert remote_head == record["commit"]
    assert git("--git-dir", remote, "rev-parse", remote_head + "^").decode().strip() == base
    for name, raw in payloads.items():
        assert git("--git-dir", remote, "show", remote_head + ":" + name) == raw
    assert git("--git-dir", remote, "show", remote_head + ":.gitattributes") == b"*.txt text eol=lf\n"
    assert git("rev-parse", "HEAD").decode().strip() == head
    assert index.read_bytes() == index_bytes
    assert (working / "README.md").read_text() == "Keep this unstaged edit\n"
    assert (working / "staged.txt").read_text() == "Keep this staged content\n"
    assert git("diff", "--cached", "--name-only").decode().strip() == "staged.txt"
    assert b"local_only.txt" not in git("--git-dir", remote, "ls-tree", "--name-only", remote_head)
