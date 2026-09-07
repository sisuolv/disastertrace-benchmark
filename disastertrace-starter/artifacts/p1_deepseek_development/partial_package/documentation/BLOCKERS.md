# Blockers

## Current P1 status after the machine restart

The original P1 live capture is interrupted, with 79 admitted requests and 78
responses. Snapshot and structured_state completed; answer_history has 18/30
responses, one uncertain request and 11 unattempted checkpoints. Offline
finalization and reporting are complete and independently verified. Entry:
`README_P1_DEEPSEEK.md`. All original capture/history files remain unchanged.

The user requests background resubmission. The remaining constraint is the
explicit budget/retry amendment, not a missing credential. The old USD 1 guard
has USD 0.30435328 settled and USD 0.46678016 reserved for the uncertain request;
one further reservation would reach USD 1.23791360. A concrete USD 1.5, maximum
12-additional/91-cumulative-attempt proposal, including one explicit uncertain
retry, is awaiting the user's answer. Received invalid answers will not be
retried. Proposal: `artifacts/p1_deepseek_development/restart_proposal.json`.

The actual total cost is unknown; USD 0.123358592 estimates only the 78 received
responses. The partial answer_history score includes missing observations and
cannot establish a method ranking. Output truncation and an incompletely typed
public output contract are development-calibration findings, not evidence that
all failed cases contain false weather claims. No new per-item human review or
LLM judge is required to address them in a new version.

## Previous P0 completion and persistent research limitations

P0 equivalent-citation scoring and immutable offline migration are complete.
The full suite passes 611 tests, zero skips; archived replay, collection audit
and derived-package verification pass. Current entry: README_SCORING_V2.md.
The earlier authorized DeepSeek trial remains one SDK probe plus ten Ida
development requests; P0 makes zero additional model requests.
Records: artifacts/deepseek_probe_v1/ and work/deepseek-ida-state-v1/. Prior
pre-API artifacts and their original implementation sources are preserved.

There is no missing credential/model configuration blocker for the completed
bounded trial. The secret was held only in the calling process and not persisted
in project files. Larger comparisons still need model/method scope and budget
fixed; this trial did not execute the full two-model or heldout matrix.

The strict-citation finding is resolved under a separately versioned restricted
evidence policy: the same ten saved responses score 50/50 overall and 32/32
known-only grounding in v2. Original v1 stays 49/50 and is exactly reproduced.
One field changes because a supported body citation is now accepted. Results:
work/deepseek-ida-rescore-v2/. This is not a model improvement. Arbitrary prose,
new languages/source genres and contradictory cross-paragraph text remain
outside the declared support grammar; evaluator_unverifiable is reported
separately from demonstrated false model claims.

The collector enforces attempts, request-body bytes and aggregate requested output
token reservations, with independently audited safe-prefix resume. These are not
total-token or currency caps. Exact DeepSeek model/high-effort/thinking options
were documented and successfully exercised; full context limits and other
providers remain untested. The USD 0.015092568 usage-based estimate is not a
billing receipt. Docs and price snapshots are retained with the trial artifacts.

The 12-event source catalogue yields 10 complete events (3 development, 7
heldout). Four parser rejections are retained: three older Matthew publisher
headers and a Harvey remnants advisory. This version does not broaden the frozen
parser or replace rejected events. These are documented coverage limits, not
blockers or reasons to require per-item human review.

The cohort uses controlled release times and shared task templates. Exact and
fixed-threshold lexical near-duplicate screening now passes; historical public
availability, pretraining decontamination, representative event coverage and broad
extreme-weather generalization remain unestablished. The heldout
last-arrival control gets all coarse actions right despite only 84% grounded
field accuracy, so action accuracy is not sufficient as a standalone metric.

The legacy starter has previously documented defects. Its original tests will be retained, but passing them is not certification of the new protocol or of real model behavior.
