# ADR-001: repair-mechanism policy visibility and isolation scope

Status: **ACCEPTED_WITH_DISCLOSED_LIMITATIONS**, reached after a 4th independent review round found
Revision 3 closed all of round 3's findings without introducing a new blocking error, and Track C is
treated as closed pending this round's own small text fixes (applied in this text; see below). History:
round 1 rejected the original version (false premise about `NaturalKernel.clock`, factually wrong
`deepcopy` claim). Round 2 re-verified both corrections (both held up) but rejected Revision 1 again: an
unenforceable mechanical isolation gate, a false claim about which `as_of` value existing tests use, a
missing deep-copy requirement on the newly-exposed `self.read`, and a missed leak pattern (class
attributes). Revision 2 fixed all four, but round 3 found Revision 2's *own new text* had introduced two
further factual errors: a false claim that a policy could already see retrieved content today via
`step()`'s return value (exposing `read` is actually the *first* time any policy sees content at all), and
an `identity_repeat` default recommendation with the pinned-test breakage exactly backwards. Revision 3
fixed both, narrowed the `deepcopy` taxonomy's "instance attributes are safe" category, sharpened the
`PHASE_B1` reconciliation with verbatim quotes, and disclosed scope deltas against
`docs/PLAN_V20_NEXT_STEPS.md`. Round 4 confirmed all of that held up and found only small, non-blocking
issues, now fixed in this final revision: a leftover false claim (carried uncaught through rounds 2-3)
about which `as_of` value existing NOT_APPLICABLE-path tests use; a missing "disclose" half on the
`identity_repeat` default; two miscited line-number/comment references; and under-listed scope deltas
(decision 4's trigger applies to Horizon 4/L2 too, not just Horizon 3; decision 5 departs from the plan's
own literal "record verbatim" instruction where direct testing contradicted it). Not yet implemented
(implementation is Track A Batch 2). This document is currently untracked in git; it will be committed
with the rest of Horizon 1.

## Why this exists

Three independent reviews of `interventions_v18.py`'s `repair` mechanism (see
`docs/PLAN_V20_NEXT_STEPS.md` Track C, and the prior round's own 3-round fix/review cycle recorded in
`plan/plan_v19_0923/v19_execution_20260924_v6/PHASE_B1_REPAIR_POLICY_LEAK.md`, an absolute path outside
this git worktree at `/mnt/afs/260010168/extreme_weather_benchmark/plan/plan_v19_0923/
v19_execution_20260924_v6/PHASE_B1_REPAIR_POLICY_LEAK.md`) converged on two open questions: how much a
`NaturalPolicy` should be allowed to see, and how far isolation between the control and natural replay
should go.

## Corrected facts about `NaturalKernel.clock`, verified directly twice now

`clock` is an absolute position on the timeline `NaturalSource.available_at` values live on, not a
counter of anything "consumed." Verified again this revision, more precisely: a kernel built with
`start=5` stays at `clock == 5` across `RETRIEVE` (available), `RETRIEVE` (unavailable), and `UPDATE`
actions; only `WAIT` moves it, to `min(wake_at, deadline)` (`natural_track_v18.py:154`) — **not
unconditionally to `wake_at`** as the previous revision of this document said; a `WAIT` requesting a
time past the kernel's `deadline` clamps to `deadline` and marks the kernel expired. `clock` also does
**not** start at 0 in general — it starts at whatever `start` the caller passes to the constructor
(`natural_track_v18.py:120`); the previous revision's "starts at 0" was only true of the specific
example used to verify it, not a general property, and is corrected here.

Known stale comment, not fixed here (small, cosmetic, tracked for Batch 2 cleanup rather than blocking
this ADR): `NaturalKernel.snapshot()`'s own docstring (`natural_track_v18.py:182`) still calls `clock`
"the consumed clock (the budget proxy)" — the same misconception this ADR's decision 3 originally had,
still live in the code's own comment. Batch 2 should fix that docstring alongside whatever it implements
from this ADR, so the false description doesn't keep re-seeding the same error.

Whether the `clock` timeline is the same one `qualify_stream`'s `as_of` parameter uses is still a real,
open question this ADR cannot answer today: no production code currently constructs a `NaturalKernel`
from real evidence records, so there is nothing to check the two timelines against. See decision 3.

## The decisions

### 1 & 2. What does a policy see, and what's the call signature?

**Revised decision: expose the kernel's own current read cache (`self.read`) as a deep copy, computed
fresh on each `public_state()` call — not `last_result` — and keep the single-argument `policy(state)`
signature. Two real gaps are disclosed below, not silently glossed over.**

`last_result`-only does not survive contact with how repair actually works (unchanged from the prior
revision): every T-60/T-40/T-20 checkpoint is reached via `WAIT`, so `last_result` would be `None`
exactly when a repair policy most needs to see something; and if `last_result` were derived from the
action log instead of the live cache, it would survive eviction — exactly the content `_repair` is
trying to remove.

**Gap found this round, now fixed as a requirement, not left implicit: `public_state()` must return a
deep copy of `self.read`, never the live dict.** Verified directly: with a live reference returned, a
policy could write straight back into the kernel's own read cache through the returned `state` (a
fabricated key showed up in a subsequent `UPDATE`'s `read_query_ids`), which breaks the exact invariant
`test_policy_cannot_mutate_kernel_through_its_state_argument` (`test_v18_fork_continuation.py:171-178`)
exists to protect — and that existing test would **not** have caught this specific regression, since it
only mutates `read_query_ids` and `clock`, not `read`. Batch 2 must deep-copy `self.read` before
returning it in `public_state()`, and should add a test that specifically tries to mutate the kernel
through the newly-exposed `read` field, not just the pre-existing fields.

**Gap found this round, disclosed and deliberately not decided here: exposing `read` loses the
"when will this be ready" hint an unavailable `RETRIEVE`'s own return value carries.** A `RETRIEVE`
against a source whose `available_at` is still in the future never populates `self.read`; today that
information only reaches whatever code issued the `RETRIEVE` call directly (e.g. a test, or a future
caller of `NaturalKernel.step()` outside the policy-replay path), via that call's own return value.
Choosing `read` over `last_result` means a policy inspecting only `public_state()` after a `WAIT` cannot
recover that hint. Whether this matters enough to add a separate, narrow field (carrying only scheduling
metadata, never content) is a completeness question, not a safety one — omitting it costs a policy
information, it does not leak anything — so this ADR leaves it to be decided during Batch 2's own
test-writing, rather than deciding it speculatively here.

**Corrected this revision — a real error in the previous one, not just an omission: exposing `read`
through `public_state()` is not a widening of an existing content-exposure channel. It is the *first*
time any policy sees retrieved content at all, in any form.** The previous revision of this document
claimed retrieved content "was already reachable... via the return value of `step()`," and used that to
argue this change "does not introduce a wholly new category of leak." **That claim is false, and is
withdrawn.** `replay_suffix` (`natural_track_v18.py:335`) is the only place anything ever calls a
`NaturalPolicy`, and it calls `policy(kernel.public_state())` — the `step()` call's own return value goes
into the replay's `trace` list, and is never passed to the policy in any form. Verified directly: a
recording policy driven through `replay_suffix` saw only `{clock, deadline, read_query_ids, stopped,
expired, terminal, action_count}` on every call; retrieved content appeared only in `trace`, which no
policy ever receives. `docs/PLAN_V20_NEXT_STEPS.md`'s own Track C description independently says the
same thing ("policy never observes retrieved content"). So today, **no leak pattern of any kind — not
even a fully-shared class attribute — can carry retrieved content from a control replay into a natural
replay, because no policy ever sees content in the first place**; only keys and timing are exposed via
`public_state()`, exactly as `replay_suffix` was designed to guarantee. Decision 1 changes that
guarantee for the first time: once `read` is in `public_state()`, any of decision 4's still-open leak
patterns (class attribute, module global, RNG state) that can smuggle information across the two
replay calls can smuggle actual observed content, not merely keys and timing. This is a materially larger
exposure than "widens an existing surface" — there is no existing surface for content today. Given that,
**this ADR now makes explicit what decision 4 only implied before: Batch 2 must not wire any
non-synthetic, potentially stateful policy into `repair_policy` until decision 4's fork isolation
actually exists**, precisely because decision 1 is what first makes a content leak possible at all, not
merely larger. This is a real, accepted trade-off for Batch 2 — every policy Batch 2 itself introduces
remains synthetic and stateless — recorded here in its correct severity so it isn't underestimated later.

Scope of decision 1 itself, corrected wording: this is an additive change to `public_state()`'s *schema*
(a new key, existing keys unchanged) but **not** a non-breaking change in practice — any test or fixture
that pins `public_state()`'s exact dict shape (e.g.
`test_forked_kernels_share_no_state_with_each_other_or_the_parent`,
`tests/test_v18_fork_continuation.py:97-106`) will need updating, as will any artifact-generation script
that snapshots `public_state()` verbatim (`scripts/build_v18_natural_synthetic.py`,
`scripts/build_v19_offline_gate.py`). This breakage is expected and small, not evidence against the
change — but it should not be described as "non-breaking." Separately confirmed: a restored-from-snapshot
kernel's `read` is independently owned, not aliased to the snapshot it was restored from; nothing about
this conflicts with the existing `policy_isolation` witness fields already in `interventions_v18.py`.

### 3. `as_of` vs. snapshot `clock`, and binding the target

**Revised decision: still DEFERRED, not decided — but the previous revision's stated reason was itself
wrong and is corrected here, not just repeated.**

The previous revision claimed "`as_of=None` is the one case that actually occurs in code today" and
that "existing tests call repair with no `as_of` at all." **This is false, and is withdrawn.** Re-checked
directly against `tests/test_v18_interventions.py`: the `repair()` helper (defined at line 83) hardcodes
`as_of=10` in its own call to `apply_intervention` (line 91), and every test that goes through it
(e.g. lines 113, 122, 170, 172, 190, 570) builds its snapshot from a `NaturalKernel` that reaches
`clock == 10` via a `WAIT` before calling `.snapshot()` (the `corrupted_cache_snapshot()` helper at line
72 and its inline equivalents both follow this pattern) — so `as_of` and the snapshot's `clock` are equal,
`10 == 10`, in every APPLIED-path case exercised through this helper. The `repair_with()` helper (line
300) does the same (`as_of=10` at line 306, default snapshot `corrupted_cache_snapshot()` also at
`clock == 10`). Separately, a handful of tests call `apply_intervention` directly on the NOT_APPLICABLE
path, and these are mixed: lines 100 and 590 pass `as_of=10` with **no** `kernel_snapshot` at all; lines
531 and 533-536, by contrast, pass a real `kernel_snapshot=corrupted_cache_snapshot()` (a snapshot with
`clock == 10`, same as everywhere else) with **no `as_of` argument at all**, so `as_of=None` genuinely is
exercised there — **correcting an error carried over uncaught through two prior revisions of this ADR**,
which both claimed no existing test passes `as_of=None`. All of these NOT_APPLICABLE-path calls raise
before any `as_of`-vs-`clock` check could run (missing `corrected_state_patch`, in this case), so this
still does not amount to test evidence favoring any particular invariant over another — but it does mean
`as_of=None` is a real, already-exercised case today, just one that currently short-circuits before
reaching any code that would use the value.

This correction **reinforces, rather than weakens, the deferral**: existing fixtures happening to set
`as_of == clock` is compatible with several different future invariants (`==`, `>=`, `<=`) and provides
no real evidence favoring any one of them over the others — there simply is no test today that would
distinguish `>=` from `==`. And since `_repair` does not currently receive `as_of` as a parameter at
all, there is no live code path today that could crash on any particular value, `None` included — so
"must not crash on `as_of=None`" is not an action item for Batch 2 in this round; there is nothing for
it to act on yet.

- The real relationship between `as_of` and `clock` must be decided **when code first exists that
  builds a `NaturalKernel` from real evidence records** (a P1/L1/L2-era bridge) — the concrete,
  checkable trigger for revisiting this decision, named here rather than left implicit.
- **Target binding stays a real, separate, still-good idea**, independent of the deferred `as_of`/`clock`
  question: `target_start`/`target_end` are not part of `SNAPSHOT_SCHEMA`
  (`natural_track_v18.py:12`, currently `.v1`) at all, so nothing today stops a repair snapshot taken
  for one target being replayed against qualification parameters for a different one.
- **Scope of the target-binding change, corrected and widened**: this is not just a `SNAPSHOT_SCHEMA`
  version bump and a `_repair` signature change. `NaturalKernel` has no notion of a "target" today at
  all — binding `target_start`/`target_end` at `snapshot()` time requires adding them to `__init__`, as
  new instance attributes, to `from_snapshot`, and to whatever internal key-list `snapshot()` reads from
  (`_SNAPSHOT_KEYS` or equivalent). There are no stored snapshot fixture files in this repo today — every
  snapshot in the test suite is built live via `env.snapshot()` — so "breaking every existing snapshot
  fixture" more precisely means "updating every live `snapshot()`/constructor call site that will need
  the new arguments," a smaller, more concrete scope than the previous revision implied.
- **The binding is an opaque tag, not a validated one, until the deferred bridge exists**: because the
  kernel has no independent notion of what a target's timeline means, `target_start`/`target_end` bound
  into the snapshot cannot be checked against kernel semantics — they are only as meaningful as whatever
  the caller passes in. If the eventual `as_of`/`clock` decision later ties the deadline to the target,
  expect a **second** schema bump beyond `.v2`, not a one-time cost paid now.
- **Still not addressed, flagged as a residual gap rather than solved**: this binds the target, not the
  records stream — a snapshot could still be paired with a mismatched evidence stream for the same
  nominal target. Out of scope for this revision.
- **Missing plumbing, unchanged from the prior revision**: `_repair` does not currently receive
  `target_start`/`target_end` at all — wiring the binding through means extending `_repair`'s own
  signature, not just adding an internal check.

### 4. Process-fork isolation: deferred permanently, or gated on a trigger?

**Revised decision: the previous revision's proposed mechanical gate does not work and is withdrawn.
Decision 4 is now a scope statement with a named, procedural trigger — not a code-enforced one. Fork
isolation is explicitly not required for Batch 2, and nothing in Batch 2 depends on it.**

The independently-verified reason the previous mechanism fails: a `NotImplementedError` gate keyed off
`_is_plain_function_without_own_state` (or any similar "provably stateless" allowlist) was simulated
directly against the real test suite and **breaks 6 existing B-1 regression tests**
(`tests/test_v18_interventions.py`), including `test_repair_replays_get_separate_policy_instances_so_control_future_cannot_leak`
and the RNG-rewind/restore tests — these tests deliberately use stateful policies
(`ClockMemoryPolicy`, `RandomWaitPolicy`) precisely to prove the *factory* pattern (a fresh instance
built per replay) already closes the leak pattern B-1 fixed. A gate that rejects any policy with its own
state cannot admit these without contradicting the very tests that prove decision-appropriate isolation
already works for them. It would also reject the "Safe:" pattern documented in `apply_intervention`'s
own docstring (`interventions_v18.py:429-437`, e.g. `lambda: MyPolicy(config)`). And
`_is_plain_function_without_own_state`'s own docstring (`interventions_v18.py:127`) says outright that
it "is NOT a proof of statelessness" — using it as a hard safety gate contradicts what its author already
wrote about it.

The previously-proposed run-spec `isolation: process` field is also withdrawn as a Batch 2 deliverable:
`scripts/validate_v18_run_spec.py` has no intervention, repair, tier, or isolation concept at all today
(only `schema`/`run_id`/`status`/`scopes`/`permissions`), and `_repair` never sees the run-spec regardless
— inventing the field without also wiring `_repair` to consult it would validate a schema no code path
reads, providing no actual protection while looking like it does.

**What decision 4 now actually says**:
- **What's real and already enforced today**: the factory pattern (`Callable[[], NaturalPolicy]`, a
  fresh instance built per replay) plus the existing same-object-rejection test close the specific
  identity-across-replays leak pattern B-1 fixed. This protection is real and already shipped.
- **What is not enforced by anything today, and is not being added in Batch 2**: class-attribute,
  module-global, and RNG-module-state leaks. No structural check on a policy's shape can reliably detect
  these (per `_is_plain_function_without_own_state`'s own admission), so none is added.
- **Corrected scope of what fork isolation would actually fix, once built**: fork-per-replay closes the
  in-process-unfixable leak patterns (class attribute, closed-over container, mutable default, module
  global) and the stdlib/`numpy` RNG gaps — but **only for state that is polluted after the fork point**.
  It does **not** help state already polluted in the parent process *before* a fork happens (e.g. if a
  repair runs after other ticks in the same process have already mutated shared class/module state), and
  it does not help state held on a remote server or in a file/database a policy writes to across calls.
  This caveat, requested by `docs/PLAN_V20_NEXT_STEPS.md`'s own Track C description, was missing from
  the previous revision and is restored here.
- **Trigger, now explicitly procedural rather than code-enforced**: before any non-synthetic,
  potentially-stateful policy is wired into `repair_policy` for a P1 or L2 run, fork isolation must
  exist and be used. Enforcing this remains a run-spec-review and code-review responsibility today, not
  a runtime check — no run-spec field or `_repair` plumbing exists to check it mechanically, and none is
  added by this revision. A future revision of this ADR, made once a real `isolation: process` concept
  and its consuming code both exist together, can upgrade this from procedural to code-enforced. Naming
  note for whenever that field is actually added: an unrelated `isolation_mode` config key already exists
  elsewhere in this codebase (`policies.py:157-159`, `comparison_fingerprint.py:30`) — pick a name that
  doesn't collide with it.
- **Explicitly out of Batch 2's critical path**: none of Batch 2 items 5-8 depend on fork isolation
  existing. Decision 4 records scope and the trigger; it does not block anything else in this ADR or in
  Batch 2.

### 5. Is `deepcopy` of built policies rejected permanently?

**Decision: still rejected as the general-purpose mitigation. The bound-method correction from the prior
revision is re-verified and holds. A real gap the prior revision missed — class attributes — is added.
The closures claim is sharpened with the precise mechanism, and reconciled with `PHASE_B1`'s different
terminology rather than left in apparent contradiction with it.**

Re-verified directly, again: `copy.deepcopy` of a bound method **does** separate the underlying
instance — `copied.__self__ is not original` holds, and mutating the original's state after the copy
does not leak into the copy. The prior revision's withdrawal of "a bound method still binds the same
instance" stands, confirmed a second time.

**Missed in the prior revision, added now: a policy whose state lives on a *class* attribute (not an
instance attribute) is not separated by `deepcopy`, no matter how many instances are deep-copied** —
deep-copying an instance never copies its class object, so a class attribute stays shared regardless.
This is not hypothetical: it is one of the four concrete leak patterns the original B-1 review named,
and `deepcopy` does not close it. Read narrowly, "bound methods are separated" is correct and re-verified
— but it must not be read as "deepcopy makes instance-based policies safe in general," since a
class-attribute-backed policy is instance-based and still leaks.

**Closures, sharpened**: `copy.deepcopy` of a closure function itself returns the *identical* function
object (`copy.deepcopy(f) is f` holds) — the `copy` module treats function objects as atomic and does not
descend into their cells at all. So a closure's state is not "not meaningfully separated," it is not
touched by `deepcopy` in any way. This is a stronger, more precise claim than the prior revision's
wording, and is distinct from the class-attribute case: a closure cell backing a plain function is never
copied because the function itself is never copied; a class attribute is not copied because `deepcopy`
of an *instance* never touches the *class*.

**By contrast, and directly re-verified**: a mutable value provided as an `__init__` default and stored
as an instance attribute (not a closure cell) *is* separated by `deepcopy` — confirmed directly, matching
the same mechanism that separates bound methods (both are ordinary instance-attribute copying).

**Reconciling with `PHASE_B1_REPAIR_POLICY_LEAK.md:94-96`**, quoted here directly rather than paraphrased
(also solves a citation-portability problem a prior review flagged, since that file lives outside this
git worktree): *"`deepcopy`-based closure of the two in-process-shareable patterns that could take it
(closed-over dict, mutable default — needs an opt-in/fallback design for policies holding
locks/sockets)."* Against this ADR's own directly-tested taxonomy: "mutable default" matches cleanly (a
mutable `__init__`-provided default, once stored as an instance attribute, is separated). "Closed-over
dict" is not a Python closure cell in this context — it is the shape of `apply_intervention`'s own
documented UNSAFE example (`interventions_v18.py:442-443`, `lambda: MyPolicy(history=shared_history)`):
a container closed over by the *factory* function and passed into the *built instance* as an attribute.
Directly re-tested: deep-copying each built `MyPolicy` instance does separate that `history` attribute —
confirming `PHASE_B1`'s claim is correct on this reading, not merely plausible. This is a different thing
from a Python closure *cell* backing a plain function directly (no instance at all), which `deepcopy`
does not touch, as below.

The more precise, directly-tested taxonomy this ADR now uses, **narrowed this revision** after finding
category 1 as previously stated was too broad:
1. **Separated by `deepcopy`**: ordinary instance attributes holding plain data, including a bound
   method's `__self__` and a mutable `__init__`-provided default stored as an attribute (the
   `PHASE_B1`-cited "closed-over dict, mutable default" patterns, confirmed above) — **provided the
   attribute's own value is not itself a function or closure** (see the correction below).
2. **Not separated by `deepcopy`**: closure cells backing a plain function directly (the function object
   itself is returned unchanged by `deepcopy`, `copy.deepcopy(f) is f` holds); class attributes (the
   class object is never copied by deep-copying an instance, regardless of how many instances are
   copied). **Corrected this revision**: this also includes an *instance attribute whose value is itself
   a function or closure* (e.g. `self.fn = make_closure()`) — directly tested, `deepcopy(instance).fn is
   instance.fn` holds. So "instance attribute" alone is not sufficient for category 1; the attribute's
   *value* must itself be plain data, not another function. Whether a given class-attribute-backed policy
   actually leaks also depends on lookup mechanics (an instance attribute that happens to reference a
   class-level container is separated at the reference level the same as any other instance attribute;
   only genuine class-level *storage*, looked up via the class rather than shadowed on the instance,
   is unaffected by deep-copying the instance) — a nuance, not a change to the bottom line that
   class-attribute-backed state is not reliably separated.
3. **Fails loudly rather than silently aliasing, usually**: unpicklable resources — locks, sockets,
   database connections, module references, open files, generators — raise `TypeError` under `deepcopy`
   rather than silently copying a reference, correcting the prior revision's "silently copies a
   reference" claim. **Not universal**, however: some real client objects (e.g. `requests.Session`)
   deep-copy without error, so "fails loudly" is a common but not guaranteed outcome and must not be
   relied on as a safety mechanism in general.

Also worth naming precisely, since it is easy to conflate with a `deepcopy` failure and isn't one: two
factory-built instances still share a mutable `__init__` default *if the factory itself hands the same
object to both* (directly tested: `d3.memory is d1.memory` holds when both are built from a factory that
closes over one shared default). That is the pre-existing factory-level leak B-1's own fix already
addresses by rejecting a factory that returns the same object twice, not a `deepcopy` limitation — listed
here only to avoid it being mistaken for a new gap in this section's taxonomy.

`deepcopy` remains rejected as a general-purpose mitigation because categories 2 (silent) are real and
common enough (class attributes are exactly the kind of thing a hastily-written policy would use for
memoization), even though category 1 is safe and category 3 fails safely. A future, narrower decision
could revisit `deepcopy` specifically for policies provably restricted to category-1 state, if that
pattern becomes common enough to be worth a dedicated check — not decided here, out of scope.

The code's own docstring at `interventions_v18.py:423-427` still says "Deferred, not implemented" for
`deepcopy`, consistent with this revision — no code change needed there.

### Batch 2 item 5 (`identity_repeat`): a pragmatic default, not a first-principles design decision

Earlier revisions of this ADR framed this as "not decided by this ADR." **That framing doesn't survive
contact with what's actually written below it — a stated default, defended by two pinned tests and G3's
classification, is a real decision, just a compatibility-driven one rather than a re-examination of
whether the phantom-row design is right on its own merits.** Correcting that inconsistency here rather
than repeating it: this ADR does decide item 5, on pragmatic grounds, while explicitly not re-litigating
the original design's merits (`interventions_v18.py:471-482`, records/qualification shape, unrelated to
decisions 1-5's policy-visibility/replay-isolation subject matter).

**Default: keep the current phantom-row behavior, corrected this revision on two points.** Directly
tested both variants against the current suite: the true no-op (making `qualify_stream` operate on the
real, unmodified `records`) produces 2 qualification rows ending in `TARGET_CONTENT_CHANGE`, breaking
`tests/test_v18_interventions.py:43` (asserts `DUPLICATE`) and `:584` (asserts
`len(qualification) == 3`). **Correction**: it does *not* also require `held_fields` at `:44` to change —
re-tested directly, `held_fields` is untouched by which rows feed qualification (`held.remove("content")`
at `interventions_v18.py:478` runs regardless); only line 43 fails. Keeping the current phantom-row
behavior breaks neither test. **Correction**: the citation supporting the phantom row was wrong — the
comment at `interventions_v18.py:472-475` ("Appending a row would silently change the information set")
argues for *not* growing `records`/`child` itself, which both options already agree on (line 476 always
returns the unmodified parent as `child`); it is not an argument for the phantom row. The actual
justification for appending a phantom duplicate specifically to `qualification_records` (a separate
variable, distinct from `records`) is at `interventions_v18.py:479-482` ("Preserve the exact parent input
while still exposing the duplicate arrival that the qualification audit would observe") — that is the
right citation. This behavior is also what G3's committed duplicate-detection classification already
assumes. The condition the prior revision set for keeping current behavior ("Batch 2 discovers a
concrete consumer that depends on it") is met by the two pinned tests and G3's classification.

**Disclose, not just keep — the plan's own option was "keep-and-disclose," and the previous revision
dropped the "disclose" half.** Both `docs/PLAN_V20_NEXT_STEPS.md` and `PHASE_B1_REPAIR_POLICY_LEAK.md`
call the current result internally inconsistent: `result.changed_fields == []` and `result.records ==
parent` (nothing changed, by the result's own report), yet `result.qualification` reports a duplicate
arrival that isn't in `records`, and `held_fields` omits `content` even though content is, in fact,
unchanged. Keeping this behavior without disclosing it would leave that inconsistency silently baked into
Batch 2's output. Batch 2 must add an explicit note (in the intervention's own docstring and in
`repair_witness`/qualification output, not just this ADR) that `identity_repeat` deliberately reports a
qualification-only phantom duplicate not reflected in `changed_fields`/`records`, and why — this
disclosure is part of the default, not a separate follow-up.

One thing true regardless of which option is chosen, so it is not miscounted as a cost of this decision:
`review/v18_execution_20260923/G3_SYNTHETIC_INTERVENTIONS_V2.json` is already stale today —
`PHASE_B1_REPAIR_POLICY_LEAK.md:90` already records this (an internally inconsistent result and a stale
G3, in that document's own words) — so G3 needs regenerating either way, not only if Batch 2 later
revisits this default.

## What this ADR does not certify

This document decides *scope*, not *guarantee*. Implementing decisions 1-4 does not make the repair
mechanism future-leak-safe for stateful policies in general — decision 4's fork isolation is what closing
that residual gap actually requires, and it remains unimplemented, with no code-level trigger, after this
revision. Decision 1's `read` exposure is what first makes a content leak (as opposed to a keys/timing
leak) possible at all through the still-open leak patterns decision 4 describes — accepted specifically
because Batch 2 is not wiring any non-synthetic stateful policy into repair yet, not because the exposure
itself is small. Any future document describing this mechanism must still carry the caveat recorded
verbatim in `PHASE_B1_REPAIR_POLICY_LEAK.md`'s "Mandatory caveat" section, reproduced here in full so a
reader of this ADR does not need the external file to see it:

> The v18 repair intervention replays each suffix twice, natural then control, using two policies
> built by a caller-supplied factory. Isolation between those replays is best effort and in-process
> only; it is not guaranteed, and nothing produced by this mechanism may be described as
> future-leak-safe. Within one call, running the natural replay first stops that call's control
> replay from reaching the natural trace. But shared mutable state the mechanism cannot detect
> (class attributes, closed-over or default-argument containers, module globals, caches, files,
> non-stdlib RNGs, remote session state) can still carry the natural replay's future into the control
> trace. So control traces and `traces_differ` are unreliable, biased toward a null repair effect,
> for any policy that is not provably free of shared state. Across calls there is no isolation at
> all: state surviving one repair, such as a persistent memory store, can contaminate the natural
> trace of a later repair, including later checkpoints of the same episode. The stdlib `random` state
> is restored after each call, but only for sequential calls on a single thread.
> `repair_witness.policy_isolation` records which mitigations were applied; it does not certify
> independence. Claims of leak-free repair need per-replay process isolation, which is deferred and
> not implemented.

This ADR does not authorize reading real weather/outcome/holdout data or making a real provider call.

## Scope deltas against `docs/PLAN_V20_NEXT_STEPS.md`, disclosed rather than silently absorbed

This revision's decisions land slightly differently than Batch 2's item list (items 5-8) currently
describes, and that delta should be reconciled the next time the plan document itself is touched, not
silently treated as already covered:
- **Decision 1** (exposing `read` via `public_state()`) is new work the plan's Batch 2 item list does not
  currently name as a line item — it falls out of answering "what does a policy see," which the plan does
  assign to this ADR, but the plan itself has no explicit task for it.
- **Decision 3** narrows item 8 (originally: bind `as_of`/`clock` validation *and* target binding) down to
  target binding only, deferring the `as_of`/`clock` half entirely. Item 8's own premise, that `_repair`
  "accepts an `as_of`," is itself incorrect today (confirmed: it does not) — the plan's phrasing of item 8
  should be corrected alongside implementing whatever this ADR ends up deciding.
- **Decision 4**'s trigger effectively makes fork isolation a prerequisite for wiring any stateful policy
  into a P1 or L2 run that uses `repair` — this is a real constraint that neither Horizon 3 (P1) nor
  Horizon 4 (L1/L2) currently mention; both need the same note, not just Horizon 3.
- **Decision 5**, corrected this revision: the plan's own instruction (`docs/PLAN_V20_NEXT_STEPS.md:135-136`)
  asks this ADR to "record the three reviews' reasoning verbatim: functions/closures/client objects aren't
  truly copied." Direct testing this round found that instruction only partially holds — closures and class
  attributes genuinely aren't separated, but most unpicklable client-type objects (locks, sockets, DB
  connections) raise `TypeError` rather than being silently, untruly copied, and at least one real client
  shape (`requests.Session`) deep-copies without error at all. This ADR's taxonomy intentionally departs
  from the plan's literal instruction where direct testing contradicted it — flagged here as a delta rather
  than silently overriding the plan's stated expectation.
- **Batch 2 item 5** (`identity_repeat`): the plan assigns this decision to Track C outright, without the
  "pragmatic default, not first-principles" framing this revision now uses. That framing is this ADR's own
  correction, not a plan delta to reconcile elsewhere — noted here so it isn't mistaken for one.

## Implementation notes for Track A Batch 2

- Decision 1: `public_state()`'s `read` field must be a deep copy, not a live reference — add a test that
  tries to mutate the kernel through it, not just through the pre-existing `read_query_ids`/`clock`
  fields. Any test/fixture pinning `public_state()`'s exact dict shape, and any script that snapshots it
  verbatim (`build_v18_natural_synthetic.py`, `build_v19_offline_gate.py`), will need updating. This is
  the first change to ever expose retrieved content to a policy at all — every synthetic/stateless policy
  Batch 2 itself introduces is fine, but do not use this as an opportunity to wire in anything stateful or
  non-synthetic; that stays blocked until decision 4's fork isolation exists.
- Decision 1's public-schedule hint gap (the "when will this be ready" information an unavailable
  `RETRIEVE` currently only returns transiently) is left for Batch 2 to decide whether to address, based
  on whether its own test-writing surfaces a real need.
- Decision 3: bind `target_start`/`target_end` into the snapshot — this touches `NaturalKernel.__init__`,
  new instance attributes, `from_snapshot`, and `snapshot()`'s internal key list, plus a `SNAPSHOT_SCHEMA`
  bump to `.v2` and a `_repair` signature change to actually receive the values. No `as_of`-vs-`clock`
  check is implemented in Batch 2 — that remains deferred per decision 3.
- Decision 4: no code changes are required or expected in Batch 2. The factory pattern and existing
  same-object test are the real protection today; nothing else is added or gated in this round.
- Decision 5: no code changes required; `interventions_v18.py:423-427`'s existing docstring already
  matches this decision.
- Batch 2 item 5 (`identity_repeat`): decided independently of decisions 1-4, with a stated default of
  **keeping the current phantom-row behavior AND disclosing it** — two existing tests
  (`tests/test_v18_interventions.py:43,584`) and G3's committed duplicate-detection classification already
  depend on keeping it, so the condition for this default is already met, not merely a fallback to watch
  for. The "disclose" half is mandatory, not optional: add an explicit docstring/witness note that
  `qualification_records` (not `records`) carries a phantom duplicate row not reflected in
  `changed_fields`. `G3_SYNTHETIC_INTERVENTIONS_V2.json` needs regenerating regardless, since it is
  already stale.
- Known stale comment to fix while in this code either way: `NaturalKernel.snapshot()`'s docstring
  (`natural_track_v18.py:182`) still describes `clock` as "the consumed clock (the budget proxy)" —
  update it to match the corrected description in this ADR.
