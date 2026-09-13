"""Bind each external review action to code, tests, real evidence and remaining gates."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
SRC = "disastertrace-starter/src/disastertrace/monitoring_v1/"
TEST = "disastertrace-starter/tests/"
BUNDLE = str(BASE.relative_to(REPO)) + "/"


def main():
    definitions = [
        (
            "V7-R01",
            "R5",
            "implemented_comparison_research_claim_pending",
            [BUNDLE + "NOVELTY_RECHECK_CN.md", BUNDLE + "run_strong_controls.py"],
            [
                TEST
                + "test_monitoring_policies.py::test_complete_batch_control_accumulates_budget_without_reading_missing_payloads"
            ],
            [BUNDLE + "strong_controls_full_01/SUMMARY.json",
             BUNDLE + "calendar_analysis_bay_02/REPORT.json",
             BUNDLE + "static_baselines_bay_03/REPORT.json"],
            "Actual bulk transport can remove scarcity in the small airport chain. Full 2024 calendars have not established positive model gain. Constant predictors are labeled post-hoc diagnostics. Independent mechanism benefit remains unproved.",
        ),
        (
            "V7-R02",
            None,
            "core_implemented_SPC_provider_gate_pending",
            [SRC + "targets.py", BUNDLE + "HAZARD_REVIEW_OVERLAY.json"],
            [
                TEST
                + "test_monitoring_support.py::test_different_full_windows_are_different_targets_even_if_end_matches",
                TEST
                + "test_monitoring_support.py::test_product_release_can_forecast_a_past_physical_period",
            ],
            [],
            "The identity and time contract is tested. SPC/USDM task-specific admission and matching remain required.",
        ),
        (
            "V7-R03",
            "R5",
            "strict_isolation_control_implemented",
            [SRC + "views.py", SRC + "policies.py"],
            [
                TEST
                + "test_monitoring_policies.py::test_private_model_result_latency_and_token_count_do_not_change_other_target_inputs",
                TEST
                + "test_monitoring_runtime.py::test_derived_assets_inherit_intersection_of_parent_entitlements",
            ],
            [BUNDLE + "gpu_x01_base_01_validation_01/VERIFIED.json"],
            "Private 2x2 uses public metadata selectors, isolated fresh target contexts and declared public timing slots. It does not identify natural latency benefit.",
        ),
        (
            "V7-R04",
            "R3",
            "core_and_real_replay_implemented",
            [
                SRC + "state.py",
                SRC + "providers/aviation.py",
                SRC + "providers/taf_timeline.py",
            ],
            [
                TEST
                + "test_monitoring_runtime.py::test_same_content_reissue_does_not_invalidate_override",
                TEST
                + "test_monitoring_runtime.py::test_baseline_expires_to_frozen_fallback_without_new_release",
                TEST
                + "test_monitoring_runtime.py::test_first_opportunity_does_not_close_target",
                TEST
                + "test_monitoring_policies.py::test_new_unparsed_taf_replaces_old_mapping_and_remains_visible_to_model",
            ],
            [BUNDLE + "extension_front_range_03/REGIONAL_JOIN_AUDIT.json"],
            "Four strict-unparsed native TAFs remain raw public inputs with frozen fallback; malformed clauses are not silently repaired. General provider freshness policies remain source-specific.",
        ),
        (
            "V7-R05",
            "R1",
            "real_E_query_F_development_implemented",
            [SRC + "support.py", SRC + "evidence.py", BUNDLE + "build_regional.py"],
            [
                TEST
                + "test_monitoring_real_chain.py::test_real_native_reports_form_E_query_F_triples",
                TEST
                + "test_monitoring_real_chain.py::test_evaluator_only_label_payload_cannot_certify_the_fact",
                TEST
                + "test_monitoring_support.py::test_missing_nonnegative_quantity_has_unbounded_upper_support",
            ],
            [
                BUNDLE + "regional_02/public/E_F_PAIRS.json",
                BUNDLE + "calibration_bank_01/CHECK_REPORT.json",
                BUNDLE + "e_diagnostic_analysis_01/REPORT.json",
            ],
            "E certification concerns visible product facts from registered neighbor slots, not continuous atmospheric truth or every latest observation. The two-model 96-case diagnostic changes multiple prompt factors and is not independent-weather F evidence. No artificial conflict is presented as a found natural case.",
        ),
        (
            "V7-R06",
            "R2",
            "budget_and_joint_reference_implemented_natural_cost_gate_open",
            [
                SRC + "resources.py",
                SRC + "reachability.py",
                BUNDLE + "run_strong_controls.py",
            ],
            [
                TEST
                + "test_monitoring_reachability.py::test_two_individual_paths_are_not_jointly_feasible",
                TEST
                + "test_monitoring_reachability.py::test_min_cost_and_min_completion_cannot_be_spliced",
                TEST
                + "test_monitoring_runtime.py::test_fixed_quotas_use_declared_initiator_pays_rule",
                TEST + "test_monitoring_reachability.py::test_witness_rejects_spliced_completion_metadata",
                TEST + "test_monitoring_reachability.py::test_witness_rejects_queries_outside_frozen_horizon",
            ],
            [
                BUNDLE + "strong_controls_full_01/t1000-budget144-JOINT.json",
                BUNDLE + "bulk_hourly_captures_01/MANIFEST.json",
                BUNDLE + "joint_reference_bay_validation_01/VERIFIED.json",
                BUNDLE + "joint_reference_front_validation_01/VERIFIED.json",
                BUNDLE + "joint_reference_replication_validation_01/VERIFIED.json",
            ],
            "All 81 saved joint references reverify unchanged with completion metadata/horizon checks. Exact source-query E witnesses are not F/model-compute-optimal schedules. First X01 varies acquisition requests/bytes only; natural scarcity and binding costs remain separate gates.",
        ),
        (
            "V7-R07",
            "R3",
            "dual_wrapper_and_v2_calendar_comparisons_implemented",
            [SRC + "state.py", BUNDLE + "verify_gpu.py", BUNDLE + "analyze_wrappers.py"],
            [
                TEST
                + "test_monitoring_runtime.py::test_stale_candidate_fixed_trace_separates_wrappers",
                TEST
                + "test_monitoring_runtime.py::test_release_at_cutoff_precedes_inflight_completion",
            ],
            [
                BUNDLE + "gpu_x01_base_01_validation_01/VERIFIED.json",
                BUNDLE + "gpu_x01_persistent_01_validation_01/VERIFIED.json",
                BUNDLE + "wrapper_analysis_bay_01/REPORT.json",
            ],
            "Early v1 prompts remain separate. Full v2 Bay protocol runs are verified; fixed-candidate wrapper changes leave all Bay cutoff scores unchanged. Separately executed differences must not be called fallback gains or additive causal effects.",
        ),
        (
            "V7-R08",
            None,
            "realized_loss_contract_implemented_confirmation_pending",
            [
                SRC + "scoring.py",
                SRC + "calibration.py",
                BUNDLE + "PLAN_AMENDMENT_CN.md",
            ],
            [
                TEST
                + "test_monitoring_runtime.py::test_common_mask_missingness_bounds_do_not_assert_population_gain"
            ],
            [BUNDLE + "calibration_bank_01/CHECK_REPORT.json"],
            "Net Brier and G+/G- describe realized outcomes. No per-update expected-risk, non-inferiority or post-acquisition calibration guarantee is claimed.",
        ),
        (
            "V7-R09",
            None,
            "missingness_strata_and_bounds_implemented",
            [SRC + "scoring.py", BUNDLE + "analyze_calendar.py"],
            [
                TEST
                + "test_monitoring_runtime.py::test_common_mask_missingness_bounds_do_not_assert_population_gain",
                BUNDLE + "test_calendar_analysis.py::test_missing_bounds_keep_the_shared_outcome_across_repeated_leads",
            ],
            [BUNDLE + "extension_front_range_03/REGIONAL_JOIN_AUDIT.json",
             BUNDLE + "replication_2026_01/REGIONAL_JOIN_AUDIT.json",
             BUNDLE + "report_event_profile_02/REPORT.json"],
            "All methods retain six unresolved Front 2024 and 36 unresolved Front 2026 opportunities per threshold. Paired missingness bounds share one outcome across a target's repeated leads. Calendar blocks are not independent storms; common masks do not establish unbiased sampling.",
        ),
        (
            "V7-R10",
            "R4",
            "one_regional_MM_chain_verified_second_process_pending",
            [
                BUNDLE + "build_images.py",
                BUNDLE + "mm_inputs.py",
                BUNDLE + "mm_worker.py",
            ],
            [],
            [
                BUNDLE + "images_03/REGIONAL_IMAGE_JOIN.json",
                BUNDLE + "gpu_mm_01_validation_01/VERIFIED.json",
            ],
            "Four real GOES18 thermal inputs and actual VLM tensor/token replay are verified. Same-source lossy panels and numeric summaries are not equal-information or surface-fog truth; two physical processes are not yet delivered.",
        ),
        (
            "V7-R11",
            "R5",
            "16_hazard_overlay_complete_full_release_pending",
            [
                BUNDLE + "HAZARD_REVIEW_OVERLAY_CN.md",
                BUNDLE + "HAZARD_REVIEW_OVERLAY.json",
            ],
            [],
            [],
            "Preserves existing A0-A5/E/F/D/MM registry and all16 hazard objectives. The current result is an engineering/development release, not a fully admitted16-hazard or independent novelty confirmation.",
        ),
    ]
    records = []
    for issue, action, status, code, tests, evidence, remaining in definitions:
        additional = {
            "V7-R01": ["calendar_analysis_front_02/REPORT.json", "calendar_analysis_replication_01/REPORT.json",
                       "static_baselines_front_02/REPORT.json", "static_baselines_replication_01/REPORT.json",
                       "ranking_analysis_bay_01/REPORT.json", "ranking_analysis_front_01/REPORT.json",
                       "ranking_analysis_replication_01/REPORT.json"],
            "V7-R05": ["e_order_analysis_01/REPORT.json", "E_CASE_WALKTHROUGH_BINDINGS.json"],
            "V7-R06": [str(p.relative_to(BASE)) for pattern in ("resource_analysis_*/REPORT.json", "joint_E_analysis_*/REPORT.json")
                       for p in sorted(BASE.glob(pattern))],
            "V7-R07": ["wrapper_analysis_front_01/REPORT.json", "wrapper_analysis_replication_01/REPORT.json",
                       "WRAPPER_CASE_WALKTHROUGH.json"],
            "V7-R09": ["hydro_revision_validation_01/REPORT.json", "live_observer_validation_01/VERIFIED.json",
                       "hydro_metadata_validation_01/REPORT.json", "hydro_stage_validation_01/REPORT.json"],
        }.get(issue, [])
        evidence = list(evidence) + [BUNDLE + path for path in additional if (BASE / path).is_file()]
        paths = sorted(set(code + [p.split("::")[0] for p in tests] + evidence))
        bindings = {}
        for name in paths:
            path = REPO / name
            if not path.is_file():
                raise ValueError("Review evidence is missing: " + name)
            bindings[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append(
            {
                "issue": issue,
                "supplementary_action": action,
                "status": status,
                "implementation": code,
                "regression_nodes": tests,
                "real_evidence": evidence,
                "remaining_gate": remaining,
                "bindings": bindings,
            }
        )
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_commit": "63c77694797c2436ef79465d9c076fb940404f06",
        "path_root": "repository",
        "issues": records,
        "supplementary_action_coverage": {
            key: [r["issue"] for r in records if r["supplementary_action"] == key]
            for key in ("R1", "R2", "R3", "R4", "R5")
        },
        "test_execution_record": BUNDLE + "review_replay_01/CORE_AND_ANALYSIS_VALIDATION_09.xml",
        "packaged_reproduction_record": BUNDLE + "packaged_replay_02_receipts/COMPLETE.json",
        "additional_packaged_replication_record": BUNDLE + "packaged_replay_replication_01_receipts/COMPLETE.json",
        "additional_checks_are_separate_from_core_tests": [
            BUNDLE + "review_replay_01/RANKING_VALIDATION_01.xml",
            BUNDLE + "review_replay_01/E_ORDER_ANALYSIS_VALIDATION_01.xml",
            "publication/v7_review_execution_20260912/SCREEN_AFTER_02.xml",
            "publication/v7_review_execution_20260912/PUBLISHER_INTEGRATION_01.xml",
        ],
        "interpretation": "Implementation and observed development evidence are distinguished from incomplete scientific acceptance; original reviewer statuses remain unchanged.",
    }
    (BASE / "REVIEW_RESOLUTION.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = [
        "# v7 review resolution map",
        "",
        "The original review packages remain unchanged. This map binds implementation, regression nodes and observed development evidence. Scientific gates stay explicit.",
        "",
        "| Issue | Supplement | Status | Remaining gate |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {r['issue']} | {r['supplementary_action'] or '-'} | {r['status']} | {r['remaining_gate']} |"
        for r in records
    ]
    lines += [
        "",
        "Exact repository paths and SHA256 bindings are in `REVIEW_RESOLUTION.json`. A listed regression node is an implementation check, not an independent meteorological confirmation.",
        "",
    ]
    (BASE / "REVIEW_RESOLUTION.md").write_text("\n".join(lines))
    print(
        json.dumps(
            {
                "issues": len(records),
                "supplementary_actions": len(result["supplementary_action_coverage"]),
            }
        )
    )


if __name__ == "__main__":
    main()
