"""Independent possible-world checks and counterexamples for the new protocol."""

import copy
import itertools
from fractions import Fraction

import pytest
from pydantic import ValidationError

from disastertrace.active_forecast import Episode, Evaluator, public_view
from disastertrace.active_forecast.schema import parse_instant


def locator():
    return {
        "kind": "json_pointer",
        "path": "fixtures/source.json",
        "sha256": "a" * 64,
        "role": "derived_product",
        "pointer": "/0",
    }


def day(index):
    return {"kind": "station_day", "label": f"day-{index}", "day": f"2024-01-{index + 1:02}"}


def count_data(values=(1, 1, 0), needed=2):
    supports = [day(i) for i in range(len(values))]
    return {
        "schema_version": "active_forecast.v1",
        "id": "fixture",
        "family": "fixture",
        "group": "synthetic-group",
        "variant": "complete_pool",
        "split": "development",
        "origin": "synthetic",
        "question": "At least two station days at or above one?",
        "time_policy": "archive_delivery",
        "as_of": None,
        "delivery_step": 0,
        "target": {
            "operator": "count_threshold",
            "entity": "station",
            "variable": "TMAX",
            "unit": "degC",
            "supports": supports,
            "value_threshold": 1,
            "count_threshold": needed,
        },
        "cards": [
            {
                "id": str(i),
                "cost": 1,
                "title": "Synthetic daily record",
                "source_id": "fixture",
                "issued_at": None,
                "issue_label": "issue time unknown",
                "issue_missing_reason": "synthetic fixture does not declare issue time",
                "availability": None,
                "availability_missing_reason": "synthetic controlled delivery",
                "delivery_step": 0,
                "captures": [],
                "records": [
                    {
                        "entity": "station",
                        "variable": "TMAX",
                        "unit": "degC",
                        "support": s,
                        "version": "original",
                        "value": value,
                        "quality": "valid" if value is not None else "missing",
                        "locators": [locator()],
                    }
                ],
            }
            for i, (s, value) in enumerate(zip(supports, values))
        ],
    }


def area_data(values=((2, 0), (0, 0), (0, 2)), threshold="1/2"):
    data = count_data()
    supports = [
        {
            "kind": "tile",
            "label": f"tile-{i}",
            "valid_at": "2024-01-01T00:00:00Z",
            "box": [0, 1, 2 * i, 2 * i + 2],
        }
        for i in range(3)
    ]
    data["target"] = {
        "operator": "area_threshold",
        "entity": "station",
        "variable": "TMAX",
        "unit": "degC",
        "supports": supports,
        "height": 1,
        "width": 6,
        "fraction_threshold": threshold,
    }
    for card, support, (positive, negative) in zip(data["cards"], supports, values):
        card["records"][0].update(
            support=support, value={"positive": positive, "negative": negative}
        )
    return data


def revision_data(values=("0.1", "0.3"), threshold="0.2"):
    data = count_data(values)
    support = {"kind": "instant", "label": "forecast validity", "valid_at": "2024-01-03T00:00:00Z"}
    data["target"] = {
        "operator": "revision_delta",
        "entity": "station",
        "variable": "TMAX",
        "unit": "degC",
        "supports": [support],
        "versions": ["old", "new"],
        "threshold": threshold,
    }
    for card, version in zip(data["cards"], ["old", "new"]):
        card["records"][0].update(support=support, version=version)
    return data


def subsets(ids):
    for n in range(len(ids) + 1):
        yield from itertools.combinations(ids, n)


def test_exact_revision_at_decimal_boundary():
    evaluator = Evaluator(Episode.model_validate(revision_data()))
    assert evaluator.reference(["0", "1"]).value == Fraction(1, 5)
    assert evaluator.reference(["0", "1"]).decision == "yes"
    assert evaluator.reference(["1"]).decision == "unknown"
    assert evaluator.certificates().minimum_cost == 2


def test_exact_area_upper_boundary_and_nodata():
    data = area_data(((0, 2), (0, 2), (0, 0)), threshold="1/3")
    evaluator = Evaluator(Episode.model_validate(data))
    ref = evaluator.reference(["0", "1", "2"])
    assert ref.upper == Fraction(1, 3)
    assert ref.decision == "unknown"
    assert not evaluator.sufficient([])
    assert evaluator.sufficient(["0", "1", "2"])


def test_normalized_instant_support_matches_equivalent_offsets():
    data = revision_data()
    data["cards"][1]["records"][0]["support"] = {
        "kind": "instant",
        "label": "other offset",
        "valid_at": "2024-01-02T19:00:00-05:00",
    }
    assert Evaluator(Episode.model_validate(data)).reference(["0", "1"]).decision == "yes"


@pytest.mark.parametrize("bad", ["2024-01-01", "2024-01-01T00:00:00", 0, True])
def test_naive_or_numeric_instants_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        parse_instant(bad)


def test_historical_availability_uses_proof_upper_bound_not_issue_or_capture():
    data = count_data()
    data.update(time_policy="historical_asof", as_of="2024-01-01T23:45:00Z")
    for card in data["cards"]:
        card.update(
            issued_at="2024-01-01T01:00:00+02:00",
            issue_label="original issue",
            issue_missing_reason=None,
        )
    card = data["cards"][0]
    card.update(
        availability={
            "lower": "2024-01-02T00:00:00+02:00",
            "upper": "2024-01-02T01:00:00+02:00",
            "proof": locator(),
        },
        availability_missing_reason=None,
    )
    evaluator = Evaluator(Episode.model_validate(data))
    assert evaluator.legal_ids == ("0",)
    assert evaluator.episode.cards[0].issued_at.isoformat() == "2023-12-31T23:00:00+00:00"
    card["availability"]["upper"] = "2024-01-02T00:00:00Z"
    assert Evaluator(Episode.model_validate(data)).legal_ids == ()


def test_forecast_valid_time_can_be_future_but_delivery_cannot():
    data = revision_data()
    data["cards"][1]["delivery_step"] = 1
    evaluator = Evaluator(Episode.model_validate(data))
    assert evaluator.legal_ids == ("0",)
    with pytest.raises(ValueError, match="unavailable"):
        evaluator.reference(["1"])
    data["delivery_step"] = 1
    assert Evaluator(Episode.model_validate(data)).reference(["0", "1"]).decision == "yes"


def test_possible_world_count_certificates():
    checked = 0

    def classify(values):
        return "yes" if values.count(1) >= 2 else "no" if values.count(0) >= 2 else "unknown"

    for values in itertools.product([0, 1, None], repeat=3):
        evaluator = Evaluator(Episode.model_validate(count_data(values)))
        for read in subsets(["0", "1", "2"]):
            unread = [i for i in range(3) if str(i) not in read]
            worlds = set()
            for completion in itertools.product([0, 1, None], repeat=len(unread)):
                world = list(values)
                for i, value in zip(unread, completion):
                    world[i] = value
                worlds.add(classify(world))
            assert evaluator.sufficient(read) == (worlds == {classify(list(values))})
            checked += 1
    assert checked == 216


def test_possible_world_area_certificates():
    states = [(2, 0), (0, 2), (0, 0), (1, 0), (0, 1), (1, 1)]

    def classify(values):
        return (
            "yes"
            if sum(v[0] for v in values) >= 3
            else ("no" if 6 - sum(v[1] for v in values) < 3 else "unknown")
        )

    checked = 0
    for values in itertools.product(states, repeat=3):
        evaluator = Evaluator(Episode.model_validate(area_data(values)))
        for read in subsets(["0", "1", "2"]):
            unread = [i for i in range(3) if str(i) not in read]
            worlds = set()
            for completion in itertools.product(states, repeat=len(unread)):
                world = list(values)
                for i, value in zip(unread, completion):
                    world[i] = value
                worlds.add(classify(world))
            assert evaluator.sufficient(read) == (worlds == {classify(values)})
            checked += 1
    assert checked == 1728


@pytest.mark.parametrize("bad", [True, 1.0, "NaN", "Infinity", "1/0", float("nan")])
def test_invalid_exact_numbers_rejected(bad):
    data = count_data()
    data["target"]["value_threshold"] = bad
    with pytest.raises(ValidationError):
        Episode.model_validate(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["target"].update(count_threshold=True),
        lambda d: d["target"].update(count_threshold=4),
        lambda d: d["cards"][0].update(cost=True),
        lambda d: d["cards"][0].update(cost=0),
        lambda d: d["cards"][0]["records"][0].update(value=None),
        lambda d: d["cards"][1]["records"][0].update(support=day(0)),
        lambda d: d["target"].update(supports=[day(0), day(0)]),
        lambda d: d.update(private_answer="yes"),
        lambda d: d["cards"][0].update(availability_missing_reason=None),
        lambda d: d.update(as_of="2024-01-01T00:00:00Z"),
    ],
)
def test_invalid_schema_rejected(mutate):
    data = count_data()
    mutate(data)
    with pytest.raises(ValidationError):
        Episode.model_validate(data)


def test_area_partition_is_geometrically_disjoint_and_complete():
    data = area_data()
    data["target"]["supports"][1]["box"] = [0, 1, 1, 3]
    with pytest.raises(ValidationError, match="overlap"):
        Episode.model_validate(data)
    data = area_data(((3, 0), (0, 0), (0, 2)))
    with pytest.raises(ValidationError, match="support size"):
        Episode.model_validate(data)


def test_wrong_scope_and_wrong_version_do_not_substitute():
    data = revision_data()
    data["cards"][1]["records"][0]["version"] = "newer"
    evaluator = Evaluator(Episode.model_validate(data))
    assert evaluator.reference(["0", "1"]).decision == "unknown"
    assert evaluator.sufficient([])  # The complete catalog proves one required version absent.
    data = count_data()
    data["cards"][1]["records"][0]["unit"] = "kelvin"
    assert Evaluator(Episode.model_validate(data)).reference(["0", "1", "2"]).decision == "unknown"


def test_scoring_separates_answer_grounding_acquisition_and_budget():
    evaluator = Evaluator(Episode.model_validate(count_data()))
    result = evaluator.score([], {"decision": "unknown", "citations": []}, budget=3)
    assert result.visible_decision_correct and not result.goal_correct
    assert result.avoidable_unresolved and result.minimum_extra_cost == 2
    assert not evaluator.score(
        ["0"], {"decision": "yes", "citations": ["0", "1"]}, 3
    ).cited_only_read
    assert not evaluator.score(
        ["0", "1"], {"decision": "yes", "citations": ["0"]}, 3
    ).grounded_success
    assert evaluator.score(
        ["0", "1"], {"decision": "yes", "citations": ["0", "1"]}, 2
    ).grounded_success
    assert not evaluator.score([], None, 1).budget_resolvable
    with pytest.raises(ValueError, match="budget"):
        evaluator.score(["0", "1"], {"decision": "yes", "citations": []}, 1)
    with pytest.raises(ValueError):
        evaluator.score([], None, True)


@pytest.mark.parametrize(
    "answer",
    [
        None,
        [],
        {"decision": "yes"},
        {"decision": "yes", "citations": [], "reasoning": "extra"},
        {"decision": ["yes"], "citations": []},
        {"decision": "unknown", "citations": ["0", "0"]},
        {"decision": "yes", "citations": [1]},
        {"decision": True, "citations": []},
    ],
)
def test_malformed_answers_are_failures_without_crashing(answer):
    evaluator = Evaluator(Episode.model_validate(count_data()))
    assert not evaluator.score([], answer, 3).valid


def test_public_projection_hides_unread_values_quality_provenance_and_future_cards():
    data = count_data()
    data["cards"][2]["delivery_step"] = 2
    episode = Episode.model_validate(data)
    view = public_view(episode, ["0"], 2).model_dump(mode="json")
    assert [c["id"] for c in view["catalog"]] == ["0", "1"]
    assert [c["id"] for c in view["evidence"]] == ["0"]
    assert view["remaining_budget"] == 1
    serialized = str(view)
    for field in (
        "locators",
        "sha256",
        "captures",
        "minimum_cost",
        "goal_decision",
        "group",
        "split",
    ):
        assert field not in serialized
    assert "value" not in view["catalog"][1]["record_index"][0]
    assert "quality" not in view["catalog"][1]["record_index"][0]
    changed = copy.deepcopy(data)
    changed["cards"][1]["records"][0].update(value=None, quality="missing")
    assert (
        public_view(Episode.model_validate(changed), ["0"], 2).model_dump()
        == public_view(episode, ["0"], 2).model_dump()
    )


def test_schema_json_roundtrip_is_exact_and_frozen():
    episode = Episode.model_validate(revision_data())
    assert Episode.model_validate_json(episode.model_dump_json()) == episode
    with pytest.raises(ValidationError):
        episode.cards[0].cost = 8
    assert Episode.model_json_schema()["additionalProperties"] is False


def test_minimum_cost_is_not_the_first_inclusion_minimal_certificate():
    data = count_data([1, 1, 1, 1])
    data["cards"][0]["records"].extend(data["cards"][1]["records"])
    data["cards"][0]["cost"] = 5
    del data["cards"][1]
    evaluator = Evaluator(Episode.model_validate(data))
    certificates = evaluator.certificates()
    assert [(c.ids, c.cost) for c in certificates.minimal_sets] == [
        (("0",), 5),
        (("2", "3"), 2),
    ]
    assert certificates.minimum_cost == 2
    assert evaluator.extension_cost(["2"]) == 1
    assert evaluator.score(["2"], {"decision": "unknown", "citations": []}, 2).budget_resolvable


def test_revision_unknown_needs_inspection_when_required_version_is_present_but_invalid():
    data = revision_data()
    data["cards"][0]["records"][0].update(quality="invalid", value="0.1")
    evaluator = Evaluator(Episode.model_validate(data))
    assert evaluator.reference(["0", "1"]).decision == "unknown"
    assert not evaluator.sufficient([])
    assert not evaluator.sufficient(["1"])
    assert evaluator.sufficient(["0"])
    assert evaluator.certificates().minimum_cost == 1


def test_area_decimal_upper_boundary_is_not_a_false_negative():
    data = area_data(((0, 1), (0, 1), (0, 1)), threshold="0.1")
    boxes = [[0, 1, 0, 4], [0, 1, 4, 8], [0, 1, 8, 10]]
    data["target"]["width"] = 10
    for support, card, box, negative in zip(
        data["target"]["supports"], data["cards"], boxes, [4, 4, 1]
    ):
        support["box"] = box
        card["records"][0]["value"]["negative"] = negative
    evaluator = Evaluator(Episode.model_validate(data))
    assert evaluator.reference(["0", "1", "2"]).upper == Fraction(1, 10)
    assert evaluator.reference(["0", "1", "2"]).decision == "unknown"
