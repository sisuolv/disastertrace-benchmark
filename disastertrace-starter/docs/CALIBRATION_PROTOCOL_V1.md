# Common output contract and output-budget calibration v1

Status: offline preparation of a proposed development experiment. This document
does not authorize model requests. The preparation module has no live execution
entry point. Its package freezes the protocol and generated configuration before
any new model outcomes; this is a local preregistration, not an external registry.

The completed P1 experiment motivated this calibration: 20 of 90 responses ended
at the output limit and two others violated the output structure. Those outcomes,
their prompts, both scorers, and all historical records remain unchanged. The
proposed experiment uses fresh responses and a new implementation/build identity.
No new per-item human annotation, human response review, or LLM judge is required.

## Questions and permitted conclusions

1. At 4096 maximum output tokens, does making the existing public output contract
   explicit change format success and full-denominator grounded correctness?
2. Under that explicit contract, does increasing the maximum to 8192 reduce
   truncation sufficiently to select a common budget for later development work?
3. How do these changes affect the three declared input methods, actual token use,
   cache use, and observed request latency on the same development trajectories?

The first comparison estimates the effect of this specific public-contract
intervention at 4096 tokens. The second estimates the budget change under that
contract. Three arms do not identify a contract-by-budget interaction; that
would require a fourth legacy-contract/8192 arm, which is outside this proposal.
Full trajectories include effects mediated by earlier accepted answers. They do
not isolate a direct, single-checkpoint formatting effect or memory mechanism.

This is one model, one fresh repeat, and three already inspected development
storms. Results are descriptive calibration, not a heldout model ranking or a
statistical claim about all extreme-weather events. Earlier P1 responses are
historical context, not concurrent control observations or additional repeats.

## Frozen matrix

| Arm ID | Public output contract | Maximum output tokens | Fresh requests |
| --- | --- | ---: | ---: |
| legacy_4096 | Original public instruction | 4096 | 90 |
| explicit_4096 | Explicit common output contract | 4096 | 90 |
| explicit_8192 | Same explicit common output contract | 8192 | 90 |

Every arm covers snapshot, structured_state, and answer_history. Every arm and
method covers Ida (AL092021), Florence (AL062018), and Dorian (AL052019), both
existing base and delay branches, and all five checkpoints c0 through c4.

- Nine arm-by-method cells, each with 30 responses planned.
- Twenty-seven arm-by-method-by-storm blocks, each with ten checkpoints.
- Fifty-four separate five-checkpoint episode trajectories.
- One repeat: 270 scoring opportunities and at most 270 provider attempts.
- Requested output-token ceilings sum to 1,474,560; each method has 491,520.
- Per arm the requested output ceilings are 368,640, 368,640, and 737,280.

All seven heldout storms remain outside model inference. No failed P1 cell is
selected for special treatment, and no new response is substituted into P1.

## Fixed inputs and output interpretation

Use deepseek-v4-flash at https://api.deepseek.com with reasoning_effort=high,
thinking enabled, and no temperature override. The output-cap parameter is
max_tokens. Hold timeout=60 seconds, maximum response bytes=1,048,576, and
request-body byte guard=262,144 across all arms. Preserve endpoint, model options,
system message, raw evidence, policy, source parser, schedules, field order,
answer parser, and both scoring policies. Only the declared public-contract
variant and max_tokens differ between arms.

The explicit contract describes the already expected JSON object, exact state
keys, each slot's fields and types, unknown/null behavior, citation locators, and
action as one of the three permitted strings. It applies equally to all methods.
It does not include an event-specific answer or a filled all-unknown decision,
which would provide the answer at c0. It does not request an API response_format
mode, use constrained decoding, add response repair, or change parsing/scoring.

Task instructions can require support for known facts while the frozen parser
continues to accept a known numeric slot with an empty evidence list. Such a
slot remains a grounding failure under the existing scorer, rather than a new
schema failure. Parser acceptance and full task correctness are distinct.

Each request receives cumulative delivered evidence and fresh messages. The
snapshot method has no prior-answer carrier. Structured_state receives its own
latest schema-valid decision; answer_history receives its own schema-valid
decisions in order. Existing handling of invalid answers is retained: keep the
raw response and failed opportunity, but do not promote it into the carrier.
Schema-valid wrong answers propagate unchanged. Never supply Gold, a repaired
answer, another arm's answer, or another method's answer as live history.

Carrier identity includes arm, method, storm, branch, and repeat. A new branch
starts empty. Prepared c0 requests are authentic empty-carrier request templates.
Later requests cannot be frozen as actual live wire payloads before their prior
model answers exist. Offline full-trajectory rehearsals use explicitly labeled
deterministic diagnostic answers derived from public evidence. They are neither
LLM observations nor reusable live carriers.

## Execution order

Execute one request at a time. Use fixed storm order Ida, Florence, Dorian and
storm index s=0,1,2. Start with arm order legacy_4096, explicit_4096,
explicit_8192 and method order snapshot, structured_state, answer_history.
Rotate each of those two orders left by s positions. Within each storm, iterate
arms then methods using those rotated orders and run each ten-checkpoint block
without interleaving its checkpoints with another configuration.

For storm indices 0 and 2 run base then delay; for index 1 run delay then base.
Every branch always runs c0,c1,c2,c3,c4 in that order. The generated schedule in
the preparation package is the exact execution order to bind before live work.

Across three storms, each arm occupies each third of the storm block once and
each method occupies each within-arm position once. This reduces fixed-order
imbalance. It does not control provider cache history, service load, alias
changes, or time effects perfectly. No artificial cache-busting text or forced
cache warm-up requests are added. Report the order and cache metadata explicitly.

Record request start/end time, returned model alias, available fingerprint and
provider version metadata, finish reason, usage, and successful transport latency.
A matching alias or fingerprint is not independent evidence of an immutable
underlying model. Transport latency excludes parsing, scoring, and preparation;
timeouts have their own count, not a fabricated successful latency value. The
common 60-second timeout is a possible ceiling for high-budget requests and is
not increased after observing an individual failure.

## Full-denominator endpoints and budget-selection rule

Report schema success, length-finish count, empty final content, partial/invalid
JSON, structural errors, transport failures, unsubmitted opportunities, and usage
availability separately. These diagnostic categories can overlap. Finish reason
length counts toward the truncation endpoint even when the received final text
passes the frozen parser; parsing and scoring still follow the frozen rules.

Quality reporting retains dynamic_score_v2.0 with nhc_equivalent_support_v2 as
the primary grounding policy and preserves v1 scores. Per arm and method the
unchanged full denominators include 30 checkpoint opportunities, 96 known fields,
54 unknown fields, and 150 total fields. Also report the fixed-reference 64
changes, 56 preservations, and eight provenance-refresh opportunities. Conditional
recovery and other model-dependent opportunities retain their own denominators.
Zero opportunities have null rates. Valid-response-only accuracy is secondary
diagnostic information and never replaces a fixed denominator.

For each method report the paired, within-storm difference between explicit_4096
and legacy_4096, and between explicit_8192 and explicit_4096. Include pooled
counts, equal-weight storm macro results, base/delay results, and source-support
failure reasons. Do not treat 30 dependent checkpoints as 30 independent storms
or attach population significance claims to this one-repeat calibration.

The final common-budget recommendation requires a complete, audited 270-response
matrix with valid usage and response metadata. Incomplete execution produces no
selected budget. For each explicit-contract candidate independently, require:

- At least 29 of 30 schema-valid responses in every method.
- At most one length-finish response out of 30 in every method.
- All 90 planned responses received, with no infrastructure or accounting failure.

Choose 4096 when it satisfies every condition; otherwise choose 8192 when it
satisfies every condition; otherwise return no_selection. Use one common cap for
all three methods. Do not select a different cap for each method, choose the
highest observed grounding score, or repeat only a failing cell. These thresholds
are a development screening rule, not a confidence-bound claim of 95% reliability.
Factual and evidence errors remain benchmark outcomes even when a budget passes.

The offline aggregate-count selector only rehearses this decision rule. Its
screening output has evidence_validated=false: supplied counts do not establish
that any model call happened or that a collection is complete and authentic.
A live recommendation additionally needs independent collection verification and
the frozen response, usage, scorer, and schedule bindings described here.

If neither cap qualifies, retain both results and prepare a separately versioned
next experiment. No automatic 16384-token escalation, reasoning-mode change,
prompt rewrite, or task exclusion is part of this protocol.

## Proposed spending and failure controls

The proposed allowance is USD 3 for this new experiment only. It is a proposal,
not an authorization, an estimate of the eventual invoice, or permission to reuse
the completed P1 continuation's unused allowance. Old unresolved attempt 79 and
its USD 0.46678016 reservation stay in the original accounting.

Reference rates and limits are the captured official 2026-09-06 documents at
artifacts/p1_deepseek_development/docs/pricing.html and
artifacts/p1_deepseek_development/docs/rates.json. They describe 1M context,
384K maximum output, and the
following USD prices per million tokens:

| Window | Input cache hit | Input cache miss | Output |
| --- | ---: | ---: | ---: |
| Off-peak | 0.007 | 0.22 | 0.66 |
| Peak | 0.014 | 0.44 | 1.32 |

The captured peak windows are Monday-Friday 01:00-04:00 and 06:00-10:00 UTC.
Do not apply the earlier Sunday's discount to an arbitrary future execution.
Before any later live launch, verify the relevant published rates and model
limits and bind that snapshot. A changed price/limit requires a new explicit
accounting amendment before sending requests; do not silently reuse stale caps.

Before each proposed sequential call, reserve the full documented 1,048,576
prompt tokens at the peak cache-miss price and the arm's requested output cap
at the peak output price. The conditional reservations are USD 0.46678016 at
4096 and USD 0.47218688 at 8192. Full-context reservation deliberately does not
estimate prompt tokens from request bytes or historical average usage. It may
over-reserve a combined context window that includes output.

After validated usage, settle prompt usage at the peak cache-miss rate and
completion usage at the peak output rate, releasing only the unused reservation.
Reasoning tokens are included in completion usage and are not charged twice.
Record a separate actual-window, cache-aware received-response cost estimate.
Keep a distinct unknown charge when a sent request has no validated usage.

USD 3 is a conditional stopping allowance, not a guarantee that all 270 calls
complete. Charging all 270 requests at these full-context input ceilings and
their output ceilings would be USD 126.517248. A future live runner must refuse
a next request when settled accounting plus retained reservations plus the next
reservation exceeds USD 3. This control depends on provider enforcement and the
documented rates; it cannot guarantee the provider's account-level final charge.

No automatic retry, timeout reissue, response repair, or selective regeneration
is allowed. Malformed benchmark answers within a valid provider envelope remain
received failures and execution can proceed with the unchanged carrier policy.
A provider error, uncertain in-flight call, invalid/missing usage, cap violation,
or unexpected model alias stops further calls after preserving available records.
All remaining planned opportunities remain represented as unsubmitted failures.
Never claim a local crash proves provider failure or zero charge.

An interrupted batch is reported separately as incomplete. This offline package
does not implement a restart or retry policy. A future runner must preserve exact
request/response bytes, completed prefixes, launch ownership, pending reservations,
and the frozen schedule. Any later recovery scope must be bound separately before
execution, with no implicit reuse of the P1 continuation's consumed launch claim.

## Offline deliverables and executable preparation

The implementation provides an offline-only calibration module. Starting with a
fresh implementation-matching build at work/build-calibration-v1, execute:

```bash
.venv/bin/python -m disastertrace.automated.calibration prepare --build work/build-calibration-v1 --provider-config artifacts/p1_deepseek_development/provider.json --output work/calibration-v1-preparation
.venv/bin/python -m disastertrace.automated.calibration verify --output work/calibration-v1-preparation
```

The preparation package binds this protocol, common output contract, source and
scoring identities, provider configuration, captured prices, complete schedule,
c0 request templates, and deterministic full-trajectory rehearsal evidence. It
contains 54 unsent initial request templates and 1,080 diagnostic responses:
four program backends times nine cells times 30 checkpoints. The backends are
rule, last-arrival, no-update, and invalid-control. The last one deliberately
returns an empty answer at c2 in each branch to exercise failure retention and
the unchanged accepted-answer carrier. These are program controls, not new model
observations or evidence that either output budget is sufficient.

The frozen scorer reconstructs the legacy instruction when it audits a trace.
To preserve that scorer, each rehearsal retains its actual diagnostic trace and
a distinct scoring_projection.jsonl. Before constructing this projection, the
new wrapper sequentially reconstructs and verifies each actual request, its
declared contract, exact public exposure, response acceptance, and carried state.
It then replaces only the instruction with the legacy instruction and recomputes
that projected request's hash. Responses, evidence, carrier, and other request
fields stay the same. The score record separately binds the actual trace and
projection fingerprints and declares actual_exposure_is_projection=false and
live_collection_verified=false. The projection is a compatibility input for
scoring deterministic controls; it is not the actual explicit-contract exposure,
a provider response record, or proof of a live collection.

The unchanged collector and collection audit have no live explicit-contract path.
Their legacy instruction reconstruction must not be used to claim that newly
transformed prompts were what a model actually received. The next live package
requires contract-aware collection and independent audit before scoring actual
model results under this new instruction.

The preparation records zero model requests and no live authorization. Its
built-in verification reconstructs the generated files and checks the new build,
input hashes, matrix counts, method/carrier isolation, and public-evidence
boundaries. A separate historical audit checks the original packages and their
checksums; built-in calibration verification alone does not reverify all earlier
P1 archives. The exact executed commands, exit codes, and tests belong in the
task's verification records, not inferred from this plan.

Acceptance for the present package is offline preparation and verification with
all historical artifacts intact. It is not successful model calibration. The
next live package needs an independently tested scheduler and cumulative budget
guard implementing this protocol, a frozen launch manifest, and actual scope and
budget authorization. No live launch command is included in this document.
