"""Verify immutable inputs, captured bytes, assembly and plan references offline."""

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
EXCLUDED = {"ARTIFACT_MANIFEST.json", "VERIFY_REPORT.json"}


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def read(path):
    def reject(value):
        raise ValueError("nonstandard JSON number: " + value)
    return json.loads(path.read_text(), parse_constant=reject)


def check_binding(binding, base=REPO):
    path = base / binding["path"]
    if not path.is_file() or digest(path) != binding["sha256"]:
        raise ValueError("bound file missing or changed: " + str(path))
    if "bytes" in binding and path.stat().st_size != binding["bytes"]:
        raise ValueError("bound byte length changed: " + str(path))


def files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and not {"parser_libs", "__pycache__"}.intersection(p.relative_to(ROOT).parts))


def main():
    inputs = read(ROOT / "INPUT_BINDINGS.json")
    for binding in inputs["inputs"] + inputs["existing_modified_files"]:
        check_binding(binding)
    env = {**os.environ, "SUDO_UID": "11329"}

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=REPO, env=env, text=True).strip()

    assert git("rev-parse", "HEAD") == inputs["head"], "HEAD changed"
    assert git("status", "--short", "--untracked-files=no") == inputs["tracked_status"], "tracked state changed"
    assert git("diff", "--cached", "--raw") == inputs["staged_raw"], "staging state changed"
    existing_manifest = ROOT / "ARTIFACT_MANIFEST.json"
    if existing_manifest.exists():
        for binding in read(existing_manifest)["files"]:
            check_binding(binding, ROOT)

    inherited = read(ROOT / "INHERITED_SAMPLE_AUDIT.json")
    for binding in inherited["file_bindings"]:
        check_binding(binding)
    inherited_joins = read(ROOT / "INHERITED_JOIN_BINDINGS.json")
    for binding in inherited_joins["files"]:
        check_binding(binding)
    capture_rows = []
    for manifest in sorted(ROOT.glob("captures_*/MANIFEST.json")):
        rows = read(manifest)
        specs = read(manifest.parent / "SPEC.json")
        assert {r["id"] for r in rows} == {s["id"] for s in specs}
        for record in rows:
            assert read(manifest.parent / (record["id"] + ".json")) == record
            if "raw" in record:
                check_binding({**record, "path": record["raw"]}, manifest.parent)
            if record.get("range_verified"):
                requested = re.fullmatch(r"bytes=(\d+)-(\d+)", record["headers"]["Range"])
                returned = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", record["response_headers"]["Content-Range"])
                assert requested and returned and requested.groups() == returned.groups()[:2]
                assert record["bytes"] == int(requested[2]) - int(requested[1]) + 1
            if "Range" in record.get("headers", {}) and record["status"] == "received":
                assert record["range_verified"]
        capture_rows.extend(rows)
    assert len({r["id"] for r in capture_rows}) == len(capture_rows)
    intent = read(ROOT / "PROBE_INTENT.json")
    assert len(capture_rows) <= intent["max_requests"]
    assert sum(r["max_bytes"] for r in capture_rows) <= intent["max_response_caps_sum_bytes"]
    assert all(r["max_bytes"] <= intent["max_single_response_bytes"] for r in capture_rows)
    assemblies = read(ROOT / "ASSEMBLY_MANIFEST.json")
    for item in assemblies:
        check_binding(item, ROOT)
        assembled = (ROOT / item["path"]).read_bytes()
        offset = 0
        origins = set()
        snapshots = set()
        for part in item["parts"]:
            receipt_path = ROOT / part["receipt"]
            receipt = read(receipt_path)
            raw = (receipt_path.parent / receipt["raw"]).read_bytes()
            assert offset == part["offset"] and len(raw) == part["bytes"]
            assert digest(receipt_path.parent / receipt["raw"]) == part["sha256"]
            assert assembled[offset:offset + len(raw)] == raw
            if offset:
                assert receipt["range_verified"]
                assert receipt["headers"]["Range"].startswith("bytes=" + str(offset) + "-")
            else:
                assert receipt.get("range_verified") or receipt.get("reason") == "response_body_cap"
            origins.add(receipt["url"])
            snapshots.add(receipt["response_headers"].get("Last-Modified"))
            offset += len(raw)
        assert offset == len(assembled) and len(origins) == 1 and len(snapshots) == 1

    audit = read(ROOT / "NEW_SAMPLE_AUDIT_05.json")
    for item in audit["reports"]:
        check_binding({"path": item["raw_path"], "sha256": item["sha256"]}, ROOT)
        assert item["level"] != "decode_failed"
    for item in audit["reports"]:
        if item["capture_id"].startswith("petss-"):
            assert item["details"]["station_blocks"] == 290
            assert item["details"]["values_per_station"] == {"102": 290}
            assert item["details"]["explicit_tropical_exclusion"]

    summary = read(ROOT / "CAPTURE_SUMMARY.json")
    assert summary["http_requests"] == len(capture_rows)
    assert summary["response_payload_bytes"] == sum(r.get("bytes", 0) for r in capture_rows)
    assert summary["request_status_counts"] == dict(Counter(r["status"] for r in capture_rows))
    assert summary["scientific_audit_records"] == sum(r["level"] != "rendered_product_only" for r in audit["reports"])
    sources = read(ROOT / "SOURCE_SAMPLE_INVENTORY.json")["sources"]
    by_source = {s["source_id"]: s for s in sources}
    assert len(sources) == len(by_source)
    for source in sources:
        assert source["evidence_refs"], source["source_id"]
        assert source["urls"], source["source_id"]
        for ref in source["evidence_refs"]:
            assert (ROOT / ref).is_file(), ref
    matrix = read(ROOT / "HAZARD_SOURCE_MATRIX.json")
    hazards = matrix["hazards"]
    assert [h["hazard_id"] for h in hazards] == [f"H{i:02}" for i in range(1, 17)]
    assert len({h["group"] for h in hazards}) == 6
    for hazard in hazards:
        for key in ("forecast_sources", "outcome_and_observation_sources", "auxiliary_or_benchmark_sources", "conditional_extension_sources"):
            assert all(s in by_source for s in hazard[key])
        assert set(hazard["outcome_kinds"]) <= {"O", "P", "R"}
        assert hazard["new_formal_tasks"] == 0
    assert audit["formal_new_tasks"] == audit["new_model_calls"] == 0

    parsed_json = 0
    links = []
    for path in files():
        if path.suffix == ".json" and path.name not in EXCLUDED:
            read(path)
            parsed_json += 1
        if path.suffix == ".md":
            for ref in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if re.match(r"[a-zA-Z]+://", ref) or ref.startswith("#"):
                    continue
                target = (path.parent / ref.split("#", 1)[0]).resolve()
                assert target.is_file() or target in {ROOT / name for name in EXCLUDED}, f"broken local link {path.name}: {ref}"
                links.append(ref)
    artifacts = []
    for path in files():
        if path.name not in EXCLUDED:
            artifacts.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest = {"excluded": ["parser_libs/**", "__pycache__/**", *sorted(EXCLUDED)], "files": artifacts}
    existing_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    output = {
        "status": "pass", "verified_at": datetime.now(timezone.utc).isoformat(),
        "original_head_tracked_changes_and_staged_diff_unchanged": True,
        "input_bindings_checked": len(inputs["inputs"]), "preexisting_modified_files_checked": len(inputs["existing_modified_files"]),
        "inherited_sample_files_checked": len(inherited["file_bindings"]),
        "additional_join_bindings_checked_not_disjoint": len(inherited_joins["files"]),
        "capture_requests": len(capture_rows), "response_payload_bytes": summary["response_payload_bytes"],
        "assemblies_verified": len(assemblies), "final_scientific_audit": "NEW_SAMPLE_AUDIT_05.json",
        "audit_records": len(audit["reports"]), "scientific_semantic_gates_still_apply": True,
        "source_records_not_independent_datasets": len(sources), "hazard_families": len(hazards),
        "json_artifacts_parsed": parsed_json, "local_markdown_links_checked": len(links),
        "artifact_files": len(artifacts), "artifact_manifest_sha256": digest(existing_manifest),
        "new_formal_tasks": 0, "new_model_calls": 0,
        "limits": ["Inherited scientific decoders not rerun.", "No broad model/application regression suite run for this data/plan work.", "Byte and schema checks do not establish scientific validity, historical visibility or licensing."]
    }
    (ROOT / "VERIFY_REPORT.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
