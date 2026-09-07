"""Record actual offline verification commands; preserve prior attempts."""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import file_hash, write_json
from disastertrace.automated.workflow import implementation_snapshot

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
root = Path(__file__).resolve().parents[2]
python = str(root / ".venv/bin/python")
ruff = str(root / ".venv/bin/ruff")
targets = ["src/disastertrace/automated"] + [str(path.relative_to(root)) for path in sorted((root / "tests").glob("test_automated_*.py"))]
commands = [
    ("full_pytest", [python, "-m", "pytest", "-o", "addopts=", "-q"]),
    ("ruff_check", [ruff, "check", "--select", "E4,E7,E9,F,I", *targets]),
    ("ruff_format", [ruff, "format", "--check", *targets]),
    ("pip_check", [python, "-m", "pip", "check"]),
]
snapshot = implementation_snapshot()
record = {"schema_version": "offline_verification_v1", "implementation_id": snapshot["implementation_id"],
          "checks": [], "pytest_passed": 0, "pytest_skipped": None,
          "test_files": {str(path.relative_to(root)): file_hash(path) for path in sorted((root / "tests").rglob("*.py"))},
          "executed_at": datetime.now(timezone.utc).isoformat()}
for name, command in commands:
    log = args.output / f"{name}.log"
    result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log.write_text(result.stdout, encoding="utf-8")
    record["checks"].append({"command": command, "exit_code": result.returncode, "log": log.name, "log_sha256": file_hash(log)})
    if name == "full_pytest":
        passed = re.search(r"(\d+) passed", result.stdout)
        skipped = re.search(r"(\d+) skipped", result.stdout)
        record["pytest_passed"] = int(passed[1]) if passed else 0
        record["pytest_skipped"] = int(skipped[1]) if skipped else 0
    print(f"{name}: exit={result.returncode}\n{result.stdout[-3500:]}", flush=True)
    write_json(args.output / "test_result.json", record)
if snapshot != implementation_snapshot():
    raise RuntimeError("implementation changed during verification")
sys.exit(int(any(check["exit_code"] != 0 for check in record["checks"])))
