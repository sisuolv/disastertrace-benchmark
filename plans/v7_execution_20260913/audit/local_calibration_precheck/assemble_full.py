"""Join complete receipts, retaining the failed transport and one bounded retry."""

import hashlib
import json
import shutil
from pathlib import Path

from precheck import HERE, REPO, capture


def main():
    plan = json.loads((HERE / "FULL_NATIVE_PLAN.json").read_text())
    origins = {k: REPO / v for k, v in plan["reused"].items()}
    for spec in plan["requests"]:
        identity = spec["id"]
        original = HERE / "full_native_new_01"
        receipt = json.loads((original / (identity + ".json")).read_text())
        origins[identity] = original if receipt["complete"] else HERE / "native_retry_02"
    verified = {identity: capture(origin, identity)[1] for identity, origin in origins.items()}
    output = HERE / "full_native_01"
    output.mkdir(exist_ok=False)
    for identity, origin in sorted(origins.items()):
        for suffix in (".body", ".json"):
            shutil.copyfile(origin / (identity + suffix), output / (identity + suffix))
    (output / "MANIFEST.json").write_text(json.dumps({"planned": len(origins), "attempted": len(origins),
                                                    "rows": [verified[k] for k in sorted(verified)],
                                                    "assembly_is_not_network": True}, indent=2) + "\n")
    (output / "ORIGINS.json").write_text(json.dumps({"sources": {k: str(p.relative_to(REPO)) for k, p in origins.items()},
                                                   "failed_original_retained": str((HERE / "full_native_new_01/MANIFEST.json").relative_to(REPO)),
                                                   "assembly_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + "\n")
    print(json.dumps({"assembled_native_products": len(origins), "bytes": sum(r["bytes"] for r in verified.values())}))


if __name__ == "__main__":
    main()
