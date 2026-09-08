# Next research plan after the paired P6 run

This plan continues the four supplied plan_v3 documents. The current deliverable
is one 2,160-opportunity model matrix and one bounded, independently parsed NHC
source pilot. Read FINDINGS.md for their actual outcomes. This file defines later
work; it does not claim a new forecast-task score, representation experiment,
second-model run or expanded source collection has already happened.

## 1. Build the forecast-claim task offline

The next implementation priority is a separately versioned task over the admitted
NHC products. Its question is: given the explicitly delivered advisory texts,
which forecast is the latest statement covering this exact target valid time,
what does it say, and which source lines support the answer? This measures use
of published forecasts. It does not measure the model's numerical weather
prediction skill or the quality of operational hurricane decisions.

Use the existing twelve-source acquisition claim as consumed evidence. Keep
quarantined bodies and their reasons. If a general parser defect is found,
preserve review_v1 and build a tested review_v2 from the same saved raw bytes;
do not silently fetch replacements or manually repair individual Gold records.

### Deliverables

| Deliverable | Content | Acceptance condition |
| --- | --- | --- |
| Task specification | Fact key, delivery, answer schema, null/terminal and citation rules | Every field has an explicit source or an explicit unknown state |
| Dataset manifest | Exact admitted product hashes, candidate/query selection and exclusions | Counts reproduce from the source bundle without network |
| Compiler | Reference values, product authority and original byte/line support | Uses only products admitted by both parsers |
| Public resolver | Rebuilds answers from exactly the text shown to the model | Does not read hidden Gold or share the compiler's parsing implementation |
| Independent scorer | Value/unit/time, source version, locator and full-answer metrics | Invalid and missing outputs retain their planned opportunities |
| Offline execution package | Frozen source, dataset, methods, context and schedule | Correct and deliberately wrong program runs reconstruct on CPU |

The fact key should include storm identity, absolute valid_at, variable,
measurement_kind=forecast and unit. The initial variables are latitude,
longitude and maximum sustained wind in KT. Keep gusts and qualifiers available
in the source, while scoring them only if a later task specification adds them.
Do not add a future-pressure field or carry over the controlled track's port
action rule.

### Time and authority rules

- Preserve issued_at, center_at, valid_at, retrieved_at and the controlled
  delivery step separately. Historical first available_at and numerical-model
  initialization_at remain unknown unless independent evidence establishes them.
- Define visibility by the synthetic delivery schedule. An archived issuance
  timestamp does not prove historical availability. Label this as official
  source facts with controlled delivery.
- Resolve authority per exact fact key among visible products that explicitly
  cover it. A later product without that target row does not provide an
  interpolated forecast or erase a prior explicit row under this rule.
- Restrict the first task's targets to future valid times at each checkpoint.
  If retrospective queries are useful, specify them as a separate task mode.
- A terminal row such as DISSIPATED or ABSORBED is an explicit forecast status,
  with null numeric fields. It is not zero wind and does not automatically
  terminate all other valid-time keys. Preserve POST-TROP qualifiers separately.
- A same-value revision still updates the authoritative product identity.
  An old citation can support the number literally while failing the current
  version requirement; report both aspects.

### Scope and selection before any model run

Enumerate all eligible same-absolute-time targets from the frozen source pilot,
including unchanged and changed values and explicit terminal rows. Report the
number of targets, revision transitions, unique products and independent storms
separately. Several transitions for one target and all targets within a storm
are dependent observations.

Freeze deterministic inclusion/order and any caps without consulting future
model performance. Keep a complete candidate and exclusion table. A task may
have few informative revisions; report that result instead of manufacturing
changes or treating each template as an independent weather event.

Choose natural issuance-order delivery as the initial task. A controlled late
delivery of an older advisory can be a later, separately labeled intervention.
Preserve full input hashes and do not describe synthetic delivery as an actual
historical arrival sequence.

### Required checks

Use fixed-answer fixtures and generated calendar cases for month/year rollover,
leap days, midnight UTC, invalid days, and identical relative leads with different
absolute valid times. Check sustained wind versus gusts, KT versus MPH, hemisphere
signs, current-center versus forecast rows, missing targets, explicit terminal
rows, repeated numerical values, stale product delivery and out-of-scope storms.

Add deliberately wrong public policies: last displayed row, same relative lead,
latest document regardless of coverage, maximum wind across valid times and
copying current pressure into a forecast. The scorer must distinguish their
failures from a legal latest-explicit-covering-key resolver. Some policies may
agree on some natural items; retain those no-effect cases and actual denominators.

Check that citation spans reproduce the original source bytes, and that every
model-visible view can be reconstructed without Gold. Run context checks with
the actual pinned tokenizer and reserved output budget before freezing any model
matrix. Keep generation disabled throughout this offline milestone.

Include an import/CLI smoke check executed from the exact copied source package
with original paths and network blocked. The source pilot's first command failed
before networking because a minimal snapshot omitted package-import dependencies;
source_execution_v2 supplies that closure while preserving the original parsers.

## 2. Prepare a separate carrier-representation control

The P6 methods expose different amounts and forms of model-derived history.
Their scores cannot isolate a pure representation or memory mechanism.

Prepare two deterministic renderers of exactly the same previously saved model
decision: JSON and an explicit text/table state. Preserve every value, status,
source ID, locator and existing error; never correct the carrier with Gold.
Use one declared source run and a deterministic selection rule independent of
its correctness. The current all-fields attribution inventory supports auditing
that selection but should not be used to select only favorable cases.

Require both views to round-trip to the same declared carrier object. Measure
token differences under the target tokenizer. Information equality and token
equality are separate properties; report both, and do not claim a length control
merely because the renderers retain equal facts.

For a later model test, both branches start from the same saved prefix and see
identical current public evidence. Their outputs and any subsequent histories
then remain separate. This estimates a conditional representation effect for
those fixed prefixes; it is not a fresh autonomous trajectory score. Any oracle
carrier belongs to an explicitly marked diagnostic upper bound.

The first implementation milestone contains renderers, round-trip tests,
provenance and token measurements only. Any downstream model opportunities need
a separate frozen count, schedule, paired seeds, resource cap and one-use run.

## 3. Match a second model to the frozen task

Choose the task version and scientific comparison before choosing or downloading
another model. Use the same development data, evidence budget, method definitions,
fixed denominators and scoring implementation. Keep native free-output and
structure-constrained tracks separate when backends have different capabilities.

Verify the actual candidate checkpoint/license, tokenizer, context limit,
reasoning delimiters, grammar support, precision and installed backend. Perform
generation-disabled hardware preflight before binding a new execution. Do not
infer support from a model-family name or use a fallback silently.

Test the installed backend's text rendering independently of its token list,
including stop-token exclusion, length termination and reasoning delimiters.
The P6 collector preserved every answer, but its initial CPU audit expected EOS
text contrary to the frozen include_stop_str_in_output=false setting. The
separate repeat_live_review version fixes that comparison and retains exact
extraction/scoring; reuse its regression cases before later generation.

Compute opportunities from the frozen eligible targets, checkpoints, methods,
conditions and repeats. Old Qwen or DeepSeek calls are historical evidence and
cannot stand in for a matched fresh repeat. Maintain the user's ceiling of four
concurrent H100s. If using multiple workers, keep each paired unit on one worker
and freeze the balanced assignment before generation. Paid API scope and pricing
would require their own concrete reservation if that route is selected.

The user subsequently requested more GPU parallelism during this run. Prefer
four independent TP=1 replicas for the next suitable matrix. The new
`../p6_parallel_preparation_v1/README.md` records the implemented offline layout,
whole-episode assignment and remaining collection/aggregation engineering. The
active single-worker matrix is preserved; this preview launches no new jobs.

## 4. Expand source coverage after task validation

The current controlled model matrix has three independent storm groups. The NHC
pilot has at most two storms and only one candidate storm beyond the existing
Ida source. Neither supports general claims over extreme-weather phenomena.

Prepare a larger development-source catalogue with declared years, product
types, deterministic selection order, missing-format handling and download caps.
Protect all eight originally declared heldout IDs, including quarantined Matthew;
the seven admitted heldout storms are not the complete protection list. Preserve
the recorded Ian/Francine plan exposure and group all products and variants by
storm identity.

Expand natural product and revision diversity, not only template count or storm
names. Prefer documenting actual coverage gaps before adding a second hazard.
CAP/VTEC is a future alternative with its own event/area/status semantics. It is
not an interchangeable source format for this NHC task.

## Reporting and completion gates

Report checkpoint and whole-episode correctness, repeat-specific outcomes,
both directions of paired change, source-level descriptions, full failure
denominators, source acquisition/quarantine and actual resource use. Keep
controlled, native forecast and fixed-carrier diagnostic tracks in separate
tables. Avoid population confidence or universal model/method rankings from
the present small source groups.

Each milestone is complete only with implemented code, actual checks and exits,
immutable raw evidence, a CPU reconstruction path and an explicit limitation
statement. A proposal is not a run, two parsers are not two independent weather
sources, a successful output grammar is not semantic correctness, and duplicated
archive views do not increase the count of independent examples.

The recommended next executable boundary is Section 1's offline forecast task.
Its completion provides the concrete dataset and count needed for a later model
experiment; no additional model answers are included in the current P6 scope.
