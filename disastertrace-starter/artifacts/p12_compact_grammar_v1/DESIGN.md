# Separate bounded-formatting study after observed whitespace degeneration

This development amendment is motivated by already observed P9 worker0 outputs.
It is fixed before any P12 generation. The earlier P7 and P8 results are known;
P11 expanded generation has not started at specification. Keep P9/P11 executions,
failures,source code,settings and all planned denominators unchanged.

P9's saved worker0 includes truncated final texts of333386 and333158 characters,
of which333304 and333088 are whitespace. Independent CPU reconstruction proves
that an unsubmitted answer_history prompt would contain24828 tokens plus the8192
output reservation,exceeding32768. The original worker stops after218 answers;
its remaining172 slots stay unattempted. The candidate next-batch reconstruction
is not an actual dispatched request. Evidence is in the P9 stopped_context and
whitespace_worker0 records. These are model-output/instrument observations,not
Gold changes or a population-level diagnosis of model reasoning.

## Intervention and fixed quantities

Change only the static constrained-output whitespace setting:
guided_decoding_disable_any_whitespace=True at engine setup and the matching
disable_any_whitespace=True in each request's guide. Compile the independent
CPU XGrammar replay with any_whitespace=False. Use the installed backend's
documented default JSON spacing grammar instead of arbitrary formatting padding.
This is a new output-format track; it is not a repair of already captured text.

Keep the P10 six-storm source task,all804 checkpoints,three methods,repeat0,
inherited seeds,SCHEMA,SYSTEM,public rendering,reference values,scoring,context32768
and max8192 output tokens unchanged. Both local checkpoints retain BF16,TP1,
batch4,temp0.6,top_p0.95,top_k20 and their native reasoning parsers/templates.
Strings,wrong units,wrong values,wrong source IDs and wrong citation locators
remain expressible. Do not insert source-specific values or answers in grammar.
Tests must establish that wrong semantic answers remain accepted and formatting
padding is rejected. The input protocol and previous-own-output history policy
remain unchanged; no output cleanup,carrier truncation or fallback is introduced.

Use a new compact_live source namespace with separately bound adapters and
generation origins. No mutation of frozen adapter globals is permitted. There
are2412 planned answers per model,4824 combined,two H100 replicas per model,four
maximum across active and pending jobs. Whole-target ownership remains1206 slots
per worker. Maximum requested output is19,759,104 tokens per model and39,518,208
combined. Both live executions have a common at-most4-hour deadline capped by
2026-09-09T02:05:16.104344+00:00. No retries,extra probes or partial-result refill.

Original independent trajectories still stop their worker on a context or backend
failure under the retained collector policy. This formatting intervention does
not solve failure isolation across otherwise independent trajectories. Preserve
that limitation and every unattempted slot. Do not claim this change guarantees
bounded string length,complete JSON output,successful reasoning or full coverage.

## Gates and comparisons

Before model generation require frozen source/resources/tests,same-task identity,
actual installed-backend checks for both profiles,full2412-slot latest-explicit,
invalid-even and missing-even controls per model,independent reconstruction,
copied CPU review,and one new no-generation H100 preflight per profile. Reuse
the pinned checkpoint resources; no download,training or paid API is involved.
Preflights use spare capacity only. The combined live controller waits for P11
and all preflights to release their allocations. If insufficient time remains,
retain the offline package and report P12 as not executed.

Report actual response coverage,shape/length/extraction failures,whitespace and
token use,and inherited semantic/citation scores on the full fixed denominator.
Compare P11 and P12 on the same source slots,by model,method and storm. Later
histories differ through each run's own generations; these are full trajectory
track comparisons,not shared-prefix causal estimates. Report single-repeat
whole-target success,not the inherited scorer's misleading both_repeats label.

This is failure-driven development on a curated cohort with six dependent storm
source groups and one sampling repeat. No heldout confirmation,universal decoder
superiority,numerical weather skill or extreme-weather generalization follows.
Keep raw P11 and P12 tables separate; neither overwrites the other. All prior
parser/monitor/test failures and finalization evidence remain available for review.
