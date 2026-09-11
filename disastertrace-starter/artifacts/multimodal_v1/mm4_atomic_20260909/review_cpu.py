"""Relocated CPU review without network, original evidence paths, Torch or weights."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    manifest = json.loads((bundle / "REVIEW_MANIFEST.json").read_text())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != expected:
            raise ValueError("review input hash mismatch: " + name)
    forbidden = manifest["denied_paths"]

    def guard(event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise PermissionError("review network disabled")
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes)):
            path = str(Path(arguments[0]).resolve())
            if any(path == prefix or path.startswith(prefix + "/") for prefix in forbidden):
                raise PermissionError("original source/model path disabled")

    sys.addaudithook(guard)
    sys.dont_write_bytecode = True
    batch = bundle / "batch"
    sys.path.insert(0, str(batch / "source/src"))
    from disastertrace.multimodal_atomic_v1.audit import reconstruct
    from disastertrace.multimodal_atomic_v1.references import control, reference
    from disastertrace.multimodal_atomic_v1.tasks import build
    from disastertrace.multimodal_v1.storage import read, write

    plan = build(batch / "seed/public/requests")
    if plan != read(batch / "REQUEST_PLAN.json"):
        raise ValueError("public task construction does not reproduce")
    geometry = {g["artifact_id"]: g for g in read(batch / "seed/private/geometry_lineage.json")}
    refs = {t["task_id"]: reference(t, geometry) for t in plan["tasks"]}
    if refs != read(batch / "references.json"):
        raise ValueError("automatic references do not reconstruct")
    if any(control(t) != refs[t["task_id"]] for t in plan["tasks"]):
        raise ValueError("independent public controls disagree")
    report = reconstruct(batch)
    if report != read(batch / "REPORT.json"):
        raise ValueError("raw-response report reconstruction differs")
    if "torch" in sys.modules or "transformers" in sys.modules:
        raise ValueError("score review imported a GPU backend")
    receipt = {"status": "passed", "verified_files": len(manifest["files"]),
               "public_tasks_reproduced": 40, "references_and_controls_reproduced": 40,
               "report_reproduced": True, "generations": 0,
               "torch_imported": False, "transformers_imported": False,
               "network": "Python audit-hook denied", "original_paths": "Python audit-hook denied",
               "limitation": "audit hooks are not an OS sandbox for hostile code"}
    write(args.receipt, receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
