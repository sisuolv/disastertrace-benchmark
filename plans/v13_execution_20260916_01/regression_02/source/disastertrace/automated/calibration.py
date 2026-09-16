"""Offline preparation for a separately versioned contract/budget experiment."""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

from .common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    safe_child,
    strict_json,
    write_json,
    write_jsonl,
)
from .dynamic import (
    diagnostic_response,
    parse_decision,
    render_request,
    score_dynamic,
    validate_episode,
)
from .output_contract import (
    EXPLICIT_CONTRACT,
    LEGACY_CONTRACT,
    contract_spec,
    render_calibration_request,
)
from .provider import ProviderClient, ProviderConfig
from .scoring_v2 import score_dynamic_v2
from .workflow import _require_implementation, selected_episodes, verify_build

ROOT = Path(__file__).resolve().parents[3]
DEVELOPMENT_EVENTS = ("AL092021", "AL062018", "AL052019")
METHODS = ("snapshot", "structured_state", "answer_history")
ARMS = (
    ("legacy_4096", LEGACY_CONTRACT, 4096),
    ("explicit_4096", EXPLICIT_CONTRACT, 4096),
    ("explicit_8192", EXPLICIT_CONTRACT, 8192),
)
BACKENDS = ("rule", "last-arrival", "no-update", "invalid-control")
DEFAULT_PROTOCOL = ROOT / "docs/CALIBRATION_PROTOCOL_V1.md"
DEFAULT_RATES = ROOT / "artifacts/p1_deepseek_development/docs/rates.json"


def read(path: Path) -> dict:
    return strict_json(Path(path).read_text(encoding="utf-8"))


def cells() -> list[dict]:
    return [
        {
            "cell_id": arm + "__" + method,
            "arm_id": arm,
            "contract": contract,
            "max_output_tokens": cap,
            "method": method,
            "planned_responses": 30,
        }
        for arm, contract, cap in ARMS
        for method in METHODS
    ]


def make_schedule(episodes: list[dict]) -> list[dict]:
    expected_ids = {
        event.lower() + ":controlled:" + branch
        for event in DEVELOPMENT_EVENTS
        for branch in ("base", "delay")
    }
    if len(episodes) != 6 or {ep["episode_id"] for ep in episodes} != expected_ids:
        raise ValueError("calibration requires exactly the six frozen development episodes")
    mapping = {ep["episode_id"]: ep for ep in episodes}
    for ep in episodes:
        validate_episode(ep)
        if (
            ep["split"] != "development"
            or ep["group_id"] not in DEVELOPMENT_EVENTS
            or ep["episode_id"].split(":")[0] != ep["group_id"].lower()
            or [cp["checkpoint_id"] for cp in ep["checkpoints"]] != [f"c{i}" for i in range(5)]
        ):
            raise ValueError("calibration development scope or checkpoint sequence changed")
    rows = []
    for storm_index, event in enumerate(DEVELOPMENT_EVENTS):
        arms = ARMS[storm_index:] + ARMS[:storm_index]
        methods = METHODS[storm_index:] + METHODS[:storm_index]
        branches = ("base", "delay") if storm_index % 2 == 0 else ("delay", "base")
        for arm_index, (arm, contract, cap) in enumerate(arms):
            for method_index, method in enumerate(methods):
                cell_id = arm + "__" + method
                for branch in branches:
                    episode_id = event.lower() + ":controlled:" + branch
                    for cp_index, checkpoint in enumerate(mapping[episode_id]["checkpoints"]):
                        rows.append(
                            {
                                "attempt_number": len(rows) + 1,
                                "cell_id": cell_id,
                                "arm_id": arm,
                                "contract": contract,
                                "method": method,
                                "max_output_tokens": cap,
                                "event_id": event,
                                "episode_id": episode_id,
                                "checkpoint_id": checkpoint["checkpoint_id"],
                                "trajectory_id": cell_id + "__" + episode_id,
                                "trajectory_checkpoint_index": cp_index,
                                "configuration_position": 3 * arm_index + method_index,
                                "repeat": 0,
                            }
                        )
    return rows


def provider_configs(config: ProviderConfig) -> dict[str, dict]:
    baseline = {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "max_output_tokens": 4096,
        "token_parameter": "max_tokens",
        "temperature": None,
        "timeout": 60,
        "max_response_bytes": 1048576,
        "reasoning_effort": "high",
        "thinking_type": "enabled",
    }
    if asdict(config) != baseline:
        raise ValueError("provider configuration differs from the proposed calibration protocol")
    return {
        cell["cell_id"]: asdict(replace(config, max_output_tokens=cell["max_output_tokens"]))
        for cell in cells()
    }


def proposed_budget(rates: dict) -> dict:
    if rates.get("model") != "deepseek-v4-flash" or rates.get("currency") != "USD":
        raise ValueError("calibration needs the captured DeepSeek USD rates")
    prompt = rates["context"]["reservation_prompt_tokens"]
    input_rate = Decimal(str(rates["peak_per_million_tokens"]["input_cache_miss"]))
    output_rate = Decimal(str(rates["peak_per_million_tokens"]["output"]))
    if (
        type(prompt) is not int
        or prompt != 1048576
        or (input_rate, output_rate) != (Decimal("0.44"), Decimal("1.32"))
    ):
        raise ValueError("price/context changes need a separately versioned accounting plan")
    reservations = {
        str(cap): str((prompt * input_rate + cap * output_rate) / Decimal(1000000))
        for cap in (4096, 8192)
    }
    return {
        "currency": "USD",
        "allowance": "3.00",
        "authorized": False,
        "applies_to": "new_calibration_only_not_the_completed_P1_ledger",
        "max_provider_requests": 270,
        "maximum_requested_output_tokens": 1474560,
        "max_request_bytes": 262144,
        "prompt_reservation_tokens": prompt,
        "peak_input_per_million": str(input_rate),
        "peak_output_per_million": str(output_rate),
        "pending_reservation_by_output_cap_usd": reservations,
        "all_calls_at_full_context_ceiling_usd": str(
            180 * Decimal(reservations["4096"]) + 90 * Decimal(reservations["8192"])
        ),
        "completion_guaranteed": False,
        "billing_guaranteed": False,
        "live_guard_implemented": False,
        "rates_must_be_revalidated_before_live": True,
    }


def screen_budget(rows: list[dict]) -> dict:
    """Rehearse the count rule; aggregate counts cannot authenticate live evidence."""
    expected = {cell["cell_id"] for cell in cells()}
    if not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("nine unique complete cell summaries required")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "cell_id",
            "received",
            "schema_valid",
            "length_failures",
        }:
            raise ValueError("invalid screening summary fields")
        key = row["cell_id"]
        if not isinstance(key, str) or key not in expected or key in indexed:
            raise ValueError("unknown or duplicate screening cell")
        for name in ("received", "schema_valid", "length_failures"):
            if type(row[name]) is not int or not 0 <= row[name] <= 30:
                raise ValueError("screening counts must be integers within planned opportunities")
        if max(row["schema_valid"], row["length_failures"]) > row["received"]:
            raise ValueError("screening successes/failures exceed received responses")
        indexed[key] = row
    complete = all(row["received"] == 30 for row in rows)
    qualifies = {
        str(cap): complete
        and all(
            indexed[f"explicit_{cap}__{method}"]["schema_valid"] >= 29
            and indexed[f"explicit_{cap}__{method}"]["length_failures"] <= 1
            for method in METHODS
        )
        for cap in (4096, 8192)
    }
    selected = next((cap for cap in (4096, 8192) if qualifies[str(cap)]), None)
    return {
        "schema_version": "calibration_budget_screen_v1",
        "status": "incomplete" if not complete else ("selected" if selected else "no_selection"),
        "selected_output_tokens": selected,
        "qualified_caps": qualifies,
        "evidence_validated": False,
        "live_recommendation": False,
        "note": (
            "Aggregate screening only; live use needs independently audited usage and responses."
        ),
    }


def rehearse(episodes: list[dict], method: str, contract: str, backend: str) -> list[dict]:
    if backend not in BACKENDS:
        raise ValueError("unsupported diagnostic backend")
    rows = []
    for ep in episodes:
        previous, history = None, []
        for checkpoint in ep["checkpoints"]:
            request = render_calibration_request(
                ep,
                checkpoint["checkpoint_id"],
                previous,
                method=method,
                history=history,
                contract=contract,
            )
            raw = (
                ""
                if backend == "invalid-control" and checkpoint["checkpoint_id"] == "c2"
                else diagnostic_response(
                    request, "rule" if backend == "invalid-control" else backend
                )
            )
            status, error = "ok", None
            try:
                decision = parse_decision(raw)
            except (ValueError, TypeError, KeyError) as exc:
                status, error = "invalid", str(exc)
            else:
                previous = decision
                history.append(copy.deepcopy(decision))
            rows.append(
                {
                    "episode_id": ep["episode_id"],
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "backend": backend,
                    "method": method,
                    "contract": contract,
                    "model_kind": "diagnostic_program",
                    "eligible_for_llm_leaderboard": False,
                    "request": request,
                    "request_hash": fingerprint(request),
                    "raw_response": raw,
                    "status": status,
                    "error": error,
                    "state_after": copy.deepcopy(previous),
                    "logical_queries": 1,
                    "provider_requests": 0,
                }
            )
    return rows


def score_rehearsal(
    episodes: list[dict], traces: list[dict], method: str, contract: str
) -> tuple[dict, list[dict]]:
    """Verify exposures before making a separate, labeled legacy-audit projection."""
    expected = [(ep, cp) for ep in episodes for cp in ep["checkpoints"]]
    if len(traces) != len(expected):
        raise ValueError("rehearsal must retain every planned checkpoint")
    projection = []
    for ep in episodes:
        previous, history = None, []
        for cp in ep["checkpoints"]:
            row = traces[len(projection)]
            if (
                row["episode_id"] != ep["episode_id"]
                or row["checkpoint_id"] != cp["checkpoint_id"]
                or row["method"] != method
                or row["contract"] != contract
                or row["model_kind"] != "diagnostic_program"
                or row["eligible_for_llm_leaderboard"] is not False
                or type(row["provider_requests"]) is not int
                or row["provider_requests"] != 0
                or type(row["logical_queries"]) is not int
                or row["logical_queries"] != 1
            ):
                raise ValueError("invalid rehearsal identity or non-diagnostic trace")
            actual = render_calibration_request(
                ep,
                cp["checkpoint_id"],
                previous,
                method=method,
                history=history,
                contract=contract,
            )
            if canonical(row["request"]) != canonical(actual) or row["request_hash"] != fingerprint(
                actual
            ):
                raise ValueError("actual calibration request/history changed")
            legacy = render_request(
                ep, cp["checkpoint_id"], previous, method=method, history=history
            )
            if {k: v for k, v in actual.items() if k != "instruction"} != {
                k: v for k, v in legacy.items() if k != "instruction"
            }:
                raise ValueError("projection changes more than the instruction")
            try:
                decision = parse_decision(row["raw_response"])
            except (ValueError, TypeError, KeyError):
                status = "invalid"
            else:
                status = "ok"
                previous = decision
                history.append(copy.deepcopy(decision))
            if row["status"] != status or canonical(row["state_after"]) != canonical(previous):
                raise ValueError("rehearsal changed accepted state or invalid-answer accounting")
            projected = copy.deepcopy(row)
            projected["request"] = legacy
            projected["request_hash"] = fingerprint(legacy)
            projection.append(projected)
    frozen_score = score_dynamic_v2(episodes, projection)
    return {
        "schema_version": "calibration_diagnostic_score_v1",
        "model_calls": 0,
        "eligible_for_llm_leaderboard": False,
        "metrics": frozen_score["metrics"],
        "baseline_v1": score_dynamic(episodes, projection),
        "frozen_score": frozen_score,
        "projection": {
            "policy": "verified_actual_exposure_then_legacy_instruction_only_v1",
            "actual_trace_sha256": fingerprint(traces),
            "scoring_projection_sha256": fingerprint(projection),
            "actual_exposure_is_projection": False,
            "live_collection_verified": False,
        },
    }, projection


def _generated_files(episodes: list[dict], config: ProviderConfig, rates: dict) -> dict:
    schedule = make_schedule(episodes)
    configs = provider_configs(config)
    mapping = {ep["episode_id"]: ep for ep in episodes}
    files = {
        "schedule.jsonl": schedule,
        "contract.json": contract_spec(),
    }
    initial = []
    for row in schedule:
        if row["trajectory_checkpoint_index"] != 0:
            continue
        request = render_calibration_request(
            mapping[row["episode_id"]],
            row["checkpoint_id"],
            None,
            method=row["method"],
            history=[],
            contract=row["contract"],
        )
        prepared = ProviderClient(ProviderConfig.from_dict(configs[row["cell_id"]])).prepare(
            request
        )
        if len(prepared["raw_request"].encode("utf-8")) > 262144:
            raise ValueError("initial request exceeds proposed request byte guard")
        initial.append(
            {
                "cell_id": row["cell_id"],
                "episode_id": row["episode_id"],
                "checkpoint_id": row["checkpoint_id"],
                "public_request": request,
                "prepared": prepared,
                "model_calls": 0,
                "kind": "unsent_initial_request_only",
                "live_carrier_available": False,
            }
        )
    files["initial_requests.jsonl"] = initial
    diagnostics = []
    for cell in cells():
        key = cell["cell_id"]
        files[f"configs/{key}.json"] = configs[key]
        for backend in BACKENDS:
            traces = rehearse(episodes, cell["method"], cell["contract"], backend)
            scored, projection = score_rehearsal(episodes, traces, cell["method"], cell["contract"])
            base = f"rehearsals/{backend}/{key}"
            files[base + "/trace.jsonl"] = traces
            files[base + "/scoring_projection.jsonl"] = projection
            files[base + "/score.json"] = scored
            # Prepare every diagnostic wire request, without reading a key or sending it.
            client = ProviderClient(ProviderConfig.from_dict(configs[key]))
            sizes = [
                len(client.prepare(row["request"])["raw_request"].encode("utf-8")) for row in traces
            ]
            known = scored["metrics"]["known_grounded_accuracy"]
            schema = scored["metrics"]["schema_success"]
            expected_known = {
                "rule": 96,
                "last-arrival": 72,
                "no-update": 0,
                "invalid-control": 72,
            }[backend]
            expected_valid = 24 if backend == "invalid-control" else 30
            if (
                known["numerator"] != expected_known
                or known["denominator"] != 96
                or schema["numerator"] != expected_valid
            ):
                raise ValueError("diagnostic control failed its predeclared expectation")
            if max(sizes) > 262144:
                raise ValueError("diagnostic request exceeds proposed request byte guard")
            diagnostics.append(
                {
                    "cell_id": key,
                    "backend": backend,
                    "responses": len(traces),
                    "known_grounding": known,
                    "schema_success": schema,
                    "max_diagnostic_request_bytes": max(sizes),
                    "model_calls": 0,
                }
            )
    files["diagnostics.json"] = {
        "schema_version": "calibration_offline_diagnostics_v1",
        "model_calls": 0,
        "diagnostic_responses": 1080,
        "live_predictions_created": False,
        "cells": diagnostics,
        "note": "Program controls do not measure LLM behavior or output-budget sufficiency.",
    }
    files["budget_proposal.json"] = proposed_budget(rates)
    return files


def _scope() -> dict:
    return {
        "schema_version": "calibration_offline_preparation_v1",
        "status": "offline_prepared",
        "development_event_ids": list(DEVELOPMENT_EVENTS),
        "cells": cells(),
        "planned_provider_calls": 270,
        "planned_trajectories": 54,
        "repeats": 1,
        "model_calls": 0,
        "heldout_model_calls": 0,
        "live_ready": False,
        "live_runner_implemented": False,
        "historical_answers_reused": 0,
        "automatic_retry": False,
        "new_per_item_human_review": False,
        "llm_judge": False,
        "next_stage": (
            "contract-aware collector/audit and tested budget guard "
            "before a separately authorized live launch"
        ),
        "initial_request_count": 54,
        "remaining_requests": "must_use_actual_same_trajectory_schema_valid_model_answers",
    }


def prepare(
    build_path: Path,
    provider_config_path: Path,
    output: Path,
    *,
    protocol_path: Path = DEFAULT_PROTOCOL,
    rates_path: Path = DEFAULT_RATES,
) -> dict:
    output = Path(output)
    if output.exists():
        raise ValueError("calibration output exists; choose a fresh path")
    build_path = Path(build_path).resolve()
    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    episodes = selected_episodes(build_path, "development")
    config = ProviderConfig.from_dict(read(provider_config_path))
    rates = read(rates_path)
    protocol_bytes = Path(protocol_path).read_bytes()
    generated = _generated_files(episodes, config, rates)
    plan = {
        **_scope(),
        "build_path": str(build_path),
        "build_id": manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "episodes_sha256": fingerprint(episodes),
        "proposed_budget": generated["budget_proposal.json"],
        "protocol_sha256": file_hash(protocol_path),
        "provider_config_sha256": file_hash(provider_config_path),
        "rates_sha256": file_hash(rates_path),
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "plan.json", plan)
    write_jsonl(output / "development_episodes.jsonl", episodes)
    write_json(output / "implementation.json", implementation)
    (output / "protocol.md").write_bytes(protocol_bytes)
    (output / "provider_input.json").write_bytes(Path(provider_config_path).read_bytes())
    (output / "rates.json").write_bytes(Path(rates_path).read_bytes())
    for name, content in generated.items():
        (write_jsonl if name.endswith(".jsonl") else write_json)(output / name, content)
    file_map = {
        str(path.relative_to(output)): file_hash(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    package = {"schema_version": "calibration_preparation_manifest_v1", "files": file_map}
    package["package_id"] = fingerprint(package)
    write_json(output / "manifest.json", package)
    return {**plan, "package_id": package["package_id"]}


def verify(output: Path) -> dict:
    output = Path(output)
    manifest = read(output / "manifest.json")
    if manifest["package_id"] != fingerprint(
        {k: v for k, v in manifest.items() if k != "package_id"}
    ):
        raise ValueError("preparation manifest identity changed")
    for name, expected in manifest["files"].items():
        if file_hash(safe_child(output, name)) != expected:
            raise ValueError("preparation artifact changed: " + name)
    plan = read(output / "plan.json")
    build_path = Path(plan["build_path"])
    build_manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    episodes = selected_episodes(build_path, "development")
    if (
        build_manifest["build_id"] != plan["build_id"]
        or implementation["implementation_id"] != plan["implementation_id"]
        or read(output / "implementation.json") != implementation
        or read_jsonl(output / "development_episodes.jsonl") != episodes
        or fingerprint(episodes) != plan["episodes_sha256"]
    ):
        raise ValueError("preparation build/development data binding changed")
    for name, field in (
        ("protocol.md", "protocol_sha256"),
        ("rates.json", "rates_sha256"),
        ("provider_input.json", "provider_config_sha256"),
    ):
        if file_hash(output / name) != plan[field]:
            raise ValueError("preparation input binding changed")
    expected_plan = {
        **_scope(),
        "build_path": str(build_path.resolve()),
        "build_id": build_manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "episodes_sha256": fingerprint(episodes),
        "proposed_budget": proposed_budget(read(output / "rates.json")),
        "protocol_sha256": file_hash(output / "protocol.md"),
        "provider_config_sha256": file_hash(output / "provider_input.json"),
        "rates_sha256": file_hash(output / "rates.json"),
    }
    if canonical(plan) != canonical(expected_plan):
        raise ValueError("offline scope/plan claims changed")
    generated = _generated_files(
        episodes,
        ProviderConfig.from_dict(read(output / "provider_input.json")),
        read(output / "rates.json"),
    )
    required_files = set(generated) | {
        "plan.json",
        "development_episodes.jsonl",
        "implementation.json",
        "protocol.md",
        "provider_input.json",
        "rates.json",
    }
    if set(manifest["files"]) != required_files:
        raise ValueError("preparation manifest file inventory changed")
    for name, expected in generated.items():
        actual = read_jsonl(output / name) if name.endswith(".jsonl") else read(output / name)
        if canonical(actual) != canonical(expected):
            raise ValueError("preparation semantic verification failed: " + name)
    return {
        "status": "passed",
        "package_id": manifest["package_id"],
        "verified_artifacts": len(manifest["files"]),
        "planned_provider_calls": 270,
        "initial_requests_verified": 54,
        "diagnostic_responses_verified": 1080,
        "model_calls": 0,
        "live_ready": False,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Build unsent requests and offline program controls")
    prep.add_argument("--build", type=Path, required=True)
    prep.add_argument("--provider-config", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    prep.add_argument("--rates", type=Path, default=DEFAULT_RATES)
    check = commands.add_parser("verify", help="Reconstruct and verify the offline preparation")
    check.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = (
        prepare(
            args.build,
            args.provider_config,
            args.output,
            protocol_path=args.protocol,
            rates_path=args.rates,
        )
        if args.command == "prepare"
        else verify(args.output)
    )
    print(canonical(result))


if __name__ == "__main__":
    main()
