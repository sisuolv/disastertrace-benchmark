# P2 captured execution and offline acceptance

Subsequent live results are in [README_P2_DEEPSEEK_V1.md](README_P2_DEEPSEEK_V1.md):
270 captured responses, independent audit passed, common format screen failed.
This document preserves the preceding offline engineering stage and its proposal.

The P2 controlled weather task now has its own durable collector, independent
captured-response audit and direct scoring/report pipeline. This extends the
[controlled task](README_CONTROLLED_V1.md) after the completed
[T6 calibration](README_T6_CALIBRATION_V1.md).

This stage executes no paid model request. Program transports and local HTTP
fixtures validate implementation behavior; their scores are not LLM results.
Current validation evidence is indexed in
[the delivery record](artifacts/p2_execution_v1/README.md).

## What this stage adds

1. Strict P2 prepared-byte capture with bounded response storage, credential
   reflection filtering, no redirects/retries, and a separate total deadline.
   The NHC public wrapper still rejects P2 requests, and P2 rejects NHC requests.
2. One execution registry, one writer, one hash-chain journal and one shared
   Decimal budget across all 270 slots. A copied output cannot create another
   production launch claim for the same execution.
3. Sequential reconstruction of every model carrier from saved raw responses.
   Invalid full answers retain the prior valid carrier. Valid factual errors
   propagate unchanged. No Gold repair or cross-trajectory history is allowed.
4. Independent rechecking of schedule, evidence, carrier, wire bytes, captured
   completion, timestamps, model identity, usage and all budget arithmetic.
5. Direct captured-result scoring through the unchanged P2 metric definitions.
   Reports bind their audit and capture hashes. The public diagnostic scorer
   still rejects model origins; relabeling a program trace does not admit it.
6. Recomputed report verification and a complete offline reproduction command.
   Missing opportunities retain fixed denominators and explicit execution status.

The implementation resides in `src/disastertrace/controlled/execution.py`,
`provider_capture.py`, `live.py`, `live_audit.py` and `live_report.py`. Shared
transport primitives live in `automated/provider_capture.py`; its existing
NHC validation boundary remains intact. The common metric arithmetic is private
to the separately checked diagnostic and captured-result entry points.

## Frozen first-model proposal

| Item | Proposed P2 scope |
| --- | --- |
| Model | `deepseek-v4-flash` |
| Settings | high reasoning effort, thinking enabled, no temperature |
| Methods | snapshot, structured_state, answer_history |
| Task scope | 18 development episodes, 5 checkpoints, 3 methods |
| Request scope | at most 270 attempts, one repeat, no retries |
| Output cap | common 8192, initially inherited from T6 |
| Requested output reservation | 2,211,840 tokens |
| Conditional allowance | USD 3 for this separate execution |
| Maximum one-request reserve | USD 0.47218688 at the saved peak/cache-miss rates |
| Network limits | 180-second socket timeout and 180-second total deadline |
| Heldout and second-model calls | zero in this proposal |

The conditional allowance may stop an incomplete run; it does not guarantee all
270 requests or equal an invoice estimate. Actual authorization and a fresh
matching price applicability attestation are separate launch inputs. T6's
consumed scope cannot authorize P2. If current rates or settings change, create
a new execution identity before dispatch.

The format screen is fixed in advance for each family-by-method cell: 30 slots,
at least 29 schema-valid answers and at most one length finish, with a complete
audited matrix. Passing a program rehearsal does not measure P2 model reliability.
An actual failing matrix is retained in full; changing settings creates a new
common execution, rather than selectively retrying failed questions.

## Reproduce without external network access

From the installed project environment, choose a fresh output directory:

```bash
.venv/bin/python scripts/reproduce_p2_execution.py \
  --output work/p2-execution-acceptance-new
```

The script scrubs credential-like environment variables and blocks external
network/DNS in subprocesses, while allowing loopback socket fixtures. It runs
the full test suite, lint/format/dependency checks, a fresh NHC build, P2 package
preparation and verification, P2 execution freezing, all 270 diagnostic slots,
independent audit, direct scoring and report recomputation. Every command, exit
code, duration and log hash is saved. A skipped test is explicitly recorded as
not run; the release archive requires a full-suite acceptance result.

The final status also compares task episodes, micro fixtures, schedule, Gold,
initial public requests and parent source bytes with the previous frozen P2
package, and compares all 30 historical program scoring configurations. New
implementation/content IDs do not imply that those semantic task artifacts changed.
When ignored historical runtime directories are absent from a Git checkout,
the verifier can read their bytes from the checked archives without extraction.
Pricing bytes resolve from a local saved document and must match the recorded
hash; the historical original-machine path is provenance metadata only.

## Inspect and recover an existing run

These commands are read-only except that recovery can append a verified local
decision for an already captured response:

```bash
.venv/bin/python -m disastertrace.controlled.live verify \
  --execution work/p2-execution-acceptance-002/execution
.venv/bin/python -m disastertrace.controlled.live audit \
  --execution work/p2-execution-acceptance-002/execution \
  --run work/p2-execution-acceptance-002/rehearsal
.venv/bin/python -m disastertrace.controlled.live verify-report \
  --execution work/p2-execution-acceptance-002/execution \
  --run work/p2-execution-acceptance-002/rehearsal \
  --output work/p2-execution-acceptance-002/report
```

`recover --execution ... --output <existing-run>` is offline only. It never
reads credentials or sends a request. A saved reservation before send intent
can later be dispatched once by an explicitly resumed collector. A saved send
intent without a response remains unknown and blocks further sends. Damaged
journals fail validation. Neither machine restarts nor lock release establish
that an uncertain provider request was never processed.

`run` and `resume` are actual network commands and require separate
`--authorization` and `--price-attestation` files matching the frozen execution.
Preparation writes unapproved templates. There is no automatic launch, retry,
scope reset or migration of diagnostic history into a real run.

## How to read the reports

`report/report.json` includes per-method totals, per-family and per-source-group
scores, matched branch pairs, the predeclared reliability screen, full coverage,
overlapping failure categories, verified usage, latency and cost estimates.
`actual_trace.jsonl` preserves the actual P2 request and raw final answer with
capture provenance. It is not a legacy scoring projection.

Every method retains 90 checkpoints and 360 field opportunities: 282 known and
78 unknown. Update, preservation, source refresh, recovery and scope opportunity
sets come from Gold, independently of earlier model correctness. Missing,
unresolved or invalid responses do not disappear from the denominators.

The costs of injected/local fixtures are explicitly diagnostic. Actual price
estimates require verified usage and cache counts within an unambiguous UTC
pricing interval. Unknown reservations remain separate; this stage does not
resolve the original P1 unknown charge. Local hashes bind captured artifacts,
but are not external signatures authenticating a model provider.

P2 remains a controlled evidence-update task. Initial source inheritance does
not make its generated correction chains historical NHC corrections. Three
source groups, dependent branches/checkpoints and one repeat support descriptive
comparisons; they do not establish broad weather generalization or statistical
significance. No per-item human annotation or LLM judge is introduced.

## Next experiment

The next executable research step is the separate, complete P2 DeepSeek
development matrix under the frozen proposal. Before dispatch, bind the user's
actual authorization and current matching price evidence to that execution,
then retain and report every received response. Evaluate format reliability
before interpreting differences in update or source-tracking accuracy. A
second model and all heldout inference remain subsequent experiments.
