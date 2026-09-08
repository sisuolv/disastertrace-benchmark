# P4: constrained final JSON on the balanced Qwen3 benchmark

P4 creates a separate structure-constrained output track while retaining the
completed P3 free-JSON experiment. The user explicitly permits automatic GPU use
on 2026-09-08. The new 540-response local matrix completes at 02:49:31 UTC with all
540 contract-valid responses, no retries/missing/length/extraction errors and all
nine screens passing. Independent audit, token-mask replay and CPU relocation pass.
Full results are in `artifacts/p4_constrained_output_v1/FINDINGS.md`.

All-correct checkpoints are structured_state 178/180, snapshot 167/180 and
answer_history 145/180. The 15 value/status and 39 citation field failures, plus
six overlapping action errors, remain scored. Free and constrained results stay
separate. Its initial launch is consumed and all model processes have exited.

- Bundle: `artifacts/p4_constrained_output_v1/`.
- Protocol: `docs/P4_CONSTRAINED_OUTPUT_V1.md`.
- New modules: `src/disastertrace/constrained_eval/`.
- Canonical model run: `work/p4-qwen3-constrained-v1`.
- Live execution: `45b6a94b64ccd421a720cd1d27bf5c0658b13dab7c037ae4737c5c34cbefc393`.
- Offline execution: `17a7eb8f50edb87cef0ff9e735ecd5badaa063a05788262291a3030e1f615958`.

The same 36 episodes, 108 trajectories and 540 slots retain the common prompt v2,
public evidence, automatic Gold, original parser/scorer, sampling and carrier
rules. XGrammar constrains containers, keys, types and literals after `</think>`;
it does not choose values, citations or actions. Wrong but contract-valid answers
still propagate and score as wrong. JSON validity, structural validity and the
complete original task contract are reported separately on fixed denominators.

Offline acceptance passes 44 new tests, 224 relevant historical regression tests,
and 14 supplemental launcher/comparison/context checks. All 180 Gold and 5,400
program controls undergo actual grammar token-mask checks; 108 intended malformed
outputs are rejected. Complete diagnostics reconstruct in a relocated CPU environment
with Torch/vLLM, original data, model weights and network unavailable. The 6,932
historical protected entries and the P3 package inventory remain unchanged.

The separate stress calibration checks 32,400 program-carrier inputs over the
216 existing candidates. All three level-4 factors fit the 8192 output reservation;
level 16 fails this context screen. This calibration makes no stress model calls
and does not guarantee that arbitrary longer LLM-produced histories will fit.

Read-only status:

```bash
python3 artifacts/p4_constrained_output_v1/status.py
```

No new paid API, heldout, training, item-level human annotation, LLM judge or Git
publication is part of this matrix. Three dependent source groups and one repeat
limit generalization; free and constrained scores belong to separate output tracks.
