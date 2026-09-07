# Explicit P1 Background Continuation

This package prepares one separate amendment to interrupted P1. Preparation is
offline. It does not authorize model calls. The original 90-request no-retry
experiment remains immutable and separately reportable.

The original run has 79 admitted attempts and 78 received answers. Original
attempt 79, answer_history / Florence delay / c3, has no received response or
usage. Its USD 0.46678016 reservation remains retained even if its explicitly
authorized reissue receives an answer.

The proposed amendment permits at most 12 additional provider calls, 91
cumulative attempts, 372736 cumulative requested output tokens, and a USD 1.5
conditional cumulative allowance. It reuses all 78 received answers, including
20 invalid answers across the three methods. No received invalid answer is
retried. The first new request must exactly match the unresolved request.

## Offline Preparation

Run from the project root:

```bash
.venv/bin/python artifacts/p1_deepseek_development/background_resume/resume_background.py prepare \
  --experiment artifacts/p1_deepseek_development/experiment.json \
  --source work/p1-deepseek-development-v1 \
  --output artifacts/p1_deepseek_development/background_resume/prepared
```

The package binds the frozen experiment, runner, reporter, provider config,
rates, original source tree, derived prefix, and this continuation script.
The 18-answer prefix preserves raw answers, invalid answers, and accepted state
history. Only the derived prefix excludes original local request 19; explicit
provenance retains that request, original counters, and cumulative ledger row 79.
The independently audited prefix is the unchanged collector's resume input.

## Authorization And Launch

Only after the user actually approves the amended scope, create an authorization
JSON record containing these fields:

- `authorized`: Boolean true.
- `original_experiment_id`: the original experiment ID.
- `amendment_id`: the prepared amendment ID.
- `allowance_usd`: string `1.5`.
- `max_additional_provider_attempts`: integer 12.
- `max_cumulative_provider_attempts`: integer 91.
- `explicit_retry_original_attempt`: integer 79.
- `user_message`: the actual nonempty user approval text.

Then run:

```bash
.venv/bin/python artifacts/p1_deepseek_development/background_resume/resume_background.py launch \
  --amendment artifacts/p1_deepseek_development/background_resume/prepared/amendment.json \
  --authorization PATH_TO_ACTUAL_AUTHORIZATION.json \
  --output work/p1-deepseek-background-continuation-v1 \
  --live
```

The launcher uses `DEEPSEEK_API_KEY` if present, otherwise a non-echoing terminal
prompt. It passes the credential in the child process environment, without
writing it to arguments, configuration, or logs. An exclusive claim tied to the
canonical prepared package prevents repeated launch to another output directory.
The child uses a new session, closed stdin, and durable output logging.

Monitor `pid.json`, `status.json`, `budget_ledger.json`, and
`runs/answer_history/collection/summary.json` in the new output. `exit.json`
records a normal worker exit, including sanitized failures. Abrupt process death
or another machine restart can leave historical running flags and no exit file;
those flags do not authenticate a live process. No automated relaunch occurs.

The collector, independent audit, offline import, v1 score, and verified v2
rescore retain all 30 answer_history opportunities. Completed methods are
referenced through symlinks to immutable original outputs. No scoring rule,
model parameter, source evidence, or heldout set changes.

## Accounting And Reporting

The cumulative ledger retains every original row verbatim and admits new attempts
starting at 80. Its original pending row stays pending and reserved; the runtime
active marker describes only a new in-flight continuation call. A failure,
missing usage, model drift, or admission denial stops further calls without
automatic retry. The full-context peak-rate guard remains conditional on
provider rates and limits, rather than a billing guarantee.

The original unresolved attempt makes total incurred expense unknown, including
when 90 answers are eventually available. Report received-answer cost subtotals
separately. The existing frozen comparison reporter assumes original accounting;
do not pass it the amended 91-attempt ledger as if it were the original protocol.
An amended report must explicitly reconcile the original 79 rows, the resumed
collection's 18 copied rows, all new attempts, and the retained uncertain row.

## Verification

`test_resume_background.py` forbids real HTTP and credential prompts. It tests
prefix provenance and tampering, all received answers and invalid answers,
retained reserves from the first durable ledger write, the 91/92 request cap,
first-request identity, legitimate equal-payload checkpoints, full offline
collection/scoring, failure without retry, authorization, exclusive launch,
credential-free artifacts, and persisted sanitized worker failure status.

```bash
.venv/bin/python -m pytest -o addopts= -q \
  artifacts/p1_deepseek_development/background_resume/test_resume_background.py
```
