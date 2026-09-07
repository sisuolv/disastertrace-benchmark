# DeepSeek official documentation check

Retrieved on 2026-09-06 UTC with unauthenticated HTTPS GET requests. This check
does not establish successful inference, credential validity, account balance,
or observed parameter enforcement. Raw HTML, extracted text, HTTP status,
retrieval times and SHA-256 hashes are retained in this directory.

## Documented compatibility

- Chat Completions accepts `deepseek-v4-flash`, `deepseek-v4-pro` and
  `deepseek-v4-flash-vision-exp`.
- The OpenAI-format base URL is `https://api.deepseek.com`.
- `reasoning_effort="high"` is supported. Available effort levels are `low`,
  `high` and `max`; `medium` and `xhigh` map to `high`.
- The thinking guide explicitly demonstrates the OpenAI SDK with
  `extra_body={"thinking": {"type": "enabled"}}`. Thinking is enabled by
  default, with default effort `high`.
- The pricing page identifies the current flash version as
  `DeepSeek-V4-Flash-0731`. This is documentation metadata, not a claim about the
  version returned by any actual request.
- JSON output is documented. A request using `response_format` with
  `{"type": "json_object"}` must also instruct the model to produce JSON.

## Token and thinking semantics

- `max_tokens` is documented as the maximum number of tokens generated in the
  chat completion. Input and generated tokens together must fit the context.
- The model table lists a 1M context and maximum output of 384K. The retrieved
  pages do not provide a numerical default for `max_tokens` or an explicit
  explanation of how the cap is partitioned between reasoning and final answer.
- The response schema exposes `reasoning_content` separately from `content`,
  while usage includes `completion_tokens` and optional
  `completion_tokens_details.reasoning_tokens`.
- `finish_reason="length"` denotes a reached generation limit; JSON may be
  incomplete when this happens.
- In thinking mode, `temperature`, `top_p`, `presence_penalty` and
  `frequency_penalty` are accepted for compatibility but have no effect.
- Without tools, prior `reasoning_content` need not be sent and is ignored even
  if supplied. With tools, the documented continuation rules differ.

## Published flash prices

USD per 1,000,000 tokens, as retrieved from the official pricing page:

| Category | Off-peak | Peak |
| --- | ---: | ---: |
| Input, cache hit | 0.007 | 0.014 |
| Input, cache miss | 0.22 | 0.44 |
| Output | 0.66 | 1.32 |

Peak hours are Monday through Friday, 01:00-04:00 and 06:00-10:00 UTC. Other
hours are off-peak, including Sunday 2026-09-06. Prices can change. Cost computed
from published rates and returned usage is an estimate, not a billing receipt.

## Sources and execution

- `https://api-docs.deepseek.com/api/create-chat-completion/`
- `https://api-docs.deepseek.com/guides/thinking_mode/`
- `https://api-docs.deepseek.com/quick_start/pricing/`
- `https://api-docs.deepseek.com/quick_start/token_usage/`
- `https://api-docs.deepseek.com/faq/`

Two Python standard-library fetch commands completed with process exit code 0;
all five documentation fetches returned HTTP 200. Results are in
`fetch_status.json` and `supplemental_fetch_status.json`. Follow-up `rg` reads
completed with process exit code 0. No credential was used or stored by this
documentation subtask. No production files were changed. No tests were needed
for these static documentation artifacts. The next task is the parent's bounded
live connectivity probe and recording its actual response and usage.
