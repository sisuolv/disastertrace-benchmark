"""Frozen three-family constructions with honest inheritance of initial source values."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from disastertrace.automated.common import fingerprint, read_jsonl
from disastertrace.automated.workflow import verify_build

from .schema import FIELDS, PROTOCOL, UNITS, validate_episode, validate_number

EVENTS = ("AL092021", "AL062018", "AL052019")
GENERATOR_VERSION = "controlled_generator_v1"
SEED = 20260907


def _time(minute: int) -> str:
    return f"2040-01-01T00:0{minute}:00+00:00"


def _episode(
    group: str, family: str, case: str, branch: str, values: dict, provenance: dict, split: str
) -> dict:
    root = f"{group}:{family}:{case}"
    target = {
        "entity_id": "entity-" + fingerprint({"group": group})[:24],
        "valid_start": "2040-01-01T00:00:00+00:00",
        "valid_end": "2040-01-01T01:00:00+00:00",
        "measurement_kind": "controlled_observation",
    }
    records, deliveries = [], []

    def record(name, minute, updates, parents=None, scope=None):
        record_id = "record-" + fingerprint({"root": root, "name": name})[:24]
        assertions = [
            {
                **(scope or target),
                "variable": field,
                "unit": UNITS[field],
                "value": value,
                "revision_id": "revision-"
                + fingerprint({"record": record_id, "field": field})[:24],
                "supersedes": None if parents is None else parents[field],
            }
            for field, value in updates.items()
        ]
        item = {
            "record_id": record_id,
            "issued_at": _time(minute),
            "operation": "SET" if parents is None else "PATCH",
            "source_origin": "controlled_generated",
            "assertions": assertions,
        }
        records.append(item)
        return item

    def deliver(item, minute):
        deliveries.append(
            {
                "delivery_id": "delivery-"
                + fingerprint({"root": root, "index": len(deliveries)})[:24],
                "record_id": item["record_id"],
                "delivered_at": _time(minute),
            }
        )

    def parents(item):
        return {a["variable"]: a["revision_id"] for a in item["assertions"]}

    wind = values["maximum_wind_mph"]
    new_wind = wind if case == "secondary" else (110 if wind < 100 else 90)
    if family == "U1":
        initial = record("initial", 1, values)
        update = record("wind-update", 2, {"maximum_wind_mph": new_wind}, parents(initial))
        deliver(initial, 1)
        deliver(update, 2)
        if branch == "active":
            pressure = values["minimum_pressure_mb"]
            patch = record(
                "pressure-update",
                3,
                {"minimum_pressure_mb": pressure + 1 if pressure < 1100 else pressure - 1},
                parents(initial),
            )
            deliver(patch, 3)
        else:
            deliver(update, 3)
        deliver(initial, 4)
    elif family == "U2":
        initial = record("initial", 1, values)
        scope = {
            **target,
            "valid_start": "2040-01-02T00:00:00+00:00",
            "valid_end": "2040-01-02T01:00:00+00:00",
        }
        if branch == "active":
            update = record(
                "target-correction", 2, {"maximum_wind_mph": new_wind}, parents(initial)
            )
        else:
            update = record("other-window-root", 2, {"maximum_wind_mph": new_wind}, scope=scope)
        unrelated = record(
            "other-entity-root",
            4,
            {"maximum_wind_mph": 120},
            scope={**target, "entity_id": target["entity_id"] + "-other"},
        )
        for item, minute in ((initial, 1), (update, 2), (initial, 3), (unrelated, 4)):
            deliver(item, minute)
    elif family == "U3":
        missing = "maximum_wind_mph" if case == "primary" else "minimum_pressure_mb"
        others = record("other-fields-root", 1, {k: v for k, v in values.items() if k != missing})
        support = record("target-support-root", 1, {missing: values[missing]})
        unrelated_field = "minimum_pressure_mb" if missing == "maximum_wind_mph" else "latitude_deg"
        old_value = values[unrelated_field]
        new_value = round(old_value - 1 if old_value >= 90 else old_value + 1, 2)
        update = record("unrelated-update", 2, {unrelated_field: new_value}, parents(others))
        deliver(others, 1)
        if branch == "control":
            deliver(support, 1)
        deliver(update, 2)
        deliver(support, 3)
        deliver(others, 4)
    else:
        raise ValueError("unsupported family")
    episode = {
        "protocol": PROTOCOL,
        "episode_id": root + ":" + branch,
        "root_id": root,
        "group_id": group,
        "split": split,
        "family": family,
        "case": case,
        "branch": branch,
        "target": target,
        "records": records,
        "deliveries": deliveries,
        "checkpoints": [{"checkpoint_id": f"c{i}", "at": _time(i)} for i in range(5)],
        "provenance": {
            **deepcopy(provenance),
            "generator_version": GENERATOR_VERSION,
            "seed": SEED,
            "generated_components": [
                "entity_and_windows",
                "revision_graph",
                "update_values",
                "delivery_times",
                "controlled_record_text",
            ],
            "official_historical_correction": False,
            "physical_process_realism_validated": False,
        },
    }
    validate_episode(episode)
    return episode


def micro_episodes() -> list[dict]:
    values = dict(zip(FIELDS, (90, 980, 20, -70)))
    provenance = {
        "origin": "synthetic_software_fixture",
        "inherited_values": {},
        "parent_source_sha256": None,
    }
    return [
        _episode("synthetic-micro", family, case, branch, values, provenance, "synthetic_fixture")
        for family in ("U1", "U2", "U3")
        for case in ("primary", "secondary")
        for branch in ("active", "control")
    ]


def source_bindings(source_build: Path) -> list[dict]:
    source_build = Path(source_build)
    manifest = verify_build(source_build)
    episodes = read_jsonl(source_build / "episodes/dynamic_episodes.jsonl")
    declared = {e["group_id"] for e in episodes if e["split"] == "development"}
    if declared != set(EVENTS):
        raise ValueError("source build must contain the frozen three development groups")
    records = read_jsonl(source_build / "records/nhc_records.jsonl")
    return bindings_from_records(records, manifest["build_id"])


def bindings_from_records(records: list[dict], source_build_id: str) -> list[dict]:
    result = []
    for event in EVENTS:
        candidates = [r for r in records if r["storm_id"] == event]
        record = min(candidates, key=lambda r: r["issued_at"])
        values = {field: record["fields"][field] for field in FIELDS}
        for field, value in values.items():
            validate_number(field, value)
        result.append(
            {
                "group_id": event,
                "split": "development",
                "source_build_id": source_build_id,
                "source_record_id": record["record_id"],
                "parent_source_sha256": record["provenance"]["source_sha256"],
                "source_record_sha256": fingerprint(record),
                "source_url": record["provenance"]["source_url"],
                "inherited_values": values,
                "source_field_evidence": {
                    field: record["field_evidence"][field] for field in FIELDS
                },
            }
        )
    return result


def from_bindings(bindings: list[dict]) -> list[dict]:
    if len(bindings) != 3 or [b["group_id"] for b in bindings] != list(EVENTS):
        raise ValueError("three ordered source bindings required")
    episodes = []
    for index, binding in enumerate(bindings):
        case = "secondary" if index == 2 else "primary"
        provenance = {
            **{k: v for k, v in binding.items() if k != "source_build_id"},
            "origin": "controlled_generated_with_source_inherited_initial_values",
        }
        for family in ("U1", "U2", "U3"):
            for branch in ("active", "control"):
                episodes.append(
                    _episode(
                        binding["group_id"],
                        family,
                        case,
                        branch,
                        binding["inherited_values"],
                        provenance,
                        "development",
                    )
                )
    return episodes


def development_episodes(source_build: Path) -> tuple[list[dict], list[dict]]:
    bindings = source_bindings(source_build)
    return from_bindings(bindings), bindings
