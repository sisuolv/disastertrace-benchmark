"""Seal both MM-3 outcome evidence and the explicitly unlaunched V2 candidate."""

import datetime
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
V2 = ROOT.parent / "mm3_contract_v2_offline_20260909"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = json.loads((ROOT / "REPORT.json").read_text())
    assert report["generation_intents"] == report["returned"] == 12
    assert report["counts"] == {"received_invalid": 12}
    assert not report["interface_gate"]
    assert json.loads((ROOT / "CPU_REVIEW_RESULT.json").read_text())["status"] == "passed"
    assert json.loads((ROOT / "PRESERVATION_VERIFIED.json").read_text())["status"] == "passed"
    release = json.loads((ROOT / "acp/ACCOUNT_RELEASE_VERIFIED.json").read_text())
    assert release["active_job_count"] == 0 and release["mm3_job"]["state"] == "SUCCEEDED"
    assert json.loads((V2 / "OFFLINE_ACCEPTANCE.json").read_text())["generations"] == 0
    suite = ET.parse(V2 / "TESTS.xml").find("testsuite")
    assert int(suite.attrib["tests"]) == 41
    assert all(int(suite.attrib[k]) == 0 for k in ["errors", "failures", "skipped"])
    local_files, selected = {}, {}
    for directory in [ROOT, V2]:
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.name in {"MM3_REVIEW.zip", "COMPLETED.json", "DELIVERY_VERIFIED.json"}:
                continue
            if path.name.endswith(".tmp"):
                raise ValueError("unresolved temporary evidence")
            local_files[str(path.relative_to(ROOT.parent))] = digest(path)
            # The full historic account job catalogue is local resource evidence.
            if path.name != "account_jobs_before.json":
                selected[str(path.relative_to(ROOT.parent))] = path
    review = PROJECT / "work/mm3-cpu-review-20260909"
    for path in sorted(review.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            selected["cpu_review/" + str(path.relative_to(review))] = path
    selected["cpu_review/requirements.txt"] = ROOT.parent / "mm0_2_20260909/requirements-mm-cpu-resolved.txt"
    for path in selected.values():
        data = path.read_bytes()
        if re.search(rb"(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|BEGIN [A-Z ]*PRIVATE KEY)", data):
            raise ValueError("credential-pattern scan requires inspection: " + str(path))
    manifest = {name: digest(path) for name, path in selected.items()}
    archive = ROOT / "MM3_REVIEW.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for name, path in selected.items():
            package.write(path, name)
        package.writestr("ARCHIVE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        package.writestr("README.txt", "Read mm3_20260909/REVIEW_GUIDE_CN.md.\nMM-3: 12 real replies; 12 invalid state-array outputs.\nV2: offline prepared only; zero generations.\nCPU replay: python cpu_review/review_cpu.py --bundle cpu_review --receipt /tmp/mm3-review-new.json\n")
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise ValueError("archive CRC failed")
        for name, expected in manifest.items():
            if hashlib.sha256(package.read(name)).hexdigest() != expected:
                raise ValueError("archive member digest mismatch")
    result = {"status": "engineering_closed_interface_gate_failed", "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "execution_sha256": digest(ROOT / "EXECUTION.json"), "report_sha256": digest(ROOT / "REPORT.json"),
              "generation_opportunities": 12, "responses": 12, "valid_outputs": 0,
              "strict_correct": 0, "interface_gate": False, "gpu_terminal": "SUCCEEDED",
              "gpu_jobs": 1, "max_simultaneous_h100": 1, "paid_api_calls": 0,
              "v2_status": "offline_prepared_unlaunched", "v2_generations": 0,
              "archive": archive.name, "archive_bytes": archive.stat().st_size,
              "archive_sha256": digest(archive), "archive_members_verified": len(manifest),
              "credential_pattern_scan_passed": True, "local_files_sha256": local_files}
    result["acceptance_id"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with (ROOT / "COMPLETED.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "local_files_sha256"}, indent=2))


if __name__ == "__main__":
    main()
