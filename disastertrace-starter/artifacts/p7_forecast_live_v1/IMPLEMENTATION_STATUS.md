# P7 native live engineering status

The user authorizes continued execution and explicitly reiterates four-GPU
parallelism on2026-09-08. Existing bounded automatic GPU permission persists.
The native task itself remains frozen at P7 offline acceptance
33c1c706e1528ab78e1e62f558411815c99ad4d4f78a4c90b1369c6fc95d4988.

Implemented in the new forecast_live namespace:

- Exact native renderer/carriers, schema, per-slot seeds and full tokenizer
  reservation before every request, with no evidence truncation or sanitization.
- Whole-target ownership across four TP1 workers; per-round batches of at most4.
- Exclusive phase/submission/worker claims, durable intents and started markers,
  raw-first results, strict returned-ID validation and separate parsed caches.
- Independent reconstruction of histories, request bodies/tokens, raw extraction,
  caches, timestamps, counters and all planned scores, including absent workers.
- ACP host/job/image/spec/volume/retry and origin binding; one no-generation
  preflight before the fresh model freeze; a common four-hour deadline.
- GPU-independent CPU review and actual installed XGrammar token-mask replay.

The first core test command failed in its fixture setup because the new test used
private instead of the compiler's existing private_reference key. The fixture was
corrected without modifying the accepted task. Initial lint findings were fixed.
core_004 subsequently passes56 native core tests. The full validation driver also
runs64 accepted P7 tests, giving120 core tests total; its command/exit is retained.

installed_001 retains8 passes and1 failing test expectation: XGrammar's native root
does not accept leading whitespace before'{'. The corrected test separately proves
lossless whitespace retention by the text adapter, rejection of the leading tokens
by the bound grammar, and acceptance of a legal final sequence. The second installed
run passes all9 tests with CUDA hidden; no weights are loaded for these tests.
Pytest's GPU environment reports one harmless unknown asyncio_mode option because
pytest-asyncio is not installed there. No environment is changed.

Full real-tokenizer diagnostics and CPU relocation are running through the unique
validate_offline.py invocation. Three policies each retain1542 planned slots. Its
CPU_ACCEPTANCE.json is written only after every command and relocation succeeds.
No P7 live model result is claimed at this status boundary. Later live/progress
records in this bundle supersede this engineering boundary without rewriting it.
