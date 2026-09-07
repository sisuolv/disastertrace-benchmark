# First DeepSeek live trial

Follow-up: [README_SCORING_V2.md](README_SCORING_V2.md) records the completed
versioned offline rescoring of these same answers. The original trial and v1
scores below remain historical results; no additional model calls were needed.

On 2026-09-06, the user supplied a DeepSeek credential and requested a small test
of `deepseek-v4-flash` with `reasoning_effort=high` and thinking enabled. One SDK
connectivity request and ten Ida benchmark requests completed successfully. No
heldout model requests or other model/method combinations were executed.

## Actual results

The SDK probe returned `Hello! How can I help you today?` in 2.495 seconds,
reporting 89 prompt tokens and 62 completion tokens (52 reasoning tokens).
The benchmark uses the independent journaled HTTP collector with the same explicit
model/reasoning/thinking options. It completed ten checkpoints in about 74 seconds.

| Metric | Result |
| --- | --- |
| Valid output schema | 10/10 |
| State values/statuses | 50/50 |
| State plus strict reference citation | 49/50 |
| Research-rule actions | 10/10 |
| Appropriate unknown fields | 18/18 |
| Known-field answer coverage | 32/32 |
| Required changes | 22/22 |
| Eligible state preservation | 18/18 |

All ten responses ended with `finish_reason=stop`. The experiment covers one
public development storm, two controlled delivery branches, and one method
(`structured_state`). It does not establish heldout generalization, method
superiority or a cross-model ranking.

The one citation deduction exposes a reference restriction: at the base branch's
final checkpoint, the model correctly answered 105 mph and cited advisory 011,
line 88: `Maximum sustained winds are near 105 mph (165 km/h) with higher`.
The frozen scorer accepts only summary line 21:
`MAXIMUM SUSTAINED WINDS...105 MPH...165 KM/H`.
Both lines support the wind value. The recorded 49/50 is preserved under the
frozen exact-locator rule; it must not be described as a demonstrated unsupported
weather claim. Equivalent citation handling is a development issue for a future
version, with new tests/builds and separate historical scores.

## Usage and cost

All eleven responses reported usage. Combined totals, including the SDK probe:
51,024 input tokens, 10,734 output tokens, 61,758 total tokens. Output already
includes 9,125 reported reasoning tokens. Input consists of 15,104 cache-hit and
35,920 cache-miss tokens.

Using the official Sunday off-peak prices retrieved for this trial, the estimate
is **USD 0.015092568**. This is not a provider billing receipt. Raw usage and the
saved price-source hash are in `artifacts/deepseek_probe_v1/live_result.json`.
No currency budget enforcement is claimed; the ten-checkpoint sample uses an
attempt cap, a 262144-byte request guard and 40960 total output-token reservations.

## Reproduction and credential handling

OpenAI SDK 3.8.0 was installed into the existing `.venv`; `pip check` passes.
The environment snapshot is in `artifacts/deepseek_probe_v1/requirements.txt`.
Official DeepSeek documentation and fetch hashes are in the adjacent `docs/`.
The API response reports `deepseek-v4-flash`; the documentation's underlying
version label is not independently authenticated by that alias response.

The credential was read without terminal echo and held only in the calling
process/environment. It was not put in a project configuration, script or log.
The sample scripts use `DEEPSEEK_API_KEY` if set, otherwise prompt without echo.
Do not put a credential in the example config.

These commands make real requests. Use new output paths:

```bash
.venv/bin/python examples/probe_deepseek.py --output work/my-deepseek-probe
.venv/bin/python examples/run_deepseek_ida.py \
  --build work/build-deepseek-v1 \
  --config configs/provider.deepseek-flash.example.json \
  --output work/my-deepseek-ida-state
```

The example config adds typed `reasoning_effort` and `thinking_type` options;
arbitrary request-body overrides are rejected. Temperature is omitted because
DeepSeek documents it as ineffective in thinking mode. Response reasoning is
retained in the provider body but is not passed as the next answer carrier.
No output repair or automatic retries are performed.

The new build is `work/build-deepseek-v1`; all 15 data artifacts and the source
parser match the pre-API build. Existing build/run/score history is preserved.
The full updated suite passes **483 tests, zero skips**; test logs and source
identity are in `artifacts/deepseek_probe_v1/offline_checks/`.

Actual traces, audit and scores: `work/deepseek-ida-state-v1/`.
Compact report: `artifacts/deepseek_probe_v1/REPORT.md`.
The broader pilot plan and remaining model/method matrix are in README_PRE_API.md.

Proposed next steps are in [OPTIMIZATION_ROADMAP.md](OPTIMIZATION_ROADMAP.md):
first fix and version evidence-support scoring with offline historical rescoring,
then calibrate methods on development events before extending capabilities and
event coverage. This roadmap is a proposal; it does not change the frozen
protocol or the scores reported here.
