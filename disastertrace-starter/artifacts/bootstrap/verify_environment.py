"""Record actual isolated-environment checks without altering source files."""

from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts" / "bootstrap"
PACKAGES = [
    "disastertrace", "pydantic", "typer", "PyYAML", "orjson", "python-dateutil",
    "ijson", "pytest", "pytest-asyncio", "hypothesis", "ruff", "mypy", "pip",
]
report = {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "executable": sys.executable,
    "python_version": sys.version,
    "isolated": sys.prefix != sys.base_prefix,
    "versions": {},
    "checks": [],
}
for name in PACKAGES:
    try:
        report["versions"][name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        report["versions"][name] = None

commands = [
    ("pip_check", [sys.executable, "-m", "pip", "check"]),
    ("original_tests", [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-rA",
                        "tests/test_scoring.py", "tests/test_runner.py",
                        "tests/test_interventions.py", "tests/test_evidence_gate.py"]),
    ("editable_import", [sys.executable, "-c",
                         "import disastertrace; print(disastertrace.__file__)"]),
    ("runtime_imports", [sys.executable, "-c",
                         "import pydantic, typer, yaml, orjson, dateutil, ijson, hypothesis; "
                         "print('All runtime dependencies and hypothesis import successfully.')"]),
    ("ruff_version", [str(Path(sys.executable).parent / "ruff"), "--version"]),
    ("mypy_version", [str(Path(sys.executable).parent / "mypy"), "--version"]),
    ("native_cli_help", [str(Path(sys.executable).parent / "disastertrace"), "--help"]),
    ("automated_cli_help", [sys.executable, "-m", "disastertrace.automated", "--help"]),
]
for name, command in commands:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    (OUTPUT / f"{name}.log").write_text(completed.stdout + completed.stderr)
    report["checks"].append({"name": name, "command": command, "exit_code": completed.returncode})

(OUTPUT / "environment_verification.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
sys.exit(0 if report["isolated"] and all(x["exit_code"] == 0 for x in report["checks"]) else 1)
