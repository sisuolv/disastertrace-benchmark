# Calibration execution v1.1

This execution amendment inherits the three arms, nine cells, 54 trajectories,
270 development opportunities, source/answer parsers, carrier acceptance, scoring,
fixed denominators and selection rules of CALIBRATION_PROTOCOL_V1.md.

The common socket timeout and separately enforced total network deadline are
180 seconds in every arm. These are engineering choices, not empirically proven
sufficient limits. All other model settings and task content remain inherited.
No automatic retry, failed-answer repair, cache warm-up or heldout inference.

Only the new explicit live entry reads an environment credential. It requires
matching authorization evidence and a recent explicit attestation that the bound
captured prices and limits still apply. Changed prices require another execution
version; this package does not silently update its accounting rates. Preparation,
verification, injected-transport rehearsal and report make zero model calls.
The existing USD 3 allowance is a proposed conditional stopping amount, not a
guarantee to finish 270 calls or a statement of provider account charges.

One experiment owns one shared registry claim, writer lock and hash-chain journal.
Claim identity does not change with output directory. Preparation freezes the
canonical absolute registry path in the execution identity, defaulting to the
preparing checkout root. Live callers cannot override it; copying the execution
package does not change that path. Relocation requires a new explicit execution
identity and scope, not reuse of an old authorization. Diagnostic tests may use
isolated registries and cannot become live runs. The initial
live scope permits safe-prefix resume in the same output only when every earlier
dispatch has a complete, verified durable response. A dangling send intent, damaged
journal or invalid usage stops further network work and retains its reservation.
PID or lease expiry alone does not authorize failover. Local locking is not a
distributed or provider exactly-once guarantee.

Prepared wire bytes, reservation and send intent are durable before dispatch.
Bounded response capture and credential-reflection filtering precede persistence
and envelope parsing. HTTP errors, malformed bodies and interrupted prefixes are
retained when safely available; withheld bodies and incomplete captures are labeled.
Network deadline terminates/reaps the transport worker; disk durability is separate.
Task-schema-invalid responses with valid provider usage are settled and retained;
they do not replace the last accepted carrier. Schema-valid wrong answers propagate.

The independent auditor reconstructs actual public inputs, sequential carriers,
wire bodies and Decimal settlements. It does not authenticate provider signatures
or defeat an adversary rewriting every trusted local anchor consistently.
Injected transports always retain their diagnostic origin and cannot yield a live
budget recommendation. The scorer consumes a separately labeled offline projection:
actual received inputs differ only in instruction from its legacy-compatible views;
missing opportunities use explicitly unsubmitted placeholders, not alleged exposures.
Projection provider_requests=0 describes offline materialization. Actual attempts
remain separately accounted by the journal; projection rows are not network receipts.

Completion requires 270 received, audited responses with valid metadata and usage.
Candidate explicit caps require schema >=29/30 and length <=1/30 in each method.
Every length finish counts even if parsed successfully. Select the smallest common
qualifying cap; otherwise no_selection. Program rehearsals can only simulate this
rule. A partial run retains all 270 planned opportunities and its stopping reason.

The immutable authorization excludes the refreshable price-confirmation timestamp.
Each live start/resume appends a matching price attestation, so a later unchanged
price confirmation does not reset scope or prevent safe-prefix recovery. The
`recover` command performs only offline finalization of already captured responses;
it requires no model credential or new request and never proceeds to an unsent slot.

The journal records UTC send-intent time before its durable append and UTC capture
observation time after transport returns, before capture persistence. The auditor
requires explicit UTC timestamps. These are local collection brackets, not provider
billing-time authentication. Network elapsed time is measured separately using a
monotonic clock; filesystem persistence is not included in transport latency.
Reports retain per-request usage and per-cell latency, overlapping failure counts,
per-storm numerators/denominators, event macro rates and paired arm differences.
Cache-aware estimates use the bound 2026-09-06 price snapshot and its UTC schedule,
conditional on its continued applicability. Missing/inconsistent cache counts,
reversed clocks, intervals over 24 hours, and intervals crossing a pricing boundary
do not yield a point estimate. Covered subtotals and coverage counts are separate
from conservative peak/cache-miss settlements and unknown reservations; none is an
invoice or an observed account debit. Diagnostic transports yield simulated estimates.

The current implementation freezes the complete recursive Python source inventory,
Python/platform and installed distribution versions, and this execution protocol.
Old manifests, old P1 outcomes and unknown attempt 79
are preserved. Both this preparation and its parent must be regenerated after code
changes; a running experiment uses an immutable execution checkout.
