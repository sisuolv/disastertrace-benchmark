"""Bind bounded development ASOS observations to the v21 TAF targets.

The input roster is source-only and contains no labels.  This evaluator-only
step reads ASOS files for the four explicitly allowed stations and the two
allowed months, converts statute-mile ``vsby`` to metres, and selects the
first valid observation in the one-hour target window.  It never enters an
actor public state and never reads provider, holdout, quarantine, or the
protected February window.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


STATIONS = ("KDEN", "KJFK", "KORD", "KSFO")
ALLOWED_MONTHS = ("202501", "202503")
SM_TO_M = 1609.344
FORBIDDEN = ("quarantine_holdout", "2025-02-17", "2025-02-18", "2025-02-19", "2025-02-20", "2025-02-21", "2025-02-22", "2025-02-23", "2025-02-24")


def _parse_sm(value: str) -> float | None:
    text = value.strip().upper()
    if not text or text in {"M", "NA", "N/A"}:
        return None
    try:
        if " " in text:
            whole, fraction = text.split(None, 1)
            return float(whole) + _parse_sm(fraction)  # type: ignore[operator]
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            return float(numerator) / float(denominator)
        return float(text.lstrip("P"))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _timestamp(value: str) -> int:
    dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000)


def _station_dir(station: str) -> str:
    return {"KDEN": "DEN", "KJFK": "JFK", "KORD": "ORD", "KSFO": "SFO"}[station]


def _read_station_month(data_root: Path, station: str, month: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if station not in STATIONS or month not in ALLOWED_MONTHS:
        raise ValueError("station/month outside the declared development readset")
    month_dir = data_root / "asos" / station / f"{month[:4]}-{month[4:]}"
    files = sorted(month_dir.glob("*/as*" + _station_dir(station).lower() + "-" + month + ".body"))
    if not files:
        raise FileNotFoundError(f"no ASOS body for {station} {month}")
    if any(path.is_symlink() for path in files):
        raise PermissionError("ASOS symlinks are not allowed in the bounded readset")
    rows: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    for path in files:
        resolved = path.resolve()
        try:
            resolved.relative_to(data_root.resolve())
        except ValueError as exc:
            raise PermissionError("ASOS body resolves outside data root") from exc
        raw = path.read_bytes()
        identities.append({"path": str(resolved), "size_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()})
        for row in csv.DictReader(raw.decode("utf-8").splitlines()):
            valid = row.get("valid")
            if not valid:
                continue
            try:
                ts = _timestamp(valid)
            except ValueError:
                continue
            sm = _parse_sm(row.get("vsby", ""))
            if sm is None or not math.isfinite(sm) or sm < 0:
                continue
            rows.append({"valid_us": ts, "visibility_m": sm * SM_TO_M, "vsby_sm": sm, "station": station})
    rows.sort(key=lambda row: row["valid_us"])
    return rows, identities


def run(source_artifact: Path, data_root: Path, out: Path) -> dict[str, Any]:
    source_raw = source_artifact.read_text(encoding="utf-8")
    for term in FORBIDDEN:
        if term in source_raw:
            raise ValueError(f"forbidden scope marker in source artifact: {term}")
    source = json.loads(source_raw)
    if source.get("outcomes_accessed") is not False or source.get("model_calls") != 0:
        raise ValueError("input must be the source-only G1 roster")
    episodes = source.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("source roster has no episodes")
    cache: dict[tuple[str, str], tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
    bound: list[dict[str, Any]] = []
    for episode in episodes:
        station = episode["station"]
        month = datetime.fromtimestamp(int(episode["target_start"]) / 1_000_000, timezone.utc).strftime("%Y%m")
        key = (station, month)
        if key not in cache:
            cache[key] = _read_station_month(data_root, station, month)
        rows, identities = cache[key]
        start, end = int(episode["target_start"]), int(episode["target_end"])
        candidates = [row for row in rows if start <= row["valid_us"] < end]
        if not candidates:
            bound.append({"episode_id": episode["episode_id"], "status": "UNBOUND_NO_VALID_ASOS_IN_TARGET_WINDOW", "station": station, "target_start": start, "target_end": end, "source_files": identities})
            continue
        observation = candidates[0]
        bound.append({
            "episode_id": episode["episode_id"],
            "status": "BOUND",
            "station": station,
            "target_start": start,
            "target_end": end,
            "observation_valid": observation["valid_us"],
            "observation_visibility_m": observation["visibility_m"],
            "outcome_y": int(observation["visibility_m"] < 5000.0),
            "outcome_rule": "first valid ASOS vsby observation in [target_start,target_end), statute miles converted to metres",
            "source_files": identities,
        })
    artifact = {
        "schema": "disastertrace.v21.real_dev_asos_outcomes.v1",
        "evidence_role": "BOUNDED_REAL_DEV_EVALUATOR_OUTCOMES",
        "synthetic": False,
        "empirical": True,
        "actor_received_outcomes": False,
        "episode_count": len(episodes),
        "bound_count": sum(row["status"] == "BOUND" for row in bound),
        "unbound_count": sum(row["status"] != "BOUND" for row in bound),
        "stations": list(STATIONS),
        "months": list(ALLOWED_MONTHS),
        "protected_window_read": False,
        "holdout_read": False,
        "quarantine_read": False,
        "provider_calls": 0,
        "rows": bound,
        "claim_boundary": "These are development-only ASOS labels for a frozen target contract; they do not validate model value until complete method registrations and a provider/model run are separately bound.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = run(args.source_artifact, args.data_root, args.out)
    print(json.dumps({"status": "PASS" if artifact["unbound_count"] == 0 else "PARTIAL", "bound": artifact["bound_count"], "unbound": artifact["unbound_count"]}))
    return 0 if artifact["unbound_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
