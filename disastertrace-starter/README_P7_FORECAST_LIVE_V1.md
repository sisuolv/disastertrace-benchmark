# P7 native forecast live evaluation

Completed on 2026-09-08: all 1542 planned Qwen3-8B answers are captured and
independently verified; all four H100 jobs succeed and release their allocations.
Fully correct: 527/1542 (34.18%). By method: snapshot 187/514,
structured_state 194/514, answer_history 146/514. All answers pass shape and
unit checks; the remaining errors concern semantics and citations. Method order
reverses between the two storms. There are no missing answers, retries, length
finishes, unknown outcomes or extraction errors.

Read artifacts/p7_forecast_live_v1/FINDINGS.md for the detailed results and
limitations, and COMPLETED_ACCEPTANCE.json in that bundle for the evidence
inventory. The report, exact final/EOS token replay and CPU relocation pass.
Every live claim is consumed; never restart the completed workers or observer.

This phase evaluates the accepted native NHC forecast-claim task with the existing
pinned Qwen3-8B model. Entry plan: artifacts/p7_forecast_live_v1/EXECUTION_PLAN.md.
The task's data, automatic references, public renderer and scorer remain unchanged.
Its earlier program-only acceptance remains README_P7_FORECAST_TASK_V1.md.

The fixed matrix contains257 checkpoints, three carrier methods and two repeats:
1542 planned answers. Four independent TP1 H100 workers own390/390/384/378 slots.
Every failed, invalid, truncated, missing or unattempted slot stays in the score
denominator. There are no retries, heldout calls, paid APIs or model-based judges.

Implementation is src/disastertrace/forecast_live. Tests are
tests/p7_forecast_live. Detailed command/results, CPU acceptance, separate hardware
preflight and fresh live execution belong in artifacts/p7_forecast_live_v1.
The live watcher only queries/stops those exact jobs and reconstructs saved output;
it has no submission or generation path.

This is development evaluation of published forecast understanding and revision
tracking over Francine and Ida. It is not real weather prediction, and two storms
cannot establish general extreme-weather competence. Keep this table separate
from the constructed P6 stress task. GPU count alone does not measure speedup.

The bundle's IMPLEMENTATION_STATUS.md preserves its earlier engineering boundary;
finalization_01/FINAL_STATUS.json and FINDINGS.md contain completed outcomes.
