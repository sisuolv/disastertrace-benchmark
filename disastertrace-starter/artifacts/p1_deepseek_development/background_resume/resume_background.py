"""Prepare and explicitly authorize one detached continuation of interrupted P1.

Preparation is offline. The original uncertain attempt remains in the cumulative
ledger forever; an authorized amendment permits its single explicit reissue.
"""

from __future__ import annotations

import argparse
import copy
import getpass
import importlib.util
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

from disastertrace.automated.collection import collect_model
from disastertrace.automated.collection_audit import audit_collection
from disastertrace.automated.common import (
    file_hash,
    fingerprint,
    read_jsonl,
    strict_json,
    write_json,
)
from disastertrace.automated.model_workflow import _match_collection_trace
from disastertrace.automated.rescoring import rescore, verify_rescore
from disastertrace.automated.workflow import run, score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNNER_PATH = HERE.parent / "run_experiment.py"
REPORTER_PATH = HERE.parent / "report_results.py"
SPEC = importlib.util.spec_from_file_location("_frozen_p1_resume_dependency", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
FROZEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FROZEN)
AMENDED_BUDGET = {
    **FROZEN.FROZEN_BUDGET,
    "allowance": 1.5,
    "max_provider_requests": 91,
    "max_reserved_output_tokens": 372736,
}


def read_object(path: Path) -> dict:
    value = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("JSON object required")
    return value


def inventory(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("source or prepared package cannot contain symlinks")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = file_hash(path)
    return result


def validate_original(source: Path, episodes: list[dict]) -> tuple[dict, dict]:
    ledger = read_object(source / "budget_ledger.json")
    audit = audit_collection(
        episodes, source / "runs/answer_history/collection", allow_incomplete=True
    )
    if (
        not audit["valid"]
        or audit["safe_to_resume"]
        or not audit["inflight_request"]
        or len(audit["verified_requests"]) != 19
        or len(audit["verified_outcomes"]) != 18
        or len(audit["responses"]) != 18
        or len(read_jsonl(source / "runs/answer_history/collection/responses.jsonl")) != 18
    ):
        raise ValueError("expected original 18-completion prefix and one uncertain request")
    request = audit["verified_requests"][-1]
    rows = ledger["attempts"]
    if (
        len(rows) != 79
        or ledger["provider_attempts_started"] != 79
        or ledger["provider_completions_received"] != 78
        or ledger["active_attempt"] != 79
        or ledger["halted"]
        or not ledger["conditional_budget_assumptions_satisfied"]
        or ledger["budget"] != FROZEN.FROZEN_BUDGET
        or any(row["attempt_number"] != index for index, row in enumerate(rows, 1))
        or any(
            not row["completion_received"] or not row["reservation_released"] for row in rows[:-1]
        )
        or rows[-1]["completion_received"]
        or rows[-1]["reservation_released"]
        or rows[-1]["status"] != "pending"
        or rows[-1]["method"] != "answer_history"
        or rows[-1]["request_sha256"] != request["prepared"]["request_sha256"]
        or request["episode_id"] != "al062018:controlled:delay"
        or request["checkpoint_id"] != "c3"
    ):
        raise ValueError("original pending ledger identity mismatch")
    spent = sum(
        (Decimal(str(row["conservative_reported_cost_usd"])) for row in rows[:-1]), Decimal(0)
    )
    if (
        spent != Decimal("0.30435328")
        or Decimal(str(ledger["conservative_reported_cost_usd"])) != spent
        or Decimal(str(ledger["pending_reservation_usd"])) != Decimal("0.46678016")
        or Decimal(str(rows[-1]["reserved_usd"])) != Decimal("0.46678016")
        or ledger["requested_output_tokens_reserved_total"] != 79 * 4096
    ):
        raise ValueError("original pending ledger budget mismatch")
    observed = []
    for method in FROZEN.METHODS:
        method_audit = audit_collection(
            episodes,
            source / "runs" / method / "collection",
            allow_incomplete=method == "answer_history",
        )
        requests = method_audit["verified_requests"]
        outcomes = method_audit["verified_outcomes"]
        if method != "answer_history" and (len(requests) != 30 or len(outcomes) != 30):
            raise ValueError("completed method is not complete")
        for index, row in enumerate(requests):
            observed.append((method, row["prepared"]["request_sha256"]))
            if index < len(outcomes):
                ledger_row = rows[len(observed) - 1]
                outcome = outcomes[index]
                if (
                    outcome["status"] not in {"accepted", "invalid"}
                    or ledger_row["raw_response_sha256"] != outcome["raw_response_sha256"]
                    or ledger_row["usage"]
                    != {
                        key: outcome["metadata"]["usage"][key]
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                    }
                ):
                    raise ValueError("original completion and ledger binding mismatch")
    if observed != [(row["method"], row["request_sha256"]) for row in rows]:
        raise ValueError("original request and ledger binding mismatch")
    return ledger, audit


def derive_prefix(source: Path, output: Path, episodes: list[dict]) -> dict:
    ledger, original = validate_original(source, episodes)
    if output.exists() or output.is_symlink():
        raise ValueError("prefix output exists")
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("prefix must be outside original files")
    original_collection = source / "runs/answer_history/collection"
    output.mkdir(parents=True)
    for name in ("plan.json", "outcomes.jsonl", "responses.jsonl"):
        shutil.copyfile(original_collection / name, output / name)
    request_bytes = (original_collection / "requests.jsonl").read_bytes().splitlines(keepends=True)
    if len(request_bytes) != 19 or not all(row.endswith(b"\n") for row in request_bytes):
        raise ValueError("original journal requires exactly 19 newline-terminated requests")
    (output / "requests.jsonl").write_bytes(b"".join(request_bytes[:18]))
    summary = read_object(original_collection / "summary.json")
    summary.update(original["counters"])
    summary["attempts_started"] -= 1
    summary["reserved_output_tokens"] -= 4096
    summary["request_bytes_sent"] -= len(
        original["verified_requests"][-1]["prepared"]["raw_request"].encode("utf-8")
    )
    summary.pop("artifact_sha256", None)
    write_json(output / "summary.json", summary)
    prefix = audit_collection(episodes, output, allow_incomplete=True)
    if not prefix["safe_to_resume"] or prefix["counters"]["attempts_started"] != 18:
        raise ValueError("derived prefix failed independent resumption audit")
    if (
        prefix["verified_outcomes"] != original["verified_outcomes"]
        or prefix["responses"] != original["responses"]
    ):
        raise ValueError("received answers or states changed")
    return {
        "original_collection": str(original_collection.resolve()),
        "original_collection_sha256": inventory(original_collection),
        "original_budget_ledger_sha256": file_hash(source / "budget_ledger.json"),
        "original_counters": original["counters"],
        "derived_prefix_counters": prefix["counters"],
        "excluded_request_from_derived_prefix_only": original["verified_requests"][-1],
        "retained_original_global_attempt": copy.deepcopy(ledger["attempts"][-1]),
        "original_incomplete_audit_sha256": fingerprint(original),
        "derived_prefix_audit_sha256": fingerprint(prefix),
        "received_invalid_answers_reused": 4,
        "received_invalid_answers_retried": 0,
        "new_api_calls": 0,
        "interpretation": "The clean prefix is a derived resume input, not the complete historical attempt log. The original pending attempt and its full reservation remain in the cumulative ledger; only an explicit protocol amendment may reissue it once.",
    }


def prepare(experiment: Path, source: Path, output: Path) -> dict:
    manifest, _, episodes = FROZEN.validate_experiment(experiment)
    before = inventory(source)
    if output.exists() or output.is_symlink():
        raise ValueError("prepared package exists")
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("prepared package must be outside original files")
    output.mkdir(parents=True)
    provenance = derive_prefix(source, output / "prefix", episodes)
    write_json(output / "prefix_provenance.json", provenance)
    frozen_files = {
        str(path.resolve()): file_hash(path)
        for path in (
            Path(__file__),
            RUNNER_PATH,
            REPORTER_PATH,
            experiment,
            Path(manifest["provider_config_path"]),
            Path(manifest["rates_path"]),
        )
    }
    amendment = {
        "schema_version": "p1_explicit_background_continuation_v1",
        "status": "prepared_offline_requires_explicit_authorization",
        "created_at": FROZEN._timestamp(),
        "original_experiment_id": manifest["experiment_id"],
        "experiment_path": str(experiment.resolve()),
        "original_source_root": str(source.resolve()),
        "original_source_files_sha256": before,
        "prepared_prefix_path": str((output / "prefix").resolve()),
        "prepared_files_sha256": inventory(output),
        "frozen_files_sha256": frozen_files,
        "budget": copy.deepcopy(AMENDED_BUDGET),
        "original_provider_attempts": 79,
        "original_received_answers": 78,
        "max_additional_provider_attempts": 12,
        "explicit_retry_original_attempt": 79,
        "explicit_retry_request_sha256": provenance["retained_original_global_attempt"][
            "request_sha256"
        ],
        "automatic_retry": False,
        "heldout_calls": 0,
        "new_api_calls_during_preparation": 0,
        "interpretation": "Separate amended continuation; not the original fresh 90-request no-retry experiment. Total expense remains unknown because original attempt 79 has no received usage, even if 90 checkpoint answers are eventually received.",
    }
    amendment["amendment_id"] = fingerprint(amendment)
    if inventory(source) != before:
        raise ValueError("original source changed during preparation")
    write_json(output / "amendment.json", amendment)
    validate_amendment(output / "amendment.json")
    return amendment


def validate_amendment(path: Path) -> tuple[dict, dict, object, list[dict]]:
    amendment = read_object(path)
    if path.parent.resolve() != Path(amendment["prepared_prefix_path"]).parent.resolve():
        raise ValueError("amendment must remain at its bound prepared package location")
    if amendment.get("amendment_id") != fingerprint(
        {k: v for k, v in amendment.items() if k != "amendment_id"}
    ):
        raise ValueError("amendment fingerprint mismatch")
    if (
        amendment["budget"] != AMENDED_BUDGET
        or amendment["max_additional_provider_attempts"] != 12
        or amendment["explicit_retry_original_attempt"] != 79
    ):
        raise ValueError("unsupported amendment scope")
    if str(Path(__file__).resolve()) not in amendment["frozen_files_sha256"]:
        raise ValueError("amendment does not bind this runner")
    for name, expected in amendment["frozen_files_sha256"].items():
        if file_hash(Path(name)) != expected:
            raise ValueError("frozen dependency changed: " + name)
    manifest, config, episodes = FROZEN.validate_experiment(Path(amendment["experiment_path"]))
    if manifest["experiment_id"] != amendment["original_experiment_id"]:
        raise ValueError("original experiment identity mismatch")
    source = Path(amendment["original_source_root"])
    if inventory(source) != amendment["original_source_files_sha256"]:
        raise ValueError("original source files changed")
    for name, expected in amendment["prepared_files_sha256"].items():
        if file_hash(path.parent / name) != expected:
            raise ValueError("prepared prefix or provenance changed")
    ledger, _ = validate_original(source, episodes)
    prefix = audit_collection(
        episodes, Path(amendment["prepared_prefix_path"]), allow_incomplete=True
    )
    if not prefix["safe_to_resume"] or prefix["counters"]["attempts_started"] != 18:
        raise ValueError("prefix is no longer safe to resume")
    if ledger["attempts"][-1]["request_sha256"] != amendment["explicit_retry_request_sha256"]:
        raise ValueError("explicit retry request identity changed")
    return amendment, manifest, config, episodes


def validate_authorization(path: Path, amendment: dict) -> dict:
    authorization = read_object(path)
    expected = {
        "authorized": True,
        "original_experiment_id": amendment["original_experiment_id"],
        "amendment_id": amendment["amendment_id"],
        "allowance_usd": "1.5",
        "max_additional_provider_attempts": 12,
        "max_cumulative_provider_attempts": 91,
        "explicit_retry_original_attempt": 79,
    }
    if any(
        type(authorization.get(k)) is not type(v) or authorization[k] != v
        for k, v in expected.items()
    ):
        raise ValueError("explicit authorization does not match amendment")
    if (
        not isinstance(authorization.get("user_message"), str)
        or not authorization["user_message"].strip()
    ):
        raise ValueError("authorization requires the actual user approval text")
    return authorization


class ContinuationLedger(FROZEN.BudgetLedger):
    """Retain the interrupted reserve while allowing one explicitly approved reissue."""

    def __init__(self, original: dict, path: Path, amendment: dict) -> None:
        self._seeded = False
        self.continuation = {
            "amendment_id": amendment["amendment_id"],
            "original_provider_attempts": 79,
            "original_unresolved_attempts": [79],
            "original_pending_reservation_retained_usd": 0.46678016,
            "explicit_retry_original_attempt": 79,
            "original_global_elapsed_times_have_original_origin": True,
            "new_elapsed_times_have_continuation_origin": True,
        }
        self.retry_sha = amendment["explicit_retry_request_sha256"]
        super().__init__(AMENDED_BUDGET, path, experiment_id=amendment["original_experiment_id"])
        self.rows = copy.deepcopy(original["attempts"])
        self.spent = Decimal(str(original["conservative_reported_cost_usd"]))
        self.pending = Decimal(str(original["pending_reservation_usd"]))
        self.reserved_output_total = original["requested_output_tokens_reserved_total"]
        self.denials = original["guard_denials_before_provider"]
        self.active = None
        self._seeded = True
        self._save()

    def _save(self) -> None:
        if self._seeded:
            super()._save()

    def snapshot(self) -> dict:
        return {**super().snapshot(), "continuation": copy.deepcopy(self.continuation)}

    def reserve(self, prepared: dict, method: str, config: object) -> int:
        if method != "answer_history":
            self._deny("continuation_method_mismatch")
        if len(self.rows) == 79 and prepared["request_sha256"] != self.retry_sha:
            self._deny("explicit_retry_request_mismatch")
        return super().reserve(prepared, method, config)


def finalize_collection(manifest: dict, output: Path, episodes: list[dict]) -> dict:
    collection = read_object(output / "collection/summary.json")
    audit = audit_collection(episodes, output / "collection")
    write_json(output / "collection_audit.json", audit)
    context = read_object(output / "build_context.json")
    build = Path(manifest["build_path"])
    imported = run(
        build,
        output / "imported_run",
        track="dynamic",
        backend="submissions",
        predictions_path=output / "collection/responses.jsonl",
        max_queries=30,
        split="development",
        method="answer_history",
        group_ids=manifest["development_event_ids"],
    )
    traces = read_jsonl(output / "imported_run/trace.jsonl")
    _match_collection_trace(audit, traces)
    if len(traces) != 30 or imported["live_model_calls"] != 0:
        raise ValueError("offline import lost scoring opportunities")
    imported["collection_binding"] = {
        "relative_path": "../collection",
        "audit_sha256": fingerprint(audit),
        "artifact_sha256": {
            p.name: file_hash(p) for p in sorted((output / "collection").iterdir()) if p.is_file()
        },
    }
    write_json(output / "imported_run/run.json", imported)
    scored = score(build, output / "imported_run", output / "score.json")
    result = {
        **context,
        "collection": collection,
        "collection_audit_sha256": fingerprint(audit),
        "offline_import": imported,
        "metrics": scored["metrics"],
        "interpretation": "Explicitly amended continuation reuses the 18 received prefix answers, including invalid answers, and preserves all 30 scoring opportunities. Cumulative original plus resumed attempt accounting is external.",
    }
    write_json(output / "result.json", result)
    return result


def execute(amendment_path: Path, output: Path, *, transport=None) -> dict:
    amendment, manifest, config, episodes = validate_amendment(amendment_path)
    source = Path(amendment["original_source_root"])
    original, _ = validate_original(source, episodes)
    ledger = ContinuationLedger(original, output / "budget_ledger.json", amendment)
    for method in ("snapshot", "structured_state"):
        for dirname in ("runs", "rescores"):
            target = output / dirname / method
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source / dirname / method, target_is_directory=True)
    method_output = output / "runs/answer_history"
    method_output.mkdir()
    shutil.copyfile(
        source / "runs/answer_history/build_context.json", method_output / "build_context.json"
    )
    client = FROZEN.BudgetedClient(config, ledger, method="answer_history", transport=transport)
    # Offline injected transports exercise the exact resume contract without HTTP.
    if transport is not None:
        client.transport_kind = "urllib_http_with_external_budget_guard"
    validate_amendment(amendment_path)
    collection = collect_model(
        episodes,
        config,
        method_output / "collection",
        max_queries=30,
        client=client,
        method="answer_history",
        resume_from=Path(amendment["prepared_prefix_path"]),
        max_request_bytes=262144,
        max_reserved_output_tokens=122880,
    )
    print("Continuation collection finished: " + collection["status"], flush=True)
    validate_amendment(amendment_path)
    result = finalize_collection(manifest, method_output, episodes)
    derived = output / "rescores/answer_history"
    rescore(
        Path(manifest["build_path"]),
        method_output / "imported_run",
        derived,
        historical_score=method_output / "score.json",
    )
    verification = verify_rescore(derived)
    validate_amendment(amendment_path)
    if ledger.rows[:79] != original["attempts"]:
        raise ValueError("historical ledger rows changed")
    if ledger.pending < Decimal("0.46678016"):
        raise ValueError("uncertain original reservation was released")
    final = {
        "schema_version": "p1_amended_continuation_execution_v1",
        "amendment_id": amendment["amendment_id"],
        "status": "completed" if collection["status"] == "completed" else "stopped",
        "finished_at": FROZEN._timestamp(),
        "new_provider_attempts": len(ledger.rows) - 79,
        "cumulative_provider_attempts": len(ledger.rows),
        "cumulative_completions_received": ledger.snapshot()["provider_completions_received"],
        "original_uncertain_attempts": 1,
        "original_pending_reservation_usd": 0.46678016,
        "actual_total_cost_usd": None,
        "full_three_method_scoring_opportunities": 90,
        "original_source_files_unchanged": True,
        "collection": result["collection"],
        "rescore_verification": verification,
        "injected_offline_transport": transport is not None,
        "interpretation": amendment["interpretation"],
    }
    write_json(output / "execution.json", final)
    return final


def launch(amendment_path: Path, authorization_path: Path, output: Path) -> dict:
    amendment, _, config, _ = validate_amendment(amendment_path)
    authorization = validate_authorization(authorization_path, amendment)
    if output.exists() or output.is_symlink():
        raise ValueError("background output exists; automatic relaunch is prohibited")
    claim_path = amendment_path.parent / "launch_claim.json"
    if claim_path.exists():
        raise ValueError("amendment already claimed; a second output cannot reuse its budget")
    if output.resolve().is_relative_to(Path(amendment["original_source_root"])):
        raise ValueError("background output must be outside original experiment")
    secret = os.environ.get(config.key_env) or getpass.getpass("DeepSeek API key (not stored): ")
    if not secret or any(ord(c) < 33 or ord(c) > 126 for c in secret):
        raise ValueError("missing or invalid credential")
    claim = {
        "amendment_id": amendment["amendment_id"],
        "output_path": str(output.resolve()),
        "authorization_sha256": file_hash(authorization_path),
        "created_at": FROZEN._timestamp(),
    }
    with claim_path.open("x", encoding="ascii") as stream:
        stream.write(FROZEN.canonical(claim) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    output.mkdir(parents=True)
    shutil.copyfile(authorization_path, output / "authorization.json")
    shutil.copyfile(amendment_path, output / "amendment_snapshot.json")
    launch_record = {
        "amendment_id": amendment["amendment_id"],
        "authorization_path": str(authorization_path.resolve()),
        "authorization_sha256": file_hash(authorization_path),
        "authorization_snapshot_sha256": fingerprint(authorization),
        "created_at": FROZEN._timestamp(),
        "credential_persisted": False,
        "automatic_relaunch": False,
    }
    write_json(output / "launch.json", launch_record)
    environment = dict(os.environ)
    environment[config.key_env] = secret
    try:
        with (output / "worker.log").open("xb") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "worker",
                    "--amendment",
                    str(amendment_path.resolve()),
                    "--output",
                    str(output.resolve()),
                ],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
    finally:
        environment.pop(config.key_env, None)
        secret = None
    launch_record.update(pid=process.pid)
    write_json(output / "launch.json", launch_record)
    write_json(
        output / "pid.json",
        {"pid": process.pid, "recorded_at": FROZEN._timestamp(), "start_new_session": True},
    )
    return launch_record


def worker(amendment_path: Path, output: Path) -> int:
    # The exclusive marker prevents duplicate child execution, even after a crash.
    with (output / "worker_started.json").open("x", encoding="ascii") as stream:
        stream.write('{"pid":' + str(os.getpid()) + "}\n")
        stream.flush()
        os.fsync(stream.fileno())
    status = {"pid": os.getpid(), "status": "running", "started_at": FROZEN._timestamp()}
    write_json(output / "status.json", status)
    code = 1
    try:
        amendment, _, _, _ = validate_amendment(amendment_path)
        record = read_object(output / "launch.json")
        claim = read_object(amendment_path.parent / "launch_claim.json")
        if (
            claim["amendment_id"] != amendment["amendment_id"]
            or claim["output_path"] != str(output.resolve())
            or claim["authorization_sha256"] != record["authorization_sha256"]
        ):
            raise ValueError("worker does not match exclusive amendment launch claim")
        snapshot = output / "authorization.json"
        authorization = validate_authorization(snapshot, amendment)
        if (
            file_hash(snapshot) != record["authorization_sha256"]
            or fingerprint(authorization) != record["authorization_snapshot_sha256"]
            or file_hash(output / "amendment_snapshot.json") != file_hash(amendment_path)
        ):
            raise ValueError("launch authorization or amendment changed")
        result = execute(amendment_path, output)
        status["status"] = result["status"]
        code = 0 if result["status"] == "completed" else 2
    except BaseException as error:  # noqa: BLE001 - persist sanitized exit for every failure
        status.update(status="failed", error_type=type(error).__name__)
        print("Continuation failed; sanitized error type: " + type(error).__name__, flush=True)
    finally:
        status.update(exit_code=code, finished_at=FROZEN._timestamp())
        write_json(output / "status.json", status)
        write_json(output / "exit.json", {"exit_code": code, "finished_at": status["finished_at"]})
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--experiment", type=Path, required=True)
    prepare_parser.add_argument("--source", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    for name in ("launch", "worker"):
        child = sub.add_parser(name)
        child.add_argument("--amendment", type=Path, required=True)
        child.add_argument("--output", type=Path, required=True)
        if name == "launch":
            child.add_argument("--authorization", type=Path, required=True)
            child.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.experiment, args.source, args.output)
        print("Prepared offline amendment " + result["amendment_id"])
    elif args.command == "launch":
        result = launch(args.amendment, args.authorization, args.output)
        print("Detached continuation submitted; PID " + str(result["pid"]))
    else:
        raise SystemExit(worker(args.amendment, args.output))


if __name__ == "__main__":
    main()
