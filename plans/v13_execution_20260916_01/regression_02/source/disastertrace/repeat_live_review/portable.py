"""Reconstruct a relocated report while forbidding original data, weights and network."""

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copy", type=Path, required=True)
    parser.add_argument("--original-project", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    copied = args.copy.resolve()
    blocked = (args.original_project.resolve(), args.model_directory.resolve())

    def guard(event, fields):
        if event == "open" and isinstance(fields[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(fields[0])).resolve()
            if not path.is_relative_to(copied) and any(path.is_relative_to(p) for p in blocked):
                raise RuntimeError("portable audit attempted original source/data/weights access")
        if event == "socket.connect":
            raise RuntimeError("portable audit attempted network access")

    sys.addaudithook(guard)
    if any(importlib.util.find_spec(name) is not None for name in ("torch", "vllm")):
        raise RuntimeError("CPU review environment must not contain Torch or vLLM")
    from disastertrace.local_eval.storage import write
    from disastertrace.repeat_live import package

    from . import audit

    source = Path(package.__file__).resolve()
    if not source.is_relative_to(copied / "review_source") or not Path(
        audit.__file__
    ).resolve().is_relative_to(copied / "review_source"):
        raise RuntimeError("original implementation was imported")
    verified = audit.verify_report(copied / "execution", copied / "run", copied / "report")
    result = {
        "status": "passed",
        "verification": verified,
        "relocated": True,
        "original_project_and_weights_blocked": True,
        "network_blocked": True,
        "torch_and_vllm_absent": True,
        "additional_model_calls": 0,
        "loaded_source": str(source),
        "python": sys.version,
    }
    # Save inside the copied root; the caller can then preserve the receipt elsewhere.
    write(args.output, result)
    print(result, flush=True)


if __name__ == "__main__":
    main()
