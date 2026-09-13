"""Replay the temporal replication from checked ZIP parts in an isolated root."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, write

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
PUBLICATION = REPO / "publication/v7_review_execution_20260912"


def main(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    copied = {}
    for source in (
        BASE / "offline_model_replay.py",
        BASE / "gpu_worker.py",
        PUBLICATION / "evidence_archive.py",
        Path(__file__),
    ):
        destination = root / source.relative_to(REPO)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if digest(destination) != digest(source):
            raise ValueError("Copied replay helper changed")
        copied[str(destination.relative_to(root))] = digest(destination)
    write(root / "SOURCE_BINDINGS.json", copied)
    module_spec = importlib.util.spec_from_file_location(
        "replication_archive", root / PUBLICATION.relative_to(REPO) / "evidence_archive.py"
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    units = ["model_replication_base", "data_replication_2026", "tokenizers"]
    restored = []
    for name in units:
        source = PUBLICATION / "evidence" / name
        checked = PUBLICATION / "inventories" / (name + "_ARCHIVE_CHECK.json")
        if not checked.is_file():
            raise ValueError("Evidence archive lacks a completed content check")
        restored.append({"unit": name, "manifest_sha256": digest(source / "manifest.json"),
                         "check_sha256": digest(checked), "result": module.restore(source, root)})
        print(json.dumps({"restored": name}), flush=True)
    write(root / "RESTORATION.json", restored)
    bundle = root / BASE.relative_to(REPO)
    name = "gpu_replication_primary_base_01"
    command = [
        args.model_python, str(bundle / "offline_model_replay.py"),
        "--batch", str(bundle / name),
        "--validation", str(bundle / (name + "_validation_01")),
        "--evidence", str(bundle / "replication_2026_01/private/OUTCOMES.json"),
        "--tokenizer-root", str(root / PUBLICATION.relative_to(REPO) / "review_tokenizers"),
        "--region", "front_range_2026", "--kind", "F",
        "--deny-project", str(REPO), "--output", str(root / "replay"),
    ]
    started = datetime.now(timezone.utc).isoformat()
    with (root / "REPLAY.log").open("x") as stream:
        result = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                timeout=1800, check=False)
    write(root / "COMMAND.json", {"argv": command, "started_at": started,
          "finished_at": datetime.now(timezone.utc).isoformat(), "returncode": result.returncode})
    if result.returncode:
        raise ValueError("Temporal replication replay failed; inspect preserved logs")
    report = load(root / "replay/validation/REPLAY_REPORT.json")
    if report["replayed_model_calls"] != 5184 or report["new_model_calls"] != 0:
        raise ValueError("Unexpected replay denominator")
    write(root / "COMPLETE.json", {"finished_at": datetime.now(timezone.utc).isoformat(),
          "units": restored, "replayed_model_calls": report["replayed_model_calls"],
          "replayed_tokens": report["replayed_tokens"], "new_model_calls": 0,
          "replay_report_sha256": digest(root / "replay/validation/REPLAY_REPORT.json"),
          "source_bindings_sha256": digest(root / "SOURCE_BINDINGS.json"),
          "environment": "Existing installed dependency environment; not a clean installation",
          "scope": "Actual archive restoration and copied audit with network/original project reads denied; recorded infrastructure receipts, no weights"})
    print(json.dumps({"status": "passed", "replayed_model_calls": 5184, "new_model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-python", required=True)
    main(parser.parse_args())
