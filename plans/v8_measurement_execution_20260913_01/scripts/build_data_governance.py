"""Bind exposed calendars, missingness, and narrow admissions to source receipts."""

import datetime as dt
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / "data_governance_01"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    calendars = [
        ("bay_initial", "development_dataset_v2", "us_west_2025_feb03_10"),
        (
            "bay_extension",
            "calendar_extension_01/dataset_v2_complete_02",
            "us_west_2025_feb03_10",
        ),
        *[
            (
                region,
                f"regional_calendar_extension_01/{region}/dataset_v2",
                "us_2025_jan06_12",
            )
            for region in ("new_york", "chicago", "denver")
        ],
    ]
    ledger, missingness = [], []
    seen_opportunities, canonical_targets, all_physical = set(), {}, set()
    for name, rel, block in calendars:
        folder = HERE / rel
        opportunities = read(folder / "public/OPPORTUNITIES.json")
        targets = {r["target_id"]: r for r in read(folder / "public/TARGETS.json")}
        outcomes = {r["target_id"]: r for r in read(folder / "private/OUTCOMES.json")}
        assert len(opportunities) == len({r["opportunity_id"] for r in opportunities})
        assert not seen_opportunities.intersection(
            r["opportunity_id"] for r in opportunities
        )
        seen_opportunities.update(r["opportunity_id"] for r in opportunities)
        counters = defaultdict(Counter)
        referenced = set()
        for row in opportunities:
            target, outcome = targets[row["target_id"]], outcomes[row["target_id"]]
            assert row["cutoff"] < target["physical_start"] < target["physical_end"]
            referenced.add(row["target_id"])
            identity = (
                target["entity"],
                target["physical_start"],
                target["physical_end"],
                target["threshold"],
            )
            reference = (outcome["status"], outcome["outcome"])
            if identity in canonical_targets:
                assert canonical_targets[identity] == reference
            canonical_targets[identity] = reference
            all_physical.add(identity[:3])
            cutoff_date = (
                dt.datetime.fromtimestamp(row["cutoff"] / 1e6, dt.timezone.utc)
                .date()
                .isoformat()
            )
            key = (
                name,
                target["entity"],
                cutoff_date,
                target["threshold"],
                row["lead_hours"],
                outcome["status"],
            )
            counters[key]["opportunities"] += 1
            counters[key]["known_binary"] += int(outcome["outcome"] in (0, 1))
            counters[key]["positive"] += int(outcome["outcome"] == 1)
        for key, counts in sorted(counters.items()):
            missingness.append(
                dict(
                    zip(
                        (
                            "calendar",
                            "station",
                            "cutoff_date",
                            "threshold_m",
                            "lead_hours",
                            "quality_status",
                        ),
                        key,
                    ),
                    **counts,
                )
            )
        files = (
            "BUILD.json",
            "public/OPPORTUNITIES.json",
            "public/TARGETS.json",
            "private/OUTCOMES.json",
        )
        ledger.append(
            {
                "calendar": name,
                "dataset": rel,
                "provisional_dependence_block": block,
                "opportunities": len(opportunities),
                "referenced_threshold_targets": len(referenced),
                "first_cutoff": min(r["cutoff"] for r in opportunities),
                "last_cutoff": max(r["cutoff"] for r in opportunities),
                "stations": sorted({r["entity"] for r in targets.values()}),
                "exposed_to_development": True,
                "eligible_for_independent_confirmation": False,
                "regional_bank_qualified": name.startswith("bay"),
                "bank_note": "Existing Dec2023 Bay research frequency mapping with temporal transfer; no whole-system calibration guarantee."
                if name.startswith("bay")
                else "No new regional fit or qualified probability mapping; data admission only.",
                "files": {r: sha(folder / r) for r in files},
            }
        )
    save(
        "EXPOSURE_LEDGER.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "calendars": ledger,
            "total_unique_opportunities": len(seen_opportunities),
            "canonical_threshold_targets": len(canonical_targets),
            "station_time_windows_ignoring_threshold": len(all_physical),
            "independent_weather_process_count": None,
            "old_model_material": "All prior H15, NHC and other published diagnostic outcomes remain exposed; this ledger adds current calendars, not a reset of historical exposure.",
            "reserved_bay_confirmation": {
                "start": "2025-02-17T00:00:00Z",
                "end_exclusive": "2025-02-24T00:00:00Z",
                "retrieved_in_this_execution": False,
                "evaluated_in_this_execution": False,
            },
        },
    )
    save(
        "MISSINGNESS_TABLE.json",
        {
            "rows": missingness,
            "actual_model_calls": 0,
            "rule": "Source/region/date/station/threshold/lead strata retain every opportunity. No unknown outcome is imputed as zero. Baseline-risk strata require a qualified regional bank before F scoring.",
        },
    )
    save(
        "PROCESS_BLOCK_DESIGN.json",
        {
            "status": "design_only_not_independence_proof",
            "development_blocks": [
                {
                    "id": "us_2025_jan06_12",
                    "calendars": ["new_york", "chicago", "denver"],
                    "reason": "Treat concurrent regions conservatively together until synoptic-process identity is established.",
                },
                {
                    "id": "us_west_2025_feb03_10",
                    "calendars": ["bay_initial", "bay_extension"],
                    "reason": "Contiguous regional dates and shared target windows cannot be separate confirmation groups.",
                },
            ],
            "future_split_rule": "Freeze new process/calendar blocks before labels or model outputs, keep all nearby stations, thresholds, source versions, leads and parent event together. Use full evidence/target window overlap plus at least24h purge; increase purge if process provenance shows longer dependence.",
            "uncertainty_rule": "Compute paired block-level differences and resample whole blocks only after enough independently justified blocks exist; provide72h/7-day grouping sensitivity. Do not attach independent confidence intervals to this two-period development set.",
            "population_rule": "Natural calendars and externally defined enriched extremes are separate estimands; never substitute enriched prevalence into operational Brier/calibration claims.",
            "missingness_rule": "Use common outcome mask plus per-stratum missingness and existing prediction-conditional Brier bounds, reported on full opportunity denominator. A common mask alone is not population unbiasedness.",
            "confirmation_gate": "Freeze prompts, models, costs, policies, main contrasts, minimum independent-block design, outcomes and resolution/maturity before opening reserved data; do not require positive LLM gain.",
        },
    )
    registry = (
        REPO / "plans/user_authorized_sources_20260912/usage_01/USAGE_REGISTRY.json"
    )
    hazards_path = REPO / "plans/v7_0912_overall_research/OVERALL_HAZARD_CONTRACTS.json"
    prior = read(registry)
    relevant = {
        "AW-IEM": [
            "development_dataset_v2/BUILD.json",
            "regional_calendar_extension_01/BATCH_COMPLETE.json",
            "reports/large_model_diagnostic_01/VALIDATION.json",
        ],
        "AW-TAF": [
            "development_dataset_v2/BUILD.json",
            "shadow_capture_01/poll_00/taf.receipt.json",
        ],
        "AW-METAR": ["shadow_capture_01/poll_00/metar.receipt.json"],
        "AW-QPE": [
            "h07_extension_01/decoded_01/REPORT.json",
            "h07_extension_01/semantic_contract_01/QUALIFICATION.json",
        ],
        "D09": [
            "h07_extension_01/decoded_01/REPORT.json",
            "h07_extension_01/semantic_contract_01/QUALIFICATION.json",
        ],
        "AW-HEFS": ["hydro_e_extension_01/FREE_COMMON_BASELINE_CONTROL.json"],
    }
    source_rows = []
    for source in prior["sources"]:
        refs = relevant.get(source["source_id"], [])
        source_rows.append(
            {
                "source_id": source["source_id"],
                "name": source["name"],
                "inherited_access_state": source["state"],
                "new_evidence": {r: sha(HERE / r) for r in refs},
                "current_all_versions_downloadability_retested": False,
                "inherited_licence_status": source["licence_status"],
                "remaining_gates_cn": source["remaining_gates_cn"],
            }
        )
    save(
        "CANDIDATE_SOURCE_DELTA.json",
        {
            "prior_registry": {
                "path": str(registry.relative_to(REPO)),
                "sha256": sha(registry),
            },
            "inherited_source_count": len(source_rows),
            "inherited_state_counts": dict(
                Counter(r["inherited_access_state"] for r in source_rows)
            ),
            "sources": source_rows,
            "separately_qualified_extension": {
                "name": "EUPPBench forecast / DWD Berus station460 native reference pair",
                "evidence": {
                    r: sha(HERE / r)
                    for r in (
                        "temperature_extension_01/THERMAL_TARGET_CARD.json",
                        "temperature_extension_01/admission_01/REPORT.json",
                    )
                },
                "registry_note": "Separate v7/v8 point-temperature extension; not silently counted as one of the inherited97 or a complete extreme-temperature chain.",
            },
            "counting_rule": "Registered products, mirrors and benchmark wrappers are not independent weather sources, tasks, hazards or events. Historical decoded_sample means a particular sample was parsed, not every current endpoint/version was retested.",
        },
    )
    deltas = {
        "H07": (
            "12 native MRMS one-hour QPE grids, official unit/QC/duration mapping",
            "Exact physical endpoints, historical first-seen, matched F and native-MM comparison remain.",
        ),
        "H08": (
            "Two HEFS versions,697 common times and2788 native E states",
            "Full common HEFS resolves those E tasks freely; paid transport is not C1 gain. Physical QINE/member/station/F mapping remains.",
        ),
        "H10": (
            "Two-year EUPP/DWD future point-temperature validation and960 scalar replays",
            "General point forecasts and>=30C examples do not qualify heatwaves or spatial/extreme impact.",
        ),
        "H11": (
            "Same point-temperature pair includes<0C targets",
            "Cold point labels do not qualify cold waves, frost damage or multi-day process tasks.",
        ),
        "H15": (
            "Typed historical report-target E/F chain,235B/8B diagnostics, longer calendars, local serial recovery",
            "Severe-fog positives, regional calibration, fair adaptive model results, native imagery and independent confirmation remain.",
        ),
    }
    save(
        "HAZARD_ADMISSION_DELTA.json",
        {
            "prior_contract_sha256": sha(hazards_path),
            "required_final_hazards": 16,
            "hazards": [
                {
                    "id": h["id"],
                    "name_cn": h["name_cn"],
                    "current_execution_progress": deltas.get(
                        h["id"],
                        (
                            "Inherited source/legacy qualification only; no new full chain this execution.",
                            "Follow the unchanged hazard-specific target/source/availability/baseline gates.",
                        ),
                    )[0],
                    "remaining": deltas.get(
                        h["id"],
                        (
                            None,
                            "Follow the unchanged hazard-specific target/source/availability/baseline gates.",
                        ),
                    )[1],
                    "new_independent_confirmation": False,
                }
                for h in read(hazards_path)["hazards"]
            ],
            "complete_16_hazard_release": False,
            "new_independent_weather_process_count": None,
        },
    )
    print(
        json.dumps(
            {
                "opportunities": len(seen_opportunities),
                "threshold_targets": len(canonical_targets),
                "physical_windows": len(all_physical),
                "sources_inherited": len(source_rows),
                "all16_complete": False,
            }
        )
    )


if __name__ == "__main__":
    main()
