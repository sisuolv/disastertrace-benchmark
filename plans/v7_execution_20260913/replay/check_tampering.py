"""Exercise deep integrity checks using disposable relocated copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(package, output):
    output.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="disastertrace-replay-negative-") as temporary:
        trial = Path(temporary) / "package"
        shutil.copytree(package, trial, ignore=shutil.ignore_patterns("__pycache__"))
        original_manifest = (trial / "PACKAGE_MANIFEST.json").read_bytes()
        request_path = next((trial / "batches/fixed_matrix_01/worker-0").glob("*-request.json"))
        response_path = request_path.with_name(request_path.name.replace("request", "response"))
        policy_path = next((trial / "matrix/policy").glob("*.json"))
        cases = [
            ("raw_changed", response_path, "Raw output checksum differs"),
            ("token_count_changed", request_path, "Input token accounting differs"),
            ("late_cutoff", policy_path, "Cutoff contradicts target semantics"),
            ("missing_capture", request_path, "FileNotFoundError"),
        ]
        results = []
        for name, path, expected in cases:
            original = path.read_bytes()
            value = json.loads(original)
            if name == "raw_changed":
                value["raw"] += "\n"
            elif name == "token_count_changed":
                value["input_tokens"] += 1
            elif name == "late_cutoff":
                value["payload"]["cutoff"] = value["payload"]["target"]["physical_start"]
            if name == "missing_capture":
                path.unlink()
            else:
                path.write_text(json.dumps(value, indent=2) + "\n")
                manifest = json.loads(original_manifest)
                # Update only the outer package digest, exercising inner contracts.
                manifest["files"][str(path.relative_to(trial))] = hashlib.sha256(path.read_bytes()).hexdigest()
                (trial / "PACKAGE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
            process = subprocess.run(
                [sys.executable, "-I", "-B", "run_replay.py", "--guard-original-paths-and-network", "--output", str(Path(temporary) / (name + "_result"))],
                cwd=trial, text=True, capture_output=True, timeout=120, check=False,
            )
            path.write_bytes(original)
            (trial / "PACKAGE_MANIFEST.json").write_bytes(original_manifest)
            passed = process.returncode != 0 and expected in process.stderr
            (output / (name + ".log")).write_text(process.stdout + process.stderr)
            results.append({"case": name, "rejected": passed, "expected": expected, "returncode": process.returncode})
            if not passed:
                raise ValueError("Negative check failed: " + name)
    (output / "REPORT.json").write_text(json.dumps({"all_rejected": True, "cases": results, "authentic_package_changed": False}, indent=2) + "\n")
    print(json.dumps({"negative_checks_passed": len(results), "authentic_package_changed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.package.resolve(), arguments.output.resolve())
