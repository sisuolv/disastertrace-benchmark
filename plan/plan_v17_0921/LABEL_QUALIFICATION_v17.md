> **⚠️ SUPERSEDED BY BATCH A2 (2026-09-21).** This report's 15-sample AI-re-read has been
> superseded by a 30-item byte-identity-traceable witness package built from the corrected
> checkpoint-aware census (26/26 change-level witnesses resolved to exact byte offsets, all 7
> structural witness types represented). See **`LABEL_QUALIFICATION_v17_A2.md`**. Both this
> original report and the A2 report remain honestly `PENDING_HUMAN_VERIFICATION` /
> `PENDING_INDEPENDENT_REVIEW` respectively — neither claims genuine independent human review
> has occurred. The original text below is preserved unchanged for the record.

---

# Label Qualification v17: Classification Reliability Assessment

Generated: 2026-09-21
Census Script: `scripts/run_transition_census_v17.py`

## PENDING_HUMAN_VERIFICATION

**CRITICAL NOTICE**: All label classifications in this report are marked as `PENDING_HUMAN_VERIFICATION`. The verification samples below were re-derived by the executing AI agent (Claude Opus 4.5) from raw TAF text, NOT by independent human reviewers.

While this provides a consistency check (the agent's re-read matches the script's automated classification), it does NOT constitute genuine independent human verification. The actual resource constraint is stated honestly: no human reviewer was available for this round.

A genuine second-party verification would require:
1. A human domain expert independently reading the raw TAF bulletin text
2. Applying the WMO amendment/correction rules (BBB indicators)
3. Confirming the lineage relationships (which TAF supersedes which)
4. Cross-checking against the script's automated classification

Until such review occurs, all classifications should be treated as provisional.

## Verification Sample Selection

**Method**: Random sampling with fixed seed (20260921) from the full change population.
**Sample size**: 10 AMD changes + 5 COR changes = 15 total (0.012% of 121,885 changes)
**Selection criteria**: Changes with non-null predecessor_source_id (i.e., actual supersession relationships)

This sample size is NOT statistically powered to detect rare classification errors. It serves only as a basic sanity check that the classification logic produces plausible results on examined examples.

## Verified AMD Samples

### Sample 1: KDEN Feb 13, 2023 (VERIFIED CORRECT)

| Field | Predecessor | Current |
|-------|-------------|---------|
| source_id | KDEN-1676287740000000-d561aebf3285 | KDEN-1676290140000000-55b355277a43 |
| issued_at | 2023-02-13T11:29:00Z | 2023-02-13T12:09:00Z |
| amendment_kind | original | AMD |
| wmo_bbb | None | AAA |
| valid_start | 2023-02-13T12:00:00Z | 2023-02-13T12:00:00Z |
| valid_end | 2023-02-14T18:00:00Z | 2023-02-14T18:00:00Z |

**Re-read verification**: The raw TAF text shows:
- First bulletin has no BBB indicator (original issuance)
- Second bulletin has BBB=AAA (first amendment)
- Both share the same validity window
- The AMD correctly supersedes the original

**Classification**: `PENDING_HUMAN_VERIFICATION` - AI re-read matches script classification

### Sample 2: (Additional samples from automated verification)

The following samples were verified by the same method (AI re-read of raw TAF text):

| Station | Month | Classification | Verification Status |
|---------|-------|----------------|---------------------|
| KDEN | 202302 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KJFK | 202309 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KDEN | 202308 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KORD | 202303 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KSFO | 202509 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KJFK | 202302 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KDEN | 202509 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KDEN | 202501 | AMD | `PENDING_HUMAN_VERIFICATION` |
| KJFK | 202306 | AMD | `PENDING_HUMAN_VERIFICATION` |

## Verified COR Samples

### Sample 1: KDEN May 27, 2024 (VERIFIED CORRECT)

| Field | Predecessor | Current |
|-------|-------------|---------|
| source_id | KDEN-1716803700000000-eaeecc9c0407 | KDEN-1716804660000000-2291e2e0c022 |
| issued_at | 2024-05-27T09:55:00Z | 2024-05-27T10:11:00Z |
| amendment_kind | AMD | COR |
| wmo_bbb | AAB | CCA |
| valid_start | 2024-05-27T10:00:00Z | 2024-05-27T10:00:00Z |
| valid_end | 2024-05-28T12:00:00Z | 2024-05-28T12:00:00Z |

**Re-read verification**: The raw TAF text shows:
- Predecessor has BBB=AAB (second amendment)
- Current has BBB=CCA (first correction)
- Both share the same validity window
- The COR correctly supersedes the AMD (lineage-based, not exact-window-only)

**Classification**: `PENDING_HUMAN_VERIFICATION` - AI re-read matches script classification

### Additional COR Samples

| Station | Month | Predecessor Kind | Classification | Verification Status |
|---------|-------|------------------|----------------|---------------------|
| KDEN | 202405 | AMD | COR | `PENDING_HUMAN_VERIFICATION` |
| KSFO | 202404 | original | COR | `PENDING_HUMAN_VERIFICATION` |
| KDEN | 202408 | original | COR | `PENDING_HUMAN_VERIFICATION` |
| KJFK | 202403 | AMD | COR | `PENDING_HUMAN_VERIFICATION` |
| KORD | 202403 | original | COR | `PENDING_HUMAN_VERIFICATION` |

## Classification Logic Summary

The classification logic (from `ledger.py`) uses:

1. **amendment_kind field**: Extracted from raw TAF text based on presence of AMD/COR/CNL keywords
2. **wmo_bbb indicator**: The WMO BBB field (AAA/AAB/AAC for amendments, CCA/CCB/CCC for corrections)
3. **Lineage-based supersession**: Products in the same lineage (station + provider + product_series) with overlapping/adjacent validity windows
4. **Receipt-order tie resolution**: When multiple products have the same issued_at, resolved by receipt_seq with BBB cross-validation

## Error Rate Estimation

Based on the 15-sample verification (all matching):
- Point estimate: 0% classification error
- But 95% CI for 0/15: [0%, 21.8%] (using exact binomial)

**This confidence interval is very wide because the sample is small.** We cannot rule out a true error rate up to ~20% based on this sample alone.

However, the classification logic is deterministic and based on explicit WMO standards:
- AMD/COR/CNL keywords are unambiguous in TAF text
- BBB indicators follow strict WMO patterns (AA*, CC*, RR*)
- The logic has been tested against 41,386 compiled packages with no assertion failures

## Limitations

1. **No human verification**: All "verifications" were AI re-reads, not human domain expert review
2. **Small sample**: 15/121,885 = 0.012% coverage
3. **No adversarial testing**: No intentionally malformed or edge-case TAF text was examined
4. **Provenance assumption**: We assume IEM archive faithfully reproduces original AFOS bulletins
5. **No cross-source validation**: No comparison against independent TAF archives (e.g., OGIMET, NOAA NOAAport)

## Recommendations for Human Verification

If human verification resources become available:
1. Sample at least 100-300 changes (0.1-0.25%) stratified by station and change type
2. Have a meteorology domain expert independently classify each sampled TAF pair
3. Compare against automated classification
4. Focus on edge cases: same-minute issuances, cross-window amendments, RRx bulletins
5. Document any disagreements and resolution

## Conclusion

All 15 sampled classifications match the expected values based on AI re-reading of raw TAF text. However, this check is self-referential (same reasoning system) and should NOT be reported as "independently verified."

**Status**: `PENDING_HUMAN_VERIFICATION` until genuine domain expert review is completed.
