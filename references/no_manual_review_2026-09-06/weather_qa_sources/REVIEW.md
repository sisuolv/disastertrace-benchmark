# Additional disaster benchmark source audit

Audit date: 2026-09-06. Source snapshots are pinned to GitHub commits;
`MANIFEST.json` records retrieval URLs, byte lengths, and SHA-256 hashes.
This audit reads documentation, data structure, and scoring code. It does not
execute upstream code or perform new item-level expert annotation/review.

## DisasterBench_Open

- Repository: https://github.com/TamuChen18/DisasterBench_Open
- Data: the public repository contains `data/benchmark.jsonl` (328,011 bytes).
  Local JSON parsing confirms 233 records, all with `task_desc` and nonempty
  `structured_plan`. The tool manifest contains 26 agents. No large asset
  download is required for the structured planning evaluation.
- Task: given a textual disaster-related request and tool interfaces, produce
  an ordered structured workflow with agents, parameters, outputs, and
  dependencies. Image filenames occur as tool arguments; this does not require
  the evaluated LLM to interpret those images for plan comparison.
- Labels: existing `structured_plan` references. README describes the 233
  tasks as expert-verified; this audit does not independently verify that claim.
- Scoring: deterministic comparison of structured plans, tools, parameters,
  outputs, and dependency fields; first-point-of-failure diagnostics.
  `check_tools_correctness` explicitly compares ordered `(step, agent)` lists.
  A semantically equivalent reordered independent branch can therefore differ
  from the existing reference. Preserve original scores for reproduction;
  report a separately versioned alternative if adding graph-equivalence tests.
- License: actual root `LICENSE` is MIT, and README also states MIT. Preserve
  notices when reusing code/data; a separate dataset-specific license is not
  present among the inspected files.
- Recommendation: suitable as a small, ready-to-use text-LLM planning track
  without new per-item review. Disaster response is broader than extreme
  weather; do not describe all 233 examples as extreme weather. Keyword counts
  are not a validated weather subset. Keep the complete original benchmark as
  an auxiliary comparison unless an objective metadata-based subset exists.
- Limit: the inspected evaluator compares plans to references. This is not
  evidence of executing operational disaster tools or validating real-world
  recommendations. It is not a dynamic weather-evidence benchmark by itself.
- README also links https://huggingface.co/datasets/tamuzc/DisasterBench;
  Hugging Face access failed from this environment, but GitHub data retrieval
  succeeds and is sufficient to establish data availability.

## Obshazard-bench

- Repository: https://github.com/YYQ898/Obshazard-bench
- Claimed data: https://huggingface.co/datasets/YYQ898/Obshazard-bench.
  README reports 127 events / 4,202 VQA samples after removing 397 incorrect
  tmax-label samples. These counts are README claims, not verified data counts.
  The GitHub tree contains evaluation code, documentation, and utilities, but
  does not contain the VQA dataset or the output examples described by README.
- Task: multimodal satellite multispectral images plus optional station data;
  early warning, impact assessment, and recovery assessment, across weather
  and non-weather hazards including earthquakes and volcanic activity.
- Labels: README documents a `Ground truth` answer field alongside `Text`,
  `Image`, `Stations`, task, subtask, and ID fields. Label-generation provenance
  could not be verified from an actual dataset card/sample.
- Scoring: `evaluate.py:249` applies boolean substring matching, first-number
  extraction with tolerance/partial credit, short-text class exact/substring
  matching, then word-overlap scoring. This is automated and does not use an
  LLM judge, but these heuristics do not establish factual answer correctness.
  For example, substring matching can mishandle negation, and first-number
  extraction omits unit and multi-number semantics. The numeric formula also
  lacks a safe nonnegative magnitude denominator for negative references.
- License: README states MIT; no actual LICENSE file appears in the fetched
  GitHub tree. Dataset license was not verified because the Hugging Face API
  and README endpoints were inaccessible from this environment.
- Recommendation: defer from the text-only main benchmark. Removing required
  images changes the task and can make reference answers unsupported. Consider
  as a later multimodal track only after dataset availability, license,
  label provenance, and task-specific deterministic scorers are checked.
- Limit: a publication link or downloadable-data statement in README is not
  independent verification that the full data can currently be retrieved.

## Implications for a benchmark without new manual review

Existing published references can support automatic evaluation while retaining
their provenance and known limitations. This means no *new* per-item manual
labeling/review, not that the original datasets never involved humans.
Do not use model consensus as a substitute for ground truth. Keep inherited
reference-answer evaluation distinct from deterministic tasks generated from
structured weather records. Ambiguous or unparseable newly generated examples
should be excluded automatically and exclusion coverage reported.
