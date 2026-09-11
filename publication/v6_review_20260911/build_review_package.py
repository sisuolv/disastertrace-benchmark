"""Build the explicit V6 publication list, standalone Markdown and deterministic ZIP."""

import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V6 = ROOT / "plans/v6_0911_dataset_selection"
PRIOR = ROOT / "plans/multihazard_source_validation_20260911"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def main():
    selected = set()

    def add(path):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("invalid publication file: " + str(path))
        if path.stat().st_size >= 16 * 1024**2:
            raise ValueError("file outside reading-size bound: " + str(path))
        selected.add(path)

    for path in V6.iterdir():
        if path.is_file() and path.suffix in {".py", ".md", ".json", ".jsonl", ".csv"}:
            add(path)
    for directory in [V6 / "inputs", V6 / "specs"]:
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".md"}:
                add(path)
    for name in ["DOWNLOADED_AUDIT.json", "SELECTION_AUDIT.json", "SCOPE_METADATA_CORRECTION_01.json",
                 "audit_selection_attempt01.py", "probe_sources_priority01.py", "selection_audit_01.log",
                 "selection_audit_04.log", "build_reports_02.log", "verify_selection_01.log"]:
        add(V6 / "analysis" / name)
    for path in PRIOR.iterdir():
        if path.is_file() and path.suffix in {".py", ".md", ".json"}:
            add(path)
    for name in ["INHERITED_SAMPLES.json", "VALIDATION_FAILURE_01.json", "FETCHER_AMENDMENT_01.json"]:
        path = PRIOR / "analysis" / name
        if path.exists():
            add(path)
    # Audit sources import these older readers; retain their exact implementation.
    for path in (PRIOR / "specs").glob("*.json"):
        add(path)
    package = ROOT / "disastertrace-starter"
    for relative in ["src/disastertrace/multimodal_v1", "src/disastertrace/active_forecast", "tests/active_forecast"]:
        for path in (package / relative).glob("*.py"):
            add(path)
    for name in ["README_MULTIMODAL_V1.md", "README_ACTIVE_FORECAST_V1.md"]:
        if (package / name).exists():
            add(package / name)
    add(ROOT / "README.md")
    add(HERE / "REVIEW_FOR_CHATGPT_PRO_CN.md")
    add(HERE / "README.md")
    add(HERE / "build_review_package.py")
    add(HERE / "verify_review_snapshot.py")

    sections = [HERE / "REVIEW_FOR_CHATGPT_PRO_CN.md"] + [V6 / name for name in [
        "DATA_READINESS_REVIEW_CN.md", "HAZARD_COVERAGE.md", "SOURCE_FEASIBILITY.md",
        "RELATED_BENCHMARK_COMPARISON.md", "REUSE_AND_GAPS.md"]]
    content = ["# DisasterTrace V6: ChatGPT Pro 单文件复查材料\n\n"
               "本文件汇集审查任务、主要报告和关键代码。当前为数据验证阶段，尚无新增模型实验。\n"
               "请优先核对主张与证据，按严重性报告问题。完整文件清单和机器可读审计另在同目录 ZIP。\n"]
    for path in sections:
        content.append("\n---\n\n来源文件：`" + str(path.relative_to(ROOT)) + "`\n\n" + path.read_text())
    for path in [V6 / "audit_selection.py", V6 / "audit_downloaded.py", V6 / "verify_selection.py"]:
        content.append("\n---\n\n## 代码：" + str(path.relative_to(ROOT)) + "\n\n```python\n" + path.read_text() + "\n```\n")
    all_in_one = HERE / "CHATGPT_PRO_REVIEW_ALL_IN_ONE.md"
    all_in_one.write_text("\n".join(content))
    add(all_in_one)

    scanner_path = ROOT / "publication/autonomy_review_20260909/check_payload.py"
    spec = importlib.util.spec_from_file_location("payload_scanner", scanner_path)
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    issues = []
    content = {}
    for path in sorted(selected):
        name, raw = str(path.relative_to(ROOT)), path.read_bytes()
        scanner.inspect(name, raw, issues)
        if re.search(rb"(?:X-Amz-Signature|[?&]Signature)=[A-Za-z0-9_%_-]{32,}", raw, re.I):
            issues.append({"path": name, "rule": "signed_download_credential_in_reading_copy"})
        content[name] = raw
    if issues:
        (HERE / "PAYLOAD_SCAN_FAILURE.json").write_bytes(encode({"issues": issues, "matched_values_printed": False}))
        raise ValueError("Publication scan needs correction; see paths/rules in failure record")
    manifest = {"schema": "v6_review_publication_files_v1", "source_parent_commit": "a8ea30d6fd35e5889f5f846ee9f49c87480cf96d",
                "target_branch": "next-phase-v1", "selected_files": len(content),
                "files_sha256": {n: sha(b) for n, b in content.items()},
                "full_raw_data_reproduction_bundle": False, "model_calls": 0,
                "excluded": ["raw HTTP payloads and signed redirects", "scientific arrays", "model weights",
                             "credentials and runtime environments", "unrelated staged historical archives"],
                "original_scripts_require_raw_inputs": True}
    manifest_path = HERE / "PUBLICATION_FILES.json"
    manifest_path.write_bytes(encode(manifest))
    content[str(manifest_path.relative_to(ROOT))] = manifest_path.read_bytes()
    notes = {"start_here": str((HERE / "REVIEW_FOR_CHATGPT_PRO_CN.md").relative_to(ROOT)),
             "files_sha256": {n: sha(b) for n, b in content.items()}, "limits": manifest["excluded"],
             "check": "python3 publication/v6_review_20260911/verify_review_snapshot.py"}
    content["READING_CONTENTS.json"] = encode(notes)
    archive_path = HERE / "disastertrace_v6_chatgpt_review.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(content.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("reading ZIP CRC failed")
        for name, raw in content.items():
            if archive.read(name) != raw:
                raise ValueError("reading ZIP payload differs: " + name)
    summary = {"status": "built_and_scanned", "selected_files": len(selected), "zip_members": len(content),
               "zip_bytes": archive_path.stat().st_size, "zip_sha256": sha(archive_path.read_bytes()),
               "standalone_markdown_bytes": all_in_one.stat().st_size,
               "credential_scan_issues": [], "matched_values_printed": False, "new_model_calls": 0}
    (HERE / "BUILD_RESULT.json").write_bytes(encode(summary))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
