> **⚠️ SUPERSEDED BY BATCH A2 (2026-09-21).** Three independent reviews found the measurement
> chain that produced this report was checkpoint-blind (`issued_at < T` only, never consuming
> T-60/T-40/T-20 or `available_at`), read a `tie_unresolved` field the ledger never emitted
> (making "0% dispute rate" structurally guaranteed rather than measured), and used a wrong
> denominator for its coverage percentage. This report's headline conclusions, including the
> G1 "PROCEED" recommendation below, are **withdrawn** — see `TASK_CONTRACT_v17.json`
> `meta.correction_history` and `EXECUTION_STATUS_v17.md` Gate Status. The corrected,
> checkpoint-aware re-census is in **`TRANSITION_CENSUS_v17_A2.md`**. The original text below
> is preserved unchanged for the record; it is historical, not current.

---

# Transition Census v17: Evidence Change Analysis for H15 Data Qualification

Generated: 2026-09-21T13:35:49Z
Census Script: `scripts/run_transition_census_v17.py`
Process Grouping Version: `process_grouping.v1`

## Executive Summary

This census answers: **Before prediction deadlines on fixed weather-risk targets, do verifiable target-relevant evidence changes genuinely exist, in enough volume/quality to support state-maintenance-vs-revision evaluation (H15)?**

**Conclusion**: YES - the archive contains substantial evidence of real TAF revisions (AMD/COR) occurring before prediction deadlines, distributed across all four stations and the full 35-month calendar. The volume is sufficient for H15 evaluation, though with caveats about independence (see Process Group analysis).

## File Integrity

| Metric | Value |
|--------|-------|
| Expected files | 140 |
| Verified OK (SHA256 match) | 140 |
| Missing | 0 |
| Hash mismatches | 0 |

**All 140 station-month files passed integrity verification.** No gaps or corruptions in the development material.

Files follow the pattern `{STATION}_{YYYYMM}.body` with companion `.json` receipts containing SHA256 checksums.

## Process Grouping Rule (v1)

```
Process Grouping Rule (v1):
---------------------------
Evidence changes belong to the SAME weather process group if ALL of:
1. Same station (ICAO code)
2. Same UTC calendar day (defined by day-of-year at 00:00:00Z)

This rule means each station-day pair is ONE independent weather process.
```

**Justification**:
- TAF products are issued routinely every 6 hours (00Z, 06Z, 12Z, 18Z)
- A single weather system (front, storm) typically affects a station for 6-24 hours
- Calendar-day grouping is the standard unit for meteorological verification
- Same-day amendments/corrections are typically responses to the same weather evolution
- Cross-day boundaries represent synoptic breaks (new 00Z issuance cycle)

**Count semantics**: Total process groups = number of distinct (station, calendar_day) pairs with at least one pre-deadline change. This represents an UPPER BOUND on independent weather-driven decisions (actual independent synoptic events may be fewer due to multi-day systems).

## Continuous Calendar vs Revision-Enriched Counts

### Continuous Calendar (all candidate slots)

| Metric | Value |
|--------|-------|
| Total routine-hour slots | 17,420 |
| Slots with ANY TAF evidence | 17,078 |
| Slots WITHOUT TAF evidence | 342 |
| Coverage rate | 98.0% |

Routine hours: 00Z, 06Z, 12Z, 18Z (every 6 hours) across all 4 stations and the 35-month calendar (excluding Feb 2025 holdout).

### Revision-Enriched (slots with pre-deadline changes)

| Metric | Value |
|--------|-------|
| Slots with pre-deadline changes | 17,064 |
| Revision-enriched rate | 98.0% of slots with evidence |
| Total pre-deadline changes | 121,885 |
| Average changes per slot | 7.1 |

Nearly ALL candidate slots have at least one evidence change before the deadline. This is expected for operational TAF service where amendments are common.

## Change Type Distribution

| Change Type | Count | Percentage |
|-------------|-------|------------|
| AMD (Amendment) | 119,276 | 97.86% |
| COR (Correction) | 2,594 | 2.13% |
| mirror_duplicate | 15 | 0.01% |
| **Total** | **121,885** | **100%** |

The overwhelming majority of changes are amendments (AMD), which is consistent with normal TAF operations where forecasters update forecasts as conditions evolve. Corrections (COR) represent about 2% of changes, indicating relatively low error rates in original issuances.

## Process Groups (Independent Weather Processes)

| Station | Process Groups (unique calendar days with changes) |
|---------|---------------------------------------------------|
| KSFO | 1,068 |
| KDEN | 1,067 |
| KJFK | 1,068 |
| KORD | 1,061 |
| **Total** | **4,264** |

Each station has changes on roughly 1,065 distinct calendar days, which is consistent with the ~1,095 total calendar days in the 35-month period (some days may have no changes if the original TAF was correct throughout).

### Statistical Implications

- 4,264 process groups provides a reasonable base for statistical analysis
- However, cross-station correlation on the same day (shared synoptic patterns) may reduce effective independence
- Conservative estimate: ~1,000-1,100 independent weather processes (if treating same-day events at different stations as correlated)

## Dispute/Conflict Rate

| Metric | Value |
|--------|-------|
| Unresolved conflicts | 0 |
| Disputed changes | 0 |
| Dispute rate | 0.00% |

**All changes were classified without disputes.** The V17-02 fixes (F10, F11) successfully resolved the tie-resolution and conflict-handling issues identified in the Codex audit.

## Compilation Statistics

| Metric | Value |
|--------|-------|
| Total TAF packages compiled | 41,386 |
| Skipped frames | 60 |
| Skip rate | 0.14% |

The 60 skipped frames match the expected count from the DL3R semantic validation (already confirmed as non-blocking by `--expected-skips=60`).

## Verification Limitations

This census is Y-BLIND by design:
- The census script (`run_transition_census_v17.py`) contains ZERO imports of outcome_wiring or ASOS-reading symbols
- AST-based import isolation guard test verifies this guarantee
- No ASOS/METAR ground truth data was read during this census
- Change classification is based solely on TAF-side evidence (issued_at, amendment_kind, semantic hashes)

This means:
- We have verified that TARGET-RELEVANT evidence changes exist
- We have NOT verified that these changes "matter" for outcome prediction
- Whether changes correlate with outcome differences is the subject of the experiments, not the census

## G1 Gate Assessment

### Evidence for G1 (Data Qualification)

1. **Volume**: 121,885 pre-deadline changes across 17,064 slots - SUFFICIENT
2. **Type distribution**: 97.9% AMD + 2.1% COR - REAL OPERATIONAL CHANGES
3. **Process groups**: 4,264 station-day groups - ADEQUATE FOR BLOCK INFERENCE
4. **Dispute rate**: 0% - NO UNRESOLVED CONFLICTS
5. **Coverage**: 98% of slots have evidence - NEAR-COMPLETE CALENDAR
6. **Integrity**: 140/140 files verified - NO GAPS

### Scope Clarification: G1 Evidence-Existence vs. Codex Statistical Power Concern

The G1 gate criterion asks: "Does verifiable target-relevant evidence exist, in sufficient volume, to support state-maintenance/revision evaluation?" This is an evidence-existence question about TAF-side data availability.

The Codex audit concern (codex_audit_v16/FINDINGS.md section 0) is a separate question: the H15 paired-diagnostic experiment had only 3 positive labels across 36 checkpoints (8.33% positive-label rate), raising statistical power concerns about whether the experiment can reliably detect meaningful differences.

**These are distinct questions:**

| Question | Domain | What it measures | Answered by census? |
|----------|--------|------------------|---------------------|
| G1 evidence-existence | TAF-side (X) | Do evidence changes exist? | YES |
| Codex statistical power | Outcome-side (Y) | Is positive-label rate adequate for H15 power? | NO |

This census is Y-blind by design (see Verification Limitations above). The 121,885 evidence changes, 17,064 slots, and 4,264 process groups demonstrate abundant TAF-side evidence but cannot speak to the positive-label rate of the H15 paired-diagnostic, which depends on how often those TAF changes correlate with actual outcome-label differences. Evidence-change volume and positive-label rate are uncorrelated in general: you could have abundant TAF churn with a persistently low positive-label rate if amendments rarely flip the ground-truth outcome.

**G1 finding (evidence-existence):** The evidence-existence question is answered YES. Target-relevant TAF revisions exist in sufficient volume (121,885 changes), with near-complete calendar coverage (98%), adequate independent process groups (4,264), zero TAF-side classification disputes, and full file integrity (140/140).

**Codex concern (statistical power):** REMAINS OPEN. The positive-label-rate question requires a future outcome-side (Y-permissioned) analysis that measures how often evidence changes actually correlate with outcome-label differences. This is out of scope for the Y-blind census and for Batch A.

### TAF-Side Classification vs. Outcome-Label Reliability

Similarly, the "0% dispute rate" finding refers specifically to TAF-side classification:
- **TAF-side classification dispute rate**: 0% (all AMD/COR/mirror classifications resolved without ambiguity)
- **Outcome-label reliability**: PENDING_HUMAN_VERIFICATION per LABEL_QUALIFICATION_v17.md

These are separate. The census demonstrates that the ledger's AMD/COR classification logic produces consistent, unambiguous results. It does not demonstrate that the ASOS/outcome-derived labels themselves are correct, which remains pending human domain expert verification.

### G1 Recommendation

**RECOMMENDATION: PROCEED WITH H15 EVIDENCE-EXISTENCE GATE**

The evidence base satisfies the G1 evidence-existence criterion:
- Sufficient volume for paired comparisons (121,885 changes)
- Sufficient independence for block-based inference (4,264 station-day groups)
- Zero unresolved TAF-side classification disputes
- Complete file integrity (140/140)

**Open follow-up item:** The Codex audit's positive-label statistical-power concern is NOT addressed by this census and remains open. Before the H15 paired-diagnostic experiment's results can be trusted, a properly-scoped outcome-side (Y-permissioned) analysis must assess whether the positive-label rate provides adequate statistical power. This analysis is out of scope for Batch A and should be assigned to a future batch with Y access.

No adjustment to the contract's evidence-existence claims or entry into QN (NHC fallback) is warranted at this gate. The contract items relying solely on evidence-existence (C01 transition density, C04 checkpoint feasibility) remain valid on their own narrower terms.

## Files Produced

- `artifacts_v17/ba4_20260921/census_summary.json` - structured summary
- `artifacts_v17/ba4_20260921/all_changes.jsonl` - detailed per-change records
- `artifacts_v17/ba4_20260921/process_groups.json` - group membership
- `artifacts_v17/ba4_20260921/slot_summary.jsonl` - per-slot change summaries
