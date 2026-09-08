# P2 controlled weather evidence semantics v1

Status: offline task specification, `disastertrace_controlled_v1`.
This task evaluates evidence update, preservation, scope and source tracking by
LLMs. It does not measure weather forecasting skill, physical simulation,
operational warning quality or an internal memory mechanism.

## Scope and source inheritance

The development scope has 18 trajectories, five checkpoints per trajectory,
90 checkpoints per method, and 270 planned slots across `snapshot`,
`structured_state` and `answer_history`. There are three development source
groups, three families and two matched branches per family. The first two groups
use the primary case; the third uses the secondary case. These choices precede
model results. There is one planned model and repeat; no live model is selected
or authorized by this offline package.

| Source group | Actual initial source | Assigned case |
| --- | --- | --- |
| AL092021 (Ida) | earliest admitted advisory, 009 | primary |
| AL062018 (Florence) | earliest admitted advisory, 009 | primary |
| AL052019 (Dorian) | earliest admitted advisory, 009 | secondary |

All four initial field values are inherited from each named source record in a
verified NHC development build. Each binding retains the raw source hash,
canonical source-record hash, URL, field evidence spans and inherited values.
The package includes the actual parent records, verifies their raw-text hashes,
and reparses them with the bound original NHC parser. Schema admission checks
that declared initial values equal the controlled target root values. Only
package preparation/verification validates the claims against source bytes.

Entities, effective windows, revision graphs, later update values, generated
document text and delivery schedules are controlled constructions. They are
explicitly labeled `controlled_generated`; they are not historical official
corrections. No physical process realism has been validated. Three provenance
groups do not turn the generated branches into independent observed storms.

The 12 microtrajectories are separate synthetic software fixtures: three families
times two minimal cases times two branches, each with five checkpoints. They
use initial wind 90, pressure 980, latitude 20 and longitude -70. They are not
added to the 18-trajectory development matrix. The generator version is
`controlled_generator_v1`, seed declaration 20260907, with deterministic rules
and no model-dependent selection.

## Fields and strict numerical contract

| Variable | Unit | Inclusive range |
| --- | --- | --- |
| maximum_wind_mph | mph | 0 to 300 |
| minimum_pressure_mb | mb | 800 to 1100 |
| latitude_deg | degree | -90 to 90 |
| longitude_deg | degree | -180 to 180 |

Values are finite JSON integers or floats, excluding booleans, with at most two
decimal places. There is no implicit unit conversion or tolerance-based match.
This version has no port reopening field. The action is a research rule: known
wind at least 100 means `prepare`, known wind below 100 means `monitor`, and
unknown wind means `request_evidence`. It is not operational advice or an
independent decision-making task.

## Fact keys and authority

A fact key is `(entity_id, variable, valid_start, valid_end, measurement_kind)`.
Times must be timezone aware; equality uses UTC instants. Effective intervals
are nonempty and half open. The measurement kind is `controlled_observation`.
Queries select an exact fact key for each required field, not an overlapping
window and not the newest storm document globally.

`SET` asserts roots and has null `supersedes`. `PATCH` names an explicit parent
revision for every assertion. A legal key has a single root and a single
revision chain. Cross-key replacement, duplicate revisions, branches, cycles,
missing parents, invalid units and non-increasing revision issue times are
rejected. The parent must have been visible in an earlier delivery before a
child is delivered. Multiple independent roots belong in a `SET`, and each
document contains at most one assertion for each fact key.

Delivery time, issue time and effective time have different roles. An admitted
record has a scheduled delivery no later than the final checkpoint and cannot
be delivered before issue. Visible evidence at a checkpoint consists only of
deliveries no later than that checkpoint. Replaying a record retains its
original bytes and authority. Missing fields in a later document preserve the
latest visible authority; they never delete it. This version excludes retract,
expiry, conflict resolution and known-to-unknown transitions.

## Five-checkpoint families

| Family | c0 | c1 | c2 | c3 | c4 |
| --- | --- | --- | --- | --- | --- |
| U1 partial update | empty | initial four fields | wind PATCH | active pressure PATCH; control wind replay | initial replay |
| U2 same-window correction | empty | initial W | active W PATCH; control W2 root SET | old W replay | other entity root |
| U3 recoverable absence | empty | complete control; missing target in active | unrelated PATCH | target support delivered/replayed | other-fields replay |

U1 and U2 primary cases change wind across the action threshold. Secondary
cases keep its value but change the authoritative revision and citation. U1
pressure updates change by one within bounds. U2 W2 is an independent root;
there is no invalid cross-window `supersedes` link.

U3 primary withholds wind and secondary withholds pressure. All support for that
target field is absent from the delayed branch at c1/c2, including metadata and
carriers. The complete branch sees it at c1. The target support arrives at c3,
and both branches converge to the same values and citations. U3 secondary uses
a latitude update as its unrelated update. Support remains in cumulative
evidence after first delivery. History cannot create new Gold support.

## Public request and answer

Each record is rendered as numbered lines: one `CONTROLLED_RECORD` JSON header
followed by `ASSERT` JSON lines. The header exposes record ID, issue time,
operation and `source_origin`. Each assertion exposes its exact key, revision
ID, unit, value and parent revision. These are public semantic inputs.

The request allowlist is protocol, instruction, checkpoint time, target,
required fields, action policy, delivered evidence and method. Evidence entries
have delivery ID, record ID, issue time and numbered text. Gold, private
provenance, source group, family, case, branch, future documents and future
delivery schedule are not request fields. The compiler uses structured events;
the independent oracle parses the actual public text.
Generated public entity, record, revision and delivery IDs use stable opaque
digests, so private family, case and source-group labels are not embedded in IDs.

All methods receive identical cumulative evidence. `snapshot` has no carrier.
`structured_state` receives the preceding valid complete decision, or null.
`answer_history` receives all preceding valid complete decisions. Every
checkpoint is a fresh request. The output is exactly an action and a complete
state over the four fields. Each slot has `status`, `value`, and `evidence`:
known requires a typed number; unknown requires null and an empty evidence list.
Each citation has a record ID and a positive integer line.

Known with empty citations is structurally valid but fails grounding. Every
submitted citation must support the current authoritative field revision; a
correct number with an old revision or an unrelated same-valued assertion fails
grounding. Invalid full outputs are retained as failures and do not update
carriers. Schema-valid factual errors do propagate. The harness never merges
partial answers, repairs from Gold or treats diagnostic answers as live history.

## Version boundary

The recursive implementation manifest includes controlled code, actual shared
dependencies and the two P2 semantic/validation documents. The content identity
binds implementation, episodes, source content, split, templates, microfixtures
and compiled Gold. Parent build identity is retained for lineage but omitted
from semantic episode identity, so relocation alone does not change content.
The separate future live execution identity must also bind environment,
provider settings, execution path and schedule. The current P2 adapter only
constructs an unsent request; it exposes no live collection command.
