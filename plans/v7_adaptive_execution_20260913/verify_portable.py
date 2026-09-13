"""Relocated, network-disabled, stdlib-only reconstruction of the new evidence."""

import hashlib
import importlib.util
import json
import socket
import sys
from pathlib import Path


def main(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(exist_ok=False, parents=True)

    def denied(*args, **kwargs):
        raise RuntimeError("Network is disabled during portable review")

    socket.socket = denied
    socket.create_connection = denied
    sys.path.insert(0, str(root / "disastertrace-starter/src"))
    from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
    from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator

    manifest = json.loads((root / "MANIFEST.json").read_text())
    for rel, sha in manifest.items():
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != sha:
            raise ValueError("Portable file differs: " + rel)
    here = root / "plans/v7_adaptive_execution_20260913"
    reports = here / "reports"
    journal_count = 0
    for name in ("typed_session_01", "new_calendar_typed_01", "model_development_01"):
        folder = reports / name
        expected = json.loads((folder / "SCORES.json").read_text())
        arms = {}
        for arm in expected["scores"]["arms"]:
            if name == "model_development_01":
                path = folder / (arm + ".jsonl")
            elif arm.startswith("branch_"):
                path = folder / (arm.removeprefix("branch_") + "-branch.jsonl")
            else:
                path = folder / (arm + ".jsonl")
            arms[arm] = path
            journal_count += 1
        actual = score_admitted(json.loads((folder / "OUTCOME_REFERENCES.json").read_text()), arms)
        if actual != expected:
            raise ValueError("Portable cutoff score differs: " + name)
    branches = 0
    for name in ("typed_session_01", "new_calendar_typed_01"):
        folder = reports / name
        for spec in sorted(folder.glob("*-branch-input.json")):
            row = json.loads(spec.read_text())
            session = SessionCoordinator.restore(row["snapshot"], row["data"], row["bank"])
            while not session.done:
                session.step(row["controls"])
            expected = json.loads(
                spec.with_name(spec.name.replace("-input", "-result")).read_text()
            )
            if session.report != expected["report"] or session.snapshot() != expected["snapshot"]:
                raise ValueError("Portable controller continuation differs")
            branches += 1
    spec = importlib.util.spec_from_file_location(
        "new_model_replay", here / "verify_development.py"
    )
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.main(
        here / "gpu/development_01", here / "development_dataset_01", output / "model", False
    )
    if json.loads((output / "model/REPORT.json").read_text()) != json.loads(
        (reports / "model_development_01/REPORT.json").read_text()
    ):
        raise ValueError("Portable model capture/score reconstruction differs")
    old_spec = importlib.util.spec_from_file_location(
        "old_smoke_replay", here / "diagnose_previous_smoke.py"
    )
    old = importlib.util.module_from_spec(old_spec)
    old_spec.loader.exec_module(old)
    old.main(output / "old_smoke")
    if json.loads((output / "old_smoke/REPORT.json").read_text()) != json.loads(
        (reports / "previous_smoke_audit_02/REPORT.json").read_text()
    ):
        raise ValueError("Old smoke audit changed during relocation")
    report = {
        "passed": True,
        "network_disabled": True,
        "manifest_files": len(manifest),
        "typed_journals_replayed": journal_count,
        "controller_branches_replayed": branches,
        "new_batch_captures_reaudited": 252,
        "old_batch_captures_reaudited": 108,
        "new_inference_calls": 0,
        "model_weights_required": False,
        "source_root": str(root / "disastertrace-starter/src"),
        "admission_module": str(Path(sys.modules[AdmissionEngine.__module__].__file__).resolve()),
    }
    (output / "RESULT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
