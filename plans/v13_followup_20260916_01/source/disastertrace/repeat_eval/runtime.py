"""Raw-first repeat collector exercised only by declared public program backends."""

import time
from copy import deepcopy
from pathlib import Path

from disastertrace.automated.common import fingerprint, strict_json
from disastertrace.constrained_eval import adapter, contract
from disastertrace.controlled import public_oracle, renderer
from disastertrace.controlled.schema import empty_decision, parse_decision
from disastertrace.local_eval.storage import now

from . import package, protocol
from .storage import atomic_write

ORIGIN = "diagnostic_p6_repeat_fixture_v1"
MODES = ("correct", "invalid-control", "wrong-valid", "extraction-control")


class FixtureBackend:
    def __init__(self, tokenizer, mode):
        self.tokenizer, self.mode, self.calls = tokenizer, mode, 0

    def generate(self, prepared):
        results = []
        for index, item in enumerate(prepared):
            request = strict_json(item["messages"][1]["content"])
            decision = public_oracle.answer(request)
            at_c2 = request["checkpoint_time"].endswith("00:02:00+00:00")
            if self.mode == "wrong-valid" and at_c2:
                decision = empty_decision()
            text = contract.serialize_fixture(decision)
            if self.mode == "invalid-control" and at_c2:
                text = "{invalid diagnostic"
            reasoning = self.tokenizer.encode(
                "Program fixture, no model inference.", add_special_tokens=False
            )
            close = self.tokenizer.encode("</think>", add_special_tokens=False)
            if self.mode == "extraction-control" and index == 0:
                close = []
            tokens = (
                reasoning
                + close
                + self.tokenizer.encode(text, add_special_tokens=False)
                + [self.tokenizer.eos_token_id]
            )
            results.append(
                {
                    "attempt_id": item["attempt_id"],
                    "runtime_request_id": f"fixture-{self.calls}-{index}",
                    "prompt_token_ids": item["prompt_token_ids"],
                    "output_token_ids": tokens,
                    "runtime_output_text": self.tokenizer.decode(tokens, skip_special_tokens=False),
                    "finish_reason": "stop",
                    "stop_reason": None,
                }
            )
        self.calls += 1
        return results


def collect(execution, output, *, mode="correct", fault=None):
    if mode not in MODES:
        raise ValueError("offline candidate has no model dispatch authorization")
    if fault not in (None, "before_raw", "after_raw", "after_first_parse", "partial_raw"):
        raise ValueError("unknown diagnostic fault")
    plan, datasets, slots = package.verify(execution)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("run directory consumes its launch")
    reservation = Path(plan["registry_path"]) / (plan["execution_id"] + "-" + mode + ".json")
    claim = {
        "execution_id": plan["execution_id"],
        "origin": ORIGIN,
        "mode": mode,
        "canonical_run_path": str(output),
        "started_at": now(),
        "generation_authorized": False,
        "additional_model_calls": 0,
        "grammar_sampling_performed": False,
    }
    atomic_write(reservation, claim)
    output.mkdir(parents=True, exist_ok=False)
    atomic_write(output / "claim.json", claim)
    tokenizer = package.tokenizer(execution, plan)
    backend = FixtureBackend(tokenizer, mode)
    by_id = {(condition, ep["episode_id"]): ep for condition, eps in datasets.items() for ep in eps}
    carriers, attempted, received, parsed_count = {}, 0, 0, 0
    stop = "complete"
    try:
        for index, selected in enumerate(protocol.batches(slots)):
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
            intent = {
                "execution_id": plan["execution_id"],
                "origin": ORIGIN,
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
                "state": "generation_started_program_only",
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
                "origin": ORIGIN,
                "mode": mode,
                "batch_index": index,
                "intent_sha256": fingerprint(intent),
                "at": now(),
                "batch_wall_seconds": time.monotonic() - begin,
                "results": results,
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
                "origin": ORIGIN,
                "at": now(),
                "stop_reason": stop,
                "attempted": attempted,
                "raw_received": received,
                "parsed_records": parsed_count,
                "complete": parsed_count == len(slots) and stop == "complete",
                "additional_model_calls": 0,
            },
        )
    return {
        "attempted": attempted,
        "received": received,
        "parsed": parsed_count,
        "additional_model_calls": 0,
    }
