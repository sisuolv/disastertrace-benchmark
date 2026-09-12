"""Build input-selected development targets and separately stored outcomes."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from disastertrace.active_forecast.provenance import SourceReader, load_json, write_json
from disastertrace.active_forecast.schema import parse_instant
from disastertrace.active_warning_v1 import Artifact, Episode, Outcome, Tool

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]


def ident(text):
    return "aw-" + hashlib.sha256(text.encode()).hexdigest()[:16]


def tools():
    return tuple(
        Tool(id=kind, kind=kind, description=description)
        for kind, description in (
            ("forecast", "Latest issued compatible professional forecast at request time."),
            (
                "observation",
                "Latest available current wind estimate or same-station observed flow.",
            ),
            (
                "mirror",
                "Another representation of the same latest professional forecast; shared upstream.",
            ),
            ("archive", "Earliest archived forecast for the same target; may be superseded."),
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "dataset_v2")
    args = parser.parse_args()
    destination = args.output
    destination.mkdir(exist_ok=False)
    reader = SourceReader(REPO)
    prior = REPO / "plans/v5_0910_feasibility_12h_20260910"
    products = json.loads((prior / "data/NHC_PRODUCTS.json").read_text())
    lookup = {(p["storm_id"], p["advisory_number"]): p for p in products}
    by_target = defaultdict(list)
    for line in (BASE / "source_audit_nhc/forecast_rows.jsonl").read_text().splitlines():
        row = json.loads(line)
        by_target[row["storm_id"], row["target_time"]].append(row)
    private = {
        (r["storm_id"], r["target_time"]): r
        for r in (
            json.loads(line)
            for line in (BASE / "source_audit_nhc/outcome_targets_private.jsonl")
            .read_text()
            .splitlines()
        )
    }
    episodes, outcomes, excluded = [], [], []
    for (storm, target), rows in sorted(by_target.items()):
        target_time = parse_instant(target)
        deadline = target_time - timedelta(hours=6)
        rows = [r for r in rows if parse_instant(r["issue_time"]) + timedelta(hours=1) < deadline]
        rows.sort(key=lambda r: r["issue_time"])
        if len(rows) < 3:
            excluded.append(
                {"entity": storm, "target": target, "reason": "fewer_than_three_input_versions"}
            )
            continue
        artifacts = []
        for row in rows:
            product = lookup[storm, row["advisory_number"]]
            source = product["source"]
            locator = reader.bind(REPO / source["path"], role="source_bytes")
            if locator.sha256 != source["sha256"]:
                raise ValueError("NHC source no longer matches independently audited bytes")
            issue = parse_instant(row["issue_time"])
            aid = f"{storm}-a{row['advisory_number']:03d}"
            artifacts.append(
                Artifact(
                    id=aid + "-forecast",
                    product_id=aid,
                    provider="NOAA NHC",
                    entity=storm,
                    variable="storm_maximum_sustained_wind",
                    unit="kt",
                    kind="forecast",
                    issued_at=issue,
                    valid_at=target_time,
                    release_at=issue + timedelta(hours=1),
                    captured_at=source["captured_at"],
                    values=(row["forecast_wind_kt"],),
                    source=locator,
                    quality="operational intensity forecast; not local wind exposure",
                )
            )
        start = artifacts[0].release_at
        for product in products:
            issue = parse_instant(product["issue_time"])
            if product["storm_id"] != storm or issue + timedelta(hours=1) > deadline:
                continue
            source = product["source"]
            aid = f"{storm}-a{product['advisory_number']:03d}"
            artifacts.append(
                Artifact(
                    id=aid + "-observation",
                    product_id=aid,
                    provider="NOAA NHC",
                    entity=storm,
                    variable="storm_maximum_sustained_wind",
                    unit="kt",
                    kind="observation",
                    issued_at=issue,
                    valid_at=issue,
                    release_at=issue + timedelta(hours=1),
                    captured_at=source["captured_at"],
                    values=(product["current_wind_kt"],),
                    source=reader.bind(REPO / source["path"], role="source_bytes"),
                    quality="same-agency current intensity estimate; independence not assumed",
                )
            )
        initial_obs = max(
            (a for a in artifacts if a.kind == "observation" and a.release_at <= start),
            key=lambda a: a.valid_at,
        )
        episode = Episode(
            id=ident(storm + target),
            group=storm,
            family="tropical_cyclone",
            entity=storm,
            variable="storm_maximum_sustained_wind",
            unit="kt",
            start_at=start,
            target_at=target_time,
            deadline=deadline,
            checkpoints=(start + (deadline - start) / 2, deadline),
            threshold=64,
            threshold_meaning="storm maximum sustained wind >= 64 kt; no local exposure claim",
            initial_artifact_id=artifacts[0].id,
            initial_observation_id=initial_obs.id,
            artifacts=tuple(artifacts),
            tools=tools(),
        )
        episodes.append(episode)
        result = private[storm, target]
        source = reader.bind(REPO / result["source_path"], role="source_bytes")
        source_capture = load_json(prior / "data/NHC_OUTCOME_JOINS_PRIVATE.json")["source"][
            "captured_at"
        ]
        outcomes.append(
            Outcome(
                episode_id=episode.id,
                entity=storm,
                variable=episode.variable,
                unit=episode.unit,
                valid_at=target_time,
                value=result["outcome_value"],
                status="unresolved"
                if result["outcome_value"] is None
                else "retrospective_analysis",
                source=source if result["outcome_value"] is not None else None,
                captured_at=source_capture,
                reason=result["reason"] or "exact-time HURDAT2 same-agency retrospective analysis",
            )
        )

    hydro = REPO / "plans/v6_data_decision_20260911"
    files = [
        hydro / "captures_04/hefs-scoc1-ensemble-earlier.raw",
        hydro / "captures_03/hefs-scoc1-ensemble.raw",
    ]
    ensembles = []
    for path in files:
        (members,) = load_json(path)
        ids = [m["ensemble_member_index"] for m in members]
        if len(ids) != len(set(ids)) or len(ids) != 45:
            raise ValueError("unexpected or duplicate HEFS members")
        for member in members:
            if (member["location_id"], member["parameter_id"], member["units"], member["type"]) != (
                "SCOC1",
                "QINE",
                "CFS",
                "instantaneous",
            ):
                raise ValueError("HEFS station/parameter/support mismatch")
        receipt = json.loads(path.with_suffix(".json").read_text())
        ensembles.append((members, reader.bind(path, role="source_bytes"), receipt))
    metadata = load_json(hydro / "captures_02/nwps-scoc1-metadata.raw")
    if metadata["usgsId"] != "11477000":
        raise ValueError("NWPS/USGS mapping changed")
    obs_path = BASE / "acquisition/usgs-scoc1-continuous.json"
    obs_capture = json.loads((BASE / "acquisition/usgs-scoc1-receipt.json").read_text())
    obs_collection = load_json(obs_path)
    observations = {}
    for index, row in enumerate(obs_collection["features"]):
        prop = row["properties"]
        if (
            prop["monitoring_location_id"],
            prop["parameter_code"],
            prop["unit_of_measure"],
            prop["statistic_id"],
        ) != ("USGS-11477000", "00060", "ft^3/s", "00011"):
            raise ValueError("USGS station, flow unit, or instantaneous statistic mismatch")
        if prop["qualifier"] is not None or prop["approval_status"] not in (
            "Provisional",
            "Approved",
        ):
            continue
        key = (prop["time_series_id"], prop["time"])
        if key in observations and observations[key][0]["value"] != prop["value"]:
            raise ValueError("conflicting stable observation identity")
        observations[key] = (prop, reader.bind(obs_path, pointer=f"/features/{index}/properties"))
    for target in (
        "2026-09-10T18:00:00Z",
        "2026-09-10T21:00:00Z",
        "2026-09-11T00:00:00Z",
        "2026-09-11T03:00:00Z",
    ):
        target_time = parse_instant(target)
        artifacts = []
        for members, locator, receipt in ensembles:
            values = []
            for member in members:
                matched = [
                    event
                    for event in member["events"]
                    if parse_instant(event["valid_datetime"]) == target_time
                ]
                if len(matched) != 1 or matched[0]["flag"] != "0" or matched[0]["value"] is None:
                    raise ValueError("missing or ambiguous HEFS target/member")
                values.append(str(matched[0]["value"]))
            first = members[0]
            creation = parse_instant(first["creation_datetime"])
            issue = parse_instant(first["forecast_datetime"])
            artifacts.append(
                Artifact(
                    id="hefs-" + issue.strftime("%Y%m%dT%H%M"),
                    product_id="hefs-" + issue.isoformat(),
                    provider="NOAA/NWS HEFS",
                    entity="USGS-11477000",
                    variable="instantaneous_discharge",
                    unit="ft3/s",
                    kind="forecast",
                    issued_at=issue,
                    valid_at=target_time,
                    release_at=creation + timedelta(minutes=30),
                    captured_at=receipt["finished_at"],
                    values=tuple(values),
                    source=locator,
                    quality="45 equal-weight MEFP members; deterministic summary is ensemble mean",
                )
            )
        start = parse_instant("2026-09-09T18:00:00Z")
        deadline = target_time - timedelta(hours=2)
        for prop, locator in observations.values():
            valid = parse_instant(prop["time"])
            if valid + timedelta(minutes=30) > deadline:
                continue
            artifacts.append(
                Artifact(
                    id="usgs-" + valid.strftime("%Y%m%dT%H%M"),
                    product_id=prop["time_series_id"] + ":" + prop["time"],
                    provider="USGS",
                    entity="USGS-11477000",
                    variable="instantaneous_discharge",
                    unit="ft3/s",
                    kind="observation",
                    issued_at=None,
                    valid_at=valid,
                    release_at=valid + timedelta(minutes=30),
                    captured_at=obs_capture["captured_at"],
                    values=(prop["value"],),
                    source=locator,
                    quality=prop["approval_status"],
                )
            )
        initial_obs = max(
            (a for a in artifacts if a.kind == "observation" and a.release_at <= start),
            key=lambda a: a.valid_at,
        )
        episode = Episode(
            id=ident("SCOC1" + target),
            group="SCOC1-20260909-20260911",
            family="river_discharge",
            entity="USGS-11477000",
            variable="instantaneous_discharge",
            unit="ft3/s",
            start_at=start,
            target_at=target_time,
            deadline=deadline,
            checkpoints=(start + (deadline - start) / 2, deadline),
            threshold=None,
            threshold_meaning="no compatible official discharge flood threshold; continuous forecast only",
            initial_artifact_id=artifacts[0].id,
            initial_observation_id=initial_obs.id,
            artifacts=tuple(artifacts),
            tools=tools(),
        )
        episodes.append(episode)
        exact = [
            (prop, loc)
            for prop, loc in observations.values()
            if parse_instant(prop["time"]) == target_time
        ]
        if len(exact) > 1:
            raise ValueError("multiple outcome series at the same station/time")
        outcomes.append(
            Outcome(
                episode_id=episode.id,
                entity=episode.entity,
                variable=episode.variable,
                unit=episode.unit,
                valid_at=target_time,
                value=exact[0][0]["value"] if exact else None,
                status="provisional_observation" if exact else "unresolved",
                source=exact[0][1] if exact else None,
                captured_at=obs_capture["captured_at"],
                reason="exact-time USGS provisional value"
                if exact
                else "missing exact target sample",
            )
        )
    grouped = defaultdict(list)
    for episode in episodes:
        grouped[episode.group].append(episode)
    pilot = []
    for group, entries in sorted(grouped.items()):
        ordered = sorted(entries, key=lambda e: e.target_at)
        # The deterministic selection depends only on input coverage, never outcomes.
        indices = sorted({round(i * (len(ordered) - 1) / 3) for i in range(min(4, len(ordered)))})
        pilot.extend(ordered[index].id for index in indices)
    write_json(destination / "episodes.json", [e.model_dump(mode="json") for e in episodes])
    write_json(destination / "outcomes_private.json", [o.model_dump(mode="json") for o in outcomes])
    write_json(destination / "pilot_ids.json", pilot)
    write_json(destination / "SOURCE_BINDINGS.json", reader.bindings)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "episodes": len(episodes),
        "pilot_targets": len(pilot),
        "groups": {g: len(es) for g, es in grouped.items()},
        "excluded_by_input_coverage": excluded,
        "outcome_status": dict(Counter(o.status for o in outcomes)),
        "historical_availability_proven": False,
        "online_evaluation": False,
        "release_scenarios": {
            "NHC": "issue + 1h",
            "HEFS": "creation + 30min",
            "USGS": "observation + 30min",
        },
        "release_scenarios_are_assumptions": True,
        "hydro_members": 45,
        "usgs_records": len(observations),
        "hydro_flood_threshold_available": False,
        "heldout_targets": 0,
    }
    write_json(destination / "DATA_REPORT.json", report)
    print(
        json.dumps({k: v for k, v in report.items() if k != "excluded_by_input_coverage"}, indent=2)
    )


if __name__ == "__main__":
    main()
