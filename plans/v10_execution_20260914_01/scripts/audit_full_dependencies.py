"""Record-level split audit with separate raw-container and learned-bank ancestry."""

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import typed_target
from disastertrace.monitoring_v1.process_split import process_components
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash, utc_us


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out, old = args.out.absolute(), args.historical.absolute()
    out.mkdir(exist_ok=False)
    original = read(old / "reports/process_manifest_02/DATA_PROCESS_MANIFEST.json")[
        "rows"
    ]
    intervals = read(old / "reports/process_manifest_02/SPLITS.json")["intervals"]
    by_dataset = defaultdict(list)
    for row in original:
        by_dataset[row["dataset"]].append(row)
    uses, envelopes, edges, rows, verified = (
        defaultdict(dict),
        defaultdict(dict),
        [],
        [],
        {},
    )
    bank_freeze, actual_role_ids = {}, defaultdict(set)
    for region in ("bay", "new_york", "chicago", "denver"):
        folder = old / "reports/regional_baselines_01" / region
        bank_freeze[region] = {
            n: digest(folder / n)
            for n in (
                "BANK.json",
                "BANK_RAW.json",
                "FIT_IDS.json",
                "CALIBRATION_IDS.json",
            )
        }
        actual_role_ids["fit"].update(read(folder / "FIT_IDS.json"))
        actual_role_ids["calibration"].update(read(folder / "CALIBRATION_IDS.json"))

    def use(kind, value, row):
        roles = uses[(kind, value)]
        roles.setdefault(row["role"], row["opportunity_id"])

    def envelope(value, row):
        envelopes[value].setdefault(row["role"], row["opportunity_id"])

    for dataset_name, subset in by_dataset.items():
        dataset = Path(dataset_name)
        sources = read(dataset / "SOURCES.json")
        source_lines = {}
        for sid, source in sources.items():
            for field, sha_field in (
                ("path", "sha256"),
                ("receipt_path", "receipt_sha256"),
            ):
                p, sha = Path(source[field]), source[sha_field]
                if str(p) not in verified:
                    if digest(p) != sha:
                        raise ValueError("Original native file/receipt hash mismatch")
                    verified[str(p)] = sha
            if sid.startswith("metar"):
                source_lines[sid] = Path(source["path"]).read_text().splitlines()
        targets = {r["target_id"]: r for r in read(dataset / "public/TARGETS.json")}
        catalog = {
            r["query_id"]: r for r in read(dataset / "public/QUERY_CATALOG.json")
        }
        results = {
            r["query_id"]: r for r in read(dataset / "environment/QUERY_RESULTS.json")
        }
        outcomes = {r["target_id"]: r for r in read(dataset / "private/OUTCOMES.json")}
        decoded = {
            (r["source_id"], r["source_line"]): r
            for r in read(dataset / "private/DECODED_REPORTS.json")
        }
        candidates = defaultdict(list)
        for r in read(dataset / "environment/BASELINE_CANDIDATES.json"):
            candidates[r["opportunity_id"]].append(r)
        for original_row in subset:
            row = dict(original_row)
            oid, tid = row["opportunity_id"], row["target_id"]
            target = targets[tid]
            native = [r for r in candidates[oid] if r["available_at"] <= row["cutoff"]]
            assets = ["target:" + typed_target(target).contract_hash]
            spans = [
                {
                    "station": target["entity"],
                    "start": target["physical_start"],
                    "end": target["physical_end"],
                    "role": "outcome",
                }
            ]
            used_source_ids = set()
            for candidate in native:
                source = sources[candidate["source_id"]]
                assets.append("taf:" + source["sha256"])
                used_source_ids.add(candidate["source_id"])
            reports = []
            for qid in row["query_ids"]:
                query, result = catalog[qid], results[qid]
                assets.extend(
                    ["query:" + qid, "query_result:" + canonical_hash(result)]
                )
                spans.append(
                    {
                        "station": query["station"],
                        "start": query["slot_start"],
                        "end": query["slot_end"],
                        "role": "input",
                    }
                )
                reports.extend((r, "input") for r in result.get("reports", []))
            for ref in outcomes[tid]["references"]:
                reports.append(
                    (decoded[ref["source_id"], ref["source_line"]], "outcome")
                )
            for report, role in reports:
                sid, line = report["source_id"], report["source_line"]
                values = next(csv.reader([source_lines[sid][line - 1]]))
                if report["raw"] not in values:
                    raise ValueError(
                        "Decoded report does not bind the exact original source line"
                    )
                used_source_ids.add(sid)
                raw_sha = hashlib.sha256(report["raw"].encode()).hexdigest()
                identity = canonical_hash(
                    [report["station"], report["observation_time"], raw_sha]
                )
                assets.extend(
                    ["native_report:" + identity, "native_report_text:" + raw_sha]
                )
                edges.append(
                    {
                        "opportunity_id": oid,
                        "use": role,
                        "record_id": identity,
                        "native_raw_sha256": raw_sha,
                        "source_sha256": sources[sid]["sha256"],
                        "source_line": line,
                        "station": report["station"],
                        "observed_at": report["observation_time"],
                    }
                )
            for sid in used_source_ids:
                envelope(sources[sid]["sha256"], row)
            for asset in set(assets):
                kind, value = asset.split(":", 1)
                use(kind, value, row)
            first = min([row["footprint_start"]] + [s["start"] for s in spans])
            last = max([row["footprint_end"]] + [s["end"] for s in spans])
            row.update(
                footprint_start=first,
                footprint_end=last,
                native_versions=sorted(set(assets)),
                station_windows=spans,
            )
            rows.append(row)
        print(
            json.dumps(
                {
                    "dataset": dataset.name,
                    "region": subset[0]["region"],
                    "completed_rows": len(rows),
                }
            ),
            flush=True,
        )
    conflicts = []
    admitted_roles = {"fit", "calibration", "development_evaluation"}
    for (kind, asset), roles in uses.items():
        used = {k: v for k, v in roles.items() if k in admitted_roles}
        if len(used) > 1:
            conflicts.append({"kind": kind, "asset": asset, "role_witnesses": used})
    container_crossings = [
        {
            "source_sha256": k,
            "role_witnesses": {r: v for r, v in uses.items() if r in admitted_roles},
        }
        for k, uses in envelopes.items()
        if len(admitted_roles & set(uses)) > 1
    ]
    # Time overlap is tested across roles at a station, including neighbor input versus target outcome.
    windows = defaultdict(list)
    for row in rows:
        if row["role"] not in admitted_roles:
            continue
        for span in row["station_windows"]:
            windows[span["station"]].append(
                (
                    span["start"],
                    span["end"],
                    row["role"],
                    row["opportunity_id"],
                    span["role"],
                )
            )
    window_conflicts = []
    for station, spans in windows.items():
        ends = {}
        for start, end, role, oid, use_kind in sorted(spans):
            for other, (stop, previous) in ends.items():
                if other != role and start < stop:
                    window_conflicts.append(
                        {
                            "station": station,
                            "left": previous,
                            "right": oid,
                            "roles": [other, role],
                            "input_or_outcome": use_kind,
                        }
                    )
            if role not in ends or end > ends[role][0]:
                ends[role] = (end, oid)
    boundary_errors = [
        r["opportunity_id"]
        for r in rows
        if r["role"] in intervals
        and not (
            intervals[r["role"]][0]
            <= r["footprint_start"]
            < r["footprint_end"]
            <= intervals[r["role"]][1]
        )
    ]
    row_by_id = {r["opportunity_id"]: r for r in rows}
    id_errors = [
        {"role": role, "id": oid}
        for role, ids in actual_role_ids.items()
        for oid in ids
        if oid not in row_by_id or row_by_id[oid]["role"] != role
    ]
    if actual_role_ids["fit"] & actual_role_ids["calibration"]:
        raise ValueError("Actual bank fit/calibration IDs overlap")
    confirmation_start, confirmation_end = (
        utc_us("2025-02-17T00:00:00Z"),
        utc_us("2025-02-24T00:00:00Z"),
    )
    confirmation_overlap = [
        r["opportunity_id"]
        for r in rows
        if r["footprint_start"] < confirmation_end
        and r["footprint_end"] > confirmation_start
    ]
    sensitivity = {}
    evaluation = [r for r in rows if r["role"] == "development_evaluation"]
    for hours in (0, 24, 72, 168):
        groups = process_components(evaluation, gap_us=hours * 3600_000_000)
        sensitivity[str(hours)] = {
            "global_blocks": len(set(groups.values())),
            "regional_blocks": {
                region: len(
                    {
                        groups[r["opportunity_id"]]
                        for r in evaluation
                        if r["region"] == region
                    }
                )
                for region in ("bay", "new_york", "chicago", "denver")
            },
        }
    weeks = Counter(
        (
            r["region"],
            dt.datetime.fromtimestamp(
                r["target_start"] / 1e6, dt.timezone.utc
            ).strftime("%G-W%V"),
        )
        for r in evaluation
    )
    with (out / "RECORD_DEPENDENCIES.jsonl").open("x") as stream:
        for row in edges:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    with (out / "COMPLETE_FOOTPRINTS.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    publish(
        out / "BANK_FREEZE.json",
        {
            "banks": bank_freeze,
            "scripts": {
                str(p): digest(p)
                for p in [
                    Path(__file__),
                    old / "scripts/fit_regional_baselines.py",
                    old / "scripts/build_process_manifest.py",
                ]
            },
            "post_result_bank_selection": False,
            "fixed_learned_banks_are_declared_ancestry_not_raw_observation_overlap": True,
        },
    )
    report = {
        "rows": len(rows),
        "record_edges": len(edges),
        "verified_source_and_receipt_files": len(verified),
        "cross_role_record_or_query_overlaps": conflicts,
        "cross_role_station_window_overlaps": window_conflicts,
        "full_boundary_violations": boundary_errors,
        "actual_bank_role_violations": id_errors,
        "raw_container_crossings": container_crossings,
        "raw_container_rule": "Shared archive files are not shared visible records. Exact source lines verified; policy exposes filtered records only.",
        "confirmation_overlap": confirmation_overlap,
        "confirmation_payload_read": False,
        "group_sensitivity_hours": sensitivity,
        "region_weeks": [
            {"region": r, "week": w, "opportunities": n}
            for (r, w), n in sorted(weeks.items())
        ],
        "independent_weather_process_count_established": False,
        "passed": not (
            conflicts
            or window_conflicts
            or boundary_errors
            or id_errors
            or confirmation_overlap
        ),
    }
    publish(out / "SPLIT_NONLEAKAGE_AUDIT.json", report)
    publish(out / "SOURCE_HASHES.json", verified)
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                in {
                    "passed",
                    "rows",
                    "record_edges",
                    "verified_source_and_receipt_files",
                    "group_sensitivity_hours",
                }
            }
        ),
        flush=True,
    )
    if not report["passed"]:
        raise ValueError("Split dependency audit found retained counterexamples")


if __name__ == "__main__":
    main()
