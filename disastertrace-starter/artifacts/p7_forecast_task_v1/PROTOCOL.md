# P7 native forecast-claim task v1

Status at specification: offline implementation; generation disabled. This is a
separate task over the twelve admitted NHC forecast advisories, not a change to
P1-P6. The evaluation target is understanding, updating and citing published
forecasts. Neither numerical forecast skill nor operational decisions are scored.

## Source and enumeration

Use only the sealed `nhc_forecast_source_v1` acquisition and review_v1. Recompute
both original parsers and every canonical line from those exact bytes. Admission
must match the saved review; a discrepancy stops this compiler. Do not reacquire,
repair individual rows or open any of the eight declared heldout storm IDs.

For each storm, sort the six admitted products by issued_at (ties are rejected).
The target catalogue is the sorted union of all explicit absolute forecast valid
times, including terminal rows. Every target defines one episode. Enumerate the
Cartesian product of that storm's targets and its six delivery checkpoints before
scoring. Include exactly those with valid_at strictly after the checkpoint's
forecast_reference_at; retain every exclusion and reason. There is no correctness
filter, revision-only selection, cap or template expansion.

The target catalogue is a declared design input derived from the full admitted
cohort. A query date can therefore precede its first explicit forecast. Its
existence in the catalogue is not an evidence claim. Requests reveal only that
query, the current clock and already delivered documents, never future product
text, source-version labels, values, transition labels or Gold. This deliberately
includes not_stated opportunities. It is not a study of surprise query arrivals.

Deliver one complete, line-numbered canonical PRE text at a time in natural issue
order. Preserve every source line, including gusts, qualifiers, observations,
radii, pressure and nuisance material. Do not provide derived forecast tables.
The controlled delivery step and elapsed hours are synthetic. A checkpoint's
forecast_reference_at equals that step's issuance time solely to define the
future-query cutoff; this does not establish historical availability. Keep
issued_at, center_at, valid_at, retrieved_at, delivery step and elapsed time
separate in provenance. available_at and initialization_at remain null.

## Answer and authority

One response jointly answers three exact fact keys: storm_id, absolute valid_at,
measurement_kind=forecast, variable and unit. Variables are latitude and longitude
in signed degrees (`deg`; north/east positive), and max_sustained_wind in `KT`.
Numeric equality is exact at published precision; no spatial/time interpolation,
unit conversion, pressure extrapolation or port-action rule is used.

The authority is the latest issued *visible product explicitly covering the exact
storm and valid time*. A newer product missing that row leaves the older explicit
claim authoritative. Delivery order itself is not authority. Equal issue times
for the same storm are unsupported and rejected before admission.

The output is exactly one JSON object with keys storm_id, valid_at,
measurement_kind, status, latitude, longitude, max_sustained_wind, citation.
Each measured field has exactly value and unit. UTC valid_at permits either Z or
+00:00 with second precision. status is numeric, DISSIPATED, ABSORBED or not_stated.
For numeric rows all three values are numbers; terminal and not_stated values are
null. not_stated has citation=null. Terminal rows cite their forecast line with
wind_line=null; they are not zero wind and do not terminate other valid times.
Numeric citation is {source_id, forecast_line, wind_line}; numbers refer to the
public L0001-style canonical line labels. The citation object binds the entire
three-field row. Gusts and POST-TROP/INLAND qualifiers remain source information
and are preserved in provenance; they are not additional answer fields in v1.

The structure-only schema checks shape, allowed status labels and primitive
types. It does not encode current source IDs, correct units, values or semantic
null consistency. A separate scorer retains wrong scope/unit/time/null/source
answers as semantic errors. Extra keys, duplicate JSON keys, booleans as numbers,
nonfinite numbers, fenced JSON and missing responses do not receive shape credit.

## Metrics

Report planned, received, shape-valid, exact-key, status, per-variable value/unit,
current-source, locator and complete correctness on the full planned denominator.
An invalid or missing response remains an incorrect opportunity. Raw byte spans
and line hashes are checked for every reference version, including older ones.

Literal support is distinct from current authority: a cited visible older row can
literally support an unchanged value while failing source-version correctness.
Check the target key and relevant source lines for literal support. For latitude
and longitude the forecast line is required; wind also requires the wind line.
Locator correctness checks the exact row's forecast/wind line pair independently
of the predicted numbers. Never grant literal support for a different valid time,
storm, unseen source, gust, observed wind or pressure.

Break down transition opportunities as first checkpoint, still_not_stated,
first_explicit, no_new_coverage, unchanged_wind, changed_wind and terminal_revision.
Wind categories do not imply coordinates or qualifiers were unchanged. Count
products, storms, unique targets, forecast rows, revision pairs and checkpoint
transitions separately. Targets and all products within a storm are dependent.

## Methods and offline schedule

All methods receive identical cumulative delivered source evidence and fresh
system/user messages. snapshot has no carrier; structured_state carries the
previous own shape-valid answer, or an explicit missing/invalid marker;
answer_history carries all prior own final texts and missing markers for that
target. No Gold correction, cross-target history or diagnostic-to-model history
is permitted. These methods differ in historical information and are not a pure
representation experiment.

The offline schedule has three methods and two independent repeat identities.
Seeds bind target, checkpoint, method and repeat. Entire target episodes are the
unit for any later worker assignment. Report each repeat and whole-episode
pass-in-both-repeats with variable episode lengths. Deterministic program repeats
exercise accounting; they do not estimate stochastic model reliability.

Use a legal public-text-only resolver plus wrong last-row, relative-lead,
newest-document-without-coverage, maximum-wind, current-pressure and first-version
policies. Invalid and missing controls exercise full denominators. Retain every
policy's agreements, including natural no-effect cases. These are software
diagnostics, never model results.

## Offline acceptance and later GPU work

Bind source closure (including package __init__ dependencies), input hashes,
schema, public requests, private references, schedule, tokenizer and context
settings. Use a common 32768-token context (within the pinned model's 40960 limit):
the full six-product Ida text alone already exceeds the old 16384 context when
8192 output tokens are reserved. Check the actual pinned Qwen3 tokenizer with
thinking enabled and the full 8192-token output reservation. Arbitrary future model carriers must be
checked again at runtime and fail closed without truncation or selective dropping.

Run fixed-answer and generated calendar/semantic tests, real-source diagnostics,
and CLI/import/reconstruction from an exact copied package on CPU, blocking the
original project, original weights and network before imports. Preserve failed
attempts. P6 acceptances must still verify. Generation remains disabled through
this milestone. A new live collector, audited text/token extraction, one-use
worker claims, a global resource budget and failure-prefix aggregation are needed
before the prospective matrix can run on at most four H100 TP=1 replicas.
