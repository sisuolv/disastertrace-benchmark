"""Check only the published reading files; original scientific arrays are not bundled."""

import ast
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V6 = ROOT / "plans/v6_0911_dataset_selection"


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(HERE / "PUBLICATION_FILES.json")
    checked = 0
    for name, expected in manifest["files_sha256"].items():
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("missing or nonregular reading file: " + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("reading file hash mismatch: " + name)
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=name)
        checked += 1
    registry = read(V6 / "SOURCE_REGISTRY.json")
    sources = registry["sources"]
    assert len(sources) == len({r["source_id"] for r in sources}) == 74
    assert sum(r["seed_id_preserved"] for r in sources) == 54
    assert all(not r["new_task_admitted"] for r in sources)
    hazards = read(V6 / "HAZARD_COVERAGE.json")
    assert {r["hazard_id"] for r in hazards} == {f"H{i:02d}" for i in range(1, 17)}
    old = {r["id"]: r for r in read(V6 / "analysis/DOWNLOADED_AUDIT.json")["reports"]}
    new = {r["id"]: r for r in read(V6 / "analysis/SELECTION_AUDIT.json")["reports"]}
    assert len(new) == 10 and all(r["level"] == "verified" for r in new.values())
    assert sum(old[k]["details"]["records"] for k in ["storm-events-2021-assembled", "storm-events-2023-assembled"]) == 136982
    assert new["exebench-coldwave"]["details"]["source_case_ids"] == 9
    assert new["exebench-coldwave"]["details"]["time_steps"] == 559
    assert new["ewb-hourly-rowgroup"]["details"]["decoded_rows"] == 122880
    assert all(t["flood_pixels"] == 0 for t in new["geoid-complete-pairs-and-cems"]["details"]["tiles"])
    assert new["droughted-prefix"]["details"]["fractional_score_rows"] == 1330
    assert new["droughted-prefix"]["details"]["observed_date_max"] == "2016-12-31"
    counts = read(V6 / "DATA_COUNTS.json")
    assert counts["new_model_calls"] == counts["new_gpu_jobs"] == 0
    assert counts["event_family_total"] is None
    assert read(V6 / "VERIFY_REPORT.json")["status"] == "passed"
    assert len(read(V6 / "NEXT_ACQUISITION_MANIFEST.json")["items"]) == 12
    print(json.dumps({"status": "passed", "files_sha256_checked": checked,
                      "scope": "published reading files and cross-report assertions",
                      "raw_scientific_arrays_replayed": False, "model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
