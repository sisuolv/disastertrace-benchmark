"""Reconstruct local captures independently from intents, tokens and public carriers."""

import itertools
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.controlled import renderer, scorer
from disastertrace.controlled.schema import METHODS, parse_decision

from . import adapter, execution
from .runtime import tokenizer_for
from .storage import inventory, read, seal, verify_seal, write


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("timezone required in execution observation")
    return result


def audit(execution_path, run, *, require_model=False):
    plan, episodes, slots = execution.verify(execution_path)
    run = Path(run)
    claim = read(run / "claim.json")
    last_observation = timestamp(claim["started_at"])
    origin = claim["origin"]
    if origin not in ("local_model_vllm", "diagnostic_fixture"):
        raise ValueError("unrecognized capture origin")
    real = origin == "local_model_vllm"
    if require_model and not real:
        raise ValueError("diagnostics cannot be relabeled as model outputs")
    if claim["execution_id"] != plan["execution_id"]:
        raise ValueError("claim execution mismatch")
    if real and claim["canonical_run_path"] != plan["run_path"]:
        raise ValueError("model run claim is not bound to the canonical run")
    tokenizer = tokenizer_for(execution_path, diagnostic=not real)
    runtime_file = run / "runtime.json"
    if runtime_file.exists():
        runtime = read(runtime_file)
        if timestamp(runtime["ready_at"]) < last_observation:
            raise ValueError("runtime time precedes launch")
        last_observation = timestamp(runtime["ready_at"])
        if runtime["origin"] != origin or runtime["chat_template_sha256"] != fingerprint(
            tokenizer.chat_template
        ):
            raise ValueError("runtime/tokenizer origin mismatch")
        if real and runtime["observation"]["environment_sha256"] != plan["environment_sha256"]:
            raise ValueError("runtime environment binding mismatch")
    else:
        runtime = None
    by_id = {ep["episode_id"]: ep for ep in episodes}
    carriers, traces, captures, attempted = {}, [], [], []
    pending = []
    size = plan["settings"]["batch_size"]
    batches = sorted((run / "batches").glob("*.json"))
    recognized = {"claim.json"}
    if runtime_file.exists():
        recognized.add("runtime.json")
    for index, path in enumerate(batches):
        if path.name != f"{index:03d}.json" or pending:
            raise ValueError("missing/reordered batch or collection after unresolved batch")
        if runtime is None:
            raise ValueError("dispatch without runtime observation")
        intent = read(path)
        started_at = timestamp(intent["started_at"])
        if started_at < last_observation or real and started_at >= timestamp(plan["deadline_utc"]):
            raise ValueError("batch time violates order or authorized deadline")
        last_observation = started_at
        expected_slots = slots[index * size : (index + 1) * size]
        if (
            not expected_slots
            or intent["slots"] != expected_slots
            or intent["batch_index"] != index
        ):
            raise ValueError("batch schedule mismatch")
        if intent["origin"] != origin or intent["execution_id"] != plan["execution_id"]:
            raise ValueError("batch provenance mismatch")
        if len(intent["requests"]) != len(expected_slots) or len(intent["prepared"]) != len(
            expected_slots
        ):
            raise ValueError("batch cardinality mismatch")
        recognized.add(str(path.relative_to(run)))
        for position, slot in enumerate(expected_slots):
            previous, history = carriers.get(slot["trajectory_id"], (None, []))
            request = renderer.render_request(
                by_id[slot["episode_id"]],
                slot["checkpoint_id"],
                method=slot["method"],
                previous=previous,
                history=history,
            )
            prep = adapter.prepare(request, slot, tokenizer, plan["settings"])
            if request != intent["requests"][position] or prep != intent["prepared"][position]:
                raise ValueError("public evidence, messages, seed, tokens or carrier mismatch")
            attempted.append(slot["slot_index"])
            capture_path = run / "captures" / f"{slot['slot_index']:04d}.json"
            if not capture_path.exists():
                pending.append(slot["slot_index"])
                continue
            if pending:
                raise ValueError("capture appears after missing persisted response")
            capture = read(capture_path)
            captured_at = timestamp(capture["captured_at"])
            if captured_at < last_observation:
                raise ValueError("capture time precedes prior observation")
            last_observation = captured_at
            recognized.add(str(capture_path.relative_to(run)))
            if (
                capture["origin"] != origin
                or capture["execution_id"] != plan["execution_id"]
                or capture["slot_index"] != slot["slot_index"]
                or capture["batch_index"] != index
                or capture["intent_sha256"] != fingerprint(intent)
                or capture["prepared_sha256"] != fingerprint(prep)
            ):
                raise ValueError("capture binding mismatch")
            result = capture["result"]
            if result["prompt_token_ids"] != prep["prompt_token_ids"]:
                raise ValueError("actual model prompt token mismatch")
            ids = result["output_token_ids"]
            if not isinstance(ids, list) or any(type(t) is not int or t < 0 for t in ids):
                raise ValueError("invalid output token inventory")
            if len(ids) > plan["settings"]["max_tokens"] or result["finish_reason"] not in (
                "stop",
                "length",
            ):
                raise ValueError("output cap/finish reason mismatch")
            if result["finish_reason"] == "length" and len(ids) != plan["settings"]["max_tokens"]:
                raise ValueError("unexpected early length termination")
            extracted = adapter.extract(ids, tokenizer)
            texts = {extracted["raw_text"]}
            if ids and ids[-1] in adapter.terminal_ids(tokenizer):
                texts.add(tokenizer.decode(ids[:-1], skip_special_tokens=False))
            if result["runtime_output_text"] not in texts:
                raise ValueError("runtime text/token decoding mismatch")
            if (
                extracted != capture["extracted"]
                or capture["prompt_tokens"] != len(prep["prompt_token_ids"])
                or capture["completion_tokens"] != len(ids)
            ):
                raise ValueError("content extraction/usage mismatch")
            if (
                not math.isfinite(capture["batch_wall_seconds"])
                or capture["batch_wall_seconds"] < 0
            ):
                raise ValueError("invalid batch duration")
            status = "invalid"
            try:
                decision = parse_decision(extracted["content"])
            except (ValueError, TypeError, KeyError, RecursionError):
                pass
            else:
                status, previous = "ok", decision
                history = history + [deepcopy(decision)]
            if capture["status"] != status or capture["state_after"] != previous:
                raise ValueError("capture acceptance/carrier mismatch")
            carriers[slot["trajectory_id"]] = (previous, history)
            captures.append(capture)
            traces.append(
                {
                    "episode_id": slot["episode_id"],
                    "checkpoint_id": slot["checkpoint_id"],
                    "method": slot["method"],
                    "request": request,
                    "request_hash": fingerprint(request),
                    "raw_response": extracted["content"],
                    "status": status,
                    "state_after": previous,
                    "model_kind": "local_model" if real else "diagnostic_program",
                    "eligible_for_llm_leaderboard": False,
                    "provider_requests": 0,
                    "local_model_calls": int(real),
                    "capture_sha256": fingerprint(capture),
                }
            )
    completion_path = run / "completion.json"
    completion = read(completion_path) if completion_path.exists() else None
    if completion is not None:
        if timestamp(completion["finished_at"]) < last_observation:
            raise ValueError("completion time precedes prior observation")
        recognized.add("completion.json")
        if (
            completion["execution_id"] != plan["execution_id"]
            or completion["origin"] != origin
            or completion["attempted"] != len(attempted)
            or completion["received"] != len(captures)
            or completion["complete"]
            != (len(captures) == len(slots) and completion["stop_reason"] == "complete")
        ):
            raise ValueError("completion record mismatch")
    files = inventory(run)
    if set(files) != recognized:
        raise ValueError("unexpected or orphan run artifacts")
    summary = {
        "schema_version": "local_gpu_audit_v1",
        "execution_id": plan["execution_id"],
        "origin": origin,
        "attempted": len(attempted),
        "received": len(captures),
        "planned": len(slots),
        "pending_slots": pending,
        "unsubmitted": len(slots) - len(attempted),
        "complete": completion is not None and completion["complete"],
        "stop_reason": completion["stop_reason"] if completion else "worker_exit_unobserved",
        "run_files": files,
        "runtime": runtime,
        "local_model_calls": len(attempted) if real else 0,
        "paid_api_calls": 0,
        "origin_attestation": "local_code_and_content_binding_no_hardware_attestation",
    }
    summary["audit_id"] = fingerprint(summary)
    return plan, episodes, slots, summary, traces, captures


def reconstruct(execution_path, run, *, require_model=False):
    plan, episodes, slots, summary, traces, captures = audit(
        execution_path, run, require_model=require_model
    )
    order = {
        (ep["episode_id"], cp["checkpoint_id"]): i
        for i, (ep, cp) in enumerate((ep, cp) for ep in episodes for cp in ep["checkpoints"])
    }
    methods = {}
    for method in METHODS:
        selected = sorted(
            (r for r in traces if r["method"] == method),
            key=lambda r: order[r["episode_id"], r["checkpoint_id"]],
        )
        missing = {
            (slots[i]["episode_id"], slots[i]["checkpoint_id"]): "attempted_unresolved"
            for i in summary["pending_slots"]
            if slots[i]["method"] == method
        }
        methods[method] = scorer._score_rows(episodes, selected, method, missing_status=missing)
    cells, rule = [], plan["reliability_rule"]
    for method in METHODS:
        for family, group in methods[method]["by_family"].items():
            value = group["metrics"]["schema_success"]
            length = sum(
                c["result"]["finish_reason"] == "length"
                for c in captures
                if slots[c["slot_index"]]["method"] == method
                and slots[c["slot_index"]]["family"] == family
            )
            cells.append(
                {
                    "method": method,
                    "family": family,
                    "schema_valid": value["numerator"],
                    "planned": value["denominator"],
                    "length_finishes": length,
                    "passed": value["denominator"] == rule["planned_per_family_method"]
                    and value["numerator"] >= rule["min_schema_valid"]
                    and length <= rule["max_length"],
                }
            )
    error_fields, error_actions = [], []
    for method, score in methods.items():
        for row in score["per_checkpoint"]:
            for field, result in row["slots"].items():
                if not result["grounded_correct"]:
                    error_fields.append(
                        {
                            "method": method,
                            "episode_id": row["episode_id"],
                            "checkpoint_id": row["checkpoint_id"],
                            "field": field,
                            **result,
                        }
                    )
            if not row["counts"]["action_correct"]:
                error_actions.append(
                    {
                        "method": method,
                        "episode_id": row["episode_id"],
                        "checkpoint_id": row["checkpoint_id"],
                        "status": row["status"],
                    }
                )
    paired = []
    for a, b in itertools.combinations(METHODS, 2):
        for group in plan["settings"].get("source_groups", ("AL092021", "AL062018", "AL052019")):
            counts = Counter()
            for left, right in zip(methods[a]["per_checkpoint"], methods[b]["per_checkpoint"]):
                if left["group_id"] == group:
                    x, y = left["counts"]["all_correct"], right["counts"]["all_correct"]
                    counts[
                        "both_correct"
                        if x and y
                        else "left_only"
                        if x
                        else "right_only"
                        if y
                        else "neither"
                    ] += 1
            paired.append(
                {
                    "left": a,
                    "right": b,
                    "source_group": group,
                    "counts": dict(counts),
                    "dependent_checkpoint_pairs": sum(counts.values()),
                }
            )
    token_totals = {
        key: sum(c[key] for c in captures) for key in ("prompt_tokens", "completion_tokens")
    }
    token_totals["total_tokens"] = sum(token_totals.values())
    token_totals.update(
        {
            key: sum(c["extracted"][key] for c in captures)
            for key in ("reasoning_tokens", "content_tokens", "delimiter_tokens", "terminal_tokens")
        }
    )
    result = {
        "schema_version": "local_balanced_report_v1",
        "execution_id": plan["execution_id"],
        "dataset_content_id": plan["dataset_content_id"],
        "audit_id": summary["audit_id"],
        "model": plan["settings"]["model_id"],
        "origin": summary["origin"],
        "complete": summary["complete"],
        "planned": len(slots),
        "attempted": summary["attempted"],
        "received": summary["received"],
        "unsubmitted": summary["unsubmitted"],
        "local_model_calls": summary["local_model_calls"],
        "paid_api_calls": 0,
        "heldout_model_calls": 0,
        "new_human_annotations": 0,
        "llm_judge": False,
        "eligible_for_llm_leaderboard": False,
        "reliability": {
            "rule": rule,
            "cells": cells,
            "thresholds_passed": summary["complete"] and all(c["passed"] for c in cells),
            "measured_model_reliability": summary["origin"] == "local_model_vllm"
            and summary["complete"],
        },
        "methods": methods,
        "paired_by_source": paired,
        "usage": token_totals,
        "finish_reasons": dict(Counter(c["result"]["finish_reason"] for c in captures)),
        "extraction_errors": dict(
            Counter(
                c["extracted"]["extraction_error"]
                for c in captures
                if c["extracted"]["extraction_error"]
            )
        ),
        "errors": {"fields": error_fields, "actions": error_actions},
        "interpretation": "Development only: three dependent source groups, one repeat; "
        "540-version scores must not be mixed into a ranking with historical 270-version scores.",
        "batch_timing_note": "Captured wall time is shared batch time, not per-request latency.",
        "gpu_cost_usd": None,
    }
    return {"audit.json": summary, "report.json": result, "trace.json": traces}


def report(execution_path, run, output, *, require_model=False, verify=False):
    output = Path(output)
    if output.exists() and not verify:
        raise ValueError("preserve prior report")
    files = reconstruct(execution_path, run, require_model=require_model)
    if verify:
        verify_seal(output)
        if set(inventory(output, exclude=("manifest.json",))) != set(files):
            raise ValueError("unexpected report artifact")
        for name, value in files.items():
            if read(output / name) != value:
                raise ValueError("independent report reconstruction mismatch: " + name)
    else:
        output.mkdir(parents=True, exist_ok=False)
        for name, value in files.items():
            write(output / name, value)
        seal(output)
    result = files["report.json"]
    return {
        "status": "passed",
        "complete": result["complete"],
        "received": result["received"],
        "audit_id": result["audit_id"],
        "model_calls": result["local_model_calls"],
    }
