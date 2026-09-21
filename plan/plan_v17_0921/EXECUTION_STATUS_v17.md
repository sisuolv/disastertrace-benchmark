# DisasterTrace v17 Execution Status

Version: v17-20260921

## Batch A: Problem and Data Qualification

Target: Reach G1 (data qualification gate)

| Task ID | Task Name | Status | Description | Dependencies |
|---------|-----------|--------|-------------|--------------|
| BA0 (V17-00) | Candidate Contract and Claim Preparation | **DONE** | Candidate contract, claim-evidence matrix, decision table, execution status skeleton | None |
| BA1 (V17-01) | Access Boundary and Input Identity | PENDING | Allow-list paths, date guards, exposure registry | V17-00 |
| BA2 (V17-02) | Target, Lineage, and Outcome Policy | PENDING | Source lineage, outcome resolution, validity/target separation | V17-00, V17-01 |
| BA3 (V17-03) | Real Change Census and G1 | PENDING | Transition census, label qualification, development contract freeze | V17-02 |
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

### BA2 (V17-02) - PENDING

**Scope:** Target and lineage semantics repair
**Files:** `src/disastertrace/revision_v1/contracts.py`, `manifest.py`, `ledger.py`, `episode_compiler.py`, `outcome_wiring.py`
**Tests:** Cross-window AMD, same-window different-source, mirror vs original publisher, late old version, CNL, same-minute conflict
**Addresses:** Codex F01, F02, F10, F11

### BA3 (V17-03) - PENDING

**Scope:** Real change census using V17-01 allow-list
**Deliverables:** `PLAN/TRANSITION_CENSUS_v17.md`, `PLAN/LABEL_QUALIFICATION_v17.md`
**Decision:** Retain H15 / modify contract / enter QN

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
| G0 | Problem and scope | **CANDIDATE** | V17-00 deliverables provide candidate contract/claims; not frozen until V17-03 |
| G1 | Data qualification | NOT STARTED | Requires V17-03 census |
| G2 | Measurement qualification | NOT STARTED | Requires Batch B |
| G3 | Development evidence | NOT STARTED | Requires V17-07 |
| G4 | Living capability | NOT STARTED | Requires V17-09 |
| G5 | Confirmation readiness | NOT STARTED | Requires V17-10 |

## Open Risks

1. **Statistical power**: 8.33% positive rate may make falsification condition undecidable (see claim matrix)
2. **LAMP completeness**: F06 shows truncated gzip streams; QL branch needed
3. **Ledger semantics**: F01 shows cross-window AMD handling still broken
4. **Outcome ordering**: F11 shows input order changes Y

## Next Steps

After BA0 completion:
1. BA1 (V17-01): Access boundary implementation
2. BA2 (V17-02): Lineage and outcome policy fixes
3. BA3 (V17-03): Real change census with G1 decision
4. BA4 (V17-04 partial): View and arm interface tests

---

*Last updated: 2026-09-21*
*This file will be updated by subsequent batch tasks*
