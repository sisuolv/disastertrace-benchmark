"""Build a small, source-only v18 development qualification roster.

The v16 archive contains TAF CSV rows and declared archive issue timestamps,
but not prospective publication receipts.  We therefore bind a declared
replay lag and label it explicitly; this script does not create outcomes or
claim prospective availability.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
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
# Fixed-future-target decision grid (PLAN_V18 section 1.1): one target is
# judged at T-60, T-40 and T-20 minutes before target_start.  Values are
# microseconds on the utc_us clock.  The order is part of the contract:
# earliest checkpoint first, so cutoffs strictly increase.
CHECKPOINT_OFFSETS_US = {"T-60": 3_600_000_000, "T-40": 2_400_000_000, "T-20": 1_200_000_000}


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
    # A declared readset is a real directory boundary, not a lexical prefix.
    # Do not follow a symlink from the allowed tree into an unregistered file.
    root = data_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError("TAF body resolves outside declared data root") from exc
    if path.is_symlink():
        raise PermissionError("TAF body symlinks are not allowed in a bounded readset")
    return path


def _read_verified_body(data_root: Path, station: str, month: str, run_id: str) -> tuple[bytes, dict[str, Any]]:
    """Return the exact bytes of an allowed TAF body plus its size/hash identity.

    Binding the readset to a recorded size and sha256 makes every downstream
    record traceable to the exact bytes that were actually read; it does not
    by itself prove archive completeness or label correctness, and there is
    no independent pre-existing receipt for this dev dataset to cross-check
    against, so this is hash *binding*, not hash *cross-validation*.
    """

    path = _body_path(data_root, station, month, run_id)
    raw = path.read_bytes()
    identity = {
        "canonical_path": str(path.resolve()),
        "size_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return raw, identity


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


# Text markers for an explicit cancellation bulletin.  Checked against the
# raw CSV text of every row in a product; real archives observed by this
# project so far contain zero matches (see the relation_status docstring
# below), so this branch is validated only by synthetic fixtures.
_CANCELLATION_MARKERS = ("CNL", "CNCL", "CANCEL")


def _has_cancellation_text(rows: list[dict[str, Any]]) -> bool:
    return any(
        marker in (row.get("raw") or "").upper()
        for row in rows
        for marker in _CANCELLATION_MARKERS
    )


def _periods_content_hash(periods: list[dict[str, Any]]) -> str:
    canonical = json.dumps(periods, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _classify_relation_status(
    *, rows: list[dict[str, Any]], periods: list[dict[str, Any]], previous_hash: str | None
) -> str:
    """Classify one product against the immediately preceding product at the
    same station (within one ``_load_products`` call, i.e. one station-month).

    Priority is cancellation > duplicate > revision > normal: an explicit
    cancellation marker is the most specific signal and wins even if the row
    also happens to carry ``is_amendment``; byte-identical content against the
    prior product is reported as a duplicate even if ``is_amendment`` is set
    (a same-content "amendment" is exactly the surprising case worth
    flagging, not something to silently relabel as a normal revision).
    ``"conflict"`` is deliberately never produced here -- it is a qualify_evidence-
    level signal for cross-source contradictions, not something this per-source
    loader is positioned to detect.
    """

    if _has_cancellation_text(rows):
        return "cancellation"
    current_hash = _periods_content_hash(periods)
    if previous_hash is not None and current_hash == previous_hash:
        return "duplicate"
    if any(row.get("is_amendment") == "True" for row in rows):
        return "revision"
    return "normal"


def _load_products(data_root: Path, station: str, month: str, run_id: str) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    raw, body_identity = _read_verified_body(data_root, station, month, run_id)
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        if row.get("product_id") and row.get("fx_valid"):
            grouped[row["product_id"]].append(row)
    products = []
    previous_content_hash: str | None = None
    for product_id, rows in sorted(grouped.items(), key=lambda item: _issue_from_product(item[0])):
        rows.sort(key=lambda row: _dt(row["fx_valid"]))
        issue = _issue_from_product(product_id)
        periods = []
        operators = [_group_operator(row)[0] for row in rows]
        for index, row in enumerate(rows):
            start = _dt(row["fx_valid"])
            conditional = _conditional_window(row.get("raw", ""), issue)
            if conditional is not None:
                start, end = conditional
            elif row.get("fx_valid_end"):
                end = _dt(row["fx_valid_end"])
            else:
                # A conditional row overlays the prevailing group; it must
                # not truncate that group's validity.  The next prevailing
                # (BASE/FM/BECMG) group establishes the boundary.
                next_prevailing = next(
                    (
                        _dt(rows[j]["fx_valid"])
                        for j in range(index + 1, len(rows))
                        if operators[j] in {"BASE", "FM", "BECMG"}
                    ),
                    None,
                )
                if next_prevailing is not None:
                    end = next_prevailing
                elif index + 1 < len(rows) and operators[index] in {"TEMPO", "PROB30", "PROB40"}:
                    # An unusual conditional row without an explicit window
                    # remains bounded by the next row, never by an invented
                    # prevailing fact.
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
        relation_status = _classify_relation_status(
            rows=rows, periods=periods, previous_hash=previous_content_hash
        )
        previous_content_hash = _periods_content_hash(periods)
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
                "body_identity": body_identity,
                "relation_status": relation_status,
            }
        )
    return sorted(products, key=lambda row: (row["issued_at"], row["source_id"]))


def _checkpoint_cutoffs(
    target_start: int, offsets: dict[str, int] = CHECKPOINT_OFFSETS_US
) -> tuple[list[tuple[str, int]], list[dict[str, Any]]]:
    """Resolve each decision checkpoint's own cutoff for one future target.

    Reuses the cutoff rule of ``targets.Opportunity`` (``future_physical``)
    and ``agent_view_v18.public_checkpoint``: a cutoff is an integer strictly
    before ``target_start``.  A checkpoint that fails the rule, or whose
    cutoff falls before the Unix epoch, is returned in the second list with
    its reason.  It is never clamped or shifted onto a valid instant.
    """

    if not isinstance(target_start, int) or isinstance(target_start, bool):
        raise ValueError("target_start must be an integer timestamp")
    values = list(offsets.values())
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        raise ValueError("Checkpoint offsets must be integer microseconds")
    if any(later >= earlier for earlier, later in zip(values, values[1:])):
        raise ValueError("Checkpoint offsets must strictly decrease so cutoffs strictly increase")
    valid: list[tuple[str, int]] = []
    excluded: list[dict[str, Any]] = []
    for checkpoint_id, offset in offsets.items():
        cutoff = target_start - offset
        if cutoff >= target_start:
            reason = "cutoff does not strictly precede target_start"
        elif cutoff < 0:
            reason = "cutoff precedes the Unix epoch (negative utc_us)"
        else:
            valid.append((checkpoint_id, cutoff))
            continue
        excluded.append({"checkpoint_id": checkpoint_id, "as_of": cutoff, "offset_us": offset, "reason": reason})
    return valid, excluded


def _qualify_checkpoints(
    stream: list[dict[str, Any]],
    *,
    target_start: int,
    target_end: int,
    offsets: dict[str, int] = CHECKPOINT_OFFSETS_US,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Qualify one arrival stream separately at each checkpoint cutoff.

    Every checkpoint gets its own ``qualify_stream`` call.  Its rows therefore
    say what was legitimately visible by that cutoff: a record that arrives
    later is ``NOT_YET_AVAILABLE`` there and never advances that checkpoint's
    comparison state.  The whole stream stays in each checkpoint's list for
    audit; the public agent view drops the unavailable rows per cutoff.
    Returns ``(checkpoints, excluded_checkpoints)``.
    """

    valid, excluded = _checkpoint_cutoffs(target_start, offsets)
    checkpoints = [
        {
            "checkpoint_id": checkpoint_id,
            "as_of": cutoff,
            "qualifications": [
                result.to_dict()
                for result in qualify_stream(
                    stream,
                    target_start=target_start,
                    target_end=target_end,
                    as_of=cutoff,
                )
            ],
        }
        for checkpoint_id, cutoff in valid
    ]
    return checkpoints, excluded


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
    excluded_episodes: list[dict[str, Any]] = []
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
        # One fixed future target is judged at T-60/T-40/T-20, and each
        # checkpoint is qualified against its own cutoff.  There is
        # deliberately no episode-level as_of: one decision time shared by
        # every checkpoint is exactly what this grid replaces, and a single
        # value there would invite readers to reuse it for every checkpoint.
        # Consumers must read checkpoint["as_of"].
        checkpoints, excluded_checkpoints = _qualify_checkpoints(
            stream, target_start=target_start, target_end=target_end
        )
        episode_id = f"v18-dev-{station_code}-{day}"
        if excluded_checkpoints:
            # The roster only admits the complete checkpoint grid; an episode
            # missing a checkpoint is recorded with the reasons, not padded.
            excluded_episodes.append(
                {
                    "episode_id": episode_id,
                    "station": station_code,
                    "target_start": target_start,
                    "target_end": target_end,
                    "excluded_checkpoints": excluded_checkpoints,
                }
            )
            continue
        candidates.append(
            {
                "episode_id": episode_id,
                "station": station_code,
                "target_start": target_start,
                "target_end": target_end,
                "source_count": len(stream),
                "source_ids": [item["source_id"] for item in stream],
                "availability_basis": "declared_archive_issue_plus_120s_replay_lag",
                "outcome_status": "NOT_BOUND_G1_SOURCE_ONLY",
                "checkpoints": checkpoints,
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
    # Status counts are kept per checkpoint rather than as one flat total.
    # Every checkpoint qualifies the same evidence rows against its own
    # cutoff, so a row can be NOT_YET_AVAILABLE at T-60 and a content change
    # at T-20.  A flat sum would count each row three times and mix three
    # visibility states.  Each per-checkpoint table sums to the roster's
    # evidence-row count (the sum of source_count).
    status_counts: dict[str, defaultdict[str, int]] = {
        checkpoint_id: defaultdict(int) for checkpoint_id in CHECKPOINT_OFFSETS_US
    }
    for episode in episodes:
        for checkpoint in episode["checkpoints"]:
            for row in checkpoint["qualifications"]:
                status_counts[checkpoint["checkpoint_id"]][row["status"]] += 1
    return {
        "schema": "disastertrace.v18.dev_qualification.v3",
        "scope": "source-only development qualification; no outcome or model run",
        "data_root": str(data_root),
        "stations": list(STATIONS),
        "months": list(ALLOWED_MONTHS),
        "taf_run_id": run_id,
        "checkpoint_offsets_us": dict(CHECKPOINT_OFFSETS_US),
        "episodes": episodes,
        "episode_count": len(episodes),
        "checkpoint_count": sum(len(episode["checkpoints"]) for episode in episodes),
        "qualification_status_counts_by_checkpoint": {
            checkpoint_id: dict(sorted(counts.items())) for checkpoint_id, counts in status_counts.items()
        },
        "excluded_episodes": excluded_episodes,
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
