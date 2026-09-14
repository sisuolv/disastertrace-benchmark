"""Audit overlap in already-exposed calendars without reading outcome labels."""

import datetime as dt
import hashlib
import itertools
import json
import shutil
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "data_dependence_audit_01"
TARGET_FIELDS = (
    "entity",
    "variable",
    "units",
    "event_operator",
    "threshold",
    "spatial_support",
    "physical_start",
    "physical_end",
    "report_policy",
    "outcome_kind",
    "temporal_semantics",
    "release_event_at",
    "spatial_radius_m",
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def iso(value):
    return dt.datetime.fromtimestamp(value / 1e6, dt.timezone.utc).isoformat()


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    ledger_path = HERE / "data_governance_01/EXPOSURE_LEDGER.json"
    ledger = read(ledger_path)
    loaded, bindings, target_members, physical = {}, {}, defaultdict(list), set()
    native_versions = {}
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE opportunities (calendar TEXT, opportunity TEXT, "
        + ", ".join(field + "" for field in TARGET_FIELDS)
        + ")"
    )
    for calendar in ledger["calendars"]:
        assert calendar["exposed_to_development"] is True
        assert calendar["eligible_for_independent_confirmation"] is False
        name, folder = calendar["calendar"], HERE / calendar["dataset"]
        assert folder.resolve().is_relative_to(HERE)
        build = read(folder / "BUILD.json")
        assert sha(folder / "BUILD.json") == calendar["files"]["BUILD.json"]
        names = (
            "public/OPPORTUNITIES.json",
            "public/TARGETS.json",
            "public/E_F_PAIRS.json",
            "public/QUERY_CATALOG.json",
            "environment/NATIVE_PRODUCT_INDEX.json",
        )
        bindings[name] = {}
        for filename in names:
            digest = sha(folder / filename)
            assert digest == build["files"][filename]
            bindings[name][filename] = digest
        opportunities = read(folder / names[0])
        targets = {row["target_id"]: row for row in read(folder / names[1])}
        pairs = {row["opportunity_id"]: row for row in read(folder / names[2])}
        queries = {row["query_id"]: row for row in read(folder / names[3])}
        native = read(folder / names[4])
        identities, e_slots, footprints = Counter(), set(), []
        for row in opportunities:
            target, pair = targets[row["target_id"]], pairs[row["opportunity_id"]]
            assert pair["F_target_id"] == row["target_id"]
            assert row["cutoff"] < target["physical_start"] < target["physical_end"]
            identity = tuple(target[field] for field in TARGET_FIELDS)
            identities[identity] += 1
            physical.add(
                (target["entity"], target["physical_start"], target["physical_end"])
            )
            target_members[identity].append((name, row["opportunity_id"]))
            connection.execute(
                "INSERT INTO opportunities VALUES ("
                + ",".join("?" for _ in range(15))
                + ")",
                (name, row["opportunity_id"], *identity),
            )
            starts = [row["cutoff"]]
            for query_id in pair["query_ids"]:
                query = queries[query_id]
                assert query["slot_start"] < query["slot_end"] <= row["cutoff"]
                e_slots.add((query["station"], query["slot_start"], query["slot_end"]))
                starts.append(query["slot_start"])
            footprints.append((min(starts), target["physical_end"]))
        for row in native:
            identity = row["source_id"]
            content = {key: value for key, value in row.items() if key != "source_id"}
            if identity in native_versions:
                assert native_versions[identity] == content
            native_versions[identity] = content
        loaded[name] = {
            "identities": identities,
            "slots": e_slots,
            "native": {row["source_id"] for row in native},
            "footprint": (min(a for a, _ in footprints), max(b for _, b in footprints)),
            "opportunities": len(opportunities),
        }
    columns = ", ".join(TARGET_FIELDS)
    sql_targets = connection.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT " + columns + " FROM opportunities)"
    ).fetchone()[0]
    assert sql_targets == len(target_members) == ledger["canonical_threshold_targets"]
    assert len(physical) == ledger["station_time_windows_ignoring_threshold"]
    pair_rows = []
    for left, right in itertools.combinations(loaded, 2):
        a, b = loaded[left], loaded[right]
        shared = set(a["identities"]) & set(b["identities"])
        sql_shared = connection.execute(
            "SELECT COUNT(*) FROM (SELECT "
            + columns
            + " FROM opportunities WHERE calendar IN (?, ?) GROUP BY "
            + columns
            + " HAVING COUNT(DISTINCT calendar) = 2)",
            (left, right),
        ).fetchone()[0]
        assert sql_shared == len(shared)
        af, bf = a["footprint"], b["footprint"]
        signed_gap = max(af[0], bf[0]) - min(af[1], bf[1])
        pair_rows.append(
            {
                "left": left,
                "right": right,
                "shared_threshold_targets": len(shared),
                "left_opportunities_reusing_shared_targets": sum(
                    a["identities"][key] for key in shared
                ),
                "right_opportunities_reusing_shared_targets": sum(
                    b["identities"][key] for key in shared
                ),
                "shared_registered_E_slots": len(a["slots"] & b["slots"]),
                "shared_catalog_TAF_versions": len(a["native"] & b["native"]),
                "registered_E_slot_to_F_window_signed_gap_hours": signed_gap
                / 3_600_000_000,
                "registered_E_to_F_24h_separation": signed_gap >= 86_400_000_000,
                "full_input_purge_qualified": False,
                "independence_qualified": False,
            }
        )
    repeated = Counter(len(rows) for rows in target_members.values())
    cross_calendar = [
        {"target_contract": dict(zip(TARGET_FIELDS, key)), "occurrences": rows}
        for key, rows in target_members.items()
        if len({name for name, _ in rows}) > 1
    ]
    total = sum(row["opportunities"] for row in loaded.values())
    assert total == ledger["total_unique_opportunities"]
    assert sum(copies * count for copies, count in repeated.items()) == total
    save("PAIR_OVERLAPS.json", pair_rows)
    save("CROSS_CALENDAR_TARGETS.json", cross_calendar)
    save(
        "VALIDATION.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "passed": True,
            "calendars": len(loaded),
            "opportunities": total,
            "threshold_targets": len(target_members),
            "physical_station_windows": len(physical),
            "opportunity_multiplicity_per_threshold_target": dict(
                sorted(repeated.items())
            ),
            "cross_calendar_threshold_targets": len(cross_calendar),
            "python_sqlite_target_and_pair_counts_equal": True,
            "native_catalog_same_id_metadata_agree": True,
            "calendar_registered_E_to_F_envelopes": {
                name: {
                    "start": iso(row["footprint"][0]),
                    "end_exclusive": iso(row["footprint"][1]),
                }
                for name, row in loaded.items()
            },
            "source_bindings": bindings,
            "exposure_ledger_sha256": sha(ledger_path),
            "new_source_requests": 0,
            "new_model_calls": 0,
            "private_outcomes_read": False,
            "reserved_confirmation_opened": False,
            "independent_weather_process_count": None,
            "interpretation": [
                "Observed overlap in already-exposed development material; not a selected confirmation split.",
                "Public target identity uses all listed contract fields and ignores arbitrary target IDs.",
                "Native catalog overlap is potential common product availability, not proof every method saw it.",
                "E-slot/F-window envelopes exclude full TAF valid windows and persistent model/session history; a positive envelope gap alone cannot qualify full-input purging.",
                "A negative signed gap denotes overlap of the two regional temporal envelopes; different stations need not share the same physical observation.",
                "Temporal separation does not establish distinct synoptic processes or sample independence.",
            ],
        },
    )
    print(
        json.dumps(
            {
                "opportunities": total,
                "targets": len(target_members),
                "cross_calendar_targets": len(cross_calendar),
                "passed": True,
            }
        )
    )


if __name__ == "__main__":
    main()
