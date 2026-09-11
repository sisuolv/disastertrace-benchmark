"""Make and actually reconstruct a self-contained review ZIP; never rewrite one."""

import io
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "source/src"))

from disastertrace.multimodal_v1.storage import canonical, digest, now, publish_bytes, read, write


def main():
    write(ROOT / "SEAL_CLAIM.json", {"at": now()})
    if read(ROOT / "FINALIZATION_RESULT.json")["status"] != "passed":
        raise ValueError("finalization has not passed")
    patterns = [rb"sk-[A-Za-z0-9]{20,}", rb"gh[pousr]_[A-Za-z0-9]{20,}",
                rb"github_pat_[A-Za-z0-9_]{20,}", rb"-----BEGIN (?:OPENSSH|RSA|EC) PRIVATE KEY-----"]
    selected = sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                      and p.name not in {"SEAL_01.log", "MM4_REVIEW.zip"} and p.suffix != ".pyc")
    files = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in selected}
    for p in selected:
        if any(re.search(pattern, p.read_bytes()) for pattern in patterns):
            raise ValueError("credential-like bytes in review input: " + str(p.relative_to(ROOT)))
    manifest = {"files": {"batch/" + name: sha for name, sha in files.items()},
                "denied_paths": [str(ROOT), str(ROOT.parent / "mm0_2_20260909"),
                                 str(ROOT.parent / "mm3_20260909"),
                                 str(ROOT.parent / "mm3_contract_v2_live_20260909"),
                                 str(PROJECT / "src"), read(ROOT / "EXECUTION.json")["model_directory"]]}
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for p in selected:
            archive.write(p, "batch/" + str(p.relative_to(ROOT)))
        archive.writestr("REVIEW_MANIFEST.json", canonical(manifest) + "\n")
    data = payload.getvalue()
    publish_bytes(ROOT / "MM4_REVIEW.zip", data)
    extracted = PROJECT / "work/mm4-atomic-archive-review-20260909"
    extracted.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() is not None:
            raise ValueError("archive CRC mismatch")
        if set(archive.namelist()) != set(manifest["files"]) | {"REVIEW_MANIFEST.json"}:
            raise ValueError("archive membership mismatch")
        for name, expected in manifest["files"].items():
            if digest(archive.read(name)) != expected:
                raise ValueError("archive member hash mismatch")
        archive.extractall(extracted)
    argv = ["/mnt/afs/260010168/.venvs/disastertrace-mm-cpu-v1/bin/python", str(extracted / "batch/review_cpu.py"),
            "--bundle", str(extracted), "--receipt", str(extracted / "VERIFIED.json")]
    reply = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    write(ROOT / "ARCHIVE_REVIEW_COMMAND.json", {"argv": argv, "returncode": reply.returncode,
          "stdout": reply.stdout, "stderr": reply.stderr})
    if reply.returncode:
        raise RuntimeError("archive-extracted CPU reconstruction failed; preserve this attempt")
    publish_bytes(ROOT / "ARCHIVE_REVIEW_RESULT.json", (extracted / "VERIFIED.json").read_bytes())
    prior = read(ROOT / "PRIOR_BINDINGS.json")
    for name, expected in prior.items():
        if digest((PROJECT / name).read_bytes()) != expected:
            raise ValueError("prior evidence changed")
    report, resources = read(ROOT / "REPORT.json"), read(ROOT / "RESOURCE_ACCOUNTING.json")
    selected_after = sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                            and p.name != "SEAL_01.log" and p.suffix != ".pyc")
    acceptance = {"status": "completed_and_reviewed", "at": now(),
                  "execution_sha256": digest((ROOT / "EXECUTION.json").read_bytes()),
                  "report_sha256": digest((ROOT / "REPORT.json").read_bytes()),
                  "planned": report["planned"], "dispatches": report["dispatches"],
                  "by_family": report["by_family"], "event_count": 1,
                  "gpu_jobs": [j["job_id"] for j in resources["jobs"]],
                  "all_jobs_succeeded": all(j["state"] == "SUCCEEDED" for j in resources["jobs"]),
                  "max_reserved_h100": resources["max_reserved_h100"], "active_account_jobs": 0,
                  "paid_api_calls": 0, "generation_retries": 0,
                  "submission_initial_interruption": "STARTING realized replicas=0; three unsubmitted shards continued",
                  "archive": "MM4_REVIEW.zip", "archive_bytes": len(data), "archive_sha256": digest(data),
                  "archive_members_verified": len(manifest["files"]) + 1,
                  "archive_cpu_review": True, "credential_pattern_scan_passed": True,
                  "prior_bound_files_verified": len(prior),
                  "local_files_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in selected_after}}
    acceptance["acceptance_id"] = digest(canonical(acceptance).encode())
    write(ROOT / "COMPLETED.json", acceptance)
    print(json.dumps({"acceptance_id": acceptance["acceptance_id"], "archive_bytes": len(data),
                     "archive_sha256": digest(data), "bound_files": len(acceptance["local_files_sha256"])}))


if __name__ == "__main__":
    main()
