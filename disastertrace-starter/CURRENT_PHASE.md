# Current phase pointer: MM-4 atomic diagnostics complete and reviewed

All 40 actual Qwen3-VL responses are structurally valid, query complete and EOS.
Strict success: spatial 8/9, watch-list 3/9, privileged logic 9/12, metadata selection
7/10. All six map-present points are predicted inside; the sole outside is wrong.
Presence-only posthoc value controls match all spatial and watch predictions.
These are one-event development diagnostics, not a combined capability score.

Four disjoint one-H100 jobs all succeed and release. The retained STARTING-replica
accounting failure is resolved by submitting only the three never-submitted shards;
actual peak reserved/allocated concurrency is three. No request or worker is retried.
All 96 required functional test nodes and five resource regression tests pass.
All 40 real processor/token captures replay; 1,986 historical bindings are unchanged.
Both relocated and actual ZIP-extracted CPU reviews reproduce tasks, references,
independent controls and the raw-response report. Acceptance:
`860860f54e267cf0064a0b2b3fc22bc09a9fe07e2a04528ff8f7c76f88343e7f`.

Entry: [MM-4 actual results and review archive](README_MM4_ATOMIC_V1.md).
Next: [input representation and balanced spatial coverage](artifacts/multimodal_v1/mm4_atomic_20260909/NEXT_STEP_CN.md).
The 40/40 revision gate fails. MM-5A's proposed 80-request comparison has not run.
All MM-4 preparation, submission, worker, finalization and sealing claims are consumed.
Preserve its raw failures, old batches and all frozen code, captures and acceptances.

## Previous MM-3 V2 model validation

The fresh V2 run returned all 12 answers: structural parsing 12/12, EOS 12/12,
query-site coverage 10/12, strict correctness 0/12. ACP job pt-yc7yhd4r succeeds
on one H100. CPU reconstruction and actual processor/token replay pass.
Entry: [V2 actual results](README_MM3_CONTRACT_V2_LIVE.md).
Next: [atomic diagnostics and four-GPU scheduling](artifacts/multimodal_v1/mm3_contract_v2_live_20260909/NEXT_STEP_CN.md).
The V2 launch is consumed; preserve all raw results and never replace failures.

## Previous MM-3 V1 result and V2 preparation

The first Qwen3-VL-8B-Instruct run completed on one H100 on 2026-09-09.
All 12 generation opportunities returned with EOS; all 12 failed the required
state-object output structure. Actual image tensors, CPU/GPU processor checks
and no-generation multimodal forwards passed. The interface gate failed.
Entry: [MM-3 actual results](README_MM3_VLM_V1.md).
The [explicit output-contract V2 offline package](artifacts/multimodal_v1/mm3_contract_v2_offline_20260909/NEXT_STEP_CN.md)
preserves its zero-generation preparation record with unchanged public evidence
and references; its later model run lives in the separate V2 live batch. Do not relaunch the
consumed MM-3 worker, rewrite its failures, or reopen older phase windows.

## MM-0 through MM-2 offline complete

The 2026-09-09 multimodal seed is complete: 96 tests pass, one real Francine
development episode has six controlled delivery branches and 30 checkpoints,
and all seven program reports reconstruct in a relocated CPU environment.
Entry: [README_MULTIMODAL_V1.md](README_MULTIMODAL_V1.md).
Batch status: [MM implementation record](artifacts/multimodal_v1/mm0_2_20260909/IMPLEMENTATION_STATUS.md).
Next: [MM-3 VLM preflight](artifacts/multimodal_v1/mm0_2_20260909/NEXT_MM3_CN.md).
This batch has zero model calls/GPU jobs; program diagnostics are not VLM scores.
The old final GitHub publication remains a separately recorded handoff.

## Preserved P6-P14 closure

The original autonomous model window ended at 2026-09-09T02:05:16.104344+00:00,
starting at 2026-09-08T16:05:16.104344+00:00. All model collection is over.
Do not reset this window, reopen a consumed phase/worker claim or relaunch P14.
The user's later continuation covers CPU recovery, documentation and publication.

Current result entry: [RESULTS_20260909.md](../RESULTS_20260909.md).
Detailed Chinese review: [REVIEW_FOR_CHATGPT_PRO_P6_PLUS.md](REVIEW_FOR_CHATGPT_PRO_P6_PLUS.md).
Publication and reconstruction: [review package](../publication/autonomy_review_20260909/README.md).

## Six terminal model cases

All six LOCATION records and four comparisons in
`artifacts/autonomy_10h_v1/reviews_continuation_v2/FINAL_STATUS.json` pass.
Each condition has 2,412 planned slots, three methods, six development storms
and one repeat. Primary accuracy retains all missing/invalid outcomes.

| Case | Returned | Strict correct | Unattempted | Unknown | Collection |
| --- | ---: | ---: | ---: | ---: | --- |
| P11 Qwen3-8B | 2412 | 1000 | 0 | 0 | Complete |
| P11 DeepSeek-R1-Distill-Qwen-7B | 1604 | 3 | 808 | 0 | Context-stopped |
| P12 Qwen3-8B | 2412 | 1060 | 0 | 0 | Complete |
| P12 DeepSeek distill | 1994 | 9 | 418 | 0 | Context-stopped |
| P13 DeepSeek distill | 2064 | 6 | 348 | 0 | Context-stopped |
| P14 Qwen3-8B | 1628 | 952 | 780 | 4 | Deadline-stopped |

P14 collectors exit 124 at 02:05:00 UTC. Both ACP jobs are FAILED and released
at 02:05:04/02:05:06 UTC. Its audit passing does not change those states.
Execution: `69569f3dfb4fab2ddf387c16c47a87b9ae1093d9d8bc975872cf79a6210f3100`.
Report: `cfd6368dc983a2a0904a92623a69777e636164422d7db1cb2104adb79ba3e054`.
The zero-byte unpublished worker-1 intent is not an inferred dispatch. The four
worker-0 unknown outcomes have no replacement requests or fabricated answers.

## Final checks and persistent recovery

The final ACP snapshot at 02:42:53 UTC records 33 in-window jobs, all released,
maximum four reserved/running H100s. Reservation time is 31.035833 GPU hours;
allocation time is 30.865556 GPU hours. These are not utilization or billing.
`gpu_snapshots_01/final_accounting_01.json` builds and verifies unchanged.

`dispatch_deadlines_v3.json` builds/verifies all six cases with zero dispatches
outside their cutoff and no late raw returns. Its 23-test suite passes. Original
V1/V2 real-command failures and regression failures remain preserved: V1 lacked
atomic-intent residue support; V2 rejected normal parsed caches. V3 counts only
published records and does not change scientific capture/scoring code.

`pair_coverage_v1.json` builds/verifies four comparisons after nine tests. Qwen's
P12/P14 difference of -108 strict successes is +68 on common returns minus176
on P12-only returns. This selected subset is descriptive, not a causal adjustment.
`result_tables_v1` exports all six verified analyses and reconstructs every byte.

All four P11-P14 phase acceptances and archives exist. P11's unchanged v2
acceptance omits14 analysis/command files; its separate30-file addendum covers
them. Full P11 analysis closure requires the global supplement. P12-P14 use v3.
The earlier P12 QUEUEING/INIT observer failures and CPU-only continuation remain
in their original directories; exact finalization paths come from LOCATION files.

The first publication CPU processes and temporary restore roots were absent in
the continuing environment. `CPU_PUBLICATION_INTERRUPTION_02.json` records the
observation without guessing the cause or missing process exit codes.
`recover_cpu_publication_v2.py` completes P14 sealing, rebuilds no existing phase
archive, restores five archive groups and verifies four inventories. Its first
CPU report command fails before task import because the receipt is outside the
unchanged wrapper's isolation directory. `complete_cpu_reconstruction_v3.py`
reuses those successful steps, writes receipts inside each isolated copy and
immediately copies successful bytes to AFS. All failures stay preserved.

The receipt copier is `copy_reconstruction_receipts_v2.py`; the final closure is
`close_cpu_publication_v3.py`. The final CLOSE_GLOBAL_03 status passes at
2026-09-09 03:06:27 UTC and the completed supplement binds 572 files.
The earlier v2 failed attempt remains preserved. Do not run the original failed or
interrupted controllers again. Their source and command chains are evidence.
Final accepted CPU copies live in `artifacts/autonomy_10h_v1/publication_reconstruction_02`.
Publication receipts live outside the committed tree under
`../review-outputs/autonomy-publication-20260909/`.

## Frozen boundaries and next work

P6 remains1861/2160 strict; P7 is527/1542 with complete Qwen answers; P8 retains
422 JSON/text pairs (118 vs143 strict); P9 is1/1542 with986 returns and four
context stops; P10 is the accepted six-storm offline task. Their distinct tasks,
cohorts and repeats must not be pooled into a single capability score.

All accepted source, raw captures, execution identities, scores, failure records
and archives remain frozen. Root AGENTS/README/IMPLEMENTATION_STATUS/DECISIONS/
BLOCKERS also retain their accepted historical bytes. This pointer is mutable
navigation, outside the phase scientific inventories.

Next priorities are in `artifacts/autonomy_10h_v1/POST_WINDOW_PRIORITIES.md`:
trajectory-level failure isolation and unknown-outcome recovery, public output
representation bounds, storm-stage coverage, equal-budget comparisons and
independent model families, followed by a separately frozen heldout plan.
No paid API, training, heldout inference, human per-item Gold, LLM judge, model
retry or selective replacement occurs in this autonomous window or CPU recovery.

Private publication to `sisuolv/disastertrace-benchmark`, branch `next-phase-v1`,
remains authorized; default branch `main` and repository visibility stay as they
are. The unrelated local `.github/` directory is outside the publication.
Select the final commit containing this pointer and verify it against the local
FINAL_PUBLICATION_01 receipt; no hosted Actions success is implied.
