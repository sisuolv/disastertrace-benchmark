# Review snapshot boundaries

This private review snapshot preserves the original project layout under
`disastertrace-starter/`, with a selected exact-byte reference bundle alongside it.
The current evaluator, parser, provider and test sources are copied unchanged.
The additional Chinese review document summarizes existing work; it does not add
model responses, experiments, external review conclusions or evaluation scores.

The export includes saved `work/` and `artifacts/` evidence so that reviewers can
inspect raw responses, invalid answers, interrupted runs, cost assumptions,
versioned scores and audit code. It excludes virtual environments, cache files,
compiled Python bytecode, downloaded dependency wheels and the standalone Ruff
executable under `work/tooling/`. It contains no GitHub authentication config.

Internal directory aliases are materialized as ordinary file copies for a
self-contained checkout. Their original targets are recorded in
`EXPORT_MANIFEST.json`; the source project and its aliases are not changed.
The copied project's `.gitignore` has a publication-only override allowing its
archived `work/` evidence to be tracked.

Archived manifests can contain absolute paths from the original environment.
Their preserved bytes record that original execution; copying the archive does
not make those paths portable. Use the fresh-build commands in the root README.
Fresh build IDs can differ because provenance includes relocated source paths.
Do not rewrite old manifests, replace old scores, or use archived diagnostic
answers as future model history.

The root README and this document describe this review export. Source milestone
documents retain their historical dates and completion claims. Historical tests
under artifacts are separate from the current `pytest tests` suite. The original
684-test result and 6,979-check audit are retained, while new export verification
records are written separately under `handoff_audit/`.

The exported source was also installed into a fresh Python 3.10 virtual
environment using the Tsinghua PyPI mirror. Its current suite passed all 684 tests
in 57.41 seconds. Fresh build, calibration preparation and calibration verification
all exited successfully, verifying 128 artifacts, 54 unsent initial requests and
1,080 program-generated diagnostic responses. The commands, actual dependency
versions and logs are retained under `handoff_validation/`. Fresh generated output
trees are ignored by Git; they do not replace the historical evidence.

The owner explicitly authorized this private GitHub review export. The nested
`AGENTS.md` retains earlier milestone instructions, including its historical
no-publication wording; it was not rewritten. This one-time export does not
authorize new model calls or public redistribution.

The bundled sources keep their upstream attribution and terms; see
`REFERENCE_BUNDLE.md` and `disastertrace-starter/THIRD_PARTY_NOTICES.md`.
No new license is applied to all project material, and this snapshot does not
claim official benchmark reproduction or NOAA/NWS endorsement.
