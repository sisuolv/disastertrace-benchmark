"""Instrument smoke test for v16-MP measurement-prep round.

THIS IS AN INSTRUMENT SMOKE TEST ON ONE EPISODE. IT MAKES NO STATISTICAL CLAIM.
THIS IS NOT A PRE-REGISTERED MEASUREMENT.

The purpose is to exercise the full pipeline end-to-end with real data to verify
plumbing works correctly. Results demonstrate instrument operability, not method
quality.

Station-month: KSFO 2023-01
Target slot: 2023-01-02T00:00:00Z (first hour of second UTC day)
Threshold: visibility < 5000.0 meters
Instrument grid: T-60/T-40/T-20 minutes before slot start, equal weight (1/3 each)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output report path. Default: dev root INSTRUMENT_SMOKE_KSFO_2023-01_v16.md",
    )
    args = parser.parse_args()

    project = Path(__file__).resolve().parents[1]
    dev_root = project.parents[1]

    # Paths to real data (read-only)
    # Data is at extreme_weather_benchmark/data_real_v16/, which is 3 levels up from project
    # project = disastertrace-starter
    # dev_root = v14_revision_20260919_01 (contains .venv and repo)
    # dev_root.parent = development
    # dev_root.parent.parent = extreme_weather_benchmark (contains data_real_v16)
    data_root = dev_root.parent.parent / "data_real_v16"
    taf_body_path = (
        data_root / "taf" / "20260920T134949Z_1bbe63aedc00_dl3rbulk" / "KSFO_202301.body"
    )
    taf_receipt_path = taf_body_path.with_suffix(".json")
    asos_body_path = (
        data_root / "asos" / "KSFO" / "2023-01" / "20260920T083945Z_5a91ac05a955" / "asos-sfo-202301.body"
    )
    asos_receipt_path = asos_body_path.with_suffix(".json")

    output_path = args.output
    if output_path is None:
        output_path = dev_root / "INSTRUMENT_SMOKE_KSFO_2023-01_v16.md"

    # Import modules from the project
    import sys
    sys.path.insert(0, str(project / "src"))

    from disastertrace.monitoring_v1.targets import utc_us
    from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream, compile_asos_csv_to_observations
    from disastertrace.revision_v1.ledger import compile_ledger
    from disastertrace.revision_v1.outcome_wiring import (
        make_h15_visibility_target,
        select_routine_observations,
        resolve_h15_outcomes,
        register_h15_outcomes,
        make_resolution_version,
        load_asos_with_provenance,
    )
    from disastertrace.revision_v1.p1_harness import (
        ArmType,
        MethodArmRunner,
        TrapPolicyMethodAdapter,
        create_default_baseline_registry,
    )
    from disastertrace.revision_v1.metrics import trajectory_score_Q_with_bounds

    report_lines: list[str] = []

    def log(msg: str):
        print(msg)
        report_lines.append(msg)

    log("# v16-MP Instrument Smoke Test: KSFO 2023-01")
    log("")
    log("**WARNING: THIS IS AN INSTRUMENT SMOKE TEST ON ONE EPISODE.**")
    log("**IT MAKES NO STATISTICAL CLAIM. THIS IS NOT A PRE-REGISTERED MEASUREMENT.**")
    log("")
    log("Purpose: verify full pipeline end-to-end with real data.")
    log("")
    log(f"Run timestamp: {datetime.now(timezone.utc).isoformat()}")
    log("")

    # =========================================================================
    # Step 1: Load and verify TAF data
    # =========================================================================
    log("## Step 1: Load TAF Data")
    log("")

    # Read receipt
    with open(taf_receipt_path) as f:
        taf_receipt = json.load(f)
    log(f"TAF receipt: {taf_receipt_path}")
    log(f"- Expected sha256: `{taf_receipt['sha256']}`")
    log(f"- Expected frame_count_etx: {taf_receipt['frame_count_etx']}")

    # Read body and verify sha256
    with open(taf_body_path, "rb") as f:
        taf_body_bytes = f.read()
    computed_sha256 = hashlib.sha256(taf_body_bytes).hexdigest()
    log(f"- Computed sha256: `{computed_sha256}`")

    if computed_sha256 != taf_receipt["sha256"]:
        raise ValueError(f"TAF SHA256 mismatch: {computed_sha256} != {taf_receipt['sha256']}")
    log("- SHA256 verification: PASS")

    taf_text = taf_body_bytes.decode("utf-8")

    # Compile TAF packages
    packages, skipped = compile_afos_taf_stream(
        taf_text,
        station="KSFO",
        reference_month="2023-01",
    )

    log(f"- Compiled packages: {len(packages)}")
    log(f"- Skipped frames: {len(skipped)}")

    # ASSERTION: 303 packages, 0 skipped
    if len(packages) != 303 or len(skipped) != 0:
        raise ValueError(f"STOP: Expected 303 packages/0 skipped, got {len(packages)}/{len(skipped)}")
    log("- Assertion (303/0): PASS")

    # Check amendment_kind distribution
    kind_counter: Counter = Counter(p["amendment_kind"] for p in packages)
    log(f"- amendment_kind distribution: {dict(kind_counter)}")

    # =========================================================================
    # Step 2: Deduplicate known duplicate source_id
    # =========================================================================
    log("")
    log("## Step 2: Deduplicate Packages")
    log("")

    # Find duplicates
    source_id_map: dict[str, list[dict]] = {}
    for p in packages:
        sid = p["source_id"]
        if sid not in source_id_map:
            source_id_map[sid] = []
        source_id_map[sid].append(p)

    duplicates = [(sid, plist) for sid, plist in source_id_map.items() if len(plist) > 1]
    log(f"- Found {len(duplicates)} duplicate source_id(s)")

    if duplicates:
        for sid, plist in duplicates:
            log(f"  - source_id `{sid}`: {len(plist)} copies")
            # Dedup policy: keep first occurrence (by index in original list)
            log(f"    - Keeping first occurrence, discarding {len(plist)-1} duplicate(s)")

    # Build deduplicated list (keep first occurrence per source_id)
    seen_ids: set[str] = set()
    deduped_packages: list[dict] = []
    for p in packages:
        sid = p["source_id"]
        if sid not in seen_ids:
            seen_ids.add(sid)
            deduped_packages.append(p)

    log(f"- Packages after dedup: {len(deduped_packages)}")

    # =========================================================================
    # Step 3: Build Ledger
    # =========================================================================
    log("")
    log("## Step 3: Build Ledger")
    log("")

    # The compile_ledger signature per reading the actual code at ledger.py:391:
    # compile_ledger(products: list[dict], *, declared_lag_us: int = DEFAULT_DECLARED_LAG_US,
    #                collector_first_seen: dict[str, int] | None = None) -> list[dict]
    # No fabricated wall-clock collector_first_seen for 2023 data.
    DECLARED_LAG_US = 120_000_000  # 120 seconds = 2 minutes

    ledger = compile_ledger(
        deduped_packages,
        declared_lag_us=DECLARED_LAG_US,
        collector_first_seen=None,
    )
    log(f"- Ledger entries: {len(ledger)}")
    log(f"- declared_lag_us: {DECLARED_LAG_US} (120 seconds)")
    log("- collector_first_seen: None (declared_lag basis only for historical episode)")

    # Count ledger kinds
    ledger_kind_counter: Counter = Counter(e["kind"] for e in ledger)
    log(f"- Ledger kind distribution: {dict(ledger_kind_counter)}")

    # =========================================================================
    # Step 4: Load and verify ASOS data
    # =========================================================================
    log("")
    log("## Step 4: Load ASOS Data")
    log("")

    # Load with provenance verification (sha256 check built in)
    asos_content, asos_provenance = load_asos_with_provenance(str(asos_body_path))

    log(f"ASOS body: {asos_body_path}")
    log(f"- sha256: `{asos_provenance.sha256}`")
    log(f"- run_id: `{asos_provenance.run_id}`")

    # Compile to observations
    observations, asos_skipped = compile_asos_csv_to_observations(
        asos_content,
        station="KSFO",
    )
    log(f"- Compiled observations: {len(observations)}")
    log(f"- Skipped rows: {len(asos_skipped)}")

    # ASSERTION: 801 observations, 0 skipped (per parent's verification)
    if len(observations) != 801 or len(asos_skipped) != 0:
        raise ValueError(f"Expected 801 obs/0 skipped, got {len(observations)}/{len(asos_skipped)}")
    log("- Assertion (801/0): PASS")

    # Select routine observations
    routine_obs, routine_meta = select_routine_observations(observations, station="KSFO")
    log(f"- Routine observations (modal minute {routine_meta['modal_minute']}): {len(routine_obs)}")
    log(f"- Modal count: {routine_meta['modal_count']}")

    # ASSERTION: modal minute 56, count 720
    if routine_meta["modal_minute"] != 56 or routine_meta["modal_count"] != 720:
        raise ValueError(
            f"Expected modal_minute=56, modal_count=720, got {routine_meta['modal_minute']}/{routine_meta['modal_count']}"
        )
    log("- Assertion (minute 56, count 720): PASS")

    # =========================================================================
    # Step 5: Build Target and Resolve Outcome
    # =========================================================================
    log("")
    log("## Step 5: Build Target and Resolve Outcome")
    log("")

    # Target slot: 2023-01-02T00:00:00Z
    slot_start_str = "2023-01-02T00:00:00+00:00"
    slot_start_us = utc_us(slot_start_str)
    threshold_m = 5000.0

    target = make_h15_visibility_target(
        station="KSFO",
        slot_start_us=slot_start_us,
        threshold_m=threshold_m,
    )
    log(f"- Target ID: `{target.target_id}`")
    log(f"- contract_hash: `{target.contract_hash}`")
    log(f"- slot_start: {slot_start_str}")
    log(f"- threshold: {threshold_m} meters")

    # Resolve outcome
    resolution_version = make_resolution_version(asos_provenance)
    outcome_records = resolve_h15_outcomes(
        routine_obs,
        [target],
        provenance=asos_provenance,
        resolution_version=resolution_version,
    )

    if len(outcome_records) != 1:
        raise ValueError(f"Expected 1 outcome record, got {len(outcome_records)}")

    outcome_record = outcome_records[0]
    log("")
    log(f"- Resolution version: `{resolution_version}`")
    log(f"- Outcome status: `{outcome_record['status']}`")
    log(f"- Outcome value: `{outcome_record['value']}`")

    # ASSERTION: value is strictly int or None
    outcome_value = outcome_record["value"]
    if outcome_value is not None and not isinstance(outcome_value, int):
        raise ValueError(f"Outcome value must be int or None, got {type(outcome_value)}")
    if isinstance(outcome_value, bool):
        raise ValueError("Outcome value must not be bool")
    log("- Type assertion (int or None, not bool): PASS")

    # Get the raw report text that determined the outcome
    refs = outcome_record.get("references", [])
    raw_report = refs[0]["raw"] if refs else "(no raw report in record)"
    log(f"- Raw determining report: `{raw_report}`")

    # Register in formal_provider_bound mode
    log("")
    log("### Outcome Registry Round-Trip")
    registry, success_flags = register_h15_outcomes(
        outcome_records,
        [target],
        mode="formal_provider_bound",
    )

    log(f"- Registry mode: formal_provider_bound")
    log(f"- First registration success: {success_flags[0]}")

    # Read back from registry to verify round-trip
    # Registry key is (contract_hash, resolution_version)
    readback_key = (target.contract_hash, resolution_version)
    readback = registry.records.get(readback_key)
    if readback is None:
        raise ValueError("Failed to read back outcome from registry")
    log(f"- Round-trip readback value: `{readback['value']}`")

    # Re-register to test idempotency (same record returns False)
    replay_result = registry.register(outcome_record)
    # First registration returns True, replay returns False (idempotent)
    if success_flags[0] is not True:
        raise ValueError(f"Expected first registration to return True, got {success_flags[0]}")
    if replay_result is not False:
        raise ValueError(f"Expected replay to return False, got {replay_result}")
    log("- Idempotency check: PASS (replay returns False as expected)")

    # =========================================================================
    # Step 6: Wire into P1 Harness
    # =========================================================================
    log("")
    log("## Step 6: P1 Harness Wiring")
    log("")

    # Frozen grid: T-60, T-40, T-20 minutes before slot start, equal weight
    checkpoint_offsets_min = [60, 40, 20]  # minutes before slot
    weight_each = 1.0 / 3.0
    checkpoints = []
    for offset_min in checkpoint_offsets_min:
        checkpoint_us = slot_start_us - (offset_min * 60 * 1_000_000)
        checkpoints.append((checkpoint_us, weight_each))

    # ASSERTION: weights sum to ~1.0
    weight_sum = sum(w for _, w in checkpoints)
    if not math.isclose(weight_sum, 1.0, rel_tol=1e-9):
        raise ValueError(f"Checkpoint weights must sum to 1.0, got {weight_sum}")
    log(f"- Grid checkpoints: T-{checkpoint_offsets_min[0]}, T-{checkpoint_offsets_min[1]}, T-{checkpoint_offsets_min[2]} minutes")
    log(f"- Weight per checkpoint: {weight_each:.6f}")
    log(f"- Weight sum: {weight_sum} (assertion PASS)")

    # Format checkpoint times for display
    for i, (cp_us, w) in enumerate(checkpoints):
        cp_dt = datetime.fromtimestamp(cp_us / 1_000_000, tz=timezone.utc)
        log(f"- Checkpoint {i+1}: {cp_dt.isoformat()} (T-{checkpoint_offsets_min[i]}min)")

    # Build evidence_values dict - for ORACLE_LEDGER we don't need specific probabilities
    # but the adapter may use them. Use a default of 0.5 for each package.
    evidence_values: dict[str, float] = {p["source_id"]: 0.5 for p in deduped_packages}

    # Create TrapPolicyMethodAdapter for ORACLE_LEDGER (instrument probe, not method being scored)
    episode_id = "smoke-test-ksfo-2023-01"
    target_id = target.target_id

    log("")
    log("### ORACLE_LEDGER Arm (Instrument Probe)")
    log("")
    log("NOTE: ORACLE_LEDGER is an instrument probe - mechanical, known behavior")
    log("used to sanity-check plumbing. It is NOT a method being scored for skill.")
    log("")

    adapter = TrapPolicyMethodAdapter(
        "ORACLE_LEDGER",
        episode_id=episode_id,
        target_id=target_id,
        evidence_values=evidence_values,
    )

    runner = MethodArmRunner(
        episode_id=episode_id,
        target_id=target_id,
        fallback_probability=0.5,
    )

    # Run under STATELESS arm
    result = runner.run_arm(
        ArmType.STATELESS,
        ledger=ledger,
        method=adapter,
    )

    log(f"- Arm: STATELESS")
    log(f"- Commits produced: {len(result.commits)}")

    # Check that T-60 checkpoint has non-empty visible evidence
    t60_checkpoint_us = checkpoints[0][0]
    from disastertrace.revision_v1.ledger import visible_at
    visible_at_t60 = visible_at(ledger, cutoff=t60_checkpoint_us)
    if len(visible_at_t60) == 0:
        raise ValueError("FATAL: T-60 checkpoint has no visible evidence")
    log(f"- Evidence visible at T-60: {len(visible_at_t60)} entries")
    log("- Non-empty T-60 assertion: PASS")

    # Convert commits to scoring format
    scoring_commits: list[dict] = []
    for commit in result.commits:
        for forecast in commit.get("forecast_updates", []):
            tid = forecast.get("target_id")
            prob = forecast.get("event_probability")
            if tid and prob is not None:
                as_of_str = commit.get("as_of", "")
                # Verify as_of ends with .000Z per canonical test pattern
                if not as_of_str.endswith(".000Z"):
                    log(f"  WARNING: as_of '{as_of_str}' does not end with .000Z")
                # Convert to microseconds
                effective_at = utc_us(as_of_str.replace(".000Z", "+00:00"))
                scoring_commits.append({
                    "target_id": tid,
                    "effective_at": effective_at,
                    "probability": prob,
                })

    log(f"- Scoring commits extracted: {len(scoring_commits)}")

    # =========================================================================
    # Step 7: Compute trajectory_score_Q_with_bounds
    # =========================================================================
    log("")
    log("## Step 7: Compute Trajectory Score")
    log("")

    grid = {target_id: checkpoints}
    outcomes = {target_id: outcome_value}  # outcome_value is int or None
    fallback = {target_id: 0.5}

    q_result = trajectory_score_Q_with_bounds(
        scoring_commits,
        grid,
        outcomes,
        fallback,
    )

    # ASSERTIONS on q_result keys
    expected_keys = {
        "q_settled", "q_lower_bound", "q_upper_bound",
        "settled_count", "missing_count", "coverage",
        "cohort_fingerprint", "interpretation",
    }
    actual_keys = set(q_result.keys())
    if actual_keys != expected_keys:
        raise ValueError(f"q_result keys mismatch: expected {expected_keys}, got {actual_keys}")
    log("- Result keys assertion: PASS")

    # ASSERTION: q_lower_bound <= q_upper_bound
    if q_result["q_lower_bound"] is not None and q_result["q_upper_bound"] is not None:
        if q_result["q_lower_bound"] > q_result["q_upper_bound"]:
            raise ValueError("q_lower_bound > q_upper_bound")
    log("- Bounds ordering assertion: PASS")

    # ASSERTION: settled_count + missing_count == 1
    if q_result["settled_count"] + q_result["missing_count"] != 1:
        raise ValueError(
            f"settled_count + missing_count should be 1, got {q_result['settled_count'] + q_result['missing_count']}"
        )
    log("- Single target assertion: PASS")

    # ASSERTION: 0 <= q_settled <= 1 when settled
    if q_result["q_settled"] is not None:
        if not (0 <= q_result["q_settled"] <= 1):
            raise ValueError(f"q_settled out of range: {q_result['q_settled']}")
        log("- q_settled range assertion: PASS")
    else:
        log("- q_settled is None (missing outcome)")

    # Log per-checkpoint predictions
    log("")
    log("### Per-Checkpoint Predictions (ORACLE_LEDGER)")
    log("")
    for i, (cp_us, w) in enumerate(checkpoints):
        cp_dt = datetime.fromtimestamp(cp_us / 1_000_000, tz=timezone.utc)
        # Find effective probability at this checkpoint
        # Get all commits with effective_at <= checkpoint, take latest
        relevant = [c for c in scoring_commits if c["effective_at"] <= cp_us and c["target_id"] == target_id]
        if relevant:
            relevant.sort(key=lambda c: c["effective_at"])
            p_eff = relevant[-1]["probability"]
        else:
            p_eff = 0.5  # fallback
        log(f"- T-{checkpoint_offsets_min[i]}min ({cp_dt.strftime('%H:%M')}): p_eff = {p_eff}")

    log("")
    log("### Score Result")
    log("")
    log(f"- q_settled: {q_result['q_settled']}")
    log(f"- q_lower_bound: {q_result['q_lower_bound']}")
    log(f"- q_upper_bound: {q_result['q_upper_bound']}")
    log(f"- settled_count: {q_result['settled_count']}")
    log(f"- missing_count: {q_result['missing_count']}")
    log(f"- coverage: {q_result['coverage']}")
    log(f"- cohort_fingerprint: `{q_result['cohort_fingerprint']}`")
    log(f"- interpretation: {q_result['interpretation']}")

    # =========================================================================
    # Step 8: Baselines
    # =========================================================================
    log("")
    log("## Step 8: Baseline Registry")
    log("")

    baseline_registry = create_default_baseline_registry()
    baseline_names = [b.name for b in baseline_registry.all_baselines()]
    log(f"- Registered baselines: {baseline_names}")

    # For each baseline, try to get prediction at T-60 checkpoint
    t60_us = checkpoints[0][0]
    log("")
    log("### Baseline Predictions at T-60")
    log("")

    for baseline in baseline_registry.all_baselines():
        try:
            pred = baseline.predict(
                target_id,
                t60_us,
                ledger=ledger,
                evidence_values=evidence_values,
            )
            # pred is a dict with keys: probability, claim_status, baseline_name, etc.
            claim_status = pred["claim_status"]
            if claim_status.value == "not_tested":
                log(f"- {baseline.name}: NOT_TESTED (no fitted parameters for this episode)")
            else:
                log(f"- {baseline.name}: probability={pred['probability']}, claim_status={claim_status.value}")
        except Exception as e:
            log(f"- {baseline.name}: ERROR - {e}")

    log("")
    log("NOTE: climatology/follow_mapping/values_bank baselines are explicitly NOT_TESTED")
    log("per hard constraint (no Y-derived parameter fitting from this month's data).")

    # =========================================================================
    # Summary
    # =========================================================================
    log("")
    log("## Summary")
    log("")
    log("### Source Data")
    log("")
    log(f"- TAF body SHA256: `{taf_receipt['sha256']}`")
    log(f"- ASOS body SHA256: `{asos_provenance.sha256}`")
    log(f"- TAF packages compiled: 303 (1 duplicate removed = 302 unique)")
    log(f"- ASOS observations compiled: 801")
    log(f"- Routine observations: {len(routine_obs)} (modal minute 56)")
    log("")
    log("### Target")
    log("")
    log(f"- Target ID: `{target.target_id}`")
    log(f"- contract_hash: `{target.contract_hash}`")
    log(f"- Slot: 2023-01-02T00:00:00Z")
    log(f"- Threshold: visibility < 5000.0m")
    log("")
    log("### Outcome")
    log("")
    log(f"- Status: `{outcome_record['status']}`")
    log(f"- Value: `{outcome_value}` (type: {type(outcome_value).__name__})")
    log(f"- Determining report: `{raw_report}`")
    log("")
    log("### ORACLE_LEDGER Score (Instrument Probe)")
    log("")
    log(f"- q_settled: {q_result['q_settled']}")
    log(f"- q_lower_bound: {q_result['q_lower_bound']}")
    log(f"- q_upper_bound: {q_result['q_upper_bound']}")
    log(f"- cohort_fingerprint: `{q_result['cohort_fingerprint']}`")
    log("")
    log("### Assertions Passed")
    log("")
    log("- [x] TAF SHA256 matches receipt")
    log("- [x] TAF packages: 303, skipped: 0")
    log("- [x] ASOS observations: 801, skipped: 0")
    log("- [x] Modal minute: 56, count: 720")
    log("- [x] Outcome value is int or None (not bool)")
    log("- [x] Checkpoint weights sum to 1.0")
    log("- [x] T-60 has non-empty visible evidence")
    log("- [x] trajectory_score_Q_with_bounds result has expected keys")
    log("- [x] q_lower_bound <= q_upper_bound")
    log("- [x] settled_count + missing_count == 1")
    log("- [x] 0 <= q_settled <= 1 (when settled)")
    log("")
    log("---")
    log("END OF INSTRUMENT SMOKE TEST REPORT")

    # Write report
    report_text = "\n".join(report_lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report_text)
    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()
