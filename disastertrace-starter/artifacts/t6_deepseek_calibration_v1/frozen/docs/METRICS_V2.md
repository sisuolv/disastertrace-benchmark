# Dynamic metrics v2

Implementation: `disastertrace.automated.scoring_v2.score_dynamic_v2(episodes,
traces)`. Result schema: `dynamic_score_v2`; scorer version:
`dynamic_score_v2.0`. This is an offline derived score. It does not change the
task schema, source parser, release schedule, model input methods or saved v1
results, and it does not perform inference.

## Validation, identity and units

The scorer first runs the existing `score_dynamic` validator, retaining its
exact request, method, accepted-answer history, state-carry, schema and attempt
checks. A missing trace is a failed expected checkpoint. An invalid, missing or
budget-exhausted response contributes no successful slot or action, even when a
previous accepted answer remains in the runtime carrier. V2 never repairs model
state from Gold. Mixed methods and malformed trace histories remain rejected.

Each result identifies the scorer version, evidence policy version and SHA-256
fingerprint of the complete deterministic evidence index. The index binds source
text, episodes, candidate support spans and the evidence policy. A derived
migration package must additionally bind the original build, raw responses,
traces and old/new implementation hashes; version strings alone do not attest
an experiment's integrity. Historical build manifests must not be rewritten to
bypass implementation checks.

The elementary observations are fields at checkpoints. `state_accuracy` includes
both known and unknown fields; `known_grounded_accuracy` excludes unknown fields.
For the first saved Ida trial, there are 50 field slots, comprising 32 known and
18 unknown slots. Its v1 strict grounding of 49/50 corresponds to 31/32 on known
fields. All rates retain integer `numerator` and `denominator`; zero denominators
produce JSON `null`, never zero or a perfect score.

Semantic equality is exactly `(status, value)` equality under the unchanged
decision schema and canonical values. V2 does not introduce numeric tolerance
or alternative-unit conversion. Known-answer coverage measures whether a known
answer was submitted, including incorrect known values. It is not correctness.

## Support policy

For a known field, grounded correctness requires the exact correct semantic
answer, at least one citation, and a valid result for every supplied citation.
The versioned support validator checks the latest report actually delivered,
entity/field/time applicability, locator and source-supported value/unit. It may
accept supported summary or bounded body spans. A valid citation cannot rescue
an additional stale, out-of-bounds or otherwise unverifiable citation.

Unknown answers retain the original requirement: `status=unknown`, `value=null`
and an empty evidence list. A correctly unknown slot counts toward overall
grounded state and unknown accuracy, but not known-only grounding.

Every scored slot reports `value_correct`, `grounded_correct`, a reason,
individual `citation_checks`, and opportunity flags. Slot reasons are
`supported`, `correct_unknown`, `status_mismatch`, `value_mismatch`,
`missing_citation`, `unverified_citation`, or the unsuccessful attempt status.
Each citation check preserves the citation, validator reason and support spans.
An `evaluator_unverifiable` citation reason describes a limitation of the
restricted grammar; it is not automatically evidence of hallucination. Per-slot
booleans retain the full denominator even when the validator cannot verify a
claim. Report these reasons alongside aggregate scores.

## Metrics and denominators

Let `G[t,f]` be the Gold semantic state of field `f` at checkpoint `t`. Gold uses
only reports released by that checkpoint. Let `V[t,f]` mean a schema-valid current
response with correct status/value, and `S[t,f]` mean that it also meets v2 support
requirements. Let `A[t,f]` be the last schema-valid accepted model field strictly
before checkpoint `t`; this may survive intervening failed attempts. A failed
current attempt has both `V=false` and `S=false`.

| Metric key | Numerator | Denominator |
| --- | --- | --- |
| `schema_success` | Current responses passing schema | All expected checkpoints |
| `state_accuracy` | `V` | All expected field slots |
| `grounded_state` | `S` | All expected field slots |
| `known_value_accuracy` | `V` where Gold is known | All Gold-known slots |
| `known_grounded_accuracy` | `S` where Gold is known | All Gold-known slots |
| `unknown_accuracy` | `V` where Gold is unknown | All Gold-unknown slots |
| `known_answer_coverage` | Current schema-valid known answers where Gold is known | All Gold-known slots |
| `action_accuracy` | Correct current research-rule actions | All expected checkpoints |
| `all_correct_checkpoints` | Correct action and all fields satisfy `S` | All expected checkpoints |
| `gold_transition_value_success` | `V` on semantic-change opportunities | Adjacent Gold pairs where `G[t,f] != G[t-1,f]` |
| `gold_transition_success` | `S` on semantic-change opportunities | Same fixed semantic-change opportunities |
| `gold_preservation` | `V` on semantic-stable opportunities | Adjacent Gold pairs where `G[t,f] == G[t-1,f]` |
| `gold_preservation_grounded` | `S` on semantic-stable opportunities | Same fixed semantic-stable opportunities |
| `provenance_refresh` | `S` on source-refresh opportunities | Semantic-stable, Gold-known adjacent pairs whose authoritative report changes |
| `self_error_recovery_value` | `V` on conditional recovery opportunities | Semantic-stable adjacent Gold pairs with an existing `A[t,f] != G[t-1,f]` |
| `self_error_recovery` | `S` on conditional recovery opportunities | Same conditional recovery opportunities |

The first checkpoint has no transition, preservation, refresh or recovery
opportunity. Every later field belongs to exactly one of fixed Gold transition
or fixed Gold preservation. Consequently their denominators sum to all adjacent
field pairs, independent of missing responses, carrier availability or prior
model correctness. In the saved two-branch Ida task there are 22 semantic-change
and 18 semantic-stable opportunities, totaling 40; two of the stable known
opportunities also require provenance refresh.

`gold_preservation` measures correctness when the reference is stable. Its
numerator can include correction of a prior model error; it does not assert that
the model literally preserved a previously correct answer. Recovery is therefore
reported separately and can overlap the preservation subset. Recovery requires a
semantic error in the previous accepted answer and excludes simultaneous Gold
changes, so it cannot be interpreted as an independent, method-invariant task
denominator. The same persisting error may create multiple opportunities across
failed attempts; every failed current attempt remains a failure. A prior
citation-only error is not a semantic self-error recovery opportunity.

Provenance refresh is also a subset of fixed semantic preservation. Its
denominator changes only with Gold, and a successful response must cite the new
authoritative report, even when its numeric value equals the old report. An old
105 mph observation cannot ground a new 105 mph observation solely because the
number is unchanged. Repeated delivery of the same report creates no refresh
opportunity. These overlapping diagnostics must not be summed into one score.

## Historical conditional metrics

The original `required_change_success` and `preservation` metrics are returned
unchanged under `v1_method_conditional_metrics`, outside the v2 main metric map.
They use v1 strict-locator support and denominators based on actual accepted prior
answers; their counts can differ between methods. This preserves the historical
result without relabeling it as a fixed-reference v2 comparison. For primary
comparisons use the explicit fixed Gold metrics and report conditional metrics
as diagnostics with their denominators.

## Events and paired branches

`counts` and `metrics` pool all expected checkpoints. `per_checkpoint` includes
the same additive counts for inspection. `per_event` groups every episode sharing
`group_id`, retaining event counts and rates. `event_macro` is the equal-weight
mean of defined event rates; it reports `n_events_defined` and `n_events_total`
because some metrics have no opportunities in an event. It does not replace a
null event rate with zero, and missing event traces still contribute failures
where that event's Gold has opportunities.

For an event with exactly one `:base` and one `:delay` episode,
`paired_branches` reports both branch metrics and delay-minus-base differences.
`paired_delay_minus_base` averages defined differences equally across paired
events and reports paired/defined/all-event counts. Unpaired inputs still score,
but have no paired result.

`paired_branches.both_correct` separately reports field and checkpoint rates
where both branches are correct at matching checkpoint IDs. Correctness always
uses each branch's own Gold. At the delayed checkpoint the correct answers may
differ; answer agreement is not the metric. Matching/base/delay checkpoint counts
make incomplete structural pairing visible. This diagnostic counts dependent
paired slots; it does not increase the number of independent events.

No confidence interval or causal memory claim is generated. The current methods
all receive cumulative delivered evidence. State-carry differences are not
isolated memory tests, and public-source contamination remains unmeasured. Rule
action accuracy is secondary because its threshold can mask field errors.

## Offline verification scope

`tests/test_automated_scoring_v2.py` uses clearly labeled synthetic records and
hand-computed trajectory counts. Regressions cover equivalent body citations,
missing/extra/stale citations, unchanged-value provenance refresh, unsuccessful
attempt denominators, recovery across invalid attempts, three methods, original
trace validation, event weighting and correctness across delayed branches.
Evidence grammar fixtures are tested separately. No fixture result is presented
as an LLM evaluation and no heldout outcome is needed to define these metrics.
