# DisasterTrace v9 review bundle — 6f71c879

Start with CODEX_NEXT_PLAN_CN.md and CODEX_START_PROMPT_CN.txt.

## What was actually run
26 offline scenarios against five full Git-blob-verified source files. There are
20 positive/protective controls, four scenarios reproducing two issue classes,
and two diagnostic/design observations. Passing a counterexample assertion means
the boundary was reproduced, not that the production system passed acceptance.

The supplied verified_sources directory contains only five small source snapshots,
not the repository or its datasets. All hashes refer to commit
6f71c8799ff69439a18f645e63b8c966ca21eec4.

## Reproduce locally without network/model calls
Run using a NEW output filename:

```bash
python3 review_checks.py --source-dir verified_sources --output review_results_local.json
python3 check_audit_completeness.py --source verified_sources/analyze_temperature_fullcalendar.py --output completeness_local.json
```

To use your full checkout instead:

```bash
python3 review_checks.py --repo /path/to/disastertrace-benchmark --output review_results_checkout.json
python3 check_audit_completeness.py --repo /path/to/disastertrace-benchmark --output completeness_checkout.json
```

The tests reject changed source hashes. After applying fixes, port these checks
into normal regression tests and reverse the relevant undesirable-behavior
expectations; do not keep requiring a fixed implementation to reproduce the bug.

HTTP and credentials are fake; spool read/publish and lifecycle ledger/clock are
explicit test doubles. ApiBudget uses actual local files and fcntl, not AFS.
The temperature auditor runs on synthetic 24-month file trees, not the user's
192 original trajectories. No launcher, API call, GPU, download or live collector
is run. No user repository content was edited during this review.

## Evidence limitations
The private GitHub text connector was readable, but container download of the
full review ZIP failed with DNS resolution error. Full 616-test suite, full E02
captures, all F journals/checkpoints and all raw scientific arrays were not rerun.
Read REVIEW_SCOPE.json before interpreting findings.

## File index
- CODEX_NEXT_PLAN_CN.md: detailed staged implementation plan.
- CODEX_START_PROMPT_CN.txt: copyable entry instruction.
- FINDINGS.json: confirmed boundaries vs attribution/control requirements.
- WORK_PACKAGES.json: dependencies and execution gates.
- source_verification.json: exact source hashes.
- review_results.json, audit_completeness_results.json: actual test observations.
- review_checks.py, check_audit_completeness.py: reproducible tests.
- verified_sources/: small exact reviewed source snapshots.
- ARTIFACT_MANIFEST.json: package file integrity.

Original files/results, model settings, consumed launchers and the pause state
must remain preserved. New costly experiments need new, explicit authorization.
