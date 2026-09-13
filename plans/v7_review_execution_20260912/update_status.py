"""Refresh mutable execution status from actual receipts, without changing freezes."""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    status = json.loads((ROOT / "EXECUTION_STATUS.json").read_text())
    verified = {}
    for file in sorted(ROOT.glob("gpu*_validation_*/VERIFIED.json")):
        record = json.loads(file.read_text())
        if "actual_calls" not in record or "plan_sha256" not in record:
            continue
        key = record["plan_sha256"]
        if key not in verified or record["verified_at"] > verified[key]["verified_at"]:
            verified[key] = {
                "verified_at": record["verified_at"],
                "path": str(file.relative_to(ROOT)),
                "calls": record["actual_calls"],
                "tokens": record["actual_tokens"],
                "execution_kind": record.get(
                    "execution_kind", "forecast_state_model_experiment"
                ),
                "verified_workers": record["verified_workers"],
            }
    tests = []
    for file in sorted((ROOT / "review_replay_01").glob("CORE*VALIDATION_*.xml")):
        suite = ET.parse(file).getroot().find("testsuite")
        tests.append({"path": str(file.relative_to(ROOT)), **suite.attrib})
    tests.sort(key=lambda row: row["timestamp"])
    supplemental_tests = []
    for path in (
        ROOT / "review_replay_01/RANKING_VALIDATION_01.xml",
        ROOT / "review_replay_01/E_ORDER_ANALYSIS_VALIDATION_01.xml",
        ROOT.parents[1] / "publication/v7_review_execution_20260912/SCREEN_AFTER_02.xml",
        ROOT.parents[1] / "publication/v7_review_execution_20260912/PUBLISHER_INTEGRATION_01.xml",
    ):
        if path.exists():
            suite = ET.parse(path).getroot().find("testsuite")
            supplemental_tests.append({"path": str(path), **suite.attrib})
    calendar_complete = (ROOT / "delivery_queue_01/COMPLETE.json").exists()
    e_order_terminal = any((ROOT / "e_order_queue_01" / name).exists()
                           for name in ("COMPLETE.json", "STOPPED.json"))
    status.update(
        updated_at=datetime.now(timezone.utc).isoformat(),
        stage=("W6_analysis_reproduction_and_delivery" if calendar_complete and e_order_terminal
               else "W4_models_and_W5_extended_calendar_in_progress"),
        current_release="core_and_real_regional_development_model_validation",
        model_calls=sum(v["calls"] for v in verified.values()),
        verified_model_tokens=sum(v["tokens"] for v in verified.values()),
        verified_batches=list(verified.values()),
        verified_gpu_jobs=sum(v["verified_workers"] for v in verified.values()),
        gpu_jobs=len(list(ROOT.glob("gpu*/submissions/*/job-id.txt"))),
        received_reply_files=len(list(ROOT.glob("gpu*/worker-*/*/*-response.json"))),
        tests=tests,
        supplemental_tests=supplemental_tests,
        remaining_scientific_gates=[
            "positive-event independent blocks",
            "LLM selector versus strong equal-resource controls",
            "post-acquisition calibration",
            "native MM across distinct processes",
            "first-seen provenance",
            "formal16-hazard admission",
        ],
        literature_recheck="NOVELTY_RECHECK_CN.md",
        hazard_contract_overlay="HAZARD_REVIEW_OVERLAY_CN.md",
    )
    status["completed"] = [
        "review_package_hash_verification_11_members",
        "review_examples_replayed_8_and_6_separate_from_core_tests",
        "governing_v7_contract_amendment_and_16_hazard_overlay",
        "joint_support_state_resources_and_entitlement_core",
        "native_TAF_METAR_72h_regional_chain",
        "separate_December_calibration_fit_and_check",
        "26_short_and_26_full_program_controls",
        "48_stronger_program_controls_and_full_session_joint_E_witnesses",
        "real_GOES18_C07_C13_and_actual_VLM_tensor_replay",
        "five_literature_fulltext_comparisons",
        "11_review_issues_and_5_supplementary_actions_mapped",
        "real_three_station_hourly_bulk_transport_verified",
    ]
    evidence_checks = {
        "native_METAR_independent_decoder_2024": "independent_metar_validation_02/VERIFIED.json",
        "native_METAR_independent_decoder_2025_2026": "independent_metar_validation_03/VERIFIED.json",
        "native_TAF_independent_comparison_with_retained_disagreements": "independent_taf_validation_02/REPORT.json",
        "prior_December_2025_calibration_and_check": "calibration_bank_2025_01/CHECK_REPORT.json",
        "fixed_2026_calendar_data_admission": "REPLICATION_2026_ADMISSION.json",
        "balanced_E_diagnostic_8B": "gpu_e_diagnostic_01_validation_01/VERIFIED.json",
        "balanced_E_diagnostic_32B": "gpu_e_diagnostic_32b_01_validation_01/VERIFIED.json",
        "cheap_controls_Bay_2024": "calendar_controls_bay_secondary_01/SUMMARY.json",
        "cheap_controls_Front_2024": "calendar_controls_front_primary_01/SUMMARY.json",
        "cheap_controls_Front_2026": "calendar_controls_replication_primary_01/SUMMARY.json",
        "joint_reference_81_revalidation_Bay": "joint_reference_bay_validation_01/VERIFIED.json",
        "joint_reference_81_revalidation_Front": "joint_reference_front_validation_01/VERIFIED.json",
        "joint_reference_81_revalidation_replication": "joint_reference_replication_validation_01/VERIFIED.json",
        "packaged_evidence_replay_01": "packaged_replay_01_receipts/COMPLETE.json",
        "portable_packaged_evidence_replay_02": "packaged_replay_02_receipts/COMPLETE.json",
        "packaged_2026_model_replication_replay": "packaged_replay_replication_01_receipts/COMPLETE.json",
        "dual_wrapper_Bay_all_opportunity_comparison": "wrapper_analysis_bay_01/REPORT.json",
        "dual_wrapper_Front_all_opportunity_comparison": "wrapper_analysis_front_01/REPORT.json",
        "dual_wrapper_replication_all_opportunity_comparison": "wrapper_analysis_replication_01/REPORT.json",
        "balanced_E_two_model_analysis": "e_diagnostic_analysis_01/REPORT.json",
        "native_weather_code_and_coverage_profile": "report_event_profile_02/REPORT.json",
        "bounded_live_version_observer": "live_observer_validation_01/VERIFIED.json",
        "fixed_candidate_wrapper_case_walkthrough": "WRAPPER_CASE_WALKTHROUGH.json",
        "native_E_case_walkthrough": "E_CASE_WALKTHROUGH_BINDINGS.json",
        "warning_ranking_Bay": "ranking_analysis_bay_01/REPORT.json",
        "warning_ranking_Front": "ranking_analysis_front_01/REPORT.json",
        "warning_ranking_replication": "ranking_analysis_replication_01/REPORT.json",
        "unchanged_message_E_execution_order_analysis": "e_order_analysis_01/REPORT.json",
        "H08_provisional_source_revision_preflight": "hydro_revision_validation_01/REPORT.json",
        "H08_official_mapping_and_threshold_metadata": "hydro_metadata_validation_01/REPORT.json",
        "H08_native_stage_forecast_and_service_pairing": "hydro_stage_validation_01/REPORT.json",
        "full_portfolio_E_joint_reference_Bay": "joint_E_analysis_bay_01/REPORT.json",
        "full_portfolio_E_joint_reference_Front": "joint_E_analysis_front_01/REPORT.json",
        "full_portfolio_E_joint_reference_replication": "joint_E_analysis_replication_01/REPORT.json",
    }
    for label, path in evidence_checks.items():
        if (ROOT / path).exists():
            status["completed"].append(label)
            status["evidence"][label] = path
    resource_reports = sorted(ROOT.glob("resource_analysis_*/REPORT.json"))
    if resource_reports:
        status["evidence"]["actual_resource_use_and_calendar_E"] = str(resource_reports[-1].relative_to(ROOT))
        status["completed"].append("actual_resource_use_and_calendar_E")
    replays = []
    for path in sorted(ROOT.glob("offline_*_replay_*/validation/REPLAY_REPORT.json")):
        record = json.loads(path.read_text())
        process = path.parent.parent / "PROCESS.json"
        if not process.exists() or json.loads(process.read_text())["returncode"] != 0:
            continue
        replays.append(
            {
                "path": str(path.relative_to(ROOT)),
                "replayed_calls": record["replayed_model_calls"],
                "replayed_tokens": record["replayed_tokens"],
                "new_model_calls": record["new_model_calls"],
                "weights_loaded": record["weights_loaded"],
            }
        )
    status["offline_replays"] = replays
    publication_receipt = ROOT.parents[1] / "publication/v7_review_execution_20260912/PUBLISH_RESULT.json"
    status["pending"] = []
    if publication_receipt.is_file() and json.loads(publication_receipt.read_text()).get("remote_verified"):
        status["completed"].append("selected_GitHub_delivery_remote_confirmed")
        status["evidence"]["GitHub_delivery_receipt"] = str(publication_receipt)
    else:
        status["pending"].append("final_selected_GitHub_push_receipt_generated_after_snapshot")
    for batch in ("gpu_front_primary_persistent_01", "gpu_replication_primary_base_01",
                  "gpu_replication_primary_persistent_01"):
        if not (ROOT / (batch + "_validation_01") / "VERIFIED.json").exists():
            status["pending"].append("independent_verification:" + batch)
    if not e_order_terminal:
        status["pending"].append("bounded_E_execution_order_queue")
    elif (ROOT / "e_order_queue_01/COMPLETE.json").exists() and not (ROOT / "e_order_analysis_01/REPORT.json").exists():
        status["pending"].append("bounded_E_execution_order_analysis")
    status["evidence"].update(
        tests=tests[-1]["path"] if tests else None,
        full_programs="programs_full_01/SUMMARY.json",
        strong_controls="strong_controls_full_01/SUMMARY.json",
        multimodal="gpu_mm_01_validation_01/VERIFIED.json",
        charged_selector="gpu_active_pilot_01_validation_02/VERIFIED.json",
        queued_dual_protocol_runs="gpu_queue_01/STATUS.json",
        prospective_receipts="live_version_observer_01/STATUS.json",
        CPU_delivery_queue="delivery_queue_01/STATUS.json",
        bounded_E_order_queue="e_order_queue_01/STATUS.json",
    )
    status["regional_cohorts"] = []
    for name in (
        "regional_02",
        "calibration_03",
        "extension_bay_area_01",
        "extension_front_range_03",
        "calibration_2025_02",
        "replication_2026_01",
    ):
        file = ROOT / name / "REGIONAL_JOIN_AUDIT.json"
        if file.exists():
            record = json.loads(file.read_text())
            status["regional_cohorts"].append(
                {
                    "path": str(file.relative_to(ROOT)),
                    "metar_rows": record["metar_rows"],
                    "native_taf_bulletins_decoded": record[
                        "native_taf_bulletins_decoded"
                    ],
                    "by_threshold": record["by_threshold"],
                    "decoder_failures": len(record["failures"]),
                }
            )
    (ROOT / "EXECUTION_STATUS.json").write_text(json.dumps(status, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: status[k]
                for k in (
                    "updated_at",
                    "model_calls",
                    "gpu_jobs",
                    "received_reply_files",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
