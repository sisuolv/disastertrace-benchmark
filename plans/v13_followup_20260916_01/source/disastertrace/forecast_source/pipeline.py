"""Bounded official-source acquisition and independently repeatable consensus review."""

import argparse
import hashlib
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval.storage import digest, now, read, seal, verify_seal, write

from . import consensus, normalization, parser_a, parser_b, views

PROJECT = Path(__file__).resolve().parents[3]
SELECTION = (("AL062024", "FRANCINE", range(5, 11)), ("AL092021", "IDA", range(9, 15)))
MAX_BYTES = 2 * 1024 * 1024


def selection():
    return [
        {
            "storm_id": storm,
            "storm_name": name,
            "split": "development",
            "advisory_number": number,
            "source_id": f"{storm.lower()}-fstadv-{number:03d}",
            "url": f"https://www.nhc.noaa.gov/archive/{storm[-4:]}/{storm[:4].lower()}/{storm.lower()}.fstadv.{number:03d}.shtml",
        }
        for storm, name, numbers in SELECTION
        for number in numbers
    ]


def source_inventory():
    names = [
        "src/disastertrace/__init__.py",
        "src/disastertrace/automated/__init__.py",
        "src/disastertrace/automated/common.py",
        "src/disastertrace/local_eval/__init__.py",
        "src/disastertrace/local_eval/storage.py",
    ]
    names += [
        str(p.relative_to(PROJECT))
        for p in (PROJECT / "src/disastertrace/forecast_source").glob("*.py")
    ]
    return {name: digest(PROJECT / name) for name in sorted(names)}


def snapshot(output, files):
    for name in files:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, target)


def prepare(bundle):
    bundle = Path(bundle)
    catalogue = read(PROJECT / "configs/nhc_cohort_v1.json")
    split = read(PROJECT / "work/build-cohort-v1/splits/event_groups.json")
    protected = sorted(
        {row["storm_id"] for row in catalogue["events"] if row["split"] == "heldout"}
        | set(split["splits"]["heldout"]["planned_event_ids"])
    )
    selected = []
    for storm, name, numbers in SELECTION:
        if storm in protected:
            raise ValueError("heldout selection collision")
        for number in numbers:
            stem = storm.lower()
            selected.append(
                {
                    "storm_id": storm,
                    "storm_name": name,
                    "split": "development",
                    "advisory_number": number,
                    "source_id": f"{stem}-fstadv-{number:03d}",
                    "url": f"https://www.nhc.noaa.gov/archive/{storm[-4:]}/{stem[:4]}/{stem}.fstadv.{number:03d}.shtml",
                }
            )
    files = source_inventory()
    scope = {
        "schema_version": "nhc_forecast_source_scope_v1",
        "created_at": now(),
        "planned_bodies": 12,
        "maximum_bytes_per_body": MAX_BYTES,
        "automatic_retries": 0,
        "selected": selected,
        "protected_heldout_ids": protected,
        "catalogue_sha256": digest(PROJECT / "configs/nhc_cohort_v1.json"),
        "split_sha256": digest(PROJECT / "work/build-cohort-v1/splits/event_groups.json"),
        "implementation_files": files,
        "model_generations": 0,
        "new_human_gold_annotations": 0,
        "llm_judge": False,
        "plan_exposure": {
            "AL092022": "Ian examples in supplied plan; protected heldout, do not acquire",
            "AL062024": "Francine supplied-plan exposure; explicitly development",
        },
    }
    scope["scope_id"] = fingerprint(scope)
    bundle.mkdir(parents=True, exist_ok=True)
    write(bundle / "SOURCE_SCOPE.json", scope)
    (bundle / "input_evidence").mkdir(parents=True, exist_ok=False)
    shutil.copyfile(
        PROJECT / "configs/nhc_cohort_v1.json", bundle / "input_evidence/catalogue.json"
    )
    shutil.copyfile(
        PROJECT / "work/build-cohort-v1/splits/event_groups.json",
        bundle / "input_evidence/split.json",
    )
    snapshot(bundle / "acquisition_source", files)
    print(
        {"scope_id": scope["scope_id"], "bodies": 12, "protected_heldout": len(protected)},
        flush=True,
    )
    return scope


def verify_scope(bundle, *, acquisition=False):
    bundle = Path(bundle)
    scope = read(bundle / "SOURCE_SCOPE.json")
    if scope["scope_id"] != fingerprint({k: v for k, v in scope.items() if k != "scope_id"}):
        raise ValueError("source scope binding changed")
    if (
        digest(bundle / "input_evidence/catalogue.json") != scope["catalogue_sha256"]
        or digest(bundle / "input_evidence/split.json") != scope["split_sha256"]
    ):
        raise ValueError("frozen split evidence changed")
    catalogue = read(bundle / "input_evidence/catalogue.json")
    split = read(bundle / "input_evidence/split.json")
    protected = sorted(
        {row["storm_id"] for row in catalogue["events"] if row["split"] == "heldout"}
        | set(split["splits"]["heldout"]["planned_event_ids"])
    )
    if (
        scope["selected"] != selection()
        or scope["protected_heldout_ids"] != protected
        or type(scope["automatic_retries"]) is not int
        or scope["automatic_retries"] != 0
        or type(scope["maximum_bytes_per_body"]) is not int
        or scope["maximum_bytes_per_body"] != MAX_BYTES
    ):
        raise ValueError("URLs, paths, split protection or acquisition caps differ")
    expected = {(storm, n) for storm, _, numbers in SELECTION for n in numbers}
    if (
        scope["planned_bodies"] != 12
        or len(scope["selected"]) != 12
        or {(s["storm_id"], s["advisory_number"]) for s in scope["selected"]} != expected
        or any(s["storm_id"] in scope["protected_heldout_ids"] for s in scope["selected"])
    ):
        raise ValueError("bounded development selection changed")
    for name, value in scope["implementation_files"].items():
        if digest(bundle / "acquisition_source" / name) != value:
            raise ValueError("prepared source changed")
    if acquisition and source_inventory() != scope["implementation_files"]:
        raise ValueError("acquisition code differs from frozen source")
    return scope


def acquire(bundle):
    bundle = Path(bundle)
    scope = verify_scope(bundle, acquisition=True)
    target = bundle / "acquisition"
    target.mkdir(parents=True, exist_ok=False)
    write(
        target / "claim.json",
        {"scope_id": scope["scope_id"], "started_at": now(), "no_retry": True},
    )
    rows = []
    for item in scope["selected"]:
        directory = target / item["source_id"]
        write(directory / "intent.json", {**item, "attempt": 0, "at": now()})
        result = {**item, "retrieved_at": None, "available_at": None, "status": "failed"}
        body = None
        try:
            request = urllib.request.Request(
                item["url"], headers={"User-Agent": "DisasterTrace-SourceValidation/1.0"}
            )
            try:
                response = urllib.request.urlopen(request, timeout=30)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                body = response.read(MAX_BYTES + 1)
                result.update(
                    http_status=response.status,
                    final_url=response.geturl(),
                    response_headers={
                        k: v
                        for k, v in response.headers.items()
                        if k.lower()
                        in ("content-type", "last-modified", "etag", "date", "content-length")
                    },
                )
            if urllib.parse.urlparse(result["final_url"]).hostname != "www.nhc.noaa.gov":
                raise ValueError("unexpected redirect host")
            if result["http_status"] != 200 or len(body) > MAX_BYTES:
                raise ValueError("HTTP failure or response size exceeded")
            result["status"] = "received"
        except (OSError, ValueError, TimeoutError) as exc:
            result["error"] = type(exc).__name__ + ": " + str(exc)
        finally:
            result["retrieved_at"] = now()
            if body is not None:
                with (directory / "body.html").open("xb") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                result.update(raw_sha256=hashlib.sha256(body).hexdigest(), raw_bytes=len(body))
            write(directory / "result.json", result)
            rows.append(result)
            print(
                {
                    "source_id": item["source_id"],
                    "status": result["status"],
                    "bytes": len(body) if body else 0,
                },
                flush=True,
            )
    write(target / "results.json", rows)
    seal(target)
    return rows


def reconstruct(bundle):
    bundle = Path(bundle)
    scope = verify_scope(bundle)
    verify_seal(bundle / "acquisition")
    records, products, exports, canonical = [], [], {}, {}
    for item in scope["selected"]:
        directory = bundle / "acquisition" / item["source_id"]
        fetched = read(directory / "result.json")
        record = {"source_id": item["source_id"], "status": "quarantined", "reasons": []}
        try:
            if fetched["status"] != "received":
                raise ValueError("source acquisition did not succeed")
            raw = (directory / "body.html").read_bytes()
            if hashlib.sha256(raw).hexdigest() != fetched["raw_sha256"]:
                raise ValueError("raw source digest differs")
            normalized = normalization.normalize(raw)
            first, second = parser_a.parse(raw), parser_b.parse(raw)
            record.update(parser_a=first, parser_b=second)
            if first != second:
                raise ValueError("independent parser disagreement")
            if (
                first["storm_id"] != item["storm_id"]
                or first["advisory_number"] != item["advisory_number"]
            ):
                raise ValueError("body identity differs from requested source")
            products.append(first)
            exports[item["source_id"]] = views.export(first, normalized["text"])
            canonical[item["source_id"]] = normalized
            record.update(
                status="admitted",
                forecast_rows=len(first["forecasts"]),
                raw_sha256=fetched["raw_sha256"],
            )
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            record["reasons"].append(type(exc).__name__ + ": " + str(exc))
        records.append(record)
    pairs = consensus.revision_pairs(products)
    report = {
        "scope_id": scope["scope_id"],
        "planned_bodies": 12,
        "received_bodies": sum(
            read(bundle / "acquisition" / s["source_id"] / "result.json")["status"] == "received"
            for s in scope["selected"]
        ),
        "admitted_bodies": len(products),
        "quarantined_bodies": 12 - len(products),
        "forecast_rows": sum(len(p["forecasts"]) for p in products),
        "same_valid_revision_pairs": len(pairs),
        "wind_changed_pairs": sum(p["wind_change_kt"] not in (None, 0) for p in pairs),
        "independent_storm_sources": len({p["storm_id"] for p in products}),
        "available_at_proved": False,
        "model_initialization_proved": False,
        "model_generations": 0,
        "new_human_gold_annotations": 0,
        "llm_judge": False,
        "two_parsers_are_not_two_independent_weather_sources": True,
        "implementation_files": source_inventory(),
        "records": records,
    }
    return {
        "report": report,
        "products": products,
        "revision_pairs": pairs,
        "views": exports,
        "canonical": canonical,
    }


def review(bundle, output, *, verify=False):
    output = Path(output)
    reconstructed = reconstruct(bundle)
    if verify:
        verify_seal(output)
        for name, value in reconstructed.items():
            if read(output / (name + ".json")) != value:
                raise ValueError("saved source review differs: " + name)
        print({"status": "passed", "model_generations": 0}, flush=True)
        return
    output.mkdir(parents=True, exist_ok=False)
    for name, value in reconstructed.items():
        write(output / (name + ".json"), value)
    snapshot(output / "implementation_source", source_inventory())
    seal(output)
    print(
        {
            k: v
            for k, v in reconstructed["report"].items()
            if k not in ("records", "implementation_files")
        },
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "acquire", "review", "verify"))
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.bundle)
    elif args.command == "acquire":
        acquire(args.bundle)
    else:
        review(args.bundle, args.output, verify=args.command == "verify")


if __name__ == "__main__":
    main()
