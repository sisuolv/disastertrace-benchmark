"""Re-review existing source bytes with the versioned center-header grammar extension."""

from collections import Counter, defaultdict
from pathlib import Path
import shutil

from disastertrace.forecast_catalog import parser_a
from disastertrace.forecast_live.storage import now, write
from disastertrace.forecast_source import normalization, parser_b
from disastertrace.forecast_task.common import digest, fingerprint, read, seal, verify

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def main():
    source_manifest = verify(ROOT / "sources")
    catalogue = read(ROOT / "CATALOGUE_RESULT.json")
    scope = read(ROOT / "ACQUISITION_CLAIM.json")
    output = ROOT / "review_v2"
    output.mkdir(exist_ok=False)
    write(output / "CLAIM.json", {"at": now(), "script_sha256": digest(__file__),
          "source_package_id": source_manifest["package_id"], "scope_id": scope["scope_id"],
          "catalogue_sha256": digest(ROOT / "CATALOGUE_RESULT.json"), "new_downloads": 0, "model_calls": 0,
          "parser_a_sha256": digest(parser_a.__file__), "parser_b_sha256": digest(parser_b.__file__)})
    for name in ("PLAN.md", "ACQUISITION_CLAIM.json", "CATALOGUE_RESULT.json"):
        shutil.copyfile(ROOT / name, output / name)
    shutil.copytree(ROOT / "sources", output / "original_sources")
    names = ("disastertrace/__init__.py", "disastertrace/forecast_catalog/__init__.py", "disastertrace/forecast_catalog/parser_a.py",
             "disastertrace/forecast_source/__init__.py", "disastertrace/forecast_source/normalization.py", "disastertrace/forecast_source/parser_b.py",
             "disastertrace/forecast_task/__init__.py", "disastertrace/forecast_task/common.py", "disastertrace/forecast_live/__init__.py",
             "disastertrace/forecast_live/storage.py")
    for name in names:
        destination = output / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / "src" / name, destination)
    seal(output / "source")
    results, by_storm, inputs = [], defaultdict(list), []
    previous = {r["source_id"]: r for r in catalogue["results"]}
    for item in scope["selected"]:
        sid = item["source_id"]
        record = {"source_id": sid, "storm_id": item["storm_id"], "status": "failed",
                  "legacy_status": previous[sid]["status"]}
        try:
            raw_path = output / "original_sources" / sid / "raw.html"
            raw = raw_path.read_bytes()
            if digest(raw_path) != previous[sid]["body_sha256"] or previous[sid]["http_status"] != 200:
                raise ValueError("received source bytes or HTTP status differ")
            first, second = parser_a.parse(raw), parser_b.parse(raw)
            if first != second or first["storm_id"] != item["storm_id"] or first["advisory_number"] != item["advisory_number"]:
                raise ValueError("extended and independent parser products disagree")
            if item["storm_id"] in scope["protected_heldout_ids"]:
                raise ValueError("protected source in development review")
            if record["legacy_status"] == "admitted" and first != read(output / "original_sources" / sid / "product.json"):
                raise ValueError("previously admitted product semantics changed")
            canonical = normalization.normalize(raw)
            product_path = Path("products") / (sid + ".json")
            canonical_path = Path("canonical") / (sid + ".json")
            write(output / product_path, first)
            write(output / canonical_path, canonical)
            inputs.append({**item, "raw_path": "original_sources/" + sid + "/raw.html",
                           "product_path": product_path.as_posix(), "canonical_path": canonical_path.as_posix(),
                           "retrieved_at": previous[sid]["retrieved_at"], "available_at": None})
            by_storm[item["storm_id"]].append((sid, first))
            record.update(status="admitted", product_sha256=fingerprint(first))
        except Exception as exc:
            record["error"] = type(exc).__name__ + ": " + str(exc)
        results.append(record)
    coverage = []
    for storm, products in sorted(by_storm.items()):
        keys = defaultdict(list)
        for sid, product in products:
            for row in product["forecasts"]:
                keys[row["valid_at"]].append((sid, product["advisory_number"], product["issued_at"], row))
        revisions = []
        for valid_at, versions in sorted(keys.items()):
            for before, after in zip(versions, versions[1:]):
                if before[2] >= after[2]:
                    raise ValueError("covering versions are not ordered by issue time")
                revisions.append({"valid_at": valid_at, "before_source": before[0], "after_source": after[0],
                    "numbered_advisory_gap": after[1] - before[1],
                    "wind_changed": before[3]["max_sustained_wind_kt"] != after[3]["max_sustained_wind_kt"],
                    "coordinates_changed": (before[3]["latitude"], before[3]["longitude"]) != (after[3]["latitude"], after[3]["longitude"]),
                    "terminal_status_changed": before[3]["terminal_status"] != after[3]["terminal_status"]})
        write(output / "coverage" / (storm + "_successive_covering_revisions.json"), revisions)
        coverage.append({"storm_id": storm, "products": len(products), "unique_target_times": len(keys),
                         "successive_covering_revisions": len(revisions),
                         "advisory_gap_counts": dict(Counter(str(r["numbered_advisory_gap"]) for r in revisions)),
                         "wind_changes": sum(r["wind_changed"] for r in revisions),
                         "coordinate_changes": sum(r["coordinates_changed"] for r in revisions),
                         "terminal_changes": sum(r["terminal_status_changed"] for r in revisions)})
    write(output / "compiler_inputs.json", inputs)
    result = {"status": "reviewed_with_complete_source_accounting", "planned_products": len(scope["selected"]),
              "admitted_products": len(inputs), "legacy_admitted_products": catalogue["admitted_products"],
              "newly_supported_products": sum(r["status"] == "admitted" and r["legacy_status"] != "admitted" for r in results),
              "results": results, "coverage": coverage, "new_downloads": 0, "model_calls": 0,
              "same_valid_time_versions_need_not_be_adjacent_numbered_advisories": True,
              "previous_failures_are_preserved": True, "completed_at": now()}
    write(output / "REVIEW_RESULT.json", result)
    manifest = seal(output)
    print({"status": result["status"], "admitted": len(inputs), "planned": len(scope["selected"]),
           "review_package_id": manifest["package_id"], "new_downloads": 0, "model_calls": 0}, flush=True)


if __name__ == "__main__":
    main()
