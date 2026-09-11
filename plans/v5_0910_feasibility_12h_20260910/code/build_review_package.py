"""Create a small review bundle; source arrays and full raw runs stay on AFS."""

import json
from pathlib import Path
import zipfile

from common import ROOT, dump
from model_adapter import sha_file


def main():
    names = ["README.md", "FINAL_PLAN_CN.md", "RESULTS_CN.md", "FINAL_DATASETS.json", "REPRODUCIBILITY.md",
        "REVIEW_FOR_CHATGPT_PRO_CN.md", "CLOSURE.json", "RESOURCE_ACCOUNTING.json", "BASELINE.json", "SCOPE.json",
        "SCOPE_AMENDMENT_01.json", "TASK_LEDGER.json", "reports/NOVELTY_AUDIT_CN.md",
        "reports/figures/feasibility_diagnostics.png", "reports/figures/feasibility_diagnostics.svg",
        "analysis/FINAL_RESULTS_02.json", "analysis/MODEL_RESULTS.csv", "analysis/PROGRAM_BUDGET_CURVES.csv",
        "analysis/PILOT_CONSTRUCTION.json", "analysis/PUBLIC_SOLVABILITY.json", "analysis/STATE_CONSTRUCTION.json",
        "analysis/STATE_REFERENCE_PREFLIGHT.json", "analysis/USDM_POINT_REFERENCE_RECHECK.json",
        "analysis/NATURAL_COVERAGE_FEASIBILITY.json", "analysis/CLIMATOLOGY_FEASIBILITY_02.json",
        "analysis/NHC_RESOLUTION_DIAGNOSTIC.json", "verification/final_01/VERIFICATION.json",
        "data/PILOT_EPISODES_PRIVATE.json", "data/NATURAL_EPISODES_PRIVATE.json",
        "data/STATE_PUBLIC.json", "data/STATE_REFERENCES_PRIVATE.json"]
    names += [f"analysis/WAVE{i}_AUDIT.json" for i in range(1, 8)]
    names += [str(p.relative_to(ROOT)) for p in (ROOT / "code").glob("*.py")]
    names = sorted(set(names))
    manifest = {"purpose": "Research/code review; not a self-contained inference or full-data reproduction archive",
        "not_included": ["Model weights", "Raw HTTP bodies", "Native source NPY arrays", "Full inference prompt/processor logs", "Inherited parent captures"],
        "files": [{"path": name, "bytes": (ROOT / name).stat().st_size, "sha256": sha_file(ROOT / name)} for name in names]}
    archive_path = ROOT / "REVIEW_PACKAGE.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("PACKAGE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        for name in names:
            archive.write(ROOT / name, name)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("review archive CRC failed")
        for row in manifest["files"]:
            import hashlib
            if hashlib.sha256(archive.read(row["path"])).hexdigest() != row["sha256"]:
                raise ValueError("review archive entry hash differs")
    dump(ROOT / "REVIEW_PACKAGE_MANIFEST.json", {**manifest, "archive_bytes": archive_path.stat().st_size,
                                                "archive_sha256": sha_file(archive_path), "zip_integrity": "passed"})
    print(json.dumps({"files": len(names), "bytes": archive_path.stat().st_size, "zip_integrity": "passed"}))


if __name__ == "__main__":
    main()
