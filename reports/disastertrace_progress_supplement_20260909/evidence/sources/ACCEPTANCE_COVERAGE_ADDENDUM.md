# P11 analysis evidence coverage addendum

The P11 completed acceptance remains
`a6b69e2cd071b4255a000d44f3195827c0d16da88a8f19690bc5d3c8a45ad714`.
Its 71,485 inventoried files, the original v2 sealer, and the original P11
evidence archive are preserved without replacement.

## Discovered omission

The final-supplement input-coverage probe failed when it reached
`cohort_reviews_01/p11_deepseek_r1.json`. That first inline probe did not save a
timestamped command log. The later `validation/p11_coverage_gap_01.json` records
this limitation, the observed error and a fresh enumeration of the actual gap;
it is not represented as a contemporaneous receipt for the earlier probe.

In `seal_cohort_evidence_v2.py`, the loop checking `analysis_id`, `report_id` and
`execution_id` reused the variable holding the case name. The later file glob
therefore searched for `execution_id*`, omitting both P11 analysis JSON files
and each analysis/verification command's intent, result and log. There are
exactly 14 omitted files. Their LOCATION records and validated identities were
included, but that did not bind the omitted bytes in the acceptance inventory.

The raw model captures, final reports, per-model audit receipts, CPU relocated
closures and scientific analysis source remain covered. This is an evidence
closure defect; no answer is replaced or rescored and no model result changes.

## Versioned repair and regression evidence

`seal_cohort_evidence_v3.py` retains distinct variables for the case and identity
field, includes each case's analysis and command files, and explicitly checks
that all seven required files per case are present in its final inventory.
Use this version for the still-unsealed P12-P14 phases.

The full-acceptance regression first runs against the preserved v2 source:
all four new tests fail, including the three cases in which changing an
analysis or command log went undetected. The corrected v3 run passes all
29 tests in the combined closure and inherited-location suites. These logs
are retained as `acceptance_closure_before_01` and `acceptance_closure_v3_01`.
The tests also reject missing and conflicting supplemental evidence.

`seal_p11_review_addendum.py` checks the original acceptance identity, both
original LOCATION records, both model-result identities and the four successful
command-chain receipts. It then binds the 14 omitted files in a separate
`p11_review_addendum_v1/COMPLETED_ACCEPTANCE.json`. It refuses to replace that
addendum or the original acceptance. Each command has an intent/result/log
triple: two actions per model give four commands and twelve command files.

The final autonomous supplement must bind this addendum and every dependency
used by the examples, prompt checks and result tables. Newly inventoried
supplemental files may satisfy a dependency; a differing hash for a file already
accepted by a phase is always an error. The full review package therefore
requires the P11 phase archive together with the supplemental evidence archive.
The original phase archive alone does not contain these 14 omitted files.

No model calls, GPU submissions, retry, deadline extension or scoring-rule
change is part of this repair.
