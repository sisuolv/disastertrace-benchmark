"""Read-only source and numerical reconstruction; standard library, no scorer import."""

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

REPO = next(
    p
    for p in Path(__file__).resolve().parents
    if (p / "disastertrace-starter/pyproject.toml").is_file()
)
POLICIES = ("initial_professional", "latest_professional", "persistence", "half_blend")


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def at(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    need(parsed.tzinfo is not None, "timezone missing")
    return parsed.astimezone(timezone.utc)


def utc(value):
    return at(value).isoformat().replace("+00:00", "Z")


def close(a, b):
    return (
        a is not None and b is not None and math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
    )


def value(x):
    need(x is not None and not isinstance(x, bool), "missing numeric value")
    result = float(x)
    need(
        math.isfinite(result) and result not in (-999, -9999), "invalid provider value"
    )
    return result


def source(raw, receipt_path):
    receipt = load(receipt_path)
    need(
        at(receipt["started_at"]) <= at(receipt["finished_at"]), "receipt time reversal"
    )
    if raw.exists():
        need(
            digest(raw) == receipt["sha256"] and raw.stat().st_size == receipt["bytes"],
            "source digest/size mismatch",
        )
    else:
        need(receipt["status"] != "received", "successful source body missing")
    supervision = receipt_path.with_name("SUPERVISION.json")
    failed_child = supervision.exists() and (
        load(supervision)["timed_out"] or load(supervision)["exit_code"] != 0
    )
    if receipt["status"] != "received" or failed_child:
        return None, receipt
    need(
        receipt["complete"] and receipt["http_status"] == 200,
        "source success is incomplete",
    )
    return load(raw), receipt


def check_snapshot(station, snapshot, payloads, receipts):
    metadata, site = payloads["metadata"], payloads["site"]
    need(
        metadata is not None and site is not None,
        "snapshot has no identity/datum support",
    )
    need(metadata["lid"] == station["lid"], "NWPS station mismatch")
    need(metadata["flood"]["stageUnits"] == "ft", "threshold units changed")
    need(
        close(metadata["flood"]["categories"]["minor"]["stage"], station["threshold"]),
        "threshold changed",
    )
    contract = {
        "minor_stage_ft": value(metadata["flood"]["categories"]["minor"]["stage"]),
        "reference_name": metadata["name"],
        "vertical_datums": metadata.get("datums", {})
        .get("vertical", {})
        .get("value", []),
    }
    need(canonical(contract) == station["contract_hash"], "threshold contract changed")
    times = {k: r["finished_at"] for k, r in receipts.items()}
    need(snapshot["source_received_at"] == times, "source receipt projection differs")
    need(
        snapshot["captured_at"] == utc(max(times.values(), key=at)),
        "snapshot predates source receipt",
    )
    forecast = {}
    sf = payloads.get("stageflow")
    if sf is not None:
        section = sf.get("forecast", {})
        if (
            section.get("primaryName") == station["variable"]
            and section.get("primaryUnits") == "ft"
        ):
            issue, received = at(section["issuedTime"]), at(times["stageflow"])
            if issue <= received:
                for index, row in enumerate(section["data"]):
                    try:
                        v = value(row["primary"])
                        t, generated = at(row["validTime"]), at(row["generatedTime"])
                    except (ValueError, KeyError, TypeError):
                        continue
                    if generated > received:
                        continue
                    key = utc(t.isoformat())
                    point = {
                        "valid_at": key,
                        "generated_at": utc(generated.isoformat()),
                        "issued_at": utc(issue.isoformat()),
                        "value": v,
                        "source_row": index,
                    }
                    old = forecast.get(key)
                    if old and old["generated_at"] == point["generated_at"]:
                        need(old["value"] == v, "conflicting forecast version")
                    if old is None or old["generated_at"] < point["generated_at"]:
                        forecast[key] = point
    need(
        snapshot["forecast"] == sorted(forecast.values(), key=lambda x: x["valid_at"]),
        "forecast reconstruction differs",
    )
    primary, expected = payloads.get("primary"), {}
    offset = station["offset_ft"]
    if station["provider"] == "usgs":
        props = site["properties"]
        need(
            props["id"]
            == "USGS-" + station["source_station"]
            == "USGS-" + metadata["usgsId"],
            "USGS identity mismatch",
        )
        need(
            props["vertical_datum"] == station["source_datum"]["datum"]
            and close(props["altitude"], station["source_datum"]["elevation_ft"]),
            "gage datum changed",
        )
        if offset:
            need(
                station["reference"] == "NAVD88" and close(offset, props["altitude"]),
                "invalid absolute conversion",
            )
            need(
                any(
                    d["abbrev"] == "STND" and close(d["value"], -offset)
                    for d in contract["vertical_datums"]
                ),
                "offset not supported by NWPS",
            )
        if primary is not None:
            need(
                not any(link.get("rel") == "next" for link in primary.get("links", [])),
                "USGS truncation",
            )
            for feature in primary["features"]:
                row = feature["properties"]
                need(
                    row["monitoring_location_id"] == props["id"]
                    and row["parameter_code"] == station["parameter"],
                    "USGS row identity mismatch",
                )
                need(
                    row["statistic_id"] == "00011" and row["unit_of_measure"] == "ft",
                    "USGS support/unit mismatch",
                )
                try:
                    val, time = value(row["value"]), utc(row["time"])
                except (ValueError, TypeError):
                    continue
                if (
                    at(time) > at(times["primary"])
                    or row.get("qualifier") not in (None, "")
                    or row["approval_status"] not in ("Provisional", "Approved")
                ):
                    continue
                point = {
                    "valid_at": time,
                    "value": val + offset,
                    "quality": row["approval_status"],
                    "source_identity": row["time_series_id"] + ":" + time,
                }
                if offset:
                    point["raw_value_ft"] = val
                need(
                    time not in expected or expected[time] == point,
                    "conflicting primary observations",
                )
                expected[time] = point
    else:
        provider_station = site["stations"][0]
        need(
            provider_station["id"] == station["source_station"]
            and provider_station["shefcode"] == station["lid"],
            "coastal station mismatch",
        )
        need(
            "MLLW" in metadata["name"].upper()
            and provider_station["datums"]["units"] == "feet",
            "coastal reference mismatch",
        )
        query = parse_qs(urlsplit(receipts["primary"]["url"]).query)
        for key, expected_query in {
            "datum": "MLLW",
            "units": "english",
            "time_zone": "gmt",
            "product": "water_level",
            "station": station["source_station"],
        }.items():
            need(
                query.get(key) == [expected_query], "coastal request contract mismatch"
            )
        if primary is not None:
            need(
                primary["metadata"]["id"] == station["source_station"],
                "coastal response identity mismatch",
            )
            for row in primary["data"]:
                try:
                    val, time = value(row["v"]), row["t"].replace(" ", "T") + ":00Z"
                    valid = at(time)
                except (ValueError, TypeError):
                    continue
                if (
                    valid > at(times["primary"])
                    or row.get("q") not in ("p", "v")
                    or row.get("f") != "0,0,0,0"
                ):
                    continue
                point = {
                    "valid_at": time,
                    "value": val,
                    "quality": "Approved" if row["q"] == "v" else "Provisional",
                    "source_identity": station["source_station"]
                    + ":MLLW:english:"
                    + time,
                }
                need(
                    time not in expected or expected[time] == point,
                    "conflicting coastal observations",
                )
                expected[time] = point
    observed = sorted(expected.values(), key=lambda x: x["valid_at"])
    need(
        len(observed) == len(snapshot["observations"]),
        "primary observations silently omitted",
    )
    for original, saved in zip(observed, snapshot["observations"]):
        need(
            original.keys() == saved.keys()
            and close(original["value"], saved["value"]),
            "primary value reconstruction differs",
        )
        need(
            all(original[k] == saved[k] for k in original if k != "value"),
            "primary metadata reconstruction differs",
        )


def expected_predictions(snapshot, target, prepared):
    now = at(prepared)
    forecast = [
        p
        for p in snapshot["forecast"]
        if p["valid_at"] == target["valid_at"]
        and at(p["generated_at"]) <= now
        and at(p["issued_at"]) <= now
        and now - at(p["issued_at"]) <= timedelta(hours=36)
    ]
    observations = [
        p
        for p in snapshot["observations"]
        if now - timedelta(hours=6) <= at(p["valid_at"]) <= now
    ]
    official = (
        max(forecast, key=lambda p: p["generated_at"])["value"] if forecast else None
    )
    persistence = (
        max(observations, key=lambda p: p["valid_at"])["value"]
        if observations
        else None
    )
    return {
        "initial_professional": target["initial_value"],
        "latest_professional": official,
        "persistence": persistence,
        "half_blend": (official + persistence) / 2
        if official is not None and persistence is not None
        else None,
    }


def verify(root):
    freeze = load(root / "FREEZE.json")
    for name, hashed in freeze["files"].items():
        need(digest(root / name) == hashed, "frozen file changed: " + name)
    registry, run = load(root / "REGISTRY.json"), root / "run"
    need(registry["policies"] == list(POLICIES), "unexpected policies")
    targets = {t["id"]: t for t in registry["targets"]}
    need(
        len(targets) * 4 == registry["expected_target_policy_results"],
        "fixed denominator mismatch",
    )
    stations = {s["lid"]: s for s in registry["stations"]}
    for t in targets.values():
        need(
            at(registry["created_at"]) < at(t["deadline"]) < at(t["valid_at"]),
            "target was not registered before deadline",
        )
        need(
            at(t["valid_at"]) - at(t["deadline"]) == timedelta(hours=2),
            "target deadline differs",
        )
        need(
            t["threshold"] == stations[t["lid"]]["threshold"],
            "target threshold differs",
        )
    snapshots, source_count, body_bytes = {}, 0, 0
    for station in stations.values():
        lid = station["lid"]
        payloads, receipts = {}, {}
        for role, locator in station["sources"].items():
            need(
                digest(REPO / locator["path"]) == locator["sha256"],
                "initial source changed",
            )
            need(
                digest(REPO / locator["receipt_path"]) == locator["receipt_sha256"],
                "initial receipt changed",
            )
            payloads[role], receipts[role] = source(
                REPO / locator["path"], REPO / locator["receipt_path"]
            )
            source_count += 1
        snapshot = load(root / "initial" / f"{lid}.json")
        check_snapshot(station, snapshot, payloads, receipts)
        need(
            at(snapshot["captured_at"]) <= at(registry["created_at"]),
            "initial data arrived after registration",
        )
        snapshots[("initial", lid)] = snapshot
    for target in targets.values():
        initial = snapshots[("initial", target["lid"])]
        need(
            canonical(initial) == target["initial_snapshot_sha256"],
            "initial snapshot binding differs",
        )
        matching = [
            p for p in initial["forecast"] if p["valid_at"] == target["valid_at"]
        ]
        need(
            len(matching) == 1 and close(matching[0]["value"], target["initial_value"]),
            "initial professional forecast does not match source",
        )
    cycles = [p for p in sorted(run.glob("cycle_*")) if (p / "COMPLETE.json").exists()]
    for cycle in cycles:
        opportunities = load(cycle / "OPPORTUNITIES.json")
        need(
            len(opportunities["requests"]) == 4 * len(stations),
            "poll request denominator differs",
        )
        for station in stations.values():
            lid = station["lid"]
            payloads, receipts = {}, {}
            for role in ("metadata", "stageflow", "site", "primary"):
                directory = cycle / "captures" / lid / role
                payloads[role], receipts[role] = source(
                    directory / "response.raw", directory / "RECEIPT.json"
                )
                source_count += 1
                body_bytes += receipts[role]["bytes"]
            snapshot_path = cycle / "snapshots" / f"{lid}.json"
            if snapshot_path.exists():
                snapshot = load(snapshot_path)
                check_snapshot(station, snapshot, payloads, receipts)
                snapshots[(cycle.name, lid)] = snapshot
    commits, late = [], 0
    for directory in [run / "initial"] + cycles:
        rows = load(directory / "SUBMISSIONS.json")
        receipt = load(directory / "SUBMISSION_RECEIPT.json")
        need(
            digest(directory / "SUBMISSIONS.json") == receipt["sha256"]
            and len(rows) == receipt["count"],
            "submission receipt differs",
        )
        need(
            len({(c["target_id"], c["policy"]) for c in rows}) == len(rows),
            "duplicate prediction slot",
        )
        for c in rows:
            t, snapshot = targets[c["target_id"]], snapshots[(directory.name, c["lid"])]
            need(
                c["lid"] == t["lid"] and c["valid_at"] == t["valid_at"],
                "submission target mismatch",
            )
            need(
                c["snapshot_sha256"] == canonical(snapshot),
                "prediction source hash differs",
            )
            need(
                c["source_first_seen_at"] == snapshot["captured_at"],
                "prediction receipt differs",
            )
            need(
                at(registry["created_at"])
                <= at(c["committed_at"])
                <= at(receipt["persisted_at"]),
                "prediction timestamp invalid",
            )
            need(
                at(snapshot["captured_at"])
                <= at(c["committed_at"])
                <= at(t["deadline"]),
                "prediction used unavailable data or prepared too late",
            )
            expected = expected_predictions(snapshot, t, c["committed_at"])[c["policy"]]
            need(close(expected, c["value"]), "program prediction does not reconstruct")
            need(
                c["threshold"] == t["threshold"]
                and c["point_exceeds_threshold"] == (c["value"] >= t["threshold"]),
                "threshold prediction differs",
            )
            if at(receipt["persisted_at"]) > at(t["deadline"]):
                late += 1
            commits.append({**c, "committed_at": receipt["persisted_at"]})
    settled_checks = 0
    for cycle in cycles:
        results = load(cycle / "SETTLEMENTS.json")
        need(
            len(results) == len(targets)
            and {r["target_id"] for r in results} == set(targets),
            "settlement denominator differs",
        )
        for result in results:
            target = targets[result["target_id"]]
            check = at(result["checked_at"])
            snapshot = snapshots.get((cycle.name, target["lid"]))
            outcomes = (
                [
                    p
                    for p in snapshot["observations"]
                    if p["valid_at"] == target["valid_at"]
                ]
                if snapshot
                else []
            )
            if check < at(target["valid_at"]):
                need(
                    result["status"] == "pending_future", "future outcome scored early"
                )
                continue
            if not outcomes:
                need(
                    result["status"] == "pending_exact_observation",
                    "missing exact outcome not retained",
                )
                continue
            need(len(outcomes) == 1, "ambiguous outcome")
            outcome = outcomes[0]
            need(
                result["outcome"] == outcome
                and result["binary_outcome"]
                == int(outcome["value"] >= target["threshold"]),
                "outcome differs",
            )
            need(
                result["status"] == "settled_" + outcome["quality"].lower(),
                "outcome quality concealed",
            )
            for policy in POLICIES:
                eligible = [
                    c
                    for c in commits
                    if c["target_id"] == target["id"]
                    and c["policy"] == policy
                    and at(c["committed_at"]) <= min(at(target["deadline"]), check)
                ]
                score = result["policies"][policy]
                if not eligible:
                    need(
                        score["status"] == "missing_prediction",
                        "missing submission not retained",
                    )
                    continue
                latest = max(eligible, key=lambda c: c["committed_at"])
                need(
                    close(score["prediction"], latest["value"]),
                    "wrong last lawful prediction",
                )
                need(
                    close(
                        score["absolute_error"], abs(latest["value"] - outcome["value"])
                    ),
                    "numerical MAE differs",
                )
                need(
                    score["point_threshold_error"]
                    == int(
                        (latest["value"] >= target["threshold"])
                        != (outcome["value"] >= target["threshold"])
                    ),
                    "warning diagnostic differs",
                )
                settled_checks += 1
    need(
        len(cycles) * len(stations) * 4 <= registry["max_logical_downloads"],
        "download cap exceeded",
    )
    need(body_bytes <= registry["max_body_bytes"], "body budget exceeded")
    last = load(cycles[-1] / "SETTLEMENTS.json") if cycles else []
    return {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "registry_sha256": digest(root / "REGISTRY.json"),
        "frozen_files": len(freeze["files"]),
        "complete_polls_verified": len(cycles),
        "source_captures_verified": source_count,
        "program_submissions_verified": len(commits),
        "late_disk_submissions_excluded": late,
        "settled_policy_errors_reconstructed": settled_checks,
        "latest_target_status_counts": dict(Counter(r["status"] for r in last)),
        "interpretation": "verified captured prefix; future observations and LLM comparisons remain unmeasured",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.root.resolve())
    with args.out.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report, indent=2))
