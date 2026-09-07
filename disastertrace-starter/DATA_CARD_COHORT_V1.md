# NHC Atlantic pilot cohort v1

Date: 2026-09-06. Cohort ID: `nhc-atlantic-pilot-v1`.
Build ID: `204681b7be7600a23ad57a7517e2ce5847d2bb5746d978d7b4a144775752f484`.

The current pre-API build is documented in README_PRE_API.md. All 15 data
artifacts are byte-identical to this cohort build; only implementation changes.
The later independent audit and exact/normalized/near-duplicate results are in
`work/pre-api-v1/dataset_audit.json` and `docs/DATA_AUDIT_METHOD.md`.

## Purpose and provenance

This selected cohort tests text evidence selection, state updates, grounded
reported observations, unsupported information, and an explicit research rule.
It is an engineering/research pilot, not a representative extreme-weather sample
or a reconstruction of actual port operations. There are no new per-item human
labels, human reviews, LLM-generated facts, or LLM-judge scores.

All source texts are official NHC public advisories. Acquisition retains the
original HTML, the unchanged text inside the unique PRE element, URLs, retrieval
timestamps, content hashes, and per-attempt records. The catalogue's exact bytes
are frozen before the first request. The snapshot manifest uses a raw-file SHA256
for `catalogue_sha256`; derived cohort records use a canonical-JSON fingerprint
of the same catalogue object. These hashes serve different serialization bases.

Source snapshot: `../references/nhc_cohort_v1/`. Raw catalogue hash:
`feef1008e7b3920bd2f42d5cd1424a9100d791bb46e5f151ec49d5d59146c1d9`.
The parser's source-file hash is unchanged from `work/build-v2`.

Gold is `generated_by_spec`; facts are `derived_from_source`; delivery schedules
are `controlled_release`. Source issue time and current retrieval time do not
prove historical public availability. Reports are successive observations, not
corrections for the same forecast valid time.

## Selection and exclusions

Twelve named Atlantic storms, spanning 2016-2024, were selected purposefully.
Advisories 009/010/011 were specified uniformly before download. Equal advisory
numbers do not imply equal intensity, landfall phase, or task difficulty.

| Storm | ID | Frozen split | Outcome |
| --- | --- | --- | --- |
| Ida | AL092021 | development | admitted |
| Harvey | AL092017 | development | excluded: advisory 011 is a remnants product |
| Florence | AL062018 | development | admitted |
| Dorian | AL052019 | development | admitted |
| Matthew | AL142016 | heldout | excluded: uppercase historical publisher header |
| Irma | AL112017 | heldout | admitted |
| Maria | AL152017 | heldout | admitted |
| Michael | AL142018 | heldout | admitted |
| Laura | AL132020 | heldout | admitted |
| Ian | AL092022 | heldout | admitted |
| Idalia | AL102023 | heldout | admitted |
| Beryl | AL022024 | heldout | admitted |

All 36 downloads succeed. Thirty-two records pass the frozen parser; 30 enter
complete three-record events. Ten events yield 20 base/delay branches, 100
checkpoints and 500 scored field opportunities. Source rejections describe parser
scope/format limits, not meteorological invalidity. The parser was not broadened
after seeing heldout formats and rejected events were not replaced.

Ida stays in development because its records were already used during the first
implementation. Every original record, branch and repeated delivery for a storm
inherits the same split. Seven heldout events support an event-generalization
pilot using the same task format; the project does not establish pretraining
decontamination, hidden test access, or cross-disaster generalization.

## Task and diagnostic results

Each branch has five checkpoints and asks for maximum wind, latitude, longitude,
minimum pressure, and unsupported port reopening time. The first four fields must
cite the current report and exact numbered line. Unknown is correct only where
evidence is missing. The 100 mph research threshold maps to prepare/monitor;
missing wind maps to request_evidence. This is not an operational safety rule.

| Split | Program | Grounded fields | Correct actions |
| --- | --- | --- | --- |
| development | rule | 150/150 | 30/30 |
| development | last-arrival | 126/150 | 28/30 |
| development | no-update | 54/150 | 6/30 |
| heldout | rule | 350/350 | 70/70 |
| heldout | last-arrival | 294/350 | 70/70 |
| heldout | no-update | 126/350 | 14/70 |

These are diagnostic programs, not model responses. The heldout last-arrival
control gets every coarse action right despite incorrect grounded fields. The
unchanged action threshold is therefore insufficient as a standalone ranking
metric. Keep grounding, value accuracy, coverage and actions separate rather than
changing the heldout Gold to create errors.

Development references contain 6 request_evidence, 19 monitor, and 5 prepare
labels; heldout references contain 14, 32, and 24 respectively. All checkpoints
request the same schema and supply all evidence delivered so far. The tasks do
not establish causal use of a compressed state carrier or broad reasoning depth.

Per-event results use one storm as the unit. Event macro rates average defined
event rates equally and disclose undefined counts; pooled opportunity fractions
are also retained. Paired base/delay branches are dependent. No confidence
intervals are reported for this small purposeful pilot.

## Verification and remaining work

322 tests pass, zero are skipped. Source admission, split consistency, missing and
budget-exhausted denominators, private/future input exclusion, provider failures,
request/state replay, and immutable output paths are tested. The new build and
historical scorer were independently reproduced from saved sources/artifacts.

No actual LLM service, model or monetary budget has been selected in the project.
Provider tests use injected fixtures and a local HTTP test server. Actual model
compatibility, expense, and behavior remain unverified. Official OpenAI doc page
requests returned HTTP 403; the compatibility adapter does not claim verification
against a current hosted model. See docs/PROVIDER_INTERFACE.md for details.

Next: configure the selected model, test a small development-only collection,
record actual responses and provider usage, and inspect protocol failures before
any larger comparison. Richer task variants should be developed on development
data and evaluated under a newly frozen protocol without tuning to heldout scores.
