# DisasterTrace starter scaffold

The latest completed experiment is
[T6 output calibration](README_T6_CALIBRATION_V1.md): 270 audited DeepSeek responses
and a common 8192-token cap selected by the frozen reliability rule. The next
engineering step is P2-specific live collection and independent provenance audit.

The current `next-phase-v1` development entry is
[README_NEXT_PHASE_V1.md](README_NEXT_PHASE_V1.md): T0-T5 offline calibration
execution and controlled evidence tasks, with no new model calls. The descriptions
below retain the earlier pilot/scaffold context. Current validation records are
in [artifacts/next_phase_v1/README.md](artifacts/next_phase_v1/README.md).

The active implementation is the **automatically scored weather pilot** in
`src/disastertrace/automated/`, following `../INTEGRATED_BENCHMARK_PLAN.md` v0.3.
Start with [README_PRE_API.md](README_PRE_API.md) for the current frozen pilot,
three methods, data/collection audit, safe recovery and API preparation.
The first actual DeepSeek API trial and its citation-scoring caveat are recorded
in [README_DEEPSEEK.md](README_DEEPSEEK.md).
[README_COHORT.md](README_COHORT.md) records the completed data expansion stage.
[README_AUTOMATED.md](README_AUTOMATED.md) retains the first-work-package guide.
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) records
executed checks and limitations. No new per-item human annotation or review is
required. Offline diagnostic results are not LLM results.

The original scaffold and its historical instructions are retained below. The
automated track has its own strict schemas, replay, and scorers; it does not use
the legacy scoring/runtime modules for its results.

This is a deliberately small reference implementation for:

- as-of-time evidence legality;
- fresh-session checkpoint replay;
- explicit model-authored state carriers;
- release-delay and stale-version interventions;
- deterministic transition scoring;
- streaming CyPortQA candidate indexing;
- NHC UTC issue-time parsing;
- text and GIS delta candidate builders.

It is **not** a finished benchmark and does not include private Gold annotations.

## Install and test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Validate the demo episode:

```bash
disastertrace validate-episode examples/episode.json
```

Build a compact CyPortQA scenario index:

```bash
disastertrace index-cyportqa \
  /path/to/MLLM-Bench-CyPortQA/source_data/Encoded_senario.json \
  work/cyportqa_candidates.jsonl
```

## Recommended upstream use

- Treat CyPortQA as a data and multimodal-I/O source, not as the episodic runner.
- Reuse EarthVerse's package isolation, retry, trace, and submission-validation patterns.
- Keep the DisasterTrace replay engine independent of any one evaluation framework.
- Add an lmms-eval task exporter after the schemas and scorers are frozen.

## Non-negotiable invariant

Each checkpoint is sent as a **new model request** containing only:

1. the fixed task protocol;
2. the evidence delivered at that checkpoint under the selected policy/arm;
3. the explicit prior state carrier, when that arm permits it.

The prior raw chat transcript is never carried across checkpoints. Otherwise a
masked-carrier experiment cannot establish causal use of the explicit commit.

## Historical scaffold implementation issues

1. Add an artifact-hash verifier before every run.
2. Add `source_manifest.jsonl` and provenance fields to all importers.
3. Build one real NHC + USCG episode with A-grade timestamps.
4. Add span/region IDs to deterministic hidden Gold.
5. Implement the fixture agents: oracle, no-op, stale, overreact, future-leak.
6. Add paired Core-C aggregation across actual/masked/oracle/edited arms.
7. Export frozen episodes to lmms-eval only after the core tests pass.

## Attribution

This scaffold is newly written. When copying or adapting upstream code, preserve
CyPortQA's MIT notice and EarthVerse's Apache-2.0 software notice. Third-party
evidence retains the original provider's terms.
