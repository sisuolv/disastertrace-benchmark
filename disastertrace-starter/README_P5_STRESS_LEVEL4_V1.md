# P5 level-4 stress profiles: offline acceptance complete

The next engineering step after P4 is complete: three separately versioned stress
datasets, execution freezes, full diagnostic collection and independent report
reconstruction. **P5 has zero model calls.** The diagnostic answers are generated
by the public oracle and must not be presented as new Qwen3 scores.

| Factor | Episodes | Gold comparisons | Captured diagnostics | Zero-effect controls |
| --- | ---: | ---: | ---: | ---: |
| revision_chain | 36 | 180 | 540 | 6 |
| irrelevant_scope | 36 | 180 | 540 | 0 |
| late_stale_replay | 36 | 180 | 540 | 0 |

All level-4 episodes are retained. The 108 variants derive from the same 36 base
episodes and three source groups; they are not 108 independent weather events.
All checkpoint values, statuses, current citations and actions equal their base
references. All 16,200 program controls retain the same metric denominators and
checkpoint opportunities. Actual context calibration remains the P4 32,400-row
program-carrier study, with its disclosed limits for arbitrary model histories.

This phase passes 1,118 prior CPU regression tests and 27 new stress tests. Each
factor's diagnostic report is reconstructed in a relocated CPU environment with
Torch/vLLM absent and original data, weights and network access blocked. All 9,092
historical preservation entries and the pinned GPU environment remain unchanged.

Read [the frozen protocol](docs/P5_STRESS_LEVEL4_V1.md),
[findings and next work](artifacts/p5_stress_level4_v1/FINDINGS.md), and
[machine-readable acceptance](artifacts/p5_stress_level4_v1/OFFLINE_ACCEPTANCE.json).
The code lives in `src/disastertrace/stress_eval/`; P3/P4 code and captures remain
unchanged. Each factor is under `artifacts/p5_stress_level4_v1/units/`.

## CPU reconstruction

Install the existing P4 CPU review requirements in a separate environment. From
the project directory, set `PYTHONPATH` to the selected execution's frozen source,
then run the verification command with that environment's Python:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=artifacts/p5_stress_level4_v1/units/revision_chain/execution_offline/implementation_source/src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m disastertrace.stress_eval.cli report \
  --execution artifacts/p5_stress_level4_v1/units/revision_chain/execution_offline \
  --run artifacts/p5_stress_level4_v1/units/revision_chain/diagnostic \
  --output artifacts/p5_stress_level4_v1/units/revision_chain/diagnostic_report \
  --verify
```

Use the other factor directory names to verify their reports. Do not add
`--require-model`: these are diagnostic origins, which that flag correctly rejects.
`verify_portable.py` reproduces the observed relocation/access-guard procedure.

## Next execution unit

Prepare three fresh live freezes and a phase-level one-use launcher, bind all
offline acceptance evidence and exact runtime settings, then use the existing GPU
authorization for at most 540 responses per factor / 1,620 in total. Keep one
repeat, no retries or extra probes, independent prefix reports and fixed scoring
denominators. No P5 live freeze or live claim exists yet. Paid API, heldout and
training remain outside this scope.

The existing GitHub login can be reused by Git and `gh api`. Its current `repo`
scope permits this private repository upload. The optional Actions workflow is
published as a [template](docs/ci/README.md); it is not active hosted CI.
