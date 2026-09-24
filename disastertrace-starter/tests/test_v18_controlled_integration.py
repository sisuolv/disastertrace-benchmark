"""Offline tests for the v18 controlled pilot on the T-60/T-40/T-20 grid.

Synthetic inputs only: no weather archive, outcome, API key, network or
provider.  main() runs with call() replaced by a local stub.

Two layers are covered.  The agent-view boundary (agent_view_v18, plus
prompt_for's rendering of one view) keeps its flat-view contract, so it is
still attacked with adversarial flat views (``spanning_episode``, rows
labelled ``known``).  The checkpoint grid itself goes through the builder's
own ``_qualify_checkpoints`` and the runner's ``checkpoint_inputs`` adapter,
which is exactly the path main() dispatches (``grid_episode``).
"""

from __future__ import annotations

import copy
import io
import json

import pytest

from disastertrace.monitoring_v1 import agent_view_v18 as view
from disastertrace.monitoring_v1.evidence_qualification_v18 import qualify_evidence, qualify_stream
from scripts import build_v18_dev_episodes as builder
from scripts import run_v18_controlled_api as api


# CUTOFF is one arbitrary cutoff for the flat-view boundary tests.
TARGET_START, TARGET_END, CUTOFF = 100, 200, 40
# The builder's T-60/T-40/T-20 grid scaled to this file's integer clock:
# cutoffs target_start - 60/40/20 = 40, 60 and 80.
OFFSETS = {"T-60": 60, "T-40": 40, "T-20": 20}
GRID_CUTOFFS = {"T-60": 40, "T-40": 60, "T-20": 80}
FULL = "FULL_PREFIX_TRANSCRIPT"
ENTRY_FIELDS = {"issued_at", "available_at", "current_relevance", "current_projection"}
SCORER_FIELDS = {
    "status",
    "availability",
    "source_change",
    "target_content_change",
    "current_source_hash",
    "previous_source_hash",
    "current_projection_hash",
    "previous_projection_hash",
    "witness",
    "source_identity",
    "previous_source_identity",
    "as_of",
    "previous_relevance",
    "previous_projection",
    "source_qualification",
}
# Verbatim system prompt of the three pre-existing arms.
BASE_SYSTEM = (
    "You are in a controlled weather-risk state-maintenance pilot. "
    "Use only the supplied target and evidence. Do not retrieve sources. "
    "Return exactly JSON with risk_probability, target_state, next_action. "
    'target_state MUST be a JSON object such as {"visibility_m": 4000, "confidence": "medium"}, never a string. '
    "risk_probability is a number in [0,1]; next_action is UPDATE, WAIT, or STOP."
)
TARGET = {
    "station": "KSFO",
    "target_start": TARGET_START,
    "target_end": TARGET_END,
    "proposition": "future routine report visibility below 5000 m",
}
PRIOR = {"risk_probability": 0.37, "target_state": {"visibility_m": 3000, "confidence": "low"}, "next_action": "UPDATE"}


def record(revision, *, available, vis):
    return {
        "source_id": "synthetic-source",
        "source_revision": revision,
        "kind": "taf",
        "issued_at": 1 if available is None else available - 5,
        "available_at": available,
        "valid_start": TARGET_START,
        "valid_end": TARGET_END,
        "content": {
            "periods": [
                {"valid_start": TARGET_START, "valid_end": TARGET_END, "operator": "BASE", "visibility_m": vis}
            ]
        },
    }


def periods(vis):
    return {"periods": [{"valid_start": TARGET_START, "valid_end": TARGET_END, "operator": "BASE", "visibility_m": vis}]}


# ---------------------------------------------------------------------------
# Flat-view boundary fixture (agent_view_v18's own per-row defences)
# ---------------------------------------------------------------------------

# (revision, own as_of, available_at, visibility); arrival order.  Only the
# first two conditions below make a row visible at CUTOFF.
SPANNING_ROWS = (
    ("rev-before", 25, 20, 8100),  # own cutoff before CUTOFF: visible
    ("rev-own-cutoff-after", 50, 30, 1112),  # own cutoff after CUTOFF
    ("rev-stale-label", 25, 35, 1113),  # not_yet_available at its own cutoff
    ("rev-at", CUTOFF, CUTOFF, 8200),  # own cutoff == available_at == CUTOFF: visible
    ("rev-after", 50, 45, 1111),  # own cutoff and arrival after CUTOFF
    ("rev-late", CUTOFF, 60, 2222),  # not_yet_available at CUTOFF
    ("rev-unknown", CUTOFF, None, 3333),  # unknown availability
)
VISIBLE_REVISIONS = {"rev-before", "rev-at"}
HIDDEN_MARKERS = ("1111", "1112", "1113", "2222", "3333")


def spanning_episode():
    """Adversarial flat view whose rows carry cutoffs before, at and after CUTOFF.

    The builder never mixes cutoffs inside one checkpoint (checkpoint_inputs
    refuses that); this view pins agent_view_v18's own per-row defence.
    """

    qualifications, previous = [], None
    for revision, as_of, available, vis in SPANNING_ROWS:
        row = record(revision, available=available, vis=vis)
        result = qualify_evidence(row, previous, target_start=TARGET_START, target_end=TARGET_END, as_of=as_of)
        qualifications.append(result.to_dict())
        previous = row
    return {
        "episode_id": "SYNTHETIC-PREFIX",
        "station": "KSFO",
        "target_start": TARGET_START,
        "target_end": TARGET_END,
        "as_of": CUTOFF,
        "qualifications": qualifications,
    }


def checkpoint_for(episode, revision):
    return next(
        q for q in episode["qualifications"] if q["witness"]["source_identity"]["source_revision"] == revision
    )


# ---------------------------------------------------------------------------
# Checkpoint-grid fixture (builder-shaped, what main() dispatches)
# ---------------------------------------------------------------------------

# (revision, available_at, visibility); arrival order.  One arrival before
# each cutoff, one after T-20 but before target_start, one with no receipt.
GRID_ROWS = (
    ("rev-1", 20, 8000),  # before T-60 (40)
    ("rev-2", 50, 4000),  # T-60 < arrival <= T-40 (60)
    ("rev-3", 70, 2500),  # T-40 < arrival <= T-20 (80)
    ("rev-4", 90, 1357),  # after T-20, before target_start: never visible
    ("rev-unknown", None, 3333),  # no receipt: never visible
)
VISIBLE_BY_CHECKPOINT = {"T-60": [8000], "T-40": [8000, 4000], "T-20": [8000, 4000, 2500]}
NEVER_VISIBLE_MARKERS = ("1357", "3333")


def grid_episode(rows=GRID_ROWS, episode_id="SYNTHETIC-GRID"):
    """Builder-shaped episode: one qualify_stream call per checkpoint cutoff."""

    stream = [record(revision, available=available, vis=vis) for revision, available, vis in rows]
    checkpoints, excluded = builder._qualify_checkpoints(
        stream, target_start=TARGET_START, target_end=TARGET_END, offsets=OFFSETS
    )
    assert excluded == []
    return {
        "episode_id": episode_id,
        "station": "KSFO",
        "target_start": TARGET_START,
        "target_end": TARGET_END,
        "checkpoints": checkpoints,
    }


def checkpoint_named(episode, checkpoint_id):
    return next(c for c in episode["checkpoints"] if c["checkpoint_id"] == checkpoint_id)


def grid_prompt(arm, episode, checkpoint_id, prior=None):
    episode_view, checkpoint_view = api.checkpoint_inputs(episode, checkpoint_named(episode, checkpoint_id))
    return api.prompt_for(arm, episode_view, checkpoint_view, prior)


def all_grid_prompts(episode):
    return {cid: {arm: grid_prompt(arm, episode, cid) for arm in api.ARMS} for cid in api.CHECKPOINT_IDS}


def visibilities(history):
    return [entry["current_projection"]["periods"][0]["visibility_m"] for entry in history]


def all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_keys(item)


def user_payload(messages):
    return json.loads(messages[1]["content"])


def good_reply(key, messages, model, max_tokens, timeout):
    content = json.dumps(
        {"risk_probability": 0.4, "target_state": {"visibility_m": 4000, "confidence": "medium"}, "next_action": "UPDATE"}
    )
    envelope = {"id": "stub", "model": model, "choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
    return 200, envelope, json.dumps(envelope)


def configure_main(monkeypatch, tmp_path, episodes, fake_call, *extra_args):
    source = tmp_path / "episodes.json"
    source.write_text(json.dumps({"episodes": episodes}))
    out = tmp_path / "run.json"

    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(api, "call", fake_call)
    monkeypatch.setattr(api, "urlopen", no_network)
    # This file's rosters are built on the miniature OFFSETS clock (via
    # grid_episode -> builder._qualify_checkpoints(..., offsets=OFFSETS)), not
    # the real-microsecond production CHECKPOINT_OFFSETS_US. main()'s
    # require_complete_roster now verifies each checkpoint's as_of actually
    # matches its declared offset, so the runner's notion of what "T-60"
    # means has to be patched to the same OFFSETS these fixtures were built
    # with -- this is not a workaround, it's what's actually true of these
    # synthetic rosters.
    monkeypatch.setattr(api, "CHECKPOINT_OFFSETS_US", OFFSETS)
    monkeypatch.setattr(
        api.sys,
        "argv",
        ["offline", "--episodes", str(source), "--out", str(out), "--run-id", "OFFLINE-F12-PREFIX", *extra_args],
    )
    monkeypatch.setattr(api.sys, "stdin", io.StringIO("OFFLINE-NONCREDENTIAL\n"))
    return out


# ---------------------------------------------------------------------------
# Boundary layer: unchanged flat-view contract of agent_view_v18/prompt_for
# ---------------------------------------------------------------------------


def test_public_prefix_excludes_records_after_the_checkpoint_cutoff():
    episode = spanning_episode()
    checkpoint = checkpoint_for(episode, "rev-at")
    prefix = view.public_prefix(episode, checkpoint)
    assert visibilities(prefix) == [8100, 8200]
    assert [entry["available_at"] for entry in prefix] == [20, CUTOFF]
    assert all(entry["available_at"] <= CUTOFF for entry in prefix)
    serialized_prefix = json.dumps(prefix)
    serialized_prompt = json.dumps(api.prompt_for(FULL, episode, checkpoint, None))
    for marker in HIDDEN_MARKERS:
        assert marker not in serialized_prefix
        assert marker not in serialized_prompt
    # An earlier checkpoint cutoff shrinks the prefix to what existed then.
    assert visibilities(view.public_prefix(episode, checkpoint_for(episode, "rev-before"))) == [8100]


def test_known_entries_still_need_available_at_not_after_the_cutoff():
    # qualify_stream(as_of=None) labels every timed row "known" without
    # comparing it to any cutoff; the checkpoint cutoff falls back to the
    # episode as_of.  Only the arrival time can keep row k2 out.
    rows = [record("rev-k1", available=35, vis=8300), record("rev-k2", available=45, vis=4444)]
    qualifications = [
        q.to_dict() for q in qualify_stream(rows, target_start=TARGET_START, target_end=TARGET_END, as_of=None)
    ]
    assert [q["availability"] for q in qualifications] == ["known", "known"]
    episode = {
        "episode_id": "SYNTHETIC-KNOWN",
        "station": "KSFO",
        "target_start": TARGET_START,
        "target_end": TARGET_END,
        "as_of": CUTOFF,
        "qualifications": qualifications,
    }
    for checkpoint in qualifications:
        assert visibilities(view.public_prefix(episode, checkpoint)) == [8300]
        assert "4444" not in json.dumps(api.prompt_for(FULL, episode, checkpoint, None))


def test_public_checkpoint_also_hides_a_known_entry_that_arrives_after_the_cutoff():
    # A "known" label only means qualify_stream had no cutoff to compare
    # against (as_of=None); it is not proof available_at <= this checkpoint's
    # cutoff. public_checkpoint feeds the 3 original arms, not just the new
    # FULL_PREFIX_TRANSCRIPT arm, so this must hold there too, not only in
    # public_prefix (adversarial review found this gap was real but latent:
    # unreachable through today's build_roster, which always passes as_of).
    rows = [record("rev-k1", available=35, vis=8300), record("rev-k2", available=45, vis=4444)]
    qualifications = [
        q.to_dict() for q in qualify_stream(rows, target_start=TARGET_START, target_end=TARGET_END, as_of=None)
    ]
    assert [q["availability"] for q in qualifications] == ["known", "known"]
    episode = {
        "episode_id": "SYNTHETIC-KNOWN-CHECKPOINT",
        "station": "KSFO",
        "target_start": TARGET_START,
        "target_end": TARGET_END,
        "as_of": CUTOFF,
        "qualifications": qualifications,
    }
    late_checkpoint = qualifications[-1]  # rev-k2, available_at=45 > CUTOFF=40
    result = view.public_checkpoint(episode, late_checkpoint)
    assert result["current_evidence"] == {}
    for arm in ("TRULY_FRESH", "PRIOR_P_ONLY", "PRIOR_P_FACT"):
        assert "4444" not in json.dumps(api.prompt_for(arm, episode, late_checkpoint, None))
    # The earlier, genuinely-visible-by-then row must still come through.
    early_checkpoint = qualifications[0]  # rev-k1, available_at=35 <= CUTOFF=40
    early_evidence = view.public_checkpoint(episode, early_checkpoint)["current_evidence"]
    assert early_evidence["periods"][0]["visibility_m"] == 8300


@pytest.mark.parametrize("bad_availability", [[], {}, ["available"]])
def test_unhashable_availability_is_skipped_not_crashed(bad_availability):
    # A bare `value in {"available", "known"}` raises TypeError for an
    # unhashable value instead of just being false (found by adversarial
    # review). Both public_checkpoint and public_prefix must fail closed the
    # same way every other malformed-input path in this module already does:
    # silently treat it as not visible, never crash.
    episode = {
        "episode_id": "SYNTHETIC-UNHASHABLE", "station": "KSFO",
        "target_start": TARGET_START, "target_end": TARGET_END, "as_of": CUTOFF,
        "qualifications": [
            {"availability": bad_availability, "witness": {"as_of": CUTOFF, "available_at": 10, "current_projection": {"x": 1}}},
        ],
    }
    checkpoint = episode["qualifications"][0]
    result = view.public_checkpoint(episode, checkpoint)
    assert result["current_evidence"] == {}
    assert view.public_prefix(episode, checkpoint) == []


def test_future_suffix_and_hidden_labels_do_not_change_the_raw_prompt():
    episode = spanning_episode()
    before = api.prompt_for(FULL, episode, checkpoint_for(episode, "rev-at"), None)

    perturbed = copy.deepcopy(episode)
    checkpoint = checkpoint_for(perturbed, "rev-at")
    for qualification in perturbed["qualifications"]:
        witness = qualification["witness"]
        if witness["source_identity"]["source_revision"] not in VISIBLE_REVISIONS:
            witness["current_projection"] = periods(7)
        qualification.update(
            status="PERTURBED",
            source_change="PERTURBED",
            target_content_change="PERTURBED",
            current_source_hash="0" * 64,
            previous_source_hash="1" * 64,
            current_projection_hash="2" * 64,
            previous_projection_hash="3" * 64,
        )
        witness["source_identity"] = {"source_id": "perturbed"}
        witness["previous_source_identity"] = {"source_id": "perturbed"}
        witness["previous_relevance"] = "perturbed"
        witness["previous_projection"] = periods(9)
    future = record("rev-future", available=90, vis=9999)
    perturbed["qualifications"].append(
        qualify_evidence(future, None, target_start=TARGET_START, target_end=TARGET_END, as_of=95).to_dict()
    )

    assert api.prompt_for(FULL, perturbed, checkpoint, None) == before


# ---------------------------------------------------------------------------
# Checkpoint grid: builder rows -> checkpoint_inputs -> prompt_for
# ---------------------------------------------------------------------------


def test_runner_checkpoint_ids_match_the_builder_grid():
    assert api.CHECKPOINT_IDS == tuple(builder.CHECKPOINT_OFFSETS_US) == ("T-60", "T-40", "T-20")
    assert tuple(OFFSETS) == api.CHECKPOINT_IDS


def test_each_checkpoint_has_its_own_cutoff_and_the_visible_prefix_only_grows():
    # Replaces the old shared-as_of test: the old builder qualified every row
    # against one as_of, so both "checkpoints" (really the first two arrivals)
    # saw one identical prefix.  Now each checkpoint is its own qualify_stream
    # call at its own cutoff.
    episode = grid_episode()
    assert [c["checkpoint_id"] for c in episode["checkpoints"]] == list(api.CHECKPOINT_IDS)
    cutoffs = [c["as_of"] for c in episode["checkpoints"]]
    assert cutoffs == list(GRID_CUTOFFS.values())
    assert cutoffs[0] < cutoffs[1] < cutoffs[2] < TARGET_START
    histories = []
    for checkpoint in episode["checkpoints"]:
        assert {q["witness"]["as_of"] for q in checkpoint["qualifications"]} == {checkpoint["as_of"]}
        episode_view, checkpoint_view = api.checkpoint_inputs(episode, checkpoint)
        history = view.public_prefix(episode_view, checkpoint_view)
        assert visibilities(history) == VISIBLE_BY_CHECKPOINT[checkpoint["checkpoint_id"]]
        assert all(entry["available_at"] <= checkpoint["as_of"] for entry in history)
        # The single-snapshot arms see exactly the newest entry of this history.
        current = view.public_checkpoint(episode_view, checkpoint_view)["current_evidence"]
        assert current == history[-1]["current_projection"]
        histories.append(history)
    # Monotone and strictly growing on this stream: every earlier history is a
    # prefix of the next one.
    for earlier, later in zip(histories, histories[1:]):
        assert later[: len(earlier)] == earlier and len(later) > len(earlier)
    prompts = [json.dumps(grid_prompt(FULL, episode, cid)) for cid in api.CHECKPOINT_IDS]
    assert len(set(prompts)) == 3


def test_each_checkpoint_prompt_excludes_arrivals_after_its_own_cutoff():
    episode = grid_episode()
    for checkpoint_id, cutoff in GRID_CUTOFFS.items():
        hidden = [str(vis) for _, available, vis in GRID_ROWS if available is None or available > cutoff]
        shown = [str(vis) for _, available, vis in GRID_ROWS if available is not None and available <= cutoff]
        for arm in api.ARMS:
            text = json.dumps(user_payload(grid_prompt(arm, episode, checkpoint_id)))
            for marker in hidden:
                assert marker not in text, (checkpoint_id, arm, marker)
        full_text = json.dumps(user_payload(grid_prompt(FULL, episode, checkpoint_id)))
        assert all(marker in full_text for marker in shown)


def test_checkpoint_inputs_carry_the_latest_row_visible_at_the_cutoff():
    # Rows qualified with no cutoff are all "known".  The synthetic checkpoint
    # must carry the latest row visible at this cutoff (rev-k1).  It must not
    # carry the latest-labelled row (rev-k2, which arrives after the cutoff),
    # so the single-snapshot arms keep real evidence and still never see 4444.
    rows = [record("rev-k1", available=35, vis=8300), record("rev-k2", available=45, vis=4444)]
    qualifications = [
        q.to_dict() for q in qualify_stream(rows, target_start=TARGET_START, target_end=TARGET_END, as_of=None)
    ]
    episode = {
        "episode_id": "SYNTHETIC-KNOWN-GRID",
        "station": "KSFO",
        "target_start": TARGET_START,
        "target_end": TARGET_END,
        "checkpoints": [{"checkpoint_id": "T-60", "as_of": CUTOFF, "qualifications": qualifications}],
    }
    episode_view, checkpoint_view = api.checkpoint_inputs(episode, episode["checkpoints"][0])
    assert checkpoint_view == {
        "availability": "known",
        "witness": {"as_of": CUTOFF, "available_at": 35, "current_projection": periods(8300)},
    }
    assert episode_view["as_of"] == CUTOFF and episode_view["qualifications"] is qualifications
    assert "checkpoints" not in episode_view
    for arm in api.ARMS:
        payload = user_payload(api.prompt_for(arm, episode_view, checkpoint_view, None))
        assert "4444" not in json.dumps(payload)
        if arm == FULL:
            assert visibilities(payload["evidence_history"]) == [8300]
        else:
            assert payload["current_evidence"] == periods(8300)


def test_a_checkpoint_with_nothing_visible_yet_sends_empty_evidence_not_a_crash(monkeypatch):
    # First arrival at 50: T-60 (cutoff 40) legitimately knows nothing yet.
    monkeypatch.setattr(api, "CHECKPOINT_OFFSETS_US", OFFSETS)
    episode = grid_episode(rows=GRID_ROWS[1:])
    episode_view, checkpoint_view = api.checkpoint_inputs(episode, checkpoint_named(episode, "T-60"))
    assert checkpoint_view == {"availability": None, "witness": {"as_of": 40}}
    for arm in api.ARMS:
        payload = user_payload(api.prompt_for(arm, episode_view, checkpoint_view, None))
        if arm == FULL:
            assert payload["evidence_history"] == []
        else:
            assert payload["current_evidence"] == {}
    assert visibilities(user_payload(grid_prompt(FULL, episode, "T-40"))["evidence_history"]) == [4000]
    api.require_complete_roster([episode])  # a legitimately empty checkpoint is not a roster error


def test_prompt_for_refuses_a_roster_episode_instead_of_sending_an_empty_history():
    episode = grid_episode()
    row = checkpoint_named(episode, "T-20")["qualifications"][0]
    # This is the hazard the guard closes: the unchanged view finds no flat
    # rows on a roster episode and would silently return an empty history.
    assert view.public_prefix(episode, row) == []
    for arm in api.ARMS:
        with pytest.raises(ValueError, match="checkpoint_inputs"):
            api.prompt_for(arm, episode, row, None)


def test_checkpoint_inputs_refuse_rows_qualified_at_another_cutoff():
    episode = grid_episode()
    t60, t40 = checkpoint_named(episode, "T-60"), checkpoint_named(episode, "T-40")
    mixed = {**t60, "qualifications": t40["qualifications"]}
    with pytest.raises(ValueError, match="own cutoff"):
        api.checkpoint_inputs(episode, mixed)


def test_prefix_entries_carry_only_scorer_label_free_fields():
    spanning, grid = spanning_episode(), grid_episode()
    cases = [(spanning, checkpoint_for(spanning, "rev-at"))]
    cases += [api.checkpoint_inputs(grid, checkpoint) for checkpoint in grid["checkpoints"]]
    for episode, checkpoint in cases:
        prefix = view.public_prefix(episode, checkpoint)
        assert prefix
        for entry in prefix:
            assert set(entry) == ENTRY_FIELDS
        assert not set(all_keys(prefix)) & SCORER_FIELDS
        payload = user_payload(api.prompt_for(FULL, episode, checkpoint, None))
        assert set(payload) == {"arm", "target", "evidence_history"}
        assert not set(all_keys(payload)) & SCORER_FIELDS
        text = json.dumps(payload)
        for qualification in episode["qualifications"]:
            for label in (
                qualification["status"],
                qualification["current_source_hash"],
                qualification["previous_source_hash"],
                qualification["current_projection_hash"],
                qualification["previous_projection_hash"],
                qualification["witness"]["source_identity"]["source_revision"],
            ):
                if label:
                    assert label not in text
        assert "synthetic-source" not in text
    # The synthetic checkpoints themselves hold no scorer label.
    for _, checkpoint_view in cases[1:]:
        assert set(checkpoint_view) == {"availability", "witness"}
        assert set(checkpoint_view["witness"]) <= {"as_of", "available_at", "current_projection"}


def test_full_prefix_arm_sends_history_while_truly_fresh_payload_is_unchanged():
    # At T-40 the newest visible row is rev-2 (4000), which is the snapshot the
    # old record-as-checkpoint test used, so the exact TRULY_FRESH bytes carry over.
    episode = grid_episode()

    full = grid_prompt(FULL, episode, "T-40")
    payload = user_payload(full)
    assert payload["arm"] == FULL
    assert set(payload) == {"arm", "target", "evidence_history"}
    assert payload["target"] == TARGET
    assert isinstance(payload["evidence_history"], list) and len(payload["evidence_history"]) == 2
    assert visibilities(payload["evidence_history"]) == [8000, 4000]
    assert full[0]["content"].startswith(BASE_SYSTEM + " ")
    assert "Do not retrieve sources." in full[0]["content"]
    assert "full legitimate evidence history so far" in full[0]["content"]
    # The Raw arm carries no model state.
    assert grid_prompt(FULL, episode, "T-40", prior=PRIOR) == full

    fresh = grid_prompt("TRULY_FRESH", episode, "T-40")
    expected_payload = {"arm": "TRULY_FRESH", "target": TARGET, "current_evidence": periods(4000)}
    expected_user = (
        '{"arm":"TRULY_FRESH","current_evidence":{"periods":[{"operator":"BASE","valid_end":200,'
        '"valid_start":100,"visibility_m":4000}]},"target":{"proposition":"future routine report '
        'visibility below 5000 m","station":"KSFO","target_end":200,"target_start":100}}'
    )
    assert json.dumps(expected_payload, sort_keys=True, separators=(",", ":")) == expected_user
    assert fresh == [{"role": "system", "content": BASE_SYSTEM}, {"role": "user", "content": expected_user}]


@pytest.mark.parametrize("prior", [None, PRIOR], ids=["no-prior", "prior"])
@pytest.mark.parametrize("arm", ["PRIOR_P_ONLY", "PRIOR_P_FACT"])
def test_prior_arms_keep_their_single_snapshot_payload(arm, prior):
    episode = grid_episode()
    messages = grid_prompt(arm, episode, "T-60", prior)
    expected = {"arm": arm, "target": TARGET, "current_evidence": periods(8000)}
    expected["previous_probability"] = None if prior is None else prior["risk_probability"]
    if arm == "PRIOR_P_FACT":
        expected["previous_target_state"] = None if prior is None else prior["target_state"]
    assert messages == [
        {"role": "system", "content": BASE_SYSTEM},
        {"role": "user", "content": json.dumps(expected, sort_keys=True, separators=(",", ":"))},
    ]


def test_later_arrivals_and_hidden_labels_do_not_change_an_earlier_checkpoint_prompt():
    episode = grid_episode()
    before = all_grid_prompts(episode)

    # A later arrival, re-qualified by the builder at every cutoff, changes no
    # checkpoint that precedes it.
    assert all_grid_prompts(grid_episode(rows=GRID_ROWS + (("rev-5", 95, 1111),))) == before

    # Content arriving between T-60 and T-40 cannot reach T-60, but does
    # legitimately reach T-40 (so this check is not vacuous).
    changed_rows = tuple(("rev-2", 50, 7777) if row[0] == "rev-2" else row for row in GRID_ROWS)
    changed = all_grid_prompts(grid_episode(rows=changed_rows))
    assert changed["T-60"] == before["T-60"]
    assert changed["T-40"][FULL] != before["T-40"][FULL]
    assert changed["T-40"]["TRULY_FRESH"] != before["T-40"]["TRULY_FRESH"]

    # Scorer labels and the projections of rows not visible at a checkpoint are
    # not part of any Raw prompt.
    perturbed = copy.deepcopy(episode)
    for checkpoint in perturbed["checkpoints"]:
        for qualification in checkpoint["qualifications"]:
            witness = qualification["witness"]
            if qualification["availability"] != "available":
                witness["current_projection"] = periods(7)
            qualification.update(
                status="PERTURBED",
                source_change="PERTURBED",
                target_content_change="PERTURBED",
                current_source_hash="0" * 64,
                previous_source_hash="1" * 64,
                current_projection_hash="2" * 64,
                previous_projection_hash="3" * 64,
            )
            witness["source_identity"] = {"source_id": "perturbed"}
            witness["previous_source_identity"] = {"source_id": "perturbed"}
            witness["previous_relevance"] = "perturbed"
            witness["previous_projection"] = periods(9)
    assert all_grid_prompts(perturbed) == before


def test_public_prefix_returns_copies_not_live_references():
    episode = grid_episode()
    pristine = copy.deepcopy(episode)
    episode_view, checkpoint_view = api.checkpoint_inputs(episode, checkpoint_named(episode, "T-20"))

    prefix = view.public_prefix(episode_view, checkpoint_view)
    prefix[0]["current_projection"]["periods"][0]["visibility_m"] = -1
    prefix[0]["current_projection"]["injected"] = True
    prefix.append({"injected": True})
    current = view.public_checkpoint(episode_view, checkpoint_view)["current_evidence"]
    current["periods"][0]["visibility_m"] = -3
    assert episode == pristine

    kept = view.public_prefix(episode_view, checkpoint_view)
    kept_current = view.public_checkpoint(episode_view, checkpoint_view)["current_evidence"]
    for checkpoint in episode["checkpoints"]:
        for qualification in checkpoint["qualifications"]:
            qualification["witness"]["current_projection"]["periods"][0]["visibility_m"] = -2
    assert visibilities(kept) == [8000, 4000, 2500]
    assert kept_current == periods(2500)


@pytest.mark.parametrize(
    "episode_changes,witness_changes,message",
    [
        ({}, {"as_of": TARGET_START}, "Public decision cutoff must precede target start"),
        ({}, {"as_of": TARGET_START + 1}, "Public decision cutoff must precede target start"),
        ({"as_of": None}, {"as_of": None}, "Public decision cutoff must precede target start"),
        ({"target_start": None}, {}, "Future target interval is required"),
        ({"target_end": TARGET_START}, {}, "Future target interval is required"),
    ],
)
def test_public_prefix_applies_the_public_checkpoint_validation(episode_changes, witness_changes, message):
    grid = grid_episode()
    episode, checkpoint = copy.deepcopy(api.checkpoint_inputs(grid, checkpoint_named(grid, "T-40")))
    episode.update(episode_changes)
    checkpoint["witness"].update(witness_changes)
    with pytest.raises(ValueError, match=message):
        view.public_checkpoint(episode, checkpoint)
    with pytest.raises(ValueError, match=message):
        view.public_prefix(episode, checkpoint)
    with pytest.raises(ValueError, match=message):
        api.prompt_for(FULL, episode, checkpoint, None)


def test_main_registers_and_dispatches_every_arm_at_every_checkpoint(monkeypatch, tmp_path):
    seen = []

    def fake_call(key, messages, model, max_tokens, timeout):
        seen.append(messages)
        return good_reply(key, messages, model, max_tokens, timeout)

    out = configure_main(monkeypatch, tmp_path, [grid_episode()], fake_call)
    assert api.main() == 0
    report = json.loads(out.read_text())
    registration = json.loads((tmp_path / "run.json.registration.json").read_text())
    assert api.ARMS == ("TRULY_FRESH", "PRIOR_P_ONLY", "PRIOR_P_FACT", FULL)
    assert registration["attempts"] == report["registered_attempts"] == report["actual_attempts"] == 12
    assert registration["checkpoints"] == report["registered_checkpoints"] == 3
    assert registration["checkpoint_ids"] == report["checkpoint_ids"] == ["T-60", "T-40", "T-20"]
    assert report["valid_by_arm"] == {arm: 3 for arm in api.ARMS}
    assert [(a["checkpoint_index"], a["checkpoint_id"], a["arm"]) for a in report["attempts"]] == [
        (index, checkpoint_id, arm) for index, checkpoint_id in enumerate(api.CHECKPOINT_IDS) for arm in api.ARMS
    ]
    assert [a["request_id"] for a in report["attempts"]] == [
        f"SYNTHETIC-GRID::{index}::{arm}" for index in range(3) for arm in api.ARMS
    ]
    assert len((tmp_path / "run.json.dispatch.jsonl").read_text().splitlines()) == 12
    assert len(seen) == 12
    for attempt, messages in zip(report["attempts"], seen):
        payload = user_payload(messages)
        visible = VISIBLE_BY_CHECKPOINT[attempt["checkpoint_id"]]
        if attempt["arm"] == FULL:
            assert set(payload) == {"arm", "target", "evidence_history"}
            assert visibilities(payload["evidence_history"]) == visible
        else:
            assert "evidence_history" not in payload
            assert payload["current_evidence"] == periods(visible[-1])
        if attempt["arm"] in {"PRIOR_P_ONLY", "PRIOR_P_FACT"}:
            # Each checkpoint carries the previous checkpoint's valid output.
            assert payload["previous_probability"] == (None if attempt["checkpoint_index"] == 0 else 0.4)
        text = json.dumps(payload)
        assert not any(marker in text for marker in NEVER_VISIBLE_MARKERS)


def _legacy_flat(episode):
    # The pre-grid shape: one flat list qualified against one shared as_of.
    flat = {key: value for key, value in episode.items() if key != "checkpoints"}
    flat.update(as_of=GRID_CUTOFFS["T-20"], qualifications=episode["checkpoints"][-1]["qualifications"])
    return flat


def _set_cutoff(checkpoint_id, value):
    def change(episode):
        checkpoint_named(episode, checkpoint_id)["as_of"] = value
        return episode

    return change


def _swap_t60_t40_rows(episode):
    t60, t40 = episode["checkpoints"][0], episode["checkpoints"][1]
    t60["qualifications"], t40["qualifications"] = t40["qualifications"], t60["qualifications"]
    return episode


def _rows_not_a_list(episode):
    episode["checkpoints"][1]["qualifications"] = None
    return episode


def _mislabel_offsets(episode):
    # Every cutoff shifted by +1: still strictly increasing and still before
    # target_start, so the ordering check alone would accept this. But "T-60"
    # no longer actually sits OFFSETS["T-60"] before target_start -- the
    # label is lying about what it claims (adversarial-review finding).
    for checkpoint in episode["checkpoints"]:
        checkpoint["as_of"] = checkpoint["as_of"] + 1
    return episode


def _missing_episode_id(episode):
    episode["episode_id"] = ""
    return episode


@pytest.mark.parametrize(
    "mutate",
    [
        _legacy_flat,
        lambda episode: {**episode, "checkpoints": episode["checkpoints"][:2]},
        lambda episode: {**episode, "checkpoints": episode["checkpoints"][::-1]},
        _set_cutoff("T-40", GRID_CUTOFFS["T-60"]),
        _set_cutoff("T-20", TARGET_START),
        _swap_t60_t40_rows,
        _rows_not_a_list,
        _mislabel_offsets,
        _missing_episode_id,
    ],
    ids=[
        "legacy-flat-roster",
        "two-checkpoints",
        "reversed-order",
        "cutoffs-not-increasing",
        "cutoff-at-target-start",
        "rows-from-another-checkpoint",
        "rows-not-a-list",
        "mislabeled-offsets",
        "missing-episode-id",
    ],
)
def test_main_refuses_anything_but_the_complete_grid_before_dispatch(monkeypatch, tmp_path, mutate):
    calls = []

    def fake_call(*args):
        calls.append(1)
        return good_reply(*args)

    configure_main(monkeypatch, tmp_path, [mutate(grid_episode())], fake_call)
    with pytest.raises(SystemExit):
        api.main()
    assert calls == []
    assert not (tmp_path / "run.json.registration.json").exists()


def test_main_refuses_duplicate_episode_ids_before_dispatch(monkeypatch, tmp_path):
    calls = []

    def fake_call(*args):
        calls.append(1)
        return good_reply(*args)

    monkeypatch.setattr(api, "CHECKPOINT_OFFSETS_US", OFFSETS)
    same_id = [grid_episode(episode_id="SYNTHETIC-DUP"), grid_episode(episode_id="SYNTHETIC-DUP")]
    configure_main(monkeypatch, tmp_path, same_id, fake_call)
    with pytest.raises(SystemExit, match="unique"):
        api.main()
    assert calls == []


def test_default_max_calls_is_twelve_episodes_times_three_checkpoints_times_arms(monkeypatch, tmp_path):
    calls = []

    def fake_call(*args):
        calls.append(1)
        return good_reply(*args)

    episodes = [grid_episode(episode_id=f"SYNTHETIC-GRID-{index}") for index in range(13)]
    configure_main(monkeypatch, tmp_path, episodes, fake_call, "--max-episodes", "13")
    with pytest.raises(SystemExit, match="registered calls 156 exceed max-calls 144"):
        api.main()
    assert calls == [] and 144 == 12 * len(api.CHECKPOINT_IDS) * len(api.ARMS)
