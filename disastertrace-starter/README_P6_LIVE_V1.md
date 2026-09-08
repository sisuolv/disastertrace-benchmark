# P6 paired model and forecast-source milestone

Qwen3-8B: 2160/2160 actual answers; 2160 schema-valid; 1861 fully correct. Original ACP state: FAILED; the complete capture is verified after a versioned CPU-only stop-token audit fix.

NHC source pilot: 12/12 admitted products from 2 development storms; 49 same-valid-time revision pairs.

- Detailed results and next research steps: [FINDINGS](artifacts/p6_live_v1/FINDINGS.md).
- Scope and runtime: [execution plan](artifacts/p6_live_v1/EXECUTION_PLAN.md).
- Safe CPU reproduction: [reproduction instructions](artifacts/p6_live_v1/REPRODUCE.md).
- Next implementation milestone: [forecast-task plan](artifacts/p6_live_v1/NEXT_RESEARCH_PLAN.md).
- Raw forecast semantics and boundaries: [source protocol](artifacts/nhc_forecast_source_v1/PROTOCOL.md).
- Completed acceptance: artifacts/p6_live_v1/COMPLETED_ACCEPTANCE.json.

The model launch is consumed. Never rerun a launcher or use old answers as a fresh repeat. Read-only CPU verification needs neither an API key nor a GPU. Historical root navigation/status files remain frozen; CURRENT_PHASE.md is the mutable phase pointer.
