"""Read historical bytes locally or from verified archives, without extraction."""

import hashlib
import json
import tarfile
from pathlib import Path

ARCHIVES = (
    "disastertrace-starter/artifacts/next_phase_v1/archive_manifest.json",
    "disastertrace-starter/artifacts/t6_deepseek_calibration_v1/archive_manifest.json",
)


class HistoricalFiles:
    def __init__(self, repo, *, manifests=ARCHIVES):
        self.repo = Path(repo).resolve()
        self.manifests = manifests
        self.archived = {}
        self.loaded = set()

    def read(self, name):
        path = (self.repo / name).resolve()
        if not path.is_relative_to(self.repo):
            raise ValueError("historical path escapes the repository")
        if path.is_file():
            return path.read_bytes()
        if name in self.archived:
            return self.archived[name]
        for entry in self.manifests:
            manifest_path = self.repo / entry
            if entry in self.loaded or not manifest_path.is_file():
                continue
            manifest = json.loads(manifest_path.read_text())
            if name not in manifest["files"]:
                continue
            archive_path = manifest_path.parent / manifest["archive"]
            if not archive_path.resolve().is_relative_to(manifest_path.parent.resolve()):
                raise ValueError("archive path escapes its bundle")
            if hashlib.sha256(archive_path.read_bytes()).hexdigest() != manifest["archive_sha256"]:
                raise ValueError("historical archive digest mismatch")
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                if len(members) != len(manifest["files"]) or {m.name for m in members} != set(
                    manifest["files"]
                ):
                    raise ValueError("historical archive inventory mismatch")
                for member in members:
                    if (
                        not member.isfile()
                        or Path(member.name).is_absolute()
                        or ".." in Path(member.name).parts
                    ):
                        raise ValueError("unsafe historical archive member")
                    with archive.extractfile(member) as stream:
                        content = stream.read()
                    if hashlib.sha256(content).hexdigest() != manifest["files"][member.name]:
                        raise ValueError("historical archive member digest mismatch")
                    self.archived[member.name] = content
            self.loaded.add(entry)
            return self.archived[name]
        raise FileNotFoundError("historical artifact unavailable: " + name)

    def digest(self, name):
        return hashlib.sha256(self.read(name)).hexdigest()
