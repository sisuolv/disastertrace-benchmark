"""Package one complete captured model study for offline CPU rescoring."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    batch, out = args.batch.absolute(), args.out.absolute()
    plan = json.loads((batch / "PLAN.json").read_text())
    audit = json.loads((batch / "final_audit_01/RESULT.json").read_text())
    if plan["api_models"] or not audit["passed"]:
        raise ValueError("Requires the completed local-only paired model study")
    out.mkdir(exist_ok=False)
    files = set(plan["files"])
    files.add("PLAN.json")
    for task in plan["tasks"]:
        for suffix in ("request", "response", "publication"):
            files.add("gpu/worker_0/" + task["call_id"] + "." + suffix + ".json")
    for path in (batch / "final_audit_01/scores").iterdir():
        files.add(str(path.relative_to(batch)))
    files.update(
        {"final_audit_01/RESULT.json", "final_audit_01/LOCAL_TOKEN_AUDIT.json"}
    )
    for name in sorted(files):
        source = batch / name
        if source.is_symlink() or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Invalid source path")
        if name in plan["files"] and digest(source) != plan["files"][name]:
            raise ValueError("Frozen study changed: " + name)
        target = out / "study" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(
        Path(__file__).with_name("verify_model_capsule.py"), out / "verify.py"
    )
    (out / "README.md").write_text(
        "# Complete captured-model rescoring capsule\n\n"
        "Run `python3 -B verify.py --capsule . --result ../model-rescoring.json` "
        "with Python 3.10 or newer. No third-party package, model, API, or network "
        "is needed. Use a fresh result location: the rescoring output is never overwritten.\n\n"
        "All 212 original Qwen3-235B tasks, visible inputs, references, fitted banks, "
        "requests, replies, publication receipts, and the original frozen scorer are included. "
        "Both invalid replies remain. The verifier checks byte bindings, reruns the full "
        "scorer, independently recomputes Brier statistics and same-member temperature "
        "event fractions, and compares every score row with the original.\n\n"
        "This rebuilds the captured-model scores, not the model generations. Original "
        "token qualification is included as a receipt; tokenizer/weights are excluded. "
        "Full source archives, training-data reconstruction, active-session journals, "
        "API experiments, and physical measurement truth are outside this capsule. "
        "The raw METAR text is reparsed by the frozen provider parser, not a second "
        "independent physical decoder. The Python audit hook prevents accidental "
        "network and original-workspace reads in this verifier; it is not an adversarial sandbox.\n"
    )
    manifest = {
        "schema": "disastertrace.captured_model_capsule.v1",
        "source_plan_sha256": digest(batch / "PLAN.json"),
        "benchmark_tasks": len(plan["tasks"]),
        "model_calls_from_replay": 0,
        "original_root_blocked": "/mnt/afs/260010168",
        "files": {},
    }
    for path in sorted(out.rglob("*")):
        if path.is_file():
            manifest["files"][str(path.relative_to(out))] = {
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"files": len(manifest["files"]), "tasks": len(plan["tasks"])}))


if __name__ == "__main__":
    main()
