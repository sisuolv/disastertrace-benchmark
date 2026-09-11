"""Create and verify the local MM offline review archive without publication."""

import hashlib
import importlib.metadata
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
FINAL = ROOT / "finalization_01"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    status = json.loads((FINAL / "STATUS.json").read_text())
    if status["status"] != "passed" or status["model_generations"] != 0:
        raise ValueError("offline acceptance prerequisite differs")
    metadata = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"]):
        name = distribution.metadata["Name"]
        entry = {k: distribution.metadata.get(k) for k in ("Name", "Version", "License", "License-Expression", "Home-page")}
        copied = []
        for item in distribution.files or []:
            if ("license" in item.name.lower() or item.name.upper().startswith(("COPYING", "NOTICE"))) and ".dist-info" in str(item):
                source = distribution.locate_file(item)
                if not source.is_file():
                    continue
                target = ROOT / "dependency_licenses" / re.sub(r"[^A-Za-z0-9_.-]", "_", name) / str(item).replace("/", "__")
                target.parent.mkdir(parents=True, exist_ok=True)
                data = source.read_bytes()
                with target.open("xb") as stream:
                    stream.write(data)
                copied.append({"path": str(target.relative_to(ROOT)), "sha256": sha(data)})
        entry["license_files"] = copied
        metadata.append(entry)
    write(ROOT / "THIRD_PARTY_METADATA.json", metadata)
    selected = {}

    def tree(directory, prefix):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts:
                if path.is_symlink():
                    raise ValueError("unexpected symlink in review scope")
                selected[prefix + path.relative_to(directory).as_posix()] = path

    tree(FINAL / "source", "source/")
    tree(FINAL / "tests", "tests/")
    tree(ROOT / "build_02", "build/")
    tree(ROOT / "diagnostics_02", "diagnostics/")
    tree(ROOT / "synthetic_fixture", "synthetic_fixture/")
    tree(ROOT / "dependency_licenses", "dependency_licenses/")
    for path in FINAL.iterdir():
        if path.is_file():
            selected["verification/" + path.name] = path
    for name in ("SOURCE_FREEZE.json", "pytest-mm.ini", "finalize_mm0_2_source.py", "isolated_cpu_review.py"):
        selected[name] = FINAL / name
    for name in ("IMPLEMENTATION_STATUS.md", "REVIEW_GUIDE_CN.md", "NEXT_MM3_CN.md", "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_METADATA.json", "BASELINE.json", "seal_review_package.py"):
        selected[name] = ROOT / name
    selected["requirements.txt"] = ROOT / "requirements-mm-cpu-resolved.txt"
    selected["review.py"] = FINAL / "isolated_cpu_review.py"
    selected["INTEGRATED_PLAN_CN.md"] = PROJECT.parent / "plans/multimodal_v1/INTEGRATED_PLAN_CN.md"
    selected["EXECUTION_MM0_2_CN.md"] = PROJECT.parent / "plans/multimodal_v1/EXECUTION_MM0_2_CN.md"
    payloads, hashes = {}, {}
    for name, path in selected.items():
        data = path.read_bytes()
        if re.search(rb"\bsk-[A-Za-z0-9_-]{24,}\b|-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----", data):
            raise ValueError("credential-like payload in selected path: " + name)
        payloads[name], hashes[name] = data, sha(data)
    contents = {"schema": "mm_offline_review_package_v1", "files_sha256": hashes,
                "model_calls": 0, "full_mm_offline_reconstruction": True, "includes_old_p6_p14_full_evidence": False}
    archive = ROOT / "MM0_2_REVIEW.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for name in sorted(payloads):
            stream.writestr(name, payloads[name])
        stream.writestr("PACKAGE_CONTENTS.json", json.dumps(contents, sort_keys=True, indent=2) + "\n")
    with zipfile.ZipFile(archive) as stream:
        if stream.testzip() is not None or set(stream.namelist()) != set(hashes) | {"PACKAGE_CONTENTS.json"}:
            raise ValueError("review archive structure or CRC differs")
        for name, expected in hashes.items():
            if sha(stream.read(name)) != expected or sha(selected[name].read_bytes()) != expected:
                raise ValueError("review archive differs from selected bytes")
    receipt = {"at": datetime.now(timezone.utc).isoformat(), "status": "passed", "archive": archive.name,
               "archive_sha256": sha(archive.read_bytes()), "archive_bytes": archive.stat().st_size,
               "selected_files": len(hashes), "all_members_hash_verified": True, "credential_pattern_scan_passed": True,
               "source_freeze_sha256": sha((FINAL / "SOURCE_FREEZE.json").read_bytes()),
               "final_status_sha256": sha((FINAL / "STATUS.json").read_bytes()),
               "cpu_review_sha256": sha((FINAL / "CPU_REVIEW.json").read_bytes()),
               "tests_passed": status["tests_passed"], "model_calls": 0, "gpu_jobs": 0, "git_publication": False,
               "files_sha256": {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in set(selected.values()) if path.is_relative_to(ROOT)}}
    receipt["acceptance_id"] = sha(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
    write(ROOT / "COMPLETED.json", receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != "files_sha256"}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
