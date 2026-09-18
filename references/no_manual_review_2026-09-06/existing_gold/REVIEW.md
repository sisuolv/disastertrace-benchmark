# Existing Gold audit for a benchmark without new manual review

Audit date: 2026-09-06. This is source inspection, not benchmark execution or scientific validation.

`MANIFEST.json` records exact upstream commits, URLs, SHA256 checksums, Git blob hashes, and verification limits. Six newly inspected small files are saved here. Their bytes match the Git blob hashes in the original cached repository trees. Earlier reads existed only in memory, so the six files were downloaded again for persistence. The original audit directory was not changed.

## Scope and recommendation

An evaluation can avoid new per-item human annotation or review by inheriting published Gold and limiting new tasks to answers produced and checked by explicit programs. This does not establish that inherited labels are error-free, nor that all upstream datasets were originally created without human work.

Use EarthVerse numeric/source-selection tasks and automatically checkable CyPortQA text tasks as candidate real-data foundations. Borrow STATE-Bench state assertions and STALE's three probing dimensions for the dynamic protocol. Keep inherited-label evaluation, independently recomputed evaluation, and synthetic protocol evaluation separate. Reject examples that fail automated inclusion criteria and report rejection rates and retained coverage.

## EarthVerse

Saved files:

- `Earth-Verse/tasks/CSX-001_Q1/question_en.md`
- `Earth-Verse/tasks/CSX-001_Q1/computed_gt.json`
- `Earth-Verse/scripts/judge.py`

Exact commit: `6ee72d4094c23306660f503789e8f82b4431ecc6`.

The CSX-001_Q1 task uses package-local evidence for the June 2021 Pacific Northwest heat wave. It asks the solver to select a daily/hourly source over aggregate-only data, filter an inclusive event window, and calculate a daily temperature maximum, hottest three-day mean, and mean humidity among hot hours. The original task already requests structured JSON and is suitable for text or tool-using LLMs.

The published Gold includes a 35.5 C peak, 33.9 C hottest three-day mean, 24 percent mean hot-hour humidity, 29 hot hours, explicit numeric tolerances, source paths, and event-window dates. These values are targets for the specified package data and calculation window; they are not a claim about the maximum across the entire real-world heat wave.

The official scorer is not deterministic. `scripts/judge.py` states near its beginning that there is no deterministic exact-match scorer. Its prompt explicitly assigns correctness, numeric tolerance, semantic equivalence, evidence sufficiency, and rubric credit to the LLM judge. Both `answer_correctness_score` and `llm_rubric_score` therefore depend on a model judge. A deterministic field-based adaptation must be identified as a derived evaluation rather than the official EarthVerse score.

The previously saved `scripts/validate_submission.py` checks submission directories, files, non-empty answers, and trajectory structure. It does not verify answer correctness or Gold accuracy.

The sample Gold says `computed_by: compute_gt.py`. No `compute_gt` path appears in the original cached GitHub tree for this commit. Event evidence is distributed separately, and was not downloaded in this audit. Independent recomputation remains a required feasibility check before admitting tasks to a new deterministic core.

The previously inspected license distinguishes Apache-2.0 scripts, CC BY-NC 4.0 original task annotations/Gold, and third-party evidence terms.

## CyPortQA

Saved file:

- `MLLM-Bench-CyPortQA/dataset/MultiModalInput/Cyclone Text Archive Advisory/IDA_2021_24h.txt`

Exact commit: `1c38abf339d1471d710f6cb719a5e3874b547077`.

The Ida text is NHC Advisory 10. It contains the issue time of 2021-08-28 21:00 UTC, coordinates 26.2 N / 87.0 W, maximum sustained wind 105 mph, movement NW at 16 mph, warning areas, and regional storm-surge ranges. It provides original text evidence for extraction, comparisons, and selected temporal tasks. It does not by itself establish a complete operational Gold for port actions.

The template already saved in the original audit has text-only `text_advisory` tasks Q16-Q18 and Q28-Q29, and `Table_wind` tasks Q10-Q15 and Q25-Q27. These are candidate task families, not a blanket endorsement of label validity. Image-dependent tasks cannot preserve their original meaning merely by rendering their answer fields as input text.

### Read-only dataset-prefix observations

The actual `dataset/CyPortQA.json` was inspected only through an in-memory prefix. The successful prefix read requested and consumed 65,536 bytes, and parsed 86 complete QA objects from the initial `ANA_2015_Port_of_Savannah,_GA` scenario. An earlier 32,768-byte attempt did not parse a complete root object. No prefix file or full dataset was saved, and neither was downloaded again for this persistence step. These observations are examples from that prefix, not dataset-wide findings.

- Actual records contain `answer`, including Q18 Gold `B.`.
- Across five observed Q16 time points, the correct choice is always the port already named in the scenario context. The previously saved template also maps Q16 Gold to `senario.port.name`. This can create a shortcut and needs an automated inclusion rule or a separately reported original-data baseline.
- Observed Q17 records ask for expected landfall location but Gold gives broad impacted-coast descriptions, including `Georgia through North Carolina coasts, with primary impacts focused on the Carolina shoreline`. The template maps the answer to `impacted_coast`. Do not treat these examples as certified location Gold for a derived main evaluation.
- The observed Q18 question says A/B/C/D although the actual choices and prompt contain A-G. A derived evaluation needs an explicit policy for this format inconsistency.
- The original template maps Q28's onset of tropical-storm conditions to `hours_to_landfall`. That mapping is not automatically scientifically valid; the two times should not be assumed equal.

For a core with no new per-item human review, admit only task types whose Gold can be independently computed or checked from allowed evidence under published rules. Preserve any original-data result as an inherited-Gold comparison and report automated exclusions.

## STATE-Bench

No new STATE-Bench files were downloaded. Read the original snapshots of `state_bench/schemas.py` and `state_bench/scoring.py`.

The accurate commit, read from the original `AUDIT.json`, is `5644b1838d96bc4483da29642d058ecaa6f80f7f`. An earlier informal response included an incorrect full SHA in a URL; this recorded value supersedes that URL.

The schema supports direct field assertions, created-record matching, and relational assertions. `evaluate_state_requirements` reconstructs final state, compares required and observed assertions, and reports missing or unexpected changes. This is genuine deterministic state evaluation and is useful for required updates and protection of unchanged fields.

Only state requirements and efficiency are deterministic in the inspected code. Non-state task requirements and UX use LLM judges, and full task completion combines state and non-state checks. The data represent enterprise workflows and are not a weather Gold source.

Verified source link: <https://github.com/microsoft/STATE-Bench/blob/5644b1838d96bc4483da29642d058ecaa6f80f7f/state_bench/schemas.py>.

## STALE

Saved files:

- `STALE/STALE/README.md`
- `STALE/STALE/Evaluation/judge_prompts.py`

Exact commit: `ea7d391103a151927cd29d2f01d87597a782bdcb`.

STALE generates an old state, an updated state that implicitly invalidates it, probing questions, chat sessions, and noise. Its Gold format contains `M_old`, `M_new`, `explanation`, and three probing queries. The design is useful for state resolution, false-premise resistance, and propagation of updates into actions.

The evaluation prompt asks an LLM judge to assign Boolean judgments. It is not a deterministic oracle. The first dimension treats claims of ignorance as failure, so the rubric cannot be copied unchanged into branches where decisive evidence is deliberately withheld: ignorance may then be the correct response.

Its generated timestamps are initially anchored in 2027 and shifted by whole years so the final query falls in 2025. This is a synthetic scheduling procedure, not evidence of real historical document availability.

## Not verified

- No upstream code, judge, or model was executed.
- No published benchmark results were reproduced.
- EarthVerse evidence was not downloaded and its Gold was not independently recomputed.
- CyPortQA's complete dataset and encoded scenarios were not audited.
- Parser correctness, source sufficiency, and real-world scientific accuracy remain distinct from JSON validity or model-judge agreement.
- Open-ended operational recommendations and ambiguous geographic interpretations do not receive a certified deterministic Gold from this audit.
