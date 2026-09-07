# DisasterTrace repository instructions

Current user scope: follow ../INTEGRATED_BENCHMARK_PLAN.md v0.3. The user requested
completion of all independent preparation before actual model API testing.
The current first-pilot package includes frozen NHC event splits, three declared
input methods, independent data/collection audit, safe resume and offline preflight.
No new per-item human annotation or expert review is required.
The packaged historical plan applies only where it is consistent with this scope.

Read `DISASTERTRACE_CODEX_PLAN.md`, `IMPLEMENTATION_STATUS.md`, `DECISIONS.md`, and
`BLOCKERS.md` before editing. Create the last three if they do not exist.

The default execution target is M1: a tested offline end-to-end pipeline.
Implement incrementally on the supplied starter; do not rewrite the repository.
Preserve the user's existing changes. Do not push, publish data, or delete history.

Keep Gold and future evidence out of model requests and model-accessible tools.
Use fresh messages for every checkpoint and pass only the declared carrier.
Do not conflate issue time, effective time, and proved public availability.
Never invent source records, human reviews, model responses, or successful tests.

Add regression tests for the known scorer/runtime defects before fixing them.
Run offline tests first. The user selected DeepSeek and authorized a bounded
trial, completed as one SDK probe plus ten Ida/structured_state requests. Larger
trials still need their model/method scope and budget fixed. Do not infer a paid
provider or price from placeholder examples. Training is disabled.
The user subsequently approved P1: one fresh 90-request DeepSeek development
comparison (three methods, three storms, one repeat). Its frozen protocol is
`artifacts/p1_deepseek_development/PROTOCOL.md`; use the shared USD 1 conditional
reservation guard, no retries, no old-answer reuse and no heldout requests.
Freeze the experiment and verify the external runner before starting this batch.
After the machine restart, the user explicitly approved the separate frozen
background-continuation amendment: USD 1.5 cumulative conditional allowance,
one retry of unresolved original attempt 79, and at most 12 additional / 91
cumulative attempts. Retain all 78 received answers, including invalid answers.
Use `artifacts/p1_deepseek_development/background_resume/prepared/amendment.json`
and its actual `background_resume/authorization.json` record. Keep the original
interrupted experiment and its pending reservation unchanged; report the
continuation separately with the unresolved original charge still unknown.
This amended batch completed on 2026-09-06 with 12 new requests and 90 received
benchmark responses across 91 cumulative attempts. The one-use launch is consumed;
do not restart it or infer authorization for further model calls from this batch.
Record actual commands, exit codes, results, blockers, and the next executable task
in `IMPLEMENTATION_STATUS.md` at every task boundary.

The user then approves the next offline output-contract and calibration-design
package. `README_CALIBRATION_V1.md` is the current entry. Keep legacy requests,
source/answer parsers, scorers and all P1 captures unchanged. The new explicit
contract and offline preparation do not authorize API calls. The proposed fresh
270-request, three-arm development calibration and USD 3 conditional allowance
are recorded in `docs/CALIBRATION_PROTOCOL_V1.md`, with no live launcher yet.
Before later live work, implement and test contract-aware collection, auditing,
durable scheduling and budget accounting. Never feed diagnostic answers into
live history or present the legacy-instruction scoring projection as actual
model exposure. Keep the seven heldout storms outside calibration inference.

Distinguish implemented code, offline verification, real-data verification, human
review, and live model API verification. A skipped test is not a passed test.

If this repository already has additional user instructions, preserve and merge
this section rather than replacing them.
