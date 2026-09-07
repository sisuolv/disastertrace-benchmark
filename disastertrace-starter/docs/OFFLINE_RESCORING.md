# Immutable offline rescoring

The migration command evaluates saved dynamic-weather answers with the original
scorer and the separately versioned evidence-support scorer. It makes zero new
provider requests. It changes neither the historical source facts nor the
episodes, requests, responses, traces, build manifests or original scores.
Differences describe how evidence is validated; they are not improvements in the
model's behavior.

## Execute and verify

From the project root, choose a new output directory:

```bash
.venv/bin/python -m disastertrace.automated.rescoring rescore \
  --build work/build-deepseek-v1 \
  --run work/deepseek-ida-state-v1/imported_run \
  --historical-score work/deepseek-ida-state-v1/score.json \
  --output work/deepseek-ida-rescore-v2

.venv/bin/python -m disastertrace.automated.rescoring verify \
  --output work/deepseek-ida-rescore-v2
```

`--historical-score` is optional. When supplied, its parsed content must exactly
equal the archived scorer's reproduced result. Existing output paths are
rejected, including symlinks that resolve into the old build, run or bound
collection package. Failed commands can leave an incomplete new directory;
preserve it and select a new output path for another attempt.

Python interfaces:

```python
rescore(build_path: Path, run_path: Path, output: Path,
        *, historical_score: Path | None = None) -> dict
verify_rescore(output: Path) -> dict
```

This is a separate entry point. The existing `disastertrace-auto score` command
continues to require an exact implementation/build match. Migration does not
patch that check or substitute a different implementation identity.

## Package contents

| Artifact | Meaning |
| --- | --- |
| `baseline_v1.json` | Output of the historical build's unchanged `workflow.score` |
| `score_v2.json` | New versioned metrics over the same selected episodes and trace |
| `evidence_index_v2.json` | Deterministic support spans, policy and episode/source bindings |
| `comparison.json` | Every field's v1/v2 correctness, citation reasons, changed fields and invariant metrics |
| `implementation.json` | Hashes and identity of the implementation used for this migration |
| `implementation_source/automated/` | Exact Python source files for independent later replay |
| `manifest.json` | Derived file hashes, original input inventory and separate old/new identities |

The manifest's `original_inputs` records absolute local locations and hashes of
all files in the original build and run, all bound collection files, and the
optional original score. This includes the saved request bodies, response
envelopes, usage records and trace where present. Retain these original local
directories: the derived package references them and does not duplicate their
contents. Moving only the package preserves its own hashes but does not relocate
the original inputs automatically.

`comparison.json` requires unchanged schema success, value/status accuracy,
action accuracy, required-unknown accuracy and known-answer coverage. It also
checks checkpoint/field sets and per-field value correctness. Only evidence-
dependent outcomes and the separately added metric definitions may differ.
Read `METRICS_V2.md` for fixed-reference and model-conditional denominators.

## Replay and trust boundary

Before loading executable code, migration validates the historical manifest and
every declared artifact hash, the implementation fingerprint, the complete
Python source file set and its binding to the build manifest. It copies those
verified source bytes into a temporary directory and imports them under a
private package name. The original `workflow.score` then independently validates
the build/run, recomputes the original score and, when bound, reaudits the saved
collection. No historical manifest or identity is rewritten.

The temporary copy excludes cached bytecode and unlisted modules. Imports run
with bytecode writing disabled, so replay creates no `__pycache__` directories in
historical or derived packages. Private module names are removed after replay.
The new scorer is also run from its copied, hashed source snapshot.

`verify` checks the full derived file set and hashes, checks the original
inventory, repeats the historical score/collection audit, then recomputes v2, the
evidence index and the per-field comparison from the derived source snapshot.
Changes to the currently installed scorer do not replace that saved scorer.
Both commands recheck original inventories after computation; verification also
rechecks its derived artifacts before reporting success.

These snapshots are locally trusted executable Python code. The private import
namespace is an identity/isolation mechanism, not a security sandbox. Do not run
this loader on untrusted downloaded submissions or remote source packages.
Hashes detect changes relative to the saved manifest; they do not authenticate
the source owner, prove provider identity or prevent someone from fabricating an
entire mutually consistent archive. The workflow makes no network requests and
does not read an API credential, but trusted Python source remains executable.

## Verification scope

Migration tests cover a deliberately distinct archived implementation identity,
immutable old bytes, equivalent body citations, exact historical score matching,
output-path protection, independently audited injected-transport collections,
CLI execution, current-function replacement and input changes during scoring.
Tamper tests cover original traces/collections, executable source, derived
scores/indexes/diffs, and edited score hashes with a recomputed manifest.
Fixtures are labeled synthetic or diagnostic; they are not additional LLM runs.

The regression-first command records are under
`artifacts/optimization_p0/migration_checks/`. The project-level P0 acceptance
report records the actual unchanged ten-response trial comparison separately.
