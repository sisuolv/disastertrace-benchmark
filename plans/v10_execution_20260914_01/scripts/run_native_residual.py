"""Qualify conditional residual E reachability from real durable H15 prefixes."""

import argparse
import copy
import datetime as dt
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.evidence import sufficient_recipes
from disastertrace.monitoring_v1.providers.aviation import parse_metar
from disastertrace.monitoring_v1.reachability import Goal
from disastertrace.monitoring_v1.residual_reachability import (
    ResidualQuery,
    replay_residual_witness,
    solve_residual,
)
from disastertrace.monitoring_v1.resources import Cost
from disastertrace.monitoring_v1.session_checkpoint import (
    SessionCoordinator,
    restore_session,
)
from disastertrace.monitoring_v1.source_spool import ArchiveSpoolSource
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def condition_on_original_delivery(prefix, final, data, bank):
    config = prefix["payload"]["config"]
    before = restore_session(prefix, data, bank, config)
    after = restore_session(final, data, bank, config)
    pending = before["pending_source"]
    rid = pending["receipt_id"]
    original_events = before["ledger"].events
    if after["ledger"].events[: len(original_events)] != original_events:
        raise ValueError(
            "Original completion does not extend this exact resource prefix"
        )
    entry = after["ledger"].entries[rid]
    if not entry["settled"] or entry.get("outcome") != "completed":
        raise ValueError(
            "An original successful completion is required; unknown reserves stay held"
        )
    for event in after["ledger"].events[len(original_events) :]:
        if event["receipt_id"] != rid:
            continue
        if event["event"] == "execution_timing":
            before["ledger"].record_execution_timing(
                rid, event["timing"]["last_wall_ns"], event["phase"]
            )
        elif event["event"] == "completed":
            before["ledger"].settle(rid, Cost(**event["actual"]))
        else:
            raise ValueError("Unexpected original-delivery resource event")
    if before["ledger"].entries[rid] != entry:
        raise ValueError("Original completion entry does not reconstruct")
    original = next(r for r in after["source_receipts"] if r["receipt_id"] == rid)
    product = next(
        r for r in data["query_results"] if r["query_id"] == pending["query_id"]
    )
    if (
        canonical_hash(after["store"].assets[pending["asset_id"]]["content"])
        != canonical_hash(product)
        or original["completed_at"] < pending["clock"]
    ):
        raise ValueError("Original native response or completion time differs")
    before["store"].register(
        pending["asset_id"], product, owner=pending["payer"], receipt_id=rid
    )
    before["source_receipts"].append(original)
    completed = {
        a["asset_id"]: max(
            r["completed_at"]
            for r in before["source_receipts"]
            if r["receipt_id"] in a["receipt_ids"]
        )
        for a in before["store"].assets.values()
    }
    return before, completed, original


def qualify(prefix, final, data, bank, out):
    out.mkdir(exist_ok=False)
    state, completed, delivery = condition_on_original_delivery(
        prefix, final, data, bank
    )
    pending = prefix["payload"]["pending_source"]
    config, cutoff = prefix["payload"]["config"], pending["cutoff"]
    pairs = {p["opportunity_id"]: p for p in data["e_f_pairs"]}
    products = {p["query_id"]: p for p in data["query_results"]}
    catalog = {p["query_id"]: p for p in data["query_catalog"]}
    active = [o for o in data["opportunities"] if o["cutoff"] == cutoff]
    queries, goals = [], []

    def asset(qid, owner):
        return (
            qid
            if config["authorization_mode"] == "session_shared"
            else owner + "::" + qid
        )

    for opportunity in active:
        owner = opportunity["target_id"]
        pair = pairs[opportunity["opportunity_id"]]
        recipes = sufficient_recipes(pair["query_ids"], products, pair["threshold_m"])
        goals.append(
            Goal(
                owner,
                cutoff,
                tuple(frozenset(asset(q, owner) for q in recipe) for recipe in recipes),
            )
        )
        for qid in pair["query_ids"]:
            product = products[qid]
            for report in product.get("reports", []):
                at = dt.datetime.fromtimestamp(
                    report["observation_time"] / 1_000_000, dt.timezone.utc
                ).isoformat()
                native = parse_metar(
                    report["raw"], observation_time=at, report_type="routine"
                )
                if (
                    None if native.visibility is None else native.visibility.to_dict()
                ) != report["visibility"]:
                    raise ValueError("Native report differs from cached interval")
            queries.append(
                ResidualQuery(
                    owner + "::" + qid,
                    asset(qid, owner),
                    owner,
                    product,
                    Cost(requests=1, bytes=2048, compute_ms=100),
                    Cost(
                        requests=1,
                        bytes=len(json.dumps(product, separators=(",", ":")).encode()),
                        compute_ms=100,
                    ),
                    catalog[qid]["available_at"],
                    catalog[qid]["latency_ms"] * 1000,
                )
            )
    cutoffs = sorted({o["cutoff"] for o in data["opportunities"]})
    credit = config["request_budget"] * (pending["tick"] + 1) // len(cutoffs)
    cap = config.get("query_limit_per_tick")
    cap = None if cap is None else max(0, cap - len(pending["source_steps"]) - 1)
    kwargs = {
        "start": delivery["completed_at"],
        "cached_completed": completed,
        "source_credit": credit,
        "max_additional_queries": cap,
    }
    result = solve_residual(state["ledger"], state["store"], queries, goals, **kwargs)
    witness_results = []
    by_key = {q.query_key: q for q in queries}
    for witness in result["frontier"]:
        replay = replay_residual_witness(
            witness, state["ledger"], state["store"], queries, goals, **kwargs
        )
        receipts = copy.deepcopy(state["source_receipts"])
        for action in witness["actions"]:
            q = by_key[action["query_key"]]
            receipts.append(
                {
                    "query_id": q.content["query_id"],
                    "asset_id": q.asset_id,
                    "payer": q.owner,
                    "receipt_id": "residual:" + q.query_key,
                    "started_at": action["started_at"],
                    "completed_at": action["completed_at"],
                }
            )
        native = {}
        for opportunity in active:
            bundle = state["runtime"].freeze_acquired(
                opportunity, cutoff, replay["store"], replay["ledger"], receipts
            )
            native[opportunity["target_id"]] = native_slot_support(bundle)["status"]
        if (
            sorted(
                t for t, status in native.items() if status in {"supported", "refuted"}
            )
            != witness["resolved"]
        ):
            raise ValueError("Native support reducer differs from joint recipe witness")
        witness_results.append(
            {
                "witness": witness,
                "ledger_store_replay_passed": replay["passed"],
                "native_support": native,
            }
        )
    provenance = {
        "prefix_sha256": prefix["sha256"],
        "original_completion_checkpoint_sha256": final["sha256"],
        "original_receipt": delivery,
        "original_delivery_is_mandatory": True,
        "future_source_costs": "unchanged declared native archive cost/latency, not measured live service optimization",
        "before_original_completion": {
            "spent": prefix["payload"]["ledger"]["spent"],
            "reserved": prefix["payload"]["ledger"]["reserved"],
            "cached_assets": len(prefix["payload"]["store"]["assets"]),
        },
        "after_original_completion": {
            "spent": asdict(state["ledger"].spent),
            "reserved": asdict(state["ledger"].reserved),
            "cached_assets": len(state["store"].assets),
        },
        "pending_duration_was_not_guessed": True,
        "E_hindsight_reference_only": True,
    }
    publish(
        out / "RESIDUAL_GRAPH.json",
        {"graph": result.pop("graph"), "provenance": provenance},
    )
    publish(out / "JOINT_WITNESSES.json", witness_results)
    publish(
        out / "RESULT.json",
        {**result, "passed": True, "native_witness_replays": len(witness_results)},
    )
    return {
        "path": str(out),
        "lower_bound": result["lower_bound"],
        "upper_bound": result["upper_bound"],
        "states": result["explored_states"],
        "witnesses": len(witness_results),
        **provenance["before_original_completion"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    original = (
        root
        / "plans/v9_followup_execution_20260914_01/api_pilot_01/new_york__2025-01-06__1000"
    )
    data, bank = read(original / "DATA.json"), read(original / "BANK.json")
    cutoff = min(o["cutoff"] for o in data["opportunities"])
    data["opportunities"] = [o for o in data["opportunities"] if o["cutoff"] == cutoff]
    tids = {o["target_id"] for o in data["opportunities"]}
    oids = {o["opportunity_id"] for o in data["opportunities"]}
    for key in ("targets", "baseline_candidates", "baseline_withdrawals"):
        data[key] = [r for r in data[key] if r["target_id"] in tids]
    data["e_f_pairs"] = [p for p in data["e_f_pairs"] if p["opportunity_id"] in oids]
    qids = {q for p in data["e_f_pairs"] for q in p["query_ids"]}
    for key in ("query_catalog", "query_results"):
        data[key] = [r for r in data[key] if r["query_id"] in qids]
    publish(out / "DATA.json", data)
    publish(out / "BANK.json", bank)
    publish(
        out / "REGISTRATION.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "regions": ["new_york"],
            "cutoff": cutoff,
            "original_inputs": str(original),
            "request_budgets": [2, 3],
            "allocation": ["fixed_quota", "global_budget"],
            "authorization": ["target_private", "session_shared"],
            "model_calls": 0,
            "scope": "actual managed source prefixes and conditional finite E oracle; not a model gain",
        },
    )
    summary = []
    for budget in (2, 3):
        for allocation in ("fixed_quota", "global_budget"):
            for authorization in ("target_private", "session_shared"):
                case = out / f"b{budget}__{allocation}__{authorization}"
                case.mkdir()
                spool = case / "source_spool"
                spool.mkdir()
                backend = ArchiveSpoolSource(
                    spool,
                    {
                        "provider": "registered_native_archive",
                        "products_sha256": canonical_hash(data["query_results"]),
                    },
                    run_id=case.name,
                )
                config = read(original / "CONFIGS.json")["batch_program"]
                config.pop("execution_contract", None)
                config.update(
                    request_budget=budget,
                    selector_kind="round_robin",
                    allocation_mode=allocation,
                    authorization_mode=authorization,
                    predict=False,
                    admission_semantics="measurement.v3",
                    pending_timing_policy="lifecycle_wall_v1",
                )
                session = SessionCoordinator(data, bank, config, source_backend=backend)
                prefixes = []
                while not session.done:
                    session.step()
                    snapshot = session.snapshot()
                    if "pending_source" not in snapshot["payload"]:
                        continue
                    pending = snapshot["payload"]["pending_source"]
                    checkpoint = case / f"prefix_{len(prefixes):02d}.json"
                    session.persist(checkpoint)
                    prefixes.append(snapshot)
                    backend.claim_ready(
                        pending["receipt_id"], worker_id="native-disk-worker"
                    )
                    request = spool / (pending["ticket"]["remote_id"] + ".request.json")
                    command = [
                        sys.executable,
                        str(Path(__file__).parent / "native_source_worker.py"),
                        "--request",
                        str(request),
                        "--data",
                        str(out / "DATA.json"),
                    ]
                    with (case / f"worker_{len(prefixes):02d}.log").open("x") as log:
                        worker = subprocess.run(
                            command,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            timeout=60,
                            check=False,
                        )
                    publish(
                        case / f"worker_{len(prefixes):02d}.exit.json",
                        {
                            "exit_code": worker.returncode,
                            "command": command,
                            "request_sha256": digest(request),
                        },
                    )
                    if worker.returncode:
                        raise RuntimeError(
                            "Original native worker failed; retain its pending reservation"
                        )
                final = session.snapshot()
                publish(case / "FINAL_CHECKPOINT.json", final)
                publish(case / "REPORT.json", session.report)
                for index, prefix in enumerate(prefixes):
                    summary.append(
                        qualify(
                            prefix, final, data, bank, case / f"reference_{index:02d}"
                        )
                    )
    publish(
        out / "RESULT.json",
        {
            "passed": True,
            "prefixes": len(summary),
            "cases": 8,
            "native_worker_calls": len(summary),
            "model_calls": 0,
            "results": summary,
            "complete_general_concurrent_reference": False,
        },
    )


if __name__ == "__main__":
    main()
