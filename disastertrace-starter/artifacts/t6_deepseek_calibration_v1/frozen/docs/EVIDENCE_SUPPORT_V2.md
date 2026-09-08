# Restricted NHC evidence support policy v2

Policy ID: `nhc_equivalent_support_v2`. Index schema: `nhc_evidence_index_v2`.
Implementation: `src/disastertrace/automated/evidence_support.py`.

This deterministic evaluator supplements the frozen canonical-locator score.
It extracts a limited set of current-observation constructions from already
admitted NHC records. It is not a general natural-language entailment engine,
new source parser, or a guarantee that arbitrary adversarial prose is understood.
Original records, factual Gold, delivery schedules and historical scores remain
unchanged. No model calls, LLM judge or per-item human review are needed.

## Public API

```python
index = build_evidence_index(episodes)
result = validate_citation(
    episode,
    checkpoint_id,
    field,
    value,
    {"record_id": record_id, "line": one_based_line},
    index=index,
)
```

`EVIDENCE_POLICY_VERSION` identifies the policy. `build_evidence_index` returns
a JSON-serializable dictionary with `schema_version`, `policy_version`,
`policy_sha256` and `episodes`. The policy digest hashes the declarative policy
specification; a derived scoring package must independently bind the actual
implementation source hashes. `fingerprint(index)` is the complete index digest.

Each episode entry contains `episode_sha256` and `records`. The episode digest
binds all source records, metadata, canonical facts and release checkpoints.
Each record entry contains `raw_text_sha256` and `support_spans`. A supplied
index is compared with an independently regenerated entry before use, so changing
its spans or an episode's source/schedule cannot inject support. This deliberately
favors verification over caching speed. Index construction validates episodes and
rejects duplicate episode IDs. It does not write to any input object.

The result is `{valid: bool, reason: str, support_spans: list}`. Every eligible
span contains record ID, field, exact canonical value, unit, inclusive 1-based
line bounds, `citation_lines`, kind and verbatim source lines. The line bounds
retain the complete supporting sentence for inspection. `citation_lines` is
narrower: a line must contain part of the field phrase through its canonical
value and unit. A gust-only continuation or longitude-only line is not a wind
or latitude citation just because it is in the same paragraph.

## Gates and numeric semantics

Only `maximum_wind_mph`, `latitude_deg`, `longitude_deg` and
`minimum_pressure_mb` are supported. Unknown-status scoring belongs to the
separate scorer and is not accepted as a numeric citation operation.

The citation must identify an existing record of the episode's entity. That
record must be issued no later than the checkpoint, actually delivered by that
checkpoint, and latest by issue time among all delivered reports. Repeating an
old arrival never makes it current. A numeric value matching an old/future
report is insufficient. The locator must be an integer (not a boolean) inside
the record; the proposed value must be a finite number equal to the frozen
canonical value. There is no approximate answer tolerance or implicit unit
conversion. In particular, a separately rounded km/h value does not redefine
the mph answer. Coordinates preserve N/S/E/W as signed degrees.

## Accepted source grammar

Summary support uses the existing `field_evidence` location, independently
matching the canonical NHC summary grammar and unit/direction. It does not
search arbitrary same-valued numbers or expand source admission.

Body support requires exactly one `DISCUSSION AND OUTLOOK` section with its
separator. Scanning stops at the next upper-case section heading or `$$`.
Only the first sentence of each nonempty paragraph is eligible. Sentence
bounds are four lines and 600 characters; paragraph bounds are 24 lines and
1,800 characters. Decimal points are not sentence boundaries.

Accepted first-sentence families are:

- Maximum sustained winds `are [near]` or `have increased to [near]` a numeric
  mph value, optionally preceded by `Satellite imagery indicates that` and
  followed by the conventional km/h and higher-gust suffix.
- The `[estimated|latest]` minimum central pressure `is` a numeric mb value,
  optionally with the declared Air Force reconnaissance or NOAA Hurricane
  Hunter provenance phrase and conventional inches suffix.
- `At` the explicit local clock and parenthesized UTC clock, the center/eye
  of the named hurricane/tropical storm/tropical depression `was located`
  near latitude and longitude. The two recovered development instrument
  clauses are allowed. Named entity, UTC clock and supported local-zone
  conversion must agree with the admitted record. This accepts the publisher's
  grammatical past tense describing its current observation; arbitrary past
  observations are not admitted.

Generic wind and pressure subjects inherit the admitted report's storm scope.
Explicit conflicting cyclone names in the bounded paragraph reject support.
The first sentence must match a complete declared construction: forecasts,
negations, ranges, probability qualifiers, wrong units, station winds and gust
claims do not match it. Recognized body values must also equal canonical facts.

Following paragraph sentences are limited to declared forecast/evolution
openings: the same named storm's `is`/`will`/`could` statement, `On the forecast
track`, a directional turn forecast, or strengthening/weakening forecast.
Attribution, observation-reference, value/estimate qualifiers, repeated target
variables, reference pronouns and declared negative-context markers reject
the paragraph. Unknown suffix classes fail closed. This conservative context
filter is a limited extraction policy, not proof of arbitrary paragraph
semantics. Additional genres, dates, languages, paraphrases or contradictory
cross-paragraph prose need a new specified policy and regression coverage.

## Reasons and aggregation

Successful reasons are `supported_summary` and
`supported_body_observation`. Failure reasons include `unsupported_field`,
`invalid_value`, `invalid_citation`, `unknown_report`, `wrong_entity`,
`unknown_checkpoint`, `future_report`, `undelivered_report`, `stale_report`,
`locator_out_of_bounds`, `value_mismatch`, `invalid_episode`, `index_mismatch`
and `evaluator_unverifiable`.

`evaluator_unverifiable` means no eligible construction at that citation was
established. It must not automatically be counted or described as hallucination.
It can include a same-valued sentence outside the grammar or a field/value
combination that the source does not support. A known answer needs at least
one citation and every supplied citation must pass; aggregation and mixed
valid/invalid-citation tests are owned by the v2 scorer.

## Verification and scope

`tests/test_automated_evidence_support.py` includes labeled synthetic positives,
adversarial counterexamples, line-wrap/movement metamorphic tests, issue/delivery
gates, signed coordinates, exact-unit rules and index-tampering checks. It also
filters the frozen cohort to its three development storms before extracting
examples, checking all four canonical and body fields across nine reports.
The actual Ida advisory 011 line 88 supports the reported 105 mph; no storm,
number or line is special-cased in implementation. Heldout source outcomes
are not used to design or broaden this grammar.

Actual regression-first logs and commands are retained under
`artifacts/optimization_p0/validator_checks/`. Initial missing-module failure
and subsequent qualifier/context failures are preserved alongside the final
scoped passing run. New scores require their own provenance-bound package;
this validator never overwrites the old 49/50 score or claims model improvement.
