"""Outcome-blind monitoring policies with shared accounting and fixed predictors."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict

from .calibration import predict
from .evidence import exists_report_support
from .resources import BudgetLedger, Cost
from .selection import SELECTOR_SYSTEM, parse_selection
from .state import Baseline, Event, MonitoringEngine
from .targets import Opportunity, TargetSpec, canonical_hash
from .views import EvidenceStore, selector_view

FORECAST_SYSTEM = """You evaluate a fixed future aviation-report target. Use only the supplied common full TAF and lawfully acquired report products. Encoded product intervals are exact only for the report definition, not physical truth. TEMPO is not probability 0.5. E describes current evidence; F is a future report. E uncertainty does not force F=0.5, and E sufficiency does not guarantee F predictability. E is supported if any registered neighbor slot is definitely below the target threshold. E is refuted only if all registered neighbor slots have been read with valid reports and all are definitely not below the threshold; missing or threshold-straddling slots otherwise leave it undetermined. TAF is not a neighbor observation. Return only JSON with probability (0..1), e_status (supported/refuted/undetermined/inconsistent), decision (override/follow/no_change), and citations (array of read report asset IDs). Always propose a probability, even when it will not be applied. override installs the proposed probability; follow clears any previous override and follows the latest common baseline; no_change retains the current explicit state, which can include an older override. In base_bound_override, a relevant baseline-context change invalidates an override and an in-flight candidate. In persistent_override, the previous override persists until explicit replacement, follow, or its expiry. The current_state shown belongs only to this target. Do not use future outcomes or other targets' private memory."""


def stable_rank(*parts):
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def parse_answer(raw):
    text = raw.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    elif text.startswith("```\n") and text.endswith("```"):
        text = text[4:-3].strip()
    value = json.loads(text)
    if (
        not isinstance(value, dict)
        or type(value.get("probability")) not in (float, int)
        or not math.isfinite(value["probability"])
        or not 0 <= value["probability"] <= 1
        or value.get("e_status") not in {"supported", "refuted", "undetermined", "inconsistent"}
        or value.get("decision") not in {"override", "follow", "no_change"}
        or not isinstance(value.get("citations"), list)
        or not all(isinstance(item, str) for item in value["citations"])
    ):
        raise ValueError("Model response violates the frozen output schema")
    return value


def run_session(
    data,
    bank,
    config,
    backend=None,
    journal=None,
    resource_journal=None,
    *,
    _resume=None,
    _max_ticks=None,
):
    """data contains provider archive inputs, never a future outcome table."""
    if _resume is not None and (journal is not None or resource_journal is not None):
        raise ValueError(
            "Restored branches use a fresh explicit checkpoint, not an old open journal"
        )
    if _max_ticks is not None and (type(_max_ticks) is not int or _max_ticks < 0):
        raise ValueError("Invalid tick bound")
    if config.get("query_limit_per_tick") is not None and (
        type(config["query_limit_per_tick"]) is not int or config["query_limit_per_tick"] < 0
    ):
        raise ValueError("Invalid branch query limit")
    if "outcomes" in data or "OUTCOMES" in data:
        raise ValueError("Evaluator outcomes cannot enter a policy session")
    session_runtime = config.get("session_runtime", "legacy_probability_v1")
    if session_runtime not in {"legacy_probability_v1", "typed_admission_v1"}:
        raise ValueError("Unknown session runtime")
    typed = session_runtime == "typed_admission_v1"
    if typed and (
        config.get("typed_head", "joint") not in {"e_only", "f_only", "joint"}
        or type(config.get("persistence_latency_ms", 1)) is not int
        or config.get("persistence_latency_ms", 1) < 0
    ):
        raise ValueError("Invalid typed head or persistence latency")
    program_prediction = config.get("program_prediction", "frequency_mapping")
    if program_prediction not in {"frequency_mapping", "neighbor_persistence"}:
        raise ValueError("Unknown registered cheap prediction program")
    if typed and program_prediction != "frequency_mapping":
        raise ValueError("Typed program only qualifies the frozen frequency predictor")
    if config["selector_kind"] == "llm":
        if (
            config["allocation_mode"] != "global_budget"
            or config["authorization_mode"] != "session_shared"
        ):
            raise ValueError("The LLM selector currently requires global/shared scope")
        if backend is None or config.get("isolation_mode") != "actual_cost_clock":
            raise ValueError("LLM selection requires a charged backend and actual cost clock")
    if config.get("isolation_mode", "actual_cost_clock") not in {
        "actual_cost_clock",
        "public_schedule",
    }:
        raise ValueError("Unknown timing isolation mode")
    if config.get("isolation_mode") == "public_schedule" and config.get("gate"):
        raise ValueError(
            "A private-value-dependent global gate is not allowed in the strict timing control"
        )
    opportunities = data["opportunities"]
    targets = {r["target_id"]: r for r in data["targets"]}
    pairs = {r["opportunity_id"]: r for r in data["e_f_pairs"]}
    catalog = {r["query_id"]: r for r in data["query_catalog"]}
    products = {r["query_id"]: r for r in data["query_results"]}
    target_objects = {key: TargetSpec(**value) for key, value in targets.items()}
    object_opportunities = [
        Opportunity(r["opportunity_id"], target_objects[r["target_id"]], r["cutoff"])
        for r in opportunities
    ]
    fallback = {key: predict(bank, value, None)["probability"] for key, value in targets.items()}
    if typed:
        from ..monitoring_fixed_v1.adaptive import TypedAviationRuntime

        runtime = TypedAviationRuntime(data, bank, config, journal=journal)
    else:
        runtime = MonitoringEngine(
            object_opportunities,
            fallback_probabilities=fallback,
            protocol=config["protocol"],
            journal=journal,
        )
    source_budget = config["request_budget"]
    total_calls_cap = config["forecast_call_cap"]
    model_call_budget = config.get("model_call_budget", total_calls_cap)
    resource_limits = {
        "requests": source_budget,
        "bytes": source_budget * 2048,
        "tokens": config.get("token_cap"),
        "compute_ms": config.get("compute_ms_cap"),
    }
    quota_order = sorted(targets, key=lambda key: stable_rank(config["seed"], "quota", key))
    quotas = {
        target: {
            "requests": source_budget // len(targets) + int(index < source_budget % len(targets)),
            "bytes": 2048
            * (source_budget // len(targets) + int(index < source_budget % len(targets))),
        }
        for index, target in enumerate(quota_order)
    }
    ledger = BudgetLedger(
        resource_limits,
        allocation_mode=config["allocation_mode"],
        quotas=quotas,
        journal=resource_journal,
    )
    store = EvidenceStore(config["authorization_mode"], targets)
    events, candidates, source_receipts = [], {}, []
    for withdrawal in data.get("baseline_withdrawals", []):
        if withdrawal["target_id"] in targets:
            events.append(
                Event(
                    "withdraw-" + stable_rank(withdrawal["target_id"], withdrawal["source_id"]),
                    withdrawal["available_at"],
                    "baseline_withdrawal",
                    {
                        "target_id": withdrawal["target_id"],
                        "product_revision_id": withdrawal["source_id"],
                        "reason": withdrawal["reason"],
                    },
                )
            )
    for candidate in data["baseline_candidates"]:
        target_id = candidate["target_id"]
        if target_id not in targets:
            continue
        identity = (target_id, candidate["source_id"])
        if identity in candidates:
            continue
        mapped = predict(bank, targets[target_id], candidate)
        baseline = Baseline(
            target_objects[target_id],
            candidate["source_id"],
            candidate["projection"],
            mapped["probability"],
            candidate["available_at"],
            candidate["valid_until"],
            bank["mapping_version"],
            "NWS_TAF_via_IEM_with_frozen_research_mapping",
            "fallback" if candidate.get("projection_status") == "unavailable" else "research",
        )
        candidates[identity] = candidate
        events.append(
            Event(
                "base-" + stable_rank(*identity),
                candidate["available_at"],
                "baseline",
                {"baseline": baseline},
            )
        )
    cutoffs = sorted({o["cutoff"] for o in opportunities})
    calls, frames, call_records, selector_records = 0, [], [], []
    start_tick = 0
    if _resume is None:
        runtime.run(events, until=cutoffs[0] - config["wakeup_seconds"] * 1_000_000 - 1)
    else:
        from .session_checkpoint import restore_session

        restored = restore_session(_resume, data, bank, config)
        runtime, ledger, store = (restored[k] for k in ("runtime", "ledger", "store"))
        start_tick = restored["next_tick"]
        calls, frames, call_records, selector_records, source_receipts = (
            restored[k]
            for k in ("calls", "frames", "call_records", "selector_records", "source_receipts")
        )

    def authorized(target_id, query_id):
        key = (
            query_id
            if config["authorization_mode"] == "session_shared"
            else target_id + "::" + query_id
        )
        return key, key in store.assets

    def disclosed(target_id, query_ids):
        visible = {r["content"]["query_id"]: r["content"] for r in store.view(target_id)}
        return {qid: visible[qid] for qid in query_ids if qid in visible}

    next_tick = start_tick
    for tick, cutoff in enumerate(cutoffs):
        if tick < start_tick:
            continue
        if _max_ticks is not None and tick >= start_tick + _max_ticks:
            break
        clock = cutoff - config["wakeup_seconds"] * 1_000_000
        runtime.run([], until=clock)
        clock = max(clock, (runtime._last_time or clock - 1) + 1)
        active = [o for o in opportunities if o["cutoff"] == cutoff]
        common = selector_view(
            {
                o["target_id"]: {
                    "baseline_probability": runtime._base(o["target_id"], clock)["probability"],
                    "deadline": cutoff,
                    "entity": targets[o["target_id"]]["entity"],
                    "public_query_ids": pairs[o["opportunity_id"]]["query_ids"],
                }
                for o in active
            }
        )
        selector = config["selector_kind"]
        if selector not in {"round_robin", "risk", "coverage", "batch_complete", "llm"}:
            raise ValueError("Unsupported selector; do not silently replace an LLM selector")
        if selector == "batch_complete" and (
            config["allocation_mode"] != "global_budget"
            or config["authorization_mode"] != "session_shared"
        ):
            raise ValueError("Complete-batch control requires global shared acquisition")
        ordered = sorted(
            active,
            key=lambda o: (
                -common[o["target_id"]]["baseline_probability"] if selector == "risk" else 0,
                stable_rank(config["seed"], tick, o["opportunity_id"]),
            ),
        )
        # Public calendar pacing carries unused credits forward; it does not use
        # future archive values or force identical per-target budgets.
        released_credit = source_budget * (tick + 1) // len(cutoffs)
        source_steps = []
        forecast_order = ordered[: config["per_tick_forecast_cap"]]
        selected_query_rank = None
        if selector == "llm":
            forecast_order, selected_query_rank = [], {}
            if calls + len(selector_records) < model_call_budget and clock < cutoff:
                select_id = "select-" + str(tick)
                upper = Cost(
                    tokens=config["input_token_cap"] + config["output_token_cap"],
                    compute_ms=config["call_compute_cap_ms"],
                )
                try:
                    ledger.reserve(select_id, upper, "session_selector")
                except ValueError:
                    pass
                else:
                    handles = {"t" + str(i): o for i, o in enumerate(ordered)}
                    query_ids = sorted(
                        {
                            q
                            for o in active
                            for q in pairs[o["opportunity_id"]]["query_ids"]
                            if q not in store.assets and catalog[q]["available_at"] <= clock
                        }
                    )
                    query_handles = {"q" + str(i): q for i, q in enumerate(query_ids)}
                    public_products = {}
                    for o in active:
                        view = runtime._base(o["target_id"], clock)
                        candidate = candidates.get((o["target_id"], view["product_revision_id"]))
                        if candidate is not None:
                            public_products[candidate["source_id"]] = candidate["raw"]
                    selection_request = {
                        "clock": clock,
                        "cutoff": cutoff,
                        "protocol": config["protocol"],
                        "forecast_call_upper": asdict(upper),
                        "remaining_resources_after_selection_reserve": {
                            dimension: None
                            if limit is None
                            else limit
                            - getattr(ledger.spent, dimension)
                            - getattr(ledger.reserved, dimension)
                            for dimension, limit in resource_limits.items()
                        },
                        "remaining_ticks": len(cutoffs) - tick,
                        "remaining_model_calls_after_this_selection": model_call_budget
                        - calls
                        - len(selector_records)
                        - 1,
                        "available_source_credit": released_credit
                        - ledger.spent.requests
                        - ledger.reserved.requests,
                        "remaining_total_source_budget": source_budget - ledger.spent.requests,
                        "per_tick_forecast_cap": config["per_tick_forecast_cap"],
                        "targets": {
                            h: {
                                "target": targets[o["target_id"]],
                                "opportunity_id": o["opportunity_id"],
                                "common": common[o["target_id"]],
                                "current_state": runtime.policy_state(o["target_id"], clock),
                            }
                            for h, o in handles.items()
                        },
                        "queries": {
                            h: {
                                "query_id": q,
                                "metadata": catalog[q],
                                "serves_target_handles": [
                                    t
                                    for t, o in handles.items()
                                    if q in pairs[o["opportunity_id"]]["query_ids"]
                                ],
                            }
                            for h, q in query_handles.items()
                        },
                        "common_full_taf_products": public_products,
                        "shared_recent_products": [
                            a
                            for a in store.view(active[0]["target_id"])
                            if catalog[a["content"]["query_id"]]["slot_end"]
                            >= cutoff - 4 * 3600 * 1_000_000
                        ],
                    }
                    raw, details = backend(SELECTOR_SYSTEM, selection_request, select_id)
                    error = None
                    try:
                        answer = parse_selection(
                            raw,
                            query_handles=query_handles,
                            target_handles=handles,
                            forecast_cap=config["per_tick_forecast_cap"],
                        )
                        if not details.get("ended_with_eos", True):
                            raise ValueError("Selector generation did not finish with EOS")
                    except (ValueError, TypeError, json.JSONDecodeError) as exc:
                        answer = {"query_order": [], "forecast_handles": []}
                        error = str(exc)
                    duration = max(1, math.ceil(details["seconds"] * 1_000_000))
                    ledger.settle(
                        select_id,
                        Cost(
                            tokens=details["input_tokens"] + details["output_tokens"],
                            compute_ms=math.ceil(duration / 1000),
                        ),
                        outcome="completed" if error is None else "invalid_response",
                    )
                    selector_records.append(
                        {
                            "call_id": select_id,
                            "started_at": clock,
                            "completed_at": clock + duration,
                            "request_sha256": canonical_hash(selection_request),
                            "raw": raw,
                            "response_error": error,
                            "selection": answer,
                            "details": details,
                        }
                    )
                    clock += duration
                    runtime.run([], until=clock)
                    selected_query_rank = {
                        query_handles[h]: i for i, h in enumerate(answer["query_order"])
                    }
                    forecast_order = [handles[h] for h in answer["forecast_handles"]]
        acquire_this_tick = config.get("acquire", True)
        if selector == "batch_complete":
            pending = {
                q
                for o in active
                for q in pairs[o["opportunity_id"]]["query_ids"]
                if q not in store.assets and catalog[q]["available_at"] <= clock
            }
            # Batching uses public query topology, not the undisclosed values or
            # the evaluator's sufficient-recipe oracle. Unused credit carries.
            acquire_this_tick = acquire_this_tick and (
                released_credit - ledger.spent.requests - ledger.reserved.requests >= len(pending)
            )
        if (
            acquire_this_tick
            and calls < total_calls_cap
            and calls + len(selector_records) < model_call_budget
        ):
            while (
                ledger.spent.requests + ledger.reserved.requests < released_credit
                and clock < cutoff
                and (
                    config.get("query_limit_per_tick") is None
                    or len(source_steps) < config["query_limit_per_tick"]
                )
            ):
                options = []
                for order_index, opportunity in enumerate(ordered):
                    target_id = opportunity["target_id"]
                    for qid in pairs[opportunity["opportunity_id"]]["query_ids"]:
                        key, cached = authorized(target_id, qid)
                        if cached or catalog[qid]["available_at"] > clock:
                            continue
                        if selected_query_rank is not None and qid not in selected_query_rank:
                            continue
                        if clock + catalog[qid]["latency_ms"] * 1000 > cutoff:
                            continue
                        coverage = sum(
                            qid in pairs[o["opportunity_id"]]["query_ids"] for o in active
                        )
                        options.append(
                            (
                                -coverage
                                if selector == "coverage"
                                else selected_query_rank[qid]
                                if selector == "llm"
                                else 0,
                                order_index,
                                stable_rank(config["seed"], tick, qid),
                                target_id,
                                qid,
                                key,
                            )
                        )
                acquired = False
                for _, _, _, target_id, qid, key in sorted(options):
                    receipt_id = "query-" + stable_rank(key)
                    upper = Cost(requests=1, bytes=2048, compute_ms=100)
                    try:
                        ledger.reserve(receipt_id, upper, target_id)
                    except ValueError:
                        continue
                    result = json.loads(json.dumps(products[qid], allow_nan=False))
                    size = len(json.dumps(result, separators=(",", ":")).encode())
                    if size > 2048:
                        raise ValueError(
                            "Disclosed product exceeds frozen per-query byte reservation"
                        )
                    clock += catalog[qid]["latency_ms"] * 1000
                    ledger.settle(
                        receipt_id,
                        Cost(requests=1, bytes=size, compute_ms=100),
                        outcome="completed",
                    )
                    store.register(key, result, owner=target_id, receipt_id=receipt_id)
                    receipt = {
                        "query_id": qid,
                        "asset_id": key,
                        "payer": target_id,
                        "receipt_id": receipt_id,
                        "completed_at": clock,
                        "source_status": result["status"],
                        "bytes": size,
                        **(
                            {
                                "started_at": clock - catalog[qid]["latency_ms"] * 1000,
                                "timing_basis": "declared_archive_query_latency",
                            }
                            if typed
                            else {}
                        ),
                    }
                    source_receipts.append(receipt)
                    source_steps.append(receipt)
                    acquired = True
                    break
                if not acquired:
                    break
        frame_calls = []
        runtime.run([], until=clock)
        if config.get("predict", True):
            for opportunity in forecast_order:
                if (
                    calls >= total_calls_cap
                    or calls + len(selector_records) >= model_call_budget
                    or clock >= cutoff
                ):
                    break
                target_id, opp_id = opportunity["target_id"], opportunity["opportunity_id"]
                target, pair = targets[target_id], pairs[opp_id]
                relevant = disclosed(target_id, pair["query_ids"])
                view_base = runtime._base(target_id, clock)
                candidate = candidates.get((target_id, view_base["product_revision_id"]))
                mapped = predict(bank, target, candidate, pair["query_ids"], relevant)
                expected_e = exists_report_support(pair["query_ids"], relevant, pair["threshold_m"])
                if (
                    config.get("gate") == "capacity_revise_defer"
                    and abs(mapped["probability"] - view_base["probability"]) < 0.025
                ):
                    continue
                call_id = "forecast-" + str(calls)
                upper = Cost(
                    tokens=config["input_token_cap"] + config["output_token_cap"],
                    compute_ms=config["call_compute_cap_ms"],
                )
                try:
                    ledger.reserve(call_id, upper, target_id)
                except ValueError:
                    break
                calls += 1
                started = clock + 1
                if typed:
                    if started >= cutoff:
                        ledger.settle(call_id, Cost(), outcome="not_started_at_cutoff")
                        calls -= 1
                        break
                    call_record, clock = runtime.execute(
                        opportunity, call_id, started, store, ledger, source_receipts, backend
                    )
                    call_records.append(call_record)
                    frame_calls.append(call_record)
                    continue
                runtime.run(
                    [
                        Event(
                            call_id + "-begin",
                            started,
                            "begin",
                            {"call_id": call_id, "target_id": target_id},
                        )
                    ],
                    until=started,
                )
                base_view = runtime.calls[call_id]["baseline_snapshot"]
                candidate = candidates.get((target_id, base_view["product_revision_id"]))
                mapped = predict(bank, target, candidate, pair["query_ids"], relevant)
                visible_assets = [
                    r
                    for r in store.view(target_id)
                    if r["content"]["query_id"] in pair["query_ids"]
                ]
                request = {
                    "opportunity_id": opp_id,
                    "target": target,
                    "clock": started,
                    "cutoff": cutoff,
                    "protocol": config["protocol"],
                    "common_baseline": base_view,
                    "current_state": runtime.policy_state(target_id, started),
                    "full_native_taf": None if candidate is None else candidate["raw"],
                    "e_predicate": pair["e_predicate"],
                    "registered_query_ids": pair["query_ids"],
                    "read_evidence": visible_assets,
                    "unread_queries": [q for q in pair["query_ids"] if q not in relevant],
                    "expected_output_schema": {
                        "probability": "number 0..1",
                        "e_status": "supported/refuted/undetermined/inconsistent",
                        "decision": "override/follow/no_change",
                        "citations": "read asset IDs only",
                    },
                }
                if backend is None:
                    probability = mapped["probability"]
                    if program_prediction == "neighbor_persistence":
                        probability = (
                            1.0
                            if expected_e == "supported"
                            else 0.0
                            if expected_e == "refuted"
                            else base_view["probability"]
                        )
                    answer = {
                        "probability": probability,
                        "e_status": expected_e,
                        "decision": "override",
                        "citations": [r["asset_id"] for r in visible_assets],
                    }
                    raw = json.dumps(answer, separators=(",", ":"))
                    details = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "seconds": 0.001,
                        "ended_with_eos": True,
                        "backend": "fixed_development_frequency_program"
                        if program_prediction == "frequency_mapping"
                        else "deterministic_neighbor_persistence_program",
                    }
                else:
                    raw, details = backend(FORECAST_SYSTEM, request, call_id)
                error = None
                try:
                    answer = parse_answer(raw)
                    if not details.get("ended_with_eos", True):
                        raise ValueError("Generation did not finish with EOS")
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    answer = {
                        "probability": None,
                        "e_status": None,
                        "decision": "override",
                        "citations": [],
                    }
                    error = str(exc)
                actual_duration = max(1, math.ceil(details["seconds"] * 1_000_000))
                duration = actual_duration
                if config.get("isolation_mode") == "public_schedule":
                    duration = config["public_call_slot_ms"] * 1000
                    if actual_duration > duration:
                        raise ValueError(
                            "Actual call exceeds the public isolation slot; control is invalid"
                        )
                details = dict(
                    details,
                    archive_duration_us=duration,
                    actual_duration_us=actual_duration,
                    clock_mode=config.get("isolation_mode", "actual_cost_clock"),
                )
                clock = started + duration
                actual = Cost(
                    tokens=details["input_tokens"] + details["output_tokens"],
                    compute_ms=math.ceil(actual_duration / 1000),
                )
                ledger.settle(
                    call_id, actual, outcome="completed" if error is None else "invalid_response"
                )
                runtime.run(
                    [
                        Event(
                            call_id + "-complete",
                            clock,
                            "candidate",
                            {
                                "call_id": call_id,
                                "probability": answer["probability"],
                                "decision": answer["decision"],
                                "raw": raw,
                                "expires_at": max(
                                    o["cutoff"]
                                    for o in opportunities
                                    if o["target_id"] == target_id
                                ),
                            },
                        )
                    ],
                    until=clock,
                )
                call_record = {
                    "call_id": call_id,
                    "opportunity_id": opp_id,
                    "started_at": started,
                    "completed_at": clock,
                    "expected_e_from_disclosed_products": expected_e,
                    "reported_e": answer["e_status"],
                    "decision": answer["decision"],
                    "proposed_probability": answer["probability"],
                    "response_error": error,
                    "citation_errors": [
                        c
                        for c in answer["citations"]
                        if c not in {r["asset_id"] for r in visible_assets}
                    ],
                    "evidence_query_ids": sorted(relevant),
                    "details": details,
                    "raw": raw,
                }
                call_records.append(call_record)
                frame_calls.append(call_record)
        if runtime._last_time is None or runtime._last_time < cutoff:
            runtime.run([], until=cutoff)
        statuses = {
            o["opportunity_id"]: exists_report_support(
                pairs[o["opportunity_id"]]["query_ids"],
                disclosed(o["target_id"], pairs[o["opportunity_id"]]["query_ids"]),
                o["threshold_m"],
            )
            for o in active
        }
        frames.append(
            {
                "cutoff": cutoff,
                "public_selector_view": common,
                "source_steps": source_steps,
                "call_ids": [r["call_id"] for r in frame_calls],
                "e_statuses": statuses,
                "spent": asdict(ledger.spent),
                "reserved": asdict(ledger.reserved),
            }
        )
        next_tick = tick + 1
    if next_tick == len(cutoffs) and (not typed or runtime._last_time < cutoffs[-1]):
        runtime.run([], until=cutoffs[-1])
    checkpoint = None
    if _max_ticks is not None:
        from .session_checkpoint import capture_session

        checkpoint = capture_session(locals(), next_tick)
    return {
        "config": config,
        "snapshots": list(runtime.snapshots.values()),
        "attempts": runtime.attempts,
        "state_audit": runtime.audit,
        "calls": call_records,
        "selector_calls": selector_records,
        "actual_model_calls": 0 if backend is None else len(call_records) + len(selector_records),
        "frames": frames,
        "source_receipts": source_receipts,
        "resource_spent": asdict(ledger.spent),
        "resource_reserved": asdict(ledger.reserved),
        "resource_events": ledger.events,
        "e_counts": dict(Counter(s for frame in frames for s in frame["e_statuses"].values())),
        "event_replay": runtime.export(),
        "outcome_table_accessed_by_policy": False,
        **({"session_checkpoint": checkpoint} if checkpoint is not None else {}),
    }
