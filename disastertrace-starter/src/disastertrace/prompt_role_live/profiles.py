"""Select immutable model adapters by an explicit frozen profile, never global mutation."""

from . import adapter_deepseek as deepseek_r1

ADAPTERS = {"deepseek_r1": deepseek_r1}


def adapter_for(plan):
    name = plan["model_profile"]
    if name not in ADAPTERS:
        raise ValueError("unknown pinned model profile")
    adapter = ADAPTERS[name]
    if plan["settings"] != adapter.SETTINGS:
        raise ValueError("profile and model settings differ")
    return adapter


def decoder_for(plan):
    adapter = adapter_for(plan)
    return {
        "backend": "xgrammar",
        "disable_fallback": True,
        "disable_any_whitespace": True,
        "reasoning_backend": adapter.ENGINE_OPTIONS["reasoning_parser"],
        "speculative_config": None,
    }
