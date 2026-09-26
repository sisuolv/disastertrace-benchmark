#!/usr/bin/env python3
"""Build the v23 J1b source-only roster from the approved D1 read set.

The reader is intentionally fail-closed.  It opens only the eight DL3R TAF
body/receipt pairs and eight ASOS body/receipt pairs approved for this run.
It never emits an outcome and never calls the outcome resolver.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_v1.providers.versions import current_taf
from disastertrace.revision_v1.access_policy import AccessPolicy
from disastertrace.revision_v1.episode_compiler import (
    compile_afos_taf_stream,
    compile_asos_csv_to_observations,
)
from disastertrace.revision_v1.ledger import compile_ledger
from disastertrace.revision_v1.outcome_wiring import select_routine_observations
from disastertrace.revision_v1.v23_contracts import (
    LEAD_LABELS,
    METAR_AVAILABLE_DELAY_S,
    MONTHS,
    STATIONS,
    checkpoint_rows,
    month_hour_starts,
    metar_available_at,
)
from disastertrace.revision_v1.v23_source_features import (
    latest_visible_metar,
    metar_age_hours,
    metar_event_flag,
    merge_parse_stats,
    preflight_git_contract,
    recent_visible_metars,
    require_v23_grid_contract,
    source_gap_month_end,
    taf_content_features,
    taf_event_flag,
    validate_source_only_row,
    history_incomplete,
)

DATA_ROOT = Path("/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16").resolve()
RUN_ID = "20260926T-v23-j1b"
TAF_RUN = DATA_ROOT / "taf/20260920T134949Z_1bbe63aedc00_dl3rbulk"
ASOS_RUNS = {
    ("KDEN", "2025-01"): DATA_ROOT / "asos/KDEN/2025-01/20260920T084934Z_251f3d12cb7e",
    ("KDEN", "2025-03"): DATA_ROOT / "asos/KDEN/2025-03/20260920T085005Z_885fa54c37f7",
    ("KJFK", "2025-01"): DATA_ROOT / "asos/KJFK/2025-01/20260920T085619Z_edc2267acd5b",
    ("KJFK", "2025-03"): DATA_ROOT / "asos/KJFK/2025-03/20260920T085728Z_5d10062d959f",
    ("KORD", "2025-01"): DATA_ROOT / "asos/KORD/2025-01/20260920T090910Z_555a092f84e7",
    ("KORD", "2025-03"): DATA_ROOT / "asos/KORD/2025-03/20260920T090928Z_71b6595902e4",
    ("KSFO", "2025-01"): DATA_ROOT / "asos/KSFO/2025-01/20260920T084338Z_6e47285e6664",
    ("KSFO", "2025-03"): DATA_ROOT / "asos/KSFO/2025-03/20260920T084400Z_72fe1e4f9787",
}
TAF_NAMES = {(station, month): f"{station}_{month.replace('-', '')}" for station in STATIONS for month in MONTHS}


class D1Reader:
    def __init__(self, output: Path):
        self.output = output
        self.read_log = output / "READ_LOG.jsonl"
        self.read_log.parent.mkdir(parents=True, exist_ok=True)
        # The exact allowlist is stronger than the broad holdout policy.  The
        # known holdout interval is retained as a second fail-closed check.
        self.policy = AccessPolicy(
            allowed_root=DATA_ROOT,
            holdout_start_us=_us("2025-02-17T00:00:00Z"),
            holdout_end_us=_us("2025-02-24T00:00:00Z"),
            allowed_year_months=frozenset(MONTHS),
        )
        self.body_paths = set()
        self.receipt_paths = set()
        for station in STATIONS:
            for month in MONTHS:
                self.body_paths.add(TAF_RUN / f"{station}_{month.replace('-', '')}.body")
                self.receipt_paths.add(TAF_RUN / f"{station}_{month.replace('-', '')}.json")
                directory = ASOS_RUNS[(station, month)]
                prefix = {"KDEN": "den", "KJFK": "jfk", "KORD": "ord", "KSFO": "sfo"}[station]
                self.body_paths.add(directory / f"asos-{prefix}-{month.replace('-', '')}.body")
                self.receipt_paths.add(directory / f"asos-{prefix}-{month.replace('-', '')}.json")

    def _check(self, path: Path, kind: str) -> Path:
        path = Path(path)
        allow = self.body_paths if kind == "body" else self.receipt_paths
        if path not in allow:
            raise PermissionError(f"D1 path not in exact {kind} allowlist: {path}")
        if not path.is_file() or os.path.realpath(path) != os.path.abspath(path):
            raise PermissionError(f"D1 path missing or symlinked: {path}")
        month = next((m for m in MONTHS if m.replace('-', '') in path.name or m in path.parts), None)
        self.policy.assert_allowed(path, year_month=month)
        return path

    def read_bytes(self, path: Path, *, kind: str, purpose: str) -> bytes:
        path = self._check(path, kind)
        data = path.read_bytes()
        record = {
            "task": "J1b",
            "run_id": RUN_ID,
            "path": str(path),
            "kind": kind,
            "bytes": len(data),
            "purpose": purpose,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        with self.read_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        return data


def _us(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1_000_000)


def _json_hash(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _receipt_check(body: bytes, receipt: dict, path: Path) -> dict:
    expected = receipt.get("sha256")
    actual = hashlib.sha256(body).hexdigest()
    if expected and expected != actual:
        raise RuntimeError(f"receipt hash mismatch for approved file {path}")
    return {"path": str(path), "receipt_sha256": expected, "body_sha256": actual, "match": expected in (None, actual)}


def _interval_dict(interval):
    return None if interval is None else interval.to_dict()


def _day_from_us(timestamp_us: int) -> int:
    return datetime.fromtimestamp(timestamp_us / 1_000_000, tz=timezone.utc).day


def _read_inputs(reader: D1Reader):
    taf = {}
    asos = {}
    integrity = []
    parse_stats = {}
    for station in STATIONS:
        for month in MONTHS:
            name = TAF_NAMES[(station, month)]
            body_path = TAF_RUN / f"{name}.body"
            receipt_path = TAF_RUN / f"{name}.json"
            body = reader.read_bytes(body_path, kind="body", purpose="DL3R TAF source parsing")
            receipt = json.loads(reader.read_bytes(receipt_path, kind="receipt", purpose="DL3R receipt verification"))
            integrity.append(_receipt_check(body, receipt, body_path))
            products, skipped, parsed = compile_afos_taf_stream(
                body.decode("utf-8"), station=station, reference_month=month, return_parsed=True
            )
            # A malformed native frame is a classified source gap.  It remains
            # in the denominator and is never repaired, dropped, or replaced
            # from another product.  Unknown exception categories would still
            # fail closed below.
            for item in skipped:
                if item.get("error") != "Change group outside native validity":
                    raise RuntimeError(
                        f"unclassified DL3R parse frame for {station} {month}: {item.get('error')}"
                    )
            ledger = compile_ledger(products)
            taf[(station, month)] = {"packages": products, "parsed": parsed}
            merge_parse_stats(parse_stats, (station, month), {
                "taf_products": len(products),
                "taf_ledger_entries": len(ledger),
                "taf_skipped": len(skipped),
                "taf_skipped_frames": [item.get("frame_index") for item in skipped],
                "taf_skipped_errors": sorted({item["error"] for item in skipped}),
            })
    for (station, month), directory in ASOS_RUNS.items():
        prefix = {"KDEN": "den", "KJFK": "jfk", "KORD": "ord", "KSFO": "sfo"}[station]
        body_path = directory / f"asos-{prefix}-{month.replace('-', '')}.body"
        receipt_path = directory / f"asos-{prefix}-{month.replace('-', '')}.json"
        body = reader.read_bytes(body_path, kind="body", purpose="ASOS source feature parsing")
        receipt = json.loads(reader.read_bytes(receipt_path, kind="receipt", purpose="ASOS receipt verification"))
        integrity.append(_receipt_check(body, receipt, body_path))
        observations, skipped = compile_asos_csv_to_observations(body.decode("utf-8"), station=station)
        routine, meta = select_routine_observations(observations, station=station)
        # Keep all routine and SPECI reports for source features.  Outcome
        # settlement later uses the frozen routine selector separately.
        asos[(station, month)] = {"all": observations, "routine": routine, "meta": meta}
        merge_parse_stats(parse_stats, (station, month), {
            "asos_observations": len(observations),
            "asos_routine_observations": len(routine),
            "asos_skipped": len(skipped),
            "asos_modal_minute": meta["modal_minute"],
        })
    return taf, asos, integrity, parse_stats


def build_roster(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    # This check must happen before constructing or opening any approved body.
    runtime_commit = preflight_git_contract(
        os.environ.get("GIT_CONFIG_GLOBAL"),
        repo_root=Path(__file__).parents[2],
        script_path=Path(__file__).resolve(),
    )
    reader = D1Reader(output)
    taf, asos, integrity, parse_stats = _read_inputs(reader)
    targets = month_hour_starts()
    rows = []
    layer_counts = Counter()
    gaps = Counter()
    d_known = d_unknown = 0
    d_by_stratum = Counter()
    sensitivity = {
        "exclude_history_incomplete": {"total": 0, "known": 0, "unknown": 0},
        "exclude_month_end_stale": {"total": 0, "known": 0, "unknown": 0},
    }
    for target in targets:
        station, month = target["station"], target["month"]
        taf_input = taf[(station, month)]
        products = taf_input["packages"]
        parsed_by_id = {record["source_id"]: record for record in taf_input["parsed"]}
        asos_input = asos[(station, month)]
        observations = asos_input["all"]
        # A single full ledger is used only for visible provenance counts. The
        # current_taf selector itself applies the cutoff and 120-second lag.
        ledger = compile_ledger(products)
        for checkpoint in checkpoint_rows(target):
            cutoff = checkpoint["cutoff_us"]
            grid_contract = require_v23_grid_contract(
                expected_methods=("TAF", "METAR", "LLM"),
                cutoff=cutoff,
                available_at=metar_available_at,
            )
            current = current_taf(products, station=station, cutoff=cutoff,
                                   start=target["physical_start_us"], end=target["physical_end_us"])
            visible_ledger = [entry for entry in ledger if entry["available_at"] <= cutoff]
            selected_record = parsed_by_id.get(current.get("selected_id"))
            if current.get("status") == "active" and selected_record is not None:
                taf_features = taf_content_features(
                    selected_record["product"], target["physical_start_us"], target["physical_end_us"]
                )
            else:
                taf_features = {"coverage_status": current.get("status", "no_product"), "event_flag": None}
            taf_flag = taf_features.get("event_flag")
            latest = latest_visible_metar(observations, cutoff, available_at=metar_available_at)
            metar_flag = metar_event_flag(_interval_dict(latest.visibility) if latest is not None else None)
            month_end = source_gap_month_end(month, _day_from_us(target["physical_start_us"]))
            target_history_incomplete = history_incomplete(target["physical_start_us"], month)
            age_hours = metar_age_hours(
                observation_us=latest.observation_time if latest is not None else None,
                cutoff_us=cutoff,
            )
            month_end_stale = month_end and (age_hours is None or age_hours > 1.0)
            flags_known = taf_flag is not None and metar_flag is not None
            if flags_known:
                d_known += int(taf_flag != metar_flag)
                d_by_stratum[(station, checkpoint["checkpoint_id"])] += int(taf_flag != metar_flag)
            else:
                d_unknown += 1
            if taf_flag is None:
                gaps["taf_event_unknown"] += 1
            if metar_flag is None:
                gaps["metar_event_unknown"] += 1
            if month_end_stale:
                gaps["month_end_stale"] += 1
            if month_end:
                gaps["month_end_rows"] += 1
            if target["history_incomplete"]:
                gaps["history_incomplete"] += 1
            layer_counts["archive_candidate"] += len(products)
            layer_counts["legal_history_visible"] += len(visible_ledger)
            layer_counts["current_authority"] += int(selected_record is not None and current.get("status") == "active")
            layer_counts["product_family"] += len({p.get("product_series", "default") for p in products if p["issued_at"] + 120_000_000 <= cutoff})
            for label, exclude in (
                ("exclude_history_incomplete", target_history_incomplete),
                ("exclude_month_end_stale", month_end_stale),
            ):
                if not exclude:
                    bucket = sensitivity[label]
                    bucket["total"] += 1
                    bucket["known"] += int(flags_known and taf_flag != metar_flag)
                    bucket["unknown"] += int(not flags_known)
            row = {
                **target,
                **checkpoint,
                "history_incomplete": target_history_incomplete,
                "source_gap_month_end": month_end,
                "metar_stale_hours": age_hours,
                "metar_month_end_stale": month_end_stale,
                "source_only": True,
                "taf": {
                    "status": current.get("status"), "source_ids": current.get("source_ids", []),
                    "selected_id": current.get("selected_id"), "issued_at": current.get("issued_at"),
                    "ledger_visible_count": len(visible_ledger),
                    "raw": selected_record["raw"] if selected_record is not None else None,
                    "features": taf_features,
                    "event_flag": taf_flag,
                },
                "metar": None if latest is None else {
                    "observation_time_us": latest.observation_time,
                    "available_at_us": metar_available_at(latest.observation_time),
                    "visibility": _interval_dict(latest.visibility),
                    "report_type": latest.report_type,
                    "raw": latest.raw,
                    "event_flag": metar_flag,
                },
                "recent_metars": [
                    {
                        "observation_time_us": obs.observation_time,
                        "available_at_us": metar_available_at(obs.observation_time),
                        "visibility": _interval_dict(obs.visibility),
                        "report_type": obs.report_type,
                        "raw": obs.raw,
                    }
                    for obs in recent_visible_metars(observations, cutoff, available_at=metar_available_at)
                ],
                "grid_contract": grid_contract,
                "features_do_not_include_outcome": True,
            }
            # Deliberately no `outcome`, `value`, or evaluator label key.
            validate_source_only_row(row)
            rows.append(row)
    roster = output / "SOURCE_ONLY_ROSTER.jsonl"
    with roster.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    with (output / "SOURCE_LAYERS.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["layer", "count"])
        writer.writerows(sorted(layer_counts.items()))
    total = len(rows)
    coverage = {
        "targets_expected": len(targets), "targets_actual": len({row["target_id"] for row in rows}),
        "checkpoints_expected": 23808, "checkpoints_actual": total,
        "gaps": dict(sorted(gaps.items())), "parse_stats": {f"{s}/{m}": v for (s, m), v in sorted(parse_stats.items())},
        "integrity": integrity,
    }
    (output / "COVERAGE_AND_GAPS.json").write_text(json.dumps(coverage, indent=2, ensure_ascii=False) + "\n")
    distinguish = {
        "d_known_count": d_known, "d_unknown_count": d_unknown,
        "d_min": d_known / total if total else None,
        "d_max": (d_known + d_unknown) / total if total else None,
        "by_station_checkpoint": {f"{s}/{c}": n for (s, c), n in sorted(d_by_stratum.items())},
        "sensitivity": {
            name: {
                **bucket,
                "d_min": bucket["known"] / bucket["total"] if bucket["total"] else None,
                "d_max": (bucket["known"] + bucket["unknown"]) / bucket["total"] if bucket["total"] else None,
            }
            for name, bucket in sensitivity.items()
        },
        "definition": "TAF target-window visibility event flag versus latest visible METAR or SPECI event flag; unknown when either content flag is unknown; METAR age is recorded separately",
        "threshold_m": 5000.0,
        "metar_available_delay_s": METAR_AVAILABLE_DELAY_S,
        "denominator": total,
        "outcome_bound": False, "development_only": True,
    }
    (output / "SOURCE_DISTINGUISHABILITY.json").write_text(json.dumps(distinguish, indent=2, ensure_ascii=False) + "\n")
    (output / "PRE_Y_GATE.json").write_text(json.dumps({
        "status": "STOP_NO_Y1_RESOURCE_PRIORITY" if distinguish["d_max"] < 0.02 else "QUALIFICATION_CONTINUES",
        "q_min": 0.02, "d_min": distinguish["d_min"], "d_max": distinguish["d_max"],
        "y1_read_allowed_after_this_artifact": distinguish["d_max"] >= 0.02,
        "reason": "conservative distinguishability upper bound below q_min" if distinguish["d_max"] < 0.02 else "d_max reaches q_min; source seal required before Y1",
    }, indent=2) + "\n")
    # Content seal excludes timestamps and absolute output paths; it binds all
    # source-derived artifacts, contracts, readset paths and code commit.
    seal_inputs = {
        "pipeline_id": "revision_v1_afos_ledger",
        "runtime_code_commit": runtime_commit,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "readset_paths": sorted(str(p) for p in reader.body_paths | reader.receipt_paths),
        "contracts": {"stations": STATIONS, "months": MONTHS, "leads": LEAD_LABELS, "metar_delay_s": METAR_AVAILABLE_DELAY_S},
        "artifact_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in ("SOURCE_ONLY_ROSTER.jsonl", "SOURCE_LAYERS.csv", "COVERAGE_AND_GAPS.json", "SOURCE_DISTINGUISHABILITY.json", "PRE_Y_GATE.json")},
    }
    seal_inputs["content_hash"] = _json_hash(seal_inputs)
    (output / "SOURCE_SEAL.json").write_text(json.dumps(seal_inputs, indent=2, ensure_ascii=False) + "\n")
    return distinguish


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_roster(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
