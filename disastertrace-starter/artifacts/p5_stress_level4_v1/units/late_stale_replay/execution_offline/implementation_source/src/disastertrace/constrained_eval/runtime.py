"""Separate constrained-track collection; retains the P3 no-retry capture policy."""

import importlib.metadata
import os
import platform
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.controlled import public_oracle, renderer
from disastertrace.controlled.schema import parse_decision
from disastertrace.local_eval.storage import now, read, write

from . import adapter, contract, execution


def environment():
    return {
        "python": platform.python_version(),
        "packages": {
            d.metadata["Name"].lower().replace("_", "-"): d.version
            for d in importlib.metadata.distributions()
        },
    }


def tokenizer_for(execution_path, diagnostic=False):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        Path(execution_path) / "model_config", local_files_only=True, trust_remote_code=False
    )


class VLLMBackend:
    origin = "local_model_vllm_constrained_v1"

    def __init__(self, execution_path, config):
        import torch
        from vllm import LLM

        if environment() != read(Path(execution_path) / "environment.json"):
            raise ValueError("GPU environment changed after freeze")
        plan = read(Path(execution_path) / "execution.json")
        if execution.backend_inventory() != plan["backend_files"]:
            raise ValueError("structured backend source changed after freeze")
        if config != adapter.SETTINGS or os.environ.get("VLLM_USE_V1") != "1":
            raise ValueError("explicit frozen constrained V1 profile required")
        if not torch.cuda.is_available():
            raise ValueError("CUDA device required")
        self.observation = {
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "device_name": torch.cuda.get_device_name(0),
            "total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "capability": list(torch.cuda.get_device_capability(0)),
            "environment_sha256": fingerprint(environment()),
        }
        snapshot = read(Path(execution_path) / "model_snapshot.json")
        keys = (
            "dtype",
            "tensor_parallel_size",
            "max_model_len",
            "gpu_memory_utilization",
            "max_num_seqs",
            "max_num_batched_tokens",
            "enable_prefix_caching",
            "enforce_eager",
            "trust_remote_code",
            "seed",
        )
        self.engine = LLM(
            model=snapshot["local_path"],
            tokenizer=snapshot["local_path"],
            **{key: config[key] for key in keys},
            **adapter.ENGINE_OPTIONS,
        )
        self.tokenizer = self.engine.get_tokenizer()
        observed_config = self.engine.llm_engine.vllm_config
        decoding = observed_config.decoding_config
        observed = {
            "backend": decoding.backend,
            "disable_fallback": decoding.disable_fallback,
            "disable_any_whitespace": decoding.disable_any_whitespace,
            "reasoning_backend": decoding.reasoning_backend,
            "speculative_config": observed_config.speculative_config,
        }
        if observed != DECODING_OBSERVATION:
            raise ValueError("actual decoder differs from the frozen candidate")
        self.observation.update(
            structured_decoding=observed,
            backend_files=execution.backend_inventory(),
            constraint=contract.identity(),
            engine_version="v1",
        )

    def generate(self, prepared):
        outputs = self.engine.generate(
            [{"prompt_token_ids": p["prompt_token_ids"]} for p in prepared],
            [adapter.sampling_params(p) for p in prepared],
            use_tqdm=False,
        )
        results = []
        if len(outputs) != len(prepared):
            raise ValueError("runtime output cardinality mismatch")
        for expected, result in zip(prepared, outputs):
            if result.prompt_token_ids != expected["prompt_token_ids"] or len(result.outputs) != 1:
                raise ValueError("runtime reordered prompts or returned multiple samples")
            output = result.outputs[0]
            results.append(
                {
                    "runtime_request_id": result.request_id,
                    "prompt_token_ids": list(result.prompt_token_ids),
                    "output_token_ids": list(output.token_ids),
                    "runtime_output_text": output.text,
                    "finish_reason": output.finish_reason,
                    "stop_reason": output.stop_reason,
                }
            )
        return results


DECODING_OBSERVATION = {
    "backend": "xgrammar",
    "disable_fallback": True,
    "disable_any_whitespace": False,
    "reasoning_backend": "qwen3",
    "speculative_config": None,
}


class FixtureBackend:
    origin = "diagnostic_constrained_fixture"

    def __init__(self, execution_path):
        self.tokenizer = tokenizer_for(execution_path)
        self.observation = {
            "kind": "public_oracle_fixture_actual_tokenizer",
            "model_calls": 0,
            "constraint": contract.identity(),
            "grammar_sampling_performed": False,
        }

    def generate(self, prepared):
        from disastertrace.automated.common import strict_json

        results = []
        for i, p in enumerate(prepared):
            raw = contract.serialize_fixture(
                public_oracle.answer(strict_json(p["messages"][1]["content"]))
            )
            ids = (
                self.tokenizer.encode("Offline program diagnostic; no model generation.")
                + self.tokenizer.encode("</think>", add_special_tokens=False)
                + self.tokenizer.encode(raw, add_special_tokens=False)
                + [self.tokenizer.eos_token_id]
            )
            results.append(
                {
                    "runtime_request_id": "fixture-" + str(i),
                    "prompt_token_ids": p["prompt_token_ids"],
                    "output_token_ids": ids,
                    "runtime_output_text": self.tokenizer.decode(ids, skip_special_tokens=False),
                    "finish_reason": "stop",
                    "stop_reason": None,
                }
            )
        return results


def collect(execution_path, output, *, diagnostic=False):
    plan, episodes, slots = execution.verify(execution_path)
    if not diagnostic and plan["scope"] != execution.LIVE_SCOPE:
        raise ValueError("offline candidate cannot dispatch model requests")
    output = Path(output).resolve()
    if not diagnostic and str(output) != plan["run_path"]:
        raise ValueError("production run must use the canonical one-use claim path")
    if diagnostic and str(output) == plan["run_path"]:
        raise ValueError("diagnostics must not consume production scope")
    if not diagnostic and datetime.fromisoformat(now()) >= datetime.fromisoformat(
        plan["deadline_utc"]
    ):
        raise ValueError("execution deadline passed")
    if not diagnostic:
        from disastertrace.local_eval.execution import verify_model

        verify_model(read(Path(execution_path) / "model_snapshot.json"))
    output.mkdir(parents=True, exist_ok=False)
    origin = "diagnostic_constrained_fixture" if diagnostic else "local_model_vllm_constrained_v1"
    write(
        output / "claim.json",
        {
            "execution_id": plan["execution_id"],
            "origin": origin,
            "started_at": now(),
            "pid": os.getpid(),
            "no_relaunch": True,
            "canonical_run_path": str(output),
        },
    )
    stop, attempted, received = "complete", 0, 0
    try:
        backend = (
            FixtureBackend(execution_path)
            if diagnostic
            else VLLMBackend(execution_path, plan["settings"])
        )
        write(
            output / "runtime.json",
            {
                "origin": backend.origin,
                "observation": backend.observation,
                "tokenizer_class": type(backend.tokenizer).__name__,
                "chat_template_sha256": fingerprint(backend.tokenizer.chat_template),
                "ready_at": now(),
            },
        )
        by_id = {ep["episode_id"]: ep for ep in episodes}
        carriers = {}
        size = plan["settings"]["batch_size"]
        for offset in range(0, len(slots), size):
            if not diagnostic and datetime.fromisoformat(now()) >= datetime.fromisoformat(
                plan["deadline_utc"]
            ):
                stop = "deadline_before_next_batch"
                break
            selected = slots[offset : offset + size]
            requests, prepared = [], []
            for slot in selected:
                previous, history = carriers.get(slot["trajectory_id"], (None, []))
                request = renderer.render_request(
                    by_id[slot["episode_id"]],
                    slot["checkpoint_id"],
                    method=slot["method"],
                    previous=previous,
                    history=history,
                )
                requests.append(request)
                prepared.append(adapter.prepare(request, slot, backend.tokenizer, plan["settings"]))
            intent = {
                "execution_id": plan["execution_id"],
                "origin": backend.origin,
                "batch_index": offset // size,
                "started_at": now(),
                "slots": selected,
                "requests": requests,
                "prepared": prepared,
            }
            write(output / "batches" / f"{offset // size:03d}.json", intent)
            attempted += len(selected)
            started = time.monotonic()
            results = backend.generate(prepared)
            batch_seconds = time.monotonic() - started
            for slot, request, prep, result in zip(selected, requests, prepared, results):
                extracted = adapter.extract(result["output_token_ids"], backend.tokenizer)
                previous, history = carriers.get(slot["trajectory_id"], (None, []))
                status = "invalid"
                try:
                    decision = parse_decision(extracted["content"])
                except (ValueError, TypeError, KeyError, RecursionError):
                    pass
                else:
                    status = "ok"
                    previous = decision
                    history = history + [deepcopy(decision)]
                carriers[slot["trajectory_id"]] = (previous, history)
                capture = {
                    "execution_id": plan["execution_id"],
                    "origin": backend.origin,
                    "slot_index": slot["slot_index"],
                    "batch_index": offset // size,
                    "intent_sha256": fingerprint(intent),
                    "prepared_sha256": fingerprint(prep),
                    "captured_at": now(),
                    "batch_wall_seconds": batch_seconds,
                    "result": result,
                    "extracted": extracted,
                    "output_validity": contract.inspect(extracted["content"]),
                    "prompt_tokens": len(prep["prompt_token_ids"]),
                    "completion_tokens": len(result["output_token_ids"]),
                    "status": status,
                    "state_after": previous,
                }
                write(output / "captures" / f"{slot['slot_index']:04d}.json", capture)
                received += 1
            print(
                canonical(
                    {
                        "at": now(),
                        "attempted": attempted,
                        "received": received,
                        "planned": len(slots),
                        "last_batch_seconds": batch_seconds,
                    }
                ),
                flush=True,
            )
    except BaseException as exc:
        stop = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        write(
            output / "completion.json",
            {
                "execution_id": plan["execution_id"],
                "origin": origin,
                "finished_at": now(),
                "stop_reason": stop,
                "attempted": attempted,
                "received": received,
                "complete": received == len(slots) and stop == "complete",
            },
        )
    return {"attempted": attempted, "received": received, "stop_reason": stop}
