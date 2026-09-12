"""Recheck inherited raw evidence without rewriting any frozen files."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PRIOR = ROOT.parent / "v6_blueprint_sample_validation_20260911"


def main():
    bindings = {}

    def register(path, expected, size=None):
        key = str(path.resolve().relative_to(REPO))
        if key in bindings and bindings[key]["expected_sha256"] != expected:
            raise ValueError("Conflicting inherited binding: " + key)
        bindings[key] = dict(path=key, expected_sha256=expected, expected_bytes=size)

    for name, key in [("INHERITED_SAMPLE_AUDIT.json", "file_bindings"), ("INHERITED_JOIN_BINDINGS.json", "files")]:
        for entry in json.loads((PRIOR / name).read_text())[key]:
            register(REPO / entry["path"], entry["sha256"], entry.get("bytes"))
    for entry in json.loads((PRIOR / "ARTIFACT_MANIFEST.json").read_text())["files"]:
        register(PRIOR / entry["path"], entry["sha256"], entry["bytes"])
    auth = ROOT.parent / "earthdata_auth_validation_20260912"
    for file in auth.glob("**/*.json"):
        if file.stat().st_size > 3 * 1024 * 1024:
            continue
        try:
            data = json.loads(file.read_text())
        except (ValueError, UnicodeError):
            continue
        if not isinstance(data, dict):
            continue
        for row in data.get("rows", []):
            if row.get("body_file") and row.get("sha256"):
                register(file.parent / row["body_file"], row["sha256"], row.get("bytes"))
        records = data.get("samples", [data])
        for row in records:
            if isinstance(row, dict) and row.get("source_file") and row.get("source_sha256"):
                register(file.parent / row["source_file"], row["source_sha256"])
    results = []
    for row in bindings.values():
        path = REPO / row["path"]
        result = dict(row, exists=path.is_file())
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result.update(actual_sha256=digest.hexdigest(), actual_bytes=path.stat().st_size)
            result["passed"] = (result["actual_sha256"] == row["expected_sha256"] and
                                (row["expected_bytes"] is None or result["actual_bytes"] == row["expected_bytes"]))
        else:
            result["passed"] = False
        results.append(result)
    report = dict(files=len(results), bytes=sum(r.get("actual_bytes", 0) for r in results),
                  all_passed=all(r["passed"] for r in results), files_checked=results,
                  limit="Integrity verification reuses prior scientific decoding except the separately rerun decoders.")
    (ROOT / "INHERITED_INTEGRITY.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "files_checked"}))
    if not report["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
