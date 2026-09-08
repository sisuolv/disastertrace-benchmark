# P3 balanced development / local GPU protocol v1

This is a separate development experiment authorized by the user's 2026-09-07
instruction to autonomously execute the next plan, with GPU use permitted and
approximately four hours until review. It uses zero paid API requests. The old
DeepSeek scopes and captured records are not reused as local model history.

## Design frozen before local model responses

- Profile: `controlled_source_case_balanced_v1`.
- Three frozen development source groups: AL092021, AL062018, AL052019.
- Fully cross 3 sources x 3 families x 2 cases x 2 branches x 5 checkpoints x
  3 methods = 540 responses; 36 episodes, 108 isolated trajectories, 18 matched roots.
- One repeat, no selective retries, no new per-item human review, no LLM judge,
  no heldout inference, no training. Invalid/missing outputs retain opportunities.
- Legacy generator, public renderer, strict parser, Gold compiler and scoring
  arithmetic remain unchanged. An explicit new source/case selector adds the
  missing case for every group. The 18 original episodes remain exact members.
- Independently reparse all three source records, validate each event graph,
  compare Gold with the public-only oracle, and run all ten program controls for
  all three methods (5,400 diagnostic responses, never called model results).
- Shuffle trajectories with seed 20260907; run checkpoint waves c0..c4. Batch 12
  trajectories at a time, never two checkpoints from the same trajectory in a batch.
- Every family x method has 60 planned responses. All nine cells must have at
  least 58 schema-valid outputs and at most 2 length finishes. This scales the
  earlier 29/30 and 1/30 descriptive screen; it is not a confidence bound or proof
  of a 96.7% population reliability rate. Complete collection is also required.

## Model and runtime

Qwen/Qwen3-8B, official Qwen ModelScope repository, BF16 full weights. Each downloaded
file is pinned to its ModelScope commit and checked against the official SHA256 and
size listing. The collection of per-file revisions is the snapshot identity; do not
represent it as an observed Hugging Face commit. Hugging Face was unreachable from
this environment. Apache-2.0 license and model card are retained.

Use an isolated Python environment, vLLM 0.10.2, one H100 MIG 3g.40gb device (about
40 GB available, despite the physical H100 80GB label), tensor parallel 1, 85% memory
utilization, maximum 12 sequences and 16,384 context tokens. Eager execution avoids
CUDA-graph capture overhead; prefix caching is disabled. No quantization, training,
adapters, speculative decoding or externally exposed HTTP server.

The original Qwen3 model card recommends thinking sampling temperature 0.6, top_p
0.95, top_k 20, min_p 0 and warns against greedy decoding. Use these settings,
repetition penalty 1, thinking enabled, one sample, and a deterministic per-slot seed.
Set the common generation cap to 8,192 tokens, including reasoning and final answer.
This resource-bounded screen is shorter than the model card's general 32,768-token
recommendation; report cap failures explicitly. It is not a full-budget Qwen score.
No prompt truncation or automatic cap reduction is permitted. The frozen execution
contains a UTC deadline; stop before the next batch after that time.

## Cross-model capability mapping

| Capability | Historical DeepSeek v2 | Local Qwen3-8B |
| --- | --- | --- |
| System / user | Shared v2 system + canonical public task | Identical messages, official tokenizer chat template |
| Explicit answer carrier | Method-isolated final decisions | Same policy; new local answers only |
| Reasoning | Provider thinking enabled, high | enable_thinking=true; no high-equivalence claim |
| Length cap | 8,192 provider completion tokens | 8,192 generated tokens, including reasoning |
| Sampling | No temperature supplied | Official suggested 0.6 / 0.95 / 20 / 0 |
| Transport | Remote HTTP response capture | In-process GPU token/result capture |
| Usage | Provider counts | Actual prompt/output token lengths |
| Runtime version | Provider model label and captured config | Per-file weight hashes, package inventory, CUDA/device observation |
| Failure | HTTP, invalid schema, length | Runtime exception, context overflow, invalid schema, length |
| Cost | Captured-price estimate, not invoice | GPU cost unknown; zero paid API calls does not mean zero GPU cost |
| Latency | Request observation | Shared batch wall time; not comparable per-request latency |

## Capture, reasoning extraction and audit

The model only receives rendered public evidence and its declared carrier. Episode
IDs, source group labels, private Gold and future deliveries never enter messages.
The local backend accepts prepared public prompt tokens, not episode objects or Gold.

A canonical production directory is an exclusive one-use launch claim. Before each
batch, persist an intent containing the exact slots, public requests, messages, prompt
tokens and sampling seeds, then fsync. Persist each response separately, including
all generated token IDs, raw vLLM text, finish/stop reasons and shared batch wall time.
An interrupted intent stays unresolved; the collector has no inference-resume path.
Audit saved prefixes without credentials and without generating another response.

Qwen's prompt opens a thinking block. Require exactly one closing `</think>` token;
preserve the reasoning and token inventory. Remove only a terminal EOS token
(`im_end` or `endoftext`, both in the official generation configuration) when
extracting final content. Missing/multiple delimiters produce empty final content and
an explicit extraction error. Never repair JSON, citations, code fences or extra keys.
Only schema-valid final decisions become carriers; wrong but schema-valid decisions
remain carried model claims. Reasoning content never enters later messages.

The auditor separately reconstructs every prompt/carrier, token decoding, extraction,
usage and acceptance decision. It rejects diagnostic/model origin mixing, unexpected
slots, reordered/missing captures, unbound runtime settings and orphan files. Shared
score arithmetic is called only after provenance auditing. Local origin is supported
by frozen code and captured execution observations, not hardware attestation.

## Reporting and limits

Report all fixed denominators, values, current citations, unknowns, action compliance,
schema/length failures, automatic field/action error inventory, and paired method
outcomes within each source. No binomial confidence intervals or significance claims
treat 540 checkpoints as 540 independent storms. There are still only three source
groups, synthetic controlled update sequences and one stochastic sample per slot.

All methods receive cumulative evidence. This experiment tests the additional effect
of explicit answer carriers under that condition, not pure long-term memory or weather
forecasting. Weather values are source-inherited; later revisions are constructed.

Do not combine historical 270-version DeepSeek scores with new 540-version Qwen scores
in a model ranking. A future matched model comparison must use this same frozen data
version. Additional difficulty factors require a separate specification and automatic
validation before inference; no examples are selected because this model failed them.

## Reproduction

Use `python -m disastertrace.local_eval.cli --help`. The artifact bundle records exact
commands, package versions, source snapshots, observed exit codes, raw outputs and
the final independent reconstruction. Use its frozen `implementation_source/src`
with `PYTHONDONTWRITEBYTECODE=1`. Never rerun a consumed production collection.
