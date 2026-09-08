"""Exercise actual archive restoration, corruption rejection and protected paths."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("evidence_archive", Path(__file__).with_name("evidence_archive.py"))
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def fixture(repo):
    project = repo / "disastertrace-starter"
    project.mkdir(parents=True)
    data = b"exact forecast evidence\n" * 200
    (project / "first.txt").write_bytes(data)
    (project / "second.txt").write_bytes(data)
    (repo / "README.md").write_bytes(b"ancestor outside project, inside repo\n")
    record = {"evidence_sha256": {"first.txt": archive.sha(data), "second.txt": archive.sha(data),
                                 "../README.md": archive.digest(repo / "README.md")}}
    record["acceptance_id"] = archive.sha(archive.encoded(record))
    archive.write(project / "acceptance.json", record)
    return "disastertrace-starter/acceptance.json"


def test_full_roundtrip_deduplicates_and_can_reverify_existing_files(tmp_path):
    repo, bundle, target = (tmp_path / name for name in ("repo", "bundle", "restored"))
    acceptance = fixture(repo)
    record = archive.build(repo, [acceptance], bundle, part_limit=8192)
    assert len(record["files"]) == 4 and len(record["objects"]) == 3
    assert archive.restore(bundle, target)["written"] == 4
    for name in record["files"]:
        assert (target / name).read_bytes() == (repo / name).read_bytes()
    assert archive.restore(bundle, target)["written"] == 0
    assert archive.restore(bundle, target, verify_only=True)["status"] == "passed"


def test_existing_conflicting_file_is_never_overwritten(tmp_path):
    repo, bundle, target = (tmp_path / name for name in ("repo", "bundle", "restored"))
    acceptance = fixture(repo)
    archive.build(repo, [acceptance], bundle)
    target.mkdir()
    (target / "README.md").write_text("user change")
    with pytest.raises(ValueError, match="existing destination differs"):
        archive.restore(bundle, target)
    assert (target / "README.md").read_text() == "user change"
    assert not (target / "disastertrace-starter").exists()


def test_corrupt_compressed_bytes_are_rejected_before_restoration(tmp_path):
    repo, bundle, target = (tmp_path / name for name in ("repo", "bundle", "restored"))
    archive.build(repo, [fixture(repo)], bundle)
    part = next(bundle.glob("part-*.zip"))
    part.write_bytes(part.read_bytes()[:-1] + b"x")
    with pytest.raises(ValueError, match="archive part differs"):
        archive.restore(bundle, target)
    assert not target.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../../escape", ".git/config",
                                    ".github/workflows/a.yml", "a\\escape", "a/.env.private"])
def test_traversal_and_out_of_scope_paths_fail(tmp_path, name):
    with pytest.raises(ValueError, match="unsafe publication"):
        archive.safe_path(tmp_path, name)


def test_accepted_source_symlinks_are_rejected_even_with_same_content(tmp_path):
    repo = tmp_path / "repo"
    acceptance = fixture(repo)
    first = repo / "disastertrace-starter/first.txt"
    first.unlink()
    first.symlink_to("second.txt")
    with pytest.raises(ValueError, match="symlink"):
        archive.build(repo, [acceptance], tmp_path / "bundle")


def test_changed_accepted_evidence_fails_before_creating_archive(tmp_path):
    repo, bundle = tmp_path / "repo", tmp_path / "bundle"
    acceptance = fixture(repo)
    (repo / "README.md").write_text("different")
    with pytest.raises(ValueError, match="accepted bytes differ"):
        archive.build(repo, [acceptance], bundle)
    assert not bundle.exists()


def test_restoration_cannot_follow_destination_symlink(tmp_path):
    repo, bundle, target = (tmp_path / name for name in ("repo", "bundle", "restored"))
    archive.build(repo, [fixture(repo)], bundle)
    target.mkdir()
    (target / "disastertrace-starter").symlink_to(repo / "disastertrace-starter")
    with pytest.raises(ValueError, match="symlink"):
        archive.restore(bundle, target)
