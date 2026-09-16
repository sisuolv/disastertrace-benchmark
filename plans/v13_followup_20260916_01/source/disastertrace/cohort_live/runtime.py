"""One-use worker, durable intents and raw-first capture of complete or stopped prefixes."""

import os
from collections import defaultdict
from pathlib import Path

from disastertrace.forecast_task.common import fingerprint
from disastertrace.forecast_task.protocol import request

from . import package, profiles
from .backend import DIAGNOSTIC_ORIGIN, MODEL_ORIGIN
from .storage import now, write


def binding(plan, worker, mode, run):
    if type(worker) is not int or worker not in range(2):
        raise ValueError("worker must be 0 or 1")
    return {
        "execution_id": plan["execution_id"],
        "phase_id": plan["phase_id"],
        "worker_id": worker,
        "mode": mode,
        "run_path": str(Path(run).resolve()),
        "origin": MODEL_ORIGIN if mode == "model" else DIAGNOSTIC_ORIGIN,
    }


def validate_mode(plan, mode, root):
    if mode == "model":
        if plan["kind"] != "model" or not plan["generation_authorized"]:
            raise ValueError("model dispatch requires a fresh live freeze")
        if str(Path(root).resolve()) != plan["run_root"]:
            raise ValueError("model canonical run root differs")
    elif mode != "diagnostic" or plan["kind"] != "diagnostic":
        raise ValueError("diagnostic/model origin mixing forbidden")


def collect(root, run_root, worker, *, mode="diagnostic", backend=None, tokenizer=None, fault=None):
    root, run_root = Path(root), Path(run_root)
    plan, public, slots = package.verify(root, code=True)
    adapter = profiles.adapter_for(plan)
    validate_mode(plan, mode, run_root)
    if mode == "model":
        from .provenance import validate_request

        request_path = os.environ.get("FORECAST_WORKER_REQUEST")
        if not request_path:
            raise ValueError("model collection requires its actual ACP request")
        validate_request(request_path, plan, worker)
    run = run_root / f"worker-{worker}"
    identity = binding(plan, worker, mode, run)
    claim = {**identity, "created_at": now()}
    write(run_root / "registry" / f"worker-{worker}.json", claim)
    run.mkdir(parents=True, exist_ok=False)
    write(run / "manifest.json", {**claim, "claim_sha256": fingerprint(claim)})
    histories, attempted, returned, parsed = defaultdict(list), 0, 0, 0
    error, stop = None, "complete"
    try:
        if mode == "model":
            if backend is not None or tokenizer is not None or fault is not None:
                raise ValueError("model path forbids injected diagnostic components")
            from .backend import VLLMBackend

            backend = VLLMBackend(root)
            tokenizer = backend.tokenizer
        else:
            tokenizer = tokenizer or package.tokenizer_for(root)
            if backend is None:
                from .backend import ProgramBackend

                backend = ProgramBackend(tokenizer)
        if backend.origin != identity["origin"]:
            raise ValueError("backend origin differs")
        write(run / "runtime.json", {**identity, "at": now(), "observation": backend.observation})
        for batch_index, batch in enumerate(package.batches(slots, public, worker)):
            if package.past_deadline(plan):
                stop = "phase_deadline"
                break
            prepared = [
                adapter.prepare(
                    request(
                        public, s["opportunity_id"], s["method"], histories[s["trajectory_id"]]
                    ),
                    s,
                    tokenizer,
                )
                for s in batch
            ]
            folder = run / "batches" / f"{batch_index:06d}"
            intent = {**identity, "batch_index": batch_index, "prepared": prepared, "at": now()}
            write(folder / "intent.json", intent)
            if fault == "before_started":
                raise RuntimeError("injected interruption before dispatch marker")
            if package.past_deadline(plan):
                stop = "phase_deadline"
                break
            write(
                folder / "started.json",
                {**identity, "intent_sha256": fingerprint(intent), "at": now()},
            )
            attempted += len(batch)
            results = backend.generate(prepared)
            if fault == "before_raw":
                raise RuntimeError("injected interruption before raw publication")
            raw = {
                **identity,
                "intent_sha256": fingerprint(intent),
                "at": now(),
                "results": results,
                "backend_error": backend.last_error,
            }
            write(folder / "raw.json", raw)
            returned += len(results)
            if fault == "after_raw":
                raise RuntimeError("injected interruption after raw publication")
            by_id = {r["attempt_id"]: r for r in results}
            if len(by_id) != len(results) or not set(by_id) <= {p["attempt_id"] for p in prepared}:
                raise ValueError("duplicate or unknown returned attempt")
            for item, slot in zip(prepared, batch):
                result = by_id.get(item["attempt_id"])
                if result is None:
                    continue
                capture = adapter.parse_result(
                    result, item, tokenizer, diagnostic=mode == "diagnostic"
                )
                record = {
                    **identity,
                    "attempt_id": slot["attempt_id"],
                    "capture": capture,
                    "raw_sha256": fingerprint(raw),
                    "at": now(),
                }
                write(folder / "parsed" / (slot["attempt_id"] + ".json"), record)
                parsed += 1
                histories[slot["trajectory_id"]].append(
                    {
                        "checkpoint_id": public["opportunities"][slot["opportunity_id"]][
                            "checkpoint_id"
                        ],
                        "final_text": capture["final_text"],
                    }
                )
                if fault == "after_first_parse":
                    raise RuntimeError("injected interruption after one parsed publication")
            print(
                {
                    "worker": worker,
                    "batch": batch_index,
                    "attempted": attempted,
                    "returned": returned,
                    "parsed": parsed,
                },
                flush=True,
            )
            if backend.last_error or len(results) != len(batch):
                stop = "backend_error_or_partial_batch"
                break
    except BaseException as exc:  # noqa: BLE001 - preserve terminal collector status
        stop, error = "exception", type(exc).__name__ + ": " + str(exc)
    finally:
        result = {
            **identity,
            "at": now(),
            "stop_reason": stop,
            "error": error,
            "attempted": attempted,
            "raw_returned": returned,
            "parsed_saved": parsed,
        }
        write(run / "completion.json", result)
    return result
