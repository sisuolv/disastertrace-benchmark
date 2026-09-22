# DisasterTrace v17 Claim-Evidence Matrix

Version: v17-candidate-20260921

## Primary Contribution Statement

Based on Codex FINDINGS section 0 recommendation:

> **A benchmark for distinguishing operational evidence maintenance from probabilistic forecasting skill under real weather-product revisions.**

This is narrower than a five-feature novelty checklist. The defensible increment is that operational revision semantics allow asking whether a probability update is responsive to genuinely new information, stale information, or repeated information. The work becomes more than repackaging only if this distinction is reliable and empirically changes what we learn about agents.

## Statistical Power Concern

**CORRECTED 2026-09-21 (Batch A2)**: the previous framing conflated four distinct variables that must be tracked separately: (a) `Y=1` (ASOS outcome label), (b) presence of a lawful, checkpoint-visible source-evidence change (X-side, Y-independent), (c) whether the model commits a factual/state-maintenance error, (d) whether a probability revision improves forecast loss. A Y-blind census (V17-03/A2-3) can speak only to (b); it cannot measure (a), and (c)/(d) require paired model experiments, not census counts.

**OPEN RISK (OR1a, Y-dependent, split from prior single OR1)**: With only 3 positive labels across 36 checkpoints (8.33% positive rate) in the pilot, and all 3 corresponding to a single KDEN event (not independent occurrences), the outcome-dependent paired-diagnostic experiments (C1/C4) may be statistically underpowered. This is **not resolvable by a Y-blind census** and requires future Y-permissioned analysis (see `TASK_CONTRACT_v17.json` open_risks.OR1a).

- The 8.33% figure is the prevalence in a selected revision-enriched pilot, not natural airport-event prevalence, and is not addressed by this batch
- Thirty-six checkpoint rows (or 72 after stacking thresholds) cannot be treated as independent trials regardless of positive rate (see OR1b: independent-process/pairing-precision, Y-independent, deferred to G3/G5)
- A comparison can be dominated by what happens on one weather event
- Repeated sampling of the same 12 targets reduces Monte Carlo uncertainty about model behavior on those targets but does not create new weather processes

**Resolution path (corrected)**: V17-03/A2-3 census measures only the Y-independent quantities: evidence-change coverage (how many targets have a checkpoint-visible source change at all), independent-target/candidate-block counts, and dispute/unknown rates. It does **not** and cannot determine whether the 8.33% positive rate is "sufficient" — that is an OR1a question requiring Y access, out of scope for this batch. If the Y-blind census shows the underlying evidence-change base rate is too sparse to support the checkpoint design at all (independent of Y), a lawful checkpoint/calendar redesign or qualified additional domain becomes necessary; that is a separate finding from the OR1a positive-rate question.

## Claim-Experiment Bidirectional Mapping

| Claim ID | Candidate Claim Statement | Evidence Required | Experiment(s) | If NOT Supported |
|----------|--------------------------|-------------------|---------------|------------------|
| C1 | The selected real tasks contain verifiable source changes sufficient to evaluate continuous state maintenance | Per-checkpoint (T-60/T-40/T-20) visible-exposure change census, not merely pre-target-start issuance; genuine original verification; no-change background and dispute rate; Y-dependent positive-label sufficiency (OR1a) is a separate, deferred requirement | X0 (Real Change Qualification) | Adjust observation window/domain; do NOT use synthetic insertion to simulate natural data |
| C2 | State-carrying method measurably affects fact state or probability trajectory compared to stateless recomputation | Fresh/Transcript/Structured comparison with identical external information and same model | X1 (State Carrying), X2 (Tool Assistance for capability attribution) | If precisely equivalent: contract state-carrying advantage claim; does not automatically invalidate entire benchmark |
| C3 | Strictly information-equivalent repeated presentation produces responses beyond sampling variability | Identity-anchor / identity-repeat / duplicate pairing with same parent, clock, input, model | X3 (Equivalent Repetition) | If equivalent: report robustness; drift does not automatically prove harm |
| C4 | Lawful fact repair has substantial impact on subsequent behavior or forecast loss | Original/repair/sham intervention with fixed starting point; repair does not change probability directly or read Y | X4 (Lawful Fact Repair), X2 (Tool Assistance) | If no loss impact: claim state reliability, do NOT claim harmful probabilistic revision |
| C5 | The system can conduct truly prospective continuous evaluation | Pre-registered tasks, credible receipt timestamps, maturation settlement, subsequent batch generation, complete failure denominator | X5 (Prospective Closed Loop) | If incomplete: label as replay or lifecycle simulation only; do NOT claim real prospective evaluation has run |

## Experiment-Claim Reverse Mapping

| Experiment ID | Experiment Name | Supports Claim(s) | Controls and Outputs | Task Assignment |
|---------------|-----------------|-------------------|---------------------|-----------------|
| X0 | Real Change Qualification | C1 | Pre-cutoff changes, negative examples, unknown cases; NO target Y selection | V17-03 |
| X1 | State Carrying | C2 | Three arms (FRESH/TRANSCRIPT/STRUCTURED) with same external prefix and model; report fact and Q separately | V17-07 |
| X2 | Tool Assistance | Bounds C2/C4 capability attribution | Same LLM Raw vs Tool-assisted; separate program predictor baseline | V17-06/07 |
| X3 | Equivalent Repetition | C3 | Identity-anchor, identity-repeat, duplicate; length-matched sham if needed | V17-07 |
| X4 | Lawful Fact Repair | C4 | Original/repair/sham; fixed starting point with suffix re-execution; repair does not directly change probability or read Y | V17-07 |
| X5 | Prospective Closed Loop | C5 | Pre-cutoff submission, concurrent baseline, mature result, complete terminal states | V17-09 |

## Completeness Verification

### Every Claim Has At Least One Experiment

- C1 -> X0
- C2 -> X1, X2
- C3 -> X3
- C4 -> X4, X2
- C5 -> X5

### Every Experiment Maps to At Least One Claim

- X0 -> C1
- X1 -> C2
- X2 -> C2 (boundary), C4 (boundary)
- X3 -> C3
- X4 -> C4
- X5 -> C5

**VERIFIED: No orphan claims. No orphan experiments.**

## Critical Non-Collapse Conditions

The following are conditions where a claim is NOT supported, but the benchmark does NOT collapse:

| Claim | Non-Support Condition | Graceful Degradation |
|-------|----------------------|---------------------|
| C1 | Insufficient transition density in H15 last hour | Adjust observation window/calendar; qualify NHC domain (QN); contract scope to achievable transitions; do NOT synthesize fake natural transitions |
| C2 | Fresh and state methods are precisely equivalent | Contract state-carrying advantage claim; continue evaluating other capabilities; state method may still be useful for efficiency |
| C3 | Equivalent presentations yield equivalent responses | Report robustness; this is a positive finding (no drift); does NOT invalidate benchmark |
| C4 | Fact repair has zero loss impact | Claim state reliability without claiming harmful probabilistic revision; still valuable diagnostic |
| C5 | Living capability not demonstrated | Label results as replay/simulation; do NOT claim prospective evaluation until demonstrated |

## Statistical Power Risk Matrix

**CORRECTED 2026-09-21 (Batch A2)**: C1 is split into a Y-independent dimension (evidence-change coverage, measurable by A2-3 census) and a Y-dependent dimension (OR1a positive-label distribution, NOT measurable by census). The two must not be reported as a single risk level.

| Claim | Depends on Positive Labels | Y-Independent Dimension (census-measurable) | Y-Dependent Dimension (requires future Y access) | Mitigation |
|-------|---------------------------|------------------|------------------|------------|
| C1 | SPLIT — see columns | Evidence-change coverage: fraction of targets with a checkpoint-visible, currently-applicable source change; independent-target/candidate-block count (A2-3) | OR1a: `P(Y=1)` distribution, unique positive-event count, method-effect precision at that positive rate | A2-3 census reports coverage only; OR1a deferred to a future Y-permissioned batch; do NOT merge the two into one "HIGH risk" label |
| C2 | NO (can evaluate on negative-outcome episodes) | MEDIUM - depends on parent state diversity | N/A | A2-3 counts parent states and candidate blocks |
| C3 | NO (drift detectable without Y) | LOW - depends on pairing design and repeated draws | N/A | V17-07 design specifies pairing structure; OR1b (independent-process/pairing precision) still applies |
| C4 | Partially (needs error states to repair) | MEDIUM - depends on natural error occurrence (census can report candidate error-state frequency) | OR1a-adjacent: forecast-loss impact requires Y | A2-3 identifies candidate error states; loss-impact analysis deferred |
| C5 | NO (prospective capability is infrastructure) | LOW - depends on implementation completion | N/A | V17-08/09 deliver lifecycle |

## Relationship to Prior Decisions

This matrix respects and builds on D01-D12 (all APPROVED):

- D01: Main problem (fixed future target + semantic ledger) adopted as primary claim focus
- D02: H15 as sole primary pilot domain (C1-C4 evaluated here); NHC data qualification only (QN fallback)
- D03: T-60/T-40/T-20 checkpoint grid (used in scoring definition)
- D04: Role D (acquire + maintain + emit) as main agent role
- D05: Deferred 3/6h backends; 1h predictor as baseline
- D06: Natural track with safety cap; Controlled for budget grid
- D07: Intervention and continuation semantics (repair/sham distinction)
- D08: Q as primary metric; semantic error rate as co-primary; small N for instrument only
- D09: Holdout closed until methods frozen
- D10: No new spend by default
- D11: LAMP categorical/probabilistic/conditional must be separately registered
- D12: Execution on data machine; this node for code/fixtures/analysis

## Open Questions for V17-03/A2-3 Census (Y-blind — answerable this batch)

1. What is the actual transition density within legal, per-checkpoint (T-60/T-40/T-20) visible exposure — not merely pre-target-start issuance?
2. How many candidate independent process/blocks (station-target-day groupings) are represented in the allowed archive, with independence left as an open question for G3/G5?
3. What is the disputed/unknown provenance (relation_status=unresolved) rate for transitions?
4. If evidence-change coverage is too sparse under the current checkpoint/calendar design, what is the QN fallback qualification status?

## Open Questions Requiring Future Y Access (deferred — NOT answerable by A2-3)

5. Is the 8.33% pilot positive rate representative, and is it sufficient for the intended experimental design? (OR1a — requires Y-permissioned analysis, out of scope for Batch A2)
