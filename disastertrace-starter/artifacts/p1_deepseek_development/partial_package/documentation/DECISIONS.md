# Decisions

## P1 live development comparison and restart recovery

- Execute the user-authorized 90-request development comparison using the frozen
  DeepSeek settings, three methods, three development storms, one fresh repeat,
  USD 1 conditional guard and no retries; retain the prior trial separately.
- Keep model inputs, source parser, task schema and v1/v2 scorers fixed throughout
  the batch. Preserve output truncation and structural failures instead of
  repairing answers or silently increasing max_tokens after observing failures.
- A machine restart leaves 79 admitted requests, 78 responses, one uncertain
  attempt and 11 unattempted checkpoints. Preserve the original running/pending
  records and report the absence of a known exit code. Do not infer provider
  failure, free execution or successful completion from missing local output.
- Finalize the original partial experiment offline into a new directory. An
  explicit local administrative error disposition closes the legacy collection
  schema without inventing a provider error or response. Keep original journals
  and pending reservation intact and score all 90 planned opportunities.
- Report received-response USD 0.123358592 as a subtotal; full incurred cost is
  unknown. The conservative USD 0.30435328 settlement plus USD 0.46678016 pending
  reserve leaves insufficient allowance for a new full-context reservation.
- The user's request to resubmit a background process motivates a separate
  proposed USD 1.5, maximum 91-attempt amendment with one explicit uncertain
  retry. Obtain that scope/budget answer before live continuation; keep all
  78 received answers, including invalid outputs, without selective repeats.
- Describe format-example effects as a hypothesis, since answer carriers supply
  prior JSON examples and the current prompt leaves action type implicit.
  Explicit common output typing and output-budget calibration precede broad
  method claims. The partial last method and fixed order further limit comparison.

## Original scope and first work package

- The user's v0.3 scope supersedes the historical packaged plan's requirements for new human annotation and port-policy expert approval.
- Extend the existing disastertrace package with an automated subpackage. Preserve legacy modules and tests; the new first work package must not rely on the known-defective legacy scorer or treat its results as verified v0.3 metrics.
- Separate public tasks and actual model requests from private labels and generated references.
- The first end-to-end run uses deterministic fixture/diagnostic backends or externally supplied predictions, never a fixture result presented as an LLM score.
- Inherited DisasterBench labels, parsed source facts, controlled release schedules, and any synthetic edits retain distinct provenance.
- No paid model calls, model weights, or operational tool execution are needed for this first work package.
- DisasterBench uses a strict derived protocol: admit 230 of 233 tasks, retain inherited plans, quarantine malformed source plans, and score missing/invalid responses over the full admitted denominator. This is not the upstream permissive parser or an extreme-weather-only subset.
- CyPortQA's 48 templates are inventoried by eligibility. The implementation does not claim to recover or evaluate the full CyPortQA QA dataset.
- The dynamic example retains three original official NHC Ida reports. The two release schedules are controlled; neither source issue time nor retrieval time proves historical public availability.
- Dynamic answers describe the latest available reported observations, not a correction for the same forecast valid time. Full visible evidence is supplied at every checkpoint, so the example does not establish causal dependence on the state carrier.
- Dynamic Gold is generated_by_spec, with fact_origin=derived_from_source and schedule_origin=controlled_release. Original source text is unchanged. The unsupported port-reopening field is an explicit insufficiency control.
- The public 100 mph threshold is a research rule used to exercise a transition between the selected 85 and 105 mph reports. It is not an operational port or emergency policy.
- Build artifacts bind source provenance, generated records, and implementation hashes. A copy of the automated Python sources is retained in each new build. Changed code requires a fresh build/run; prior artifacts are preserved.
- All current backends, including externally supplied files, are marked ineligible_for_llm_leaderboard. The submission importer cannot attest which prompts an external model actually saw.
- Conditional change/preservation denominators depend on the model's actual prior state. Report their counts and do not pool planning, field correctness, and action metrics into one score.

## Second work package

- Freeze a purposeful catalogue of 12 Atlantic storms and advisories 009/010/011 before acquisition or model results. Assign four development and eight heldout storms; previously inspected Ida remains development. Do not replace rejected events or tune the frozen NHC parser on the heldout data.
- Keep failed source admission distinct from missing model evidence. Thirty-two source records pass the unchanged parser; only complete three-record events enter dynamic tasks. Ten events remain (three development, seven heldout); two parsed Harvey records are retained in the source inventory but not used in task episodes.
- Catalogue storm-name case is compared case-insensitively; original parsed names and raw text are preserved. This fixes adapter identity matching without broadening the frozen source parser.
- Retain both branches within each storm split. Check exact source-byte duplicates across splits and report unresolved near-duplicate/template similarity and pretraining contamination separately.
- Report per-event scores, equal-weight event macro rates, pooled opportunity counts, and paired base/delay differences. No confidence intervals or representative-population claims for this selected small cohort.
- Keep provider collection separate from offline submission import. The collector saves exact wire requests and responses, keeps model-authored state, enforces a global request-attempt cap, and performs no automatic retries. An import makes zero provider calls even when importing a separately collected response file.
- Provider configuration requires an explicit endpoint/model and token-parameter convention; credentials come from environment variables. Preparation makes no network calls. Aggregate token and monetary caps are not implemented, and sample config is not authorization for paid calls.
- At the start of this package, no model endpoint, key environment variable, or model budget was configured. The user was asked for model/service and budget while independent data and adapter work continued.

## Pre-API pilot preparation

- Complete all independent first-pilot engineering before asking again for the unresolved model configuration. The user's request authorizes subsequent API testing; it does not identify a provider, credential or spending limit.
- Compare structured_state, snapshot and answer_history using the same cumulative delivered evidence and fresh messages. The carrier is actual schema-valid output, including factual errors; no Gold repair. This is not a causal memory-isolation experiment.
- Retain the original source parser, all 12 predeclared events, 36 acquisition rows, 32 parsed records and 10 admitted events. Run exact/normalized duplicates and fixed word-five-shingle Jaccard analysis without tuning the threshold or replacing heldout samples.
- Independent collection audit reconstructs actual wire requests, accepted history, raw completion envelopes and usage. Scored runs bind that audit and reject any imported completion lacking an audited response. Local consistency does not authenticate the provider.
- Resume only an independently verified prefix into a new directory, preserving old artifacts and cumulative caps. No reissue of received invalid JSON, uncertain in-flight attempts or provider errors. Copy verified in-memory rows to avoid a second unverified source read.
- Request-body byte guards and output-token reservations complement the attempt limit; they do not establish total token use or enforce a currency budget. Provider-specific context support, billing/prices and missing usage remain explicit.
- Freeze two unresolved model slots, three methods and one repeat. Ida-only smoke is 60 attempts; full development 180 and heldout 420. Smoke overlaps development and cannot be pooled as independent samples. Actual models and service constraints are frozen later, before model results.
- Preflight requires expected positive/negative diagnostic behavior, independent data checks and implementation-matching full-suite evidence for offline_ready. live_ready remains false while actual endpoint/model/credentials/budget are unresolved. Every diagnostic and injected transport rehearsal is labeled as non-LLM.
- The first API pilot preparation is distinct from completing the full research program: cross-hazard/multimodal expansion, richer correction/cancellation variants, adaptive Frontier search and broad generalization remain subsequent work.

## First authorized DeepSeek trial

- The user's provided model, endpoint, credential and request to try it authorize a bounded connectivity probe and small development sample. Execute 1 SDK probe plus 10 Ida/structured_state requests; do not infer authorization for the whole two-model matrix.
- Use the exact requested deepseek-v4-flash, high reasoning effort and enabled thinking mode. Add typed, hashed provider options; omit temperature because the official thinking-mode documentation says it is ineffective.
- Hold the provided key only in the calling process/environment, obtained via a non-echoing prompt. The example config stores only DEEPSEEK_API_KEY's variable name. No key file or inline credential is needed.
- Preserve all model responses and the existing scorer. The live trial's 49/50 strict grounded score includes an equivalent citation that the frozen reference rejects; report the restriction instead of presenting it as an unsupported weather claim or silently upgrading the score.
- Price calculations use captured official rates and returned cache/usage data; reasoning tokens are already part of completion tokens. The estimate is not an account debit or invoice. Budget limits for larger trials remain to be chosen.

## P0 versioned evidence scoring and offline migration

- The user's next-step instruction executes P0 plus metric definitions/implementation from OPTIMIZATION_ROADMAP.md. This package requires zero new model requests; a broader development matrix remains the next experiment.
- Keep dynamic.py, sources.py, workflow.py and model input/runtime contracts unchanged. Add standalone nhc_equivalent_support_v2 and dynamic_score_v2.0 modules; do not overwrite v1 scores or silently relabel them.
- Accept only restricted source-supported summary/body constructions, with latest delivered report, entity/time, exact canonical value/unit and locator checks. At least one citation is required for known answers and every supplied citation must pass. Unsupported grammar is evaluator_unverifiable, not automatically hallucination.
- Fixed Gold transition and preservation denominators include unsuccessful attempts and do not depend on model prior correctness. Known-only correctness, conditional self-error recovery and provenance refresh have separate definitions; zero opportunities produce null rates. V1 model-dependent metrics remain separately labeled.
- Historical migration verifies archived source/build/run/collection, executes the trusted saved implementation in a temporary private module namespace, and binds a new scorer/index/difference package. Verification recomputes from saved source; no historical manifest identity is rewritten.
- The original ten-response trial reproduces 49/50 strict grounding; derived v2 is 50/50 with one equivalent-citation difference. This changes evidence evaluation, not observed model behavior or heldout performance. New collection work needs a fresh build matching the new implementation.
