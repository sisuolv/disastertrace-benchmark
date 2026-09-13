"""Build a source/receipt review package without weights, secrets or API clients."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main(destination):
    destination = Path(destination).resolve()
    destination.mkdir(exist_ok=False, parents=True)
    for path in sorted(HERE.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(HERE)
        if any(
            part.startswith(("portable_", "relocated_", "__pycache__")) for part in relative.parts
        ):
            continue
        if relative.parts[0] in {"baseline_source"} or path.suffix in {".zip", ".pyc", ".lock"}:
            continue
        if "legacy_parity_01/source" in relative.as_posix():
            continue
        dest = destination / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    bank = ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01/BANK.json"
    dest = destination / bank.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bank, dest)
    source = HERE / "gpu/development_01/source/disastertrace"
    shutil.copytree(source, destination / "disastertrace-starter/src/disastertrace")
    old_bindings = json.loads(
        (HERE / "reports/previous_smoke_audit_02/SOURCE_BINDINGS.json").read_text()
    )
    old_records = ROOT / "plans/v7_followup_execution_20260913/reports/model_smoke_02/RECORDS.json"
    for path in [old_records, *[ROOT / b["path"] for b in old_bindings]]:
        dest = destination / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    shutil.copyfile(HERE / "verify_portable.py", destination / "verify_portable.py")
    (destination / "README.md").write_text(
        "# DisasterTrace v7 typed adaptive review\n\n"
        "Read plans/v7_adaptive_execution_20260913/FINAL_REPORT_CN.md.\n\n"
        "Replay using the Python standard library, without network, weights or new inference:\n\n"
        "```bash\npython -I -B verify_portable.py . ../new-review-output\n```\n\n"
        "The output directory must be new. GPU launch directories are consumed; do not relaunch.\n"
    )
    manifest = {
        str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(destination.rglob("*"))
        if p.is_file()
    }
    (destination / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"directory": str(destination), "files": len(manifest)}))


if __name__ == "__main__":
    main(sys.argv[1])
