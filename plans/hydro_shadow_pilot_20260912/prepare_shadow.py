"""Freeze one prospective program pilot after source admission and offline tests."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from disastertrace.hydro_shadow_v1.capture import (
    file_hash,
    stamp,
    strict_json,
    write_new,
)
from disastertrace.hydro_shadow_v1.pipeline import make_registry

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(__file__).resolve().parent
SELECTED = ("NRWI4", "CRHA2", "DNLF1", "JMPN7", "SCOC1", "TARN7")


def prepare(output):
    stations = strict_json(
        (BUNDLE / "admission_01/QUALIFIED_STATIONS.json").read_bytes()
    )
    by_lid = {s["lid"]: s for s in stations}
    chosen = [by_lid[lid] for lid in SELECTED]
    snapshots = {}
    for station in chosen:
        for source in station["sources"].values():
            if file_hash(ROOT / source["path"]) != source["sha256"]:
                raise ValueError("admission source digest changed")
            if file_hash(ROOT / source["receipt_path"]) != source["receipt_sha256"]:
                raise ValueError("admission receipt digest changed")
        snapshots[station["lid"]] = strict_json(
            (ROOT / station["snapshot_path"]).read_bytes()
        )
    registry = make_registry(chosen, snapshots, stamp())
    registry["selection_explanation"] = {
        "rivers": "three elevated/rising/near-threshold contexts, two ordinary controls, across four RFCs",
        "coast": "JMPN7 retained in candidate order with more QC-eligible overlap than regional alternate MROS1",
        "excluded": "CHLA2 datum disagreement; MLLA1 missing forecast and primary ID; MROS1 admitted regional alternate",
        "no_future_outcome_or_model_error_selection": True,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "initial").mkdir()
    package = output / "code/disastertrace/hydro_shadow_v1"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text(
        '"""Frozen standalone shadow package."""\n'
    )
    source_dir = ROOT / "disastertrace-starter/src/disastertrace/hydro_shadow_v1"
    for path in sorted(source_dir.glob("*.py")):
        shutil.copyfile(path, package / path.name)
    shutil.copyfile(BUNDLE / "verify_shadow.py", output / "verify_shadow.py")
    for lid, snapshot in snapshots.items():
        write_new(output / "initial" / f"{lid}.json", snapshot)
    write_new(output / "REGISTRY.json", registry)
    files = {
        str(p.relative_to(output)): file_hash(p)
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    write_new(output / "FREEZE.json", {"frozen_at": stamp(), "files": files})
    print(
        {
            "root": str(output),
            "targets": len(registry["targets"]),
            "polls": len(registry["poll_at"]),
            "stop_at": registry["scheduled_stop_at"],
        }
    )


def launch(output):
    log_path = output / "WORKER.log"
    env = {
        **os.environ,
        "PYTHONPATH": str(output / "code"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    with log_path.open("xb") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "disastertrace.hydro_shadow_v1.pipeline",
                "worker",
                "--root",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    write_new(
        output / "LAUNCH.json",
        {
            "launched_at": stamp(),
            "pid": proc.pid,
            "registry_sha256": file_hash(output / "REGISTRY.json"),
        },
    )
    print({"pid": proc.pid, "log": str(log_path)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    prepare(output)
    if args.launch:
        launch(output)
