# P5: three level-4 factors on ACP H100 workers

All 1,620 actual Qwen3-8B responses are collected by 2026-09-08 07:36:54 UTC.
Three independent one-H100 ACP jobs, submitted from CPU CCI, finish successfully;
all nine collection/report/report-verification subprocesses exit zero. There are
no retries, missing answers, length finishes or extraction errors. All 1,620
answers pass JSON, structural schema and the original strict task contract.
The phase launch is consumed; never submit it again.

| Condition | snapshot all correct | structured_state all correct | answer_history all correct |
| --- | ---: | ---: | ---: |
| P4 balanced baseline | 167/180 | 178/180 | 145/180 |
| P5 revision_chain level 4 | 150/180 | 164/180 | 135/180 |
| P5 irrelevant_scope level 4 | 155/180 | 154/180 | 135/180 |
| P5 late_stale_replay level 4 | 163/180 | 172/180 | 132/180 |

P5 retains 90 value/status and 230 citation field errors across 260 incorrect
checkpoints. All 29 action errors overlap wind-field errors. Complete correctness
is 1,360/1,620 (83.95%); no answer is repaired or filtered. All 27 predeclared format
screens pass at 60/60 with zero length finishes. Unknowns are 156/156 in every
method-factor cell. Six zero-effect chain controls remain on their full denominators.

| Factor | ACP job ID | Canonical run |
| --- | --- | --- |
| revision_chain | pt-rtvkp7h8 | work/p5-qwen3-revision-chain-v1 |
| irrelevant_scope | pt-rcxzh9sh | work/p5-qwen3-irrelevant-scope-v1 |
| late_stale_replay | pt-g3y6l751 | work/p5-qwen3-late-stale-replay-v1 |

The generation-disabled preflight `pt-nmrxrdxx` succeeds before model submission.
Python 3.10.12, Torch 2.8.0+cu128, the full package inventory, model hashes and
vLLM/XGrammar settings match the frozen parent. ACP uses full H100s whereas P4
used a MIG partition; timing is descriptive. Each model remains single-GPU.

The inherited 2,229-file offline acceptance, three independent diagnostic report
reconstructions and 9,092 historical preservation entries pass verification.
Three new live freezes each pass another full 540-slot program diagnostic with
unchanged method scores. Eighteen new launcher tests and seven comparison tests
pass. Program diagnostics are not model evaluations.

Read-only progress from this project directory:

```bash
python3 artifacts/p5_stress_level4_v1/status.py
```

See the [ACP execution amendment](artifacts/p5_stress_level4_v1/ACP_EXECUTION_PLAN.md),
[CPU reproduction instructions](artifacts/p5_stress_level4_v1/REPRODUCE_ACP.md),
and [frozen live acceptance](artifacts/p5_stress_level4_v1/LIVE_ACCEPTANCE.json).
Detailed findings are in [MODEL_FINDINGS.md](artifacts/p5_stress_level4_v1/MODEL_FINDINGS.md);
the [next plan](artifacts/p5_stress_level4_v1/NEXT_PHASE_PLAN_ACP.md) prioritizes
same-hardware repeatability and broader independent sources. Token-mask replay
checks all 432,742 actual final/EOS tokens with zero violations. CPU relocation
rebuilds the P4/P5 reports, analysis and comparison with original data, weights and
network blocked. Historical preservation passes; archive integrity is recorded
separately after packaging. No paid API, heldout inference or training is included.

The 108 factor variants derive from the same three development source groups;
they are not 108 independent storms. Six zero-effect revision-chain controls
remain included. Keep wrong, invalid, missing and length-limited answers on full
fixed denominators, with all model-derived carrier history preserved.
