"""Opaque content-addressed names must not conceal nested compressed credentials."""

import gzip
import importlib.util
import io
from pathlib import Path
import tarfile
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("payload_scan", Path(__file__).with_name("check_payload.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def test_secret_in_double_compression_under_opaque_member_is_detected():
    payload = b"example=" + b"sk-" + b"x" * 32
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("objects/abcdef.gz", gzip.compress(gzip.compress(payload)))
    issues = []
    assert scan.inspect("part.zip", output.getvalue(), issues) == 3
    assert len(issues) == 1 and issues[0]["rule"] == "provider_key"
    assert payload.decode() not in str(issues)


def test_opaque_gzip_tar_members_retain_path_safety_checks():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        info = tarfile.TarInfo("../unsafe.txt")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"ok"))
    issues = []
    scan.inspect("objects/hash.gz", gzip.compress(output.getvalue()), issues)
    assert any(i["rule"] == "unsafe_archive_path" for i in issues)


def test_clean_nested_scientific_evidence_remains_accepted():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("objects/hash.gz", gzip.compress(b'{"wind":65,"unit":"KT"}'))
    issues = []
    assert scan.inspect("opaque", output.getvalue(), issues) == 2
    assert issues == []


def test_tar_container_can_exceed_single_member_limit_without_skipping_contents(monkeypatch):
    monkeypatch.setattr(scan, "MAX_MEMBER_BYTES", 4096, raising=False)
    monkeypatch.setattr(scan, "MAX_TAR_CONTAINER_BYTES", 32768, raising=False)
    output = io.BytesIO()
    payload = b"sk-" + b"x" * 32
    with tarfile.open(fileobj=output, mode="w") as archive:
        for index in range(8):
            data = payload if index == 7 else b"clean" * 200
            info = tarfile.TarInfo(f"file-{index}.txt")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    assert len(output.getvalue()) > scan.MAX_MEMBER_BYTES
    issues = []
    assert scan.inspect("large-container.gz", gzip.compress(output.getvalue()), issues) == 9
    assert any(i["rule"] == "provider_key" and i["path"].endswith("file-7.txt") for i in issues)


def test_plain_gzip_does_not_receive_a_tar_container_exemption(monkeypatch):
    monkeypatch.setattr(scan, "MAX_MEMBER_BYTES", 1024, raising=False)
    monkeypatch.setattr(scan, "MAX_TAR_CONTAINER_BYTES", 32768, raising=False)
    with pytest.raises(ValueError, match="inspection bound"):
        scan.inspect("large.json.gz", gzip.compress(b"x" * 2048), [])


def test_individual_tar_member_still_has_the_smaller_bound(monkeypatch):
    monkeypatch.setattr(scan, "MAX_MEMBER_BYTES", 1024, raising=False)
    monkeypatch.setattr(scan, "MAX_TAR_CONTAINER_BYTES", 32768, raising=False)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        info = tarfile.TarInfo("oversized.txt")
        info.size = 2048
        archive.addfile(info, io.BytesIO(b"x" * 2048))
    with pytest.raises(ValueError, match="TAR member"):
        scan.inspect("large-container.gz", gzip.compress(output.getvalue()), [])
