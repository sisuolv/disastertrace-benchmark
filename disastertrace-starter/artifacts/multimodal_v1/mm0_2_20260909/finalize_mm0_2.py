"""Freeze and validate one MM-0/1/2 offline batch; no model or GPU dispatch."""

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
PROJECT = BUNDLE.parents[2]
REPO = PROJECT.parent
FINAL = BUNDLE / "finalization_01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def read(path):
    return json.loads(path.read_text())


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    FINAL.mkdir(exist_ok=False)
    source = FINAL / "source"
    tests = FINAL / "tests"
    for path in sorted((PROJECT / "src/disastertrace/multimodal_v1").glob("*.py")):
        target = source / path.relative_to(PROJECT / "src")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for name in ("__init__.py", "models.py", "forecast_source/__init__.py", "forecast_source/normalization.py", "forecast_source/parser_a.py", "forecast_source/parser_b.py"):
        target = source / "disastertrace" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / "src/disastertrace" / name, target)
    tests.mkdir()
    for path in sorted((PROJECT / "tests").glob("test_multimodal_v1_*.py")):
        shutil.copyfile(path, tests / path.name)
    shutil.copyfile(PROJECT / "pytest-mm.ini", FINAL / "pytest-mm.ini")
    shutil.copyfile(BUNDLE / "isolated_cpu_review.py", FINAL / "isolated_cpu_review.py")
    shutil.copyfile(Path(__file__), FINAL / "finalize_mm0_2_source.py")
    files = {str(p.relative_to(FINAL)): sha(p) for folder in (source, tests) for p in folder.rglob("*") if p.is_file()}
    for name in ("pytest-mm.ini", "isolated_cpu_review.py", "finalize_mm0_2_source.py"):
        files[name] = sha(FINAL / name)
    packages = sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
    write(FINAL / "SOURCE_FREEZE.json", {"at": now(), "files_sha256": files, "packages": packages,
                                        "python": sys.version, "scope": "MM-0 through MM-2; zero model generations"})
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "PYTHONHASHSEED": "0",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(source), "PROJ_NETWORK": "OFF", "OMP_NUM_THREADS": "2"}
    records = []

    def command(name, args, cwd=PROJECT):
        write(FINAL / (name + "_intent.json"), {"at": now(), "argv": [str(a) for a in args], "cwd": str(cwd), "source_freeze_sha256": sha(FINAL / "SOURCE_FREEZE.json")})
        with (FINAL / (name + ".log")).open("xb") as stream:
            result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record = {"name": name, "at": now(), "exit_code": result.returncode, "log_sha256": sha(FINAL / (name + ".log"))}
        write(FINAL / (name + "_result.json"), record)
        records.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)
        if result.returncode:
            raise RuntimeError("validation command failed: " + name)

    command("tests", [sys.executable, "-m", "pytest", "-c", FINAL / "pytest-mm.ini", "-q", "--junitxml=" + str(FINAL / "tests.xml"), tests])
    command("lint", [PROJECT / ".venv/bin/ruff", "check", "--select", "F", source / "disastertrace/multimodal_v1", tests])
    build, diagnostics = BUNDLE / "build_02", BUNDLE / "diagnostics_02"
    command("build", [sys.executable, "-m", "disastertrace.multimodal_v1", "build-seed", "--sources", BUNDLE / "source_seed", "--output", build])
    command("diagnose", [sys.executable, "-m", "disastertrace.multimodal_v1", "diagnose", "--build", build, "--output", diagnostics])
    command("verify", [sys.executable, "-m", "disastertrace.multimodal_v1", "verify-report", "--build", build, "--diagnostics", diagnostics, "--receipt", FINAL / "REPORT_RECONSTRUCTION.json"])
    command("fixture", [sys.executable, "-c", "from disastertrace.multimodal_v1.fixtures import build_fixture; import sys; build_fixture(sys.argv[1])", BUNDLE / "synthetic_fixture"])
    review = Path(tempfile.mkdtemp(prefix="disastertrace-mm-cpu-"))
    shutil.copytree(source, review / "source")
    shutil.copytree(build, review / "build")
    shutil.copytree(diagnostics, review / "diagnostics")
    shutil.copyfile(FINAL / "isolated_cpu_review.py", review / "review.py")
    write(FINAL / "CPU_RELOCATION.json", {"review_root": str(review), "original_repository_blocked": str(REPO)})
    command("relocated_cpu", [sys.executable, "-I", review / "review.py", REPO], cwd=review)
    shutil.copyfile(review / "CPU_REVIEW.json", FINAL / "CPU_REVIEW.json")
    baseline = read(BUNDLE / "BASELINE.json")
    old_bad = [name for name, expected in baseline["historical_files_sha256"].items() if sha(PROJECT / name) != expected]
    supplement = PROJECT / "artifacts/autonomy_10h_v1/COMPLETED_SUPPLEMENT.json"
    if sha(supplement) != baseline["supplement_sha256"]:
        raise ValueError("old supplement changed")
    old_bad += [name for name, expected in read(supplement)["evidence_sha256"].items() if sha(PROJECT / name) != expected]
    if old_bad:
        raise ValueError("historical bytes changed: " + repr(old_bad))
    for name, expected in files.items():
        if sha(FINAL / name) != expected:
            raise ValueError("frozen implementation changed")
    for path in (source / "disastertrace/multimodal_v1").glob("*.py"):
        if sha(path) != sha(PROJECT / "src/disastertrace/multimodal_v1" / path.name):
            raise ValueError("working source differs from accepted source")
    suites = ET.parse(FINAL / "tests.xml").getroot().findall("testsuite")
    test_count = sum(int(s.attrib["tests"]) for s in suites)
    if any(int(s.attrib[k]) for s in suites for k in ("failures", "errors", "skipped")):
        raise ValueError("tests did not all pass")
    write(FINAL / "STATUS.json", {"status": "passed", "at": now(), "tests_passed": test_count, "commands": records,
                                  "old_source_test_config_files_unchanged": len(baseline["historical_files_sha256"]),
                                  "old_supplement_files_unchanged": len(read(supplement)["evidence_sha256"]),
                                  "real_build": "build_02", "diagnostics": "diagnostics_02", "model_generations": 0,
                                  "paid_api_calls": 0, "gpu_jobs": 0, "heldout_inference": 0, "training": False,
                                  "old_publication": baseline["old_publication"], "source_freeze_sha256": sha(FINAL / "SOURCE_FREEZE.json")})
    print(json.dumps(read(FINAL / "STATUS.json"), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
