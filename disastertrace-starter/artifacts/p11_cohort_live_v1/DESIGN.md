# Matched two-model expanded development evaluation

Fix this design before reading any expanded-cohort model scores. The complete P7
Qwen3 results were already read. P10 source admission and task counts are known;
its six storms and first six numbered advisories were selected before acquisition.
This is subsequent development, not untouched heldout confirmation.

Evaluate the complete P10 forecast_cohort execution: six storms,36 products,
144 target episodes,804 checkpoints. Use snapshot, structured_state and
answer_history, exactly inherited repeat0. Each model has2412 planned answers;
Qwen3-8B and DeepSeek-R1-Distill-Qwen-7B together have4824. No storm, target or
slot is selected using model success, errors, output length or runtime progress.

The prior frozen forecast contract, source evidence, automatic references,
public renderer, seed derivation, output schema and deterministic scoring are
unchanged. P10's separately validated loader handles its admitted source package.
All model histories come from that same model/target/method; program controls
never seed model histories. Cross-model later requests can differ through their
own histories. Seeds match source slots across models without implying identical
random draws across architectures or tokenizers.

Use the already pinned Qwen3-8B and DeepSeek-R1-Distill-Qwen-7B checkpoints with
their original verified adapters, templates and reasoning parsers. Common
settings are BF16,TP1,batch4,context32768,max8192 total output tokens including
reasoning,temp0.6,top_p0.95,top_k20,min_p0,repetition_penalty1,static shape grammar.
DeepSeek's card recommends avoiding system prompts; the fixed common system/user
contract is retained and disclosed. Its Qwen ancestry limits architectural
independence. There is no prompt tuning, extra probe, retry or selective repair.

Allocate two separate one-H100 replicas to each model, four at most across all
active or pending owned allocations. Balance whole targets by storm and then
worker load using only public schedule identity and length. Both models use
the same two-way assignment,1206 answers per replica. Each execution has fresh
phase,attempt,trajectory and launch identities and a canonical run root.

Use a single shared live deadline, at most four hours after freezing and never
later than2026-09-09T02:05:16.104344+00:00. The output reservation ceiling is
19,759,104 tokens per model,39,518,208 combined. Maximum live allocation is
eight H100-hours per model,sixteen combined; this excludes separately recorded
no-generation preflights. Count pending GPUs in capacity checks. No idle GPU
keepalive jobs. The controller waits for prior jobs to release and consumes one
submission claim per replica, including failed or uncertain submissions.

Implement the model-profile selection in a new cohort_live namespace. Reuse
the frozen per-model adapters without mutating their globals. Generalize the
P9 durable collector/auditor to two workers and the new fixed denominator.
Independently reconstruct full and interrupted journals; a missing worker or
invalid/truncated reply remains in its planned score denominator. Model-origin
and program-origin runs remain separate. Every prompt reserves the full output
budget; fail closed on excessive context without truncating evidence or history.

Before any model generation require actual installed-backend tests for both
profiles,source and checkpoint hash checks,three complete2412-slot diagnostics
per model,independent report verification,CPU relocation and one fresh actual
no-generation H100 preflight per profile. Freeze code,resources,tests,task and
CPU/preflight proof together. Preflights release immediately and may overlap
only spare capacity from earlier phases. Failure is retained and not retried as
a model run. CPU review after a completed or stopped model run is permitted.

Report planned/attempted/received/valid counts,all inherited scoring components,
per-storm and per-transition results,whole-target trajectory success,actual token
counts and allocation durations. Compare models on the same source slots,
with descriptive paired differences and storm-level sensitivity. These six
curated storms are the independent source groups;804 horizons/checkpoints are
not independent weather events. One repeat does not measure sampling stability.
P7/P9 old two-storm results remain a separate table.

No numerical weather prediction,global extreme-weather competence,operational
NHC validity,independent architecture effect or universal memory advantage is
established by this development comparison. Terminal-state revision coverage
remains absent in the expanded cohort. No heldout inference,paid API,training,
manual per-item Gold,LLM judge or third model is part of this design.
