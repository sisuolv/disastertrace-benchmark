# Independent review guide: P7 native forecast task

Please review measurement validity, code defects and reproducibility before
suggesting more model runs. This is an offline milestone, not a new model score.
No human per-item annotation or model-based judge is needed to reproduce it.

## Read in this order

1. `FINDINGS.md`: actual counts, controls, limits and preserved failures.
2. `PROTOCOL.md`: exact task, delivery, authority, output and metric rules.
3. `execution_v1/data/dataset.json` and `candidates.json`: deterministic selection,
   276 candidates, 19 future-cutoff exclusions and the complete source identity.
4. `execution_v1/data/public.json`: evaluator-side full timeline. Only the current
   request's visible-source projection is sent to a model; this file is not a
   model-accessible filesystem tool or a single model prompt.
5. `execution_v1/requests.json`: exact unsent public requests for all diagnostic
   histories, keyed by SHA-256. No future-delivery text or private Gold is added.
6. `execution_v1/data/private_reference.json`: scorer-only answers, all admitted
   source claims, supporting byte spans, line hashes and transition labels.
7. `execution_v1/diagnostics/*/captures.json` and `scores.json`: separate program
   policies, raw final text or null, fixed denominators and whole-episode metrics.
8. `CPU_RELOCATION.json`, `VALIDATION_RESULTS.json`, `PRESERVATION.json` and
   `OFFLINE_ACCEPTANCE.json`: observed verification, failures and file bindings.

## Questions that matter scientifically

- Does latest-visible-explicit coverage answer the stated document-claim task?
  It is a declared benchmark policy, not an inferred official NHC operational
  rule for carrying old forecasts through newer products that omit a horizon.
- Are absolute valid times, issue times, center times, retrieval and synthetic
  delivery kept distinct? Historical first availability and model initialization
  are not established by these archive products.
- Does deriving target dates from the full admitted union disclose a selection
  assumption? It does, and it is documented. It does not put future values or
  future source text into a request. not_stated items are deliberately retained.
- Are 49 raw revision pairs distinguished from 257 query checkpoints and 1542
  expanded method/repeat slots? The independent weather-source count is two.
- Are unchanged wind, unchanged full values and current authoritative citation
  treated differently? Coordinates can change when wind does not. Literal support
  from an older source does not make its source version current.
- Are terminal status and missing evidence distinguished from zero wind? Do
  qualifiers remain visible without silently adding extra graded fields?
- Are natural no-effect cases and invalid/missing outputs retained? None of the
  diagnostic policies is filtered to only examples where it fails.
- Are all three methods given the same current evidence while carrying different
  own-output histories? This does not isolate representation or latent memory.

## Implementation boundaries

New code lives in `src/disastertrace/forecast_task/`, relative to the project root;
the exact same code is frozen under `execution_v1/source/src/`.

| Module | Responsibility / boundary to review |
| --- | --- |
| `compiler.py` | Re-admit saved raw bytes using both frozen source parsers; compile prospective targets and raw citation support |
| `public_resolver.py` | Independent numbered-text parser, own date resolution and public-only correct/wrong policies |
| `contract.py` | Shared public shape/defaults; no source parser, current source ID or correct value encoded |
| `protocol.py` | Whitelisted public projection, fresh messages and exact own-history prefix |
| `scoring.py` | Shape, scope, time, units, values, authority, locator, literal support and complete correctness |
| `diagnostics.py` | Fresh per-policy/trajectory histories, raw program outputs and independent scoring |
| `package.py` | Exclusive snapshots, data/schedule/source bindings, tokenizer reservation and reconstruction |
| `__main__.py` | Offline build/verify only; there is no model or network dispatch command |

The public resolver shares the output shape helpers with the compiler, but not
its NHC parsing implementation, date resolver, row selection or private Gold.
The source compiler's two parsers reduce software risk; they are not independent
meteorological sources or a proof of correctness on all possible NHC formats.

## Required reproducibility checks

Use the command in `../../README_P7_FORECAST_TASK_V1.md` to reconstruct from the
frozen source. The complete copied-run command is saved in
`validation/cpu_relocation_002/intent.json`. The final receipt confirms both the
copied CLI import/help and full verify paths exit 0 with no Torch/vLLM loaded.

Inspect the initial `cpu_relocation_001` failure as well. It reports all scientific
objects reconstructed before the wrapper rejects a denied urllib3 IPv6 capability
bind. The v2 wrapper still raises PermissionError for that bind. It records only
the specific `_has_ipv6` call to `("::1", 0)` separately; all other path, connect,
DNS, bind, send, subprocess and backend-import attempts still fail. The dependency
file hash is bound to `isolation_dependency/urllib3_util_connection.py`.

The guard is a Python audit-hook restriction used to test this Python package's
dependency closure. It is not a claim of OS-level containment against arbitrary
malicious native extensions. The model is given no filesystem or network tools.

Run core tests with the project pytest environment and the four-worker preview
tests separately. 59 core, five preview and 26 historical source tests pass. Do
not sum repeated successful test invocations into a larger test count. Retain the
initial large-integer crash and verify its regression now receives a semantic
error without crashing. Keep initial lint and isolation failures in the record.

## What to review next

`NEXT_EXECUTION_PLAN.md` proposes a new native collector and four-worker
aggregator before at most 1542 Qwen3-8B model responses. The four-worker file is
only a checked ownership preview and has no dispatch path. Review the future
failure-prefix, one-use journal, global budget and token/text audit requirements
before treating it as executable GPU infrastructure.

P1-P6 source, data and model records are unchanged. Their reported model scores
must stay separate from these program controls. Larger development sources, a
matched second model and lossless carrier representation controls remain future
research. This milestone is local; no P7 GitHub upload or hosted CI run is claimed.
