"""Seal the actual V2 outcome and its portable, no-generation CPU review."""

import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def main():
    report = read(ROOT / "REPORT.json")
    assert report["generation_intents"] == report["returned"] == 12
    assert read(ROOT / "FINALIZATION_RESULT.json")["status"] == "passed"
    assert read(ROOT / "PRESERVATION_VERIFIED.json")["status"] == "passed"
    release = read(ROOT / "acp/ACCOUNT_RELEASE_VERIFIED.json")
    assert release["active_job_count"] == 0 and release["v2_job"]["state"] == "SUCCEEDED"
    paths = [p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths = [p for p in paths if p.name not in {"COMPLETED.json", "DELIVERY_VERIFIED.json", "MM3_V2_REVIEW.zip"}]
    local = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    selected = {"batch/" + str(p.relative_to(ROOT)): p for p in paths if p.name != "account_jobs_before.json"}
    review = PROJECT / "work/mm3-v2-cpu-review-20260909"
    selected.update({"cpu_review/" + str(p.relative_to(review)): p for p in review.rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts})
    selected["cpu_review/requirements.txt"] = ROOT.parent / "mm0_2_20260909/requirements-mm-cpu-resolved.txt"
    members = {n: sha(p) for n, p in selected.items()}
    for path in selected.values():
        if re.search(rb"(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|BEGIN [A-Z ]*PRIVATE KEY)", path.read_bytes()):
            raise ValueError("credential pattern requires inspection: " + str(path))
    archive = ROOT / "MM3_V2_REVIEW.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for name, path in selected.items():
            z.write(path, name)
        z.writestr("ARCHIVE_MANIFEST.json", json.dumps(members, indent=2) + "\n")
        z.writestr("README.txt", "Read batch/IMPLEMENTATION_STATUS.md and batch/REVIEW_GUIDE_CN.md.\nV2: structural parse 12/12; complete query sets 10/12; strict task correctness 0/12.\nCPU replay: python cpu_review/review_cpu.py --bundle cpu_review --receipt /tmp/mm3-v2-review-new.json\n")
    restore = PROJECT / "work/mm3-v2-archive-review-20260909"
    restore.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name, expected in members.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == expected
        z.extractall(restore)
    argv = ["/mnt/afs/260010168/.venvs/disastertrace-mm-cpu-v1/bin/python",
            str(restore / "cpu_review/review_cpu.py"), "--bundle", str(restore / "cpu_review"),
            "--receipt", str(restore / "CPU_ARCHIVE_REVIEW.json")]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=50)
    save(restore / "REVIEW_COMMAND.json", {"argv": argv, "exit_code": result.returncode,
                                           "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError("archive CPU reconstruction failed")
    summary = {"status": "completed", "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "execution_sha256": sha(ROOT / "EXECUTION.json"), "report_sha256": sha(ROOT / "REPORT.json"),
               "responses": 12, "structural_parse_valid": report["counts"].get("received_valid", 0),
               "complete_query_sets": read(ROOT / "QUERY_COVERAGE.json")["complete_query_sets"],
               "strict_correct": report["strict_correct"], "predeclared_interface_gate": report["interface_gate"],
               "gpu_jobs": 1, "max_parallel_h100": 1, "gpu_state": "SUCCEEDED",
               "paid_api_calls": 0, "retries": 0, "event_count": 1,
               "archive": archive.name, "archive_bytes": archive.stat().st_size,
               "archive_sha256": sha(archive), "archive_files_verified": len(members),
               "archive_cpu_review": read(restore / "CPU_ARCHIVE_REVIEW.json"),
               "credential_pattern_scan_passed": True, "local_files_sha256": local}
    summary["acceptance_id"] = hashlib.sha256(json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    save(ROOT / "COMPLETED.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "local_files_sha256"}, indent=2))


if __name__ == "__main__":
    main()
