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

The user subsequently approves implementation of the integrated four-plan next
phase at `../plans/INTEGRATED_NEXT_PHASE_PLAN_V1.md`. T0-T3 calibration execution
and T4-T5 controlled task work are now offline-complete on `next-phase-v1`.
Use `README_NEXT_PHASE_V1.md` and `artifacts/next_phase_v1/README.md` as current
entries. The new contract-aware collector, capture, journal, ledger, independent
audit and report exist; their diagnostic rehearsal is not a real calibration.
P2 has automatic Gold, public oracle, offline scoring and unsent provider requests,
but its real collector/auditor remains subsequent work. Do not pass diagnostic
origins into a live scoreboard. The frozen execution's price snapshot requires
current applicability confirmation; its 270-attempt / USD 3 proposal remains
unlaunched. No old P1 scope or consumed continuation claim authorizes new requests.

On 2026-09-07 the user approves the immediately proposed T6 next step: one fresh
DeepSeek three-arm calibration, at most 270 requests / USD 3 conditional allowance.
The official price/settings documents are re-fetched and match the bound rates.
Actual authorization and frozen launch files are under
`artifacts/t6_deepseek_calibration_v1/`. The initial detached worker is launched;
use `README_T6_CALIBRATION_V1.md` and its read-only status command. Never relaunch
the initial worker or reset its experiment claim. The worker automatically audits
and reports on completion/stop. No extra probes/retries, old P1 restart, P2 model
calls, second model or heldout inference are authorized by this T6 scope.

T6 completes at 2026-09-07 09:36:28 UTC: 270 attempts, 270 responses, independent
audit passed, zero T6 unknown reserve, common cap selected at 8192. The launch and
270-call scope are now consumed. Use `artifacts/t6_deepseek_calibration_v1/FINDINGS.md`
and `P2_HANDOFF.json` for subsequent offline P2 collection/audit/scoring work.
The selected cap is not authorization for a separate P2 or heldout model matrix.

Distinguish implemented code, offline verification, real-data verification, human
review, and live model API verification. A skipped test is not a passed test.

If this repository already has additional user instructions, preserve and merge
this section rather than replacing them.
