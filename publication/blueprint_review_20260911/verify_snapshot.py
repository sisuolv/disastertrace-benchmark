"""Check the published reading snapshot without raw arrays or network access."""

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PLAN = ROOT / "plans/v6_blueprint_sample_validation_20260911"


def main():
    manifest_path = HERE / "PUBLICATION_FILES.json"
    archive_mode = not manifest_path.exists()
    manifest = json.loads((ROOT / "READING_SCOPE.json" if archive_mode else manifest_path).read_text())
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        raw = path.read_bytes()
        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"], item["path"]
    summary = json.loads((PLAN / "CAPTURE_SUMMARY.json").read_text())
    rows = [r for p in sorted(PLAN.glob("captures_*/MANIFEST.json")) for r in json.loads(p.read_text())]
    assert len(rows) == summary["http_requests"] == 125
    assert sum(r.get("bytes", 0) for r in rows) == summary["response_payload_bytes"] == 94916311
    hazards = json.loads((PLAN / "HAZARD_SOURCE_MATRIX.json").read_text())["hazards"]
    assert [h["hazard_id"] for h in hazards] == [f"H{i:02}" for i in range(1, 17)]
    sources = json.loads((PLAN / "SOURCE_SAMPLE_INVENTORY.json").read_text())["sources"]
    assert len(sources) == 97
    audit = json.loads((PLAN / "NEW_SAMPLE_AUDIT_05.json").read_text())
    assert sum(r["level"] != "rendered_product_only" for r in audit["reports"]) == 31
    assert audit["formal_new_tasks"] == audit["new_model_calls"] == 0
    links = 0
    entrypoints = [HERE / "README.md", HERE / "REVIEW_FOR_CHATGPT_PRO_CN.md", PLAN / "OVERALL_PLAN_REFINED_CN.md", PLAN / "HAZARD_SOURCE_MATRIX.md", PLAN / "SOURCE_SAMPLE_INVENTORY.md"]
    for path in entrypoints:
        for ref in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if re.match(r"[a-zA-Z]+://", ref) or ref.startswith("#"):
                continue
            target = path.parent / ref.split("#", 1)[0]
            if target.name == "PUBLICATION_VALIDATION.json":
                continue
            if archive_mode and target.name in {"PUBLICATION_FILES.json", "disastertrace_blueprint_review.zip"}:
                continue
            assert target.is_file(), f"missing entrypoint link in {path.name}: {ref}"
            links += 1
    result = {"status": "pass", "archive_mode": archive_mode, "published_files_sha256_checked": len(manifest["files"]), "entrypoint_links_checked": links, "hazard_families": 16, "source_records_not_independent_datasets": 97, "http_requests": 125, "raw_arrays_redecoded": False, "new_model_calls": 0}
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    main()
