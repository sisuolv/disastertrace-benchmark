"""Verify relocated captures without access to original project data or model weights."""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--copy", type=Path, required=True)
parser.add_argument("--original-project", type=Path, required=True)
parser.add_argument("--model-directory", type=Path, required=True)
args = parser.parse_args()
copy = args.copy.resolve()
blocked = (args.original_project.resolve(), args.model_directory.resolve())


def guard(event, fields):
    if event == "open" and isinstance(fields[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(fields[0])).resolve()
        if not path.is_relative_to(copy) and any(path.is_relative_to(root) for root in blocked):
            raise RuntimeError("portable audit attempted original data/weights access")
    if event == "socket.connect":
        raise RuntimeError("portable audit attempted network access")


sys.addaudithook(guard)
assert importlib.util.find_spec("torch") is None
assert importlib.util.find_spec("vllm") is None
# Import the implementation only after access restrictions are active.
from disastertrace.local_eval.audit import report  # noqa: E402

result = report(
    copy / "execution", copy / "run", copy / "model_report", require_model=True, verify=True
)
print(
    {
        **result,
        "relocated": True,
        "original_data_and_weights_blocked": True,
        "network_blocked": True,
        "torch_and_vllm_absent": True,
        "additional_model_calls": 0,
    }
)
