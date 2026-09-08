"""Load the frozen decoder on GPU and inspect configuration without generating answers."""

import argparse
from pathlib import Path

from disastertrace.constrained_eval import adapter, execution, runtime
from disastertrace.local_eval.storage import now, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan, _, _ = execution.verify(args.execution, model_hashes=True)
    from vllm import LLM

    def forbidden(*args, **kwargs):
        raise RuntimeError("preflight must not generate model answers")

    LLM.generate = forbidden
    started = now()
    backend = runtime.VLLMBackend(args.execution, adapter.SETTINGS)
    result = {
        "execution_id": plan["execution_id"],
        "started_at": started,
        "finished_at": now(),
        "gpu_model_loaded": True,
        "model_calls": 0,
        "generate_disabled": True,
        "runtime_observation": backend.observation,
        "tokenizer_class": type(backend.tokenizer).__name__,
    }
    write(args.output, result)
    print(result)


if __name__ == "__main__":
    main()
