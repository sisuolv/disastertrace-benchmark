import copy
import json

import pytest
from shapely.geometry import Polygon

from disastertrace.multimodal_v1.compiler import public_view, reference_for, transition_obligations
from disastertrace.multimodal_v1.fixtures import build_fixture
from disastertrace.multimodal_v1.geometry_reference import relation
from disastertrace.multimodal_v1.pixel_baseline import answer, pixel_relation
from disastertrace.multimodal_v1.rendering import layout_for, pixel_for, render
from disastertrace.multimodal_v1.scoring import rate, score_trajectory
from disastertrace.multimodal_v1.types import ModelCommit, select_version, tri_and, utc


@pytest.fixture
def fixture(tmp_path):
    return build_fixture(tmp_path), tmp_path / "public"


@pytest.mark.parametrize(
    "a,b,want",
    [
        (False, False, False),
        (False, True, False),
        (False, None, False),
        (True, False, False),
        (True, True, True),
        (True, None, None),
        (None, False, False),
        (None, True, None),
        (None, None, None),
    ],
)
def test_three_valued_truth_table(a, b, want):
    assert tri_and(a, b) is want


@pytest.mark.parametrize("bad", [0, 1, "false", [], {}])
def test_rule_rejects_non_booleans(bad):
    with pytest.raises(ValueError):
        tri_and(bad, True)


@pytest.mark.parametrize("branch", ["base", "without_maps", "without_watch_list"])
@pytest.mark.parametrize("checkpoint", range(5))
def test_public_pixels_and_private_reference_agree_on_synthetic_episode(
    fixture, branch, checkpoint
):
    episode, root = fixture
    view = public_view(episode, branch, checkpoint, root)
    assert json.loads(answer(view)) == reference_for(episode, view)


def test_unknown_branch_reference_and_false_and_unknown(fixture):
    episode, root = fixture
    view = public_view(episode, "without_maps", 0, root)
    gold = reference_for(episode, view)["state"]
    assert gold["A"]["relation"] == "unknown" and gold["A"]["inspection_required"] is None
    assert gold["B"]["relation"] == "unknown" and gold["B"]["inspection_required"] is False
    view = public_view(episode, "without_watch_list", 0, root)
    gold = reference_for(episode, view)["state"]
    assert gold["A"]["watched"] is None and gold["A"]["inspection_required"] is False
    assert gold["B"]["inspection_required"] is None


def test_old_replay_does_not_create_new_version(fixture):
    episode, root = fixture
    before = reference_for(episode, public_view(episode, "base", 2, root))
    after_view = public_view(episode, "base", 3, root)
    assert reference_for(episode, after_view) == before
    assert sum(e["artifact_id"] == "map-01" for e in after_view["deliveries"]) == 2
    assert before["state"]["A"]["map_source"] == "map-02"


@pytest.mark.parametrize(
    "key,value",
    [
        ("valid_at", "2024-09-11T18:00:00+00:00"),
        ("product", "cone"),
        ("threshold_kt", 64),
        ("event_id", "OTHER"),
        ("spatial_scope", "elsewhere"),
    ],
)
def test_newer_other_scope_cannot_replace_matching_map(fixture, key, value):
    episode, root = fixture
    metas = [a["meta"] for a in episode["artifacts"] if a["meta"]["modality"] == "image"]
    metas[1]["target"] = dict(metas[1]["target"], **{key: value})
    assert (
        select_version(metas, {"map-01", "map-02"}, episode["target"], "image")["artifact_id"]
        == "map-01"
    )


def test_equal_rank_distinct_versions_fail_closed(fixture):
    episode, root = fixture
    a = episode["artifacts"][0]["meta"]
    b = dict(a, artifact_id="ambiguous")
    with pytest.raises(ValueError):
        select_version([a, b], {a["artifact_id"], b["artifact_id"]}, episode["target"], "image")


def test_visibility_no_future_gold_paths_and_independent_object(fixture):
    episode, root = fixture
    episode["private_secret"] = "SENTINEL_PRIVATE_GOLD"
    episode["private_facts"]["secret"] = "SENTINEL_FUTURE"
    view = public_view(episode, "base", 0, root)
    wire = json.dumps(view)
    assert "SENTINEL" not in wire and str(root) not in wire and "image_path" not in wire
    assert [q["site_id"] for q in view["queries"]] == ["A", "B"]
    assert {a["meta"]["artifact_id"] for a in view["evidence"]} == {"map-01", "watch-01"}
    view["evidence"][0]["meta"]["version"] = 99
    assert episode["artifacts"][0]["meta"]["version"] == 1
    assert [q["site_id"] for q in public_view(episode, "base", 4, root)["queries"]] == [
        "A",
        "B",
        "C",
    ]


def test_public_content_extensions_are_not_silently_exposed(fixture):
    episode, root = fixture
    episode["artifacts"][0]["public_content"]["private_gold"] = "inside"
    with pytest.raises(ValueError):
        public_view(episode, "base", 0, root)


def test_nested_image_metadata_cannot_smuggle_gold(fixture):
    episode, root = fixture
    episode["artifacts"][0]["public_content"]["layout"]["future_query_answer"] = "secret"
    with pytest.raises(ValueError):
        public_view(episode, "base", 0, root)


def test_hash_changed_image_and_path_escape_rejected(fixture):
    episode, root = fixture
    original = (root / "map-01.png").read_bytes()
    (root / "map-01.png").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        public_view(episode, "base", 0, root)
    (root / "map-01.png").write_bytes(original)
    episode["artifacts"][0]["image_path"] = "../outside.png"
    with pytest.raises(ValueError):
        public_view(episode, "base", 0, root)


def test_single_modality_views_recompute_reference(fixture):
    episode, root = fixture
    text = public_view(episode, "base", 0, root, "text_only")
    vision = public_view(episode, "base", 0, root, "vision_only")
    assert reference_for(episode, text)["state"]["B"]["inspection_required"] is False
    assert reference_for(episode, vision)["state"]["A"]["inspection_required"] is False
    assert all(e["meta"]["modality"] == "text" for e in text["evidence"])


def test_value_preservation_and_provenance_refresh_are_separate(fixture):
    episode, root = fixture
    gold = [reference_for(episode, public_view(episode, "base", c, root)) for c in (1, 2)]
    obligations = transition_obligations(*gold)
    assert "A.relation" in obligations["must_change_value"]
    assert "B.relation" in obligations["must_preserve_value"]
    assert "B.map_source" in obligations["must_change_provenance"]
    assert "B.inspection_required" in obligations["must_recheck_dependencies"]
    assert "B.inspection_required" in obligations["must_preserve_value"]


def test_fixing_previous_wrong_value_is_not_stable_degradation(fixture):
    episode, root = fixture
    gold = reference_for(episode, public_view(episode, "base", 0, root))
    wrong = copy.deepcopy(gold)
    wrong["state"]["A"]["relation"] = "inside"
    result = score_trajectory(
        [gold, gold],
        [{"status": "received_valid", "value": wrong}, {"status": "received_valid", "value": gold}],
    )
    assert result["conditional_stable_value_degradation"] == rate(0, 5)
    assert result["first_subsequent_correct_latency"] == 1


def test_missing_answers_keep_full_denominator(fixture):
    episode, root = fixture
    gold = reference_for(episode, public_view(episode, "base", 0, root))
    report = score_trajectory([gold, gold], [{"status": "unknown"}, {"status": "unattempted"}])
    assert report["strict_checkpoints"] == rate(0, 2)
    assert report["value_fields"] == rate(0, 12)
    assert report["conditional_stable_value_degradation"] == rate(0, 0)
    with pytest.raises(ValueError):
        score_trajectory([gold, gold], [{"status": "unknown"}])


def test_equivalent_point_locator_passes_but_wrong_version_and_whole_map_fail(fixture):
    episode, root = fixture
    gold = reference_for(episode, public_view(episode, "base", 2, root))
    result = copy.deepcopy(gold)
    result["state"]["A"]["map_locator"] = "point:A"
    assert score_trajectory([gold], [{"status": "received_valid", "value": result}])[
        "episode_all_correct"
    ]
    result["state"]["A"]["map_source"] = "map-01"
    assert not score_trajectory([gold], [{"status": "received_valid", "value": result}])[
        "episode_all_correct"
    ]
    result = copy.deepcopy(gold)
    result["state"]["A"]["map_locator"] = "whole_image"
    assert not score_trajectory([gold], [{"status": "received_valid", "value": result}])[
        "episode_all_correct"
    ]


@pytest.mark.parametrize(
    "point,want",
    [
        ((0.5, 0.5), "inside"),
        ((1.5, 1.5), "outside"),
        ((0, 1), "boundary_ambiguous"),
        ((8, 8), "unknown"),
    ],
)
def test_geometry_hole_boundary_and_outside_extent(point, want):
    polygon = Polygon([(0, 0), (3, 0), (3, 3), (0, 3)], holes=[[(1, 1), (2, 1), (2, 2), (1, 2)]])
    assert relation(polygon, point, [-1, -1, 4, 4], 0.01) == want


@pytest.mark.parametrize("size", [512, 768, 1024])
def test_pixel_solver_respects_holes_and_plot_extent(size):
    polygon = Polygon([(0, 0), (3, 0), (3, 3), (0, 3)], holes=[[(1, 1), (2, 1), (2, 2), (1, 2)]])
    layout = layout_for([-1, -1, 4, 4])
    png = render(polygon, layout, "2024-09-10T18:00:00+00:00", 34, "controlled_generated")
    for point, expected in [((0.5, 0.5), "inside"), ((1.5, 1.5), "outside"), ((8, 8), "unknown")]:
        assert pixel_relation(png, layout, pixel_for(point, layout), size) == expected


@pytest.mark.parametrize("stamp", ["2024-09-10T18:00:00", "2024-09-10T18:00:00+02:00", "invalid"])
def test_utc_is_explicit(stamp):
    with pytest.raises(ValueError):
        utc(stamp)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "integer_boolean", "extra_field", "huge_locator", "NaN"]
)
def test_output_contract_rejects_ambiguous_values(fixture, mutation):
    episode, root = fixture
    gold = reference_for(episode, public_view(episode, "base", 0, root))
    if mutation == "duplicate":
        raw = '{"state":{},"state":{}}'
    else:
        if mutation == "integer_boolean":
            gold["state"]["A"]["watched"] = 1
        if mutation == "extra_field":
            gold["state"]["A"]["gold"] = True
        if mutation == "huge_locator":
            gold["state"]["A"]["map_locator"] = "x" * 81
        if mutation == "NaN":
            gold["state"]["A"]["watched"] = float("nan")
        raw = json.dumps(gold)
    with pytest.raises(ValueError):
        ModelCommit.parse(raw)
