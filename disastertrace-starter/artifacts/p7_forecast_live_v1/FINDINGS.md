# P7 native forecast understanding: completed Qwen3-8B evaluation

All1542 planned model answers are captured and independently verified. All four
ACP jobs succeed and release their H100 allocations. There are no retries,
missing answers, unknown outcomes, length finishes or extraction errors. The
final observer completes at2026-09-08T17:23:38.167964Z.

Under the frozen task-defined latest-explicit-covering policy,527/1542 answers
are fully correct (34.18%). All1542 are shape-valid and use the correct storm,
absolute valid time, forecast measurement kind and units. This is a semantic
and citation difficulty result under the constrained-output track.

## Method and storm results

| Method | Fully correct /514 | Accuracy | Francine /256 | Ida /258 |
| --- | ---: | ---: | ---: | ---: |
| snapshot |187 |36.38% |115 |72 |
| structured_state |194 |37.74% |106 |88 |
| answer_history |146 |28.40% |85 |61 |

Structured state exceeds snapshot by only7 answers overall. Their order reverses
between storms: snapshot leads in Francine, while structured state leads in Ida.
The two repeats also vary. Structured state scores106/257 in repeat0 and88/257 in
repeat1; snapshot scores91 and96; answer history scores72 and74. These observations
do not establish a universally better memory policy.

Only19/276 method/repeat trajectories are correct at every checkpoint. Requiring
both repeats to be wholly correct gives1/46 snapshot target episodes,2/46
structured-state episodes and2/46 answer-history episodes. The46 targets are
dependent future horizons inside only two natural storms.

## Where errors occur

The disjoint primary error categories are764 value/status/unit errors,223 wrong
locators,23 wrong source versions and5 superseded sources that still support the
same values. Units are actually correct in every answer, so the764 category is
driven by values or statuses. The last three categories are251 answers whose
value/status/unit fields pass but whose citation requirements fail.

Overlapping field metrics give400 wrong statuses,548 failures of current-source
correctness and894 locator failures. These overlapping totals must not be added
to the disjoint error categories. Literal support also has a narrower eligible
meaning: not_stated answers have no positive source claim or literal citation.

| Transition | snapshot | structured_state | answer_history | Per-method denominator |
| --- | ---: | ---: | ---: | ---: |
| First checkpoint |65 |64 |61 |92 |
| Still not stated |37 |44 |41 |50 |
| First explicit forecast |16 |16 |8 |60 |
| New product omits target; retain older explicit coverage |44 |48 |29 |214 |
| Changed sustained-wind forecast |17 |13 |6 |46 |
| Unchanged sustained wind across covering versions |8 |9 |1 |48 |
| Revision involving terminal status |0 |0 |0 |4 |

The unchanged-wind category can still change coordinates, source identity and
locators. Four terminal-revision observations per method are too few to support
general claims. Natural alternating forecast grids make the no-new-coverage
category common; they are not fabricated source updates.

## Instrument and resource verification

The actual three-policy matrix uses the pinned Qwen3-8B checkpoint, BF16,
four full H100 replicas, TP1, batch4, context32768 and8192 total generated tokens
including reasoning. Every opportunity keeps its declared seed and target-owned
worker. The static XGrammar schema constrains shape and intentionally permits
wrong values, statuses, source names and citations.

The model generates2,341,943 tokens:2,118,026 reasoning,220,833 final-content,
1542 closing-thought delimiters and1542 terminal tokens. The mean is1518.77 tokens
per answer, median1126.5, maximum6679. Actual prompts range from2411 to16403
tokens, with mean7989.34; none is truncated. All final/EOS tokens pass independent
CPU XGrammar replay. Generation jobs consume3.9825 observed H100 allocation-hours;
this excludes separate no-generation preflights and CPU review.

Before generation,56 new core tests and9 installed-backend tests pass, alongside
64 accepted native-task regressions. Three full real-tokenizer program controls
retain1542 opportunities each: latest-explicit1542 correct, invalid-even780,
missing-even780. Program controls are software diagnostics, not model answers.

The completed model report reconstructs independently from the durable raw
journals and again in a copied CPU environment with original project/model paths,
network and child processes blocked. Exact generated token IDs, runtime text,
reasoning extraction, prior-answer histories, source ownership, task scoring and
denominators are checked. P6 historical acceptances and the P7 offline acceptance
remain separate and unchanged.

## Interpretation and next experiments

The task measures understanding, updating and citing already published forecast
claims. It does not evaluate physical weather prediction. The latest visible
product explicitly covering the exact target wins under a declared resolution
policy; retaining an older horizon after a newer product omits it is not a claim
about operational NHC forecast validity. Issue order is a controlled schedule;
historical public availability is unknown.

Ida and Francine are development storms. Both output grammar success and a low
semantic score are observations on this limited cohort. They do not establish
general extreme-weather competence, new-method novelty, or population-level
significance. The public latest-explicit resolver solves the task perfectly.

P8 is already preregistered before these scores were read:422 shared-prefix
JSON/text pairs,844 one-step answers, preserving every native mistake. Its
representation effect is conditional on the saved native prefixes and does not
remove token-length differences. P9 separately evaluates the verified local
DeepSeek-R1-Distill-Qwen-7B checkpoint on the same1542 native opportunities.
Broader development-source coverage is prepared in the distinct P10 catalogue.

## Evidence entry points

- Live execution: execution_live_01/execution.json
- Actual run: ../../work/p7-native-qwen3-v1
- Final status: finalization_01/FINAL_STATUS.json
- Complete report: finalization_01/global_report.json
- Token replay: finalization_01/token_replay.json
- Relocated CPU receipt: finalization_01/cpu_relocated/receipt.json
- Cross-tables, repeats, tokens and timing: analysis_01.json
- Execution ID: ab6567751121d4c146f6d9c00992720e99279c6ddd8cd135d304e4b524a3076b
- Report ID:5b74d8293acc932cd9ab8a975e705d327590a2c277b036d9f0c24ee36ac8f109
