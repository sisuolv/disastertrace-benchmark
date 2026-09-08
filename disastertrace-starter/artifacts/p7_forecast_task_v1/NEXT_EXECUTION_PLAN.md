# Next execution after the native-task offline acceptance

The task and denominators are now concrete. Preserve `execution_v1`; its false
generation flag is part of its identity and must not be toggled. Prior user
authorization for automatic GPU work persists, with a maximum of four H100s.
The following engineering leads to a fresh, separately bound live run.

## 1. Implement native collection and four-worker aggregation

Use a new `forecast_live` namespace and phase bundle. The controlled P6 runtime
assumes its own task, five-checkpoint episodes and action schema; do not dispatch
the new dataset through that runtime unchanged. Native target episodes have two
to six checkpoints. There are no controlled stress branches in this first native
matrix, and its scores belong in a separate table.

Implement a request-to-capture adapter using the frozen P7 public renderer, task
contract and scorer. At every checkpoint construct fresh messages from cumulative
delivered text and that trajectory's own prior model outputs. Keep invalid and
missing histories under the declared carrier rules. Never initialize model
history from the saved program diagnostics or automatic references.

Use raw-first exclusive captures, durable attempt journals and distinct phase,
execution, worker, trajectory and attempt identities. A submission with unknown
outcome consumes its claim. A worker failure, missing item, invalid output,
context overflow or lost worker remains in the original denominator; do not
repair it by repeating generation or silently moving it to another worker.

The preview is based only on episode lengths and storm identity. Its whole-target
assignment keeps every method, repeat and checkpoint together:

| Worker | Target episodes | Answers | Trajectories | Francine answers | Ida answers |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 12 | 390 | 72 | 198 | 192 |
| 1 | 12 | 390 | 72 | 192 | 198 |
| 2 | 11 | 384 | 66 | 180 | 204 |
| 3 | 11 | 378 | 66 | 198 | 180 |
| Total | 46 | 1542 | 276 | 768 | 774 |

The script `prepare_gpu_preview.py` and five tests check reconstruction, complete
disjoint coverage, missing/duplicate slots, episode splitting and accidental
dispatch flags. This remains a preview: its source slot IDs are provenance, not
new live attempt claims. Source load is approximate, not exactly balanced.

The live aggregator must independently reconstruct each worker's requests,
carriers, parsed answers and scores, then merge in frozen global slot order.
Test duplicate/unknown attempts, partial batches, changed ownership, stale
journals, interrupted writes, absent worker manifests and stopped prefixes. A
successful grammar must not be interpreted as semantic correctness.

## 2. Validate the local backend and freeze the actual resource budget

Keep the existing pinned Qwen3-8B checkpoint for the first native-task run; this
establishes a bridge to prior work without changing both model and task at once.
It is still a new task, not a matched repeat of P6. Reuse the installed environment
and weights; do not download or train another model in this step.

Proposed common bounds, to bind in a fresh live execution after hardware preflight:

| Quantity | Bound |
| --- | --- |
| Dataset / condition | P7 v1 / natural issue-order delivery of complete text |
| Methods / repeats | snapshot, structured_state, answer_history / two |
| Model answers | at most 1542, one attempt per planned slot, no retries |
| Context / total output reservation | 32768 / 8192 tokens including reasoning and final text |
| Maximum requested output tokens | 12632064 across all workers |
| Parallelism | at most four full H100s, four independent TP=1 replicas |
| Initial batch-cap candidate | four requests per replica; confirm before live freeze |
| Proposed live phase deadline | four hours; at most sixteen H100-hours while all four are allocated |
| Heldout / paid API / training / LLM judge | none |

Run a generation-disabled actual-H100 preflight with the specified context and
memory settings. Use the user's ACP guide at
`/mnt/afs/260010168/ACP-GPU-QUICKSTART.md`, preferably the already validated
`computing-cluster-01g-02` one-H100 spec `N6lS.Iu.I10.1.8c128g`. Confirm actual GPU,
driver, installed vLLM/XGrammar/Torch versions, checkpoint hashes, tokenizer,
schema support, reasoning delimiters, and output rendering. Release that preflight
allocation before any four-worker launch so the four-card ceiling remains true.

Reuse the P6 regression cases for EOS token IDs versus displayed text. Verify that
the installed backend respects its frozen stop policy without broad stripping of
whitespace or special tokens. Structure constraints must not contain answers,
current source IDs, correct line numbers or semantic consistency rules.

Every actual request still needs a tokenizer check including its full output
reservation. The current 2831 checks use program carriers and cannot prove bounds
for arbitrary future model-generated history. Overflow must stop dispatch and be
reported against the fixed matrix, never trigger evidence truncation.

After these checks, bind exact sampling parameters, seeds, job commands, resource
caps, closure and worker ownership. Submit each worker once, record every ACP ID,
and observe terminal states. Report phase elapsed time separately from summed
worker time and actual token usage. No fourfold speedup has yet been measured.

## 3. Complete the independent carrier representation control

Continue Section 2 of the accepted P6 research plan as a separate offline bundle:
lossless JSON and text renderers of the same deterministically selected saved
model decisions. Preserve all errors, values, statuses, citations and line numbers;
require round-trip equality and measure token differences. Do not select examples
by success or failure, and do not call equal information a token-length control.

A later paired inference experiment must share a saved prefix and current evidence
before branching, with independent subsequent histories. Its denominator and
estimand differ from autonomous native trajectories and need a separate freeze.

## 4. Expand model and source coverage after the first native audit

Match a second local model to the frozen task only after verifying the actual
checkpoint license, context, output backend and full resource accounting. Keep
free-output and constrained-output results distinct when backend support differs.

Prepare a deterministic larger development-source catalogue that adds independent
storms and natural revision diversity. Protect all eight declared heldout IDs,
including quarantined Matthew and plan-exposed Ian. Francine is development after
plan exposure; Ida was already development. Two storms cannot support population
claims about hurricane or general extreme-weather competence. Source diversity,
carrier controls and another model address different limitations.

The immediate executable work is Step 1's native collector/aggregator plus Step 2's
offline backend tests. No new permission round is needed for the user's already
authorized GPU scope; the new live freeze and one-use launch are required evidence.
