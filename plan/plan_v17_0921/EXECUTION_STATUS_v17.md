# DisasterTrace v17 Execution Status

Version: v17-20260921

## Batch A: Problem and Data Qualification

Target: Reach G1 (data qualification gate)

| Task ID | Task Name | Status | Description | Dependencies |
|---------|-----------|--------|-------------|--------------|
| BA0 (V17-00) | Candidate Contract and Claim Preparation | **DONE** | Candidate contract, claim-evidence matrix, decision table, execution status skeleton | None |
| BA1 (V17-01) | Access Boundary and Input Identity | PENDING | Allow-list paths, date guards, exposure registry | V17-00 |
| BA2 (V17-02) | Target, Lineage, and Outcome Policy | **DONE** | Source lineage, outcome resolution, validity/target separation (F01, F02, F10, F11 fixed) | V17-00, V17-01 |
| BA3 (V17-03) | Real Change Census and G1 | **DONE** | Transition census, label qualification, G1 evidence-existence gate PASSED | V17-02 |
| BA4 (V17-04 partial) | Unified View and State Arms (interface only) | PENDING | View isolation, three-arm definition, synthetic tests only | V17-00, V17-01 |
| BA-V | Batch A Verification | PENDING | Standing test suite, integration check | BA1-BA4 |

## Task Details

### BA0 (V17-00) - DONE

**Deliverables created:**
- `PLAN/TASK_CONTRACT_v17.json` - 12-dimension candidate scientific contract
- `PLAN/CLAIM_EVIDENCE_MATRIX_v17.md` - C1-C5 claims with X0-X5 experiments
- `PLAN/DECISIONS_v17.yaml` - D01-D12 inheritance/refinement analysis
- `PLAN/EXECUTION_STATUS_v17.md` - This file

**Acceptance criteria verified:**
- AC1: Every claim maps to at least one experiment (verified in matrix)
- AC2: AMD/COR existence not conflated with probability-must-change (explicit in contract)
- AC3: Downloader/archival distinguished from living system (explicit in contract)
- AC4: Output contract has no internally conflicting fields (verified orthogonal operations)

### BA1 (V17-01) - PENDING

**Scope:** Access boundary enforcement before real file discovery
**Files:** `scripts/build_episode_manifest_v16.py`, `scripts/build_lamp_categorical_registry_v16.py`, `src/disastertrace/revision_v1/outcome_wiring.py`
**Tests:** Synthetic temporary directories, symlink/alias handling, date boundary guards
**Addresses:** Codex F04, F07

### BA2 (V17-02) - DONE

**Scope:** Target and lineage semantics repair
**Files:** `src/disastertrace/revision_v1/contracts.py`, `manifest.py`, `ledger.py`, `episode_compiler.py`, `outcome_wiring.py`
**Tests:** Cross-window AMD, same-window different-source, mirror vs original publisher, late old version, CNL, same-minute conflict
**Addresses:** Codex F01, F02, F10, F11
**Commits:** 69c730e0c (V17-02: Fix four semantic bugs), 6889e2aa7 (V17-02 Gap remediation)

### BA3 (V17-03) - DONE

**Scope:** Real change census using V17-01 allow-list (Y-blind by design)
**Deliverables:** `PLAN/TRANSITION_CENSUS_v17.md`, `PLAN/LABEL_QUALIFICATION_v17.md`
**Decision:** Retain H15 - G1 evidence-existence gate PASSED
**Commit:** f72373d40 (V17-03: Transition census for G1 data qualification)
**Note:** G1 passage answers evidence-existence question only. The Codex positive-label statistical-power concern (OR1) is a separate question that remains OPEN and requires future outcome-side analysis.

### BA4 (V17-04 partial) - PENDING

**Scope:** Interface and synthetic test portion of V17-04
**Files:** `src/disastertrace/revision_v1/p1_harness.py`, `belief_commit.py`
**Tests:** View isolation, three-arm verification, commit validation
**Addresses:** Codex F03, F08, F09

### BA-V - PENDING

**Scope:** Batch A integration verification
**Tests:** Standing test suite run, combined regression check

## Gate Status

| Gate | Description | Status | Evidence |
|------|-------------|--------|----------|
| G0 | Problem and scope | **FROZEN_DEV** | V17-00 through V17-03 provide candidate contract with evidence-existence verified |
| G1 | Data qualification (evidence-existence) | **PASSED** | V17-03 census: 121,885 changes, 98% coverage, 4,264 process groups, 0% TAF-side dispute rate. NOTE: Codex positive-label statistical-power concern is separate and remains OPEN (see OR1). |
| G2 | Measurement qualification | NOT STARTED | Requires Batch B |
| G3 | Development evidence | NOT STARTED | Requires V17-07 |
| G4 | Living capability | NOT STARTED | Requires V17-09 |
| G5 | Confirmation readiness | NOT STARTED | Requires V17-10 |

## Open Risks

1. **Statistical power (REMAINS OPEN)**: The Codex audit's concern about 8.33% positive-label rate is NOT addressed by the V17-03 census. The census demonstrates abundant TAF-side evidence volume (121,885 changes) but is Y-blind by design and cannot measure positive-label rate. A future outcome-side (Y-permissioned) analysis is required before H15 paired-diagnostic results can be trusted. See TASK_CONTRACT_v17.json OR1_positive_label_statistical_power.
2. **LAMP completeness**: F06 shows truncated gzip streams; QL branch needed
3. **Ledger semantics (RESOLVED by V17-02)**: F01 cross-window AMD handling fixed
4. **Outcome ordering (RESOLVED by V17-02)**: F11 input order dependence fixed

## Next Steps

After BA0 completion:
1. BA1 (V17-01): Access boundary implementation
2. BA2 (V17-02): Lineage and outcome policy fixes
3. BA3 (V17-03): Real change census with G1 decision
4. BA4 (V17-04 partial): View and arm interface tests

---

*Last updated: 2026-09-21*
*This file will be updated by subsequent batch tasks*
