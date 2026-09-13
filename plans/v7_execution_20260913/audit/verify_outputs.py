"""Rehash original inputs and reconcile the completed W0 delivery."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def load(path):
    return json.loads(path.read_text())


def check(item):
    name, expected = item
    actual = hashlib.sha256((REPO / name).read_bytes()).hexdigest()
    return None if actual == expected else name


def main():
    manifests = [HERE / "results_02/INPUT_BINDINGS.json", HERE / "diagnostics_03/INPUT_BINDINGS.json"]
    bindings = {}
    for path in manifests:
        for key, value in load(path)["sha256_by_repo_relative_path"].items():
            if key in bindings and bindings[key] != value:
                raise ValueError("Input binding conflict: " + key)
            bindings[key] = value
    with ThreadPoolExecutor(max_workers=8) as pool:
        differences = [x for x in pool.map(check, bindings.items()) if x is not None]
    if differences:
        raise ValueError("Input hashes changed: " + repr(differences))
    funnel = load(HERE / "results_02/REVISION_FUNNEL.json")
    links = Counter()
    identities = set()
    for line in (HERE / "results_02/CALL_LINKS.jsonl").open():
        row = json.loads(line)
        identity = (row["session"], row["call_id"])
        if identity in identities:
            raise ValueError("Duplicate call link")
        identities.add(identity)
        links[(row["cohort"], row["arm"])] += 1
    expected = funnel["total_model_arm_counts"]
    if len(identities) != expected["predictor_calls"] or expected["actual_model_calls"] != expected["predictor_calls"] + expected["selector_calls"]:
        raise ValueError("Call count identity failed")
    for cohort, value in funnel["cohorts"].items():
        for arm, counts in value["arms"].items():
            if links[(cohort, arm)] != counts["predictor_calls"]:
                raise ValueError("Arm link count failed")
    old = load(HERE / "diagnostics_02/FIXED_CANDIDATE_ACTION_REPORT.json")
    new = load(HERE / "diagnostics_03/FIXED_CANDIDATE_ACTION_REPORT.json")
    if old["cohorts"] != new["cohorts"]:
        raise ValueError("Style-only rerun changed numerical results")
    old_stability = load(HERE / "diagnostics_02/STABILITY_AND_INTERFACE.json")
    if old_stability != load(HERE / "diagnostics_03/STABILITY_AND_INTERFACE.json"):
        raise ValueError("Style-only rerun changed stability")
    artifacts = [HERE / "REPORT_CN.md", HERE / "TEST_RESULTS_03.xml", *manifests,
                 HERE / "results_02/REVISION_FUNNEL.json", HERE / "results_02/BASELINE_BACKOFF_AUDIT.json",
                 HERE / "results_02/SCORE_CROSSCHECK.json", HERE / "diagnostics_03/FIXED_CANDIDATE_ACTION_REPORT.json",
                 HERE / "diagnostics_03/STABILITY_AND_INTERFACE.json"]
    result = {"verified_at": datetime.now(timezone.utc).isoformat(), "input_hashes_checked": len(bindings),
              "input_hash_failures": differences, "unique_recorded_predictor_calls": len(identities),
              "model_arms": len(links), "funnel_denominators_reconciled": True,
              "repeated_action_replay_numerically_identical": True,
              "artifacts": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},
              "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "new_model_calls": 0}
    with (HERE / "VALIDATION.json").open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "artifacts"}, indent=2))


if __name__ == "__main__":
    main()
