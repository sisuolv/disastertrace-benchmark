"""Offline replay of original journals; not a raw-source rebuild or new inference."""
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
