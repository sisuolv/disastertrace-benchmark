# Design note N2: a catalogue-disclosure field for `public_state()`

Status: **Revision 2, after one independent review.** The review confirmed both central safety claims
(replay-invariance, no `SNAPSHOT_SCHEMA` change) hold, even on a stronger basis than originally argued
(see the corrected section below), but found one real gap in the proposed field's design (non-public
sources' mere existence in an unconditional catalogue can leak information the kernel's own hidden-oracle
rule is meant to protect) and one missing constraint (source-id text itself must be constrained, not just
catalogue order) — both required amendments, applied below, not left as open questions. Still a design
note, not an ADR — scoped as design-only per `docs/PLAN_V20_NOVELTY_ALIGNMENT.md`'s Horizon 1.5/N2, claims
ADR-001's own open scheduling-metadata question rather than reinventing it. Whether this graduates into a
formal ADR-002 with independent review is a decision for after this note and N1's inventory both exist.
No code changes in this round; this is a proposal for whoever implements Track A Batch 2 to land
alongside that work, not a description of shipped behavior.

## The problem this closes

`NaturalKernel.public_state()` (`src/disastertrace/monitoring_v1/natural_track_v18.py:168-177`) — the only
thing any policy ever sees (`replay_suffix`, `:335`) — discloses `clock`/`deadline`/`read_query_ids`/
`stopped`/`expired`/`terminal`/`action_count`, but never a catalogue of what could be retrieved. A `RETRIEVE`
action (`NaturalAction`, `:19-70`) already requires a `query_id` the caller must already know out of band.
So even where an episode is configured with more than one `NaturalSource`, no policy has any way to
discover that fact from `public_state()` alone — "choice" among sources is vacuous today, which is the core
finding behind `docs/PLAN_V20_NOVELTY_ALIGNMENT.md`'s C1 diagnosis. ADR-001 decisions 1-2 already flag this
as an open question ("a separate, narrow field carrying only scheduling metadata, never content ... left
to be decided during Batch 2's own test-writing") without answering it. This note answers it.

## Proposed field, corrected after review (D1: unconditional listing was itself a leak)

The review found a real gap in the original proposal: listing every configured source unconditionally,
including ones whose `available_at` is still in the future and undisclosed, makes the catalogue the
*first* channel by which a policy could learn a non-public source *exists* at all — today, a `RETRIEVE`
against an unknown `query_id` simply raises (`natural_track_v18.py:139`) and aborts the replay, so there
is no existing way to probe for a source's existence without already knowing its id. Mere existence can
itself be an outcome-correlated leak (e.g. a special report that is only issued because conditions
changed) — exactly the class of thing the kernel's "undisclosed future arrival time is a hidden oracle"
principle (`:140-148`) is meant to protect, which the original proposal's exclusions list acknowledged for
`available_at` but not for existence itself. **Fixed by gating non-public sources' catalogue entries on
`available_at <= self.clock`** — a source that hasn't arrived yet, and never opted into public scheduling,
simply isn't listed at all until it has. This is still a function of `clock`, which is already public, so
it adds no new channel between a control and natural replay (see the replay-invariance argument below,
unaffected by this fix since it was never about *which* sources are listed, only whether the *value* is
consistent given the same clock).

```python
"sources": [
    {
        "query_id": source.query_id,
        "public_schedule": source.public_schedule,
        # Disclosed only when public_schedule is True -- same visibility
        # class as the existing RETRIEVE-on-unavailable disclosure rule
        # (natural_track_v18.py:140-148), though not an identical cost:
        # RETRIEVE reveals this only while unavailable and only at the
        # cost of one logged action; the catalogue reveals it for free,
        # on every call, including once the source is already available.
        # That's an accepted, disclosed difference in the action-cost
        # model of an active-acquisition benchmark, not an oversight.
        **({"available_at": source.available_at} if source.public_schedule else {}),
    }
    # A non-public source is not listed at all until it has actually
    # arrived (available_at <= clock) -- otherwise its mere presence in
    # the catalogue would itself disclose the hidden-oracle information
    # the kernel's own RETRIEVE-unavailable path deliberately withholds
    # (review finding D1). A public-schedule source is always listed,
    # since its timing is disclosable by contract regardless of arrival.
    for source in sorted(self.sources.values(), key=lambda s: s.query_id)
    if source.public_schedule or source.available_at <= self.clock
],
```

Deliberately excluded from the catalogue entry:
- **`content`** — never. This is the one invariant that must hold no matter what else changes; a
  catalogue is metadata about what's retrievable, not a preview of what would be retrieved.
- **`available_at` for non-`public_schedule` sources** — as above, and now also gated on existence itself,
  not just the timestamp value.
- **Any relevance/matching judgment** (e.g. "this source is likely relevant to your target") — the whole
  point of C1 is that evidence-target matching is supposed to be an agent capability. A catalogue that
  pre-filters or ranks sources by relevance would just move the "pre-matched gold" problem
  (`docs/PLAN_V20_NOVELTY_ALIGNMENT.md`'s section-20 citation) from `qualify_stream` into `public_state()`
  instead of removing it. The catalogue must list every *currently-visible* source (per the D1 fix above),
  unfiltered by relevance, every time.
- **Whether a source has already been retrieved** — redundant with the existing `read_query_ids` field;
  no need to duplicate state across two keys.

**Required constraint on episode/roster construction, added after review (D2): `query_id` text itself must
be opaque.** Sorting the catalogue by `query_id` leaks nothing through *order* — the review confirmed order
is fully determined by the set of ids the policy already sees, so alphabetical sort adds no new channel.
But the id *strings* are a real, separate risk the original note didn't constrain: a builder that names ids
like `"a_relevant_kjfk_taf"` leaks relevance directly regardless of sort order, and realistic weather-report
ids that embed issuance times (e.g. `metar_KJFK_2351Z`) would leak `available_at` for a non-public source
exactly as effectively as putting it in the `available_at` field would. **Rule for whoever builds a
multi-source episode roster: `query_id` values must carry no timing or relevance information** — opaque
identifiers (e.g. a stable hash or an arbitrary index), not anything derived from the source's content,
type, or arrival time. Prior art for this exact class of problem already exists in this repo:
`public_query_selectors.py:17` uses a seeded SHA-256 tie-break (`f"public-query-v1|{seed}|{query_id}"`)
specifically to avoid `query_id`-based bias in selection order — the same discipline, applied one level
earlier (to the ids themselves, not just their ordering), closes this gap.

## Why this needs no `SNAPSHOT_SCHEMA` change (unlike target binding)

`self.sources` is frozen once — at `__init__` (`:111-119`) on a fresh kernel, and equivalently at
`from_snapshot` (`:301`, the path `replay_suffix` actually uses, `:330`) when rebuilding one from a
snapshot — and is never reassigned anywhere in `step()`: confirmed by reading every branch (`:127-166`),
none of which touches `self.sources`. It is already part of every snapshot today (`_SOURCE_KEYS`, `:14`,
`snapshot()`/`from_snapshot()`, `:187-207`/`:241-251`). So a `sources` catalogue field in `public_state()`
is purely a derived, computed-on-each-call view over data the snapshot mechanism already carries — exactly
like `read` (ADR-001 decision 1), not like the `target_start`/`target_end` binding (ADR-001 decision 3),
which genuinely needs new snapshot fields. **This proposal and decision 3's target binding are independent
changes to different things; they should not be conflated as both needing the same `.v2` bump.** They can
still land in the same Batch 2 commit as a matter of convenience (both touch `natural_track_v18.py`), but
the catalogue field itself requires no schema version change at all.

## Why this is safer than decision 1's `read` exposure, and doesn't extend decision 4's caution

ADR-001 decision 1 (exposing `read`) was flagged as the *first* time any policy sees retrieved content,
widening what a still-open leak pattern (class attribute, module global, RNG state) could carry between a
control and natural replay. The `sources` catalogue proposed here does **not** have this property, on a
stronger basis than originally argued: it isn't just that `step()` never mutates `self.sources` — `_repair`
(`interventions_v18.py`) actively *enforces* that the roster and action log can never differ between the
parent and corrected snapshots used for the two replays (`_HISTORICAL_STATE = {"sources", "actions"}`,
`:27`; rejected if patched, `:243-245`; checked again at runtime, `:290-293`), so both replays are
structurally guaranteed to share the same roster, not merely observed to in this proposal's own reasoning.
**Precise claim, corrected from "identical on every call" (which stopped being exactly true once the D1
fix above gated entries on `clock`): the catalogue is a deterministic function of `clock` and the fixed
roster only — for any given `clock` value, its content is identical regardless of which replay (control or
natural) produced that clock**, since the roster is provably shared and `clock` is already a public field a
leak pattern could observe anyway. It can differ across two calls within the *same* replay as `clock`
advances via `WAIT`, exactly as `read_query_ids`/`clock` themselves already do — expected, not a new risk.
There is nothing here for a leak pattern to smuggle that differs *between* replays at matching clock
values, because the value doesn't differ there. This proposal does not extend the "must not wire a
non-synthetic stateful policy into `repair_policy` without fork isolation" caution decision 4 states — that
caution remains scoped to `read`'s content exposure, not to this structural, roster-invariant catalogue.

## Disclosed output-shape breakage (owed the same disclosure ADR-001 gave `read`, corrected here since the
original version of this note omitted it)

Adding a new key to `public_state()`'s returned dict is additive to the schema but not "non-breaking" in
practice, same caveat as ADR-001 decision 1:
- `tests/test_v18_fork_continuation.py:97-100` and `:103-106` pin `public_state()`'s exact dict shape and
  will need updating (already true for `read`; also true for `sources`).
- `scripts/build_v18_natural_synthetic.py:38` and `scripts/build_v19_offline_gate.py:139` snapshot
  `public_state()` verbatim into artifacts and will need regenerating.
- **Not previously disclosed for `read` either, and owed here**: the committed
  `review/v18_execution_20260923/G4_NATURAL_SYNTHETIC_V2.json` embeds a `public_state` dict, and its
  sha256 is pinned in `review/v18_execution_20260923/RUN_MANIFEST_V2.json`'s `artifacts` block. Adding
  either `read` or `sources` to `public_state()` and regenerating G4 will no longer match that pinned hash
  — Batch 2 needs to regenerate and re-pin both together, once, not discover this once per field added.

## What this does and does not unblock

Adding this field makes `RETRIEVE`'s "choice" of `query_id` non-vacuous for the first time — a policy can
now discover what it could ask for. It does **not**, by itself, give any policy a reason to prefer one
source over another (no relevance signal is disclosed, by design, per the exclusions above), and it does
**not** configure any episode-builder script to actually construct a multi-source `NaturalKernel` — every
current episode-builder path (confirmed in the diagnosis: `build_v18_dev_episodes.py` has zero
`NaturalKernel`/`NaturalSource` references at all) still needs to be extended separately to offer more than
one legitimate source per episode before this field has anything real to disclose. That extension, and the
design of an actual active-acquisition policy that uses this field, are both explicitly out of scope for
this note — left to Horizon 1.5/N3 and beyond, gated on ADR-001's decision 4 (fork isolation) once a real,
potentially-stateful policy is what's being wired in, not this catalogue field itself.

## Verification, once implemented (not performed in this round — design only)

- A test that a single-source episode's `public_state()["sources"]` is a one-element list matching the
  configured source, unchanged from today's behavior in every other field.
- A test that a `public_schedule=False` source's `available_at` never appears in the catalogue, even after
  an unrelated `WAIT` advances the clock past it.
- A test for the D1 fix specifically: a non-public source with `available_at` in the future is absent from
  the catalogue entirely (not present with a hidden/null timestamp) until `clock` reaches it, at which
  point it appears with no `available_at` key (since it's still not `public_schedule`).
- **Corrected**: not "the same snapshot" (control and natural replays actually use two distinct but
  related snapshots — the parent and the corrected one built by `_repair`, differing only in `read`, per
  `interventions_v18.py`'s `_HISTORICAL_STATE` enforcement) — the real test is that the catalogue is
  byte-identical between `NaturalKernel.from_snapshot(parent).public_state()["sources"]` and
  `NaturalKernel.from_snapshot(corrected).public_state()["sources"]` at matching `clock`, using `_repair`'s
  actual parent/corrected pair, not an assumption that they're the same object.
- A test that mutating the returned `sources` list (or its dict entries) does not affect the kernel's own
  `self.sources` — matching the same mutation-safety discipline ADR-001 decision 1 required for `read`.
- A roster-construction lint/test (per the D2 fix) that rejects or flags `query_id` values containing
  digit-runs plausibly readable as a timestamp, or literal relevance-suggestive substrings, in any test
  fixture or episode-builder default roster.
