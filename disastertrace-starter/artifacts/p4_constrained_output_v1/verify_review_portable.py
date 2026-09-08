"""Reconstruct P4 scores and both analyses from relocated files, denying originals."""

import argparse
import importlib.util
import json
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
            raise RuntimeError("portable review attempted original project/weights access")
    if event == "socket.connect":
        raise RuntimeError("portable review attempted network access")


sys.addaudithook(guard)
assert importlib.util.find_spec("torch") is None
assert importlib.util.find_spec("vllm") is None
from disastertrace.constrained_eval.audit import report  # noqa: E402
from disastertrace.local_eval.storage import read, verify_seal, write  # noqa: E402

bundle = copy / "artifacts/p4_constrained_output_v1"
run = copy / "work/p4-qwen3-constrained-v1"
result = report(
    bundle / "execution_live", run, bundle / "model_report", require_model=True, verify=True
)


def module(name):
    spec = importlib.util.spec_from_file_location("portable_" + name, bundle / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


analysis, table = module("analyze_results").generate(run)
verify_seal(bundle / "analysis")
assert analysis == read(bundle / "analysis/analysis.json")
assert table == (bundle / "analysis/RESULT_TABLES.md").read_text()
comparison = module("compare_tracks").generate(
    free_run=copy / "work/p3-qwen3-balanced-v1", constrained_run=run
)
verify_seal(bundle / "track_comparison")
assert comparison == read(bundle / "track_comparison/comparison.json")
observation = {
    **result,
    "analysis_id": analysis["analysis_id"],
    "comparison_id": comparison["comparison_id"],
    "relocated": True,
    "original_data_and_weights_blocked": True,
    "network_blocked": True,
    "torch_and_vllm_absent": True,
    "additional_model_calls": 0,
}
write(copy / "verification_result.json", observation)
print(json.dumps(observation, sort_keys=True))
