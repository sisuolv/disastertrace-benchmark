---
name: agentfuture-probability-forecast
description: Finalize a forecast from an evidence bundle that has already been collected. Use when an agent needs an auditable probability forecast, a paired direct-versus-probability comparison over identical evidence, or an evidence-locked final prediction with no additional retrieval.
---

# AgentFuture Probability Forecast

Use this skill only after evidence collection is complete. It is an adapter between an agent's saved research trace and a separately installed AgentFuture-compatible probability finalizer.

## Required inputs

- A task ID and forecast question.
- A trace file or directory containing the evidence already gathered.
- A freeze time when the task has a temporal cutoff.
- Candidate options for categorical questions, or `continuous` as the output type.
- An executable finalizer exposed through `AGENTFUTURE_FINALIZER_BIN`.

## Evidence-lock contract

- Do not search, browse, fetch URLs, or call research tools after normalization begins.
- Treat the normalized snapshot as immutable input to finalization.
- Never add facts that are absent from the snapshot.
- Preserve `evidence_bundle_hash` in every finalizer output.
- When comparing `direct` and `probability`, give both modes the same snapshot.
- If the snapshot is empty, return an explicit abstention with `empty_evidence_bundle=true`.

Here, evidence-locked means that finalization cannot collect more evidence. A configured finalizer may still call an LLM endpoint to interpret the frozen evidence.

## Normalize the completed trace

Resolve this skill's directory as `SKILL_DIR`, then run:

```bash
python3 "$SKILL_DIR/scripts/normalize_agent_trace.py" \
  --agent "<agent_name>" \
  --input "<trace_or_log_path>" \
  --output "<evidence_snapshot.json>" \
  --task-id "<task_id>" \
  --question "<forecast_question>" \
  --option "<option_a>" \
  --option "<option_b>" \
  --output-type single_choice \
  --freeze-time "<YYYY-MM-DD>"
```

For continuous targets, omit `--option` and use `--output-type continuous`.

Inspect the generated snapshot before sharing or finalizing it. The helper removes common credential patterns and avoids recording absolute input paths, but it cannot guarantee removal of personal or confidential content.

## Invoke the finalizer

For the probability forecast:

```bash
"$AGENTFUTURE_FINALIZER_BIN" \
  --snapshot "<evidence_snapshot.json>" \
  --mode probability \
  --output "<probability_result.json>"
```

For a paired evaluation over the same evidence, use `--mode both`. The backend interface and required JSON fields are defined in `references/finalizer-contract.md`.

## Validate and report

Verify that the result's `evidence_bundle_hash` exactly matches the snapshot. Report:

- Evidence snapshot path
- Finalizer output path
- `evidence_bundle_hash`
- `evidence_count`
- Probability forecast summary
- Direct forecast summary when `--mode both` was requested
- Any abstention, empty-evidence, fallback, or error flags

Stop with a clear error if the backend is missing, the hashes differ, or the result contains evidence not present in the snapshot.
