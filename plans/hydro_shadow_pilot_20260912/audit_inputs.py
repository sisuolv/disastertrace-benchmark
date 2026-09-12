"""Audit actual sampled provider bytes; never turn a download success into admission."""

import argparse
from collections import Counter
from pathlib import Path

from disastertrace.hydro_shadow_v1.capture import (
    file_hash,
    stamp,
    strict_json,
    write_new,
)
from disastertrace.hydro_shadow_v1.core import (
    align_observations,
    build_snapshot,
    instant,
    nwps_points,
    qualify_station,
    usgs_points,
)

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(__file__).resolve().parent


def read_source(path):
    receipt_path = path.with_suffix(".json")
    receipt = strict_json(receipt_path.read_bytes())
    if not (
        receipt["status"] == "received"
        and receipt["complete"]
        and receipt["http_status"] == 200
        and receipt["sha256"] == file_hash(path)
        and receipt["bytes"] == path.stat().st_size
        and instant(receipt["started_at"]) <= instant(receipt["finished_at"])
    ):
        raise ValueError("invalid capture receipt: " + str(path))
    return strict_json(path.read_bytes()), {
        "path": str(path.relative_to(ROOT)),
        "sha256": file_hash(path),
        "receipt_path": str(receipt_path.relative_to(ROOT)),
        "receipt_sha256": file_hash(receipt_path),
        "finished_at": receipt["finished_at"],
        "url": receipt["url"],
    }


def audit(output):
    output.mkdir(parents=True, exist_ok=False)
    records, admitted = [], []
    for ref in strict_json((BUNDLE / "STATION_REFERENCES.json").read_bytes()):
        lid = ref["lid"].lower()
        metadata, meta_source = read_source(ROOT / ref["metadata_path"])
        stageflow, sf_source = read_source(
            BUNDLE / "stations_01" / f"{lid}-stageflow.raw"
        )
        record = {
            "lid": ref["lid"],
            "selection_reason": ref["candidate_reason"],
            "sources": {"metadata": meta_source, "stageflow": sf_source},
            "attempts": [],
        }
        variable = "Tide Height" if "coops_id" in ref else "Stage"
        history, _ = nwps_points(
            stageflow, "observed", sf_source["finished_at"], variable
        )
        minor = metadata["flood"]["categories"]["minor"]["stage"]
        record["observed_history_diagnostic"] = {
            "points": len(history),
            "start": history[0]["valid_at"] if history else None,
            "end": history[-1]["valid_at"] if history else None,
            "min_ft": min((p["value"] for p in history), default=None),
            "max_ft": max((p["value"] for p in history), default=None),
            "above_current_minor_threshold": sum(p["value"] >= minor for p in history),
            "minor_threshold_ft": minor,
            "historical_threshold_vintage_proven": False,
            "historical_issued_forecasts_acquired": False,
        }
        if not ref["usgs_id"] and "coops_id" not in ref:
            record.update(
                admitted=False,
                problems=["no primary station ID", "no current forecast"],
            )
            records.append(record)
            continue
        provider = "coops" if "coops_id" in ref else "usgs"
        site, site_source = read_source(
            BUNDLE
            / "independent_01"
            / f"{lid}-{provider}-{'station' if provider == 'coops' else 'site'}.raw"
        )
        record["sources"]["site"] = site_source
        parameters = (
            ["water"]
            if provider == "coops"
            else ["00065", "62614"]
            if lid == "dnlf1"
            else ["00065"]
        )
        accepted = None
        for parameter in parameters:
            primary, pr_source = read_source(
                BUNDLE / "independent_01" / f"{lid}-{provider}-{parameter}.raw"
            )
            sources = {**record["sources"], "primary": pr_source}
            times = {k: s["finished_at"] for k, s in sources.items()}
            received = max(times.values(), key=instant)
            try:
                result = qualify_station(
                    metadata,
                    stageflow,
                    primary,
                    site,
                    parameter,
                    received,
                    provider,
                    times,
                )
                if provider == "usgs":
                    raw_points, _ = usgs_points(
                        primary, ref["usgs_id"], parameter, times["primary"]
                    )
                    result["raw_unconverted_alignment"] = align_observations(
                        history, raw_points
                    )
            except (ValueError, KeyError, TypeError) as exc:
                result = {
                    "admitted": False,
                    "problems": [type(exc).__name__ + ": " + str(exc)],
                }
            result.update(parameter=parameter, sources=sources)
            record["attempts"].append(result)
            if result["admitted"] and accepted is None:
                accepted = result
                snapshot = build_snapshot(result, stageflow, primary, received, times)
                result["snapshot_path"] = str(
                    (output / f"{lid}_snapshot.json").relative_to(ROOT)
                )
                write_new(ROOT / result["snapshot_path"], snapshot)
                admitted.append(result)
        record["admitted"] = accepted is not None
        records.append(record)
    report = {
        "created_at": stamp(),
        "candidates": len(records),
        "admitted": len(admitted),
        "status_counts": dict(
            Counter("admitted" if r["admitted"] else "rejected" for r in records)
        ),
        "selection": "risk-stratified engineering sample; not population incidence or independent events",
        "records": records,
    }
    write_new(output / "ADMISSION.json", report)
    write_new(output / "QUALIFIED_STATIONS.json", admitted)
    print({"candidates": len(records), "admitted": [r["lid"] for r in admitted]})
    for r in records:
        print(
            r["lid"],
            r["admitted"],
            [a.get("problems") for a in r["attempts"]],
            r["observed_history_diagnostic"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    audit(parser.parse_args().output.resolve())
