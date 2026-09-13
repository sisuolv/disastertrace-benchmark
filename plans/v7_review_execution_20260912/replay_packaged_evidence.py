"""Restore published evidence parts and exercise a separate, source-bound checkout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
PUBLICATION = REPO / "publication/v7_review_execution_20260912"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def test_worker(args):
    root = args.output.resolve()
    binding = json.loads((root / "SOURCE_BINDINGS.json").read_text())
    original = Path(binding["original_repository"])
    for name, expected in binding["files"].items():
        if digest(root / name) != expected:
            raise ValueError("Copied review implementation changed")

    original_connect = socket.socket.connect

    def local_connect(connection, address):
        if isinstance(address, tuple) and address[0] in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            return original_connect(connection, address)
        raise RuntimeError("External network disabled during packaged tests")

    socket.socket.connect = local_connect

    def audit(event, arguments):
        if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0])).absolute()
            if path.is_relative_to(original) and not path.is_relative_to(
                original / "disastertrace-starter/.venv"
            ):
                raise RuntimeError(
                    "Original project data/code disabled during packaged tests"
                )

    sys.addaudithook(audit)
    import disastertrace.monitoring_v1
    import pytest

    if not Path(disastertrace.monitoring_v1.__file__).resolve().is_relative_to(root):
        raise ValueError("Test package did not come from the separate checkout")
    tests = sorted(
        str(path)
        for path in (root / "disastertrace-starter/tests").glob("test_monitoring_*.py")
    )
    bundle = root / "plans/v7_review_execution_20260912"
    tests += [
        str(bundle / name)
        for name in [
            "test_calendar_analysis.py",
            "test_e_probe_runtime.py",
            "test_independent_taf_adapter.py",
        ]
    ]
    result = pytest.main(
        [*tests, "-q", "--junitxml=" + str(root / "results/TESTS.xml")]
    )
    if result:
        raise SystemExit(int(result))
    suites = ET.parse(root / "results/TESTS.xml").getroot().findall("testsuite")
    if sum(int(row.attrib["tests"]) for row in suites) != 109 or any(
        int(row.attrib[key])
        for row in suites
        for key in ("errors", "failures", "skipped")
    ):
        raise ValueError("Packaged test denominator differs or contains skipped tests")


def prepare(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "results").mkdir()
    bindings = {}

    def copy(path):
        destination = root / path.relative_to(REPO)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        if digest(destination) != digest(path):
            raise ValueError("Review code copy failed")
        bindings[str(destination.relative_to(root))] = digest(path)

    for path in (REPO / "disastertrace-starter/src/disastertrace/monitoring_v1").rglob(
        "*.py"
    ):
        copy(path)
    for name in ("__init__.py", "models.py"):
        copy(REPO / "disastertrace-starter/src/disastertrace" / name)
    for path in (REPO / "disastertrace-starter/tests").glob("test_monitoring_*.py"):
        copy(path)
    for path in BASE.glob("*.py"):
        copy(path)
    for path in BASE.glob("*CONTRACT.json"):
        copy(path)
    copy(BASE / "E_DIAGNOSTIC_LABELS_01.json")
    copy(PUBLICATION / "evidence_archive.py")
    write(
        root / "SOURCE_BINDINGS.json",
        {"files": bindings, "original_repository": str(REPO)},
    )
    archive_spec = importlib.util.spec_from_file_location(
        "sealed_archive",
        root / "publication/v7_review_execution_20260912/evidence_archive.py",
    )
    module = importlib.util.module_from_spec(archive_spec)
    archive_spec.loader.exec_module(module)
    units = [
        "data_regional_01",
        "data_regional_02",
        "data_replication_2026",
        "data_extension_bay_area_01",
        "tokenizers",
        "pilot_02",
        "mm_01",
        "model_e32",
        "model_bay_base",
    ]
    restored = []
    for name in units:
        source = PUBLICATION / "evidence" / name
        if not (PUBLICATION / "inventories" / (name + "_ARCHIVE_CHECK.json")).is_file():
            raise ValueError("Requested archive has not passed its content check")
        restored.append(
            {
                "unit": name,
                "manifest_sha256": digest(source / "manifest.json"),
                "result": module.restore(source, root),
            }
        )
        print(json.dumps({"restored": name}), flush=True)
    write(root / "RESTORATION.json", restored)
    bundle = root / "plans/v7_review_execution_20260912"
    tokenizer_root = root / "publication/v7_review_execution_20260912/review_tokenizers"
    env = dict(
        os.environ,
        PYTHONPATH=str(root / "disastertrace-starter/src") + ":" + str(bundle),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        NO_PROXY="127.0.0.1,localhost,::1",
    )
    commands = []

    def run(name, argv, timeout=3600):
        started = datetime.now(timezone.utc).isoformat()
        with (root / "results" / (name + ".log")).open("x") as stream:
            result = subprocess.run(
                argv,
                cwd=root,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        record = {
            "name": name,
            "argv": argv,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "returncode": result.returncode,
        }
        commands.append(record)
        (root / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n")
        print(
            json.dumps({"completed": name, "returncode": result.returncode}), flush=True
        )
        if result.returncode:
            raise ValueError("Packaged reproduction failed: " + name)

    run(
        "core_tests",
        [
            sys.executable,
            str(bundle / "replay_packaged_evidence.py"),
            "--test-worker",
            "--output",
            str(root),
        ],
    )
    run(
        "data_rebuild",
        [
            sys.executable,
            str(bundle / "offline_data_replay.py"),
            "--dataset",
            str(bundle / "replication_2026_01"),
            "--contract",
            str(bundle / "REPLICATION_2026_CONTRACT.json"),
            "--deny-project",
            str(REPO),
            "--output",
            str(root / "results/data_rebuild"),
        ],
    )
    for name, batch, evidence, kind in [
        ("pilot", "gpu_pilot_02", "regional_02/private/OUTCOMES.json", "F"),
        ("multimodal", "gpu_mm_01", "regional_02/private/OUTCOMES.json", "F"),
        ("E32", "gpu_e_diagnostic_32b_01", "E_DIAGNOSTIC_LABELS_01.json", "E"),
        (
            "Bay_full",
            "gpu_bay_secondary_base_01",
            "extension_bay_area_01/private/OUTCOMES.json",
            "F",
        ),
    ]:
        run(
            name,
            [
                args.model_python,
                str(bundle / "offline_model_replay.py"),
                "--batch",
                str(bundle / batch),
                "--validation",
                str(bundle / (batch + "_validation_01")),
                "--evidence",
                str(bundle / evidence),
                "--tokenizer-root",
                str(tokenizer_root),
                "--kind",
                kind,
                "--deny-project",
                str(REPO),
                "--output",
                str(root / "results" / name),
            ],
        )
    write(
        root / "COMPLETE.json",
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "restored_units": units,
            "commands": commands,
            "tests": 109,
            "skipped_tests": 0,
            "model_replayed_calls": 16 + 72 + 384 + 5184,
            "new_model_calls": 0,
            "new_network_requests": 0,
            "scope": "Separate checkout populated from packaged archives; frozen code and recorded outputs replayed with original project reads denied. Core tests permit loopback sockets only; model/data replays block network.",
            "fresh_ACP_job_queries": 0,
            "weights_required": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test-worker", action="store_true")
    parser.add_argument(
        "--model-python", default=sys.executable,
        help="Python with the documented tokenizer/processor replay dependencies; defaults to the current interpreter",
    )
    arguments = parser.parse_args()
    test_worker(arguments) if arguments.test_worker else prepare(arguments)
