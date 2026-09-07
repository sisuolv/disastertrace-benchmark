"""Read-only review of exported files, source equality, and test input closure.

Only the requested audit JSON is written, and it must be below handoff_audit.
Credential candidates are reported by path/line/rule, never by matching value.
Git internals and this audit directory are excluded from payload inspection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_child(root, name):
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("dependency path escapes supplied root")
    return path


def audit(root, original):
    checks, issues = [], []

    def check(name, passed, **detail):
        row = {"name": name, "passed": bool(passed), **detail}
        checks.append(row)
        if not passed:
            issues.append(row)

    patterns = {
        "provider_key_prefix": re.compile(
            rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"
        ),
        "github_classic_token": re.compile(
            rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"
        ),
        "github_fine_grained_token": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
        "aws_access_key_id": re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
        "private_key_pem": re.compile(
            rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
        ),
        "literal_secret_assignment": re.compile(
            rb"""(?i)["']?(?:api_key|access_token|refresh_token|client_secret)["']?\s*[:=]\s*["']([^\r\n"']{12,})["']"""
        ),
        "literal_bearer": re.compile(
            rb"""(?i)["']authorization["']\s*:\s*["']Bearer ([A-Za-z0-9._~+/-]{20,})"""
        ),
    }
    excluded_parts = {".git", ".venv", "handoff_audit"}
    unwanted = {
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    }
    files, symlinks, forbidden_paths, candidates = [], [], [], []
    for directory, subdirs, names in os.walk(root, followlinks=False):
        base = Path(directory)
        subdirs[:] = sorted(name for name in subdirs if name not in excluded_parts)
        for name in list(subdirs):
            path = base / name
            if path.is_symlink():
                symlinks.append(path)
                subdirs.remove(name)
        for name in sorted(names):
            path = base / name
            if path.is_symlink():
                symlinks.append(path)
                continue
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if (
                any(part in unwanted for part in path.relative_to(root).parts)
                or path.suffix == ".pyc"
                or name
                in {
                    ".env",
                    ".env.local",
                    "id_rsa",
                    "id_ed25519",
                    "hosts.yml",
                    "credentials.json",
                }
            ):
                forbidden_paths.append(relative)
            data = path.read_bytes()
            files.append(
                {
                    "path": relative,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
            for rule, pattern in patterns.items():
                for match in pattern.finditer(data):
                    value = match.group(1) if match.lastindex else match.group(0)
                    documented_placeholder = (
                        rule == "literal_secret_assignment"
                        and value.startswith(b"<")
                        and value.endswith(b">")
                        and b"api" in value.lower()
                        and b"key" in value.lower()
                    )
                    declared_fixture = rule == "literal_secret_assignment" and any(
                        word in value.lower()
                        for word in (
                            b"fixture",
                            b"test",
                            b"dummy",
                            b"example",
                            b"fake",
                            b"placeholder",
                            b"redacted",
                            b"must-not",
                        )
                    )
                    candidates.append(
                        {
                            "path": relative,
                            "line": data.count(b"\n", 0, match.start()) + 1,
                            "rule": rule,
                            "classification": "documentation_placeholder"
                            if documented_placeholder
                            else (
                                "explicit_fixture_literal"
                                if declared_fixture
                                else "requires_review"
                            ),
                            "matched_value_printed": False,
                        }
                    )
    large = [row for row in files if row["bytes"] > 50 * 1024 * 1024]
    escaping = [
        {"path": str(path.relative_to(root)), "target": os.readlink(path)}
        for path in symlinks
        if not path.resolve().is_relative_to(root.resolve())
    ]
    check("no_payload_file_above_50_mib", not large, files=large)
    check("no_escaping_symlinks", not escaping, symlinks=escaping)
    check("no_payload_symlinks", not symlinks, count=len(symlinks))
    check(
        "no_credentials_cache_or_environment_paths",
        not forbidden_paths,
        paths=forbidden_paths,
    )
    unresolved = [
        row for row in candidates if row["classification"] == "requires_review"
    ]
    check(
        "no_unreviewed_credential_pattern_candidates",
        not unresolved,
        candidates=unresolved,
    )
    starter = root / "disastertrace-starter"
    source_files = [
        path
        for folder in ("src", "tests")
        for path in (original / folder).rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    for source in sorted(source_files):
        relative = source.relative_to(original)
        target = starter / relative
        check(
            "source_test_bytes_preserved",
            target.is_file() and sha(source) == sha(target),
            path=relative.as_posix(),
        )
    test_dependencies = [
        "work/build-cohort-v1/manifest.json",
        "work/build-deepseek-v1/episodes/dynamic_episodes.jsonl",
        "artifacts/p1_deepseek_development/provider.json",
        "artifacts/p1_deepseek_development/docs/rates.json",
        "configs/pre_api_pilot_v1.json",
        "configs/provider.example.json",
        "configs/nhc_cohort_v1.json",
        "docs/CALIBRATION_PROTOCOL_V1.md",
    ]
    for relative in test_dependencies:
        check(
            "direct_test_input_present", (starter / relative).is_file(), path=relative
        )
    cohort = starter / "work/build-cohort-v1"
    if (cohort / "manifest.json").is_file():
        for relative, expected in read(cohort / "manifest.json")["files"].items():
            target = safe_child(cohort, relative)
            check(
                "cohort_fixture_manifest_entry",
                target.is_file() and sha(target) == expected,
                path=relative,
            )
    references = root / "references"
    weather = references / "no_manual_review_2026-09-06/weather_qa_sources"
    if (weather / "MANIFEST.json").is_file():
        for row in read(weather / "MANIFEST.json"):
            if row["repo"] == "TamuChen18/DisasterBench_Open":
                target = safe_child(weather, row["local_path"])
                check(
                    "disasterbench_dependency",
                    target.is_file() and sha(target) == row["sha256"],
                    path=str(target.relative_to(root)),
                )
    else:
        check("disasterbench_manifest_present", False)
    cyport = references / "opensource_audit_2026-09-06"
    if (cyport / "AUDIT.json").is_file():
        repository = next(
            row
            for row in read(cyport / "AUDIT.json")["repositories"]
            if row["repository"] == "ChenchenMobility/MLLM-Bench-CyPortQA"
        )
        row = next(
            row
            for row in repository["source_files"]
            if row["upstream_path"] == "source_data/CyPortQA_template.json"
        )
        target = safe_child(cyport, row["path"])
        check(
            "cyportqa_dependency",
            target.is_file() and sha(target) == row["sha256"],
            path=str(target.relative_to(root)),
        )
    else:
        check("cyportqa_audit_present", False)
    for name in ("implementation_sources", "nhc_cohort_v1"):
        snapshot = references / name
        if not (snapshot / "MANIFEST.json").is_file():
            check("nhc_manifest_present", False, snapshot=name)
            continue
        manifest = read(snapshot / "MANIFEST.json")
        for row in manifest["files"]:
            for kind in ("html", "text"):
                target = safe_child(snapshot, row[kind + "_path"])
                check(
                    "nhc_dependency",
                    target.is_file() and sha(target) == row[kind + "_sha256"],
                    path=str(target.relative_to(root)),
                )
        if "catalogue_path" in manifest:
            target = safe_child(snapshot, manifest["catalogue_path"])
            check(
                "nhc_catalogue_dependency",
                target.is_file() and sha(target) == manifest["catalogue_sha256"],
                path=str(target.relative_to(root)),
            )
    return {
        "schema_version": "github_handoff_readonly_audit_v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root.resolve()),
        "scope": "staged payload only; Git internals, ignored .venv environments and handoff_audit outputs excluded",
        "network_calls": 0,
        "model_api_calls": 0,
        "git_mutations": 0,
        "full_test_suite_rerun": False,
        "credential_values_printed": False,
        "checks_passed": sum(row["passed"] for row in checks),
        "checks_total": len(checks),
        "passed": not issues,
        "issues": issues,
        "checks": checks,
        "credential_pattern_candidates": candidates,
        "payload_file_count": len(files),
        "payload_bytes": sum(row["bytes"] for row in files),
        "largest_files": sorted(files, key=lambda row: row["bytes"], reverse=True)[:10],
        "suffix_counts": dict(Counter(Path(row["path"]).suffix for row in files)),
        "payload_files_sha256": {row["path"]: row["sha256"] for row in files},
        "limitations": [
            "Pattern-based scanning does not prove absence of arbitrary unrecognized secrets.",
            "Archived absolute paths remain historical metadata; original archive replay portability requires separate documentation/rebuilding.",
            "An offline deterministic diagnostic is not a live model result.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(
        (args.root / "handoff_audit").resolve()
    ):
        raise ValueError("audit output must be under handoff_audit")
    result = audit(args.root, args.original)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "passed",
                    "checks_passed",
                    "checks_total",
                    "payload_file_count",
                    "payload_bytes",
                    "issues",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
