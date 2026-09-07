# Output contract and budget calibration

This package implements offline preparation for the next development experiment.
It makes zero model calls. The completed P1 comparison, raw responses, failed
answers, costs, and historical manifests remain unchanged.

## What is implemented

- `output_contract.py` provides `legacy_v1` and `explicit_v1`. Legacy requests
  retain their original bytes. Explicit requests append the same output rules
  and JSON Schema to every method's instruction; all other public input fields
  retain the existing evidence, policy, and model-authored carrier behavior.
- `calibration.py` prepares nine configurations, a fixed 270-request schedule,
  54 unsent initial requests, and 1,080 explicitly non-LLM diagnostic responses.
  It never reads a credential or sends a completion request.
- The diagnostic controls cover correct extraction, stale last-arrival handling,
  no-update behavior, and invalid responses that must not replace accepted state.
- Verification rebuilds the complete schedule, initial wire requests, diagnostic
  responses, scoring projections, and scores, and checks the exact plan and file
  inventory against the package hashes and implementation-matching build.
- A tested aggregate-count screening function implements the proposed common
  token-budget rule. It does not authenticate supplied counts or recommend a live
  budget without separately audited model evidence.

The public contract explicitly types action as a string enum, requires all five
state fields, describes known/unknown values and citation locators, and rejects
extra keys in its declared shape. It supplies no filled answer example or
event-specific label. The frozen answer parser remains authoritative. Known
values with empty evidence remain structurally accepted but receive no grounded
credit; prompt clarification does not change the scoring rules.

See `docs/OUTPUT_CONTRACT_V1.md` for the full contract and its lexical boundaries.

## Proposed experiment

| Arm | Contract | Maximum output tokens | Planned calls |
| --- | --- | ---: | ---: |
| legacy_4096 | Original | 4096 | 90 |
| explicit_4096 | Explicit common contract | 4096 | 90 |
| explicit_8192 | Explicit common contract | 8192 | 90 |

Each arm covers snapshot, structured_state, and answer_history on Ida, Florence,
and Dorian, both existing branches and every checkpoint. There is one fresh
repeat and no heldout inference. The original P1 run is historical context, not
a reused concurrent control. Thinking remains enabled at high reasoning effort;
no temperature override or provider structured-output mode is introduced.

Arm and method orders rotate across storms. Every branch starts with an empty
carrier and uses only that configuration's accepted answers. Later live requests
cannot be materialized before their actual preceding answers exist; diagnostic
answers and their prepared requests must never be reused as live history.

The final screening rule requires a complete, independently audited 270-response
matrix. In every method a candidate cap must produce at least 29/30 schema-valid
responses and at most one length-finish response. Select the smallest qualifying
cap for all methods; incomplete data or no qualifying cap produces no selection.
This is a development screening threshold, not proof of population reliability.

The proposed new-experiment conditional allowance is USD 3, with at most 270
attempts and no automatic retries. It is not an authorization or a guarantee of
batch completion. Captured peak-rate pending reservations are USD 0.46678016 at
4096 output tokens and USD 0.47218688 at 8192. Rates and model limits must be
revalidated before any future live launch. The old unresolved P1 charge remains
in its own ledger and is not settled by this preparation.

Full protocol: `docs/CALIBRATION_PROTOCOL_V1.md`.

## Reproduce offline

Use fresh output paths when repeating preparation; existing outputs are refused.

```bash
.venv/bin/disastertrace-auto build --references ../references --nhc-snapshot ../references/nhc_cohort_v1 --output work/build-calibration-v1
.venv/bin/python -m disastertrace.automated.calibration prepare --build work/build-calibration-v1 --provider-config artifacts/p1_deepseek_development/provider.json --output work/calibration-v1-preparation
.venv/bin/python -m disastertrace.automated.calibration verify --output work/calibration-v1-preparation
```

New source files change the implementation identity, so this package uses a new
build. Source acquisition, event splits, source parser, answer parser and both
scorers retain their existing versions. The independent audit compares the new
build's non-implementation data with the preserved P1 build.

Outputs are under `work/calibration-v1-preparation/`: `plan.json`, `contract.json`,
`schedule.jsonl`, `configs/`, `initial_requests.jsonl`, `diagnostics.json`,
`budget_proposal.json`, `rehearsals/`, and `manifest.json`. Command and test records
are under `artifacts/calibration_v1/`.

## Verification results

The final full suite passes 684 tests in 54.67 seconds, with no skips. Scoped
strict Ruff, formatting and dependency checks pass. Independent review passes
6,979 checks, including all 359 entries in the previous P1 archive, all 20
unchanged existing automated modules, 15 unchanged build data artifacts, the
new 128-artifact preparation, all sequential traces and both frozen scorers.

Final records: `artifacts/calibration_v1/root_checks/final_v2/result.json`,
`artifacts/calibration_v1/execution_v2/commands.json`, and
`artifacts/calibration_v1/independent_audit/final_result.json`.
Earlier failing scope-drift regression, initial lint output, and an incorrect
CLI invocation remain recorded alongside the corrected executions.
The final archive manifest, result and checksum verification are in
`artifacts/calibration_v1/package/`, with snapshots of documentation and tests.

## Actual traces and scoring projections

Every rehearsal saves its actual explicit/legacy request and its program-produced
raw answer in `trace.jsonl`. Sequential verification regenerates the request from
the same checkpoint's public evidence and preceding accepted answers before
scoring. It rejects altered instructions, state, history, or raw-answer accounting.

The frozen scorer independently reconstructs legacy instructions. For this
offline diagnostic use, a separate `scoring_projection.jsonl` replaces only the
verified instruction with its legacy counterpart. Evidence, policy, carriers,
answers and failure denominators stay identical. The actual trace is preserved;
both trace hashes and the projection rule are recorded alongside full v1 and v2
scores. A projection is not the model's actual exposure or proof of live collection.

## Remaining work before live calibration

This package has no live launcher or calibrated-model result. Existing live
collectors and auditors still use the legacy request renderer. Before any paid
calibration, implement and independently test the contract-aware collector,
durable schedule, cumulative budget guard, and collection audit; freeze the new
launch package and bind actual scope/budget authorization. Do not use the old P1
runner, its consumed continuation claim, or diagnostic carriers for this matrix.

No new per-item human annotation or LLM judge is required. Subsequent task
expansion remains partial updates, same-window corrections, and recoverable
missing evidence after calibration, with the seven heldout storms reserved.
