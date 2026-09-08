"""Explicit final-only XGrammar settings, preserving the free-track prompt."""

from copy import deepcopy

from disastertrace.local_eval import adapter as free_adapter

from . import contract

ENGINE_OPTIONS = {
    "guided_decoding_backend": "xgrammar",
    "guided_decoding_disable_fallback": True,
    "guided_decoding_disable_any_whitespace": False,
    "reasoning_parser": "qwen3",
}
SETTINGS = {
    **deepcopy(free_adapter.SETTINGS),
    "output_track": contract.VERSION,
    "constraint": contract.identity(),
    "structured_engine_options": ENGINE_OPTIONS,
    "engine_version": "v1",
    "xgrammar_version": "0.1.23",
    "speculative_decoding": False,
    "reasoning_constraint_policy": "unconstrained_until_single_generated_close_think",
}


def guide():
    return {
        "json": contract.schema_text(),
        "backend": "xgrammar",
        "disable_fallback": True,
        "disable_any_whitespace": False,
    }


def prepare(request, slot, tokenizer, settings=SETTINGS):
    if settings != SETTINGS:
        raise ValueError("constrained profile settings changed")
    prepared = free_adapter.prepare(request, slot, tokenizer, settings)
    closing = tokenizer.encode("</think>", add_special_tokens=False)
    if len(closing) != 1 or closing[0] in prepared["prompt_token_ids"]:
        raise ValueError("prompt would prematurely end Qwen3 reasoning; do not sanitize carrier")
    prepared["sampling"]["guided_decoding"] = guide()
    prepared["constraint"] = contract.identity()
    prepared["structured_engine_options"] = deepcopy(ENGINE_OPTIONS)
    return prepared


def sampling_params(prepared):
    """Build real vLLM parameters without loading weights or calling generate."""
    from vllm import SamplingParams
    from vllm.sampling_params import GuidedDecodingParams

    if (
        prepared.get("constraint") != contract.identity()
        or prepared.get("structured_engine_options") != ENGINE_OPTIONS
        or prepared["sampling"].get("guided_decoding") != guide()
    ):
        raise ValueError("unbound structured decoding settings")
    values = deepcopy(prepared["sampling"])
    values["guided_decoding"] = GuidedDecodingParams(**values["guided_decoding"])
    return SamplingParams(**values)


extract = free_adapter.extract
terminal_ids = free_adapter.terminal_ids
