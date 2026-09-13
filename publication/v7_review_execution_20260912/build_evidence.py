"""Seal selected completed v7 evidence into checked, bounded, deduplicated parts."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from evidence_archive import build, digest, encoded, restore, sha, write

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUNDLE = REPO / "plans/v7_review_execution_20260912"
OMIT = {"__pycache__", ".pytest_cache", ".ruff_cache"}
FORBIDDEN = {
    ".git",
    ".venv",
    "site-packages",
    "credentials",
    "credentials.json",
    ".env",
}
SECRET_PATTERNS = (
    rb"sk-[A-Za-z0-9_-]{25,}",
    rb"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
    rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
    rb"[?&](?:Signature|Key-Pair-Id)=",
    rb"(?im)^\s*[\"']?(?:key|api_key|access_token)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{25,}",
)


def screen(path, data):
    if any(re.search(pattern, data) for pattern in SECRET_PATTERNS):
        raise ValueError("Potential sensitive value in selected file: " + str(path))


def main(args):
    if not re.fullmatch(r"[a-z0-9_]+", args.name):
        raise ValueError("Invalid evidence unit name")
    source = args.source.resolve()
    if not source.is_relative_to(BUNDLE) and not (
        args.kind == "auxiliary" and source == HERE / "review_tokenizers"
    ):
        raise ValueError("Only the new v7 execution bundle is an evidence source")
    gates = []
    if args.kind == "model":
        if args.verification is None:
            raise ValueError("A completed independent model audit is required")
        verified = json.loads(args.verification.read_text())
        plan = json.loads((source / "PLAN.json").read_text())
        if (
            digest(source / "PLAN.json") != verified["plan_sha256"]
            or Path(verified["batch"]).resolve() != source
            or verified["actual_calls"] > plan["maximum_model_calls"]
        ):
            raise ValueError("Model audit does not match this bounded batch")
        for worker in plan["workers"]:
            if not (source / ("worker-" + worker) / "COMPLETE.json").is_file():
                raise ValueError("A model worker is incomplete")
        gates.append(args.verification.resolve())
    elif args.kind == "controls":
        record = json.loads((source / "SUMMARY.json").read_text())
        if not record["runs"] or any(
            r["actual_model_calls"] for r in record["runs"].values()
        ):
            raise ValueError(
                "Cheap-control completion is missing or contains model calls"
            )
        gates.append(source / "SUMMARY.json")
    elif args.kind == "auxiliary":
        if args.verification is None or not args.verification.is_file():
            raise ValueError(
                "An explicit existing auxiliary inventory or report is required"
            )
        gates.append(args.verification.resolve())
    else:
        gates.append(source / "REGIONAL_JOIN_AUDIT.json")
    paths = set()

    def add(path):
        path = path.absolute()
        relative = path.relative_to(REPO)
        if (
            path.is_symlink()
            or any(part in FORBIDDEN for part in relative.parts)
            or path.suffix in {".safetensors", ".ckpt", ".pt", ".pth", ".pyc"}
        ):
            raise ValueError("Forbidden artifact in selected scope: " + str(relative))
        if not path.is_file() or path.stat().st_size > 512 * 1024**2:
            raise ValueError("Missing or unexpectedly large evidence file")
        paths.add(path)

    def tree(directory):
        for folder, directories, names in os.walk(directory):
            directories[:] = sorted(name for name in directories if name not in OMIT)
            for name in sorted(names):
                add(Path(folder) / name)

    tree(source)
    if args.kind == "model":
        tree(args.verification.resolve().parent)
    if args.kind == "dataset":
        captures = json.loads((source / "SOURCES.json").read_text())
        for record in captures.values():
            for key, checksum in (
                ("path", "sha256"),
                ("receipt_path", "receipt_sha256"),
            ):
                path = (BUNDLE / record[key]).resolve()
                if not path.is_relative_to(BUNDLE) or digest(path) != record[checksum]:
                    raise ValueError("Raw source binding failed")
                add(path)
            manifest = (BUNDLE / record["path"]).parent / "MANIFEST.json"
            if manifest.is_file():
                add(manifest)
    files = {}
    for number, path in enumerate(sorted(paths)):
        data = path.read_bytes()
        screen(path.relative_to(REPO), data)
        name = os.path.relpath(path, REPO / "disastertrace-starter")
        files[name] = sha(data)
        if number % 2000 == 0:
            print(
                json.dumps({"screened": number + 1, "selected": len(paths)}), flush=True
            )
    record = {
        "schema": "disastertrace.v7.byte_inventory.v1",
        "name": args.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "acceptance_kind": "verified_payload_bytes_not_scientific_task_or_novelty_admission",
        "evidence_sha256": files,
        "gates": {str(path.relative_to(REPO)): digest(path) for path in gates},
        "secrets_detected": 0,
        "model_weights_included": False,
    }
    record["acceptance_id"] = sha(encoded(record))
    inventory = HERE / "inventories" / (args.name + ".json")
    inventory.parent.mkdir(exist_ok=True)
    write(inventory, record)
    output = HERE / "evidence" / args.name
    packed = build(REPO, [str(inventory.relative_to(REPO))], output)
    validation = restore(output, verify_only=True)
    write(
        HERE / "inventories" / (args.name + "_ARCHIVE_CHECK.json"),
        {
            "name": args.name,
            "manifest_sha256": digest(output / "manifest.json"),
            "files": len(packed["files"]),
            "source_bytes": packed["source_bytes"],
            "archive_bytes": packed["archive_bytes"],
            "parts": packed["parts"],
            "validation": validation,
            "full_archive_content_reverified": True,
            "new_model_calls": 0,
            "new_network_requests": 0,
        },
    )
    print(
        json.dumps(
            {
                "name": args.name,
                "files": len(packed["files"]),
                "archive_bytes": packed["archive_bytes"],
                "verified": True,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--kind", choices=["model", "controls", "dataset", "auxiliary"], required=True
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--verification", type=Path)
    main(parser.parse_args())
