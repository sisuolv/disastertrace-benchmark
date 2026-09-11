"""Relocated CPU verification; original-repository reads and network are denied."""

import hashlib
import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ORIGINAL = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "source"))
blocked = {"original_reads": 0, "network": 0}


def audit(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.bind"}:
        blocked["network"] += 1
        raise PermissionError("network disabled for relocated CPU review")
    if event in {"open", "os.listdir", "os.scandir"} and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(ORIGINAL):
            blocked["original_reads"] += 1
            raise PermissionError("original repository reads disabled")


sys.addaudithook(audit)
try:
    with (ORIGINAL / "RESULTS_20260909.md").open("rb"):
        raise AssertionError("original repository unexpectedly readable")
except PermissionError:
    pass
try:
    socket.getaddrinfo("example.com", 443)
    raise AssertionError("network unexpectedly available")
except PermissionError:
    pass

from disastertrace.multimodal_v1.build import build_seed
from disastertrace.multimodal_v1.diagnostics import reconstruct

result = reconstruct(ROOT / "build", ROOT / "diagnostics/runs")
assert result == json.loads((ROOT / "diagnostics/report.json").read_text())
admission = build_seed(ROOT / "build/inputs", ROOT / "rebuilt")


def inventory(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


original_files, rebuilt_files = inventory(ROOT / "build"), inventory(ROOT / "rebuilt")
assert original_files == rebuilt_files, "source-only rebuild differs from captured task"
assert blocked == {"original_reads": 1, "network": 1}, blocked
assert "torch" not in sys.modules and "vllm" not in sys.modules
receipt = {"status": "passed", "policy_count": len(result["summaries"]), "model_calls": 0,
           "raw_source_rebuild_files": len(original_files), "raw_source_rebuild_equal": True,
           "reference_and_capture_reconstruction_equal": True, "denial_probes": blocked,
           "torch_loaded": False, "vllm_loaded": False, "event_count": admission["event_count"],
           "isolation_mechanism": "Python audit hooks and relocated files; trusted CPU review code, not an OS security sandbox"}
with (ROOT / "CPU_REVIEW.json").open("x") as stream:
    json.dump(receipt, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(receipt, sort_keys=True), flush=True)
