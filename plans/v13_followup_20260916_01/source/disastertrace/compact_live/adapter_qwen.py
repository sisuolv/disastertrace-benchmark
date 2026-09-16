"""Native schema, pinned Qwen sampling and lossless token/text accounting."""

from copy import deepcopy

from disastertrace.forecast_task.common import canonical, fingerprint
from disastertrace.forecast_task.contract import SCHEMA, SYSTEM

ENGINE_OPTIONS = {
    "guided_decoding_backend": "xgrammar",
    "guided_decoding_disable_fallback": True,
    "guided_decoding_disable_any_whitespace": True,
    "reasoning_parser": "qwen3",
}
SETTINGS = {
    "model_id": "Qwen/Qwen3-8B",
    "runtime": "vllm",
    "runtime_version": "0.10.2",
    "xgrammar_version": "0.1.23",
    "dtype": "bfloat16",
    "tensor_parallel_size": 1,
    "max_model_len": 32768,
    "gpu_memory_utilization": 0.85,
    "max_num_seqs": 4,
    "batch_size": 4,
    "max_num_batched_tokens": 32768,
    "enable_prefix_caching": False,
    "enforce_eager": True,
    "trust_remote_code": False,
    "enable_thinking": True,
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "repetition_penalty": 1.0,
    "max_tokens": 8192,
    "n": 1,
    "seed": 20260908,
    "skip_special_tokens": False,
    "include_stop_str_in_output": False,
    "structured_engine_options": ENGINE_OPTIONS,
    "schema_sha256": fingerprint(SCHEMA),
    "system_sha256": fingerprint(SYSTEM),
    "reasoning_extraction": "single_close_think_token_v1",
    "constraint_scope": "native_public_shape_only",
    "speculative_decoding": False,
}
SAMPLING_KEYS = (
    "temperature",
    "top_p",
    "top_k",
    "min_p",
    "repetition_penalty",
    "max_tokens",
    "n",
    "skip_special_tokens",
    "include_stop_str_in_output",
)


def guide():
    return {
        "json": canonical(SCHEMA),
        "backend": "xgrammar",
        "disable_fallback": True,
        "disable_any_whitespace": True,
    }


def prepare(messages, slot, tokenizer):
    if len(messages) != 2 or messages[0] != {"role": "system", "content": SYSTEM}:
        raise ValueError("native system/user messages required")
    if messages[1]["role"] != "user":
        raise ValueError("native user role required")
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=True
    )
    ids = tokenizer.encode(prompt, add_special_tokens=False)
    if len(ids) + SETTINGS["max_tokens"] > SETTINGS["max_model_len"]:
        raise ValueError("context budget exceeded; no truncation allowed")
    close = tokenizer.encode("</think>", add_special_tokens=False)
    if len(close) != 1 or close[0] in ids:
        raise ValueError("prompt contains close-think token; no carrier sanitization allowed")
    return {
        "attempt_id": slot["attempt_id"],
        "slot_id": slot["slot_id"],
        "messages": messages,
        "prompt": prompt,
        "prompt_token_ids": ids,
        "sampling": {
            **{k: SETTINGS[k] for k in SAMPLING_KEYS},
            "seed": slot["seed"],
            "guided_decoding": guide(),
        },
        "request_sha256": fingerprint(messages),
    }


def sampling_params(prepared):
    from vllm import SamplingParams
    from vllm.sampling_params import GuidedDecodingParams

    values = deepcopy(prepared["sampling"])
    if values.pop("guided_decoding") != guide():
        raise ValueError("native static schema binding differs")
    if {k: values[k] for k in SAMPLING_KEYS} != {k: SETTINGS[k] for k in SAMPLING_KEYS}:
        raise ValueError("sampling settings differ")
    return SamplingParams(**values, guided_decoding=GuidedDecodingParams(**guide()))


def terminal_ids(tokenizer):
    ids = {tokenizer.eos_token_id}
    for text in ("<|im_end|>", "<|endoftext|>"):
        encoded = tokenizer.encode(text, add_special_tokens=False)
        if len(encoded) == 1:
            ids.add(encoded[0])
    return ids


def extract(ids, tokenizer):
    close = tokenizer.encode("</think>", add_special_tokens=False)
    if len(close) != 1:
        raise ValueError("unsupported close-think tokenizer encoding")
    positions = [i for i, token in enumerate(ids) if token == close[0]]
    raw = tokenizer.decode(ids, skip_special_tokens=False)
    if len(positions) != 1:
        return {
            "raw_text": raw,
            "reasoning": raw,
            "content": "",
            "extraction_error": "missing_or_multiple_reasoning_delimiters",
            "reasoning_tokens": len(ids),
            "content_tokens": 0,
            "delimiter_tokens": 0,
            "terminal_tokens": 0,
        }
    index = positions[0]
    body = list(ids[index + 1 :])
    terminal = int(bool(body) and body[-1] in terminal_ids(tokenizer))
    if terminal:
        body.pop()
    return {
        "raw_text": raw,
        "reasoning": tokenizer.decode(ids[:index], skip_special_tokens=False),
        "content": tokenizer.decode(body, skip_special_tokens=False),
        "extraction_error": None,
        "reasoning_tokens": index,
        "content_tokens": len(body),
        "delimiter_tokens": 1,
        "terminal_tokens": terminal,
    }


def verify_runtime_text(result, tokenizer):
    ids = result["output_token_ids"]
    if result["finish_reason"] == "stop":
        if not ids or ids[-1] not in terminal_ids(tokenizer):
            raise ValueError("stop requires recorded terminal token")
        # vLLM records EOS in token IDs but excludes it from text under this policy.
        ids = ids[:-1]
    expected = tokenizer.decode(ids, skip_special_tokens=False)
    if expected != result["runtime_output_text"]:
        raise ValueError("runtime text differs from exact bound detokenization")


def parse_result(result, prepared, tokenizer, *, diagnostic=False):
    if (
        result["attempt_id"] != prepared["attempt_id"]
        or result["runtime_request_id"] != prepared["attempt_id"]
        or result["prompt_token_ids"] != prepared["prompt_token_ids"]
    ):
        raise ValueError("returned request identity or prompt differs")
    if diagnostic and result.get("diagnostic_missing") is True:
        if result["candidates"]:
            raise ValueError("missing diagnostic contains candidates")
        return {"slot_id": prepared["slot_id"], "final_text": None, "extraction": None}
    if len(result["candidates"]) != 1:
        raise ValueError("exactly one returned candidate required")
    candidate = result["candidates"][0]
    if candidate["index"] != 0 or type(candidate["index"]) is not int:
        raise ValueError("candidate index differs")
    ids = candidate["output_token_ids"]
    if not isinstance(ids, list) or any(type(t) is not int or t < 0 for t in ids):
        raise ValueError("invalid output token IDs")
    if len(ids) > SETTINGS["max_tokens"]:
        raise ValueError("generated-token cap exceeded")
    if candidate["finish_reason"] not in ("stop", "length"):
        raise ValueError("unsupported finish reason")
    if (
        not diagnostic
        and candidate["finish_reason"] == "length"
        and len(ids) != SETTINGS["max_tokens"]
    ):
        raise ValueError("length termination before full reserved output cap")
    if candidate["stop_reason"] is not None and candidate["stop_reason"] not in terminal_ids(
        tokenizer
    ):
        raise ValueError("unbound stop reason")
    verify_runtime_text(candidate, tokenizer)
    extracted = extract(ids, tokenizer)
    return {
        "slot_id": prepared["slot_id"],
        "final_text": extracted["content"],
        "extraction": extracted,
    }
