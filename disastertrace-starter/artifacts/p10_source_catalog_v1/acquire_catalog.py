"""Bounded official NHC development sources; immutable raw capture and two frozen parsers."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.error
import urllib.request

from disastertrace.forecast_live.storage import now, write
from disastertrace.forecast_source import normalization, parser_a, parser_b
from disastertrace.forecast_task.common import digest, fingerprint, read, seal

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 2 * 1024 * 1024
STORMS = (("AL052019", "DORIAN"), ("AL092020", "ISAIAS"), ("AL082021", "HENRI"),
          ("AL072022", "FIONA"), ("AL132023", "LEE"), ("AL092024", "HELENE"))


def collect(item):
    folder = ROOT / "sources" / item["source_id"]
    folder.mkdir(parents=True, exist_ok=False)
    write(folder / "intent.json", {"at": now(), **item})
    record = {**item, "status": "failed", "retrieved_at": None, "model_calls": 0}
    try:
        request = urllib.request.Request(item["url"], headers={"User-Agent": "DisasterTrace-source-catalog/1"})
        try:
            response = urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(MAX_BYTES + 1)
            with (folder / "raw.html").open("xb") as stream:
                stream.write(body)
            record.update(retrieved_at=now(), http_status=response.status, final_url=response.geturl(),
                          body_bytes=len(body), body_sha256=digest(folder / "raw.html"))
        if len(body) > MAX_BYTES or record["http_status"] != 200:
            raise ValueError("body exceeds bound or HTTP status is not200")
        if record["final_url"] != item["url"]:
            raise ValueError("unexpected redirect requires separate source review")
        parsed = []
        for label, parser in (("a", parser_a), ("b", parser_b)):
            try:
                value = parser.parse(body)
                outcome = {"status": "passed", "product": value}
            except Exception as exc:
                value = None
                outcome = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            write(folder / ("parser_" + label + ".json"), outcome)
            parsed.append(value)
        if parsed[0] is None or parsed[1] is None or parsed[0] != parsed[1]:
            raise ValueError("two frozen source parsers fail or disagree")
        product = parsed[0]
        if product["storm_id"] != item["storm_id"] or product["advisory_number"] != item["advisory_number"]:
            raise ValueError("source identity differs from predeclared product")
        canonical = normalization.normalize(body)
        write(folder / "canonical.json", canonical)
        write(folder / "product.json", product)
        record.update(status="admitted", issued_at=product["issued_at"], center_at=product["center_at"],
                      available_at=None, forecast_rows=len(product["forecasts"]),
                      terminal_rows=sum(r["terminal_status"] is not None for r in product["forecasts"]))
    except Exception as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
    write(folder / "result.json", record)
    print({k: v for k, v in record.items() if k not in ("url", "final_url")}, flush=True)
    return record


def main():
    project = ROOT.parents[1]
    original = read(project / "artifacts/nhc_forecast_source_v1/SOURCE_SCOPE.json")
    protected = original["protected_heldout_ids"]
    if set(protected) & {storm for storm, _ in STORMS} or len(set(storm for storm, _ in STORMS)) != 6:
        raise ValueError("storm overlap or protected heldout source requested")
    selected = []
    for storm, name in STORMS:
        for number in range(1, 7):
            selected.append({"storm_id": storm, "storm_name": name, "advisory_number": number,
                    "source_id": storm.lower() + f"-fstadv-{number:03d}", "split": "development",
                    "url": f"https://www.nhc.noaa.gov/archive/{storm[-4:]}/{storm[:4].lower()}/{storm.lower()}.fstadv.{number:03d}.shtml"})
    claim = {"at": now(), "planned_bodies": 36, "max_bytes_per_body": MAX_BYTES, "automatic_retries": 0,
             "parallel_downloads": 2, "model_generations": 0, "gpu_jobs": 0, "selected": selected,
             "protected_heldout_ids": protected, "original_scope_sha256": digest(project / "artifacts/nhc_forecast_source_v1/SOURCE_SCOPE.json"),
             "plan_sha256": digest(ROOT / "PLAN.md"), "script_sha256": digest(__file__),
             "parser_source_sha256": {name: digest(Path(module.__file__)) for name, module in
                                        (("parser_a", parser_a), ("parser_b", parser_b), ("normalization", normalization))}}
    claim["scope_id"] = fingerprint(claim)
    write(ROOT / "ACQUISITION_CLAIM.json", claim)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(collect, selected))
    (ROOT / "analysis").mkdir()
    storms = []
    for storm, _ in STORMS:
        admitted = [r for r in results if r["storm_id"] == storm and r["status"] == "admitted"]
        products = [read(ROOT / "sources" / r["source_id"] / "product.json") for r in admitted]
        rows = [row for product in products for row in product["forecasts"]]
        matches = []
        for first, second in zip(products, products[1:]):
            if second["advisory_number"] != first["advisory_number"] + 1:
                continue
            before = {r["valid_at"]: r for r in first["forecasts"]}
            for row in second["forecasts"]:
                if row["valid_at"] in before:
                    previous = before[row["valid_at"]]
                    matches.append({"storm_id": storm, "before_advisory": first["advisory_number"],
                        "after_advisory": second["advisory_number"], "valid_at": row["valid_at"],
                        "wind_changed": row["max_sustained_wind_kt"] != previous["max_sustained_wind_kt"],
                        "coordinates_changed": (row["latitude"], row["longitude"]) != (previous["latitude"], previous["longitude"])})
        write(ROOT / "analysis" / (storm + "_adjacent_matches.json"), matches)
        storms.append({"storm_id": storm, "planned_products": 6, "admitted_products": len(products),
                       "forecast_rows": len(rows), "terminal_rows": sum(r["terminal_status"] is not None for r in rows),
                       "unique_valid_times": len({r["valid_at"] for r in rows}), "adjacent_same_valid_time_matches": len(matches),
                       "wind_changes": sum(m["wind_changed"] for m in matches),
                       "qualifiers": dict(Counter(r["qualifier"] for r in rows))})
    record = {"status": "catalogued_with_all_failures_retained", "scope_id": claim["scope_id"],
              "planned_products": 36, "admitted_products": sum(r["status"] == "admitted" for r in results),
              "storms": storms, "results": results, "model_calls": 0, "gpu_jobs": 0, "completed_at": now()}
    write(ROOT / "CATALOGUE_RESULT.json", record)
    seal(ROOT / "sources")
    print({k: v for k, v in record.items() if k not in ("results", "storms")}, flush=True)


if __name__ == "__main__":
    main()
