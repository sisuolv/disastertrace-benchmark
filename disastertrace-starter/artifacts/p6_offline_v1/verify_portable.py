"""Reconstruct copied P6 reports using copied source and a CPU environment only."""

import argparse
import importlib.metadata
import importlib.util
import json
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
                raise RuntimeError("portable audit attempted original project/weights access")
        if event == "socket.connect":
            raise RuntimeError("portable audit attempted network access")

    sys.addaudithook(guard)
    if any(importlib.util.find_spec(name) is not None for name in ("torch", "vllm")):
        raise RuntimeError("review environment must have no Torch or vLLM")
    from disastertrace.repeat_eval import audit, package

    source = Path(package.__file__).resolve()
    if not source.is_relative_to(copied / "execution/implementation_source"):
        raise RuntimeError("review imported original implementation")
    results = {
        mode: audit.verify_report(
            copied / "execution", copied / "runs" / mode, copied / "reports" / mode
        )
        for mode in ("correct", "invalid-control")
    }
    result = {
        "status": "passed",
        "reports": results,
        "relocated": True,
        "original_project_and_weights_blocked": True,
        "network_blocked": True,
        "torch_and_vllm_absent": True,
        "additional_model_calls": 0,
        "loaded_source": str(source),
        "python": sys.version,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("transformers", "tokenizers", "jinja2")
        },
        "xgrammar_required_for_this_reconstruction": False,
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
