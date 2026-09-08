# P9: audited stopped DeepSeek native forecast run

DeepSeek-R1-Distill-Qwen-7B returns986 of1542 planned answers. Strict all-field
correctness is1/1542 (0.0649%). Response coverage is63.94%; conditional correctness
among returned answers is1/986 (0.1014%). The planned denominator is primary.
These are common-contract results on two development storms,not an optimized
DeepSeek deployment or a measurement of physical weather forecasting.

All four workers stop on the unchanged context-reservation guard. Their ACP jobs
remain FAILED and all allocations are released. Final independent audit passes
at2026-09-08T19:03:11.766523+00:00. Successful audit verifies the retained stopped
prefixes; it must not be described as successful full collection.

## Coverage and strict scoring

| Method | Planned | Returned | Shape-valid | Fully correct |
| --- | ---: | ---: | ---: | ---: |
| snapshot |514 |329 |316 |0 |
| structured_state |514 |330 |295 |1 |
| answer_history |514 |327 |283 |0 |
| Total |1542 |986 |894 |1 |

The disjoint categories are556 missing responses,92 invalid final JSON shapes,
242 wrong target keys,650 wrong value/status/unit answers,one wrong source version
and one fully correct answer. No method/repeat trajectory is wholly correct.
Missing responses include unrelated future trajectories that the whole-worker
failure policy never reaches; they are not986 observed semantic mistakes.

There are90 length finishes and896 stop finishes. Every length-finished answer
has an invalid final shape;two stop-finished answers have empty final text.
Nine outputs have no usable reasoning-to-final extraction. These counts overlap.
Independent final-token grammar replay sees977 final phases and9 reasoning-only
phases,with zero grammar-mask violations across763305 constrained tokens. A legal
unfinished token prefix does not imply a complete valid JSON answer at the cap.

## Protocol and value failures

The common system message explicitly requests signed latitude/longitude in deg,
maximum sustained wind in KT,and the requested absolute UTC valid time. Among894
shape-valid outputs,only28 use deg for each coordinate. Latitude units include
N in579 answers and degrees in178. Longitude units include W in451,E in140 and
degrees in178. Wind units are KT in880. No posthoc unit normalization is applied.
Some directional unit outputs also carry incorrect signs or values;the weak
strict score cannot be attributed solely to synonymous unit labels.

Overlapping full-denominator field metrics include871 correct storm keys,
677 correct time keys,521 correct statuses,141 correct latitude values,93 correct
longitude values and169 correct wind values. Complete target-key agreement is652.
Only267 answers cite the currently required source and138 satisfy the locator
metric. These are separate partial-credit diagnostics,not additional successes.

The corresponding P7 Qwen3 run returns1542/1542 and scores527/1542 under the same
native task. The checkpoints share architectural ancestry;native templates,
tokenizers and reasoning parsers differ. DeepSeek's model card recommends avoiding
a system prompt,whereas this experiment retains the common explicit system
contract. The comparison is conditional on that protocol and is not an
architecture-independent ranking or a best-prompt comparison.

## Context failures and whitespace

| Worker | Returned | Unattempted | Next unsubmitted history prompt tokens | Plus8192 reservation |
| --- | ---: | ---: | ---: | ---: |
|0 |218 |172 |24828 |33020 |
|1 |254 |136 |30146 |38338 |
|2 |234 |150 |51894 |60086 |
|3 |280 |98 |24887 |33079 |

Each independently reconstructed next batch contains one answer_history prompt
over the32768 context limit. The other three requests in each batch fit,but the
retained collector stops the whole worker. The12 fitting next-batch requests and
all remaining future slots stay unattempted;none is retried or selectively filled.
These reconstructed next batches are projections from saved histories,not actual
model requests. Each stopped_context_worker record says this explicitly.

Saved final text totals3551198 characters,including2891318 whitespace characters.
This simple count includes whitespace inside strings. Some individual outputs
exceed333000 characters while staying within8192 generated tokens because the
tokenizer has large-whitespace tokens. Histories preserve the actual own outputs;
no cleanup,truncation or fallback is introduced. The earlier diagnostic tokenizer
checks used finite program histories and cannot certify all possible model-owned
histories. The actual engine limit is32768;tokenizer metadata warnings mentioning
16384 do not change the recorded engine setting.

The later P12 development amendment changes only static JSON whitespace freedom,
uses a distinct source namespace and fresh execution identities,and retains this
entire run. It does not fix arbitrary string length or isolate failed trajectories.
It is failure-driven development,not heldout confirmation.

## Resources and verification

The986 actual answers contain1550100 generated tokens:785818 reasoning,762411
final content,977 closing-thought delimiters and894 terminal tokens. Generation
allocations consume2.35556 H100-hours,excluding no-generation preflights and CPU
review. All original attempts use BF16,TP1,batch4,context32768 and output8192.
No paid API,training,heldout inference,human Gold or LLM judge is used.

The global report is rebuilt from durable raw journals and verified again.
Exact token IDs and text,prior-answer histories,task scores,fixed denominators
and ACP provenance are checked. Independent XGrammar replay and a relocated CPU
review with original project/model paths,network and child processes blocked pass.
The original failed observer remains in finalization_01;the replacement in
finalization_02 accepts transient zero-running-replica metadata only after checking
the immutable one-H100 request and uses unchanged strict terminal validation.

Evidence: finalization_02/global_report.json,finalization_02/token_replay.json,
finalization_02/cpu_relocated/receipt.json,analysis_01.json and all four
stopped_context_worker*_01.json files. The analysis command supports --verify.
Report ID:4c8e7452be94cffa19615526f0dc6552e0578d85345993c112ff01eadae8bb5c.

Task authority remains latest visible issued product explicitly covering the
exact storm/absolute time. A newer noncovering product does not erase earlier
coverage under this declared policy. This is not a claim of operational forecast
validity. Public availability and initialization time remain unknown. Ida and
Francine are development groups;no population significance or general
extreme-weather competence follows from the observed counts.
