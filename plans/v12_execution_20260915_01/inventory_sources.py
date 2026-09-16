"""Verify existing native bytes and catalog scope without acquiring new sources."""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import typed_target
from disastertrace.monitoring_fixed_v1.taf_tasks import TafEvidenceTask, evaluate
from disastertrace.monitoring_v1.providers.aviation import parse_taf
from disastertrace.monitoring_v1.providers.versions import taf_semantics
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash
from dataclasses import asdict


RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OLD = REPO / "plans/v11_execution_20260915_01"
VERIFIED = {}


def verify_source(binding, base):
    body, receipt_path = (base / binding[name] for name in ("path", "receipt_path"))
    key = (str(body), binding["sha256"], str(receipt_path), binding["receipt_sha256"])
    if key not in VERIFIED:
        receipt = read(receipt_path)
        if (digest(body) != binding["sha256"] or digest(receipt_path) != binding["receipt_sha256"]
                or receipt.get("sha256") != binding["sha256"]
                or body.stat().st_size != binding["bytes"] or receipt.get("bytes") != binding["bytes"]
                or receipt.get("http_status") != 200 or not receipt.get("complete")
                or receipt.get("curl_exit") != 0):
            raise ValueError("Source body/receipt is incomplete or mismatched")
        VERIFIED[key] = (body, receipt_path, receipt)
    return VERIFIED[key]


def exposed_units():
    units = read(REPO / "plans/v10_execution_20260914_01/seasonal_completion_02/COMPLETE.json")["units"]
    result = [{**u, "role": "exposed_2025_development"} for u in units]
    monthly = read(OLD / "annual_native_sample_01/RESULT.json")["results"]
    result += [{**u, "source_root": str(Path(u["dataset"]).parent),
                "role": "2024_source_QA_only_in_this_task"} for u in monthly]
    return result


def census():
    public, evaluator, reports, raw_by_unit = [], [], [], {}
    for unit in exposed_units():
        dataset, base = Path(unit["dataset"]), Path(unit["source_root"])
        sources = read(dataset / "SOURCES.json")
        index = read(dataset / "environment/NATIVE_PRODUCT_INDEX.json")
        resolution = read(dataset / "environment/NATIVE_RESOLUTION.json")
        expected = base / "SOURCE_NATIVE_PLAN.json"
        requests = read(expected)["requests"] if expected.is_file() else None
        missing = None if requests is None else sorted({r["id"] for r in requests} - set(sources))
        native_ids = {r["source_id"] for r in index}
        if native_ids != {sid for sid in sources if sid.startswith("taf-")}:
            raise ValueError("Native index and source roster differ: " + unit["unit"])
        parsed_counts, failures, raw = Counter(), [], []
        for sid, binding in sources.items():
            body, receipt_path, receipt = verify_source(binding, base)
            if not sid.startswith("taf-"):
                continue
            meta = receipt["catalog_metadata"]
            index_row = next(r for r in index if r["source_id"] == sid)
            issue = meta["issued_at"].replace(" ", "T") + ":00Z"
            text = body.read_text()
            state = index_row["status"]
            try:
                product = parse_taf(text, station=meta["station"], archive_issue=issue)
                if taf_semantics(product) != index_row["native_semantics_sha256"]:
                    raise RuntimeError("Native product semantics changed")
                parsed_counts["parsed"] += 1
            except ValueError as exc:
                if state != "unparsed":
                    raise RuntimeError("Previously parsed native source no longer parses") from exc
                parsed_counts["unsupported"] += 1
                failures.append({"source_id": sid, "reason": str(exc)})
            visible = {"unit": unit["unit"], "source_id": sid, "station": index_row["station"],
                       "issued_at": index_row["issued_at"], "available_at": index_row["issued_at"] + 120_000_000,
                       "availability_basis": "declared_archive_scenario", "raw_source_is_common_TAF": True}
            public.append(visible)
            evaluator.append({**visible, "index_state": state, "raw_sha256": binding["sha256"],
                              "receipt_sha256": binding["receipt_sha256"], "body_path": str(body),
                              "receipt_path": str(receipt_path), "provider_request_url": receipt["url"],
                              "historical_first_seen_verified": False})
            raw.append({"source_id": sid, "station": index_row["station"], "raw": text,
                        "issued_at": index_row["issued_at"], "available_at": index_row["issued_at"] + 120_000_000,
                        "completed_at": index_row["issued_at"] + 120_000_000})
        raw_by_unit[unit["unit"]] = raw
        reports.append({"unit": unit["unit"], "role": unit["role"], "source_count": len(sources),
                        "product_count": len(index), "native_states": dict(Counter(r["status"] for r in index)),
                        "target_window_states": dict(Counter(r["status"] for r in resolution)),
                        "target_windows": len(resolution), "parsing": dict(parsed_counts), "failures": failures,
                        "request_plan_present": requests is not None, "missing_registered_sources": missing,
                        "scope": "registered_request_set" if requests is not None and not missing else "bound_dataset_only",
                        "source_manifest_sha256": digest(dataset / "SOURCES.json"),
                        "native_index_sha256": digest(dataset / "environment/NATIVE_PRODUCT_INDEX.json")})
    tasks, references = [], []
    for row in read(OLD / "c2_design_01/ROSTER.json"):
        data = read(OLD / "fullweek_02" / row["case"] / "DATA.json")
        target = next(t for t in data["targets"] if t["target_id"] == row["target_id"])
        unit = row["region"] + "__" + row["week"]
        for kind in ("coverage", "revision"):
            task = TafEvidenceTask.freeze({"schema": "disastertrace.taf_E_task.v1",
                "task_id": row["opportunity_id"] + "__v12_full_index__" + kind, "kind": kind,
                "target": asdict(typed_target(target)), "as_of": row["cutoff"],
                "availability_basis": "declared_archive_scenario",
                "products": [p for p in raw_by_unit[unit] if p["station"] == target["entity"]
                             and p["available_at"] <= row["cutoff"]]})
            tasks.append({"task": task.view(), "task_hash": task.task_hash})
            references.append(evaluate(task))
    publish(RUN / "PUBLIC_CATALOG.json", {"rows": public, "hidden_states_excluded": True})
    publish(RUN / "EVALUATOR_CATALOG.json", {"rows": evaluator, "policy_visible": False})
    publish(RUN / "SOURCE_UNIVERSE_CONTRACT.json", {
        "passed": True, "units": reports, "provider_history_complete": False,
        "availability": "120s declared scenario; not empirical historical first_seen",
        "public_fields": list(public[0]), "missing_scope_is_not_no_product": True,
        "independent_process_count": None, "source_HTTP_calls": 0})
    publish(RUN / "C2_STATE_CENSUS.json", {
        "passed": True, "units": reports, "new_taf_tasks": len(tasks),
        "native_taf_reference_statuses": dict(Counter(r["answer"]["status"] for r in references)),
        "coverage": dict(Counter(r["answer"].get("coverage") for r in references if "coverage" in r["answer"])),
        "task_scope": "closed registered archive packet; full index before version/coverage filtering",
        "taf_intervention_status": "wiring_audited_not_intervened", "new_model_calls": 0})
    publish(RUN / "C2_TAF_TASKS.json", tasks)
    publish(RUN / "C2_TAF_REFERENCES_EVALUATOR_ONLY.json", references)
    publish(RUN / "C2_CONSUMER_WIRING.json", {
        "taf": {"status": "wiring_audited_not_intervened", "consumer": "NativeFeaturePredictor.predict -> feature_vector -> parse_taf/project",
                "raw_projection_validation_retained": True, "E_boolean_consumed_by_F": False},
        "metar": {"consumer": "authorized receipt -> native_claims -> slot bound/mask/age features -> predict_features",
                  "max_slots_per_target": 2, "endpoint_closure_in_F_features": False,
                  "closure_affects_E_support": True, "actual_collision_census": "pending_branch_fields"},
        "source_code_hashes": {str(p.relative_to(REPO)): digest(p) for p in [
            REPO / "disastertrace-starter/src/disastertrace/monitoring_fixed_v1/native_feature.py",
            REPO / "disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py"]},
        "metar_states": ["supported", "refuted", "undetermined", "inconsistent"],
        "taf_states": ["resolved", "unknown", "unsupported", "conflict"],
        "future_labels_read": False})
    print({"passed": True, "units": len(reports), "source_rows": len(public), "taf_tasks": len(tasks)}, flush=True)


def inventory():
    annual = read(OLD / "annual_catalog_01/RESULT.json")
    objects, failed = {}, []
    for unit in annual["results"]:
        if not unit["complete"]:
            failed.append(unit)
            continue
        path = OLD / "annual_catalog_01" / unit["unit"] / "SOURCE_NATIVE_PLAN.json"
        plan_sha = digest(path)
        for request in read(path)["requests"]:
            key = canonical_hash({"id": request["id"], "url": request["url"]})
            entry = objects.setdefault(key, {"request_key": key, "id": request["id"], "url": request["url"],
                                            "request": request, "references": [], "verified_variants": {}})
            entry["references"].append({"unit": unit["unit"], "catalog_metadata": request["catalog_metadata"],
                                        "plan_sha256": plan_sha})
    if shutil.which("rg"):
        listing = subprocess.check_output(["rg", "--files", "plans", "-g", "SOURCES.json",
            "-g", "!**/before/**", "-g", "!**/review_inputs/**", "-g", "!**/evidence/**"], cwd=REPO, text=True, timeout=120)
    else:
        found = []
        for folder, directories, files in os.walk(REPO / "plans"):
            directories[:] = [d for d in directories if d not in {"before", "review_inputs", "evidence"}]
            if "SOURCES.json" in files:
                found.append(str((Path(folder) / "SOURCES.json").relative_to(REPO)))
        listing = "\n".join(found)
    scanned, failures = [], []
    for name in sorted(set(listing.splitlines())):
        path = REPO / name
        sources = read(path)
        if not isinstance(sources, dict):
            continue
        matching = 0
        for sid, binding in sources.items():
            if not sid.startswith("taf-") or not isinstance(binding, dict) or "receipt_sha256" not in binding:
                continue
            try:
                body, receipt_path, receipt = verify_source(binding, path.parent)
            except (OSError, ValueError, KeyError) as exc:
                failures.append({"manifest": name, "source_id": sid, "error": type(exc).__name__})
                continue
            key = canonical_hash({"id": sid, "url": receipt["url"]})
            if key not in objects:
                continue
            matching += 1
            objects[key]["verified_variants"].setdefault(binding["sha256"], {
                "body_path": str(body), "receipt_path": str(receipt_path),
                "receipt_sha256": binding["receipt_sha256"], "bytes": binding["bytes"],
                "catalog_metadata": receipt.get("catalog_metadata"), "sha256": binding["sha256"]})
        scanned.append({"manifest": name, "manifest_sha256": digest(path), "matching_references": matching})
    rows = []
    for entry in objects.values():
        variants = list(entry["verified_variants"].values())
        rows.append({**entry, "verified_variants": variants,
                     "state": "missing_bytes" if not variants else "verified_cached" if len(variants) == 1 else "same_id_content_conflict"})
    rows.sort(key=lambda row: row["request_key"])
    counts = Counter(row["state"] for row in rows)
    publish(RUN / "ANNUAL_NATIVE_OBJECTS.json", rows)
    publish(RUN / "ANNUAL_NATIVE_INVENTORY.json", {
        "passed": True, "successful_region_months": 71, "failed_region_months": failed,
        "logical_references": sum(len(row["references"]) for row in rows),
        "unique_id_url_request_keys": len(rows), "states": dict(counts), "cache_scan": scanned,
        "cache_binding_failures": failures, "unknown_contents_not_deduplicated": True,
        "scope": "all matching native TAF SOURCES manifests discoverable under plans except prior review/evidence copies",
        "new_source_HTTP_calls": 0, "objects_sha256": digest(RUN / "ANNUAL_NATIVE_OBJECTS.json")})
    publish(RUN / "EXPOSURE_LEDGER.json", {
        "schema": "disastertrace.exposure_ledger.v1", "entries": [
            {"calendar": "2023", "proposed_role": "fit_and_internal_selection", "catalog_QA": True,
             "labels_viewed": "historical_exposure_unknown_outside_declared_manifests", "method_selection": "audit_before_fit"},
            {"calendar": "2024-02", "proposed_role": "final_calibration_after_role_qualification", "source_QA": True,
             "labels_viewed": "native_dataset_builder_processed_labels", "losses_viewed_by_this_inventory": False,
             "losses_used_for_method_choice_by_this_inventory": False},
            {"calendar": "2024-12", "proposed_role": "historically_exposed_calibration", "source_QA": True,
             "labels_viewed": True, "losses_viewed": True, "method_selection": "old_no_year_feature_bank_development"},
            {"calendar": "other_2024", "proposed_role": "candidate_final_calibration", "source_QA": "catalog_only_in_v11",
             "labels_viewed": "audit_historical_manifests_before_claiming_unseen"},
            {"calendar": "2025_exposed_four_weeks", "role": "development", "labels_viewed": True,
             "losses_viewed": True, "may_be_reclassified_confirmation": False},
            {"calendar": "Bay2025-02-17..23", "role": "unopened_confirmation_candidate", "opened_in_this_batch": False}],
        "purge_dependencies": ["dynamic native versions", "observation lookback", "target/result windows", "derived assets", "session memory"],
        "static_station_metadata_and_schema_do_not_merge_years": True})
    publish(RUN / "NEXT_ACQUISITION_SPEC.json", {
        "status": "inventory_ready_requires_frozen_download_registration",
        "objects_sha256": digest(RUN / "ANNUAL_NATIVE_OBJECTS.json"),
        "missing_request_keys": [r["request_key"] for r in rows if r["state"] == "missing_bytes"],
        "conflicting_request_keys": [r["request_key"] for r in rows if r["state"] == "same_id_content_conflict"],
        "known_remaining_raw_bytes": None, "no_unknown_content_deduplication": True,
        "catalog_recovery": "KORD2023-01 exact failed request; preserve five successful companion slices",
        "new_source_requests_sent": 0})
    print({"passed": True, "request_keys": len(rows), "states": dict(counts), "scanned_manifests": len(scanned)}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=["census", "inventory"])
    args = parser.parse_args()
    (census if args.task == "census" else inventory)()
