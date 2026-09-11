"""Reconstruct and analyze the fixed V2 run after the GPU worker completes."""

from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
CPU = "/mnt/afs/260010168/.venvs/disastertrace-mm-cpu-v1/bin/python"
VLM = "/mnt/afs/260010168/.venvs/disastertrace-mm-vlm-v1/bin/python"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def command(name, argv, *, env):
    record = {"argv": argv, "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    save(ROOT / "validation" / (name + "_intent.json"), record)
    result = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
    save(ROOT / "validation" / (name + "_result.json"), {
        "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
        "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    if result.returncode:
        raise RuntimeError("validation command failed: " + name)
    print(name, result.stdout[-1500:], flush=True)


def main():
    done = read(ROOT / "gpu_run/DONE.json")
    if done["generation_intents"] != 12:
        raise ValueError("incomplete generation scope")
    execution = read(ROOT / "EXECUTION.json")
    references = ROOT.parent / "mm0_2_20260909/build_02/private/references.json"
    if sha(references) != execution["reference_sha256"]:
        raise ValueError("reference changed")
    save(ROOT / "FINALIZATION_CLAIM.json", {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "execution_sha256": sha(ROOT / "EXECUTION.json"), "reference_sha256": sha(references)})
    env = dict(os.environ, PYTHONPATH=str(ROOT / "source/src"), PYTHONDONTWRITEBYTECODE="1",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    command("score", [CPU, "-m", "disastertrace.multimodal_live_v1.audit", "--batch", str(ROOT),
            "--references", str(references), "--output", str(ROOT / "REPORT.json")], env=env)
    command("input_replay", [VLM, str(ROOT / "verify_captures.py"), "--batch", str(ROOT),
            "--output", str(ROOT / "input_replay_01")], env=env)
    sys.path.insert(0, str(ROOT / "source/src"))
    from disastertrace.multimodal_v1.scoring import field_equal

    plan, refs, report = read(ROOT / "REQUEST_PLAN.json"), read(references), read(ROOT / "REPORT.json")
    field_counts, errors, coverage = Counter(), [], Counter()
    for trajectory in plan["trajectories"]:
        for index, template in enumerate(trajectory["requests"]):
            slot = ROOT / "gpu_run/live" / trajectory["id"] / f"{index:04d}"
            outcome = read(slot / "outcome.json")
            gold = refs[trajectory["branch"]][int(template["checkpoint"][1:])]["state"]
            predicted = outcome.get("value", {}).get("state", {}) if outcome["status"] == "received_valid" else {}
            for site, expected in gold.items():
                for field in sorted(expected):
                    coverage[field] += 1
                    if not field_equal(site, field, predicted.get(site, {}), expected):
                        field_counts[field] += 1
                        errors.append({"trajectory": trajectory["id"], "checkpoint": template["checkpoint"],
                                       "site": site, "field": field,
                                       "prediction_present": field in predicted.get(site, {}),
                                       "predicted": predicted.get(site, {}).get(field), "expected": expected[field],
                                       "outcome_status": outcome["status"]})
    save(ROOT / "ERROR_ANALYSIS.json", {"posthoc": True, "score_repair": False,
         "field_opportunities": dict(coverage), "field_errors": dict(field_counts), "errors": errors,
         "warning": "missing/invalid answers remain errors; no causal attribution of model internals"})
    previous = read(ROOT.parent / "mm3_20260909/REPORT.json")
    comparison = {
        "interpretation": "descriptive development comparison; not balanced independent causal evidence",
        "event_count": 1, "same_model_and_decode_settings": True,
        "old": {"valid": previous["counts"].get("received_valid", 0), "planned": 12,
                "strict_correct": previous["strict_correct"], "report_sha256": sha(ROOT.parent / "mm3_20260909/REPORT.json")},
        "v2": {"valid": report["counts"].get("received_valid", 0), "planned": 12,
               "strict_correct": report["strict_correct"], "report_sha256": sha(ROOT / "REPORT.json")},
    }
    save(ROOT / "DESCRIPTIVE_COMPARISON.json", comparison)
    review = PROJECT / "work/mm3-v2-cpu-review-20260909"
    review.mkdir(parents=True, exist_ok=False)
    (review / "batch").mkdir()
    for name in ["EXECUTION.json", "REQUEST_PLAN.json", "REPORT.json"]:
        shutil.copyfile(ROOT / name, review / "batch" / name)
    shutil.copytree(ROOT / "source", review / "batch/source", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "gpu_run/live", review / "batch/gpu_run/live")
    shutil.copyfile(references, review / "references.json")
    shutil.copyfile(ROOT / "review_cpu.py", review / "review_cpu.py")
    manifest = {"files": {str(p.relative_to(review)): sha(p) for p in review.rglob("*") if p.is_file()},
                "reference_sha256": sha(references),
                "denied_paths": [str(ROOT), str(PROJECT / "src"), "/mnt/afs/260010168/models"]}
    save(review / "REVIEW_MANIFEST.json", manifest)
    command("relocated_review", [CPU, str(review / "review_cpu.py"), "--bundle", str(review),
            "--receipt", str(review / "CPU_REVIEW_RESULT.json")], env=env)
    shutil.copyfile(review / "CPU_REVIEW_RESULT.json", ROOT / "CPU_REVIEW_RESULT.json")
    save(ROOT / "FINALIZATION_RESULT.json", {"status": "passed", "report_sha256": sha(ROOT / "REPORT.json"),
         "interface_gate": report["interface_gate"], "strict_correct": report["strict_correct"],
         "reference_sha256": sha(references), "new_generations": 0})
    print(json.dumps(comparison, indent=2), flush=True)


if __name__ == "__main__":
    main()
