"""Rebuild one frozen native cohort from copied captures with original reads denied."""

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
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def normalized_audit(record):
    return {
        key: value
        for key, value in record.items()
        if key not in {"built_at", "implementation_sha256"}
    }


def prepare(args):
    args.output = args.output.resolve()
    original = args.dataset.resolve()
    source_root = original.parent
    original_audit = load(original / "REGIONAL_JOIN_AUDIT.json")
    if digest(args.contract) != original_audit["contract_sha256"]:
        raise ValueError("The supplied contract is not the cohort contract")
    args.output.mkdir(exist_ok=False)
    checkout = args.output / "checkout"
    checkout.mkdir()
    inputs = {}

    def copy(source, target, expected=None):
        sha = digest(source)
        if expected is not None and sha != expected:
            raise ValueError("Source does not match frozen binding: " + str(source))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != sha:
            raise ValueError("Copied bytes changed")
        inputs[str(target.relative_to(checkout))] = sha

    copy(args.contract, checkout / "CONTRACT.json")
    captures = load(original / "SOURCES.json")
    metar_dirs, taf_dirs = set(), set()
    for ident, record in captures.items():
        for key, checksum in (("path", "sha256"), ("receipt_path", "receipt_sha256")):
            copy(source_root / record[key], checkout / record[key], record[checksum])
        dirs = metar_dirs if ident.startswith("metar-routine-") else taf_dirs
        dirs.add(str(Path(record["path"]).parent))
    if len(metar_dirs) != 1 or len(taf_dirs) != 1:
        raise ValueError("One assembled METAR and one assembled TAF directory required")
    taf_dir = next(iter(taf_dirs))
    copy(source_root / taf_dir / "MANIFEST.json", checkout / taf_dir / "MANIFEST.json")
    for path in (original / "implementation").rglob("*.py"):
        copy(path, checkout / "code" / path.relative_to(original / "implementation"))
    pinned_hashes = set(original_audit["implementation_sha256"].values())
    if not pinned_hashes.issubset(set(inputs.values())):
        raise ValueError("Frozen builder/provider implementations are not recoverable")
    copy(Path(__file__), checkout / "offline_data_replay.py")
    expected_files = {
        str(path.relative_to(original)): digest(path)
        for path in original.rglob("*.json")
        if "implementation" not in path.relative_to(original).parts
        and path.name != "REGIONAL_JOIN_AUDIT.json"
    }
    write(
        checkout / "RELOCATION.json",
        {
            "source_cohort": str(original),
            "original_repository": str(source_root.parents[1]),
            "additional_denied_projects": [
                str(path.resolve()) for path in args.deny_project
            ],
            "metar_dir": next(iter(metar_dirs)),
            "taf_dir": taf_dir,
            "expected_files": expected_files,
            "expected_audit": normalized_audit(original_audit),
            "builder_hashes": sorted(pinned_hashes),
            "inputs": inputs,
            "new_network_requests": 0,
            "new_model_calls": 0,
        },
    )
    env = dict(
        os.environ, PYTHONPATH=str(checkout / "code"), PYTHONDONTWRITEBYTECODE="1"
    )
    with (args.output / "REPLAY.log").open("x") as stream:
        result = subprocess.run(
            [
                sys.executable,
                str(checkout / "offline_data_replay.py"),
                "--worker",
                "--output",
                str(args.output),
            ],
            cwd=checkout,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    write(
        args.output / "PROCESS.json",
        {
            "returncode": result.returncode,
            "new_model_calls": 0,
            "new_network_requests": 0,
        },
    )
    if result.returncode:
        raise ValueError("Copied-source reconstruction failed; inspect REPLAY.log")


def worker(args):
    root = Path(__file__).resolve().parent
    relocation = load(root / "RELOCATION.json")

    def deny_network(*_args, **_kwargs):
        raise RuntimeError("Network disabled during data reconstruction")

    socket.socket.connect = deny_network

    def audit(event, arguments):
        if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0])).absolute()
            for denied in [
                relocation["original_repository"],
                *relocation.get("additional_denied_projects", []),
            ]:
                old = Path(denied)
                runtime = old / "disastertrace-starter/.venv"
                if (
                    path.is_relative_to(old)
                    and not path.is_relative_to(root)
                    and not path.is_relative_to(args.output.resolve())
                    and not path.is_relative_to(runtime)
                ):
                    raise RuntimeError("Original project read denied: " + str(path))

    sys.addaudithook(audit)
    for name, expected in relocation["inputs"].items():
        if digest(root / name) != expected:
            raise ValueError("Copied input changed: " + name)
    spec = importlib.util.spec_from_file_location(
        "sealed_builder", root / "code/build_regional.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = root
    rebuilt = args.output / "rebuilt"
    module.build(
        root / "CONTRACT.json",
        root / relocation["metar_dir"],
        root / relocation["taf_dir"],
        rebuilt,
    )
    files = {}
    for name, expected in relocation["expected_files"].items():
        actual = digest(rebuilt / name)
        if actual != expected:
            raise ValueError("Derived file did not reproduce byte-for-byte: " + name)
        files[name] = actual
    observed = load(rebuilt / "REGIONAL_JOIN_AUDIT.json")
    if normalized_audit(observed) != relocation["expected_audit"]:
        raise ValueError("Scientific audit counts or retained failures changed")
    if (
        sorted(set(observed["implementation_sha256"].values()))
        != relocation["builder_hashes"]
    ):
        raise ValueError("Rebuild used different implementations")
    write(
        args.output / "REPLAY_REPORT.json",
        {
            "source_cohort": relocation["source_cohort"],
            "copied_inputs": len(relocation["inputs"]),
            "derived_files_byte_identical": files,
            "audit_scientific_content_identical": True,
            "allowed_audit_metadata_changes": [
                "built_at",
                "implementation path prefixes, hashes unchanged",
            ],
            "original_project_reads_denied": True,
            "network_blocked": True,
            "new_network_requests": 0,
            "new_model_calls": 0,
            "implementation_sha256": digest(Path(__file__)),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--deny-project", type=Path, action="append", default=[])
    arguments = parser.parse_args()
    worker(arguments) if arguments.worker else prepare(arguments)
