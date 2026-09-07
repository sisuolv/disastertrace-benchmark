# P1 DeepSeek development comparison: execution protocol

Registered before model outcomes on 2026-09-06. The user approved the next
90-request development comparison after P0. This is one calibration repeat,
not a heldout ranking or a cross-model evaluation.

## Frozen coverage and settings

- Three development storms: AL092021 (Ida), AL062018 (Florence), AL052019 (Dorian).
- Both existing base and delay branches, five checkpoints each: 30 per method.
- Execution order: snapshot, structured_state, answer_history; one fresh repeat
  per cell. The previous ten Ida responses are not reused or pooled.
- deepseek-v4-flash at https://api.deepseek.com, high reasoning, thinking enabled,
  max_tokens=4096, no temperature override, timeout=60 seconds.
- Original English public prompts, numerical values, task schema, thresholds,
  evidence delivery order and source parser remain unchanged. Each method
  receives cumulative delivered evidence and only its declared actual-answer
  carrier. Invalid answers are retained; wrong valid answers propagate.
- Primary derived scoring: dynamic_score_v2.0 with nhc_equivalent_support_v2.
  Retain v1, exact collection audit and versioned offline v1/v2 comparisons too.

The new build is checked against all 15 original non-implementation data
artifacts. Its implementation must match the previously verified 611-test
source identity. The experiment manifest separately binds the external runner,
provider configuration, price snapshot, protocol and preflight evidence.

## Bounded calls and conditional spending control

At most 90 provider attempts and 368,640 requested output tokens are permitted
across all methods, with at most 30 attempts and 122,880 output reservations per
method. The existing request-body guard is 262,144 bytes. No greeting probe,
automatic retry, failed-cell selective repeat or heldout request is planned.

The external sequential runner uses a USD 1 local allowance. Before each call,
it reserves 1,048,576 prompt tokens at the documented peak cache-miss rate of
USD 0.44 per million, plus 4,096 output tokens at USD 1.32 per million:
USD 0.46678016 per pending request. This uses the documented model context
ceiling rather than treating request bytes as an exact token count.

Only a valid received usage record releases the unused reservation. Settled
guard accounting conservatively charges all prompt tokens at the peak miss
rate, regardless of cache or off-peak discounts. Uncertain network failures or
missing/invalid usage retain their reservation and halt subsequent HTTP calls.
Reported output/context-cap violations or response model alias drift also halt
the batch after preserving any received answer. Pre-send rejection records its
actual guard reason and does not claim the request reached the provider.

This local control is conditional on the captured official context/prices and
provider cap enforcement; it is not a provider-side account spending limit or
invoice guarantee. Standard provider metadata keeps its original no-hard-money-
cap declaration. The separate ledger identifies the wrapper's stronger local
reservation policy without relabeling the original collector.

## Failure accounting and reporting

Schema-invalid answers remain failed checkpoints and are not repaired. A
provider error or global guard stop ends further HTTP calls; remaining planned
checkpoints still appear as failed/unsubmitted opportunities in the experiment.
No uncertain request is reissued. If infrastructure prevents completing the
matrix, report that limitation before interpreting method differences.

The unchanged provider rejects malformed provider envelopes, including malformed
usage, before returning a completion. Those failures retain a sanitized error
and pending reservation, but their raw error body is unavailable. This differs
from an invalid benchmark answer inside a valid provider envelope: that answer
is retained verbatim and scored as a failed response. No new error-body archive
or credential-handling path is introduced by the external guard.

Report all denominators, known-only grounding, unknown accuracy, fixed Gold
changes/preservation, source refresh, conditional recovery, per-storm scores,
paired method differences and evidence failure reasons. A zero denominator has
a null rate. The independent unit is the storm, not an individual checkpoint.
One repeat across three development storms is descriptive calibration only.

Record the returned model alias and available version/response timestamps,
raw request/response hashes, finish reasons, usage and successful-request
transport latency. Latency excludes setup/scoring and has no observation for a
transport failure. Cost estimates use actual cache-hit/miss/completion counts
and the captured applicable price window. Reasoning tokens are already included
in completion tokens and must not be billed twice in the estimate.

The fixed method order may affect provider cache and latency; report cache
usage and order rather than claiming an intrinsic speed/cost advantage. Every
method has full delivered evidence, so this does not isolate memory necessity.
The credential is obtained in process memory from an environment variable or
non-echoing prompt and is not written into the experiment configuration or logs.
