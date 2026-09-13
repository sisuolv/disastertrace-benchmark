"""Join complete public captures and bounded retries, preserving every source receipt."""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    plan = json.loads(args.plan.read_text())
    manifest_path = args.original / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["attempted"] != manifest["planned"] or manifest["plan_sha256"] != digest(args.plan):
        raise ValueError("Original capture sequence is incomplete or uses another plan")
    chosen = []
    for spec in plan["requests"]:
        ident = spec["id"]
        found = None
        for directory in [args.original, *args.retries]:
            path = directory / (ident + ".json")
            if not path.is_file():
                continue
            receipt = json.loads(path.read_text())
            body = directory / (ident + ".body")
            if receipt["url"] != spec["url"] or receipt["id"] != ident:
                raise ValueError("Retry changed the requested resource")
            if not receipt.get("complete") or receipt["http_status"] != 200 or receipt.get("curl_exit", 0):
                continue
            if digest(body) != receipt["sha256"] or body.stat().st_size != receipt["bytes"]:
                raise ValueError("Public capture hash or size mismatch")
            found = (body, path, receipt)
            break
        if found is None:
            raise ValueError("No complete verified capture: " + ident)
        chosen.append(found)
    args.output.mkdir(exist_ok=False)
    rows, origins = [], []
    for body, path, receipt in chosen:
        for source in (body, path):
            shutil.copyfile(source, args.output / source.name)
        rows.append(receipt)
        origins.append({"id": receipt["id"], "directory": str(path.parent.resolve()),
                        "receipt_sha256": digest(path), "body_sha256": digest(body)})
    result = {"planned": len(chosen), "attempted": len(chosen), "rows": rows,
        "plan_sha256": digest(args.plan), "assembled_at": datetime.now(timezone.utc).isoformat(),
        "assembly_is_not_a_network_request": True, "origins": origins,
        "prior_attempt_manifests": {str((p / "MANIFEST.json").resolve()): digest(p / "MANIFEST.json")
                                    for p in [args.original, *args.retries]},
        "implementation_sha256": digest(Path(__file__))}
    with (args.output / "MANIFEST.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    shutil.copyfile(__file__, args.output / "assemble_public_captures.py")
    print(json.dumps({"verified_captures": len(chosen), "prior_failures_retained": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--retries", type=Path, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
