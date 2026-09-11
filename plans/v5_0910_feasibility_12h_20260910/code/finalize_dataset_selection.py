"""Pin selected products, their roles, source evidence and release limitations."""

from datetime import datetime, timezone
import json

from common import ROOT, capture, dump
from model_adapter import sha_file


def bind(path):
    item = ROOT / path
    return {"path": path, "bytes": item.stat().st_size, "sha256": sha_file(item)}


def license_capture(key):
    _, source = capture(key)
    return source


def main():
    load = lambda name: json.loads((ROOT / name).read_text())
    nhc = load("data/NHC_PRODUCTS.json")
    ghcnd = load("data/GHCND_RECORDS.json")
    climatology = load("analysis/CLIMATOLOGY_FEASIBILITY_02.json")
    usdm = load("analysis/USDM_FEASIBILITY.json")
    sevir = load("analysis/SEVIR_FEASIBILITY_02.json")
    native = load("analysis/NATURAL_COVERAGE_FEASIBILITY.json")
    nhc_terms = license_capture("nws-disclaimer")
    products = [
        {
            "id": "nhc_forecast_advisory", "selection": "core_v1",
            "provider": "NOAA/NWS National Hurricane Center",
            "product": "Atlantic forecast/advisory archive",
            "release": "Source archive snapshots captured2026-09-10; exact bodies in source manifest",
            "roles": ["public_source_text", "same_valid_target_revision", "active_evidence"],
            "reference_kind": "published_forecast_product_fact",
            "validated_subset": {"storm_ids": sorted({p["storm_id"] for p in nhc}),
                "advisories": len(nhc), "advisories_per_storm": 16,
                "forecast_rows": sum(len(p["forecasts"]) for p in nhc), "same_target_chains": 98},
            "sources": [p["source"] for p in nhc],
            "artifacts": [bind(p) for p in ["data/NHC_PRODUCTS.json", "data/NHC_REVISION_CHAINS.json",
                          "analysis/NHC_FEASIBILITY.json", "analysis/STATE_REFERENCE_PREFLIGHT.json"]],
            "rights": {"status": "reuse_with_source_attribution_and_noted_exceptions", "evidence": [nhc_terms],
                "conditions": "NWS public-domain information except marked third-party content; no implied endorsement; identify derived renderings as derived."},
            "time_profile": "controlled_archive_replay; issue_time does not prove historical availability",
            "split_unit": "physical_storm; group all advisory versions/targets/cross-hazard derivatives",
            "limitations": ["Francine is an inherited development event, not globally new.",
                            "Center maximum wind is not point/local wind, rainfall or impact."]
        },
        {
            "id": "hurdat2_atlantic", "selection": "core_v1_outcome_only",
            "provider": "NOAA/NWS National Hurricane Center", "product": "Atlantic HURDAT2 best track",
            "release": "hurdat2-1851-2025-02272026.txt",
            "roles": ["private_retrospective_resolution", "agency_forecast_and_persistence_baselines"],
            "reference_kind": "retrospective_same_agency_best_track_analysis",
            "validated_subset": {"exact_storm_time_joins": 422, "unmatched_forecast_rows_retained": 39},
            "sources": [load("data/NHC_OUTCOME_JOINS_PRIVATE.json")["source"]],
            "artifacts": [bind("data/NHC_OUTCOME_JOINS_PRIVATE.json")],
            "rights": {"status": "reuse_with_source_attribution_and_noted_exceptions", "evidence": [nhc_terms]},
            "public_input_allowed": False,
            "limitations": ["Not independent raw physical truth; frozen version matters.",
                            "Joining historical outcomes does not establish prospective LLM forecast skill."]
        },
        {
            "id": "ghcnd_v3_daily_summaries", "selection": "core_v1",
            "provider": "NOAA NCEI", "product": "GHCN-Daily Version3 / daily-summaries service",
            "release": "Version3, DOI10.7289/V5D21VHZ; exact service snapshots2026-09-10",
            "roles": ["public_station_product", "quality_and_support", "relative_extreme_indicator", "active_evidence"],
            "reference_kind": "quality-filtered_archived_station_product_and_declared_derived_indicator",
            "validated_subset": {"stations": [s["station"] for s in climatology["stations"]],
                "development_interval": ["2021-06-01", "2021-08-31"], "development_station_days": 368,
                "development_scalar_records": 1104, "baseline_interval": ["1991-01-01", "2020-12-31"],
                "baseline_station_days": sum(s["baseline_rows"] for s in climatology["stations"]),
                "variables": ["TMAX", "TMIN", "PRCP"],
                "hot_spells_ge3_station_days": sum(len(s["hot_spells_ge3_days"]) for s in climatology["stations"])},
            "sources": ghcnd["sources"],
            "artifacts": [bind(p) for p in ["data/GHCND_RECORDS.json", "analysis/GHCND_FEASIBILITY.json",
                                            "analysis/CLIMATOLOGY_FEASIBILITY_02.json"]],
            "rights": {"status": "official_dataset_use_and_citation_terms_captured",
                "evidence": [license_capture("ghcnd-ncei-iso-xml")],
                "citation": "Menne et al.(2012), GHCN-Daily Version3, DOI10.7289/V5D21VHZ; specify subset/access date and cite dataset paper.",
                "distribution": "Source-specific terms retained; do not relabel source data under the code license."},
            "time_profile": "retrospective_station_observation_day; not uniform_UTC_day",
            "split_unit": "station_region_season_and_shared_synoptic_event",
            "limitations": ["Four US stations do not establish global coverage.",
                "Research Q90/Q95 definitions are not asserted official ETCCDI/WMO disaster labels.",
                "Pilot35C questions remain frozen; climatology is a separate feasibility result."]
        },
        {
            "id": "usdm_weekly", "selection": "core_v1",
            "provider": "NDMC/UNL, USDA, NOAA and NASA", "product": "U.S. Drought Monitor weekly vector maps",
            "release": "Map dates20240827,20240903,20240910,20240917; exact ZIP hashes bound",
            "roles": ["public_product_category", "weekly_state_evolution", "active_evidence"],
            "reference_kind": "published_expert_product_fact; no_new_itemwise_human_annotation",
            "validated_subset": {"weeks": 4, "CONUS_fixed_points": 8, "point_weeks": 32},
            "sources": [row["source"] for row in usdm["checks"]],
            "artifacts": [bind(p) for p in ["data/USDM_POINTS.json", "analysis/USDM_FEASIBILITY.json",
                                            "analysis/USDM_POINT_REFERENCE_RECHECK.json"]],
            "rights": {"status": "official_map_reproduction_attribution_captured",
                "evidence": [license_capture("usdm-permission")],
                "distribution": "Attribute all named producers; permission page covers map reproduction, not a blanket license for every related product. Prefer official fetcher and hashes for original ZIPs."},
            "time_profile": "different_valid_weeks; not same_target_revisions",
            "split_unit": "region_season_blocks; shared_map_products_are_correlated",
            "limitations": ["Outside drought polygons means outside D0-D4 at validated CONUS points, not worldwide no drought.",
                "Three source geometries have self-intersections;32fixed point labels agree under independent ring parity and make_valid. Area tasks not admitted by this test."]
        },
        {
            "id": "sevir_original", "selection": "core_v1",
            "provider": "MIT Lincoln Laboratory / MIT-AI Accelerator SEVIR",
            "product": "Original SEVIR AWS catalog and HDF5 VIL/IR069/IR107 products",
            "release": "Frozen catalog and exact HDF5 byte ranges with ETag/body hashes captured2026-09-10",
            "roles": ["public_native_VIL_visualization", "coverage_support", "product_sequence", "active_evidence"],
            "reference_kind": "archived_encoded_product_pixels_and_deterministic_coverage_bounds",
            "validated_subset": {"catalog_rows": 76004, "catalog_distinct_ids": 20838,
                "initial_arrays_decoded": 27, "initial_catalog_ids": 8, "qualified_three_channel_sequences": 5,
                "additional_natural_coverage_VIL_sequences": native["complete_native_arrays"],
                "additional_frames_examined": native["frames_examined"], "natural_coverage_model_episodes": 12},
            "artifacts": [bind(p) for p in ["data/SEVIR_ARRAYS.json", "analysis/SEVIR_FEASIBILITY_02.json",
                "data/NATURAL_COVERAGE_SELECTION.json", "data/NATURAL_COVERAGE_ARRAYS.json",
                "analysis/NATURAL_COVERAGE_FEASIBILITY.json", "data/VIL_RENDER_PALETTE.json"]],
            "rights": {"status": "no_use_restrictions_in_AWS_registry", "evidence": [license_capture("sevir-registry-license")],
                "conditions": "Retain SEVIR citation and provenance; software licenses are separate."},
            "time_profile": "native_frame_clock_only_after_ID_channel_and_monotonic_offset_checks",
            "split_unit": "event_episode_and_spatiotemporal_overlap_components",
            "limitations": ["VIL255 is missing; encoded VIL is not surface rainfall or verified disaster damage.",
                "IR channels decoded/aligned, but no IR model capability claim.",
                "Native palette PNG is source-product rendering; comparison with exact counts includes a perception task.",
                "Coverage-stratified selection is not a natural prevalence estimate."]
        },
    ]
    conditional = [
        {"id": "geoid_flood", "selection": "conditional_extension", "priority": 1,
         "verified": "Official paper and repository;219events/14282tiles; CC-BY4 dataset, MIT code, DEM has separate Copernicus terms.",
         "blocking_evidence": "Nine pinned mirror raster attempts timed out; no complete image/label pair in this environment.",
         "admission_gate": "Complete aligned pre/post SAR+validity+permanent/flood labels across predeclared events; verify transforms/times/classes and positive/negative support before any model test.",
         "natural_revision_claim": False},
        {"id": "sen1floods11_v1_1", "selection": "not_in_unrestricted_v1",
         "verified": "Three complete spatial pairs out of eight planned; published-annotation provenance and S1/S2 timing checked.",
         "blocking_evidence": "Four official STAC collections have proprietary license fields; repository license API404; alternative permission not established.",
         "admission_gate": "Unambiguous dataset-specific reuse terms and task claims limited to published water labels.",
         "rights_interpretation": "Metadata ambiguity is not a legal conclusion that all dataset uses are prohibited."},
        {"id": "worldfloods", "selection": "conditional_noncommercial_alternative",
         "verified": "Documentation and CC-BY-NC4 terms; v1GCS requester-pays access documented.",
         "blocking_evidence": "Native imagery pipeline not validated; noncommercial restriction is less suitable for a broadly reusable core."},
        {"id": "firms_fire_activity", "selection": "deferred_extension",
         "reason": "Detection without coverage does not certify absence of wildfire; coverage/outcome pairing not established."},
    ]
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "decision": "core_source_selection_fixed_after_feasibility",
        "core_source_families": 4, "core_products": 5, "products": products, "conditional_or_deferred": conditional,
        "status": "validated_development_material; full_benchmark_release_not_yet_built",
        "release_policy": "Publish code, derived task definitions, source-specific attribution and hashed fetch manifests; release raw assets only under their own applicable terms.",
        "per_item_review": "No new per-item human annotation or LLM judge; published expert products may be inherited and disclosed.",
        "candidate_coverage_limit": "257namespaced candidate records in five source plans are not257independent datasets and have not all been validated.",
        "retained_historical_holdout_storms": ["AL142016", "AL112017", "AL152017", "AL142018", "AL132020", "AL092022", "AL102023", "AL022024"],
        "new_heldout_inference": False}
    dump(ROOT / "FINAL_DATASETS.json", result)
    print(json.dumps({"core_products": len(products), "conditional_or_deferred": len(conditional),
                      "sha256": sha_file(ROOT / "FINAL_DATASETS.json")}))


if __name__ == "__main__":
    main()
