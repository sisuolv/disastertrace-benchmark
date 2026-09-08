"""Public-only fixtures deliberately do not use the private compiler or renderer."""

import copy
import itertools
import json
from datetime import datetime, timedelta

import pytest

from disastertrace.controlled.public_oracle import answer, backends, parse_evidence

FIELDS = ("maximum_wind_mph", "minimum_pressure_mb", "latitude_deg", "longitude_deg")
UNITS = ("mph", "mb", "degree", "degree")
TARGET = {
    "entity_id": "storm-a",
    "valid_start": "2026-09-07T00:00:00Z",
    "valid_end": "2026-09-07T06:00:00Z",
    "measurement_kind": "controlled_observation",
}
POLICY = {
    "variable": "maximum_wind_mph",
    "threshold": 100,
    "known_at_or_above": "prepare",
    "known_below": "monitor",
    "unknown": "request_evidence",
    "kind": "research_rule_not_operational_advice",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def assertion(index, value, revision=None, supersedes=None, **changes):
    result = {
        **TARGET,
        "revision_id": revision or f"root-{index}",
        "variable": FIELDS[index],
        "unit": UNITS[index],
        "value": value,
        "supersedes": supersedes,
    }
    result.update(changes)
    return result


def record(record_id, values, issued="2026-09-07T00:00:00Z", operation="SET", delivery=None):
    header = {
        "record_id": record_id,
        "issued_at": issued,
        "operation": operation,
        "source_origin": "controlled_generated",
    }
    lines = [f"1: CONTROLLED_RECORD {canonical(header)}"]
    lines.extend(f"{i}: ASSERT {canonical(value)}" for i, value in enumerate(values, 2))
    return {
        "delivery_id": delivery or f"delivery-{record_id}",
        "record_id": record_id,
        "issued_at": issued,
        "text": "\n".join(lines),
    }


def request(evidence=(), **changes):
    result = {
        "protocol": "disastertrace_controlled_v1",
        "instruction": "Read the public numbered records and maintain per-key state.",
        "checkpoint_time": "2026-09-07T04:00:00Z",
        "target": TARGET.copy(),
        "required_fields": list(FIELDS),
        "policy": POLICY.copy(),
        "evidence": list(evidence),
        "method": "snapshot",
    }
    result.update(changes)
    return result


def initial():
    return record("r0", [assertion(i, value) for i, value in enumerate((85, 985, 25, -70))])


def update(value=105, revision="wind-1", parent="root-0", record_id="r1"):
    return record(
        record_id,
        [assertion(0, value, revision, parent)],
        "2026-09-07T01:00:00Z",
        "PATCH",
    )


def test_correct_partial_patch_preserves_omitted_fields_and_current_sources():
    result = answer(request([initial(), update()]))
    assert result["action"] == "prepare"
    assert result["state"][FIELDS[0]] == {
        "status": "known",
        "value": 105,
        "evidence": [{"record_id": "r1", "line": 2}],
    }
    assert result["state"][FIELDS[1]] == {
        "status": "known",
        "value": 985,
        "evidence": [{"record_id": "r0", "line": 3}],
    }


def test_empty_exposure_is_unknown_and_requires_evidence():
    result = answer(request())
    assert result["action"] == "request_evidence"
    assert all(
        x == {"status": "unknown", "value": None, "evidence": []} for x in result["state"].values()
    )


def test_replaying_old_record_cannot_revert_authority():
    replay = {**initial(), "delivery_id": "replay-0"}
    req = request([initial(), update(), replay])
    assert answer(req)["state"][FIELDS[0]]["value"] == 105
    assert answer(req, "latest-arrival")["state"][FIELDS[0]]["value"] == 85
    parsed = parse_evidence(req)
    assert parsed[-1]["delivery_index"] == 2
    assert parsed[-1]["record_id"] == "r0"
    assert parsed[-1]["line"] == 5


@pytest.mark.parametrize(
    "field,value",
    [
        ("entity_id", "storm-b"),
        ("valid_start", "2026-09-07T01:00:00Z"),
        ("valid_end", "2026-09-07T07:00:00Z"),
    ],
)
def test_unrelated_exact_fact_scope_never_updates_target(field, value):
    other = assertion(0, 140, "other", **{field: value})
    req = request([initial(), record("other", [other], "2026-09-07T02:00:00Z")])
    assert answer(req)["state"][FIELDS[0]]["value"] == 85


def test_same_value_revision_refreshes_evidence():
    result = answer(request([initial(), update(85)]))
    assert result["state"][FIELDS[0]]["value"] == 85
    assert result["state"][FIELDS[0]]["evidence"] == [{"record_id": "r1", "line": 2}]


@pytest.mark.parametrize("value,action", [(99.9, "monitor"), (100, "prepare"), (100.1, "prepare")])
def test_action_threshold_is_inclusive(value, action):
    assert answer(request([record("r", [assertion(0, value)])]))["action"] == action


def test_public_input_and_output_are_not_mutated_or_aliased():
    req = request([initial(), update()])
    before = copy.deepcopy(req)
    result = answer(req)
    result["state"][FIELDS[0]]["evidence"][0]["record_id"] = "mutated"
    assert req == before
    assert answer(req)["state"][FIELDS[0]]["evidence"][0]["record_id"] == "r1"


@pytest.mark.parametrize("backend", ["global-latest-document", "clear-omitted"])
def test_document_mutants_fail_on_field_preservation(backend):
    result = answer(request([initial(), update()]), backend)
    assert result["state"][FIELDS[0]]["value"] == 105
    assert result["state"][FIELDS[1]]["status"] == "unknown"


def test_wrong_source_mutant_preserves_value_but_changes_citation():
    req = request([initial(), update()])
    result = answer(req, "correct-value-wrong-source")
    assert result["state"][FIELDS[0]]["value"] == 105
    assert result["state"][FIELDS[0]]["evidence"] != answer(req)["state"][FIELDS[0]]["evidence"]


def test_always_known_fabricates_only_missing_fields():
    req = request([record("r", [assertion(0, 85)])])
    result = answer(req, "always-known")
    assert result["state"][FIELDS[0]] == answer(req)["state"][FIELDS[0]]
    assert all(slot["status"] == "known" for slot in result["state"].values())


def test_always_unknown_is_deliberately_incorrect_when_facts_are_visible():
    assert answer(request([initial()]), "always-unknown") == answer(request())


@pytest.mark.parametrize("method", ["structured_state", "answer_history"])
def test_copy_previous_uses_only_declared_valid_public_carrier(method):
    previous = answer(request([initial()]))
    carrier = (
        {"previous_state": previous}
        if method == "structured_state"
        else {"answer_history": [answer(request()), previous]}
    )
    req = request([initial(), update()], method=method, **carrier)
    assert answer(req, "always-copy-previous") == previous
    assert answer(req)["state"][FIELDS[0]]["value"] == 105


def test_copy_previous_without_valid_carrier_defaults_unknown():
    req = request([initial()], method="structured_state", previous_state=None)
    assert answer(req, "always-copy-previous") == answer(request())


@pytest.mark.parametrize(
    "carrier", [{"previous_state": {"bad": True}}, {"answer_history": [{"bad": True}]}]
)
def test_malformed_answers_cannot_be_admitted_to_public_carrier(carrier):
    method = "structured_state" if "previous_state" in carrier else "answer_history"
    with pytest.raises(ValueError):
        answer(request([initial()], method=method, **carrier))


def test_latest_issued_is_legitimate_on_monotonic_single_chains():
    req = request([initial(), update(), {**initial(), "delivery_id": "replay"}])
    assert answer(req, "per-key-latest-issued") == answer(req)


def test_named_backends_are_fixed_and_unknown_backend_rejected():
    assert backends == (
        "correct",
        "latest-arrival",
        "global-latest-document",
        "clear-omitted",
        "always-unknown",
        "always-known",
        "always-copy-previous",
        "correct-value-wrong-source",
        "per-key-latest-issued",
    )
    with pytest.raises(ValueError):
        answer(request(), "typo")


@pytest.mark.parametrize(
    "change",
    [
        {"supersedes": "absent"},
        {"supersedes": "root-1"},
        {"unit": "km/h"},
        {"value": True},
        {"value": -1},
        {"measurement_kind": "forecast"},
        {"valid_end": TARGET["valid_start"]},
        {"extra": "hidden"},
    ],
)
def test_invalid_assertion_is_rejected_instead_of_silently_becoming_unknown(change):
    value = {**assertion(0, 105, "wind-1", "root-0"), **change}
    with pytest.raises(ValueError):
        answer(request([initial(), record("r1", [value], "2026-09-07T01:00:00Z", "PATCH")]))


def test_parent_must_be_visible_in_earlier_delivery_not_later_or_same_record():
    with pytest.raises(ValueError):
        answer(request([update(), initial()]))
    same = record("same", [assertion(0, 85), assertion(0, 105, "child", "root-0")])
    with pytest.raises(ValueError):
        answer(request([same]))


@pytest.mark.parametrize(
    "issued",
    ["2026-09-06T23:00:00Z", "2026-09-07T00:00:00Z", "2026-09-07T05:00:00Z", "2026-09-07T01:00:00"],
)
def test_invalid_issue_order_future_exposure_and_naive_time_are_rejected(issued):
    child = record("r1", [assertion(0, 105, "child", "root-0")], issued, "PATCH")
    with pytest.raises(ValueError):
        answer(request([initial(), child]))


def test_ambiguous_independent_root_and_fork_are_rejected():
    root = record("other", [assertion(0, 90, "other-root")], "2026-09-07T01:00:00Z")
    fork = record("fork", [assertion(0, 90, "fork", "root-0")], "2026-09-07T02:00:00Z", "PATCH")
    for evidence in ([initial(), root], [initial(), update(), fork]):
        with pytest.raises(ValueError):
            answer(request(evidence))


def test_patch_cannot_introduce_parentless_root():
    with pytest.raises(ValueError):
        answer(request([record("r", [assertion(0, 85)], operation="PATCH")]))


def test_conflicting_replay_and_duplicate_delivery_ids_are_rejected():
    changed = copy.deepcopy(initial())
    changed["delivery_id"] = "replay"
    changed["text"] = changed["text"].replace('"value":85', '"value":86')
    for evidence in ([initial(), changed], [initial(), initial()]):
        with pytest.raises(ValueError):
            answer(request(evidence))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item: item.update(record_id="different"),
        lambda item: item.update(issued_at="2026-09-07T01:00:00Z"),
        lambda item: item.update(text=item["text"].replace("2: ASSERT", "9: ASSERT")),
        lambda item: item.update(text=item["text"].replace("2: ASSERT", "2: OTHER")),
        lambda item: item.update(
            text=item["text"].replace('"operation":"SET"', '"operation":"SET","operation":"SET"')
        ),
        lambda item: item.update(text=item["text"].replace('"value":85', '"value":NaN')),
        lambda item: item.update(text=item["text"].replace('"value":85', '"value":1e999')),
        lambda item: item.update(text=item["text"] + "\n6: HIDDEN {}"),
    ],
)
def test_numbered_public_grammar_and_identity_are_strict(mutate):
    item = initial()
    mutate(item)
    with pytest.raises(ValueError):
        answer(request([item]))


@pytest.mark.parametrize(
    "changes",
    [
        {"protocol": "legacy"},
        {"target": {**TARGET, "extra": "secret"}},
        {"required_fields": [FIELDS[0]]},
        {"method": "snapshot", "previous_state": {}},
        {"method": "structured_state", "answer_history": []},
        {"policy": {**POLICY, "threshold": 101}},
        {"gold": {}},
    ],
)
def test_public_request_rejects_out_of_contract_fields_and_policy(changes):
    with pytest.raises(ValueError):
        answer(request([initial()], **changes))


@pytest.mark.parametrize("values", list(itertools.product((85, 100, 115), repeat=3)))
def test_small_state_space_revision_values_and_old_replays(values):
    """Exhaust the three-step wind state space, including no-op revisions."""
    root = record("first", [assertion(0, values[0])])
    child = update(values[1])
    final = record(
        "final", [assertion(0, values[2], "wind-2", "wind-1")], "2026-09-07T02:00:00Z", "PATCH"
    )
    for prefix, value, source in (
        ([root], values[0], "first"),
        ([root, child], values[1], "r1"),
        ([root, child, final], values[2], "final"),
    ):
        expected = {
            "status": "known",
            "value": value,
            "evidence": [{"record_id": source, "line": 2}],
        }
        result = answer(request(prefix))
        assert result["state"][FIELDS[0]] == expected
        assert result["action"] == ("prepare" if value >= 100 else "monitor")
        for replayed in prefix:
            replay = {**replayed, "delivery_id": "new-replay"}
            assert answer(request([*prefix, replay])) == result


def test_independent_root_delivery_permutations_preserve_state():
    roots = [
        record(f"field-{i}", [assertion(i, value)]) for i, value in enumerate((85, 985, 25, -70))
    ]
    expected = answer(request(roots))
    for permutation in itertools.permutations(roots):
        assert answer(request(permutation)) == expected


def test_timezone_equivalent_valid_windows_identify_the_same_fact():
    child = assertion(
        0,
        105,
        "child",
        "root-0",
        valid_start="2026-09-07T02:00:00+02:00",
        valid_end="2026-09-07T08:00:00+02:00",
    )
    correction = record("correction", [child], "2026-09-07T01:00:00Z", "PATCH")
    assert answer(request([initial(), correction]))["state"][FIELDS[0]]["value"] == 105


@pytest.mark.parametrize(
    "index,value",
    [
        (0, 300.01),
        (0, 85.001),
        (0, 10**500),
        (1, 799.99),
        (1, 1100.01),
        (2, -90.01),
        (2, 90.01),
        (3, -180.01),
        (3, 180.01),
    ],
)
def test_all_numeric_bounds_and_precision_are_enforced(index, value):
    with pytest.raises(ValueError):
        answer(request([record("r", [assertion(index, value)])]))


@pytest.mark.parametrize("backend", backends)
def test_every_diagnostic_output_obeys_new_schema(backend):
    from disastertrace.controlled.schema import parse_decision

    for req in (
        request(),
        request([initial(), update()]),
        request([record("partial", [assertion(0, 85)])]),
    ):
        result = answer(req, backend)
        assert parse_decision(canonical(result)) == result


def test_set_cannot_hide_a_correction_parent():
    child = record(
        "set-child", [assertion(0, 105, "child", "root-0")], "2026-09-07T01:00:00Z", "SET"
    )
    with pytest.raises(ValueError):
        answer(request([initial(), child]))


def test_revision_id_cannot_be_reused_under_different_record_identity():
    cloned = record("clone", [assertion(0, 85)])
    with pytest.raises(ValueError):
        answer(request([initial(), cloned]))


def _transform_episode(episode, transformation):
    transformed = copy.deepcopy(episode)
    time_fields = {"valid_start", "valid_end", "issued_at", "delivered_at", "at"}
    identity_fields = {
        "episode_id",
        "root_id",
        "group_id",
        "entity_id",
        "record_id",
        "delivery_id",
        "revision_id",
        "supersedes",
    }

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if transformation == "shift_times" and key in time_fields:
                    parsed = datetime.fromisoformat(item.replace("Z", "+00:00"))
                    value[key] = (parsed + timedelta(days=37, hours=3)).isoformat()
                elif transformation == "rename_ids" and key in identity_fields and item is not None:
                    value[key] = "renamed-" + item
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    if transformation == "move_locators":
        for item in transformed["records"]:
            item["assertions"].reverse()
    else:
        walk(transformed)
    return transformed


@pytest.mark.parametrize("transformation", ["shift_times", "rename_ids", "move_locators"])
@pytest.mark.parametrize("episode_index", range(12))
def test_micro_metamorphic_compiler_public_agreement_and_invariants(transformation, episode_index):
    from disastertrace.controlled import compiler, generator, renderer

    original = generator.micro_episodes()[episode_index]
    transformed = _transform_episode(original, transformation)
    assert transformed != original
    changed_citations = 0
    for checkpoint in original["checkpoints"]:
        checkpoint_id = checkpoint["checkpoint_id"]
        before = compiler.reference_at(original, checkpoint_id)
        expected = compiler.reference_at(transformed, checkpoint_id)
        public_request = renderer.render_request(transformed, checkpoint_id, method="snapshot")
        observed = answer(public_request)
        assert observed == expected
        assert observed["action"] == before["action"]
        for field in FIELDS:
            prior, current = before["state"][field], observed["state"][field]
            assert (current["status"], current["value"]) == (prior["status"], prior["value"])
            if transformation == "shift_times":
                assert current["evidence"] == prior["evidence"]
            elif transformation == "rename_ids":
                assert current["evidence"] == [
                    {"record_id": "renamed-" + ref["record_id"], "line": ref["line"]}
                    for ref in prior["evidence"]
                ]
            elif prior["evidence"] != current["evidence"]:
                changed_citations += 1
        if transformation == "move_locators":
            visible = {
                (entry["record_id"], entry["line"]): entry["assertion"]
                for entry in parse_evidence(public_request)
            }
            for field, slot in observed["state"].items():
                for ref in slot["evidence"]:
                    cited = visible[(ref["record_id"], ref["line"])]
                    assert cited["variable"] == field
                    assert cited["value"] == slot["value"]
    if transformation == "move_locators":
        assert changed_citations > 0
