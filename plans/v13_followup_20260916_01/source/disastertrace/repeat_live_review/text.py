"""Strict comparison of captured runtime text and the bound detokenization policy."""

from disastertrace.local_eval.adapter import terminal_ids


def verify_runtime_text(result, tokenizer, sampling, *, model):
    tokens = result["output_token_ids"]
    if (
        model
        and result["finish_reason"] == "stop"
        and sampling["include_stop_str_in_output"] is False
    ):
        if not tokens or tokens[-1] not in terminal_ids(tokenizer):
            raise ValueError("stopped text requires a recorded terminal token")
        # vLLM V1 retains the stop token ID while excluding it from rendered text.
        tokens = tokens[:-1]
    expected = tokenizer.decode(tokens, skip_special_tokens=sampling["skip_special_tokens"])
    if expected != result["runtime_output_text"]:
        raise ValueError("runtime text differs from the bound detokenization policy")
