# DisasterTrace: novelty-alignment diagnosis and Horizon 1.5

Companion to `docs/PLAN_V20_NEXT_STEPS.md` (additive, not a replacement — Horizon 1's Tracks A-E keep
executing exactly as already planned). Written after the user shared a research-positioning document,
`plan/DisasterTrace_Novelty_Integrated_20260924.md`, defining DisasterTrace's three claimed research
contributions, and asked (1) to use it to optimize the follow-up plan, and (2) whether the benchmark's
actual construction has been following this framing. Three parallel research audits and one independent
adversarial critique of this document's own claims (`fableplan:complex-executor`) ran before this was
written; corrections from that critique are folded in below rather than listed separately.

## The three contributions, briefly

- **C1 — Active Evidence Value**: does an agent's own active search/matching/processing of evidence, on
  top of a continuously-updating professional baseline, produce real predictive value?
- **C2 — Mechanism Attribution**: when value isn't produced, where was it lost, across the chain
  ACQUIRE → MATCH → PROCESS → STATE → PREDICT → ADOPT (six labeled failure categories, C2-1..C2-6)?
- **C3 — Generalization Boundary**: do C1/C2's findings hold across evidence sources, modalities, shared
  multi-target settings, and physical processes, or are they an artifact of one text format?

The novelty document's own section 18 explicitly warns against letting the benchmark collapse into "TAF
update → change probability," losing the active-acquisition and target-evidence-matching stages of the
intended pipeline.

## Diagnosis: current construction vs. the novelty document

**`docs/PLAN_V20_NEXT_STEPS.md` is ~100% Controlled-track substrate work.** It hardens the ground truth
C1/C2/C3 would eventually stand on, but does not itself build or demonstrate any of the three
contributions as agent capabilities. This is a scope diagnosis, not a judgment on the work's value —
Tracks A-E fix real bugs and are worth finishing — but none of Horizon 1's five tracks, nor Horizons 2-5,
contain an item that builds active acquisition, attributes an acquisition/matching failure, or advances
generalization.

**C1 (active acquisition) — not implemented in the active line, but not un-worked-on either.**
`NaturalKernel.RETRIEVE` (`src/disastertrace/monitoring_v1/natural_track_v18.py`) can structurally target
different sources, but `public_state()` (`:168-177`) — the only thing any policy ever sees (`replay_suffix`,
`:335`, the only policy call site in `src/`/`scripts/`) — never discloses a catalogue of retrievable
options. One script, `scripts/build_v18_natural_synthetic.py:16-23`, does configure a two-source kernel,
but it drives a hard-coded action list, not a policy, so even there nothing ever chooses between the two
sources. Evidence-target matching (spatial/temporal/variable) is entirely precomputed by `qualify_stream`
before any agent sees anything — the exact anti-pattern the novelty document's section 20 names ("don't
let pre-matched backend gold pass as agent active-matching capability"). However: real, previously-run
active-acquisition selector code already exists — `public_query_selectors.py`, `residual_query_plan.py`,
`selector_contract_v2.py` (round-robin/recency/fixed-hash selectors, a real LLM-callable shared-budget
allocation contract) — with real historical model results matching the novelty document's own section
12.1 claim closely (LLM selector Brier 0.004915262 vs. fixed-hash 0.004859230 and round-robin 0.004865804,
only beating coverage 0.004978936 and batch 0.005170429; these numbers are corroborated against a prior
AI-generated audit report, not against a raw experiment artifact in this repo — cite with the same "prior
AI-reviewed, not independently reproduced this round" caveat used elsewhere in this project, and note the
source itself flags a different 12-day subset with a different denominator than full-calendar figures
elsewhere). This selector code is not orphaned in the sense of dead/unreferenced: `public_query_selectors`
is imported by `monitoring_v1/policies.py:66`; `residual_query_plan` by `policies.py:83,86` and
`formal_session.py:115`; `selector_contract_v2` by `policies.py:72`, `session_checkpoint.py:78`, and
`api_transport_v2.py:269` — live modules in the same package as `natural_track_v18.py`, part of an older
production/formal-session line the v18 kernel simply never adopted.

**C2 (mechanism attribution) — real but lopsided.** The intervention suite in
`src/disastertrace/monitoring_v1/interventions_v18.py` (`identity_repeat`, `same_origin_duplicate`,
`matched_sham`, `withhold`, `delay`, `repair`) genuinely implements the novelty document's paired-
intervention design for the state/timing half of the chain — real, tested, load-bearing code (C2-4 and
C2-6 covered, C2-5 partially). But there is zero mechanism for C2-1 (acquisition failure) or C2-2
(matching failure) — same root cause as the C1 gap: no active-retrieval agent exists to attribute either
failure to, and `qualify_stream`'s classifier is the backend ground truth used to grade evidence, not a
probe of an agent's own matching judgment. No document in the repo maps any planned work onto the
ACQUIRE/MATCH/PROCESS/STATE/PREDICT/ADOPT vocabulary. Multi-target sharing: one real, tested module exists
(`monitoring_fixed_v1/joint_targets.py`), but it only answers "does a model correctly scope shared context
to the relevant targets" (Controlled-track leak-prevention), not the real question — whether an agent's
own choice to share/reuse evidence produces behavior a per-target solve couldn't replicate. Referenced by
nothing outside its own tests. `NaturalKernel` itself has no target concept at all yet (independently
corroborated by this round's ADR-001 work, which found `_repair` doesn't bind even one target today).

**C3 (generalization) — real assets exist, disconnected from the active pipeline, and under-inventoried.**
Section 12.1's historical claims (B00: 168 cases/840 trajectories; C00: 12 parents/48 GET branches; M01:
864 opportunities/857 settleable/3 positive; the selector-vs-baseline Brier numbers) all match, exactly, a
prior AI-generated audit report (`plan_v14_0919/extracted/DisasterTrace_SOTA_Audit_Redesign_20260919/
FULL_REVIEW_AND_REDESIGN_CN.md` and its sibling `REPORT_CN.md`) — not fabricated for this new document,
but also not independently reproduced this round; cite with that caveat. Real, non-trivial code exists for
multiple C3 axes: `multimodal_v1/` (including NHC hurricane-track rendering — literally a C3-4 tropical-
cyclone candidate), `multimodal_atomic_v1/`, `multimodal_live_v1/`, and `hydro_shadow_v1/` (a second-
physical-process/hydrology candidate). `multimodal_v1` specifically is not internally orphaned — it's
imported as the shared base by 7 files each in `multimodal_atomic_v1/` and `multimodal_live_v1/`, an
active cluster in its own right; what's disconnected is the whole cluster relative to the v18/v20
pipeline. `hydro_shadow_v1` is more genuinely isolated, referenced only by its own tests.
`docs/PLAN_V20_NEXT_STEPS.md`'s Horizon 5 is a single unexamined "parked" bullet that names none of this
reusable code.

**Bottom line**: three separate past phases of this project already built large pieces of C1/C2/C3, and
the current v18/v20 line — which the last several rounds of this session have been exclusively hardening
— never got reconnected to any of it. The fix this round is not to design or wire up C1/C2/C3 from
scratch, and not to attempt it all in one pass: it is to (a) inventory what already exists with honest,
stated revival criteria, and (b) claim and scope two concrete design questions this diagnosis surfaced,
without yet committing to how heavy a process each deserves.

## Horizon 1.5 — between the current Horizon 1 and Horizon 2/D1

### N1 — orphaned/disconnected-asset inventory: results

Import/compile-check done for all nine candidate modules (all green). Each asset's own existing test suite
then run under `DISASTERTRACE_OFFLINE=1` (no source edits — pytest writes `.pytest_cache`/`__pycache__`
only), reported honestly below, not assumed:

| Asset | Tests run | Result | Verdict (stated criteria) |
|---|---|---|---|
| `public_query_selectors.py` + siblings discovered during the run (`pending_selector`, `v13_selector`) | `test_monitoring_public_query_selectors.py` (22), `test_monitoring_pending_selector.py` (7), `test_monitoring_v13_selector.py` (29) | 58 passed, 0 failed | **Reusable with adaptation.** Fully tested, live-imported by `monitoring_v1/policies.py` today — not dead code. Not "as-is": lives in a different vocabulary (`session_quiescent`/`opportunities`/`e_f_pairs`) than the v18 `NaturalKernel` line (`checkpoints`/`qualifications`); bridging is real integration work, but the selector logic itself is proven and has real historical model-comparison results (Brier numbers cited in the diagnosis above) to build N2's catalogue-interface design on. |
| `residual_query_plan.py` + `selector_contract_v2.py` siblings (`v13_residual`, `formal_fork`) | `test_monitoring_residual_query_plan.py` (8), `test_monitoring_v13_residual.py` (10), `test_monitoring_formal_fork.py` (4) | 22 passed, 0 failed | **Reusable with adaptation**, same reasoning as above — `selector_contract_v2.py` is a real, tested, LLM-callable shared-budget allocation contract already in production use in the older line. |
| `joint_targets.py` | `test_monitoring_joint_targets.py` | 24 passed, 0 failed | **Reusable with adaptation for its leak-scoping pattern, not a substitute for section-5 multi-target sharing.** Fully tested and clean, but scoped to Controlled-track context-leak-prevention (does a model correctly scope shared context to relevant targets) — a different, narrower question than whether an agent's own choice to share evidence produces behavior a per-target solve couldn't replicate. Worth referencing when multi-target Natural-track work is designed, not wiring in directly. |
| `hydro_shadow_v1` | `tests/hydro_shadow_v1/` (`test_capture`, `test_core`, `test_pipeline`) | 45 passed, 0 failed | **Reusable as-is** as a second-physical-process (hydrology) candidate. Clean, offline-safe (its own test suite uses a loopback `ThreadingHTTPServer`, no real network), no missing dependencies. Genuinely isolated — referenced only by its own tests — so using it means new integration work (an episode-builder-equivalent), not fixing anything broken. |
| `multimodal_v1` (acquire/runner) + `multimodal_contract_v2` + `multimodal_live_v1` | `test_multimodal_v1_acquire.py` (16), `test_multimodal_v1_runner.py` (7), `test_multimodal_contract_v2.py` (41), `test_multimodal_live_v1.py` (16) | 80 passed, 0 failed | **Reusable with adaptation** for the acquire/runner/contract/live-orchestration layers — fully green, no missing dependencies, includes real NHC hurricane-track rendering logic. |
| `multimodal_v1` (core/geometry) + `multimodal_atomic_v1` | `test_multimodal_v1_core.py`, `test_multimodal_v1_geometry.py` (collection errors), `test_multimodal_atomic_v1.py` (235 passed, 33 errors) | **Blocked — not a code defect.** `shapely` and `shapefile` are not installed in this environment; every failure/error is `ModuleNotFoundError` for one of these two packages, nothing else. | **Verdict deferred, not "not worth reviving."** The non-geometry 235 tests in `test_multimodal_atomic_v1.py` all pass; only the spatial/polygon-matching path is blocked. Installing `shapely`/`shapefile` is an environment change, not covered by this round's approved scope (no source edits, no system changes without asking) — left as an explicit follow-up requiring a separate go-ahead before assessing this specific piece further. |

**Overall N1 verdict**: every asset examined is either fully reusable-with-adaptation/as-is, or blocked on
a concrete, narrow, named dependency gap rather than a real defect. Nothing found here is dead or broken
code — the actual work ahead is integration (bridging vocabularies, wiring into the v18 line), not repair.

### N2 — claim ADR-001's own open question, don't reinvent it

**Design note written and independently reviewed: `docs/DESIGN_NOTE_N2_catalogue_disclosure.md` (now
Revision 2).** One review round found the core safety claims solid (on a stronger basis than originally
argued — `_repair`'s own `_HISTORICAL_STATE` enforcement, not just "`step()` never mutates `self.sources`")
but required two amendments, both applied: (D1) listing every source unconditionally was itself a leak —
a non-public source's mere *existence* in the catalogue before it arrives can disclose outcome-correlated
information the kernel's own hidden-oracle rule protects against; fixed by only listing a non-public
source once `available_at <= clock`. (D2) sort order leaks nothing, but `query_id` *text* itself must be
constrained to carry no timing/relevance information (an episode roster naming ids like
`"a_relevant_kjfk_taf"` or embedding issuance times would defeat the whole mechanism) — now an explicit
roster-construction rule, with prior art cited (`public_query_selectors.py`'s seeded-hash tie-break).
Conclusion, corrected: add a `sources` key to `public_state()` listing each *currently visible* source's
`query_id` and (only for `public_schedule` sources) `available_at` — never content, never a relevance
judgment. Needs no `SNAPSHOT_SCHEMA` change (`self.sources` is already part of every snapshot and never
mutated by `step()`), and — precisely, not "identical on every call" as first claimed — is a deterministic
function of `clock` and the fixed roster only, identical between control/natural replay at matching clock
values, so it does not extend decision 4's "no non-synthetic stateful policy without fork isolation"
caution the way decision 1's `read` exposure does. See the note for the full reasoning and verification
plan.

ADR-001 already flags an open, undecided question: whether `public_state()` needs a separate field
carrying only scheduling metadata (not content) for cases like an unavailable `RETRIEVE`, explicitly left
to be decided during Batch 2's own test-writing. That is the seed of a catalogue-disclosure mechanism for
C1. If N2's design work waited until after Batch 2 lands, whoever implements Batch 2 would decide the
metadata field's shape alone, with no chance to fold in this note's D1/D2 findings first. So: N2's design
work runs now, alongside Batch 2 — coordination, not a shared schema requirement (the design note corrects
its own earlier claim that this needed the same `.v2` bump as decision 3's target binding; it doesn't, they
can simply land in the same commit). ADR-001 decision 4's fork-isolation gate is real but narrower than it
might first appear: it blocks wiring an actual non-synthetic stateful *policy* into `repair_policy`, not a
design document or a synthetic catalogue-aware test policy — so it constrains N2's eventual
*implementation* of an active-acquisition policy, not N2's design work itself. Whether this graduates to a
full ADR-002 with independent review is a call to make after N1 and this design note exist, not a process
to pre-commit to now (ADR-001 itself took 4 review rounds to land; this note settled in 1).

### N3 — deferred, not scoped yet

Before designing two new C2 diagnostic categories, first establish precisely how a C2-1 (acquisition-
failure) probe would differ from the existing `withhold` intervention (`interventions_v18.py:497-499`),
which already removes a source from the stream — the open question is whether an agent notices an absence
via a disclosed catalogue (new capability) or whether `withhold` already tests a version of this once N2's
catalogue exists. Left as an explicitly open question for the round after N1/N2.

## Explicit non-goals for this round

- No code changes to `natural_track_v18.py`/`interventions_v18.py`/`evidence_qualification_v18.py`. N1
  makes no source edits. N2 is design-note-only — the actual `public_state()`/`SNAPSHOT_SCHEMA` change
  lands as part of Track A Batch 2, not here. N3 is not scoped yet, only a stated open question.
- No revival/wiring of any orphaned/disconnected asset yet — N1 only produces the inventory, test results,
  and verdicts.
- No change to the hard boundary: D1/P1/Y1/L1/L2/H2 remain `BLOCKED_EXPLICIT_AUTHORIZATION`. Nothing in
  N1/N2 requires real weather/outcome/holdout data or a real provider call.
- Not committing/pushing anything without a separate explicit instruction, same as every other round.

## Sequencing relative to in-flight work

Track C's ADR-001 reached ACCEPTED_WITH_DISCLOSED_LIMITATIONS after a 4th independent review round; its
few remaining should-fix text corrections have been applied directly in the ADR. N1 starts immediately —
confirmed disjoint from every file Track A Batch 2 touches. N2's design work also starts now, in parallel
with Batch 2 (see N2's entry above for why waiting would risk a second schema bump); only N2's eventual
implementation is gated on Batch 2 actually landing and being reviewed.
