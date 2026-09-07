"""Execute and record the final cached-source build and offline pilot package."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import file_hash, write_json
from disastertrace.automated.workflow import implementation_snapshot, verify_build

root = Path(__file__).resolve().parents[2]
logs = root / "artifacts/pre_api_v1/cli"
logs.mkdir(parents=True, exist_ok=False)
cli = str(root / ".venv/bin/disastertrace-auto")
build = "work/build-pre-api-v1"
package = "work/pre-api-v1"
commands = [
    ["build", "--references", "../references", "--nhc-snapshot", "../references/nhc_cohort_v1", "--output", build],
    ["preflight", "--build", build, "--specification", "configs/pre_api_pilot_v1.json", "--verification-record", "artifacts/pre_api_v1/final_checks/test_result.json", "--output", package],
    ["verify-preflight", "--build", build, "--package", package],
    ["build", "--references", "../references", "--nhc-snapshot", "../references/nhc_cohort_v1", "--output", "work/repro-build-pre-api-v1"],
    ["audit-dataset", "--build", build, "--output", "artifacts/pre_api_v1/dataset_audit.json"],
]
for method in ("structured_state", "snapshot", "answer_history"):
    commands.extend([
        ["prepare-model", "--build", build, "--config", "configs/provider.example.json", "--method", method, "--split", "development", "--event-group", "AL092021", "--max-queries", "10", "--output", f"work/pre-api-provider-{method}.json"],
        ["audit-collection", "--build", build, "--collection", f"{package}/rehearsal/{method}/resumed", "--split", "development", "--event-group", "AL092021", "--output", f"artifacts/pre_api_v1/collection-audit-{method}.json"],
    ])
record = []
for index, arguments in enumerate(commands):
    command = [cli, *arguments]
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = logs / f"{index:02d}-{arguments[0]}.log"
    log.write_text(result.stdout, encoding="utf-8")
    record.append({"command": command, "started_at": started, "exit_code": result.returncode,
                   "log": str(log.relative_to(root)), "log_sha256": file_hash(log)})
    write_json(logs.parent / "commands.json", record)
    print(f"{index:02d} {arguments[0]}: exit={result.returncode}", flush=True)
    if result.returncode:
        raise RuntimeError(result.stdout)
original = verify_build(root / build)
repeated = verify_build(root / "work/repro-build-pre-api-v1")
source_parser = file_hash(root / "src/disastertrace/automated/sources.py")
prior_parser = file_hash(root / "work/build-cohort-v1/implementation_source/automated/sources.py")
prior_manifest = verify_build(root / "work/build-cohort-v1")
data_files = {name: digest for name, digest in original["files"].items()
              if name != "implementation.json" and not name.startswith("implementation_source/")}
old_data = {name: digest for name, digest in prior_manifest["files"].items()
            if name != "implementation.json" and not name.startswith("implementation_source/")}
verification = {
    "build_id": original["build_id"], "repeated_build_id": repeated["build_id"],
    "manifest_equal": original == repeated,
    "implementation_matches_current": json.loads((root / build / "implementation.json").read_text()) == implementation_snapshot(),
    "source_parser_sha256": source_parser, "source_parser_unchanged": source_parser == prior_parser,
    "data_artifacts_equal_to_cohort_v1": data_files == old_data,
    "nonimplementation_artifact_count": len(data_files),
    "live_model_calls": 0,
}
write_json(logs.parent / "reproducibility.json", verification)
assert all(verification[key] for key in ("manifest_equal", "implementation_matches_current", "source_parser_unchanged", "data_artifacts_equal_to_cohort_v1"))
print(json.dumps(verification, indent=2))
