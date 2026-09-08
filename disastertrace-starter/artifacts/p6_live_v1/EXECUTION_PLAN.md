# P6 paired model execution and forecast-source continuation

The accepted P6 offline parent remains unchanged. This phase uses repeat_live,
its own frozen source, registry and execution IDs. The user approved continuing
the next-step plan on 2026-09-08; prior permission for automatic ACP GPU use
persists. No new permission round or credential is required.

## Frozen model matrix

- Model: pinned Qwen3-8B; same tokenizer, renderer, public evidence and scorer.
- Conditions: base and irrelevant_scope level 4; 36 episodes, 5 checkpoints,
  3 methods, 2 repeats: 2,160 opportunities, 432 trajectories, 1,080 pairs.
- The two conditions in each pair share a sampling seed. Method and repeat are
  in the seed key; condition is excluded. Each repeat owns its own carrier.
- One full H100 80GB, TP1, BF16, XGrammar final-only JSON; no fallback or repair.
- Output cap 8,192; total context 16,384; batch 12; 17,694,720 output-token ceiling.
- One ACP worker runs the complete matrix on computing-cluster-01g-02.
- Generation-disabled preflight: 1,200-second timeout, no generate/add_request/step.
- Production collector ceiling: 14,400 seconds; ACP worker ceiling: 16,200
  seconds including 1,800 seconds reserved for CPU report/verification. TERM has
  at most 60 seconds to complete before KILL. An absolute UTC deadline is fixed
  at live freeze and rechecked before each dispatch. Queue delay consumes that
  deadline; it never authorizes retries or duplicate submissions.
- One-use submission and collection registries. Ambiguous/failed submissions and
  started attempts remain consumed. All failures stay in the full denominator.
- GPU Python is the existing AFS Qwen environment; CPU audit uses the separate
  existing review environment. No dependency upgrades or new model downloads.

## Validation and evidence

95 CPU tests pass (30 live-extension tests and 65 P6 tests). The initial missing
module test run and all implementation-stage logs remain recorded. The model
backend submits explicit attempt IDs to the version-pinned vLLM engine, retains
completed outputs on engine errors, and durably writes the returned batch before
parsing or carrier promotion. CPU reconstruction independently re-renders each
request, seed and carrier and checks tokens, timestamps, termination and counters.

Before production: full correct and invalid-control diagnostic runs against the
new live freeze; model initialization preflight bound into that freeze; fresh
launcher acceptance. After production: independent report, token-mask replay,
CPU relocation with original paths/network blocked, and preservation verification.

Report checkpoint accuracy alongside episode success/pass^2, source/repeat ranges,
all four paired outcomes, exposure slices and actual token/time use. There are
only three independent storm sources, so results are development descriptions.

## Forecast-source stage

The frozen original catalogue declares eight heldout storm IDs; seven were
admitted and Matthew was quarantined. Protect all eight declared IDs. Ian
AL092022 appears in supplied plan examples but remains heldout and must not be
downloaded for the new development track. Record plan exposure separately.

Candidate source scope: Francine AL062024 forecast advisories 005-010 and Ida
AL092021 forecast advisories 009-014, twelve planned bodies total. Francine is
explicitly development after plan exposure; Ida was already development. The
final acquisition manifest must bind these IDs and existing split hashes before
network requests. Failures are quarantined without replacement or repeated fetches.

Use two independent parsers for issue/center/forecast-valid times and coordinates/
sustained wind. Save raw bytes, SHA-256, retrieval metadata, canonical text and
byte/line support. Do not infer a model initialization time, first availability,
or forecast pressure from an advisory that does not state it. Pair versions only
at the same absolute forecast-valid time. Parser disagreement or ambiguity goes
to quarantine. The raw and normalized task views carry the same measured fields.

Length/carrier controls, second-model inference, training, extra phenomena and
multimodal tasks remain subsequent separately frozen studies. They do not add
requests to this matrix.
