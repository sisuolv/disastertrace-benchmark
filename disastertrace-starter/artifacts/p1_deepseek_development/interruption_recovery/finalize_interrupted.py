"""Finalize one interrupted P1 collection offline without reissuing its pending call.

The original files and budget ledger remain unchanged. A derived collection gets
one explicitly administrative error disposition; this is not a provider response.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.collection_audit import ARTIFACTS, audit_collection
from disastertrace.automated.common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    strict_json,
    write_json,
)
from disastertrace.automated.model_workflow import _match_collection_trace
from disastertrace.automated.rescoring import rescore, verify_rescore
from disastertrace.automated.workflow import run, score

ERROR_CODE = "offline_finalized_interrupted_attempt"


def tree_hashes(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("input/output trees must not contain symlinks")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = file_hash(path)
    return result


def read_object(path: Path) -> dict:
    result = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def administrative_outcome(audit: dict) -> dict:
    if not audit["valid"] or not audit["inflight_request"] or audit["safe_to_resume"]:
        raise ValueError("one audited uncertain in-flight attempt required")
    requests = audit["verified_requests"]
    outcomes = audit["verified_outcomes"]
    if len(requests) != len(outcomes) + 1:
        raise ValueError("exactly one unresolved request required")
    request = requests[-1]
    previous = None
    if outcomes and outcomes[-1]["episode_id"] == request["episode_id"]:
        previous = copy.deepcopy(outcomes[-1]["state_after"])
    return {
        "episode_id": request["episode_id"],
        "checkpoint_id": request["checkpoint_id"],
        "request_sha256": request["prepared"]["request_sha256"],
        "status": "provider_error",
        "error": {
            "code": ERROR_CODE,
            "status": None,
            "request_may_have_reached_provider": True,
            "automatic_retry": False,
        },
        "state_after": previous,
    }


def derive_collection(
    source: Path, output: Path, episodes: list[dict], *, ledger_path: Path
) -> tuple[dict, dict]:
    before = tree_hashes(source)
    ledger_hash = file_hash(ledger_path)
    audit = audit_collection(episodes, source, allow_incomplete=True)
    outcome = administrative_outcome(audit)
    if len(read_jsonl(source / "responses.jsonl")) != len(audit["responses"]):
        raise ValueError("orphan raw completion cannot be discarded or fabricated into metadata")
    ledger = read_object(ledger_path)
    pending = ledger["attempts"][-1]
    if (
        ledger["active_attempt"] != pending["attempt_number"]
        or pending["request_sha256"] != outcome["request_sha256"]
        or pending["method"] != "answer_history"
        or pending["completion_received"]
        or pending["status"] != "pending"
        or pending["reservation_released"]
        or ledger["pending_reservation_usd"] <= 0
    ):
        raise ValueError("original ledger does not identify this unresolved pending call")
    if output.exists() or output.is_symlink():
        raise ValueError("derived collection already exists")
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("derived collection must be outside the original")
    shutil.copytree(source, output)
    original_outcomes = (source / "outcomes.jsonl").read_bytes()
    if original_outcomes and not original_outcomes.endswith(b"\n"):
        raise ValueError("original outcome journal must end in a newline")
    with (output / "outcomes.jsonl").open("ab") as stream:
        stream.write((canonical(outcome) + "\n").encode("utf-8"))
    summary = read_object(source / "summary.json")
    summary.update(audit["counters"])
    summary.update(
        status="provider_error",
        stop_error=outcome["error"],
        stop_guard=None,
        artifact_sha256={name: file_hash(output / name) for name in ARTIFACTS},
    )
    write_json(output / "summary.json", summary)
    provenance = {
        "schema_version": "p1_offline_interruption_disposition_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_collection_path": str(source.resolve()),
        "original_collection_files": before,
        "original_incomplete_audit_sha256": fingerprint(audit),
        "original_budget_ledger_path": str(ledger_path.resolve()),
        "original_budget_ledger_sha256": ledger_hash,
        "original_budget_ledger_changed": False,
        "pending_reservation_usd": ledger["pending_reservation_usd"],
        "source_global_attempt_number": pending["attempt_number"],
        "new_provider_calls": 0,
        "new_provider_responses": 0,
        "automatic_retry": False,
        "administrative_outcome": outcome,
        "provider_returned_error": False,
        "preserved_verbatim": ["plan.json", "requests.jsonl", "responses.jsonl"],
        "interpretation": (
            "The original process no longer exists, while its last provider attempt has "
            "no saved completion. The appended provider_error is the existing collector "
            "schema's local administrative disposition, not a received HTTP error or "
            "model answer. Provider receipt, completion and billing remain uncertain. "
            "The request is never retried, its reservation is not released, all original "
            "requests and responses remain verbatim, and all planned scoring slots remain."
        ),
    }
    write_json(output / "interruption_finalization.json", provenance)
    final_audit = audit_collection(episodes, output)
    if final_audit["counters"] != audit["counters"]:
        raise ValueError("offline finalization changed actual collection counters")
    for name in provenance["preserved_verbatim"]:
        if file_hash(output / name) != before[name]:
            raise ValueError("original public request/response changed")
    if not (output / "outcomes.jsonl").read_bytes().startswith(original_outcomes):
        raise ValueError("original outcomes changed")
    if tree_hashes(source) != before or file_hash(ledger_path) != ledger_hash:
        raise ValueError("original collection or budget ledger changed")
    return audit, final_audit


def finalize(experiment: Path, source_root: Path, output_root: Path) -> dict:
    runner_path = experiment.parent / "run_experiment.py"
    spec = importlib.util.spec_from_file_location("_frozen_p1_runner", runner_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen runner for manifest validation")
    frozen_runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen_runner)
    manifest, config, episodes = frozen_runner.validate_experiment(experiment)
    source_inventory = tree_hashes(source_root)
    source = source_root / "runs/answer_history"
    output = output_root / "runs/answer_history"
    rescore_path = output_root / "rescores/answer_history"
    if output_root.resolve().is_relative_to(
        source_root.resolve()
    ) or output_root.resolve().is_relative_to(Path(manifest["build_path"]).resolve()):
        raise ValueError("offline output must be outside original inputs")
    if output.exists() or rescore_path.exists():
        raise ValueError("derived answer_history output already exists")
    output.mkdir(parents=True)
    shutil.copyfile(source / "build_context.json", output / "build_context.json")
    original_audit, audit = derive_collection(
        source / "collection",
        output / "collection",
        episodes,
        ledger_path=source_root / "budget_ledger.json",
    )
    write_json(output / "original_incomplete_audit.json", original_audit)
    write_json(output / "collection_audit.json", audit)
    context = read_object(output / "build_context.json")
    build = Path(manifest["build_path"])
    imported = run(
        build,
        output / "imported_run",
        track="dynamic",
        backend="submissions",
        predictions_path=output / "collection/responses.jsonl",
        max_queries=context["max_queries"],
        split="development",
        method="answer_history",
        group_ids=manifest["development_event_ids"],
    )
    traces = read_jsonl(output / "imported_run/trace.jsonl")
    _match_collection_trace(audit, traces)
    if len(traces) != 30 or imported["live_model_calls"] != 0:
        raise ValueError("offline scoring must retain the original 30 opportunities")
    imported["collection_binding"] = {
        "relative_path": "../collection",
        "audit_sha256": fingerprint(audit),
        "artifact_sha256": {
            path.name: file_hash(path)
            for path in sorted((output / "collection").iterdir())
            if path.is_file()
        },
    }
    write_json(output / "imported_run/run.json", imported)
    scored = score(build, output / "imported_run", output / "score.json")
    result = {
        **context,
        "collection": read_object(output / "collection/summary.json"),
        "collection_audit_sha256": fingerprint(audit),
        "offline_import": imported,
        "metrics": scored["metrics"],
        "interpretation": (
            "Offline import of preserved responses after local interruption disposition; "
            "19 historical provider attempts, 18 responses, no new calls, full 30 slots."
        ),
    }
    write_json(output / "result.json", result)
    rescored = rescore(
        build, output / "imported_run", rescore_path, historical_score=output / "score.json"
    )
    verification = verify_rescore(rescore_path)
    if tree_hashes(source_root) != source_inventory:
        raise ValueError("original experiment artifacts changed")
    if frozen_runner.validate_experiment(experiment) != (manifest, config, episodes):
        raise ValueError("frozen experiment changed during offline finalization")
    final = {
        "schema_version": "p1_offline_interruption_finalization_v1",
        "experiment_id": manifest["experiment_id"],
        "script_sha256": file_hash(Path(__file__)),
        "source_root": str(source_root.resolve()),
        "source_files_sha256": source_inventory,
        "source_files_unchanged": True,
        "new_provider_calls": 0,
        "planned_checkpoints": len(traces),
        "attempts_started": audit["counters"]["attempts_started"],
        "completions_received": audit["counters"]["completions_received"],
        "accepted_decisions": audit["counters"]["accepted_decisions"],
        "invalid_decisions": audit["counters"]["invalid_decisions"],
        "unsubmitted_checkpoints": audit["counters"]["unsubmitted_checkpoints"],
        "uncertain_attempts": 1,
        "never_attempted_checkpoints": len(traces) - audit["counters"]["attempts_started"],
        "rescore_id": rescored["rescore_id"],
        "rescore_verification": verification,
    }
    write_json(output / "finalization.json", final)
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    def deny_network(event: str, arguments: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            raise RuntimeError("network is forbidden during offline interruption finalization")

    sys.addaudithook(deny_network)
    result = finalize(
        args.experiment.resolve(), args.source_root.resolve(), args.output_root.resolve()
    )
    print(json.dumps({key: value for key, value in result.items() if key != "source_files_sha256"}))


if __name__ == "__main__":
    main()
