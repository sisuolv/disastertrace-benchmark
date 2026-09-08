# P9: second-model native forecast evaluation

This phase evaluates DeepSeek-R1-Distill-Qwen-7B on the unchanged P7 native
forecast-understanding task:46 target episodes,257 checkpoints, three methods,
two repeats and1542 planned answers. New phase/attempt identities isolate all
captures from the historical Qwen run.

The checkpoint is acquired from the official deepseek-ai ModelScope namespace.
All requested files match the saved official per-file revisions, SHA256 digests
and sizes. The sealed resource package contains metadata, tokenizer, runtime and
backend source evidence; the7,615,616,512 BF16 parameters remain in the separate
local model directory. Both339-tensor headers and the weight index agree.

Implementation: src/disastertrace/forecast_model. The original source task and
its Qwen tokenizer remain frozen. The new execution has a separate resources
directory with the DeepSeek tokenizer and explicit deepseek_r1 reasoning backend.
Only its bound EOS ID151643 counts as a terminal token. Exact raw token/text
agreement, final-only shape grammar, failure retention and fixed denominators
are checked independently.

Design and registration:
artifacts/p9_forecast_model_v1/DESIGN_BEFORE_NATIVE_RESULTS.md and
PREREGISTRATION.json. Interpretation details are in INTERPRETATION_NOTES.md.
The model shares Qwen architectural ancestry. The common system contract is
retained despite the model card's recommendation to place instructions in the
user prompt; this is a common-contract evaluation, not optimized prompting.

Live bounds after offline acceptance and actual no-generation H100 preflight:
four TP1 full H100s, batch4, BF16, context32768, output8192 including reasoning,
at most1542 answers and12632064 requested output tokens. At most four hours,
never beyond2026-09-09T02:05:16.104344Z. No model/platform retries, paid API,
heldout inference, training, per-item human Gold or LLM judge.

Collection stops with986/1542 captured answers and556 unattempted slots. All four
workers hit the actual context guard and their ACP jobs remain FAILED/released;
no retries occur. Strict all-field correctness is1/1542 (0.0649%). There are90
length finishes,92 invalid final answers and9 reasoning-extraction errors. The
system explicitly requests signed coordinates in deg; only28 valid-shaped
answers use that required coordinate unit. No unit cleanup or rescoring is used.

Independent raw reconstruction,report verification,763305-token grammar replay
and isolated CPU relocation pass. Final audit status is in
artifacts/p9_forecast_model_v1/finalization_02/FINAL_STATUS.json and finishes at
2026-09-08T19:03:11.766523+00:00. The failed first observer remains unchanged in
finalization_01; it could not interpret transient ACP STARTING replica metadata.
The replacement observer changes monitoring only and never resubmits a worker.

Read artifacts/p9_forecast_model_v1/FINDINGS.md and analysis_01.json for coverage,
format,unit,semantic and stopped-context breakdowns. A passed completed acceptance
means that the stopped run is auditable; it does not mean all1542 answers arrived
or any of the four failed jobs succeeded. P11 expands development source coverage;
P12 separately studies bounded JSON formatting without repairing this run.
