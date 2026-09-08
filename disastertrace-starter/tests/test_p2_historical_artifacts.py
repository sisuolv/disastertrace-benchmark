import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


def test_archived_history_is_verified_without_extracting(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/historical_artifacts.py"
    spec = importlib.util.spec_from_file_location("p2_historical_artifacts", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = b"historical record\n"
    archive = tmp_path / "saved.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        info = tarfile.TarInfo("work/private/record.txt")
        info.size = len(content)
        stream.addfile(info, io.BytesIO(content))
    manifest = {
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files": {"work/private/record.txt": hashlib.sha256(content).hexdigest()},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    history = module.HistoricalFiles(tmp_path, manifests=("manifest.json",))
    assert history.read("work/private/record.txt") == content
    assert not (tmp_path / "work").exists()
    with pytest.raises(ValueError):
        history.read("../outside.txt")
    manifest["files"]["work/private/record.txt"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="member digest"):
        module.HistoricalFiles(tmp_path, manifests=("manifest.json",)).read(
            "work/private/record.txt"
        )
