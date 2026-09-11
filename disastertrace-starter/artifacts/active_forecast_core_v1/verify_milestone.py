"""Verify this handoff's bound bytes and compatibility claims without model calls."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    package = here.parent.parent
    repository = package.parent
    failures, counts = [], {}
    baseline = json.loads((here / "BASELINE.json").read_text())
    preserved = {
        p: h for p, h in baseline["files"].items() if p not in baseline["planned_existing_edits"]
    }
    for relative, expected in preserved.items():
        if digest(repository / relative) != expected:
            failures.append("baseline changed: " + relative)
    counts["preserved_baseline_files"] = len(preserved)
    manifest = json.loads((here / "MANIFEST.json").read_text())
    for relative, expected in manifest["files"].items():
        if digest(package / relative) != expected:
            failures.append("handoff file changed: " + relative)
    counts["handoff_files"] = len(manifest["files"])
    report = json.loads((here / "replay_02/COMPATIBILITY.json").read_text())
    if report["status"] != "passed" or report["failure_count"] != 0:
        failures.append("compatibility did not pass")
    for field, expected in {
        "certificates": 104,
        "read_decisions": 1296,
        "read_sufficiency": 1296,
        "score_cases": 41600,
    }.items():
        if report["checks"][field] != expected:
            failures.append("unexpected compatibility count: " + field)
    for relative, expected in report["core_source_sha256"].items():
        if digest(package / "src/disastertrace/active_forecast" / relative) != expected:
            failures.append("core differs from the replayed version: " + relative)
    bindings = json.loads((here / "replay_02/SOURCE_BINDINGS.json").read_text())
    for relative, binding in bindings.items():
        path = repository / relative
        if digest(path) != binding["sha256"] or path.stat().st_size != binding["bytes"]:
            failures.append("bound source changed: " + relative)
    counts["source_binding_files"] = len(bindings)
    if "59 passed" not in (here / "14_tests_59.log").read_text():
        failures.append("final unit test success record missing")
    if "Ran 10 tests" not in (here / "10_frozen_prototype_tests.log").read_text():
        failures.append("frozen prototype test record missing")
    commands = json.loads((here / "CLI_EXAMPLES.json").read_text())["commands"]
    if len(commands) != 4 or any(c["exit_code"] != 0 for c in commands):
        failures.append("CLI examples did not all succeed")
    result = {
        "status": "passed" if not failures else "failed",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checks": counts,
        "failures": failures,
        "model_calls": 0,
        "meaning": "Artifact integrity and recorded acceptance, not a new independent scientific reference computation.",
    }
    with Path(args.output).open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
