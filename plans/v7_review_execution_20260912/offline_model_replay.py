"""Relocate a completed model audit, replaying recorded jobs without API or weights."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent


class ReferencePath:
    def __init__(self, original, actual):
        self.original, self.actual = original, actual

    def __str__(self):
        return self.original

    def __fspath__(self):
        return str(self.actual)

    def resolve(self):
        return self

    def read_text(self):
        return self.actual.read_text()


def prepare(args):
    args.output = args.output.resolve()
    batch = args.batch.resolve()
    recorded = json.loads((args.validation / "VERIFIED.json").read_text())
    plan = json.loads((batch / "PLAN.json").read_text())
    if recorded["plan_sha256"] != digest(batch / "PLAN.json"):
        raise ValueError("Completed audit is for another batch")
    args.output.mkdir(exist_ok=False)
    checkout = args.output / "checkout"
    checkout.mkdir()
    target = checkout / "batch"
    target.mkdir()
    bindings = {}

    def copy(source, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        expected = digest(source)
        if digest(destination) != expected:
            raise ValueError("Relocation changed file bytes")
        bindings[str(destination.relative_to(checkout))] = expected

    # Logs and active observer files are irrelevant to the sealed model trace.
    for path in batch.rglob("*"):
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or path.suffix in {".log", ".pyc"}
        ):
            continue
        copy(path, target / path.relative_to(batch))
    model_map = {}
    for key, spec in plan["models"].items():
        root = checkout / "tokenizers" / key
        supplied_model = (
            args.tokenizer_root / key
            if args.tokenizer_root
            else Path(spec["directory"])
        )
        for item in spec["files"]:
            if item["path"].endswith((".safetensors", ".safetensors.index.json")):
                continue
            source = supplied_model / item["path"]
            if digest(source) != item["sha256"]:
                raise ValueError("Pinned tokenizer/configuration changed")
            copy(source, root / item["path"])
        model_map[spec["directory"]] = str(root.resolve())
    evidence = args.evidence.resolve()
    evidence_sha = digest(evidence)
    matching_bindings = [
        name
        for name, expected in plan["evaluation_bindings"].items()
        if expected == evidence_sha
    ]
    if str(evidence) in plan["evaluation_bindings"]:
        evidence_original = str(evidence)
    elif len(matching_bindings) == 1:
        evidence_original = matching_bindings[0]
    else:
        raise ValueError("Relocated evaluation input has no unique frozen binding")
    if plan["evaluation_bindings"].get(evidence_original) != evidence_sha:
        raise ValueError("Outcome or E-label binding mismatch")
    copy(evidence, checkout / "evaluation.json")
    copy(args.validation / "VERIFIED.json", checkout / "recorded/VERIFIED.json")
    for path in args.validation.glob("JOB*.json"):
        copy(path, checkout / "recorded" / path.name)
    validator_name = "verify_e_probe.py" if args.kind == "E" else "verify_gpu.py"
    copy(args.validation / validator_name, checkout / validator_name)
    copy(BASE / "gpu_worker.py", checkout / "gpu_worker.py")
    copy(Path(__file__), checkout / "offline_model_replay.py")
    save(args.output / "INPUT_BINDINGS.json", bindings)
    save(
        checkout / "RELOCATION.json",
        {
            "model_map": model_map,
            "evidence_original": evidence_original,
            "supplied_evidence": str(evidence),
            "kind": args.kind,
            "region": args.region,
            "original_repository": str(BASE.parents[1]),
            "additional_denied_projects": [
                str(path.resolve()) for path in args.deny_project
            ],
            "recorded_validation_sha256": digest(args.validation / "VERIFIED.json"),
            "source_batch": str(batch),
            "copied_file_count": len(bindings),
            "weights_copied": False,
            "new_model_calls": 0,
        },
    )
    env = dict(
        os.environ,
        PYTHONPATH=str(checkout),
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
    )
    with (args.output / "REPLAY.log").open("x") as log:
        result = subprocess.run(
            [
                sys.executable,
                str(checkout / "offline_model_replay.py"),
                "--worker",
                "--output",
                str(args.output.resolve()),
            ],
            cwd=checkout,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    save(
        args.output / "PROCESS.json",
        {"returncode": result.returncode, "new_model_calls": 0, "api_calls": 0},
    )
    if result.returncode:
        raise ValueError("Relocated replay did not pass; see REPLAY.log")


def worker(args):
    root = Path(__file__).resolve().parent
    relocation = json.loads((root / "RELOCATION.json").read_text())
    recorded = json.loads((root / "recorded/VERIFIED.json").read_text())
    mappings = relocation["model_map"]

    def relocated_path(value):
        text = str(value)
        for original, mapped in mappings.items():
            if text == original or text.startswith(original + "/"):
                return Path(mapped + text[len(original) :])
        return Path(value)

    def deny_network(*_args, **_kwargs):
        raise RuntimeError("Network is disabled during offline replay")

    socket.socket.connect = deny_network
    from transformers import AutoProcessor, AutoTokenizer

    for factory in (AutoTokenizer, AutoProcessor):
        original_loader = factory.from_pretrained

        def loader(_cls, directory, *positional, _original=original_loader, **keyword):
            mapped = relocated_path(directory)
            if not mapped.is_relative_to(root / "tokenizers"):
                raise ValueError(
                    "Tokenizer read outside the copied model configuration"
                )
            return _original(mapped, *positional, **keyword)

        factory.from_pretrained = classmethod(loader)

    job_records = {
        r["name"]: r
        for path in (root / "recorded").glob("JOB*.json")
        for r in [json.loads(path.read_text())]
    }
    replayed_jobs = []

    def recorded_command(argv, **_kwargs):
        if (
            len(argv) < 5
            or argv[1:4] != ["acp", "jobs", "describe"]
            or argv[-1] not in job_records
        ):
            raise ValueError("Unexpected external command during offline replay")
        ident = argv[-1]
        replayed_jobs.append(ident)
        return subprocess.CompletedProcess(argv, 0, json.dumps(job_records[ident]), "")

    subprocess.run = recorded_command

    def audit(event, arguments):
        if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0])).absolute()
            for denied in [
                relocation["original_repository"],
                *relocation.get("additional_denied_projects", []),
            ]:
                old = Path(denied)
                runtime = old / "disastertrace-starter/.venv"
                if (
                    path.is_relative_to(old)
                    and not path.is_relative_to(root)
                    and not path.is_relative_to(runtime)
                    and not path.is_relative_to(args.output.resolve())
                ):
                    raise RuntimeError(
                        "Original project data/code access is disabled: " + str(path)
                    )

    sys.addaudithook(audit)
    name = "verify_e_probe.py" if relocation["kind"] == "E" else "verify_gpu.py"
    spec = importlib.util.spec_from_file_location("sealed_validator", root / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.Path = relocated_path
    original_save = module.save

    def replay_save(path, value):
        if path.name == "VERIFIED.json":
            if (
                value["reports"] != recorded["reports"]
                or value["actual_calls"] != recorded["actual_calls"]
                or value["actual_tokens"] != recorded["actual_tokens"]
            ):
                raise ValueError(
                    "Reconstructed results differ from the completed online audit"
                )
            value = {
                **value,
                "execution_mode": "offline_replay_with_recorded_job_receipts",
                "new_model_calls": 0,
                "new_api_calls": 0,
                "weights_loaded": False,
                "actual_calls": None,
                "actual_tokens": None,
                "replayed_model_calls": recorded["actual_calls"],
                "replayed_tokens": recorded["actual_tokens"],
                "checks": [
                    "Copied frozen file hashes",
                    "Copied tokenizer input/output replay",
                    "Recorded job and hardware receipt identity, no fresh resource lookup",
                    "Original project data/code denied",
                    "Socket network blocked",
                    "Every reconstructed report equals its completed online audit",
                ],
                "relocation": relocation,
                "wrapper_sha256": digest(Path(__file__)),
                "recorded_job_ids_replayed": replayed_jobs,
            }
            path = path.with_name("REPLAY_REPORT.json")
        return original_save(path, value)

    module.save = replay_save
    evidence = ReferencePath(relocation["evidence_original"], root / "evaluation.json")
    namespace = SimpleNamespace(
        batch=root / "batch",
        output=args.output / "validation",
        region=relocation["region"],
    )
    if relocation["kind"] == "E":
        namespace.labels = evidence
    else:
        namespace.outcomes = evidence
    module.main(namespace)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--batch", type=Path)
    parser.add_argument("--validation", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument(
        "--tokenizer-root",
        type=Path,
        help="Directory containing pinned tokenizer/config files under each model key; weights are unnecessary",
    )
    parser.add_argument("--kind", choices=["F", "E"], default="F")
    parser.add_argument("--region", default="bay_area")
    parser.add_argument("--deny-project", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    worker(args) if args.worker else prepare(args)
