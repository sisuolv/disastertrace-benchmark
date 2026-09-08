"""Pinned local Qwen chat preparation and lossless reasoning/content separation."""

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.controlled.output_contract import V2, identity, system_message
from disastertrace.controlled.provider_adapter import validate_public_request

MODEL = "Qwen/Qwen3-8B"
SETTINGS = {
    "model_id": MODEL,
    "runtime": "vllm",
    "runtime_version": "0.10.2",
    "dtype": "bfloat16",
    "tensor_parallel_size": 1,
    "max_model_len": 16384,
    "gpu_memory_utilization": 0.85,
    "max_num_seqs": 12,
    "batch_size": 12,
    "max_num_batched_tokens": 16384,
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
    "seed": 20260907,
    "skip_special_tokens": False,
    "include_stop_str_in_output": False,
    "reasoning_extraction": "single_close_think_token_v1",
    "output_contract": identity(V2),
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


def prepare(request, slot, tokenizer, settings=SETTINGS):
    validate_public_request(request)
    messages = [
        {"role": "system", "content": system_message(V2)},
        {"role": "user", "content": canonical(request)},
    ]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=settings["enable_thinking"],
    )
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
    if len(prompt_ids) + settings["max_tokens"] > settings["max_model_len"]:
        raise ValueError("context budget exceeded; automatic truncation is forbidden")
    seed = int(fingerprint({"seed": settings["seed"], "slot_id": slot["slot_id"]})[:8], 16)
    return {
        "messages": messages,
        "prompt": prompt,
        "prompt_token_ids": prompt_ids,
        "sampling": {**{k: settings[k] for k in SAMPLING_KEYS}, "seed": seed},
        "output_contract": identity(V2),
        "public_request_sha256": fingerprint(request),
    }


def terminal_ids(tokenizer):
    ids = {tokenizer.eos_token_id}
    for text in ("<|im_end|>", "<|endoftext|>"):
        encoded = tokenizer.encode(text, add_special_tokens=False)
        if len(encoded) == 1:
            ids.add(encoded[0])
    return ids


def extract(token_ids, tokenizer):
    close = tokenizer.encode("</think>", add_special_tokens=False)
    if len(close) != 1:
        raise ValueError("unsupported close-think tokenizer encoding")
    positions = [i for i, token in enumerate(token_ids) if token == close[0]]
    raw_text = tokenizer.decode(token_ids, skip_special_tokens=False)
    if len(positions) != 1:
        return {
            "raw_text": raw_text,
            "reasoning": raw_text,
            "content": "",
            "extraction_error": "missing_or_multiple_reasoning_delimiters",
            "reasoning_tokens": len(token_ids),
            "content_tokens": 0,
            "delimiter_tokens": 0,
            "terminal_tokens": 0,
        }
    index = positions[0]
    body = list(token_ids[index + 1 :])
    terminal = 0
    if body and body[-1] in terminal_ids(tokenizer):
        body.pop()
        terminal = 1
    return {
        "raw_text": raw_text,
        "reasoning": tokenizer.decode(token_ids[:index], skip_special_tokens=False),
        "content": tokenizer.decode(body, skip_special_tokens=False),
        "extraction_error": None,
        "reasoning_tokens": index,
        "content_tokens": len(body),
        "delimiter_tokens": 1,
        "terminal_tokens": terminal,
    }


class FixtureTokenizer:
    """Byte tokenizer for explicit diagnostic-only tests; never a local model."""

    eos_token_id = 257
    chat_template = "diagnostic_byte_template_v1"

    def apply_chat_template(self, messages, **kwargs):
        return canonical(messages) + "<think>"

    def encode(self, text, **kwargs):
        markers = {"</think>": 256, "<|im_end|>": 257, "<|endoftext|>": 258}
        if text in markers:
            return [markers[text]]
        data = text.encode("utf-8")
        return [
            (len(data[i : i + 4]) << 32) + int.from_bytes(data[i : i + 4], "big") + 1024
            for i in range(0, len(data), 4)
        ]

    def decode(self, tokens, **kwargs):
        result, buf = "", bytearray()
        for token in tokens:
            if token in (256, 257, 258):
                result += (
                    bytes(buf).decode("utf-8")
                    + {256: "</think>", 257: "<|im_end|>", 258: "<|endoftext|>"}[token]
                )
                buf = bytearray()
            else:
                value = token - 1024
                buf.extend((value & 0xFFFFFFFF).to_bytes(value >> 32, "big"))
        return result + bytes(buf).decode("utf-8")
