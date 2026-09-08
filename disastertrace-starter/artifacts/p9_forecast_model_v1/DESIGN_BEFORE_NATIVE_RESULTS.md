# Matched second-model native forecast comparison

This experiment follows the accepted P6/P7 next plan and the user's ten-hour
autonomous work window. Its task is fixed before native model scores are read.

Evaluate the verified official DeepSeek-R1-Distill-Qwen-7B checkpoint on the
unchanged P7 native forecast-understanding task. Preserve all46 target episodes,
257 checkpoints, three input methods and two repeat identities:1542 planned
answers. Use the exact public messages, Gold, scorer, history policy, opportunity
order, whole-target worker assignment and source slot seeds. New phase and attempt
identities prevent reuse of any original Qwen answer. Missing or invalid answers
stay in the denominator. No performance-based sample selection, repair or retry.

The comparison concerns the model under the common explicit task contract and
resource profile. It does not isolate model size, training, architecture or
tokenizer. DeepSeek-R1-Distill-Qwen-7B has Qwen2 architecture ancestry and a distinct
reasoning-distillation lineage; it is not an independent architecture. Native
model-specific chat templates necessarily produce different prompt token IDs and
lengths. The same system and user content is retained even though the DeepSeek
model card recommends avoiding a separate system prompt for its preferred usage.
This is a common-contract benchmark configuration, not a claim to optimal model
prompting or an official reproduction of model-card scores.

Use BF16 on four independent full H100 replicas, TP1, batch4, context32768 and
8192 total generated tokens including reasoning and final answer. Retain P7
temperature0.6, top_p0.95, top_k20, min_p0, repetition_penalty1, seed identities,
no prefix caching and no speculative decoding. Bound the actual installed
deepseek_r1 reasoning parser and XGrammar0.1.23 through vLLM0.10.2. The static
output guide permits shape-valid semantic mistakes. A generated closing-thought
token activates final-answer grammar; no semantic answer repair is allowed.

Budget:at most1542 generations and12632064 requested output tokens, zero retries,
four-hour live deadline capped by2026-09-09T02:05:16.104344Z. At most four H100s
may be allocated across all concurrent phases; release each preflight promptly.
No paid API, training, heldout inference, human per-item Gold or LLM judge.

Before generation:verify all official per-file weight/tokenizer/config/license
hashes, actual reasoning token IDs, raw token/text/EOS behavior, installed grammar,
complete program diagnostics, context bounds and CPU relocation. Run an actual
generation-disabled H100 preflight, release it, then freeze a fresh live package.
Do not modify the P7 task or replace its bound Qwen tokenizer; new model resources
belong in this separate execution namespace.

Report each model independently, then matched counts by method, storm, repeat,
transition and status, plus paired correct/wrong outcomes, tokens and timing.
Only two natural storms are represented; dependent checkpoints and repeat seeds
do not establish population significance or general extreme-weather competence.
