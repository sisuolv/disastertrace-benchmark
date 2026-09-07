# Explicit provider interface

This module prepares public dynamic tasks and collects one text response at each
selected checkpoint. It uses the Python standard library and the Chat Completions
wire shape supported by many local vLLM deployments and hosted compatible
endpoints. It does not select a model or install model weights or SDKs.

The adapter, collection journal, independent audit, and safe-prefix recovery
were initially tested with injected transports and a temporary loopback server.
On 2026-09-06 the user's OpenAI SDK probe and ten-checkpoint Ida collection with
`deepseek-v4-flash` completed successfully, using high reasoning effort and
thinking enabled. See README_DEEPSEEK.md and artifacts/deepseek_probe_v1/ for the
actual results. This establishes compatibility for the recorded model/config,
not for every hosted endpoint; fixture results remain separate from LLM results.

## Configuration and preparation

`configs/provider.example.json` is a local-server example with an intentionally
unselected model ID. The original eight configuration keys are mandatory; two
additional optional keys are documented below. Unknown keys,
inline `api_key` or password properties, invalid values, and URL credentials,
queries, and fragments are rejected. The frozen `ProviderConfig` also validates
direct construction.

| Key | Meaning |
| --- | --- |
| `model` | Exact served model identifier; the returned model identifier is recorded separately |
| `base_url` | API base ending in e.g. `/v1`; the adapter appends `/chat/completions` |
| `key_env` | Environment variable containing a bearer token, or `null` for an unauthenticated local server |
| `max_output_tokens` | Positive output cap sent using the explicitly selected token parameter |
| `token_parameter` | Exactly `max_tokens` or `max_completion_tokens`; compatibility is endpoint/model specific |
| `temperature` | Number in `[0, 2]`, or `null` to omit the field for models that reject it |
| `timeout` | Positive urllib socket timeout in seconds; this is not an end-to-end wall-clock budget |
| `max_response_bytes` | Positive maximum accepted response-body size; one extra byte is read to detect overflow |
| `reasoning_effort` | Optional; null/omitted, or `low`, `medium`, `high`, `max`, `xhigh`; support is provider/model specific |
| `thinking_type` | Optional; null/omitted, `enabled` or `disabled`; sends the explicit `thinking.type` wire field |

`configs/provider.deepseek-flash.example.json` selects the user-requested
`deepseek-v4-flash` with `reasoning_effort=high` and `thinking_type=enabled`.
Arbitrary `extra_body` is not accepted in a benchmark config; supported options
are typed, validated and included in configuration and wire request hashes.
Missing optional fields emit no corresponding wire fields. Their null defaults
are still present in the current serialized configuration, so this source revision
uses a new build; old collections remain reproducible with their saved code.
DeepSeek's documented thinking mode ignores temperature, so its config omits it
by setting `temperature` to null. Returned reasoning detail remains in response
metadata and is not added to the declared answer carrier.

HTTPS is required outside loopback. HTTP accepts only `localhost` or an IP
recognized as loopback; URL redirects are not followed. Loopback requests do not
use environment-configured proxies. Hosted configurations require an explicit
`key_env`; its value is read only by `complete()`, never by `prepare()`.

```python
from disastertrace.automated.common import strict_json
from disastertrace.automated.provider import ProviderClient, ProviderConfig
from disastertrace.automated.dynamic import render_request

config = ProviderConfig.from_dict(strict_json(config_path.read_text()))
client = ProviderClient(config)
public_request = render_request(
    episode, checkpoint_id, actual_previous_decision,
    method="structured_state",
)
prepared = client.prepare(public_request)  # No credentials read and no network.
```

Preparation accepts exactly the public `render_request` shape. Evidence entries
contain their delivery index, ID, issue time and numbered raw text. Parsed source
fields, future release schedules and reference answers are rejected as extra
properties. The caller must still supply evidence from the correct checkpoint;
shape checks cannot establish the truth of a source document.

Every prepared payload starts fresh with one fixed system message and one user
message containing canonical public request JSON. It specifies `n=1`,
`stream=false`, the exact model ID, and the configured decoding fields. It does
not request tools, enable conversation memory, repair JSON, or execute actions.

`prepare()` returns `endpoint`, `payload`, exact `raw_request`, nonsecret
`config`, `config_sha256`, `wire_payload_sha256`, and `request_sha256`. The last
hash binds the endpoint, nonsecret configuration and complete wire payload;
`wire_payload_sha256` hashes the exact canonical JSON request body. Authorization
headers and credential values are excluded from logs and hashes.

## Declared methods

All three methods receive the same cumulative source evidence, including repeated
delivery of old reports, and return the same decision schema. Only the declared
answer carrier differs. The collector resets carrier and history at every episode
boundary and constructs a fresh system/user message pair at every checkpoint.

| Method | Additional public input |
| --- | --- |
| `structured_state` (default) | `previous_state`: the latest schema-valid model decision, or `null` |
| `snapshot` | No prior answer or state carrier |
| `answer_history` | `answer_history`: all schema-valid decisions previously accepted in this episode, in chronological order |

The default request retains its original shape for compatibility; the two other
methods include an explicit `method` property. A factually wrong but schema-valid
decision is carried unchanged. Invalid responses consume an attempt but do not
replace the accepted decision or enter answer history. No private reference is
consulted to correct the carrier. When calling `render_request` directly for
`answer_history`, pass the actual accepted decision list as `history=...`.

Method selection is frozen in run and collection metadata. Since every method
receives all evidence delivered so far, their comparison does not establish that
the task causally requires memory. Request length can differ because answer
history grows; report actual request sizes and available token usage separately.

## Completion and errors

`ProviderClient(config).complete(public_request)` performs one attempt and returns:

```text
{
  raw_response: <unchanged assistant message text>,
  metadata: {
    <all preparation fields>,
    raw_response_body, response_model, finish_reason,
    usage, usage_available, elapsed_seconds, http_status, attempt_count,
    reported_output_token_cap_exceeded,
    automatic_retry: false, cost: null,
    aggregate_token_cap_enforced: false, monetary_cap_enforced: false
  }
}
```

Malformed assistant JSON and truncated text remain unchanged for the benchmark
parser. An invalid HTTP response envelope, multiple choices, nontext content or
tool calls produce a `ProviderError`. Usage may be absent or null, in which case
token consumption is unknown, not zero. Present usage must include nonnegative
integer `prompt_tokens`, `completion_tokens` and their sum `total_tokens`.
Additional provider usage detail remains in the recorded body.

`ProviderError.code`, `.status`, `.request_may_have_reached_provider`, and
`.as_dict()` are safe to persist. Error codes distinguish missing credentials,
timeout, authentication/authorization failure, rate limits, other HTTP errors,
oversized bodies, invalid schemas and transport failures. Error response bodies
and upstream exception strings are never reflected in these errors. A successful
response containing the actual credential is also rejected before it is logged.

There are no automatic retries. A timeout or provider error can occur after the
provider accepted or billed a request; such attempts are not eligible for safe
resume. Repeating that collection is a new run and may incur another charge.
The per-request output parameter is a request to the provider, not a proof that
it enforced the cap. Reported excess is flagged. The collector additionally
supports an output-token reservation limit, described below. It does not enforce
an aggregate actual token budget or monetary cap, and no price estimate is inferred.

For tests, inject a callable with this signature:

```python
transport(url: str, body: bytes, headers: dict[str, str],
          timeout: float, max_response_bytes: int) -> tuple[int, bytes]
client = ProviderClient(config, transport=transport)
```

The callable receives the actual authorization header and must not log it.
Injected transports are labeled `injected_transport_unverified`; the default is
`urllib_http`. The injected label alone cannot establish that no network was
used. Test results here use fixtures and are not live model verification.

## Sequential collection and artifacts

```python
from disastertrace.automated.collection import collect_model

summary = collect_model(
    selected_episodes, config, new_output_directory,
    max_queries=explicit_global_attempt_limit,
    method="structured_state",
    max_request_bytes=262144,
    max_reserved_output_tokens=explicit_output_reservation_limit,
)
```

This call can contact the configured endpoint. Use `prepare()` alone for offline
inspection. A compatible test client can be passed as `client=...`; its config
must match the collection configuration.

The collector handles episodes in supplied order and derives the declared
carrier from actual accepted responses. The supplied episodes, ordered checkpoint
IDs, method, nonsecret provider configuration, limits, and transport label are
recorded in `plan.json`; v2 plans also retain per-episode hashes and resume lineage.

The attempt limit is global across all supplied episodes. Each invocation of
`complete()`, including a missing-credential failure that never reaches HTTP,
increments `attempts_started`. The first provider failure stops collection;
later checkpoints remain absent from the submission file and therefore receive
the importer's normal missing-response treatment. `attempts_started` is not a
verified count of actual model calls. Provider errors say whether a request may
have reached the endpoint.

Each new output directory contains:

| File | Contents |
| --- | --- |
| `plan.json` | Frozen nonsecret config, input episode hashes, method, complete checkpoint list, limits, transport label and optional resume lineage |
| `requests.jsonl` | Public request and exact prepared wire payload, appended and fsynced before each `complete()` call |
| `responses.jsonl` | Exact `{episode_id, checkpoint_id, raw_response}` rows accepted by the existing submissions importer |
| `outcomes.jsonl` | Request hash, response metadata and hashes, accepted/invalid/error status and actual resulting carrier |
| `summary.json` | Running/final status, attempt/completion/invalid/missing counts, reported usage, request bytes, output reservations and final artifact hashes |

Successful raw responses and outcomes are flushed and fsynced individually.
Existing output directories are refused. Partial artifacts are preserved on
failure. A crash may leave a prepared request without an outcome; that attempt is
in flight and is not automatically repeated. Filesystem durability does not
establish whether an unanswered request was billed. Reported token totals cover
only responses that included usage and exclude failed attempts and unknown usage.

The collector remains ineligible for an LLM leaderboard. Importing its
`responses.jsonl` does not convert the offline importer's counters into provider
call counts; actual collection provenance belongs to this separate artifact set.

## Independent audit and scored-trace binding

`audit_collection(selected_episodes, collection_directory)` makes no network
request. It reconstructs public requests from the exact episodes and the actual
previous accepted responses, reproduces the prepared wire payload, reparses saved
response bodies, and verifies outcomes, state/history transitions, limits,
counters, stop reasons, and hashes. It does not trust recorded validity or token
counters without recomputing their supporting values.

```python
from disastertrace.automated.collection_audit import audit_collection

audit = audit_collection(selected_episodes, collection_directory)
assert audit["valid"]
# safe_to_resume is a separate result; a valid error log need not be resumable.
```

The build-level `collect-model` command writes `build_context.json`, performs
collection in its `collection/` child, saves `collection_audit.json`, imports
responses into `imported_run/`, and writes `score.json` and `result.json`. The
import binds the collection's audited requests and exact responses to the trace
used for scoring. Checkpoints without an audited completion cannot acquire a
fabricated response in that bound trace. Subsequent scoring rechecks the saved
collection artifacts, audit digest, method, requests, and responses. Missing or
unattempted checkpoints remain in the declared denominator.

This establishes consistency of local artifacts, not cryptographic authentication
of a provider or proof that a local response was generated by the claimed model.
A party able to replace every artifact can still fabricate a mutually consistent
record. The audit reports `provider_authenticated=false` explicitly.

The CLI form is:

```bash
disastertrace-auto audit-collection \
  --build work/build-current \
  --collection work/model-trial/collection \
  --split development --event-group AL092021 \
  --output work/model-trial-audit.json
```

These are example paths: use the actual frozen build and collection directory.
The split and optional event groups must reproduce the original selected episodes.
For an interrupted `status=running` journal, add `--allow-incomplete`; the audit
will distinguish a clean completed prefix from an uncertain in-flight request.

## Safe resume into a new directory

Resume is explicit and preserves the existing artifact directory. Supply the
exact directory containing `plan.json`, `requests.jsonl`, `outcomes.jsonl`,
`responses.jsonl`, and `summary.json`, not the enclosing build-level model run.
For `collect-model`, this normally means `--resume-from old-run/collection`.
The new `--output` directory must not exist.

```bash
disastertrace-auto collect-model \
  --build work/build-current --config configs/provider.selected.json \
  --split development --event-group AL092021 --method structured_state \
  --resume-from work/model-trial/collection \
  --max-queries 10 --max-request-bytes 262144 \
  --max-reserved-output-tokens 10240 \
  --output work/model-trial-resumed
```

This example can contact the configured endpoint. The reservation value assumes
`max_output_tokens=1024`; choose explicit limits matching the selected provider
configuration and intended experiment. It does not authorize a particular spend.

Before any new request, resume independently audits the old journal. It requires
identical episodes and ordering, method, provider configuration, and transport
kind. Completed valid and invalid responses are copied into the new journal and
never repeated. Actual state/history is reconstructed from those outcomes; old
attempt and reservation counters count toward the new total limits. Thus
`--max-queries 10` means at most ten total attempts across the recovered prefix
and new suffix, not ten additional attempts.

A clean prefix stopped by attempt or guard limits can resume with sufficient
new limits. A running journal can resume only if its durable request/outcome
prefix is complete and consistent. A pending request, orphan in-flight response,
or provider error is refused: the collector cannot infer whether that request
was executed or billed. Recovery lineage records the source path and plan/summary
hashes while preserving the old directory.

## Request and reservation limits

Both optional limits are checked before journaling and invoking the next request:

- `max_request_bytes` limits each canonical prepared request body in UTF-8 bytes.
  It includes the selected answer carrier but excludes HTTP headers. If the next
  body is too large, collection stops with `request_bytes_exceeded`.
- `max_reserved_output_tokens` reserves the configured `max_output_tokens` once
  for every started attempt, including attempts whose completion is invalid or
  fails. Collection stops with `output_reservation_exhausted` before a request
  would exceed the total reservation. This is a conservative configured-output
  allowance, not a measurement of actual output or reasoning-token consumption.
- Resuming cannot lower limits below already started attempts, already reserved
  output tokens, or the sizes of already journaled requests.

The request-body guard is not a model context-window check, and the reservation
does not cover input tokens or establish that the provider enforces its output
parameter. Provider-specific token accounting, pricing, and an actual monetary
budget still need to be selected before the first live trial. These limits do
not guarantee a currency spending ceiling.

## Official documentation access record

The OpenAI Docs skill was applied. Official documentation was requested before
implementing the adapter, but every attempted page returned HTTP 403 in this
environment on 2026-09-06:

- `https://platform.openai.com/docs/api-reference/chat/create`
- `https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create`
- `https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create.md`
- `https://developers.openai.com/api/docs/guides/text`
- `https://developers.openai.com/api/docs/llms.txt`
- `https://developers.openai.com/api/reference/chat/create`
- `https://platform.openai.com/docs/api-reference/chat/create?format=markdown`

These are attempted official reference URLs, not successfully fetched citations.
No current model support, pricing, account availability, or endpoint-specific
parameter support is claimed from those failed fetches. The supported wire
contract is documented and tested here; the chosen server still requires a
small, explicitly configured real model probe before comparison experiments.
