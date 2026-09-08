# P2 controlled weather evidence benchmark

The subsequent [captured execution layer](README_P2_EXECUTION_V1.md) adds durable
collection, independent provenance auditing and direct model-result scoring.
The data preparation and program controls described here remain separate;
their historical package is preserved and their results are not LLM scores.

P2 is an offline, executable task for evaluating LLM evidence updates,
preservation, scope isolation and source tracking. It uses four weather fields
and three matched task families, with deterministic Gold and an independently
implemented public oracle. It requires no per-item annotation or LLM judge.

The development plan has 18 trajectories, 90 checkpoints per method and 270
planned model slots across snapshot, structured state and answer history.
Twelve synthetic microtrajectories are separate software fixtures. Initial
development values inherit three existing NHC source records; all subsequent
updates, entities, windows and controlled text are explicitly generated.

- [Semantics and data scope](docs/P2_CONTROLLED_SEMANTICS_V1.md)
- [Automatic Gold validation and scoring](docs/P2_AUTOMATIC_GOLD_VALIDATION.md)
- Implementation: `src/disastertrace/controlled/`
- Tests: `tests/test_controlled*.py`

From an installed development environment, use an existing verified source build
and fresh output paths:

```bash
python -m disastertrace.controlled.cli prepare \
  --source-build work/build-cohort-v1 --output work/p2-controlled-v1
python -m disastertrace.controlled.cli verify --dataset work/p2-controlled-v1
python -m disastertrace.controlled.cli rehearse \
  --dataset work/p2-controlled-v1 --method structured_state \
  --backend correct --output work/p2-correct-rehearsal-v1
python -m pytest -q tests/test_controlled*.py
```

`prepare` runs 450 compiler/oracle comparisons and 2700 development diagnostic
responses. Its package binds source evidence, semantic data, Gold, public
initial requests, schedule, program-control results and recursive implementation
bytes. `verify` regenerates these artifacts and refuses changed scope or code.
Prepared requests are unsent; every diagnostic result is marked ineligible for
an LLM leaderboard. There is no live command or credential access in this module.

`P2_OFFLINE_READY` means the declared program acceptance checks passed. It does
not select provider settings, authorize spending or claim real model results.
The P2 provider adapter constructs a protocol-specific wire envelope. The
separate captured execution layer binds its response provenance and frozen
execution settings. NHC calibration and the proposed P2 model matrix are
separate experiments. The original NHC five-field protocol and historical
experiments retain their existing definitions.
