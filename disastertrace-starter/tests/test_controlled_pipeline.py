from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.automated.common import canonical
from disastertrace.controlled import compiler, generator, renderer, schema


def chosen(family, case="primary", branch="active"):
    return next(
        ep
        for ep in generator.micro_episodes()
        if ep["family"] == family and ep["case"] == case and ep["branch"] == branch
    )


def test_micro_fixture_count_and_legal_w2_roots():
    episodes = generator.micro_episodes()
    assert len(episodes) == 12
    assert sum(len(ep["checkpoints"]) for ep in episodes) == 60
    for ep in episodes:
        schema.validate_episode(ep)
    ep = chosen("U2", branch="control")
    correction = ep["records"][1]
    assert correction["operation"] == "SET"
    assert correction["assertions"][0]["supersedes"] is None
    assert correction["assertions"][0]["valid_start"] != ep["target"]["valid_start"]


def test_partial_update_preserves_value_and_original_source():
    ep = chosen("U1")
    before = compiler.reference_at(ep, "c1")
    after = compiler.reference_at(ep, "c2")
    pressure = "minimum_pressure_mb"
    assert after["state"][pressure] == before["state"][pressure]
    assert (
        after["state"]["maximum_wind_mph"]["value"] != before["state"]["maximum_wind_mph"]["value"]
    )
    assert compiler.reference_at(ep, "c4") == compiler.reference_at(ep, "c3")


def test_same_value_refresh_and_wrong_window_noninterference():
    ep = chosen("U2", "secondary")
    before = compiler.reference_at(ep, "c1")["state"]["maximum_wind_mph"]
    after = compiler.reference_at(ep, "c2")["state"]["maximum_wind_mph"]
    assert before["value"] == after["value"]
    assert before["evidence"] != after["evidence"]
    assert compiler.reference_at(ep, "c4") == compiler.reference_at(ep, "c2")
    control = chosen("U2", "secondary", "control")
    assert compiler.reference_at(control, "c4") == compiler.reference_at(control, "c1")


@pytest.mark.parametrize(
    "case,field", [("primary", "maximum_wind_mph"), ("secondary", "minimum_pressure_mb")]
)
def test_missing_support_precedes_exposure_and_recovers(case, field):
    delayed = chosen("U3", case)
    full = chosen("U3", case, "control")
    assert compiler.reference_at(delayed, "c1")["state"][field]["status"] == "unknown"
    assert compiler.reference_at(delayed, "c2")["state"][field]["status"] == "unknown"
    assert compiler.reference_at(full, "c1")["state"][field]["status"] == "known"
    for checkpoint in ("c3", "c4"):
        assert compiler.reference_at(delayed, checkpoint) == compiler.reference_at(full, checkpoint)


@pytest.mark.parametrize("mutation", ["fork", "cross_key", "hidden_parent", "unit", "duplicate_id"])
def test_invalid_source_graph_is_rejected_not_unknown(mutation):
    ep = chosen("U1")
    if mutation == "fork":
        second = deepcopy(ep["records"][1])
        second["record_id"] = "fork-record"
        second["assertions"][0]["revision_id"] = "fork-revision"
        ep["records"].append(second)
    elif mutation == "cross_key":
        ep["records"][1]["assertions"][0]["entity_id"] = "different"
    elif mutation == "hidden_parent":
        ep["deliveries"] = [
            d for d in ep["deliveries"] if d["record_id"] != ep["records"][0]["record_id"]
        ]
    elif mutation == "unit":
        ep["records"][0]["assertions"][0]["unit"] = "km/h"
    else:
        ep["records"].append(deepcopy(ep["records"][0]))
    with pytest.raises(ValueError):
        schema.validate_episode(ep)


def test_public_request_excludes_private_annotations_and_future_records():
    ep = chosen("U1")
    ep["provenance"]["private_marker"] = "PRIVATE_GOLD_SENTINEL"
    future = ep["records"][2]
    future["record_id"] = "FUTURE_SENTINEL"
    request = renderer.render_request(ep, "c1", method="snapshot")
    raw = canonical(request)
    assert "PRIVATE_GOLD_SENTINEL" not in raw
    assert "FUTURE_SENTINEL" not in raw
    assert "provenance" not in request
    assert "port_reopening_time" not in raw


def test_all_methods_share_evidence_and_keep_wrong_valid_carrier():
    ep = chosen("U1")
    wrong = compiler.reference_at(ep, "c1")
    wrong["state"]["maximum_wind_mph"]["value"] = 299
    requests = [
        renderer.render_request(ep, "c2", method=m, previous=wrong, history=[wrong])
        for m in schema.METHODS
    ]
    assert all(r["evidence"] == requests[0]["evidence"] for r in requests)
    state = next(r for r in requests if r["method"] == "structured_state")
    assert state["previous_state"]["state"]["maximum_wind_mph"]["value"] == 299
    assert "previous_state" not in requests[0]
    state["previous_state"]["state"]["maximum_wind_mph"]["value"] = 1
    assert wrong["state"]["maximum_wind_mph"]["value"] == 299


@pytest.mark.parametrize("value", [True, float("nan"), 301, -1, 1.001])
def test_numeric_contract_rejects_nonphysical_or_unrepresentable_wind(value):
    with pytest.raises(ValueError):
        schema.validate_number("maximum_wind_mph", value)


def test_real_development_sources_are_inherited_and_bound():
    root = Path(__file__).resolve().parents[1]
    episodes, bindings = generator.development_episodes(root / "work/build-cohort-v1")
    assert len(episodes) == 18
    assert len(bindings) == 3
    assert {ep["group_id"] for ep in episodes} == {"AL092021", "AL062018", "AL052019"}
    for ep in episodes:
        assert ep["split"] == "development"
        assert ep["provenance"]["inherited_values"]
        assert ep["provenance"]["parent_source_sha256"]
        assert (
            ep["provenance"]["origin"]
            == "controlled_generated_with_source_inherited_initial_values"
        )
        schema.validate_episode(ep)


@pytest.mark.parametrize(
    "field,value",
    [
        ("records", {}),
        ("records", None),
        ("deliveries", {}),
        ("split", []),
        ("family", []),
        ("branch", []),
        ("provenance", {}),
        ("split", "development"),
    ],
)
def test_source_admission_rejects_malformed_types_and_forged_origin(field, value):
    episode = chosen("U1")
    episode[field] = value
    with pytest.raises(ValueError):
        schema.validate_episode(episode)


def test_source_admission_rejects_malformed_operation_and_delivery_reference():
    for field in ("operation", "record_id"):
        episode = chosen("U1")
        (episode["records"][0] if field == "operation" else episode["deliveries"][0])[field] = []
        with pytest.raises(ValueError):
            schema.validate_episode(episode)


def test_development_admission_binds_declared_initial_values():
    root = Path(__file__).resolve().parents[1]
    episodes, _ = generator.development_episodes(root / "work/build-cohort-v1")
    episode = episodes[0]
    episode["provenance"]["inherited_values"]["maximum_wind_mph"] += 1
    with pytest.raises(ValueError):
        schema.validate_episode(episode)


def test_generated_public_identifiers_do_not_embed_private_scenario_labels():
    for episode in generator.micro_episodes():
        public = canonical(renderer.render_request(episode, "c4", method="snapshot"))
        for private in (
            episode["root_id"],
            episode["group_id"],
            episode["family"],
            episode["case"],
        ):
            assert private not in public
