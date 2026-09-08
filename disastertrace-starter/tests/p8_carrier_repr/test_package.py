"""Predeclared population and inherited raw-source closure are mandatory gates."""

import io
import shutil
import tarfile
from pathlib import Path

import pytest

from disastertrace.carrier_repr import package
from disastertrace.forecast_task.common import canonical, fingerprint, read


@pytest.fixture
def registration_copy(tmp_path):
    source = Path(__file__).resolve().parents[2] / "artifacts/p8_carrier_representation_v1"
    copied = tmp_path / "registration"
    copied.mkdir()
    for name in (
        "PREREGISTRATION.json",
        "PREDECLARED_SLOTS.json",
        "DESIGN_BEFORE_NATIVE_RESULTS.md",
    ):
        shutil.copyfile(source / name, copied / name)
    return copied


@pytest.mark.parametrize(
    "mutation",
    ["source", "design", "subset", "answers", "pairs", "reservation", "seen_scores", "dispatch"],
)
def test_registration_rejects_rehashed_scope_or_design_changes(registration_copy, mutation):
    root = registration_copy
    before = read(root / "PREREGISTRATION.json")
    package.registration(root, before["source_execution_id"])
    if mutation == "source":
        with pytest.raises(ValueError):
            package.registration(root, "different-native-execution")
        return
    if mutation == "design":
        (root / "DESIGN_BEFORE_NATIVE_RESULTS.md").write_text("changed comparison question")
    elif mutation == "subset":
        slots = read(root / "PREDECLARED_SLOTS.json")[:-2]
        (root / "PREDECLARED_SLOTS.json").write_text(canonical(slots))
    else:
        field, value = {
            "answers": ("planned_answers", 842),
            "pairs": ("planned_pairs", 421),
            "reservation": ("planned_output_reservation", 1),
            "seen_scores": ("source_model_scores_read", True),
            "dispatch": ("has_dispatch_path", True),
        }[mutation]
        before[field] = value
        before["design_id"] = fingerprint({k: v for k, v in before.items() if k != "design_id"})
        (root / "PREREGISTRATION.json").write_text(canonical(before))
    with pytest.raises(ValueError):
        package.registration(root, before["source_execution_id"])


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../outside", "file"),
        ("/absolute", "file"),
        ("foreign/file", "file"),
        ("run/link", "symlink"),
        ("run/hardlink", "hardlink"),
        ("run/duplicate", "duplicate"),
    ],
)
def test_native_archive_cannot_escape_or_alias_members(tmp_path, name, kind):
    with tarfile.open(tmp_path / "native_evidence.tar.gz", "x:gz") as archive:
        item = tarfile.TarInfo(name)
        if kind in ("symlink", "hardlink"):
            item.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            item.linkname = "../../outside"
            archive.addfile(item)
        else:
            item.size = 2
            archive.addfile(item, io.BytesIO(b"{}"))
            if kind == "duplicate":
                archive.addfile(item, io.BytesIO(b"{}"))
    with pytest.raises(ValueError, match="unsafe or duplicate"):
        package.replay_native_archive(tmp_path, tmp_path)
    assert not list(tmp_path.glob("native-prefix-review-*"))


def test_program_report_cannot_be_bound_as_model_prefix(tmp_path, monkeypatch):
    native_plan = {"kind": "diagnostic", "execution_id": "fixture"}
    monkeypatch.setattr(package.native_package, "verify", lambda *a, **k: (native_plan, {}, []))
    monkeypatch.setattr(package.native_audit, "aggregate", lambda *a, **k: {"kind": "diagnostic"})
    report = tmp_path / "report.json"
    report.write_text('{"kind":"diagnostic"}')
    with pytest.raises(ValueError, match="actual native model"):
        package.prepare_source(tmp_path, tmp_path, report, tmp_path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_model_freeze_requires_new_preflight_validation_and_window(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "verify_seal", lambda *a: {})
    monkeypatch.setattr(package, "reconstruct_source", lambda *a: ({}, {}, []))
    with pytest.raises(ValueError, match="complete gates"):
        package.freeze(tmp_path, tmp_path / "live", kind="model")
    assert not (tmp_path / "live").exists()
