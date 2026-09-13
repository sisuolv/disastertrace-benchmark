# Separate E/F Heads: CPU Interface Validation

`monitoring_fixed_v1/heads.py` adds three explicitly selected interfaces:
`e_only`, `f_only`, and `joint`. `model_messages(bundle, head)` returns fresh
messages with exactly the same canonical visible user payload for every head.
Only the system task and required response fields change. The F-only system
does not ask for an E answer; no head provides filled output examples.

`parse_response(raw, bundle, head)` returns an immutable `HeadResponse`.
An E-only result has `forecast=None`; an F-only result has `fact_truth=None`
and `e_status=None`. Missing heads must remain outside their score denominators.
Truth strings reuse aviation's four-way mapping. Forecasts bind to the exact
target hash using the existing typed `Forecast` contract.

The parser rejects missing, duplicate, extra and cross-head fields; JSON
booleans and truth aliases; nonnumeric, nonfinite and out-of-range probabilities;
and incompatible target contracts. This adapter is limited to the native hourly
aviation visibility event contract. It does not generalize scalar forecasting.

## Executed Checks

Both recorded pytest runs pass 105 tests, with zero failures, errors or skips.
Tests restore all 144 real frozen snapshots, verify their original manifest
hashes, compare identical visible inputs and fresh context behavior, and exercise
the parser on explicitly synthetic responses. Visible E states comprise 93
undetermined, 9 supported and 42 refuted snapshots. The latter counts describe
input support, not model correctness.

The initial Ruff check found one import formatting issue. `ruff --fix` and
`ruff format` corrected formatting, after which pytest, Ruff check and Ruff
format check all pass. Raw successful test logs and JUnit results are retained.
`REPORT.json` records the initial lint failure separately.

`INPUT_MANIFEST.json` binds current source dependencies, tests and all original
input fixtures. `PREPARED_MESSAGE_BINDINGS.json` hashes the three unsent message
variants for each real bundle. All `submitted` flags are false.

## Boundary

New model calls: **0**. New GPU jobs: **0**. Existing joint captures reclassified
as E-only or F-only calls: **0**. Frozen GPU source and the portable CPU replay
remain unchanged. These are 48 exposed opportunities repeated under three
evidence conditions; no new independent weather processes were added.

A future comparison needs a separately frozen dispatch/capture manifest and
actual independent calls. Interface acceptance does not establish model gain.
