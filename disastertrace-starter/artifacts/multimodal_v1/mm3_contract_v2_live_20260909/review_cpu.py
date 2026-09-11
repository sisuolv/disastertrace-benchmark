"""Rebuild the MM-3 score from copied evidence with network and old paths denied."""

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
        path = bundle / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("review input changed: " + name)
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
    sys.path.insert(0, str(bundle / "batch/source/src"))
    from disastertrace.multimodal_live_v1.audit import reconstruct

    result = reconstruct(bundle / "batch", json.loads((bundle / "references.json").read_text()))
    expected = json.loads((bundle / "batch/REPORT.json").read_text())
    if result != expected:
        raise ValueError("reconstructed score differs")
    if "torch" in sys.modules or "transformers" in sys.modules:
        raise ValueError("score review unexpectedly imported a GPU backend")
    receipt = {"status": "passed", "files_verified": len(manifest["files"]), "score_reproduced": True,
               "torch_imported": False, "transformers_imported": False, "network": "audit-hook denied",
               "original_paths": "audit-hook denied", "generations": 0,
               "limitation": "Python audit hooks are not an OS sandbox for hostile code"}
    with args.receipt.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
