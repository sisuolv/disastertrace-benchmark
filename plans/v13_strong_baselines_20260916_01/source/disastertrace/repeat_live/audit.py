"""Rebuild requests, acceptance and carriers from raw batches, not collector state."""

import math
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.constrained_eval import adapter, contract
from disastertrace.controlled.renderer import render_request
from disastertrace.controlled.schema import parse_decision
from disastertrace.local_eval.storage import inventory, read, seal, verify_seal, write
from disastertrace.repeat_eval import protocol

from . import package
from .backend import ORIGIN as MODEL_ORIGIN
from .backend import validate_observation


def reconstruct(execution, run, *, require_model=False):
    plan, datasets, slots = package.verify(execution)
    run = Path(run)
    tokenizer = package.tokenizer(execution, plan)
    claim = read(run / "claim.json")
    model = claim["mode"] == "model"
    if require_model and not model:
        raise ValueError("program diagnostics cannot be relabelled model results")
    if model and (
        not plan["generation_authorized"]
        or plan["fixture"]
        or claim["canonical_run_path"] != plan["run_path"]
    ):
        raise ValueError("model claim differs from live authorization")
    if (
        claim["execution_id"] != plan["execution_id"]
        or claim["origin"] != (MODEL_ORIGIN if model else "diagnostic_p6_live_fixture_v1")
        or claim["mode"]
        not in ("model", "correct", "invalid-control", "wrong-valid", "extraction-control")
        or claim["generation_authorized"] is not model
        or type(claim["additional_model_calls"]) is not int
        or claim["additional_model_calls"] != 0
        or claim["grammar_sampling_performed"] is not model
        or not isinstance(claim["canonical_run_path"], str)
        or not Path(claim["canonical_run_path"]).is_absolute()
    ):
        raise ValueError("unbound claim or diagnostic origin")
    last_time = datetime.fromisoformat(claim["started_at"])
    if last_time.tzinfo is None:
        raise ValueError("aware launch time required")
    by_id = {(condition, ep["episode_id"]): ep for condition, eps in datasets.items() for ep in eps}
    batches = list(protocol.batches(slots))
    carriers, last_accepted, traces, recognized, raw_ids = {}, {}, [], {"claim.json"}, set()
    runtime_path = run / "runtime.json"
    runtime = read(runtime_path) if runtime_path.exists() else None
    if model and runtime is not None:
        recognized.add("runtime.json")
        validate_observation(runtime["observation"])
        observed = runtime["observation"]
        bound = plan["preflight"]["result"]["runtime_observation"]
        if (
            runtime["execution_id"] != plan["execution_id"]
            or runtime["origin"] != MODEL_ORIGIN
            or runtime["chat_template_sha256"] != fingerprint(tokenizer.chat_template)
            # vLLM 0.10.2 wraps this tokenizer to cache vocabulary metadata only.
            or runtime["tokenizer_class"] != "Cached" + type(tokenizer).__name__
            or any(observed[k] != bound[k] for k in bound if k != "hostname")
        ):
            raise ValueError("runtime differs from the preflight-bound model environment")
        stamp = datetime.fromisoformat(runtime["ready_at"])
        if stamp.tzinfo is None or stamp < last_time:
            raise ValueError("runtime timestamp reordered")
        last_time = stamp
    unresolved, recovered, parsed_records, attempted = [], 0, 0, 0
    batch_seconds = 0.0
    intents = sorted((run / "intents").glob("*.json"))
    for index, path in enumerate(intents):
        if model and runtime is None:
            raise ValueError("model dispatch without bound runtime")
        if unresolved or index >= len(batches) or path.name != f"{index:04d}.json":
            raise ValueError("reordered batch or dispatch after unknown outcome")
        selected, intent = batches[index], read(path)
        if (
            intent["execution_id"] != plan["execution_id"]
            or intent["origin"] != claim["origin"]
            or intent["mode"] != claim["mode"]
            or intent["slots"] != selected
            or intent["batch_index"] != index
        ):
            raise ValueError("intent does not match reconstructed schedule")
        stamp = datetime.fromisoformat(intent["at"])
        if stamp.tzinfo is None or stamp < last_time:
            raise ValueError("intent timestamp reordered")
        last_time = stamp
        if model and stamp >= datetime.fromisoformat(plan["deadline_utc"]):
            raise ValueError("dispatch intent beyond fixed deadline")
        recognized.add(str(path.relative_to(run)))
        requests, preparations = [], []
        for slot in selected:
            previous, history = carriers.get(slot["trajectory_id"], (None, []))
            request = render_request(
                by_id[slot["condition"], slot["episode_id"]],
                slot["checkpoint_id"],
                method=slot["method"],
                previous=previous,
                history=history,
            )
            requests.append(request)
            preparations.append(protocol.prepare_request(request, slot, tokenizer))
        if requests != intent["requests"] or preparations != intent["prepared"]:
            raise ValueError("independent request, carrier, seed or token reconstruction differs")
        marker_path, raw_path = run / "started" / path.name, run / "raw" / path.name
        attempted += len(selected)
        if not marker_path.exists():
            if raw_path.exists():
                raise ValueError("raw response without dispatch marker")
            unresolved.extend(s["slot_id"] for s in selected)
            continue
        marker = read(marker_path)
        if (
            marker["execution_id"] != plan["execution_id"]
            or marker["intent_sha256"] != fingerprint(intent)
            or marker["state"]
            != ("model_generation_started" if model else "generation_started_program_only")
        ):
            raise ValueError("dispatch marker mismatch")
        recognized.add(str(marker_path.relative_to(run)))
        marker_time = datetime.fromisoformat(marker["at"])
        if marker_time.tzinfo is None or marker_time < last_time:
            raise ValueError("dispatch timestamp reordered")
        last_time = marker_time
        if not raw_path.exists():
            unresolved.extend(s["slot_id"] for s in selected)
            continue
        raw = read(raw_path)
        recognized.add(str(raw_path.relative_to(run)))
        if (
            raw["execution_id"] != plan["execution_id"]
            or raw["origin"] != claim["origin"]
            or raw["mode"] != claim["mode"]
            or raw["intent_sha256"] != fingerprint(intent)
            or raw["batch_index"] != index
            or not isinstance(raw["results"], list)
        ):
            raise ValueError("raw batch binding/cardinality mismatch")
        stamp = datetime.fromisoformat(raw["at"])
        if (
            stamp.tzinfo is None
            or stamp < last_time
            or type(raw["batch_wall_seconds"]) not in (int, float)
            or not math.isfinite(raw["batch_wall_seconds"])
            or raw["batch_wall_seconds"] < 0
        ):
            raise ValueError("raw timestamp or wall time invalid")
        last_time = stamp
        batch_seconds += raw["batch_wall_seconds"]
        by_attempt = {r["attempt_id"]: r for r in raw["results"]}
        if len(by_attempt) != len(raw["results"]) or not set(by_attempt) <= {
            s["attempt_id"] for s in selected
        }:
            raise ValueError("raw batch contains duplicate or unknown attempt identity")
        for slot, request, prep in zip(selected, requests, preparations):
            result = by_attempt.get(slot["attempt_id"])
            if result is None:
                unresolved.append(slot["slot_id"])
                continue
            if model:
                candidates = result.get("candidates", [])
                if (
                    result["runtime_request_id"] != slot["attempt_id"]
                    or len(candidates) != 1
                    or any(result.get(k) != v for k, v in candidates[0].items())
                    or candidates[0]["index"] != 0
                ):
                    raise ValueError("raw backend sample/identity mismatch")
            if result["runtime_request_id"] in raw_ids:
                raise ValueError("duplicate backend response identity")
            raw_ids.add(result["runtime_request_id"])
            tokens = result["output_token_ids"]
            if (
                result["prompt_token_ids"] != prep["prompt_token_ids"]
                or len(tokens) > 8192
                or any(type(t) is not int or t < 0 for t in tokens)
            ):
                raise ValueError("raw token bounds or prompt mismatch")
            if result["finish_reason"] not in ("stop", "length"):
                raise ValueError("unsupported termination")
            if result["finish_reason"] == "stop" and (
                not tokens or tokens[-1] not in adapter.terminal_ids(tokenizer)
            ):
                raise ValueError("stop output is not terminated")
            extracted = adapter.extract(tokens, tokenizer)
            if extracted["raw_text"] != result["runtime_output_text"]:
                raise ValueError("raw text differs from decoded tokens")
            previous, history = carriers.get(slot["trajectory_id"], (None, []))
            status, decision = "invalid", None
            try:
                decision = parse_decision(extracted["content"])
            except (ValueError, TypeError, KeyError, RecursionError):
                pass
            prior_checkpoint = last_accepted.get(slot["trajectory_id"])
            if decision is not None:
                status, previous, history = "ok", decision, history + [deepcopy(decision)]
                last_accepted[slot["trajectory_id"]] = slot["checkpoint_id"]
            expected_capture = {
                "slot_id": slot["slot_id"],
                "raw_sha256": fingerprint(raw),
                "extracted": extracted,
                "status": status,
                "state_after": previous,
                "output_validity": contract.inspect(extracted["content"]),
            }
            parsed = run / "parsed" / f"{slot['slot_index']:05d}.json"
            if parsed.exists():
                if read(parsed) != expected_capture:
                    raise ValueError("saved acceptance differs from raw reconstruction")
                parsed_records += 1
                recognized.add(str(parsed.relative_to(run)))
            else:
                recovered += 1
            carriers[slot["trajectory_id"]] = previous, history
            traces.append(
                {
                    **slot,
                    "request": request,
                    "request_hash": fingerprint(request),
                    "raw_response": extracted["content"],
                    "status": status,
                    "state_after": previous,
                    "prior_accepted_checkpoint": prior_checkpoint,
                    "model_kind": "local_model" if model else "diagnostic_program",
                    "eligible_for_llm_leaderboard": False,
                    "provider_requests": 0,
                    "output_validity": expected_capture["output_validity"],
                    "finish_reason": result["finish_reason"],
                    "prompt_tokens": len(prep["prompt_token_ids"]),
                    "completion_tokens": len(tokens),
                    "reasoning_tokens": extracted["reasoning_tokens"],
                    "content_tokens": extracted["content_tokens"],
                    "delimiter_tokens": extracted["delimiter_tokens"],
                    "terminal_tokens": extracted["terminal_tokens"],
                }
            )
    completion_path = run / "completion.json"
    completion = read(completion_path) if completion_path.exists() else None
    if completion is not None:
        recognized.add("completion.json")
        if (
            completion["execution_id"] != plan["execution_id"]
            or completion["origin"] != claim["origin"]
            or completion["attempted"] != attempted
            or completion["raw_received"] != len(traces)
            or completion["parsed_records"] != parsed_records
            or any(
                type(completion[k]) is not int
                for k in ("attempted", "raw_received", "parsed_records", "additional_model_calls")
            )
            or completion["additional_model_calls"] != (attempted if model else 0)
            or not isinstance(completion["stop_reason"], str)
            or completion["complete"]
            is not (parsed_records == len(slots) and completion["stop_reason"] == "complete")
            or (completion["stop_reason"] == "complete" and parsed_records != len(slots))
        ):
            raise ValueError("collector completion counters differ from raw evidence")
        stamp = datetime.fromisoformat(completion["at"])
        if stamp.tzinfo is None or stamp < last_time:
            raise ValueError("completion precedes capture")
    files = inventory(run)
    temporary = {
        name for name in files if Path(name).name.startswith(".") and name.endswith(".tmp")
    }
    if set(files) != recognized | temporary:
        raise ValueError("orphan or unrecognized run artifacts")
    if attempted > plan["planned_responses"] or (model and attempted > plan["max_model_attempts"]):
        raise ValueError("attempt budget exceeded")
    complete = len(traces) == len(slots) and not unresolved
    summary = {
        "execution_id": plan["execution_id"],
        "origin": claim["origin"],
        "mode": claim["mode"],
        "planned": len(slots),
        "attempted": attempted,
        "received": len(traces),
        "complete": complete,
        "outcome_unknown": len(unresolved),
        "unsubmitted": len(slots) - attempted,
        "raw_recovered_without_parsed_record": recovered,
        "parsed_records": parsed_records,
        "incomplete_infrastructure": not complete,
        "additional_model_calls": attempted if model else 0,
        "model_result": model,
        "batch_generation_wall_seconds": batch_seconds,
        "runtime": runtime,
        "uncertain_results_are_not_assumed_unsent": True,
        "temporary_uncommitted_files": sorted(temporary),
        "collector_completion": completion,
        "run_files": files,
    }
    summary["audit_id"] = fingerprint(summary)
    return {
        "plan": plan,
        "datasets": datasets,
        "slots": slots,
        "traces": traces,
        "summary": summary,
        "unresolved_slot_ids": unresolved,
    }


def report(execution, run, output):
    from .statistics import summarize

    output = Path(output)
    if output.exists():
        raise FileExistsError("review output already exists")
    result = reconstruct(execution, run)
    scores = summarize(result)
    output.mkdir(parents=True)
    write(output / "audit.json", result["summary"])
    write(output / "scores.json", scores)
    write(output / "trace.json", result["traces"])
    seal(output)
    return result["summary"]


def verify_report(execution, run, saved_report):
    from .statistics import summarize

    saved_report = Path(saved_report)
    verify_seal(saved_report)
    result = reconstruct(execution, run)
    for name, expected in (
        ("audit", result["summary"]),
        ("trace", result["traces"]),
        ("scores", summarize(result)),
    ):
        if read(saved_report / (name + ".json")) != expected:
            raise ValueError("saved report differs from independent reconstruction: " + name)
    return {
        "status": "passed",
        "audit_id": result["summary"]["audit_id"],
        "additional_model_calls": 0,
    }
