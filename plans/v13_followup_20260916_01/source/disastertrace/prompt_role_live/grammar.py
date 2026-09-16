"""Actual XGrammar compilation and CPU token-mask replay, with no model inference."""

import importlib.metadata

from disastertrace.forecast_task.common import canonical
from disastertrace.forecast_task.contract import SCHEMA

from . import adapter_deepseek as adapter


class GrammarReplay:
    def __init__(self, tokenizer, vocab_size):
        import xgrammar as xgr

        if importlib.metadata.version("xgrammar") != adapter.SETTINGS["xgrammar_version"]:
            raise ValueError("XGrammar version changed")
        self.xgr, self.tokenizer = xgr, tokenizer
        self.info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab_size)
        self.compiler = xgr.GrammarCompiler(self.info, max_threads=8)
        self.compiled = self.compiler.compile_json_schema(
            canonical(SCHEMA), any_whitespace=False, strict_mode=True
        )
        self.bitmask = xgr.allocate_token_bitmask(1, vocab_size)
        self.vocab_size = vocab_size

    def walk(self, token_ids):
        matcher = self.xgr.GrammarMatcher(self.compiled)
        checked = 0
        for index, token in enumerate(token_ids):
            if type(token) is not int or not 0 <= token < self.vocab_size:
                return {"accepted": False, "checked": checked, "rejected_at": index}
            if matcher.is_terminated():
                return {"accepted": False, "checked": checked, "rejected_at": index}
            matcher.fill_next_token_bitmask(self.bitmask)
            allowed = bool((int(self.bitmask[0, token // 32]) >> (token % 32)) & 1)
            accepted = matcher.accept_token(token)
            if accepted != allowed:
                raise ValueError("XGrammar token mask and matcher disagree")
            checked += 1
            if not allowed:
                return {"accepted": False, "checked": checked, "rejected_at": index}
        return {
            "accepted": True,
            "checked": checked,
            "terminated": matcher.is_terminated(),
            "rejected_at": None,
        }

    def check_text(self, text):
        ids = self.tokenizer.encode(text, add_special_tokens=False)
        return self.walk(ids + [self.info.stop_token_ids[0]])

    def check_output(self, ids):
        close = self.tokenizer.encode("</think>", add_special_tokens=False)[0]
        positions = [i for i, value in enumerate(ids) if value == close]
        if not positions:
            return {"phase": "reasoning_only", "constrained_tokens": 0, "accepted": None}
        if len(positions) != 1:
            return {"phase": "multiple_delimiters", "constrained_tokens": 0, "accepted": False}
        tokens = ids[positions[0] + 1 :]
        return {"phase": "final", "constrained_tokens": len(tokens), **self.walk(tokens)}
