"""Recheck registered study inputs without following unrelated archives or launchers."""

import argparse
import datetime as dt
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run, out = args.run.absolute(), args.out.absolute()
    out.mkdir(exist_ok=False)
    bindings, scopes = {}, {}

    def bind(path, sha, scope):
        path = path.absolute()
        if path in bindings and bindings[path] != sha:
            raise ValueError("One immutable file has conflicting expected identities")
        bindings[path] = sha
        scopes.setdefault(scope, set()).add(str(path))

    for name in [
        "fixed_packet_01",
        "feature_temperature_trial_02",
        "large_feature_trial_01",
        "clarified_feature_trial_01",
        "selector_trial_01",
        "multicutoff_01",
        "query_controls_01",
        "native_feature_sessions_01",
        "seasonal_evaluation_01",
        "seasonal_controls_01",
        "calendar_feature_ablation_01/evaluation_01",
    ]:
        path = run / name / "PLAN.json"
        plan = read(path)
        if not plan.get("files"):
            raise ValueError("Missing immutable input inventory: " + name)
        for rel, sha in plan["files"].items():
            if Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise ValueError("Study inventory leaves its registered directory")
            bind(path.parent / rel, sha, name)

    parent = run / "native_feature_bank_01"
    freeze = read(parent / "BANK_FREEZE_BEFORE_EVALUATION.json")
    for field in ("bank_files", "source_files"):
        for rel, sha in freeze[field].items():
            bind(parent / rel, sha, "native_feature_bank_01")
    ablation = run / "calendar_feature_ablation_01"
    spec = read(ablation / "FIT_SPEC.json")
    bind(
        parent / "BANK_FREEZE_BEFORE_EVALUATION.json",
        spec["parent_bank_freeze_sha256"],
        "calendar_ablation_parent",
    )
    for rel, sha in spec["files"].items():
        bind(ablation / rel, sha, "calendar_ablation_source")
    fresh = read(ablation / "BANK_FREEZE_BEFORE_SEASONAL_EVALUATION.json")
    bind(parent / "ROLE_IDS.json", fresh["role_ids_sha256"], "original_fit_roles")
    for name, sha in fresh["banks"].items():
        bind(ablation / "banks" / (name + ".json"), sha, "calendar_ablation_banks")
    for item in read(run / "BASELINE.json")["inputs"]:
        bind(Path(item["path"]), item["sha256"], "supplied_review_inputs")

    def verify(pair):
        path, expected = pair
        if path.is_symlink() or digest(path) != expected:
            raise ValueError("Immutable registered input differs: " + str(path))
        return {"path": str(path), "sha256": expected, "bytes": path.stat().st_size}

    with ThreadPoolExecutor(max_workers=8) as pool:
        verified = list(pool.map(verify, sorted(bindings.items())))
    (out / "VERIFIED_FILES.json").write_text(json.dumps(verified, indent=2) + "\n")
    result = {
        "passed": True,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verified_files": len(verified),
        "scopes": {key: len(value) for key, value in scopes.items()},
        "verified_bytes": sum(row["bytes"] for row in verified),
        "ablation_parent_and_original_fit_role_hashes_verified": True,
        "no_model_calls_or_refits": True,
        "confirmation_payload_read": False,
        "scope": "Declared immutable study inputs and supplied review files; outcome correctness is audited separately",
    }
    (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
