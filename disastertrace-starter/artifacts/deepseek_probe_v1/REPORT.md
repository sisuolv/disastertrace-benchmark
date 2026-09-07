# DeepSeek first live trial

One public development storm, one model and one method; a live protocol smoke test, not a heldout or cross-model benchmark conclusion.

Model: deepseek-v4-flash; reasoning_effort=high; thinking=enabled.
SDK probe: completed, 2.495 seconds; OpenAI SDK 3.8.0.
Benchmark: completed, 10 responses, Ida development, structured_state.

| Metric | Correct / opportunities |
| --- | --- |
| schema_success | 10/10 |
| state_accuracy | 50/50 |
| grounded_state | 49/50 |
| action_accuracy | 10/10 |
| unknown_accuracy | 18/18 |
| known_answer_coverage | 32/32 |
| required_change_success | 22/22 |
| preservation | 18/18 |

Total reported usage including probe: {'prompt_tokens': 51024, 'completion_tokens': 10734, 'total_tokens': 61758, 'reasoning_tokens': 9125, 'prompt_cache_hit_tokens': 15104, 'prompt_cache_miss_tokens': 35920}.
Estimated cost at documented off-peak prices: USD 0.015092567999999999; not a billing receipt.

No answer repair, retries, heldout calls or additional model/method runs were performed.
The API key is not stored in project files. Exact benchmark wire requests and response bodies are in the collection journal.

The sole citation deduction is a strict-locator mismatch, not a demonstrated
unsupported wind claim: the base branch c4 answer cites advisory 011 line 88,
which states 105 mph; the frozen scorer accepts only summary line 21, which also
states 105 mph. Original scores are preserved. See README_DEEPSEEK.md for the
reference-restriction issue and why a future scoring revision needs separate results.
