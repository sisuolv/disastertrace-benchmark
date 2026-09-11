# Active Forecast v1

An offline kernel for finite, fixed-target weather-product evidence tasks.
It implements the D1-D2 milestone of the closed V5 feasibility roadmap.
Historical modules, product snapshots and model scores are unchanged.

## Contract

- `Episode`: strict, immutable schema `active_forecast.v1`, at most eight cards.
- `RevisionTarget`: one valid instant, two distinct ordered versions, exact delta.
- `CountTarget`: count threshold over fixed scalar supports, including unknowns.
- `AreaTarget`: exact bounds over disjoint rectangles covering one complete frame.
- `Evaluator`: reference, sufficiency, inclusion-minimal certificates, extension
  cost and score. Certificate search sees the private complete pool and is an
  ex-post bound, not an online acquisition policy.
- `public_view`: a whitelist DTO for the **exact-product-value** representation.
  Catalog scope is public; unread values, quality, private source locators,
  group/split labels, source hashes and certificates are excluded. This is field
  projection, not a claim that a deployed model runtime has been isolated.

Internal numbers are `Fraction`. Python callers supply integers, `Decimal`,
`Fraction`, decimal strings or rational strings. Binary floats and booleans are
rejected. `provenance.load_json` reads decimal tokens exactly, rejects duplicate
JSON keys and rejects NaN/Infinity. Serialization emits canonical `n/d` strings;
the emitted JSON schemas describe that wire representation. Use `load_json`
followed by `Episode.model_validate` for noncanonical JSON decimal input.

All instants normalize to UTC. Station days and product map dates remain calendar
dates, without invented UTC intervals. For `archive_delivery`, eligibility uses
logical delivery steps and `as_of` must be null. For `historical_asof`, the upper
bound of proved public availability and any known issue time must precede `as_of`,
and logical delivery must have occurred. Capture time and forecast valid time
do not substitute for public availability. Missing clocks require a reason.

Records match normalized support, entity, variable, unit and the requested
revision versions. Ambiguous overlapping compatible records are rejected; no
implicit latest-version fusion is performed. Partial valid raster counts retain
unobserved pixels in the denominator. Missing/invalid scalar values stay unknown.

## Python

```python
from disastertrace.active_forecast import Episode, Evaluator, public_view
from disastertrace.active_forecast.provenance import load_json

episode = Episode.model_validate(load_json("episode.json"))
evaluator = Evaluator(episode)
visible = public_view(episode, read_ids=[], budget=2)
score = evaluator.score([], {"decision": "unknown", "citations": []}, budget=2)
```

`read_ids` denotes successfully acquired cards, not requested or attempted reads.
Duplicate/inaccessible reads and overspent budgets raise errors. Malformed
answer objects receive `valid=false`. Transport errors and raw JSON parse errors
must be recorded by a future model adapter before passing a parsed answer here.
The scorer does not repair answers or invoke an LLM judge.

## Commands

Run from `disastertrace-starter` with the existing `.venv`:

```bash
PYTHONPATH=src .venv/bin/python -m disastertrace.active_forecast schema
PYTHONPATH=src .venv/bin/python -m disastertrace.active_forecast validate episode.json
PYTHONPATH=src .venv/bin/python -m disastertrace.active_forecast public episode.json --budget 2
PYTHONPATH=src .venv/bin/python -m disastertrace.active_forecast score episode.json --budget 2 --answer answer.json
```

Repeat `--read CARD_ID` for acquired cards. `validate` checks schema and temporal
eligibility; it does not independently establish source truth or availability.
Source byte verification and provider-specific fact checks occur in the importer:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m disastertrace.active_forecast replay-legacy \
  --bundle ../plans/v5_0910_feasibility_12h_20260910 \
  --output artifacts/active_forecast_core_v1/reviewer_01
```

The destination must not exist and must be outside the frozen bundle. Outputs
include complete private product records and offline references; do not publish
them as model inputs. Source locators bind repo-relative paths and SHA-256 to
whole files, RFC 6901 pointers, half-open byte ranges or C-order uint8 frame tiles.
Path escapes, mismatched bytes and unresolved selectors fail closed.

## Scope And Limits

The importer is intentionally specific to 104 frozen development episodes. It
rechecks NHC wind rows in raw advisory bytes, GHCN values and quality flags in raw
JSON, and SEVIR counts in raw event bytes. USDM bindings reach the original ZIP
and frozen point derivation; this milestone does not rerun polygon operations.
No NHC outcome file is loaded. All imported historical availability stays null.
Only NHC issue instants are established; SEVIR frame/USDM map dates are valid
supports, and the GHCN archive marker is not an issue instant.

Current rectangles concern a uniform pixel lattice. Their fraction is not an
ellipsoidal geographic area estimate. The eight-card cap is deliberate: larger
pools require an explicitly different certificate algorithm and validation.
The grouping registry, source admission, native images/tools, acquisition receipts,
model adapter and release protocol remain subsequent milestones.

Execution evidence and the Chinese handoff are in
`artifacts/active_forecast_core_v1/README_CN.md` (relative to the package root).
