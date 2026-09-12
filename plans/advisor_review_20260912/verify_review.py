"""Check the advisor packet against saved evidence without new acquisition."""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DATA = ROOT.parent / "all_candidate_data_validation_20260912"
PILOT = ROOT.parent / "active_warning_miniloop_20260912"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def binding(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.relative_to(REPO)),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(
            "Preserve the existing verification; use a new output path."
        )

    checks = []

    def check(name, passed, details):
        checks.append({"name": name, "passed": bool(passed), "details": details})

    registry_path = DATA / "CANDIDATE_REGISTRY.json"
    registry = read_json(registry_path)
    sources = registry["sources"]
    source_ids = {row["source_id"] for row in sources}
    counts = dict(Counter(row["state"] for row in sources))
    expected = {
        "decoded_sample": 75,
        "partial_intended_content": 3,
        "catalog_records_only": 6,
        "no_decoded_target_sample": 8,
        "authorization_pending": 4,
        "rendered_product_only": 1,
    }
    check(
        "candidate_registry_counts",
        len(sources) == len(source_ids) == 97
        and counts == expected == registry["state_counts"],
        counts,
    )
    check(
        "sample_access_is_not_task_admission",
        registry["all_candidates_formally_admitted"] is False
        and not any(row["new_formal_task_admitted"] for row in sources)
        and registry["new_model_calls"] == registry["new_gpu_jobs"] == 0,
        {
            "formal_new_tasks": 0,
            "model_calls": registry["new_model_calls"],
            "gpu_jobs": registry["new_gpu_jobs"],
        },
    )

    docs = [
        ROOT / "PROPOSAL_FOR_ADVISOR_CN.md",
        ROOT / "CANDIDATE_SELECTION_CN.md",
        DATA / "README_CN.md",
    ]
    local_refs = set()
    missing = []
    link_count = 0
    # These documents use simple inline links, with no titles or literal parentheses.
    for path in docs:
        for href in re.findall(r"\[[^\]\n]*\]\(([^\)\n]+)\)", path.read_text()):
            parsed = urlsplit(href.strip("<>"))
            if parsed.scheme or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            link_count += 1
            if not target.exists():
                missing.append({"document": str(path.relative_to(REPO)), "link": href})
            elif target.is_file():
                local_refs.add(target)
    check(
        "document_local_links",
        not missing,
        {"checked_links": link_count, "missing": missing},
    )

    selection_text = docs[1].read_text()
    selected_ids = set(re.findall(r"\b(?:D\d{2}|AW-[A-Z][A-Z0-9]*)\b", selection_text))
    check(
        "selection_source_ids",
        selected_ids <= source_ids,
        {
            "referenced_ids": sorted(selected_ids),
            "unknown_ids": sorted(selected_ids - source_ids),
        },
    )
    hazard_rows = re.findall(r"^\| (H\d{2}) ", selection_text, re.MULTILINE)
    check(
        "sixteen_hazard_rows",
        hazard_rows == [f"H{i:02d}" for i in range(1, 17)],
        {"hazard_rows": hazard_rows},
    )

    audit_paths = [
        DATA / name
        for name in [
            "NEW_AUDIT_02.json",
            "EXTENDED_AUDIT_03.json",
            "SUPPLEMENTAL_AUDIT.json",
        ]
    ]
    audits = [read_json(path)["reports"] for path in audit_paths]
    rows = [row for group in audits for row in group]
    check(
        "recorded_new_decodes",
        [len(group) for group in audits] == [16, 23, 2]
        and all(
            row.get("level") != "decode_failed" and not row.get("error") for row in rows
        ),
        {
            "report_counts": [len(group) for group in audits],
            "distinct_source_ids": len({row["source_id"] for row in rows}),
            "scope": "Saved decoding records; scientific decoders are not rerun.",
        },
    )

    actual_files = {}
    mismatches = []
    for row in rows:
        for expected_file in row.get("files", []):
            path = REPO / expected_file["path"]
            if not path.is_file():
                mismatches.append({"path": expected_file["path"], "reason": "missing"})
                continue
            if path not in actual_files:
                actual_files[path] = binding(path)
            actual = actual_files[path]
            if any(actual[key] != expected_file[key] for key in ("sha256", "bytes")):
                mismatches.append(
                    {"path": expected_file["path"], "reason": "binding_mismatch"}
                )
    check(
        "new_sample_file_bindings",
        not mismatches,
        {
            "unique_files": len(actual_files),
            "bytes": sum(row["bytes"] for row in actual_files.values()),
            "mismatches": mismatches,
        },
    )

    integrity_path = DATA / "INHERITED_INTEGRITY.json"
    integrity = read_json(integrity_path)
    check(
        "inherited_integrity_record",
        integrity["all_passed"] is True
        and integrity["files"] == 857
        and integrity["bytes"] == 690671607,
        {"scope": "Previously saved integrity result; not another full rehash."},
    )
    gee_path = DATA / "gee_02/GEE_CHECK.json"
    gee = read_json(gee_path)
    check(
        "recorded_gee_success",
        gee["authenticated"] is True
        and gee["numeric_sample"] is True
        and gee["server_check"] == 1
        and gee["project"] == "disastertrace-gee",
        {
            "checked_at": gee["checked_at"],
            "scope": "Saved receipt; no network/authentication call.",
        },
    )

    pilot_path = PILOT / "dataset_v2/DATA_REPORT.json"
    pilot = read_json(pilot_path)
    check(
        "pilot_scope",
        pilot["episodes"] == 84
        and len(pilot["groups"]) == 5
        and pilot["outcome_status"].get("unresolved") == 6,
        {
            "episodes": pilot["episodes"],
            "groups": pilot["groups"],
            "outcome_status": pilot["outcome_status"],
        },
    )
    analysis_path = PILOT / "model_results_02/ANALYSIS.json"
    analysis = read_json(analysis_path)
    comparison = analysis["e1_active_raw_vs_fixed"]
    check(
        "pilot_negative_acquisition_result",
        analysis["active_acquisition_tool_counts"] == {"forecast": 160}
        and comparison["same_query_sequences"] == comparison["trajectory_pairs"] == 40
        and comparison["identical_raw_forecasts"]
        == comparison["forecast_message_pairs"]
        == 80,
        {
            "scope": "Saved descriptive pilot results, not independent-event confirmation."
        },
    )

    input_paths = (
        set(
            docs
            + audit_paths
            + [
                Path(__file__).resolve(),
                registry_path,
                integrity_path,
                gee_path,
                pilot_path,
                analysis_path,
            ]
        )
        | local_refs
    )
    user_plans = REPO / "publication/active_warning_review_20260912/user_plans"
    input_paths.update(user_plans.glob("*.md"))
    result = {
        "schema": "disastertrace.advisor_review.validation.v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "registry_generated_at": registry["generated_at"],
        "all_passed": all(row["passed"] for row in checks),
        "checks": checks,
        "inputs": [binding(path) for path in sorted(input_paths)],
        "new_sample_bindings": sorted(
            actual_files.values(), key=lambda row: row["path"]
        ),
        "limits": "Document and evidence consistency only; no new model, source acquisition, "
        "scientific decoder, complete task admission or novelty confirmation.",
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "all_passed": result["all_passed"],
                "checks": len(checks),
                "sample_files": len(actual_files),
                "bound_inputs": len(input_paths),
            }
        )
    )
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
