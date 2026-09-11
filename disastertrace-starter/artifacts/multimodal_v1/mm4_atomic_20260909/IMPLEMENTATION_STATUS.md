# MM-4 implementation record

## Completed collection and CPU finalization, 2026-09-09

Forty independent atomic requests are frozen at execution SHA
`a1de0b80bcc1c58a0bf3552138361f829a0b2f700b1438868a404ff75d41cb67`.
Model snapshot and runtime are unchanged from MM-3 V2. New source is isolated in
`disastertrace.multimodal_atomic_v1`; prior modules and captures are unchanged.

All 40 responses are received, structurally valid, query complete and EOS. Strict
success is spatial 8/9, watch 3/9, privileged logic 9/12 and metadata selection 7/10.
The revision gate fails. Full task scores, failure denominators and outputs remain
unchanged; no retry or extra model request is performed.

## Actual command results

| Command/script | Exit | Result |
| --- | ---: | --- |
| First atomic pytest, `TESTS_01.xml` | 0 | 34 passed before adding audit regressions |
| New module lint first check / autofix | 1 | Retained style findings; fixed before freeze |
| Combined pytest, `TESTS_02.xml` | 0 | 56 passed, 40 skipped for missing optional CPU dependency |
| Existing model-env contract pytest, `TESTS_CONTRACT_03.xml` | 0 | 41 passed, covers all 40 skips and one overlap |
| Final pre-freeze module lint, `LINT_02.log` | 0 | All checks passed |
| `prepare_offline.py` | 0 | 40 automatic controls, 96 distinct passing test nodes, 1,986 old bindings verified |
| `freeze.py` | 0 | Actual CPU processor checks for 40 tasks; max input 1,945 tokens |
| `submit_jobs.py` | 1 | Worker 0 submitted; STARTING realized-replica check rejects next submission |
| Resource regression pytest, `RESOURCE_TESTS_02.xml` | 0 | 5 passed, including queued/starting zero realized replicas |
| `continue_submission_02.py` | 0 | Only never-submitted workers 1-3 submitted; window/settings/data unchanged |
| Four ACP workers | 0 / SUCCEEDED | Ten responses each, no platform or model retries |
| `replay_inputs.py` | 0 | 40 real input/token reconstructions, six image point checks |
| `finalize.py` | 0 | Raw report reconstruction, platform release, 1,986 old bindings and relocated CPU review |
| `posthoc_controls.py` | 0 | Explicitly posthoc presence-only value controls, zero generations |

The first 34 atomic tests are included in the final 39-node atomic suite; do not
sum repeated tests. The final functional set has 39 atomic + 16 capture + 41 contract
nodes = 96 unique nodes, plus five distinct submission-resource regression nodes.
No existing environment is upgraded. No paid API, heldout, training or human per-item
Gold is used. Existing Git worktree changes and old publication artifacts remain intact.

Four jobs succeed: pt-qrght4j8, pt-y9ksckak, pt-ggnyqb85 and pt-wfmzlx4m. Actual
maximum reserved/allocated H100 concurrency is three because worker 0 finishes
before the three-shard continuation. Reservation interval total is 0.209051 GPUh;
allocation interval total is 0.190440 GPUh, neither billing nor utilization.

Report SHA: `6b507810350b0c0ae11366c86d4daab23eacb820e0540b495b27794289516ae9`.
The relocated CPU review verifies 1,117 copied files and reproduces all public
tasks, references, independent controls and the raw-response report without Torch,
Transformers, network or original source/model paths (Python audit-hook scope).

Final ZIP creation, member hashes and actual archive-extracted CPU reconstruction
are recorded in `COMPLETED.json` and `ARCHIVE_REVIEW_RESULT.json` after sealing.
Do not rerun consumed preparation/submission/worker/finalization/sealing entries.
Next executable design: `NEXT_STEP_CN.md`, starting with an equal-information input
representation comparison and balanced automatic spatial coverage, before new live
scopes or complete revision trajectories. MM-5A's proposed 80 calls have not run.
