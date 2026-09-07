# Benchmark optimization roadmap after the first live trial

Date: 2026-09-06. Status: proposed work, not an implemented scoring or dataset
release. This supplements the v0.3 integrated research plan. No additional model
calls, scorer changes, source admission changes or historical score edits are
part of preparing this document.

Execution update, 2026-09-06: P0 and the P1 metric definitions/implementation are
now complete in a separate work package; see `README_SCORING_V2.md`. Archived
Ida responses have versioned v1/v2 scores with zero new model calls. The broader
method matrix and P2-P5 remain proposed; the roadmap text below records the
original sequence and acceptance goals.

## Starting evidence and priorities

The pipeline has 483 passing tests and one real DeepSeek/Ida/structured_state
trial: ten checkpoints, 50/50 state values/statuses, 49/50 strict grounding and
10/10 rule actions. The grounding deduction is an equivalent source citation
rejected by a single-location reference. It is a measurement limitation, not a
demonstrated false weather claim. One event and one method cannot establish that
the whole benchmark is saturated or that methods are equivalent.

The cohort contains ten admitted storms, three development and seven heldout,
with 100 checkpoints. Those are ten independent event groups, not 100 independent
weather samples. Every current method receives cumulative delivered evidence.
The first priority is valid measurement, followed by development calibration,
task coverage, then broader generalization and model comparisons.

Proposed research questions:

1. Can LLMs maintain source-supported current facts under delayed, repeated,
   partial and explicitly superseded weather evidence?
2. Under a fixed evidence view, how do actual prior answers affect correctness,
   error propagation, recovery and cost?
3. Do these results persist across independent events and, later, independently
   validated weather domains and task templates?

## P0: evidence scoring v2 and versioned offline rescoring

Keep the current factual Gold, parser, episodes, schedule, input messages and
answer schema frozen. Add a separately versioned deterministic evidence-support
validator; do not hard-code Ida, advisory 011, line 88 or the number 105.

An accepted citation must support the same field, entity, applicable observation
time and canonical value/unit as the target fact. In the existing protocol it
must come from the latest issued report actually delivered at the checkpoint.
An older or different storm's report does not become valid merely because the
number happens to match. Future and undelivered records remain inaccessible.

Initial scope is the four existing numerical weather fields and explicit NHC
summary/body observation constructions. Use bounded sentence/section context to
distinguish sustained wind from gusts or movement speed, observations from
forecasts or past values, and affirmative claims from negations. Coordinates
must preserve N/S/E/W direction and the storm-center subject. Clearly declared
NHC approximate reporting such as "near 105 mph" may support the reported 105;
general intervals, probabilities and open-ended paraphrases need their own rules.

Return a list of eligible support spans with reason codes. Keep at least one
required supporting citation for known facts and require every supplied citation
to be valid, so adding one correct citation cannot hide unrelated citations.
Unsupported grammar means the evaluator cannot verify the citation; report that
reason separately from a proven wrong value, wrong source or stale observation.

Start with exact canonical numeric matching. Do not import source dual-unit
rounding tolerances as answer tolerances: 165 km/h does not exactly convert to
105 mph. Any later conversion task must specify input precision, rounding and
tolerance before evaluation. The factual parser's current unit checks stay frozen.

Regression contract:

- Positive examples: accepted summary and body repetitions, several development
  source excerpts, different entities/numbers/coordinates and explicit line wraps.
- Negative examples: gusts, movement speed, forecast/past/negated statements,
  wrong units/directions, wrong storm/report, stale/future/undelivered sources,
  out-of-bounds locators, and a correct citation mixed with an invalid one.
- Metamorphic checks: moving text and its locator together preserves support;
  changing the variable, source, time qualifier, polarity or unit invalidates it.
  Repeating an old arrival does not change the latest applicable report.
- Use explicitly labeled synthetic test fixtures for precise negative cases;
  do not modify the official raw records or call fixtures official observations.

Historical replay needs an explicit migration path: current build/run checks
intentionally reject changed implementation identities. Verify the old run and
collection using their saved implementation, then produce a new derived score
package binding original build/request/response/trace hashes to the new scorer
and evidence-index hashes. Never rewrite the old manifest to bypass validation.

Acceptance: v1 still reproduces 49/50; v2 produces its own score and a per-field
reasoned difference report from the same ten unchanged responses, with zero new
provider requests. Schema, state-value, action and opportunity counts stay fixed;
only evidence-dependent results may change. Improving the evaluator's treatment
of an answer is not an improvement in the model's performance.

Proposed deliverables: evidence-support specification, standalone validator,
positive/negative fixtures, migration manifest, and v1/v2 comparison report.

## P1: clearer metrics and the smallest useful development comparison

Separate known-only grounded correctness, unknown correctness and overall state
accuracy. The current trial's 49/50 overall grounding includes 18 unknown slots;
strict grounding on known slots alone is 31/32. Answer coverage measures whether
the model answers known, not whether its answer is correct. Report counts beside
every rate and keep malformed/missing/budget-exhausted attempts in denominators.

For transitions, add a fixed-reference-opportunity view for comparisons. Current
required-change and preservation opportunities depend on the model's own prior
state. Retain those as trajectory diagnostics, but separately report changes
required by Gold, recovery from prior model errors, semantic preservation, and
refreshing provenance when a newer report repeats a value. Do not rank methods
using conditional percentages without their different denominators.

Keep rule-action accuracy secondary. The existing last-arrival diagnostic scores
70/70 heldout actions despite only 294/350 grounded fields. Report base/delay
paired success and per-event differences, not consistency alone. Freeze any new
metric definitions as a versioned evaluation change before using them for ranking.

After P0, use the existing 30 development checkpoints with the same English
prompt/schema and explicit DeepSeek thinking settings across all three methods:

| Experiment | Complete requests at one repeat |
| --- | ---: |
| DeepSeek x 3 methods x 30 development checkpoints | 90 |
| Add a second model family with the same coverage | +90 |
| Both families, all development cells | 180 |
| Both families, all development cells, R repeats | 180R |

Use one repeat for initial calibration, then predeclare a common repeat count
(for example two or three) for the comparison that follows. Do not repeat only
failing cells. Independent repeats must call the model again, not reuse cached
answers. Prior ten-response data is suitable for offline rescoring; subtract it
from a new request budget only if a separately declared reuse policy verifies
identical inputs, settings, version metadata and repeat identity. Otherwise
budget the complete matrix and label earlier results as the original smoke run.

Output per-event accuracy, failure reasons, request/input/output sizes, actual
reported usage and latency. An alias returned by an API is not proof of an
immutable underlying model version; preserve the returned ID, request time and
available provider version metadata. Keep reasoning configuration fixed for the
first method comparison; reasoning on/off is a later separate factor.

Acceptance: every planned cell is either completed or explicitly failed, errors
are retained, no heldout model outcomes are used to tune the protocol, and cost
and quality are reported together. A second family requires a selected service;
its absence does not block the one-model development experiment.

## P2: controlled tasks that cover missing capabilities

Retain the real, unchanged NHC replay as one track. Build a separate controlled
track from explicit structured records and deterministic rules. Preserve source
values when directly inherited; label generated facts, edits and delivery times
as controlled/generated rather than official historical corrections.

Use a public fact key such as (entity, variable, valid window), plus explicit
issue/delivery times and revision relations. Reference compilation and runtime
must agree on declared semantics but have independently tested implementations.
Do not let the generator alone validate its own output. Include exact fixtures,
metamorphic relations and adversarial controls that isolate each failure mode.

| Capability | Required semantics and automatically checkable behavior |
| --- | --- |
| Partial updates | A patch changes only named fact keys; omission means no update, not cancellation. Other known values and applicable sources must survive. |
| Same-window correction | Explicit version/supersedes relation for the same fact key. Replayed old revisions cannot regain authority. Successive observation times remain a different task. |
| Recoverable missing evidence | The same field is known in some cases and unknown in others; hide all supporting copies before first exposure, then deliver support later. |
| Explicit conflict | Incompatible values for one key follow a public precedence rule, or produce a declared conflict/allowed-set outcome. Unresolvable real-source ambiguity stays outside main scoring. |
| Cancellation or expiry | Explicit target, scope and valid time. Expired evidence does not prove a physical hazard ended or a port reopened. |
| Multi-entity/window reasoning | Updates to entity A or window X cannot overwrite entity B/window Y; longer traces increase dependencies, not only raw text length. |

Start with partial updates, corrections and recoverable missing evidence. Add
conflict/cancellation only after the answer schema and automatic reference
semantics cover them. A schema with only numeric-or-unknown cannot silently
represent a new conflict class; that requires a new protocol version.

The current port-reopening field is always unknown. Preserve it as a basic
control, but do not rely on it as the sole evidence-insufficiency test. Vary
answerability for matched fields and templates, and include clearly sufficient
counterparts. Removing only a summary line is insufficient if the body still
contains the answer. Acquisition failure or inability to establish Gold is a
data rejection, not a fabricated "the model should answer unknown" example.

Freeze capability proportions, generator seeds, value ranges and exclusion
rules before model outcomes. Keep easy controls and report all admitted cases;
do not build the main score from cases selected because DeepSeek failed them.
If development performance saturates across several models/events, increase
dependency structure and semantic coverage under a newly registered version.

Acceptance: known-correct programs pass; stale, indiscriminate-overwrite and
always-unknown controls fail where intended; unrelated facts remain invariant;
all generated pairs have verified Gold relationships; no future/hidden evidence
appears in the public view. A perfect specification-following program remains
a useful reference even when LLMs are being evaluated on the same task.

## P3: optional experiments about state carriers

Keep the current full-evidence track for comparable model/method results. It
tests answer representation and interference when original evidence is available.
It does not isolate memory dependence.

If memory mechanisms are a research priority, introduce a separately named
finite-evidence track: equal new-evidence windows, declared history budgets and
explicit allowed carriers. A snapshot model with no past evidence has less
information by design; its deficit is not by itself proof of a memory-quality
effect. Report the full-evidence reference separately.

For stronger mechanism evidence, fork identical prefixes within one model and
method. At the same next checkpoint keep evidence constant and compare actual
carrier, carrier reset, a removed entry and a controlled wrong entry. Predeclare
which subsequent answers should require that entry, plus unrelated-fact controls.
Retain intervention hashes and independent sampling. This measures effects of
the controlled intervention, not an unrestricted claim about internal memory.
Carrier edits do not belong in the normal model leaderboard; they are labeled
diagnostic arms with separate costs. Private Gold is never supplied to the
model, including in these interventions.

This phase is optional if the first publication focuses on dynamic evidence
reliability rather than causal memory mechanisms.

## P4: independent events, second domain and external controls

Use the present development events to design new protocols. Preserve the current
seven heldout storms and old parser exclusions; do not repair/reassign them to
improve the old benchmark. Once heldout model outcomes influence a later rule,
treat that evaluation as exploratory and select a fresh untouched cohort.

For a larger release, predeclare a further 20-30 candidate events with explicit
year/region/intensity/lifecycle selection before acquisition and model results.
This is an acquisition target, not a guarantee of admitted events or sufficient
statistical power. Report attempted/admitted/quarantined events and their source
coverage. Keep every branch, revision, translation and generated variant of an
event together; audit shared files and near duplicates across groups.

Add one second weather domain only after sources and Gold are reproducible.
A promising candidate is station-table heat evidence: a stated study threshold,
consecutive-day conditions and rolling temperature calculations. Units, dates,
missingness, station identity and threshold origin must be explicit; do not
present a research threshold as an official heatwave warning. Existing EarthVerse
cases can be reused only after their source files and calculations are acquired
and independently reproduced; otherwise retain them as candidates.

Keep the 230 admitted DisasterBench inherited-plan controls separate from the
weather main score. CyPortQA currently contributes a profile of 48 templates,
not 48 recovered QA items. STATE-Bench/STALE supply methodological references,
not newly verified weather labels. Avoid a combined cross-source total with
incompatible meanings.

## P5: frozen comparisons, statistics and later search

Freeze task/Gold/scorer/input/method/model-setting identities before heldout
execution. With the current 70 heldout checkpoints, two model families and
three methods require 420R requests at R independent repeats. A new dataset
size requires a fresh calculation. Do not pool overlapping smoke/development
responses as extra independent observations.

Report per-storm results and event-macro differences, plus pooled opportunity
counts. Method/model comparisons should be paired within storm. With sufficient
events, resample independent storm groups for intervals rather than treating
checkpoints as independent. Seven heldout storms remain a small pilot even with
many generated variants or repeated model calls. Choose later sample sizes using
pilot variability and coverage needs, not a universal event-count threshold.

Keep public-source contamination unresolved unless independently measured.
Later-dated records, template-family holdouts and controlled counterfactuals can
serve as diagnostics; none alone establishes absence of training contamination.

Only after fixed suites and cross-model failure categories stabilize, add
Frontier search as a separate discovery experiment. Compare it with random and
fixed suites under equal total budgets including confirmation and minimization.
Search on development data; confirm found failures on heldout events/models.
Archive reproducible cases and minimize within a declared transformation space.
Discovered-failure rate is not ordinary benchmark accuracy, and consistency
without correct answers is not success.

## Execution order and acceptance gates

The estimates below assume one engineer familiar with this project and accessible
source files; they are planning ranges, not promised completion times.

| Package | Indicative effort | Gate before proceeding |
| --- | --- | --- |
| P0 + metric specification | 1-3 working days | Offline v1/v2 comparison, negative tests, immutable history and metric definitions |
| P1 development calibration | 1-2 working days after service setup | Complete 90-request first-model matrix; then second-family coverage and documented failures |
| P2 first three controlled capabilities | 4-7 working days | Independent reference checks, paired invariants, provenance and automatic quarantine |
| P3 carrier mechanisms | Optional 3-5 working days | Separate protocol, common prefixes, declared information budgets and control arms |
| P4 source expansion | Roughly 3-7 working days, acquisition dependent | Predeclared cohort, reproducible source calculations, event-group split audit |
| P5 comparison and report | After protocol/data freeze | Full planned denominators, paired event statistics, cost ledger and versioned release artifacts |

The immediate recommended work package is P0, metric definitions and offline
rescoring of the saved DeepSeek trial. Its inference budget is zero. The next
API package is the 90-request DeepSeek development matrix, not another greeting
probe or a full heldout run. The user requested this roadmap; new production
changes and broader API execution have not been performed by this planning step.

Cost controls for later execution: predeclare request/output/context limits per
cell, cumulative reported-usage accounting, prices and a monetary allowance
before the batch. Use provider-side spending controls where available. Missing
usage/failed attempts may have unknown billing; local guards cannot promise a
hard account charge limit. The observed USD 0.01509 trial estimate is a useful
measurement for that configuration, not a price promise for other models or
longer tasks. Do not multiply all possible experimental factors at the outset.

## References to current evidence

- `README_DEEPSEEK.md`: actual trial and interpretation.
- `artifacts/deepseek_probe_v1/citation_diagnostic.json`: equivalent-citation case.
- `artifacts/deepseek_probe_v1/live_result.json`: actual scores and usage.
- `README_PRE_API.md`: current frozen matrix and protocol.
- `docs/DATA_AUDIT_METHOD.md`: source/split checks and similarity definitions.
- `../INTEGRATED_BENCHMARK_PLAN.md`: research scope and reuse boundaries.
