"""Build a small, source-only v18 development qualification roster.

The v16 archive contains TAF CSV rows and declared archive issue timestamps,
but not prospective publication receipts.  We therefore bind a declared
replay lag and label it explicitly; this script does not create outcomes or
claim prospective availability.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from disastertrace.monitoring_v1.evidence_qualification_v18 import qualify_stream
from disastertrace.monitoring_v1.providers.aviation import day_time, visibility as parse_visibility
from disastertrace.monitoring_v1.targets import utc_us


STATIONS = ("KDEN", "KJFK", "KORD", "KSFO")
ALLOWED_MONTHS = ("202501", "202503")
HOLDOUT_START = datetime(2025, 2, 17, tzinfo=timezone.utc)
HOLDOUT_END = datetime(2025, 2, 24, tzinfo=timezone.utc)


def _dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _issue_from_product(product_id: str) -> datetime:
    return datetime.strptime(product_id[:12], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)


def _json_or_value(value: str) -> Any:
    if not value:
        return None
    try:
        return json.loads(value.replace("'", '"'))
    except (json.JSONDecodeError, TypeError):
        return value


def _body_path(data_root: Path, station: str, month: str, run_id: str) -> Path:
    path = data_root / "taf" / run_id / f"{station}_{month}.body"
    if not path.is_file():
        raise ValueError(f"Missing frozen body for {station}_{month} in declared run {run_id}")
    return path


def _conditional_window(raw: str, issue: datetime) -> tuple[datetime, datetime] | None:
    """Recover a conditional group's explicit day/hour window when present."""

    match = re.match(
        r"(?:(?:TEMPO|BECMG)\s+|PROB(?:30|40)(?:\s+TEMPO)?\s+)?(\d{4})/(\d{4})\b",
        raw.strip(),
    )
    if match is None:
        return None
    start = day_time(match.group(1), issue)
    end = day_time(match.group(2), start)
    return start, end


def _group_operator(row: dict[str, Any]) -> tuple[str, float | None]:
    """Retain prevailing/conditional TAF group semantics from archive rows."""

    raw = row.get("raw", "").strip()
    if raw.startswith("PROB30"):
        return "PROB30", 0.30
    if raw.startswith("PROB40"):
        return "PROB40", 0.40
    if raw.startswith("TEMPO") or row.get("is_tempo") == "True":
        return "TEMPO", None
    if raw.startswith("BECMG"):
        return "BECMG", None
    if raw.startswith("FM"):
        return "FM", None
    return "BASE", None


def _normalized_visibility(raw: str) -> dict[str, Any] | None:
    """Normalize SM/metric TAF visibility into the shared metre interval contract."""

    parsed = parse_visibility(raw)
    return None if parsed is None else parsed.to_dict()


def _load_products(data_root: Path, station: str, month: str, run_id: str) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    with _body_path(data_root, station, month, run_id).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("product_id") and row.get("fx_valid"):
                grouped[row["product_id"]].append(row)
    products = []
    for product_id, rows in grouped.items():
        rows.sort(key=lambda row: _dt(row["fx_valid"]))
        issue = _issue_from_product(product_id)
        periods = []
        for index, row in enumerate(rows):
            start = _dt(row["fx_valid"])
            conditional = _conditional_window(row.get("raw", ""), issue)
            if conditional is not None:
                start, end = conditional
            elif row.get("fx_valid_end"):
                end = _dt(row["fx_valid_end"])
            elif index + 1 < len(rows):
                end = _dt(rows[index + 1]["fx_valid"])
            else:
                end = start + timedelta(hours=1)
            if end <= start:
                continue
            operator, native_probability = _group_operator(row)
            periods.append(
                {
                    "valid_start": utc_us(start.isoformat()),
                    "valid_end": utc_us(end.isoformat()),
                    "operator": operator,
                    "native_probability": native_probability,
                    "conditional": operator not in {"BASE", "FM", "BECMG"},
                    "visibility_m": _normalized_visibility(row.get("raw", "")),
                    "presentwx": _json_or_value(row.get("presentwx", "")),
                    "skyc": _json_or_value(row.get("skyc", "")),
                    "skyl": _json_or_value(row.get("skyl", "")),
                    "wind": {
                        "sknt": row.get("sknt") or None,
                        "drct": row.get("drct") or None,
                        "gust": row.get("gust") or None,
                    },
                    "ftype": row.get("ftype"),
                    "is_amendment": row.get("is_amendment") == "True",
                    "source_row_is_tempo": row.get("is_tempo") == "True",
                }
            )
        if not periods:
            continue
        products.append(
            {
                "station": station,
                "source_id": product_id,
                "source_revision": product_id,
                "kind": "taf",
                "issued_at": utc_us(issue.isoformat()),
                "available_at": utc_us((issue + timedelta(seconds=120)).isoformat()),
                "valid_start": periods[0]["valid_start"],
                "valid_end": periods[-1]["valid_end"],
                "content": {"periods": periods},
                "availability_basis": "declared_archive_issue_plus_120s_replay_lag",
            }
        )
    return sorted(products, key=lambda row: (row["issued_at"], row["source_id"]))


def build_roster(data_root: Path, *, limit: int, run_id: str) -> dict[str, Any]:
    if "quarantine_holdout" in data_root.parts or "2025-02" in str(data_root):
        raise PermissionError("Holdout or protected month is not an allowed input")
    all_products = []
    for month in ALLOWED_MONTHS:
        for station in STATIONS:
            all_products.extend(_load_products(data_root, station, month, run_id))
    all_products.sort(key=lambda row: (row["source_id"], row["issued_at"]))
    by_day: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for product in all_products:
        start = datetime.fromtimestamp(product["valid_start"] / 1_000_000, tz=timezone.utc)
        if HOLDOUT_START <= start < HOLDOUT_END:
            continue
        issue = datetime.fromtimestamp(product["issued_at"] / 1_000_000, tz=timezone.utc)
        by_day[(product["station"], issue.strftime("%Y-%m-%d"))].append(product)

    candidates = []
    for (station_code, day), products in sorted(by_day.items()):
        target_start = target_end = None
        for left_index, left in enumerate(products):
            for right in products[left_index + 1 :]:
                overlap_start = max(left["valid_start"], right["valid_start"])
                overlap_end = min(left["valid_end"], right["valid_end"])
                if overlap_end - overlap_start >= 3_600_000_000:
                    target_start, target_end = overlap_start, overlap_start + 3_600_000_000
                    break
            if target_start is not None:
                break
        if target_start is None:
            continue
        stream = [
            product
            for product in products
            if product["valid_start"] <= target_start and product["valid_end"] >= target_end
        ][:8]
        if len(stream) < 2:
            continue
        stream.sort(key=lambda item: (item["issued_at"], item["available_at"] or 2**63, item["source_id"]))
        # This is a declared replay checkpoint after the first shared target
        # window, not proof of prospective public arrival.
        as_of = target_start + 1_800_000_000
        qualifications = [
            result.to_dict()
            for result in qualify_stream(
                stream,
                target_start=target_start,
                target_end=target_end,
                as_of=as_of,
            )
        ]
        candidates.append(
            {
                "episode_id": f"v18-dev-{station_code}-{day}",
                "station": station_code,
                "target_start": target_start,
                "target_end": target_end,
                "as_of": as_of,
                "source_count": len(stream),
                "source_ids": [item["source_id"] for item in stream],
                "availability_basis": "declared_archive_issue_plus_120s_replay_lag",
                "outcome_status": "NOT_BOUND_G1_SOURCE_ONLY",
                "qualifications": qualifications,
            }
        )
    # Keep the development roster balanced across the four stations instead
    # of letting the lexicographically first station consume the cap.
    by_station: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in candidates:
        by_station[episode["station"]].append(episode)
    episodes = []
    station_index = 0
    stations = [station for station in STATIONS if by_station[station]]
    while len(episodes) < limit and stations:
        station = stations[station_index % len(stations)]
        if by_station[station]:
            episodes.append(by_station[station].pop(0))
        else:
            stations.remove(station)
            continue
        station_index += 1
    status_counts: defaultdict[str, int] = defaultdict(int)
    for episode in episodes:
        for row in episode["qualifications"]:
            status_counts[row["status"]] += 1
    return {
        "schema": "disastertrace.v18.dev_qualification.v2",
        "scope": "source-only development qualification; no outcome or model run",
        "data_root": str(data_root),
        "stations": list(STATIONS),
        "months": list(ALLOWED_MONTHS),
        "taf_run_id": run_id,
        "episodes": episodes,
        "episode_count": len(episodes),
        "qualification_status_counts": dict(sorted(status_counts.items())),
        "raw_data_accessed": True,
        "outcomes_accessed": False,
        "holdout_accessed": False,
        "model_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--taf-run-id", default="20260920T091835Z_5f8988c0e49a")
    args = parser.parse_args()
    if args.limit < 12:
        parser.error("--limit must be at least 12 for the development roster")
    report = build_roster(args.data_root.resolve(), limit=args.limit, run_id=args.taf_run_id)
    if report["episode_count"] < 12:
        raise SystemExit(f"Only {report['episode_count']} qualifying episodes found; refusing partial roster")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "episodes": report["episode_count"], "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
