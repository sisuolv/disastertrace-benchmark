# P2 captured execution v1

This execution layer is separate from the historical diagnostic-only P2 package
and from the completed T6 calibration. It preserves the controlled task, public
instruction, Gold semantics and metric opportunity sets. Existing snapshots and
T6 authorization are not modified or reused as a P2 launch claim.

## Frozen development scope

The development matrix contains 18 episodes, three methods and five checkpoints:
270 slots and 54 isolated trajectories. Initial values still inherit three NHC
source groups; subsequent records remain explicitly generated. All seven heldout
storms remain outside this execution. Each checkpoint receives a fresh request
with the same cumulative public evidence and only its declared model carrier.

The proposed first model is deepseek-v4-flash, high reasoning effort, thinking
enabled, a common 8192 output cap, no temperature, 180-second socket timeout and
a separately enforced 180-second total network deadline. T6 supports 8192 as a
starting format setting; it has not measured P2 output reliability.

The separate P2 ledger reserves 2,211,840 requested output tokens across at most
270 attempts. Its default USD 3 conditional allowance is a proposal, not a
launch authorization or a completion guarantee. Reservation uses the saved
peak/cache-miss rates and full 1,048,576-token prompt bound. The saved price
document is historical evidence; a matching, current applicability attestation
is required before actual dispatch. Reasoning usage is already in completion
tokens. Conditional usage estimates and reservations are not invoices.

## Collection and recovery

Before dispatch, a single writer holds the execution registry lock and durably
writes the exact public request, prepared wire bytes and budget reservation.
It then writes send intent, captures bounded credential-filtered response bytes,
settles verified usage and records the parsed task decision. Each journal row
extends a hash chain. Protocol-specific wrappers validate NHC and P2 requests
separately before invoking shared transport primitives; neither wrapper accepts
the other protocol or arbitrary messages.

Schema-invalid decisions remain recorded and do not update the carrier.
Schema-valid factual mistakes do propagate unchanged. Empty content and length
finishes are preserved. No retry, Gold repair or partial-state merge occurs.
An unknown dispatch blocks subsequent network activity and retains its reserve.
Offline recovery can finalize an already captured response without credentials;
it cannot resend an uncertain request. A reservation with no send intent can be
sent once by an explicitly resumed collector. Damaged journals fail closed.

The frozen canonical registry binds one execution to one run directory. Live
authorization binds the execution ID, allowance, attempt/output-token scope and
rate identity. Diagnostic registries are separate and cannot consume or replace
the production claim. Loopback HTTP fixtures exercise the actual socket path
but are never LLM results. Injected transports are diagnostics without a hard
deadline guarantee. Neither kind is eligible for the LLM scoreboard.

## Independent audit and direct scoring

The auditor independently reconstructs the schedule, public evidence, accepted
carrier, exact prepared bytes, captured completion, UTC timing and all reserve
and settlement arithmetic. It does not trust collector summaries, copied
acceptance flags or the mutable in-memory ledger. It binds local capture origin;
local hashes are integrity evidence, not a provider signature.

The captured-result reporter always invokes this audit before using the common
P2 metric arithmetic. It neither relabels program traces nor projects P2 into
the legacy NHC scorer. The existing diagnostic scorer continues to reject model
origins. Unsubmitted and attempted-but-unresolved slots keep fixed denominators
and distinct status labels. Raw invalid answers are retained with their failures.

Format screening is predeclared at each family-by-method cell: 30 slots, schema
success at least 29 and length finishes at most one, with a complete audited
matrix. Diagnostics may test this arithmetic but cannot establish measured model
reliability. Failed screens remain reportable; changes require a new common
execution revision, not selective replacement of failed responses.

Outputs separate pooled scores, source groups, families, paired branches,
format/transport errors, current-version citation errors and wrong values.
These generated branches and checkpoints are dependent observations; this stage
does not establish physical weather realism, cross-hazard generalization or
statistical significance. No new per-item human annotation or LLM judge is used.

## Version and release boundary

The new dataset and execution bind current controlled code and shared transport,
storage, accounting and reporting dependencies recursively. A new implementation
requires a fresh package. Execution identity additionally binds environment,
provider settings, schedule, rates and registry path. Historical P2 content IDs
remain valid for their archived implementations. Preparation and offline
acceptance make zero model calls; actual model collection remains a separately
scoped launch after the execution package is reviewable.
