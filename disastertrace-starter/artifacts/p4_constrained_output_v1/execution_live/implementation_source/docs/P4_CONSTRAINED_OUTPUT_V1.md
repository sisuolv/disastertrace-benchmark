# P4: structure-constrained final JSON, offline candidate v1

This phase first prepares an independent development output track. On 2026-09-08,
the user explicitly permits automatic GPU use while requesting continued work.
After offline acceptance, this extension covers one fresh local 540-response matrix,
three methods, one repeat, no retries or extra probes. A distinct live freeze,
canonical run and deadline are required; the offline freeze remains diagnostic-only.
The completed P3 free-output 540-response matrix and its 340 invalid
answers remain frozen. No old output is repaired, replayed as a new answer, or
selected to construct this candidate. Gold remains automatic; no item-level human
annotation or LLM judge is introduced.

## Measurement and unchanged inputs

Use the identical balanced 36 episodes, 108 method trajectories and 540 slots,
common system contract v2, public renderer, automatic Gold, strict answer parser,
scorer, fixed denominators and carrier policy. All methods receive cumulative
public evidence. Each checkpoint has fresh messages; only its own trajectory's
last valid decision/history is carried. Wrong but contract-valid answers propagate;
invalid answers leave the prior carrier in place. No future evidence or Gold is
passed to the adapter. The program oracle used in diagnostics is not an LLM.

The new schema constrains exact containers, required keys, JSON types and the
known/unknown and three action literals. It does not constrain numbers to Gold,
encode ranges/precision, link unknown to null/empty evidence, enumerate record IDs
or correct lines, validate citation syntax, or link wind to action. These checks
remain in the original task contract and deterministic scorer. A structurally
valid answer can therefore fail the existing schema_success metric or semantics.
Report JSON, structural-schema and complete task-contract validity separately;
never change the original metric denominator or relabel it as JSON validity.

## Exact decoder candidate

Qwen3-8B and tokenizer are the same pinned snapshot as P3. Preserve BF16, thinking
enabled, temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition penalty 1, cap
8192 including reasoning, context 16384, one sample and the same per-slot seeds.
Input plus maximum output must fit context; no automatic truncation is allowed.
The offline execution grants no production calls; the separately scoped live
execution binds the current user's GPU instruction and these unchanged settings.

Use vLLM 0.10.2 V1, XGrammar 0.1.23, explicit xgrammar backend, fallback disabled,
any whitespace enabled, reasoning_parser=qwen3, no speculative decoding. Pass the
bound schema string through GuidedDecodingParams.json, not json_object mode.
The installed Qwen3 reasoner and StructuredOutputManager defer the token mask and
grammar advancement until after the generated </think> token. Ordinary reasoning
is unconstrained; the delimiter itself is not fed into the JSON grammar. Missing
delimiters and output-cap exhaustion remain visible failures.

The installed reasoner also searches the prompt for a closing delimiter. Reject
any prepared prompt containing that special token, including in a prior answer;
do not silently sanitize or drop the carrier. A later live collector must capture
this as a stopped prefix with the full planned denominator. Offline acceptance
checks every actual prompt in the diagnostic trajectories for this hazard.

XGrammar may restrict JSON property order despite JSON objects being unordered.
Bind exact schema bytes and verify its observed order: state then action, weather
fields in the existing FIELDS order, status/value/evidence within a slot, and
record_id/line within a citation. Only program fixtures are serialized in that
order to test token reachability; no historical or future model output is rewritten.
The order restriction and integer lexical form are decoder differences that must
be disclosed in comparisons, not treated as semantic changes to Gold.

## Offline acceptance and provenance

Freeze copied data/tokenizer/config, parent execution identity, source/spec/test
files, relevant installed backend sources, package versions and exact schema bytes.
Do not modify the historical GPU environment or require weights for report review.
Use a new diagnostic origin and exclusive output directories. Program-generated
token traces can test preparation/capture/audit/scoring but cannot demonstrate
GPU sampling reliability or speed. Actual grammar token-mask replay separately
establishes that tested token sequences are reachable under the decoder.

Required checks: all Gold and program controls (including deliberately wrong
values, citations and actions); genuine malformed and truncated failure retention;
all-method schema identity and carrier isolation; prompt/seed/token reconstruction;
actual vLLM reasoner gate and mask transitions without loading an LLM; tampered
schema/config/source/token/origin rejection; unchanged historical protected files.
An independent CPU report must reconstruct without vLLM, Torch, network or weights.
Artifacts record every executed command, exit and observed failure.

Exclusive JSON writes retain the P3 fail-closed policy: partial/corrupt files cause
audit refusal. Do not reset claims or repair such a file for inferred model reuse.
Offline fixtures may be rerun only in new directories and retain their origin.

## Subsequent execution

After offline acceptance, prepare a fresh bounded live identity and verify
engine configuration in the actual GPU process before the first dispatch. Do not
claim that this offline execution grants production calls or reuses a P3 claim.
Keep all 540 slots, one repeat initially, the nine >=58/60 and <=2 length screens,
no selective retries and no heldout/training. Separate free/constrained result
tables. A matched remote-model track requires a freshly verified capability and
price profile; generic JSON-object mode is not equivalent to strict-schema decoding.
Only then plan more independent repeats, calibrated stress and frozen heldout work.
