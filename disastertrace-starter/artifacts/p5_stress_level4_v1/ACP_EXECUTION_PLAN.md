# P5 ACP execution amendment

The user confirms the existing P5 work and explicitly requests verification,
launcher completion and GPU evaluation from the CPU CCI, using the ACP guide.
The user permits at most four parallel H100 GPUs. This phase uses three independent
one-GPU factor jobs; a preceding one-GPU load preflight generates no answers and
finishes before model jobs are submitted. No model or tensor parallel setting changes.

## Frozen experiment

- Factors: revision_chain, irrelevant_scope and late_stale_replay, all level 4.
- Each factor: 36 episodes, 108 trajectories, 540 responses, one repeat, no retry.
- Total: at most 1,620 model responses, no extra model probes or answer repair.
- Keep all P5 data, source, grammar, model weights, package versions, seeds,
  checkpoint waves, batch size, task contract, Gold and scorers unchanged.
- Three new live freezes and three independent canonical runs. Full diagnostics
  under each new identity must reconstruct the accepted offline method scores.
- Deadline: 2026-09-08 12:30 UTC for every factor. Each ACP worker has a 7,200-second
  wall bound. Queueing does not waive the absolute collection deadline.
- No paid API, heldout evaluation, training, human item labels or LLM judge.

## Compute and durability

Use cluster `computing-cluster-01g-02`, spec `N6lS.Iu.I10.1.8c128g`, one worker node
per job, reserved quota, NORMAL priority and zero platform retries. The explicit
container image, command, shared AFS mount and submission response are recorded
before dispatch. Existing SCO authentication is reused; no new credentials are needed.

The previous P4 run used an H100 MIG partition. ACP requests a full H100 80GB.
Record that hardware change and actual driver/runtime information. Preserve the
same BF16 Qwen3-8B, tensor_parallel_size=1 and vLLM/XGrammar settings. GPU timing
and exact stochastic samples are not a controlled hardware comparison with P4.

A phase-level exclusive directory consumes the three-job launch. Per-factor
submission and worker markers prevent duplicate jobs or duplicate collectors.
An ambiguous CLI submission is retained and reconciled by its exact display name;
it is never retried automatically. Results survive CCI disconnection on shared AFS.
Each collector's full run or stopped prefix gets independent report reconstruction.

## Acceptance and reporting

Recheck inherited acceptance hashes and all three diagnostic reports; verify
historical preservation. The real ACP preflight must load the frozen model with
LLM.generate disabled, match Python/packages/backend source and expose one H100.
Bind this evidence, fresh live diagnostics and tested launcher source before
submitting production jobs. Platform submission alone is not completion.

After collection, verify actual job status, raw captures, token grammar and CPU
report reconstruction. Report all planned opportunities, semantic and citation
errors, unknown/action outcomes, context or length failures, and actual token use.
Compare matched base/stress checkpoints by factor, method, source and effective
intensity. Six zero-effect revision-chain controls remain included. Three source
groups and one repeat support descriptive development conclusions only.
