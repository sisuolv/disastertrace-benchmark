"""One-use paired model collection with durable raw batches and isolated carriers."""

import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.constrained_eval import adapter, contract
from disastertrace.controlled import renderer
from disastertrace.controlled.schema import parse_decision
from disastertrace.local_eval.storage import now
from disastertrace.repeat_eval import protocol
from disastertrace.repeat_eval.runtime import FixtureBackend
from disastertrace.repeat_eval.storage import atomic_write

from . import package
from .backend import ORIGIN as MODEL_ORIGIN
from .backend import VLLMBackend

ORIGIN = "diagnostic_p6_live_fixture_v1"
MODES = ("correct", "invalid-control", "wrong-valid", "extraction-control")


def collect(execution, output, *, mode="correct", fault=None):
    if mode not in (*MODES, "model"):
        raise ValueError("offline candidate has no model dispatch authorization")
    if fault not in (None, "before_raw", "after_raw", "after_first_parse", "partial_raw"):
        raise ValueError("unknown diagnostic fault")
    plan, datasets, slots = package.verify(execution)
    output = Path(output).resolve()
    model = mode == "model"
    origin = MODEL_ORIGIN if model else ORIGIN
    if model:
        if (
            not plan["generation_authorized"]
            or str(output) != plan["run_path"]
            or plan["fixture"]
            or fault is not None
        ):
            raise ValueError("model dispatch requires the exact fresh live scope")
        if datetime.fromisoformat(now()) >= datetime.fromisoformat(plan["deadline_utc"]):
            raise ValueError("model execution deadline passed")
    elif str(output) == plan["run_path"]:
        raise ValueError("diagnostics cannot consume the production run")
    if output.exists():
        raise FileExistsError("run directory consumes its launch")
    reservation = Path(plan["registry_path"]) / (plan["execution_id"] + "-" + mode + ".json")
    claim = {
        "execution_id": plan["execution_id"],
        "origin": origin,
        "mode": mode,
        "canonical_run_path": str(output),
        "started_at": now(),
        "generation_authorized": model,
        "additional_model_calls": 0,
        "grammar_sampling_performed": model,
    }
    atomic_write(reservation, claim)
    output.mkdir(parents=True, exist_ok=False)
    atomic_write(output / "claim.json", claim)
    by_id = {(condition, ep["episode_id"]): ep for condition, eps in datasets.items() for ep in eps}
    carriers, attempted, received, parsed_count = {}, 0, 0, 0
    stop = "complete"
    begin_run = time.monotonic()
    try:
        tokenizer = package.tokenizer(execution, plan)
        backend = (
            VLLMBackend(execution, plan["settings"]) if model else FixtureBackend(tokenizer, mode)
        )
        if model:
            tokenizer = backend.tokenizer
            atomic_write(
                output / "runtime.json",
                {
                    "execution_id": plan["execution_id"],
                    "origin": origin,
                    "ready_at": now(),
                    "observation": backend.observation,
                    "tokenizer_class": type(tokenizer).__name__,
                    "chat_template_sha256": fingerprint(tokenizer.chat_template),
                },
            )
        for index, selected in enumerate(protocol.batches(slots)):
            if model and (
                datetime.fromisoformat(now()) >= datetime.fromisoformat(plan["deadline_utc"])
                or time.monotonic() - begin_run >= plan["max_worker_seconds"]
            ):
                stop = "deadline_before_next_batch"
                break
            requests, prepared = [], []
            for slot in selected:
                previous, history = carriers.get(slot["trajectory_id"], (None, []))
                request = renderer.render_request(
                    by_id[slot["condition"], slot["episode_id"]],
                    slot["checkpoint_id"],
                    method=slot["method"],
                    previous=previous,
                    history=history,
                )
                requests.append(request)
                prepared.append(protocol.prepare_request(request, slot, tokenizer))
            if model and datetime.fromisoformat(now()) >= datetime.fromisoformat(
                plan["deadline_utc"]
            ):
                stop = "deadline_after_request_preparation"
                break
            intent = {
                "execution_id": plan["execution_id"],
                "origin": origin,
                "mode": mode,
                "batch_index": index,
                "at": now(),
                "slots": selected,
                "requests": requests,
                "prepared": prepared,
            }
            atomic_write(output / "intents" / f"{index:04d}.json", intent)
            attempted += len(selected)
            marker = {
                "execution_id": plan["execution_id"],
                "intent_sha256": fingerprint(intent),
                "at": now(),
                "state": "model_generation_started" if model else "generation_started_program_only",
            }
            atomic_write(output / "started" / f"{index:04d}.json", marker)
            begin = time.monotonic()
            results = backend.generate(prepared)
            if fault == "partial_raw":
                results = results[::2]
            if fault == "before_raw":
                raise RuntimeError("injected before raw durability")
            raw = {
                "execution_id": plan["execution_id"],
                "origin": origin,
                "mode": mode,
                "batch_index": index,
                "intent_sha256": fingerprint(intent),
                "at": now(),
                "batch_wall_seconds": time.monotonic() - begin,
                "results": results,
                "backend_error": getattr(backend, "last_error", None),
            }
            # Persist every returned item before extraction, validation or carrier promotion.
            atomic_write(output / "raw" / f"{index:04d}.json", raw)
            received += len(results)
            if fault == "after_raw":
                raise RuntimeError("injected after raw durability")
            by_attempt = {r["attempt_id"]: r for r in results}
            if len(by_attempt) != len(results) or not set(by_attempt) <= {
                s["attempt_id"] for s in selected
            }:
                raise ValueError("raw response identity mismatch")
            for slot, prep in zip(selected, prepared):
                result = by_attempt.get(slot["attempt_id"])
                if result is None:
                    continue
                if model and (
                    result.get("runtime_request_id") != slot["attempt_id"]
                    or len(result.get("candidates", [])) != 1
                ):
                    raise ValueError("model result identity or sample count differs")
                if result["prompt_token_ids"] != prep["prompt_token_ids"]:
                    raise ValueError("backend returned a different prompt")
                extracted = adapter.extract(result["output_token_ids"], tokenizer)
                previous, history = carriers.get(slot["trajectory_id"], (None, []))
                status, decision = "invalid", None
                try:
                    decision = parse_decision(extracted["content"])
                except (ValueError, TypeError, KeyError, RecursionError):
                    pass
                if decision is not None:
                    status, previous, history = "ok", decision, history + [deepcopy(decision)]
                capture = {
                    "slot_id": slot["slot_id"],
                    "raw_sha256": fingerprint(raw),
                    "extracted": extracted,
                    "status": status,
                    "state_after": previous,
                    "output_validity": contract.inspect(extracted["content"]),
                }
                atomic_write(output / "parsed" / f"{slot['slot_index']:05d}.json", capture)
                parsed_count += 1
                carriers[slot["trajectory_id"]] = (previous, history)
                if fault == "after_first_parse":
                    raise RuntimeError("injected after first parsed response")
            if raw["backend_error"]:
                raise RuntimeError("backend stopped: " + raw["backend_error"])
            if len(results) != len(selected):
                raise RuntimeError("partial raw batch; stop with unresolved slots")
    except BaseException as exc:
        stop = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        atomic_write(
            output / "completion.json",
            {
                "execution_id": plan["execution_id"],
                "origin": origin,
                "at": now(),
                "stop_reason": stop,
                "attempted": attempted,
                "raw_received": received,
                "parsed_records": parsed_count,
                "complete": parsed_count == len(slots) and stop == "complete",
                "additional_model_calls": attempted if model else 0,
                "worker_wall_seconds": time.monotonic() - begin_run,
            },
        )
    return {
        "attempted": attempted,
        "received": received,
        "parsed": parsed_count,
        "additional_model_calls": attempted if model else 0,
    }
