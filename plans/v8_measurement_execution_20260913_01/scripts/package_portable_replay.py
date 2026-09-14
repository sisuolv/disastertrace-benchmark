"""Copy and re-score two original real program journals without model weights."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "portable_replay_01"

RUNNER = '''"""Offline replay of original journals; not a raw-source rebuild or new inference."""
import json
import hashlib
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "source"))
def deny_network(*args, **kwargs):
    raise RuntimeError("Network disabled for this replay")
socket.socket = deny_network
socket.create_connection = deny_network
socket.getaddrinfo = deny_network
from disastertrace.monitoring_fixed_v1.admission import score_admitted
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
read = lambda p: json.loads(p.read_text())
manifest = read(ROOT / "MANIFEST.json")
for rel, expected in manifest["files"].items():
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected, rel
contract = read(ROOT / "data/COMPARISON.json")["payload"]
arms = manifest["selected_arms"]
score = score_admitted(read(ROOT / "data/OUTCOMES.json"),
    {a: ROOT / "data" / (a + ".jsonl") for a in arms},
    comparison=ComparisonContract(contract["invariants"], contract["allowed_interventions"]))
original = read(ROOT / "data/ORIGINAL_SCORES.json")
assert score["outcome_sha256"] == original["outcome_sha256"]
assert score["time_basis"] == original["time_basis"]
for a in arms:
    assert score["scores"]["arms"][a] == original["scores"]["arms"][a]
    assert score["admission_statuses"][a] == original["admission_statuses"][a]
for key in ("registered", "settled", "missing", "score"):
    assert score["scores"][key] == original["scores"][key]
result = {"passed": True, "selected_arms": arms,
    "opportunities_per_arm": score["scores"]["registered"],
    "matches_original_scoring": True, "actual_model_calls": 0,
    "network_calls": 0, "python_network_access_blocked": True,
    "scope": "Original216-opportunity Follow and shared-batch program journals replayed from this relocated bundle. Does not rebuild original native acquisition or independently re-tokenize model captures."}
with (ROOT / "VALIDATION.json").open("x") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result))
'''


def main():
    OUT.mkdir(exist_ok=False)
    source = HERE / "reports/program_calendar_optimized_audit_01/source/disastertrace"
    shutil.copytree(
        source,
        OUT / "source/disastertrace",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    original = HERE / "reports/program_calendar_02/1000__base_bound_override"
    score = (
        HERE
        / "reports/program_calendar_optimized_audit_01/1000__base_bound_override/SCORES.json"
    )
    assert json.loads(score.with_name("VALIDATION.json").read_text())["passed"]
    data = OUT / "data"
    data.mkdir()
    for name in ("OUTCOMES.json", "COMPARISON.json"):
        shutil.copyfile(original / name, data / name)
    shutil.copyfile(score, data / "ORIGINAL_SCORES.json")
    arms = ["P00_follow", "P03_batch_shared"]
    for arm in arms:
        shutil.copyfile(original / arm / "admission.jsonl", data / (arm + ".jsonl"))
    (OUT / "replay.py").write_text(RUNNER)
    (OUT / "README.md").write_text(
        "# Portable real-journal replay\n\n"
        "Run `python3 replay.py` with Python3.11 or newer. No model weights, API key, "
        "GPU or new network request is required.\n\n"
        "This package replays two original216-opportunity development arms, checks "
        "the event transactions and canonical result/comparison contract, and "
        "matches their previously scored results. It is not a rebuild of the "
        "native downloads, a model/token audit or independent scientific confirmation.\n"
    )
    files = {
        str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in OUT.rglob("*")
        if p.is_file()
    }
    with (OUT / "MANIFEST.json").open("x") as handle:
        json.dump(
            {
                "files": files,
                "selected_arms": arms,
                "original_score_sha256": hashlib.sha256(score.read_bytes()).hexdigest(),
                "archive_scope": "Small real replay subset; full experiment stays in original execution directory.",
            },
            handle,
            indent=2,
        )
    print(
        json.dumps(
            {
                "files": len(files),
                "bytes": sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()),
                "output": str(OUT),
            }
        )
    )


if __name__ == "__main__":
    main()
