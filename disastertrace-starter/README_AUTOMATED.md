# Automatically scored first work package

This guide records the first work package. The current implementation and model
collection entry points are described in [README_PRE_API.md](README_PRE_API.md).

This is an offline implementation of the v0.3 research plan: an inherited-label
DisasterBench planning track and a small NHC text replay with deterministic
scoring. No new per-item human annotation or expert review is required. Upstream
labels can still contain errors; automatic validation is not a proof of all
natural-language semantics.

The executed local diagnostic report is [work/REPORT-v2.md](work/REPORT-v2.md).
Its build is `work/build-v2`; command records and individual command logs are in
`artifacts/verification/`. These files are kept locally, not published.

## Run it

Run these commands from this directory. Python 3.10 or later is required. The
automated modules use the standard library, so the source-tree entry point works
without installing model SDKs or the optional GIS dependencies:

```bash
PYTHONPATH=src python -m disastertrace.automated build \
  --references ../references --output work/my-build
PYTHONPATH=src python -m disastertrace.automated run \
  --build work/my-build --track dynamic --backend rule --max-queries 10 \
  --output work/my-rule-run
PYTHONPATH=src python -m disastertrace.automated score \
  --build work/my-build --run work/my-rule-run --output work/my-rule-score.json
PYTHONPATH=src python -m disastertrace.automated report \
  --build work/my-build --scores work/my-rule-score.json --output work/my-report.md
```

The cached source snapshots under `../references` are needed for `build`. There
are no network calls during build/run/score/report. Use new output paths for each
attempt: existing builds, runs, scores, and reports are not overwritten. A failed
attempt can leave a partial directory; retain it and choose another name.

For the installed CLI and the complete test suite:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/disastertrace-auto --help
```

`requirements-verified.txt` records the dependency versions used for the passing
165-test run. To reuse those versions in another environment, install that file
first, then install the project with `pip install --no-deps -e .`. This version
snapshot is not a guarantee of identical wheels across Python versions/platforms.

If the OS Python lacks `ensurepip`, an existing pip with `--python` support can
install into the created environment with
`python -m pip --python .venv/bin/python install -e '.[dev]'`.

## Data and privacy boundaries

The build produces these artifacts:

| Path | Purpose | Model access |
| --- | --- | --- |
| `public/disasterbench_tasks.jsonl` | Task descriptions, all tool schemas, output contract | Allowed |
| `private/disasterbench_references.jsonl` | Unmodified inherited plans for admitted tasks | Forbidden |
| `private/dynamic_references.jsonl` | Answers derived from the replay specification | Forbidden |
| `records/nhc_records.jsonl` | Parsed fields, locators, raw source text | Harness only |
| `episodes/dynamic_episodes.jsonl` | Full schedules, including future evidence | Harness only |
| `profiles/` | Admission counts and quarantine reasons | Analysis only |
| `implementation.json` | SHA256 of the automated Python modules | Reproducibility |
| `implementation_source/automated/` | Exact Python sources used for this build | Reproducibility |
| `source_inventory.json` | Original URLs, commits and source hashes | Provenance |
| `manifest.json` | Build identity and artifact checksums | Reproducibility |

For dynamic evaluation, only `dynamic.render_request()` output is a model
request. It contains the public task rule, numbered delivered texts, checkpoint
time, and the model's actual prior accepted state. It excludes parsed fields,
private answers, and future schedules. It is a fresh request at each checkpoint.
Do not give a model filesystem access to the whole build or the scorer.

The current policy supplies all evidence received so far, including repeated old
reports. It tests evidence selection and state updates; it does not establish
causal reliance on a compressed state carrier or reproduce a same-valid-time
forecast revision experiment.

## Implemented tracks

DisasterBench contains 233 source tasks and 26 tool definitions. Strict automatic
admission retains 230 tasks and quarantines tasks 3, 119, and 191 because of
invalid output references or duplicate steps. Labels are not silently repaired.
All 230 tasks remain in scoring denominators, including missing or invalid
responses. Exact, tool, parameter, and dependency agreement are reported.

This is a derived strict protocol. It inherits one reference plan, is sensitive
to plan order, and does not test actual tool execution or judge equivalent plans.
DisasterBench covers broad disasters; these 230 tasks are not an extreme-weather
subset. CyPortQA contributes a profile of 48 templates, not 48 admitted QA items.

The NHC example uses unchanged Ida public advisories 009, 010, and 011. The parser
checks source identity, date/time consistency, units, ranges, summary ambiguity,
and line evidence. One base schedule and one delayed schedule each have five
checkpoints. Repeated old evidence must not replace a newer issued report.

The requested quantities are latest available *reported observations*: maximum
wind, center latitude/longitude, and minimum pressure. Port reopening time is
always unsupported and must remain unknown. The explicit research rule maps
wind below 100 mph to `monitor`, wind at or above 100 mph to `prepare`, and missing
wind to `request_evidence`. This is a task rule, not an operational safety policy.

Both schedules are controlled releases, not verified historical availability.
The two episodes belong to **one independent storm**, and are development-only.
The three selected records do not establish a population-wide parser success
rate. Expanding independent events is required before statistical comparisons.

## Backends, budgets, and submissions

| Track | Backend | Interpretation |
| --- | --- | --- |
| dynamic | `rule` | Independent regex parser selecting latest issued visible report |
| dynamic | `last-arrival` | Deliberately wrong selection of last received report |
| dynamic | `no-update` | Deliberately retains initial unknown state |
| disasterbench | `reference-fixture` | Copies private labels solely to test the scorer |
| disasterbench | `empty-control` | Emits invalid empty plans to verify zero scores |
| either | `submissions` | Imports external responses with unverified provenance |

Use `--max-queries 10` for all dynamic checkpoints and `--max-queries 230` for all
DisasterBench tasks. The default is only 20. Dynamic budgets count attempted
checkpoint slots across both episodes, including missing/invalid submissions;
exhausted slots remain in the denominator. This is a logical offline budget,
not tokens, money, provider requests, or API rate limits.

DisasterBench submissions are JSONL with exactly these top-level keys:

```json
{"task_id":"disasterbench:1","structured_plan":[]}
```

The empty plan above illustrates the container only and scores zero. Fill the
plan according to the `response_schema` and tool definitions on the public task.
Omitted task IDs score zero. Duplicate or unknown IDs are rejected. Importing
more responses than the explicit budget is rejected rather than truncated.

Dynamic submissions are JSONL containing exactly `episode_id`, `checkpoint_id`,
and `raw_response`. The response is a JSON **string**, preserving the model's
original output, which must parse to exactly `state` and `action`. Every required
field must have `status`, `value`, and `evidence`:

```json
{"status":"known","value":105,"evidence":[{"record_id":"nhc-al092021-public-010","line":21}]}
```

Use the actual numbered line from the request; the above is only a schema
example. Unknown slots require `{"status":"unknown","value":null,"evidence":[]}`.
Markdown fences, extra keys, duplicate JSON keys, nonfinite numbers, booleans
as numeric values, and incomplete state objects are invalid. Invalid/missing
responses preserve the previous accepted carrier but earn zero for that attempt.

```bash
PYTHONPATH=src python -m disastertrace.automated run \
  --build work/my-build --track disasterbench --backend submissions \
  --predictions /path/to/responses.jsonl --max-queries 230 \
  --output work/my-submitted-run
```

Dynamic response collection must proceed checkpoint by checkpoint using the
actual prior response as carrier. Precomputing requests with reference states
would leak answers and invalidate the experiment. The current file importer
reconstructs and logs requests but cannot attest which prompts an external model
actually received. All current runs are marked ineligible for an LLM leaderboard.

Two small files in `examples/automated/` demonstrate the import format:
`dynamic_c0_unknown.jsonl` contains one valid initial response (the other nine
attempts are missing), and `disasterbench_empty.jsonl` contains one deliberately
invalid plan. Both are schema examples, not model outputs.

## Scoring and diagnostics

`grounded_state` requires both the right value/unknown status and the right source
record plus line. `action_accuracy` scores the declared rule on every checkpoint.
`known_answer_coverage` only checks whether known fields were answered, not
whether they were correct. Always read it with correctness and unknown accuracy.

Required-change and preservation metrics are conditional on the model's actual
previous state. Their denominators can differ across backends; they are
diagnostics, not interchangeable aggregate leaderboards. No pooled score combines
the planning and dynamic tracks.

Executed diagnostic expectations are:

| Backend | Grounded fields | Correct actions | Inherited exact plans |
| --- | --- | --- | --- |
| rule | 50/50 | 10/10 | N/A |
| last-arrival | 42/50 | 8/10 | N/A |
| no-update | 18/50 | 2/10 | N/A |
| reference-fixture | N/A | N/A | 230/230 |
| empty-control | N/A | N/A | 0/230 |

These are program/scorer checks, **not LLM performance**. No model calls, model
training, LLM judging, or real emergency tool execution took place.

Source and generated artifact hashes detect accidental changes, not malicious
rewriting of all manifests or truth of a source statement. Run/score refuse code
changes since build; generate a fresh build when modifying the implementation.
The current runner writes completed episode traces and does not yet support
provider-level crash recovery, resumable live runs, or Frontier search.

See `IMPLEMENTATION_STATUS.md` for the exact executed tests and next work item,
and `THIRD_PARTY_NOTICES.md` for sources and attribution.
