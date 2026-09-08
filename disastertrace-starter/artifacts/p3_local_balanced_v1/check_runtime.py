"""CPU tokenizer/context validation and GPU model load; no answer generation."""

import argparse
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.controlled import compiler, renderer
from disastertrace.controlled.schema import METHODS
from disastertrace.local_eval import adapter, data, runtime
from disastertrace.local_eval.storage import now, read, write

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--load-model", action="store_true")
    args = parser.parse_args()
    from transformers import AutoTokenizer

    snapshot = read(HERE / "model_snapshot.json")
    tokenizer = AutoTokenizer.from_pretrained(
        snapshot["local_path"], local_files_only=True, trust_remote_code=False
    )
    _, episodes, slots = data.verify(HERE / "dataset", full=False)
    rows, lengths = [], {}
    for episode in episodes:
        for method in METHODS:
            previous, history = None, []
            for checkpoint in episode["checkpoints"]:
                cp = checkpoint["checkpoint_id"]
                slot = next(
                    s
                    for s in slots
                    if s["episode_id"] == episode["episode_id"]
                    and s["method"] == method
                    and s["checkpoint_id"] == cp
                )
                request = renderer.render_request(
                    episode, cp, method=method, previous=previous, history=history
                )
                prepared = adapter.prepare(request, slot, tokenizer)
                assert (
                    tokenizer.encode(prepared["prompt"], add_special_tokens=False)
                    == prepared["prompt_token_ids"]
                )
                count = len(prepared["prompt_token_ids"])
                lengths.setdefault(method, []).append(count)
                rows.append(
                    {
                        "slot_id": slot["slot_id"],
                        "prompt_tokens": count,
                        "prepared_sha256": fingerprint(prepared),
                    }
                )
                previous = compiler.reference_at(episode, cp)
                history.append(previous)
    result = {
        "at": now(),
        "model_calls": 0,
        "gpu_model_loaded": False,
        "kind": "unsent_oracle_carrier_context_diagnostic",
        "does_not_bound_all_possible_model_carriers": True,
        "chat_template_sha256": fingerprint(tokenizer.chat_template),
        "tokenizer_class": type(tokenizer).__name__,
        "lengths": {m: {"min": min(n), "max": max(n)} for m, n in lengths.items()},
        "rows": rows,
    }
    if args.load_model:
        # LLM initialization profiles CUDA kernels; no benchmark prompt is generated.
        backend = runtime.VLLMBackend(HERE, adapter.SETTINGS)
        assert fingerprint(backend.tokenizer.chat_template) == result["chat_template_sha256"]
        result.update(gpu_model_loaded=True, device=backend.observation, finished_at=now())
    write(args.output, result)
    print({k: v for k, v in result.items() if k != "rows"})


if __name__ == "__main__":
    main()
