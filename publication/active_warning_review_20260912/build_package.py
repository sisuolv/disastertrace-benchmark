"""Build a review attachment and an explicit publication allowlist without Git writes."""

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUB = Path(__file__).resolve().parent
MINI = Path("plans/active_warning_miniloop_20260912")
HYDRO = Path("plans/hydro_shadow_pilot_20260912")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def collect():
    selected = {}

    def add(path):
        source = ROOT / path
        if source.is_file():
            if source.is_symlink():
                raise ValueError("symlink outside reading scope")
            selected[str(path)] = source

    def tree(path):
        for source in sorted((ROOT / path).rglob("*")):
            relative = source.relative_to(ROOT)
            if not any(
                p in relative.parts
                for p in ("__pycache__", ".pytest_cache", ".ruff_cache")
            ):
                add(relative)

    for namespace in ("active_forecast", "active_warning_v1", "hydro_shadow_v1"):
        tree(Path("disastertrace-starter/src/disastertrace") / namespace)
        tree(Path("disastertrace-starter/tests") / namespace)
    tree(MINI)
    for source in sorted((ROOT / HYDRO).iterdir()):
        relative = source.relative_to(ROOT)
        if source.name == "shadow_01":
            continue
        tree(relative) if source.is_dir() else add(relative)
    shadow = HYDRO / "shadow_01"
    for name in ("code", "initial", "run/initial", "run/cycle_000"):
        tree(shadow / name)
    for name in (
        "FREEZE.json",
        "REGISTRY.json",
        "LAUNCH.json",
        "PREFIX_AUDIT_01.json",
        "verify_shadow.py",
        "run/CLAIM.json",
    ):
        add(shadow / name)
    selected[str(shadow / "run/PROGRESS.json")] = (
        ROOT / shadow / "run/cycle_000/COMPLETE.json"
    )
    for name in (
        "README_ACTIVE_WARNING_MINILOOP_20260912_CN.md",
        "README_HYDRO_SHADOW_PILOT_20260912_CN.md",
        "LATEST_PROGRESS_20260912_CN.md",
    ):
        add(Path(name))
    for name in json.loads(
        (ROOT / MINI / "dataset_v2/SOURCE_BINDINGS.json").read_text()
    ):
        add(Path(name))
        source = ROOT / name
        if source.name == "body.bin":
            for sibling in source.parent.glob("*.json"):
                add(sibling.relative_to(ROOT))
        elif source.suffix == ".raw":
            add(source.with_suffix(".json").relative_to(ROOT))
    for name in (
        "plans/v5_0910_feasibility_12h_20260910/data/NHC_PRODUCTS.json",
        "plans/v5_0910_feasibility_12h_20260910/data/NHC_OUTCOME_JOINS_PRIVATE.json",
        "plans/v6_data_decision_20260911/captures_02/nwps-scoc1-metadata.raw",
        "plans/v6_data_decision_20260911/captures_02/nwps-scoc1-metadata.json",
        "plans/v6_active_warning_review_20260911/RESEARCH_PLAN_CN.md",
        "plans/v6_blueprint_sample_validation_20260911/OVERALL_PLAN_REFINED_CN.md",
        "plans/v6_blueprint_sample_validation_20260911/HAZARD_SOURCE_MATRIX.md",
        "plans/v6_blueprint_sample_validation_20260911/SOURCE_SAMPLE_INVENTORY.md",
    ):
        add(Path(name))
    for source in sorted(PUB.rglob("*")):
        if (
            source.name not in ("PUBLICATION_CONTENTS.json", "READING_CONTENTS.json")
            and source.suffix != ".zip"
        ):
            add(source.relative_to(ROOT))
    return selected


def reading(path):
    parts = Path(path).parts
    if path.startswith("disastertrace-starter/src/") or path.startswith(
        "disastertrace-starter/tests/"
    ):
        return True
    if path.startswith("publication/active_warning_review_20260912/"):
        return True
    if Path(path).suffix == ".md":
        return True
    if path.startswith(str(MINI)):
        return (len(parts) == 3 and Path(path).suffix in (".py", ".json")) or (
            parts[2]
            in (
                "dataset_v2",
                "dataset_short_ids_v1",
                "model_results_01",
                "model_results_02",
                "programs_01",
            )
            and Path(path).suffix == ".json"
        )
    if path.startswith(str(HYDRO)):
        return (
            (len(parts) == 3 and Path(path).suffix in (".py", ".json"))
            or parts[2] == "admission_01"
            or (
                len(parts) == 4
                and parts[2] == "shadow_01"
                and Path(path).suffix == ".json"
            )
        )
    return False


def main():
    selected = collect()
    records = {
        name: {
            "sha256": sha(path.read_bytes()),
            "bytes": path.stat().st_size,
            "source_path": str(path.relative_to(ROOT)),
        }
        for name, path in sorted(selected.items())
    }
    contents = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": records,
        "scope": "complete minimum loop plus bound input dependencies and first hydro cycle; not later live captures",
    }
    with (PUB / "PUBLICATION_CONTENTS.json").open("x") as stream:
        json.dump(contents, stream, indent=2)
    subset = {name: record for name, record in records.items() if reading(name)}
    reading_manifest = {
        "created_at": contents["created_at"],
        "files": subset,
        "exclusions": [
            "full program/model traces and raw replies",
            "most raw provider response bodies",
            "model weights and installed environments",
            "future online results",
        ],
        "scope": "selected research/code reading; full score reconstruction uses the GitHub tree",
    }
    with (PUB / "READING_CONTENTS.json").open("x") as stream:
        json.dump(reading_manifest, stream, indent=2)
    archive_path = PUB / "chatgpt_pro_active_warning_review_20260912.zip"
    with zipfile.ZipFile(
        archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in subset:
            archive.write(selected[name], name)
        archive.write(PUB / "READING_CONTENTS.json", "READING_CONTENTS.json")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("corrupt reading archive")
        for name, record in subset.items():
            if sha(archive.read(name)) != record["sha256"]:
                raise ValueError("reading bytes differ")
    print(
        {
            "publication_files": len(records),
            "publication_bytes": sum(v["bytes"] for v in records.values()),
            "reading_files": len(subset),
            "zip_bytes": archive_path.stat().st_size,
            "zip_sha256": sha(archive_path.read_bytes()),
        }
    )


if __name__ == "__main__":
    main()
