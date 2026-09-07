# P1 pricing and context snapshot

Official unauthenticated pricing fetch returned HTTP 200 on 2026-09-06 UTC.
The raw HTML hash matches the earlier same-day snapshot. Pricing and model
limits come from the same captured source referenced by rates.json.

Documented flash input/output rates per million tokens, USD:
- Off-peak: cache hit 0.007; cache miss 0.22; output 0.66.
- Peak: cache hit 0.014; cache miss 0.44; output 1.32.
- Peak windows: Monday-Friday 01:00-04:00 and 06:00-10:00 UTC.
- Sunday 2026-09-06 is off-peak.

The model table states a 1M context and maximum 384K output. This batch requests
4096 maximum output tokens. For conservative admission, reserve 1,048,576 prompt
tokens plus 4096 completion tokens at peak, all-input-cache-miss rates. This
over-reserves the combined context if output is included in that context.

Per pending request: (1048576 * 0.44 + 4096 * 1.32) / 1000000
= USD 0.46678016. A single sequential USD 1 batch ledger releases the unused
portion only after validated usage. Missing or uncertain usage retains the
reservation and stops the entire batch. No retry is authorized by this policy.

Keep actual off-peak/cache-aware cost estimates separate from conservative
peak-rate guard accounting. The software guard depends on the published prices,
context limit, truthful usage and max_tokens enforcement; it is not an invoice
or an unconditional provider billing guarantee. Reasoning tokens are already
in completion_tokens and must not be charged twice.

No credential was used and no inference request was made by this documentation
check. The wrapper/runtime source will be bound separately in the batch manifest.
