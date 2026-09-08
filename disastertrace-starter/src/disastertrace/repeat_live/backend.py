"""Explicit engine request IDs and returned outputs retained even after a batch error."""

import os
import socket
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.constrained_eval import adapter, contract
from disastertrace.constrained_eval.execution import backend_inventory
from disastertrace.local_eval.execution import verify_model
from disastertrace.local_eval.storage import read
from disastertrace.stress_eval.runtime import DECODING_OBSERVATION, environment

from . import package

ORIGIN = "local_model_vllm_p6_paired_v1"


def validate_observation(value):
    if (
        value["visible_gpu_count"] != 1
        or type(value["visible_gpu_count"]) is not int
        or "H100" not in value["device_name"]
        or "MIG" in value["device_name"]
        or not 75_000_000_000 <= value["total_memory_bytes"] <= 90_000_000_000
        or value["capability"] != [9, 0]
        or value["structured_decoding"] != DECODING_OBSERVATION
        or value["constraint"] != contract.identity()
        or value["settings"] != adapter.SETTINGS
        or value["vllm_use_v1"] != "1"
        or value["v1_multiprocessing"] != "0"
        or value["request_identity"] != "attempt_id_direct_engine_add_request"
    ):
        raise ValueError("actual GPU/decoder/settings differ from the bound H100 profile")


class VLLMBackend:
    def __init__(self, execution, config):
        import torch
        from vllm import LLM

        path = Path(execution)
        plan = read(path / "execution.json")
        self.generation_authorized = plan["generation_authorized"]
        resource = path / "parent"
        if environment() != read(resource / "environment.json"):
            raise ValueError("GPU package inventory changed")
        backend_files = backend_inventory()
        expected_backend = {
            k.removeprefix("backend_source/"): v
            for k, v in read(resource / "execution.json")["resource_files"].items()
            if k.startswith("backend_source/")
        }
        if backend_files != expected_backend or package.engine_inventory() != plan["engine_files"]:
            raise ValueError("installed engine/backend source changed")
        if (
            config != adapter.SETTINGS
            or os.environ.get("VLLM_USE_V1") != "1"
            or os.environ.get("VLLM_ENABLE_V1_MULTIPROCESSING") != "0"
        ):
            raise ValueError("explicit paired runtime settings required")
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise ValueError("one actual CUDA device required")
        snapshot = read(resource / "model_snapshot.json")
        verify_model(snapshot)
        self.observation = {
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "device_name": torch.cuda.get_device_name(0),
            "visible_gpu_count": torch.cuda.device_count(),
            "total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "capability": list(torch.cuda.get_device_capability(0)),
            "hostname": socket.gethostname(),
            "environment_sha256": fingerprint(environment()),
            "settings": config,
            "vllm_use_v1": os.environ["VLLM_USE_V1"],
            "v1_multiprocessing": os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"],
            "request_identity": "attempt_id_direct_engine_add_request",
            "engine_files": package.engine_inventory(),
            "backend_files": backend_files,
            "constraint": contract.identity(),
            "model_identity": plan["model_identity"],
        }
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
        observed = self.engine.llm_engine.vllm_config
        decoder = observed.decoding_config
        self.observation["structured_decoding"] = {
            "backend": decoder.backend,
            "disable_fallback": decoder.disable_fallback,
            "disable_any_whitespace": decoder.disable_any_whitespace,
            "reasoning_backend": decoder.reasoning_backend,
            "speculative_config": observed.speculative_config,
        }
        self.observation["actual_engine"] = {
            "dtype": str(observed.model_config.dtype),
            "max_model_len": observed.model_config.max_model_len,
            "tensor_parallel_size": observed.parallel_config.tensor_parallel_size,
            "enable_prefix_caching": observed.cache_config.enable_prefix_caching,
            "max_num_seqs": observed.scheduler_config.max_num_seqs,
            "max_num_batched_tokens": observed.scheduler_config.max_num_batched_tokens,
            "enforce_eager": observed.model_config.enforce_eager,
            "seed": observed.model_config.seed,
        }
        expected = {k: config[k] for k in self.observation["actual_engine"] if k != "dtype"}
        expected["dtype"] = "torch.bfloat16"
        if self.observation["actual_engine"] != expected:
            raise ValueError("actual engine values differ from the declared configuration")
        validate_observation(self.observation)
        self.last_error = None

    def generate(self, prepared):
        if self.generation_authorized is not True:
            raise ValueError("offline backend cannot generate model answers")
        # Submit IDs explicitly: positional zipping cannot identify partial or reordered returns.
        params = [adapter.sampling_params(item) for item in prepared]
        engine, results = self.engine.llm_engine, []
        self.last_error = None
        try:
            if engine.has_unfinished_requests():
                raise ValueError("unexpected unfinished requests before batch")
            for item, param in zip(prepared, params):
                engine.add_request(
                    item["attempt_id"], {"prompt_token_ids": item["prompt_token_ids"]}, param
                )
            while engine.has_unfinished_requests():
                returned = engine.step()
                for result in returned:
                    if not result.finished:
                        continue
                    candidates = [
                        {
                            "output_token_ids": list(o.token_ids),
                            "runtime_output_text": o.text,
                            "finish_reason": o.finish_reason,
                            "stop_reason": o.stop_reason,
                            "index": o.index,
                        }
                        for o in result.outputs
                    ]
                    results.append(
                        {
                            "attempt_id": result.request_id,
                            "runtime_request_id": result.request_id,
                            "prompt_token_ids": list(result.prompt_token_ids or []),
                            "candidates": candidates,
                            **(candidates[0] if candidates else {}),
                        }
                    )
        except Exception as exc:  # noqa: BLE001 - retain returned outputs on engine failures
            self.last_error = type(exc).__name__ + ": " + str(exc)
        return results
