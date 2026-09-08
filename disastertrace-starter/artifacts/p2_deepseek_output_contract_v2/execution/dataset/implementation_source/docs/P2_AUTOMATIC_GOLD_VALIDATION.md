# P2 automatic Gold validation and acceptance

The diagnostic package described here remains separate from the subsequent
[captured execution extension](P2_EXECUTION_V1.md). That extension adds collection,
independent provenance auditing and direct captured-result scoring. It preserves
these Gold and metric definitions; the historical diagnostic package stays frozen.

P2 uses executable source semantics and deterministic grading. It adds no
per-item human annotation and uses no LLM judge. Passing software acceptance
supports consistency with the declared controlled task; it does not establish
ecological validity or prove that all possible implementation defects are absent.

## Independent semantic paths

Compiler A validates structured episodes and reduces delivered revisions by
fact key. Public oracle B independently parses numbered public document text,
validates the visible source graph, and selects the authoritative visible
assertion. B never reads private episode provenance, final Gold, compiler state
or compiler parsing. The only shared answer-schema helper is for parsing the
optional public carrier. B's source parsing and authority logic are separate.

Preparation compares A and B on 12 microtrajectories times five checkpoints times
three methods (180 comparisons), plus 18 development trajectories times five
checkpoints times three methods (270). A disagreement fails preparation. The
450 comparisons are program checks, not model calls or independent samples.

Explicit fixtures exercise partial preservation, same-value source refresh,
window isolation, support absence and recovery. Independent public-oracle tests
enumerate small revision sequences and independent-root orders. Metamorphic
tests cover global timestamp translation, ID bijections, and ASSERT-order
changes with synchronized source locators. Additional checks cover stale
replays, unrelated entities, invalid graphs, field bounds and future/private
sentinels. Text and locator changes together preserve support; changing only a
citation to an invalid line must lose grounding credit.

Source admission rejects malformed collection types and provenance/split
mismatches. Invalid task graphs are admission errors, not answerable tasks with
unknown Gold. The fixed generator admits every planned instance, so its
quarantine list is empty. This version does not silently filter real model
failures, nor does it provide a bulk external-corpus quarantine workflow.

## Program controls

| Control | Predeclared opportunity |
| --- | --- |
| correct | full public evidence solution should pass |
| latest-arrival | U2 stale replay and scope errors |
| global-latest-document | U1 unchanged-field preservation |
| clear-omitted | U1 unchanged-field preservation |
| always-unknown | U3 supported fields |
| always-known | U3 unsupported fields, including c0 |
| always-copy-previous | U1 update and U3 recovery |
| correct-value-wrong-source | U2 same-value authority refresh |
| per-key-latest-issued | legitimate baseline under monotonic single-chain rules |
| invalid-control | empty final answer at c2; prior valid carrier retained |

The first nine are independent public-input diagnostic programs. The final
control injects a malformed response. Each runs all 90 development checkpoints
for each method: 30 program configurations and 2700 diagnostic responses.
Correct and per-key-latest-issued must have perfect overall grounding. The
targeted failure metric for each declared negative control must be below one;
invalid-control must retain all 90 planned opportunities and have 72 valid
outputs. Per-key-latest-issued is allowed to pass: legal single chains with
strictly increasing issue times do not distinguish it from the reference.

Diagnostics are labeled `diagnostic_program`, `eligible_for_llm_leaderboard=false`
and `provider_requests=0`. Their execution is grouped by program and method; it
does not claim to execute the future model schedule. The planned schedule has
270 slots and 54 five-step method trajectories, with cyclic method rotation
by episode and checkpoint order preserved within each trajectory.

## Fixed-denominator scoring

The scorer reconstructs each actual request and carrier from admitted raw
responses and rejects altered exposure, wrong method, duplicates or unexpected
opportunities. It parses raw final answers again; carried states are not trusted
as acceptance evidence. Missing responses retain their planned denominators.
This offline scorer accepts diagnostic traces only. A future live integration
must bind actual captured provider responses to this protocol before admitting
LLM results; relabeling a program trace is not supported.

Metrics include schema success; known value accuracy; known value plus current
source accuracy; unknown accuracy; overall grounding; action; update success;
preservation; same-value source refresh; support recovery; same-window correction;
stale replay preservation; scope preservation; and all-correct checkpoints.
Every rate includes raw numerator and denominator, with null for no opportunity.

Update opportunities are transitions where the new Gold is known and differs
from the preceding slot, including initial acquisition. Preservation requires
the new Gold to be known and identical to its previous value and citation.
Source refresh is a known-to-known update with equal value and changed source.
Support recovery counts U3 c3 unknown-to-known slots. U2 correction counts active
c2 wind; stale replay counts both branches at c3; scope preservation counts
both at c4. These opportunity sets are defined by Gold, not by whether a model
was previously right. Conditional recovery after a model mistake is not a main
metric in this version.

Each method has 360 development field opportunities: 282 known and 78 unknown.
The microfixture diagnostic denominator is separately 240 fields: 188 known
and 52 unknown. The matched-pair score requires both branches to be wholly
correct at their corresponding checkpoint. Group counts and equal-weight
event macro accompany pooled scores. Branches, fields, checkpoints and repeats
are dependent; the three development groups support descriptive comparisons.

## Package verification and reproducibility

`prepare` requires an absent output directory and a verified existing NHC build.
It writes source bindings, actual parent records, episodes, separate microfixtures,
the planned schedule, private Gold, unsent initial public requests, diagnostic
traces/scores, an audit, a preparation plan, a recursive implementation manifest
and archived implementation bytes. No provider or credential is accessed.

`verify` checks exact file inventory, content hashes and package identity;
compares implementation bytes to the current recursive manifest; verifies and
reparses parent source bytes; reconstructs source bindings; regenerates all
semantic, diagnostic and plan artifacts; and compares their canonical content.
A rehashed manifest alone cannot conceal a changed plan or diagnostic result.
An implementation revision requires a new package rather than overwriting the
earlier one. Package verification is local reproducibility verification, not an
external signature proving who created the original source snapshot.

The preparation plan says `P2_OFFLINE_READY` only after all these program checks
complete. It keeps model settings unselected, output cap null, live readiness
false and authorization false. There are zero model and heldout model calls.
The next scientific step is NHC output calibration, then freezing P2-specific
settings and separately scheduling the complete development comparison.

## Position relative to existing benchmarks

The existing NHC task remains a natural-source extraction and action-rule
control; the existing DisasterBench task remains a plan consistency control.
P2 adds declared updates, matched support interventions and authoritative
field-source tracking. All remain separate protocols and result tables.
The P2 adapter rejects legacy requests, and the legacy adapter rejects P2.

STATE-Bench, STALE and temporal-memory work are relevant comparisons for update,
time and persistence claims; EarthVerse is relevant for executable evaluation
boundaries. This implementation does not claim a fresh upstream code audit,
baseline reproduction or verified novelty against those projects. No additional
repository was downloaded in this offline step. A publication-level comparison
still needs pinned commits, licenses and exact task/split/baseline matching.
