"""Execute the frozen P1 development matrix with a shared conditional USD guard.

The standard collector remains unchanged. Its audit/import/scoring sequence is
composed here with one externally guarded ProviderClient and immutable v2 scores.
The guard assumes the frozen peak rates and provider context/output limits hold;
it is not a provider billing cap or a guarantee about the account's debit.
Valid provider envelopes retain model answers even when their answer JSON is
invalid. Invalid provider envelopes, including malformed usage, are rejected by
the unchanged provider parser: their sanitized error and pending reservation are
retained, but the rejected raw envelope is not available to this wrapper.
"""

from __future__ import annotations

import argparse
import copy
import getpass
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from disastertrace.automated.collection import collect_model
from disastertrace.automated.collection_audit import audit_collection
from disastertrace.automated.common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    strict_json,
    write_json,
)
from disastertrace.automated.evidence_support import EVIDENCE_POLICY_VERSION
from disastertrace.automated.methods import method_contract
from disastertrace.automated.model_workflow import _match_collection_trace
from disastertrace.automated.provider import (
    ProviderClient,
    ProviderConfig,
    ProviderError,
    Transport,
)
from disastertrace.automated.rescoring import rescore, verify_rescore
from disastertrace.automated.scoring_v2 import SCORER_VERSION
from disastertrace.automated.workflow import (
    _require_implementation,
    run,
    score,
    selected_episodes,
    verify_build,
)

METHODS = ("snapshot", "structured_state", "answer_history")
EVENTS = ("AL092021", "AL062018", "AL052019")
FROZEN_BUDGET = {
    "currency": "USD",
    "allowance": 1.0,
    "prompt_reservation_tokens": 1048576,
    "peak_input_per_million": 0.44,
    "peak_output_per_million": 1.32,
    "max_provider_requests": 90,
    "max_reserved_output_tokens": 368640,
    "max_request_bytes": 262144,
}


def _read(path: Path) -> dict:
    value = strict_json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _money(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid budget amount") from None
    if not result.is_finite() or result < 0:
        raise ValueError("budget amount must be nonnegative and finite")
    return result


class BudgetLedger:
    """Durable shared guard; at most one unresolved provider call is permitted."""

    def __init__(self, budget: dict, path: Path, *, experiment_id: str) -> None:
        if not isinstance(budget, dict) or set(budget) != set(FROZEN_BUDGET):
            raise ValueError("budget requires exactly the documented fields")
        if budget["currency"] != "USD":
            raise ValueError("budget currency must be USD")
        for name in (
            "prompt_reservation_tokens",
            "max_provider_requests",
            "max_reserved_output_tokens",
            "max_request_bytes",
        ):
            if type(budget[name]) is not int or budget[name] < 0:
                raise ValueError("budget limits must be nonnegative integers")
        self.budget = copy.deepcopy(budget)
        self.path = Path(path)
        if self.path.exists():
            raise ValueError("budget ledger output exists")
        self.allowance = _money(budget["allowance"])
        self.input_rate = _money(budget["peak_input_per_million"])
        self.output_rate = _money(budget["peak_output_per_million"])
        self.spent = Decimal(0)
        self.pending = Decimal(0)
        self.halted = False
        self.halt_reason = None
        self.active = None
        self.rows = []
        self.denials = 0
        self.reserved_output_total = 0
        self.assumptions_satisfied = True
        self.experiment_id = experiment_id
        self.started = time.monotonic()
        self.started_at = _timestamp()
        self._save()

    def snapshot(self) -> dict:
        return {
            "schema_version": "p1_conditional_budget_ledger_v1",
            "experiment_id": self.experiment_id,
            "budget": copy.deepcopy(self.budget),
            "started_at": self.started_at,
            "updated_at": _timestamp(),
            "elapsed_seconds": time.monotonic() - self.started,
            "provider_attempts_started": len(self.rows),
            "provider_completions_received": sum(row["completion_received"] for row in self.rows),
            "guard_denials_before_provider": self.denials,
            "requested_output_tokens_reserved_total": self.reserved_output_total,
            "conservative_reported_cost_usd": float(self.spent),
            "pending_reservation_usd": float(self.pending),
            "spent_plus_pending_usd": float(self.spent + self.pending),
            "allowance_remaining_after_reservations_usd": float(
                self.allowance - self.spent - self.pending
            ),
            "conditional_budget_assumptions_satisfied": self.assumptions_satisfied,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "active_attempt": self.active,
            "attempts": copy.deepcopy(self.rows),
            "automatic_retry": False,
            "conditional_usd_request_admission_guard": True,
            "monetary_cap_enforced": False,
            "billing_guarantee": False,
            "interpretation": (
                "Attempts count calls admitted immediately before ProviderClient.complete; "
                "provider receipt is not authenticated. Every request reserves the entire "
                "declared prompt context and requested output at frozen peak cache-miss "
                "rates. Valid reported usage is charged at those rates, including cached "
                "prompt tokens as misses. Missing/invalid usage and uncertain errors retain "
                "their reservation and stop the batch. Provider limit/rate compliance is "
                "an assumption, not an account-level billing guarantee."
            ),
        }

    def _save(self) -> None:
        write_json(self.path, self.snapshot())

    def halt(self, reason: str) -> None:
        if not self.halted:
            self.halted = True
            self.halt_reason = reason
        self._save()

    def _deny(self, reason: str) -> None:
        self.denials += 1
        self.halt(reason)
        raise ProviderError(reason, request_may_have_reached_provider=False)

    def reserve(self, prepared: dict, method: str, config: ProviderConfig) -> int:
        if self.halted:
            self._deny("external_budget_halted")
        if self.active is not None:
            self._deny("external_budget_pending_attempt")
        if len(self.rows) >= self.budget["max_provider_requests"]:
            self._deny("external_budget_request_limit")
        if (
            self.reserved_output_total + config.max_output_tokens
            > self.budget["max_reserved_output_tokens"]
        ):
            self._deny("external_budget_output_reservation_limit")
        request_bytes = len(prepared["raw_request"].encode("utf-8"))
        if request_bytes > self.budget["max_request_bytes"]:
            self._deny("external_budget_request_bytes")
        reservation = (
            self.budget["prompt_reservation_tokens"] * self.input_rate
            + config.max_output_tokens * self.output_rate
        ) / Decimal(1000000)
        if self.spent + self.pending + reservation > self.allowance:
            self._deny("external_budget_allowance_exhausted")
        attempt = len(self.rows) + 1
        self.pending += reservation
        self.reserved_output_total += config.max_output_tokens
        self.active = attempt
        self.rows.append(
            {
                "attempt_number": attempt,
                "method": method,
                "request_sha256": prepared["request_sha256"],
                "request_bytes": request_bytes,
                "requested_output_tokens": config.max_output_tokens,
                "reserved_usd": float(reservation),
                "reservation_released": False,
                "started_at": _timestamp(),
                "elapsed_at_start": time.monotonic() - self.started,
                "status": "pending",
                "completion_received": False,
                "request_may_have_reached_provider": True,
            }
        )
        self._save()
        return attempt

    def _release(self, row: dict) -> None:
        if not row["reservation_released"]:
            self.pending -= Decimal(str(row["reserved_usd"]))
            row["reservation_released"] = True

    def record_error(self, attempt: int, error: ProviderError) -> None:
        row = self.rows[attempt - 1]
        row.update(
            status="provider_error",
            finished_at=_timestamp(),
            error=error.as_dict(),
            request_may_have_reached_provider=error.request_may_have_reached_provider,
        )
        if not error.request_may_have_reached_provider:
            self._release(row)
        self.active = None
        self.halt("provider_error_" + error.code)

    def record_completion(self, attempt: int, completion: dict, config: ProviderConfig) -> None:
        row = self.rows[attempt - 1]
        metadata = completion["metadata"]
        row.update(
            status="completion_received",
            completion_received=True,
            finished_at=_timestamp(),
            response_model=metadata["response_model"],
            raw_response_sha256=fingerprint(completion["raw_response"]),
            provider_elapsed_seconds=metadata["elapsed_seconds"],
        )
        self.active = None
        if metadata["response_model"] != config.model:
            self.assumptions_satisfied = False
        usage = metadata.get("usage")
        valid_usage = isinstance(usage, dict) and all(
            type(usage.get(key)) is int and usage[key] >= 0
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        if valid_usage:
            valid_usage = (
                usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
            )
        if not valid_usage:
            row["usage_verified"] = False
            self.halt("missing_usage" if usage is None else "invalid_usage")
            return
        row["usage_verified"] = True
        row["usage"] = {
            name: usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        if metadata["response_model"] != config.model:
            self.assumptions_satisfied = False
            row["conservative_reported_cost_usd"] = None
            self.halt("reported_model_mismatch")
            return
        charge = (
            usage["prompt_tokens"] * self.input_rate + usage["completion_tokens"] * self.output_rate
        ) / Decimal(1000000)
        row["conservative_reported_cost_usd"] = float(charge)
        self.spent += charge
        # A limit breach falsifies the reservation assumption; retain its reserve
        # as well as the reported charge, then stop after preserving the answer.
        if usage["prompt_tokens"] > self.budget["prompt_reservation_tokens"]:
            self.assumptions_satisfied = False
            self.halt("reported_prompt_cap_exceeded")
        elif usage["completion_tokens"] > config.max_output_tokens:
            self.assumptions_satisfied = False
            self.halt("reported_output_cap_exceeded")
        else:
            self._release(row)
            if self.spent > self.allowance:
                self.assumptions_satisfied = False
                self.halt("reported_cost_exceeded_allowance")
        self._save()


class BudgetedClient(ProviderClient):
    def __init__(
        self,
        config: ProviderConfig,
        ledger: BudgetLedger,
        *,
        method: str,
        transport: Transport | None = None,
    ) -> None:
        super().__init__(config, transport=transport)
        self.ledger = ledger
        self.method = method
        self.transport_kind = (
            "urllib_http_with_external_budget_guard"
            if transport is None
            else "injected_transport_with_external_budget_guard_unverified"
        )

    def complete(self, request: dict) -> dict:
        prepared = self.prepare(request)
        if self.config.key_env is not None:
            secret = os.environ.get(self.config.key_env)
            if not secret:
                raise ProviderError("missing_credential")
            if any(ord(char) < 33 or ord(char) > 126 for char in secret):
                raise ProviderError("invalid_credential")
        attempt = self.ledger.reserve(prepared, self.method, self.config)
        try:
            completion = super().complete(request)
        except ProviderError as error:
            self.ledger.record_error(attempt, error)
            raise
        except Exception:
            error = ProviderError("unexpected_client_error", request_may_have_reached_provider=True)
            self.ledger.record_error(attempt, error)
            raise error from None
        self.ledger.record_completion(attempt, completion, self.config)
        return completion


def validate_experiment(path: Path) -> tuple[dict, ProviderConfig, list[dict]]:
    manifest = _read(path)
    identity = {key: value for key, value in manifest.items() if key != "experiment_id"}
    if manifest.get("experiment_id") != fingerprint(identity):
        raise ValueError("experiment manifest fingerprint mismatch")
    if manifest.get("runner_sha256") != file_hash(Path(__file__)):
        raise ValueError("runner source hash mismatch")
    if manifest.get("methods") != list(METHODS):
        raise ValueError("frozen method order mismatch")
    for name, expected in (
        ("expected_requests_per_method", 30),
        ("repeats", 1),
        ("total_requests", 90),
    ):
        if type(manifest.get(name)) is not int or manifest[name] != expected:
            raise ValueError("frozen matrix size mismatch: " + name)
    if manifest.get("development_event_ids") != list(EVENTS):
        raise ValueError("frozen development event order mismatch")
    if manifest.get("budget") != FROZEN_BUDGET:
        raise ValueError("frozen shared budget mismatch")
    if (
        manifest.get("scorer_version") != SCORER_VERSION
        or manifest.get("evidence_policy_version") != EVIDENCE_POLICY_VERSION
    ):
        raise ValueError("frozen scorer version mismatch")
    for name in ("build_path", "provider_config_path", "rates_path"):
        if not isinstance(manifest.get(name), str) or not Path(manifest[name]).is_absolute():
            raise ValueError("experiment requires absolute input paths")
    build_path = Path(manifest["build_path"])
    config_path = Path(manifest["provider_config_path"])
    rates_path = Path(manifest["rates_path"])
    if file_hash(config_path) != manifest.get("provider_config_sha256"):
        raise ValueError("provider configuration file hash mismatch")
    if file_hash(rates_path) != manifest.get("rates_sha256"):
        raise ValueError("price evidence file hash mismatch")
    config = ProviderConfig.from_dict(_read(config_path))
    if (
        config.model != "deepseek-v4-flash"
        or config.base_url != "https://api.deepseek.com"
        or config.key_env != "DEEPSEEK_API_KEY"
        or config.max_output_tokens != 4096
        or config.token_parameter != "max_tokens"
        or config.temperature is not None
        or config.timeout != 60
        or config.reasoning_effort != "high"
        or config.thinking_type != "enabled"
    ):
        raise ValueError("provider differs from frozen P1 configuration")
    checked_build = verify_build(build_path)
    implementation = _require_implementation(build_path)
    if checked_build["build_id"] != manifest.get("build_id"):
        raise ValueError("build identity mismatch")
    if implementation["implementation_id"] != manifest.get("implementation_id"):
        raise ValueError("implementation identity mismatch")
    episodes = selected_episodes(build_path, "development", group_ids=list(EVENTS))
    if len(episodes) != 6 or list(dict.fromkeys(ep["group_id"] for ep in episodes)) != list(EVENTS):
        raise ValueError("unexpected development episode order")
    if any(
        sum(len(ep["checkpoints"]) for ep in episodes if ep["group_id"] == group) != 10
        for group in EVENTS
    ):
        raise ValueError("each development event requires ten checkpoints")
    checkpoints = [
        {"episode_id": ep["episode_id"], "checkpoint_id": cp["checkpoint_id"]}
        for ep in episodes
        for cp in ep["checkpoints"]
    ]
    if len(checkpoints) != 30 or len({tuple(row.values()) for row in checkpoints}) != 30:
        raise ValueError("development checkpoint count or uniqueness mismatch")
    expected_checkpoint_hash = manifest.get("expected_checkpointkeys_sha256")
    if expected_checkpoint_hash is not None and expected_checkpoint_hash != fingerprint(
        checkpoints
    ):
        raise ValueError("development checkpoint identity hash mismatch")
    return manifest, config, episodes


def _collect_method(
    manifest: dict,
    config: ProviderConfig,
    episodes: list[dict],
    output: Path,
    *,
    method: str,
    max_queries: int,
    client: ProviderClient,
) -> dict:
    build_path = Path(manifest["build_path"])
    verify_build(build_path)
    _require_implementation(build_path)
    if output.exists():
        raise ValueError("model collection output exists; choose a new path")
    output.mkdir(parents=True)
    budget = manifest["budget"]
    context = {
        "schema_version": "model_collection_build_v1",
        "build_id": manifest["build_id"],
        "implementation_id": manifest["implementation_id"],
        "split": "development",
        "method": method,
        "method_contract": method_contract(method),
        "group_ids": manifest["development_event_ids"],
        "selected_episode_ids": [ep["episode_id"] for ep in episodes],
        "provider_config_sha256": manifest["provider_config_sha256"],
        "max_queries": max_queries,
        "max_request_bytes": budget["max_request_bytes"],
        "max_reserved_output_tokens": max_queries * config.max_output_tokens,
        "eligible_for_llm_leaderboard": False,
    }
    write_json(output / "build_context.json", context)
    collection = collect_model(
        episodes,
        config,
        output / "collection",
        max_queries=max_queries,
        client=client,
        method=method,
        max_request_bytes=context["max_request_bytes"],
        max_reserved_output_tokens=context["max_reserved_output_tokens"],
    )
    audit = audit_collection(episodes, output / "collection")
    write_json(output / "collection_audit.json", audit)
    imported = run(
        build_path,
        output / "imported_run",
        track="dynamic",
        backend="submissions",
        predictions_path=output / "collection/responses.jsonl",
        max_queries=max_queries,
        split="development",
        method=method,
        group_ids=manifest["development_event_ids"],
    )
    _match_collection_trace(audit, read_jsonl(output / "imported_run/trace.jsonl"))
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
    scored = score(build_path, output / "imported_run", output / "score.json")
    result = {
        **context,
        "collection": collection,
        "collection_audit_sha256": fingerprint(audit),
        "offline_import": imported,
        "metrics": scored["metrics"],
        "interpretation": "Actual collection telemetry is separate from the zero-network offline submission import; no certified leaderboard claim.",
    }
    write_json(output / "result.json", result)
    return result


def run_experiment(
    experiment_path: Path, output: Path, *, transport: Transport | None = None
) -> dict:
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("experiment output exists; choose a new path")
    manifest, config, episodes = validate_experiment(experiment_path)
    if output.is_relative_to(Path(manifest["build_path"]).resolve()):
        raise ValueError("experiment output cannot modify its frozen build")
    output.mkdir(parents=True)
    write_json(output / "experiment.json", manifest)
    ledger = BudgetLedger(
        manifest["budget"], output / "budget_ledger.json", experiment_id=manifest["experiment_id"]
    )
    started = time.monotonic()
    execution = {
        "schema_version": "p1_deepseek_development_execution_v1",
        "experiment_id": manifest["experiment_id"],
        "experiment_path": str(Path(experiment_path).resolve()),
        "experiment_file_sha256": file_hash(Path(experiment_path)),
        "runner_sha256": file_hash(Path(__file__)),
        "status": "running",
        "started_at": _timestamp(),
        "model_kind": "live_provider"
        if transport is None
        else "offline_injected_transport_fixture",
        "planned_checkpoints_total": 90,
        "provider_attempts_started": 0,
        "methods": [],
        "heldout_evaluated": False,
        "automatic_retry": False,
        "monetary_cap_enforced": False,
        "billing_guarantee": False,
        "conditional_usd_request_admission_guard": True,
        "eligible_for_llm_leaderboard": False,
    }
    write_json(output / "execution.json", execution)
    try:
        for method in METHODS:
            checked_manifest, checked_config, checked_episodes = validate_experiment(
                experiment_path
            )
            if (checked_manifest, checked_config, checked_episodes) != (manifest, config, episodes):
                raise ValueError("experiment inputs changed during execution")
            client = BudgetedClient(config, ledger, method=method, transport=transport)
            method_output = output / "runs" / method
            max_queries = 0 if ledger.halted else manifest["expected_requests_per_method"]
            result = _collect_method(
                manifest,
                config,
                episodes,
                method_output,
                method=method,
                max_queries=max_queries,
                client=client,
            )
            collection = result["collection"]
            if collection["status"] != "completed":
                ledger.halt("collection_" + collection["status"])
            rescored_output = output / "rescores" / method
            derived = rescore(
                Path(manifest["build_path"]),
                method_output / "imported_run",
                rescored_output,
                historical_score=method_output / "score.json",
            )
            verified = verify_rescore(rescored_output)
            execution["methods"].append(
                {
                    "method": method,
                    "collection_status": collection["status"],
                    "collection_attempts_started": collection["attempts_started"],
                    "completions_received": collection["completions_received"],
                    "accepted_decisions": collection["accepted_decisions"],
                    "invalid_decisions": collection["invalid_decisions"],
                    "planned_checkpoints": collection["planned_checkpoints"],
                    "run_path": str(method_output),
                    "rescore_path": str(rescored_output),
                    "rescore_id": derived["rescore_id"],
                    "rescore_verification": verified,
                }
            )
            execution["provider_attempts_started"] = ledger.snapshot()["provider_attempts_started"]
            write_json(output / "execution.json", execution)
            print(
                canonical(
                    {
                        "method": method,
                        "status": collection["status"],
                        "completions_received": collection["completions_received"],
                        "global_provider_attempts_started": execution["provider_attempts_started"],
                    }
                ),
                flush=True,
            )
        if validate_experiment(experiment_path) != (manifest, config, episodes):
            raise ValueError("experiment inputs changed during execution")
        execution["status"] = "stopped" if ledger.halted else "completed"
    except BaseException as error:
        ledger.halt(
            "runner_interrupted"
            if isinstance(error, (KeyboardInterrupt, SystemExit))
            else "runner_failure"
        )
        execution["status"] = (
            "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed"
        )
        execution["failure_type"] = type(error).__name__
        raise
    finally:
        execution["finished_at"] = _timestamp()
        execution["elapsed_seconds"] = time.monotonic() - started
        execution["provider_attempts_started"] = ledger.snapshot()["provider_attempts_started"]
        execution["halt_reason"] = ledger.halt_reason
        write_json(output / "execution.json", execution)
    return execution


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    installed_secret = False
    try:
        if args.output.exists():
            raise ValueError("experiment output exists; choose a new path")
        _, config, _ = validate_experiment(args.experiment)
        if not os.environ.get(config.key_env):
            secret = getpass.getpass("DeepSeek API key (not stored): ")
            if not secret:
                raise ValueError("empty credential")
            os.environ[config.key_env] = secret
            installed_secret = True
            del secret
        result = run_experiment(args.experiment, args.output)
    except (Exception, KeyboardInterrupt) as error:
        print(
            canonical(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "detail": "Inspect preserved execution/collection records; no automatic retry.",
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
    finally:
        if installed_secret:
            os.environ.pop("DEEPSEEK_API_KEY", None)
    print(
        canonical(
            {
                "status": result["status"],
                "provider_attempts_started": result["provider_attempts_started"],
                "output": str(args.output.resolve()),
            }
        ),
        flush=True,
    )
    if result["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
