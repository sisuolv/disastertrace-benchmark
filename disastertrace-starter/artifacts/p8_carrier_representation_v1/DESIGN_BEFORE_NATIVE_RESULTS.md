# Paired representation control, specified before P7 native model results

The user's10-hour autonomous window permits continuation of the accepted next
plan. This document fixes the next control before observing P7 native model scores.
It is a separate experiment, not a change to any P7 task or live claim.

## Question and deterministic population

Does lossless serialization of the same saved previous answer affect a model's
next forecast update? JSON versus explicit path/value text changes representation
while preserving every value, status, unit, citation and mistake.

Use every P7 native structured_state source slot with at least one previous
checkpoint, for both source repeats. There are211 such base checkpoints and422
source-prefix queries, giving844 planned JSON/text branch answers. Include all
storms/targets/transitions defined by that rule. Never select by correctness,
confidence, disagreement, citation validity or error severity.

The initial P7 model run supplies the shared prefix. For each query, reconstruct
its entire original prior-answer prefix from independently audited raw captures.
Apply the frozen native structured_state rule: the immediately previous parsed
answer, or its explicit invalid/missing marker. Both branches receive that same
carrier. A missing captured prefix cannot be silently replaced with a program
answer; any ineligible/missing-prefix branch remains in the844-slot denominator.

## Two one-step branches

Both arms receive identical current query, complete cumulative numbered source
documents, task authority rule, output contract and common serialization legend.
Render the shared evidence context once, followed by a previous-answer section.
In that section, arm JSON renders canonical JSON; arm text renders a lossless
path/value encoding with JSON literals. The decoder must reconstruct exactly the
same canonical carrier, including numeric types, negative zero, nulls, arbitrary
strings and citations. No qualitative paraphrase, semantic correction, field
selection or action/value/citation simplification is allowed.

Each fork generates only the next answer. Fork answers do not feed later queries;
later forks still use the corresponding original P7 prefix. This estimates a
one-step representation effect conditional on those source trajectories. It is
not another autonomous trajectory comparison or a measurement of internal memory.
Equal information is not equal token length: publish both actual prompt lengths
and their paired differences. Do not pad to manufacture a length match.

All source slots are fixed before native scores are observed. Pair IDs depend on
the native source slot and this design version; each JSON/text pair shares a fresh
declared seed. All pairs of a target remain on one worker. Worker assignment uses
storm and slot counts only. Condition dispatch order is deterministic and balanced,
not selected by performance. Statistics remain descriptive across two storms;
report paired correct/correct, correct/wrong, wrong/correct and wrong/wrong counts,
plus storm and transition breakdowns. Do not treat422 dependent forks as422
independent natural disasters or attach population significance to them.

## Proposed execution bounds and gates

- Same pinned Qwen3-8B, native structure-only grammar and sampling parameters.
- At most844 generated answers, one per branch slot; no retries or repair.
- Context32768 and common8192 total generated-token cap including reasoning.
- Maximum requested generated tokens6914048; four independent TP1 H100s, batch4.
- Separate two-hour phase deadline, and never beyond the user's autonomous window.
- No overlap with four active P7 workers; always at most four H100s overall.
- No paid API, heldout, training, human per-item annotation or LLM judge.

Before any branch inference: finish the native audit; verify source-prefix origin,
round-trip equality, all-sample eligibility and token bounds; test the native
one-step collector/audit and missing-prefix accounting; freeze exact data, seeds,
settings, code and hardware evidence in fresh packages and one-use claims.
This design alone has no dispatch path and consumes no model call.

Second-model coverage follows as a separate preparation stream, with checkpoint
license/source/hash, tokenizer and hardware feasibility checked before a separately
bounded comparison. Prefer finishing this information-control question over adding
uninterpretable extra model calls. The10-hour window is an upper work limit, not a
requirement to keep otherwise idle GPUs allocated.
