"""TAF-only qualification from an exact, previously authorized body readset."""

from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from .provider import canonical, digest

UTC = timezone.utc
HOUR = 3_600_000_000
STATIONS = ("KSFO", "KDEN", "KJFK", "KORD")
SEED = "disastertrace-v17-pilot-20260922-v1"
HEADER = re.compile(r"\b(KSFO|KDEN|KJFK|KORD)\s+(\d{6})Z(?:\s+(\d{4})/(\d{4}))?")
WMO = re.compile(r"\bFT[A-Z0-9]{4}\s+[A-Z]{4}\s+\d{6}(?:\s+([A-Z]{3}))?\s*\n")


def iso(us):
    return datetime.fromtimestamp(us / 1_000_000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def micros(dt):
    return int(dt.timestamp()) * 1_000_000


def allowed_month(ym):
    return bool(re.fullmatch(r"202[345]-(0[1-9]|1[012])", ym)) and ym != "2025-02"


def legal_target(us):
    dt = datetime.fromtimestamp(us / 1_000_000, UTC)
    return allowed_month(dt.strftime("%Y-%m")) and 4 <= dt.day <= 25


def readset_rows(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line]
    if len(rows) != 140:
        raise ValueError("readset must contain exactly 140 bodies")
    expected = {(station, f"{year:04}-{month:02}") for station in STATIONS
                for year in (2023, 2024, 2025) for month in range(1, 13)
                if (year, month) != (2025, 2)}
    if {(row["station"], row["year_month"]) for row in rows} != expected:
        raise ValueError("readset station-month mismatch")
    for row in rows:
        p = Path(row["canonical_body_path"])
        if "quarantine_holdout" in p.parts or not allowed_month(row["year_month"]):
            raise PermissionError("forbidden readset entry")
        expected_name = row["station"] + "_" + row["year_month"].replace("-", "") + ".body"
        if p.name != expected_name or not p.is_absolute() or ".." in p.parts:
            raise PermissionError("body identity mismatch")
    return rows


def install_guard(rows):
    allowed = {os.path.abspath(row["canonical_body_path"]) for row in rows}

    def audit(event, args):
        if event not in {"open", "os.listdir", "os.scandir"} or not args:
            return
        value = args[0]
        if not isinstance(value, (str, bytes, os.PathLike)):
            return
        p = os.fsdecode(value)
        parts = Path(p).parts
        if "quarantine_holdout" in parts:
            raise PermissionError("protected-path operation rejected before access")
        if "data_real_v16" not in parts:
            if event == "open" and re.search(r"/(?:outcome_wiring|outcome|labels?)(?:[./_])", p):
                raise PermissionError("outcome module excluded from pilot")
            return
        if event != "open":
            raise PermissionError("raw data directory enumeration is prohibited")
        mode, flags = args[1], args[2]
        write = isinstance(mode, str) and any(x in mode for x in "wax+")
        write = write or isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write or os.path.abspath(p) not in allowed:
            raise PermissionError("raw-data access is outside exact read-only body allowlist")
    sys.addaudithook(audit)


def read_body(row):
    path = Path(row["canonical_body_path"])
    if "quarantine_holdout" in path.parts or not allowed_month(row["year_month"]):
        raise PermissionError("forbidden body")
    expected = row["station"] + "_" + row["year_month"].replace("-", "") + ".body"
    if path.name != expected or path.is_symlink():
        raise PermissionError("body path mismatch")
    data = path.read_bytes()
    if len(data) != row["size_bytes"] or hashlib.sha256(data).hexdigest() != row["raw_text_sha256"]:
        raise ValueError("raw body identity changed")
    return data


def day_relative(ddhh, issued):
    day, hour = int(ddhh[:2]), int(ddhh[2:])
    if hour > 24 or not 1 <= day <= 31:
        raise ValueError("invalid validity token")
    possibilities = []
    for offset in (-1, 0, 1):
        month_index = issued.year * 12 + issued.month - 1 + offset
        year, month0 = divmod(month_index, 12)
        try:
            value = datetime(year, month0 + 1, day, tzinfo=UTC) + timedelta(hours=hour)
            possibilities.append(value)
        except ValueError:
            pass
    if not possibilities:
        raise ValueError("unresolvable validity day")
    return min(possibilities, key=lambda value: abs((value - issued).total_seconds()))


def parse_frame(data, row, start=0, end=None):
    end = len(data) if end is None else end
    text = data[start:end].decode("utf-8", errors="strict").replace("\r", "")
    match = HEADER.search(text)
    if not match:
        raise ValueError("no recognized native TAF issue header")
    station, ddhhmm, valid_start, valid_end = match.groups()
    if station != row["station"]:
        raise ValueError("station mismatch")
    year, month = map(int, row["year_month"].split("-"))
    day, hour, minute = int(ddhhmm[:2]), int(ddhhmm[2:4]), int(ddhhmm[4:])
    issued = datetime(year, month, day, hour, minute, tzinfo=UTC)
    if not valid_start or not valid_end or re.search(r"\b(?:CNL|NIL)\b", text[match.start():]):
        raise ValueError("nil/cancellation/missing validity unsupported in this pilot")
    lower = day_relative(valid_start, issued)
    upper = day_relative(valid_end, lower)
    if upper <= lower:
        month_index = lower.year * 12 + lower.month
        next_year, next_month0 = divmod(month_index, 12)
        upper = datetime(next_year, next_month0 + 1, int(valid_end[:2]), tzinfo=UTC) + timedelta(hours=int(valid_end[2:]))
    if not 0 < (upper - lower).total_seconds() <= 36 * 3600:
        raise ValueError("unsupported validity duration")
    before = text[max(0, match.start() - 30):match.start()]
    kind = "COR" if re.search(r"\bCOR\b", before) else "AMD" if re.search(r"\bAMD\b", before) else "ROUTINE"
    wmo = WMO.search(text)
    bbb = wmo.group(1) if wmo else None
    native = " ".join(text[match.start():].strip("\x01\x03 \n=").split())
    native_hash = hashlib.sha256((kind + "|" + (bbb or "") + "|" + native).encode()).hexdigest()
    return {
        "source_id": "TAF-" + station + "-" + native_hash[:16],
        "station": station, "issued_at_us": micros(issued),
        "available_at_us": micros(issued) + 120_000_000,
        "availability_basis": "declared_lag_120s",
        "valid_start_us": micros(lower), "valid_end_us": micros(upper),
        "kind": kind, "bbb": bbb, "native_sha256": native_hash,
        "body_path": row["canonical_body_path"], "body_sha256": row["raw_text_sha256"],
        "year_month": row["year_month"], "byte_start": start, "byte_end": end,
        "frame_sha256": hashlib.sha256(data[start:end]).hexdigest(),
    }


def parse_body(data, row):
    products, errors = [], []
    frames = list(re.finditer(rb"\x01.*?\x03", data, re.S))
    if not frames:
        raise ValueError("no AFOS frames")
    cursor = 0
    for frame in frames:
        if data[cursor:frame.start()].strip():
            errors.append({"body_path": row["canonical_body_path"], "byte_start": cursor,
                           "byte_end": frame.start(), "reason": "unframed or incomplete AFOS fragment"})
        cursor = frame.end()
        try:
            if frame.group().count(b"\x01") != 1:
                raise ValueError("nested AFOS start")
            products.append(parse_frame(data, row, frame.start(), frame.end()))
        except (ValueError, UnicodeDecodeError) as error:
            # Keep only input-side identity and a bounded reason; no inferred outcome.
            errors.append({"body_path": row["canonical_body_path"], "byte_start": frame.start(),
                           "byte_end": frame.end(), "reason": str(error)})
    if data[cursor:].strip():
        errors.append({"body_path": row["canonical_body_path"], "byte_start": cursor,
                       "byte_end": len(data), "reason": "unframed or incomplete AFOS fragment"})
    return products, errors


def reference_state(products, cutoff, target_start, target_end):
    visible = [p for p in products if p["available_at_us"] <= cutoff]
    overlap = [p for p in visible if p["valid_start_us"] < target_end and target_start < p["valid_end_us"]]
    if not overlap:
        raise ValueError("no applicable evidence")
    newest_issue = max(p["issued_at_us"] for p in overlap)
    newest = [p for p in overlap if p["issued_at_us"] == newest_issue]
    identities = {p["source_id"]: p for p in newest}
    if len(identities) != 1:
        raise ValueError("different same-issue products require unresolved authority")
    selected = next(iter(identities.values()))
    if not selected["valid_start_us"] <= target_start or selected["valid_end_us"] < target_end:
        raise ValueError("partial-target replacement not qualified")
    return {"active_source_ids": [selected["source_id"]],
            "valid_start": iso(selected["valid_start_us"]), "valid_end": iso(selected["valid_end_us"]),
            "relation_status": "RESOLVED"}


def qualify_candidate(station, start, products, rejected_ranges):
    end = start + HOUR
    checkpoints = [start - HOUR, start - 40 * 60_000_000, start - 20 * 60_000_000]
    prefix_start = start - 36 * HOUR
    relevant = [p for p in products if prefix_start <= p["issued_at_us"] and p["available_at_us"] <= checkpoints[-1]]
    if not relevant or min(p["available_at_us"] for p in relevant) > start - 24 * HOUR:
        raise ValueError("insufficient initial history coverage")
    if any(prefix_start <= p["issued_at_us"] <= checkpoints[-1] for p in rejected_ranges):
        raise ValueError("unparsed frame in episode history")
    # Do not silently resolve older equal-issue ambiguities either.
    issued_groups = defaultdict(set)
    for p in relevant:
        issued_groups[p["issued_at_us"]].add(p["source_id"])
    if any(len(ids) > 1 for ids in issued_groups.values()):
        raise ValueError("same-issue ambiguity in visible history")
    unique = {p["source_id"]: p for p in sorted(relevant, key=lambda p: (p["issued_at_us"], p["byte_start"]))}
    relevant = sorted(unique.values(), key=lambda p: (p["available_at_us"], p["source_id"]))
    references = [reference_state(relevant, cp, start, end) for cp in checkpoints]
    state_changed = any(references[k] != references[0] for k in (1, 2))
    arrivals = [p for p in relevant if checkpoints[0] < p["available_at_us"] <= checkpoints[-1]]
    category = "STATE_CHANGE" if state_changed else "ARRIVAL_STATE_STABLE" if arrivals else "NO_ARRIVAL"
    active = {sid for ref in references for sid in ref["active_source_ids"]}
    active_changes = [p for p in arrivals if p["source_id"] in active]
    subtype = "AMD_COR" if any(p["kind"] in ("AMD", "COR") for p in active_changes) else "ROUTINE"
    identity = f"{station}-{iso(start)}"
    episode = {"episode_id": identity, "target_id": identity + "-vis-lt5000m",
               "station": station, "target_start_us": start, "target_end_us": end,
               "checkpoints_us": checkpoints, "prefix_start_us": prefix_start,
               "threshold_m": 5000, "category": category, "change_subtype": subtype,
               "sources": relevant, "block": station + "-" + iso(start)[:10],
               "selection_hash": hashlib.sha256((SEED + "|" + identity).encode()).hexdigest()}
    return episode, references


def prepare(run, census):
    run, census = Path(run), Path(census)
    rows = readset_rows(census / "input_readset.jsonl")
    install_guard(rows)
    bodies, parse_errors, audits = {}, [], []
    for row in rows:
        data = read_body(row)
        products, errors = parse_body(data, row)
        bad = []
        for error in errors:
            snippet = data[error["byte_start"]:error["byte_end"]].decode(errors="replace")
            m = re.search(r"\b" + row["station"] + r"\s+(\d{6})Z", snippet)
            if m:
                token = m.group(1)
                try:
                    dt = datetime(int(row["year_month"][:4]), int(row["year_month"][5:]),
                                  int(token[:2]), int(token[2:4]), int(token[4:]), tzinfo=UTC)
                    bad.append({"issued_at_us": micros(dt)})
                except ValueError:
                    bad.append({"issued_at_us": -1})
            else:
                bad.append({"issued_at_us": -1})
        bodies[(row["station"], row["year_month"])] = (products, bad)
        parse_errors.extend(errors)
        audits.append({"body_path": row["canonical_body_path"], "sha256": row["raw_text_sha256"],
                       "size_bytes": len(data), "parsed_frames": len(products), "rejected_frames": len(errors)})
    candidates, rejected, refs = [], [], {}
    with (census / "slot_summary.jsonl").open() as source:
        for line in source:
            slot = json.loads(line)
            start = slot["validity_start_us"]
            if not legal_target(start):
                continue
            station, ym = slot["station"], iso(start)[:7]
            products, bad = bodies[(station, ym)]
            try:
                if any(p["issued_at_us"] == -1 for p in bad):
                    raise ValueError("unlocatable rejected frame in station-month")
                episode, reference = qualify_candidate(station, start, products, bad)
                candidates.append(episode)
                refs[episode["episode_id"]] = reference
            except ValueError as error:
                rejected.append({"station": station, "target_start": iso(start), "reason": str(error)})
    quotas = [("STATE_CHANGE", "ROUTINE", 6), ("STATE_CHANGE", "AMD_COR", 6),
              ("ARRIVAL_STATE_STABLE", None, 6), ("NO_ARRIVAL", None, 6)]
    selected, used_days, used_sources = [], set(), set()
    selection_exclusions = Counter()
    # Round-robin across stations, with hash ordering within each stratum.
    for category, subtype, count in quotas:
        pools = {station: sorted([p for p in candidates if p["category"] == category and p["station"] == station
                                 and (subtype is None or p["change_subtype"] == subtype)],
                                 key=lambda p: p["selection_hash"]) for station in STATIONS}
        remaining = count
        while remaining and any(pools.values()):
            for station in STATIONS:
                if not remaining:
                    break
                while pools[station]:
                    candidate = pools[station].pop(0)
                    sources = {p["source_id"] for p in candidate["sources"]}
                    day = iso(candidate["target_start_us"])[:10]
                    if day in used_days or sources & used_sources:
                        selection_exclusions["shared_utc_day_or_source"] += 1
                        continue
                    selected.append(candidate)
                    used_days.add(day)
                    used_sources.update(sources)
                    remaining -= 1
                    break
    def save_lines(name, values):
        with (run / name).open("x", encoding="utf-8") as out:
            for value in values:
                out.write(canonical(value) + "\n")
    save_lines("episodes.jsonl", selected)
    save_lines("reference_manifest.jsonl", [
        {"episode_id": p["episode_id"], "checkpoints": [
            {"as_of_us": cp, "fact_state": ref} for cp, ref in zip(p["checkpoints_us"], refs[p["episode_id"]])],
         "review_status": "PROGRAM_QUALIFIED_PENDING_AI_SPOTCHECK_NOT_HUMAN"} for p in selected])
    save_lines("exclusions.jsonl", rejected)
    save_lines("audit/raw_read_verification.jsonl", audits)
    save_lines("audit/parser_rejections.jsonl", parse_errors)
    report = {"input_bodies_verified": len(audits), "input_bytes_verified": sum(x["size_bytes"] for x in audits),
              "parsed_frames": sum(x["parsed_frames"] for x in audits), "rejected_frames": len(parse_errors),
              "candidate_counts": dict(Counter(x["category"] for x in candidates)),
              "candidate_change_subtypes": dict(Counter(x["change_subtype"] for x in candidates if x["category"] == "STATE_CHANGE")),
              "selected_count": len(selected), "selected_categories": dict(Counter(x["category"] for x in selected)),
              "selected_stations": dict(Counter(x["station"] for x in selected)),
              "selected_subtypes": dict(Counter(x["change_subtype"] for x in selected if x["category"] == "STATE_CHANGE")),
              "unique_utc_dates": len(used_days), "unique_source_ids": len(used_sources),
              "exclusion_reasons": dict(Counter(x["reason"] for x in rejected)),
              "selection_exclusions": dict(selection_exclusions), "seed": SEED,
              "availability_basis": "declared_lag_120s", "human_reviewed": False,
              "global_g1_passed": False, "raw_data_cache_written": False}
    (run / "qualification_summary.json").write_text(canonical(report) + "\n")
    return report
