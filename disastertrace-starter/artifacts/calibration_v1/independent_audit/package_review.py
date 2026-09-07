"""Independently replay the proposed calibration package; reject network access."""

from __future__ import annotations

import argparse
import copy
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from audit import ORIGINAL_BUILD, ROOT, Audit, read, sha

from disastertrace.automated import calibration
from disastertrace.automated.common import fingerprint as fp
from disastertrace.automated.common import read_jsonl as jsonl
from disastertrace.automated.dynamic import (
    diagnostic_response,
    parse_decision,
    render_request,
    score_dynamic,
)
from disastertrace.automated.output_contract import render_calibration_request
from disastertrace.automated.provider import ProviderClient, ProviderConfig
from disastertrace.automated.scoring_v2 import score_dynamic_v2


def review(audit: Audit, prepared: Path) -> None:
    check = audit.check
    manifest = read(prepared / "manifest.json")
    audit.bind(prepared / "manifest.json")
    audit.bind(Path(__file__))
    audit.bind(Path(__file__).with_name("audit.py"))
    check(
        manifest["package_id"] == fp({k: v for k, v in manifest.items() if k != "package_id"}),
        "package_fingerprint",
    )
    actual_files = {
        str(p.relative_to(prepared))
        for p in prepared.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    check(actual_files == set(manifest["files"]), "package_file_inventory_exact")
    for name, digest in manifest["files"].items():
        path = prepared / name
        check(
            path.resolve().is_relative_to(prepared.resolve()) and sha(path) == digest,
            "package_checksum:" + name,
        )
        audit.bind(path)
    plan = read(prepared / "plan.json")
    fixed = {
        "status": "offline_prepared",
        "development_event_ids": ["AL092021", "AL062018", "AL052019"],
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
        "initial_request_count": 54,
    }
    for key, expected in fixed.items():
        check(
            type(plan.get(key)) is type(expected) and plan[key] == expected,
            "fixed_offline_plan:" + key,
        )
    build = Path(plan["build_path"])
    audit.bind(build / "manifest.json")
    old_manifest = read(ORIGINAL_BUILD / "manifest.json")
    build_manifest = read(build / "manifest.json")
    check(
        build_manifest["build_id"]
        == plan["build_id"]
        == fp({k: v for k, v in build_manifest.items() if k != "build_id"}),
        "new_build_identity",
    )
    data_files = {
        n: h
        for n, h in old_manifest["files"].items()
        if n != "implementation.json" and not n.startswith("implementation_source/")
    }
    check(len(data_files) == 15, "fifteen_original_data_artifacts")
    for name, digest in data_files.items():
        check(
            build_manifest["files"].get(name) == digest == sha(build / name),
            "new_build_data_unchanged:" + name,
        )
    implementation = read(prepared / "implementation.json")
    check(
        implementation == read(build / "implementation.json")
        and implementation["implementation_id"] == plan["implementation_id"],
        "new_implementation_binding",
    )
    for name, digest in implementation["files"].items():
        path = ROOT / "src/disastertrace/automated" / name
        check(sha(path) == digest, "new_build_current_source:" + name)
        audit.bind(path)
    episodes = jsonl(prepared / "development_episodes.jsonl")
    expected_episodes = [
        e for e in jsonl(build / "episodes/dynamic_episodes.jsonl") if e["split"] == "development"
    ]
    check(
        episodes == expected_episodes
        and fp(episodes) == plan["episodes_sha256"]
        and len(episodes) == 6,
        "six_development_episodes_bound",
    )
    by_episode = {ep["episode_id"]: ep for ep in episodes}
    original_config = asdict(
        ProviderConfig.from_dict(read(ROOT / "artifacts/p1_deepseek_development/provider.json"))
    )
    check(
        asdict(ProviderConfig.from_dict(read(prepared / "provider_input.json"))) == original_config,
        "original_provider_controls_preserved",
    )
    arms = [
        ("legacy_4096", "legacy_v1", 4096),
        ("explicit_4096", "explicit_v1", 4096),
        ("explicit_8192", "explicit_v1", 8192),
    ]
    methods = ["snapshot", "structured_state", "answer_history"]
    expected_cells = [
        {
            "cell_id": arm + "__" + method,
            "arm_id": arm,
            "contract": contract,
            "max_output_tokens": cap,
            "method": method,
            "planned_responses": 30,
        }
        for arm, contract, cap in arms
        for method in methods
    ]
    check(plan["cells"] == expected_cells, "nine_full_cells")
    schedule = jsonl(prepared / "schedule.jsonl")
    expected_order = []
    for event_index, event in enumerate(fixed["development_event_ids"]):
        for arm_index in range(3):
            arm = arms[(arm_index + event_index) % 3][0]
            for method_index in range(3):
                method = methods[(method_index + event_index) % 3]
                for branch in ["delay", "base"] if event_index == 1 else ["base", "delay"]:
                    for checkpoint_index in range(5):
                        expected_order.append(
                            (
                                arm + "__" + method,
                                event.lower() + ":controlled:" + branch,
                                "c" + str(checkpoint_index),
                                3 * arm_index + method_index,
                            )
                        )
    observed_order = [
        (r["cell_id"], r["episode_id"], r["checkpoint_id"], r["configuration_position"])
        for r in schedule
    ]
    check(observed_order == expected_order, "independently_reconstructed_full_schedule_order")
    check(
        len(schedule) == len(set(observed_order)) == 270
        and [r["attempt_number"] for r in schedule] == list(range(1, 271)),
        "270_distinct_ordered_requests",
    )
    check(
        Counter(r["cell_id"] for r in schedule) == {c["cell_id"]: 30 for c in expected_cells},
        "thirty_opportunities_per_cell",
    )
    check(sum(r["max_output_tokens"] for r in schedule) == 1474560, "requested_output_total")
    for cell in expected_cells:
        config = read(prepared / "configs" / (cell["cell_id"] + ".json"))
        check(
            config == {**original_config, "max_output_tokens": cell["max_output_tokens"]},
            "only_output_cap_varies:" + cell["cell_id"],
        )
    budget = read(prepared / "budget_proposal.json")
    check(budget == plan["proposed_budget"], "budget_proposal_plan_binding")
    budget_fixed = {
        "authorized": False,
        "allowance": "3.00",
        "max_provider_requests": 270,
        "maximum_requested_output_tokens": 1474560,
        "max_request_bytes": 262144,
        "completion_guaranteed": False,
        "billing_guaranteed": False,
        "live_guard_implemented": False,
        "rates_must_be_revalidated_before_live": True,
    }
    for key, expected in budget_fixed.items():
        check(
            type(budget.get(key)) is type(expected) and budget[key] == expected,
            "proposed_budget_only:" + key,
        )
    reserves = {
        str(cap): (Decimal(1048576) * Decimal("0.44") + cap * Decimal("1.32")) / 1_000_000
        for cap in (4096, 8192)
    }
    check(
        {k: Decimal(v) for k, v in budget["pending_reservation_by_output_cap_usd"].items()}
        == reserves,
        "independent_full_context_reservations",
    )
    check(
        Decimal(budget["all_calls_at_full_context_ceiling_usd"])
        == 180 * reserves["4096"] + 90 * reserves["8192"]
        == Decimal("126.517248"),
        "independent_all_calls_ceiling",
    )
    initial = jsonl(prepared / "initial_requests.jsonl")
    starts = [r for r in schedule if r["trajectory_checkpoint_index"] == 0]
    check(
        len(initial) == 54
        and [(r["cell_id"], r["episode_id"], r["checkpoint_id"]) for r in initial]
        == [(r["cell_id"], r["episode_id"], r["checkpoint_id"]) for r in starts],
        "only_fiftyfour_initial_requests",
    )
    for row, scheduled in zip(initial, starts):
        label = row["cell_id"] + ":" + row["episode_id"]
        expected = render_calibration_request(
            by_episode[row["episode_id"]],
            row["checkpoint_id"],
            None,
            method=scheduled["method"],
            history=[],
            contract=scheduled["contract"],
        )
        check(
            row["public_request"] == expected
            and row["model_calls"] == 0
            and row["kind"] == "unsent_initial_request_only"
            and row["live_carrier_available"] is False,
            "unsent_initial_request:" + label,
        )
        config = ProviderConfig.from_dict(read(prepared / "configs" / (row["cell_id"] + ".json")))
        check(
            row["prepared"] == ProviderClient(config).prepare(expected),
            "initial_wire_binding:" + label,
        )
    diagnostic_count = 0
    for cell in expected_cells:
        for backend in ("rule", "last-arrival", "no-update", "invalid-control"):
            label = backend + ":" + cell["cell_id"]
            base = prepared / "rehearsals" / backend / cell["cell_id"]
            traces = jsonl(base / "trace.jsonl")
            projection = jsonl(base / "scoring_projection.jsonl")
            score = read(base / "score.json")
            check(len(traces) == len(projection) == 30, "full_diagnostic_trajectory_count:" + label)
            diagnostic_count += len(traces)
            index = 0
            for episode in episodes:
                previous, history = None, []
                for checkpoint in episode["checkpoints"]:
                    row, projected = traces[index], projection[index]
                    sublabel = label + ":" + str(index)
                    index += 1
                    actual = render_calibration_request(
                        episode,
                        checkpoint["checkpoint_id"],
                        previous,
                        method=cell["method"],
                        history=history,
                        contract=cell["contract"],
                    )
                    legacy = render_request(
                        episode,
                        checkpoint["checkpoint_id"],
                        previous,
                        method=cell["method"],
                        history=history,
                    )
                    check(
                        (row["episode_id"], row["checkpoint_id"])
                        == (episode["episode_id"], checkpoint["checkpoint_id"])
                        and row["request"] == actual
                        and row["request_hash"] == fp(actual),
                        "actual_sequential_exposure:" + sublabel,
                    )
                    check(
                        {k: v for k, v in row.items() if k not in {"request", "request_hash"}}
                        == {
                            k: v
                            for k, v in projected.items()
                            if k not in {"request", "request_hash"}
                        }
                        and projected["request"] == legacy
                        and projected["request_hash"] == fp(legacy),
                        "projection_instruction_only:" + sublabel,
                    )
                    check(
                        row["provider_requests"] == 0
                        and row["model_kind"] == "diagnostic_program"
                        and row["eligible_for_llm_leaderboard"] is False
                        and row["backend"] == backend,
                        "trace_is_not_model_observation:" + sublabel,
                    )
                    raw = (
                        ""
                        if backend == "invalid-control" and checkpoint["checkpoint_id"] == "c2"
                        else diagnostic_response(
                            actual, "rule" if backend == "invalid-control" else backend
                        )
                    )
                    check(
                        row["raw_response"] == raw,
                        "public_evidence_diagnostic_response:" + sublabel,
                    )
                    try:
                        decision = parse_decision(raw)
                    except (TypeError, ValueError, KeyError):
                        status = "invalid"
                    else:
                        status = "ok"
                        previous = decision
                        history.append(copy.deepcopy(decision))
                    check(
                        row["status"] == status and row["state_after"] == previous,
                        "accepted_only_carrier_state:" + sublabel,
                    )
            frozen = score_dynamic_v2(episodes, projection)
            check(
                score["frozen_score"] == frozen and score["metrics"] == frozen["metrics"],
                "unchanged_v2_scorer_replay:" + label,
            )
            check(
                score["baseline_v1"] == score_dynamic(episodes, projection),
                "unchanged_v1_scorer_replay:" + label,
            )
            meta = score["projection"]
            check(
                meta["actual_trace_sha256"] == fp(traces)
                and meta["scoring_projection_sha256"] == fp(projection)
                and meta["actual_exposure_is_projection"] is False
                and meta["live_collection_verified"] is False,
                "projection_bound_and_labeled:" + label,
            )
            expected_known = {
                "rule": 96,
                "last-arrival": 72,
                "no-update": 0,
                "invalid-control": 72,
            }[backend]
            check(
                frozen["metrics"]["known_grounded_accuracy"]
                == {"numerator": expected_known, "denominator": 96, "value": expected_known / 96}
                and frozen["metrics"]["schema_success"]["numerator"]
                == (24 if backend == "invalid-control" else 30),
                "predeclared_control_effect:" + label,
            )
    check(diagnostic_count == 1080, "1080_program_responses_not_live_predictions")
    verified = calibration.verify(prepared)
    check(
        verified["status"] == "passed"
        and verified["model_calls"] == 0
        and verified["live_ready"] is False,
        "built_in_semantic_verify_with_network_rejected",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = Audit()

    def reject_network(*args, **kwargs):
        raise AssertionError("independent verification prohibits model or network calls")

    with (
        patch.object(ProviderClient, "complete", reject_network),
        patch("disastertrace.automated.provider.urllib_transport", reject_network),
    ):
        audit.historical_integrity()
        audit.contract_surface()
        review(audit, args.prepared)
    result = audit.write(args.output)
    print({key: result[key] for key in ("passed", "check_count", "failure_count", "new_api_calls")})
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
