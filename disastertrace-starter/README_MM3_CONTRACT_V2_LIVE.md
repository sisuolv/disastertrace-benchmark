# MM-3 output-contract V2 model validation

The new 12-request Qwen3-VL-8B-Instruct run completed on one H100 on 2026-09-09.
All 12 responses pass the predeclared structural parser and finish with EOS.
Query-site coverage is complete in 10/12, and strict task correctness remains 0/12.
These measures are distinct: parseable JSON does not establish complete or correct answers.

- [Detailed Chinese results](artifacts/multimodal_v1/mm3_contract_v2_live_20260909/IMPLEMENTATION_STATUS.md)
- [Reconstructed report](artifacts/multimodal_v1/mm3_contract_v2_live_20260909/REPORT.json)
- [Per-field error analysis](artifacts/multimodal_v1/mm3_contract_v2_live_20260909/ERROR_ANALYSIS.json)
- [Query coverage](artifacts/multimodal_v1/mm3_contract_v2_live_20260909/QUERY_COVERAGE.json)
- [Next diagnostics and four-GPU scheduling](artifacts/multimodal_v1/mm3_contract_v2_live_20260909/NEXT_STEP_CN.md)

The single-event development result is not a leaderboard or a balanced causal comparison.
All V1 and V2 responses remain preserved. The two phase launch claims are consumed.
