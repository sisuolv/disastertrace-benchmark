# P7 native forecast live execution

This phase follows the accepted P7 native-task NEXT_EXECUTION_PLAN. Preserve its
327-file offline acceptance and both P6 acceptances. Add only forecast_live source,
new tests, this bundle and new work directories. No paid API, training, heldout
inference, human per-item Gold, LLM judge or upstream reacquisition occurs.

## Matrix and resources

Qwen3-8B uses the existing pinned weights/environment. Evaluate the 257 native
future checkpoints under snapshot, structured_state and answer_history, twice:
1542 planned answers, no retry or repair, 12632064 maximum requested generated
tokens. Context32768, output8192 including reasoning, structure-only native JSON,
temperature0.6/top_p0.95/top_k20, deterministic per-slot seeds from P7.

Four independent one-full-H100/TP1 replicas receive390/390/384/378 answers. Whole
target episodes stay on a worker. Checkpoints are grouped into rounds; deterministic
hash ordering interleaves trajectories, with at most4 ready requests per batch.
The hash order depends only on trajectory IDs and a fixed label. GPU preflight
performs no generation and must finish/release before the four live jobs launch.
The live phase deadline is four hours from its freeze, including queue/load time.
The worker subprocess observes that common deadline and has a kill timeout.
Platform job states and allocated durations must also be recorded; no speedup is
claimed from a planned worker count.

## Required sequence

1. Native adapter, one-use claims, raw-first worker and independent global audit.
2. Fault, duplicate/unknown ID, ownership, carrier, missing denominator and exact
   EOS text regressions. Installed-vLLM/XGrammar checks with CUDA hidden.
3. Full four-worker actual-tokenizer diagnostics for latest_explicit, invalid_even
   and missing_even. Independently reconstruct every request and score; relocate
   the copied execution/runs and review with original paths/network blocked.
4. Freeze and submit one generation-disabled H100 load, verify terminal ACP state
   and evidence bindings. Source/settings cannot change between this and live.
5. Fresh live freeze binds CPU acceptance, preflight, ownership, caps and deadline.
   One phase submission and four worker submissions; unknown outcomes consume
   claims. Independent workers continue after one worker's submission failure.
6. Observe terminal jobs; audit all complete or stopped prefixes. Replay real
   final-token grammar masks, relocate CPU reports, reverify P6/P7 preservation,
   write findings and the next research plan. Preserve all failures and fixed
   denominators. Publishing is separate from collecting this bounded matrix.

## Interpretation

This measures understanding, updating and citing published NHC forecast claims,
not predicting weather. Its authority rule is latest visible explicit coverage
of an exact absolute valid time, a task convention. Complete advisories remain
visible to all methods; this is a comparison of closed-loop carriers, not a causal
measurement of internal memory. Two development storms and two sampling repeats
do not support general population claims. Controlled P6 scores stay in a separate
table from this native task.
