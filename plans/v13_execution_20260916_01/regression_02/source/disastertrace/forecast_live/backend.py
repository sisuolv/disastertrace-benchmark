"""Explicit engine IDs, immutable runtime observations and zero automatic retries."""

import os
import socket
from pathlib import Path

from disastertrace.forecast_task.common import fingerprint, read

from . import adapter, package

MODEL_ORIGIN = "local_model_vllm_native_forecast_v1"
DIAGNOSTIC_ORIGIN = "public_program_forecast_live_diagnostic_v1"
DECODER = {
    "backend": "xgrammar",
    "disable_fallback": True,
    "disable_any_whitespace": False,
    "reasoning_backend": "qwen3",
    "speculative_config": None,
}
ENGINE_KEYS = (
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


def validate_observation(value, plan):
    if (
        type(value["visible_gpu_count"]) is not int
        or value["visible_gpu_count"] != 1
        or "H100" not in value["device_name"]
        or "MIG" in value["device_name"]
        or not 75_000_000_000 <= value["total_memory_bytes"] <= 90_000_000_000
        or value["capability"] != [9, 0]
        or value["structured_decoding"] != DECODER
        or value["settings"] != adapter.SETTINGS
        or value["vllm_use_v1"] != "1"
        or value["v1_multiprocessing"] != "0"
        or value["request_identity"] != "attempt_id_direct_engine_add_request"
        or value["backend_files"] != plan["backend_files"]
        or value["model_identity"] != plan["model_identity"]
        or value["environment_sha256"] != plan["environment_sha256"]
    ):
        raise ValueError("actual GPU/runtime differs from pinned native profile")
    expected = {
        k: adapter.SETTINGS[k]
        for k in (
            "max_model_len",
            "tensor_parallel_size",
            "enable_prefix_caching",
            "max_num_seqs",
            "max_num_batched_tokens",
            "enforce_eager",
            "seed",
        )
    }
    expected["dtype"] = "torch.bfloat16"
    if value["actual_engine"] != expected:
        raise ValueError("actual engine settings differ")


class VLLMBackend:
    origin = MODEL_ORIGIN

    def __init__(self, root):
        import torch
        from vllm import LLM

        root = Path(root)
        plan, _, _ = package.verify(root, code=True)
        self.plan, self.generation_authorized = plan, plan["generation_authorized"]
        if package.environment() != read(root / "environment.json"):
            raise ValueError("installed package inventory differs")
        if package.backend_inventory() != plan["backend_files"]:
            raise ValueError("installed backend source differs")
        if (
            os.environ.get("VLLM_USE_V1") != "1"
            or os.environ.get("VLLM_ENABLE_V1_MULTIPROCESSING") != "0"
        ):
            raise ValueError("explicit V1 settings required")
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise ValueError("exactly one actual CUDA device required")
        snapshot = read(root / "model_snapshot.json")
        package.verify_model(snapshot)
        self.observation = {
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "device_name": torch.cuda.get_device_name(0),
            "visible_gpu_count": torch.cuda.device_count(),
            "total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "capability": list(torch.cuda.get_device_capability(0)),
            "hostname": socket.gethostname(),
            "settings": adapter.SETTINGS,
            "vllm_use_v1": os.environ["VLLM_USE_V1"],
            "v1_multiprocessing": os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"],
            "request_identity": "attempt_id_direct_engine_add_request",
            "backend_files": plan["backend_files"],
            "model_identity": plan["model_identity"],
            "environment_sha256": fingerprint(package.environment()),
        }
        self.engine = LLM(
            model=snapshot["local_path"],
            tokenizer=snapshot["local_path"],
            **{k: adapter.SETTINGS[k] for k in ENGINE_KEYS},
            **adapter.ENGINE_OPTIONS,
        )
        self.tokenizer = self.engine.get_tokenizer()
        config = self.engine.llm_engine.vllm_config
        self.observation["structured_decoding"] = {
            "backend": config.decoding_config.backend,
            "disable_fallback": config.decoding_config.disable_fallback,
            "disable_any_whitespace": config.decoding_config.disable_any_whitespace,
            "reasoning_backend": config.decoding_config.reasoning_backend,
            "speculative_config": config.speculative_config,
        }
        self.observation["actual_engine"] = {
            "dtype": str(config.model_config.dtype),
            "max_model_len": config.model_config.max_model_len,
            "tensor_parallel_size": config.parallel_config.tensor_parallel_size,
            "enable_prefix_caching": config.cache_config.enable_prefix_caching,
            "max_num_seqs": config.scheduler_config.max_num_seqs,
            "max_num_batched_tokens": config.scheduler_config.max_num_batched_tokens,
            "enforce_eager": config.model_config.enforce_eager,
            "seed": config.model_config.seed,
        }
        validate_observation(self.observation, plan)
        self.last_error = None

    def generate(self, prepared):
        if not self.generation_authorized:
            raise ValueError("offline backend cannot generate")
        engine, results = self.engine.llm_engine, []
        self.last_error = None
        try:
            if package.past_deadline(self.plan):
                raise ValueError("phase deadline reached before engine dispatch")
            if engine.has_unfinished_requests():
                raise ValueError("unexpected unfinished engine requests")
            for item in prepared:
                engine.add_request(
                    item["attempt_id"],
                    {"prompt_token_ids": item["prompt_token_ids"]},
                    adapter.sampling_params(item),
                )
            while engine.has_unfinished_requests():
                if package.past_deadline(self.plan):
                    raise ValueError("phase deadline reached during generation")
                for result in engine.step():
                    if result.finished:
                        results.append(
                            {
                                "attempt_id": result.request_id,
                                "runtime_request_id": result.request_id,
                                "prompt_token_ids": list(result.prompt_token_ids or []),
                                "candidates": [
                                    {
                                        "output_token_ids": list(o.token_ids),
                                        "runtime_output_text": o.text,
                                        "finish_reason": o.finish_reason,
                                        "stop_reason": o.stop_reason,
                                        "index": o.index,
                                    }
                                    for o in result.outputs
                                ],
                            }
                        )
        except Exception as exc:  # noqa: BLE001 - retain answers returned before engine failure
            self.last_error = type(exc).__name__ + ": " + str(exc)
        return results


class ProgramBackend:
    origin = DIAGNOSTIC_ORIGIN

    def __init__(self, tokenizer, policy="latest_explicit"):
        self.tokenizer, self.policy, self.last_error = tokenizer, policy, None
        self.observation = {"origin": self.origin, "policy": policy, "model_calls": 0}

    def generate(self, prepared):
        from disastertrace.forecast_task.public_resolver import final_text

        output = []
        for item in prepared:
            text = final_text(item["messages"], self.policy)
            result = {
                "attempt_id": item["attempt_id"],
                "runtime_request_id": item["attempt_id"],
                "prompt_token_ids": item["prompt_token_ids"],
                "candidates": [],
            }
            if text is None:
                result["diagnostic_missing"] = True
            else:
                ids = (
                    self.tokenizer.encode("diagnostic reasoning", add_special_tokens=False)
                    + self.tokenizer.encode("</think>", add_special_tokens=False)
                    + self.tokenizer.encode(text, add_special_tokens=False)
                )
                result["candidates"] = [
                    {
                        "output_token_ids": ids + [self.tokenizer.eos_token_id],
                        "runtime_output_text": self.tokenizer.decode(
                            ids, skip_special_tokens=False
                        ),
                        "finish_reason": "stop",
                        "stop_reason": None,
                        "index": 0,
                    }
                ]
            output.append(result)
        return output
