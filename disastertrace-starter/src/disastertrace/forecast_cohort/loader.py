"""Reconstruct the complete P10 review from original bytes before compilation."""

from pathlib import Path

from disastertrace.forecast_catalog import parser_a
from disastertrace.forecast_source import normalization, parser_b
from disastertrace.forecast_task.common import digest, fingerprint, read, verify
from disastertrace.forecast_task.compiler import compile_sources

STORMS = ("AL052019", "AL092020", "AL082021", "AL072022", "AL132023", "AL092024")
PROTECTED = (
    "AL022024",
    "AL092022",
    "AL102023",
    "AL112017",
    "AL132020",
    "AL142016",
    "AL142018",
    "AL152017",
)


def contained(root, name):
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("source path must be relative and contained")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("source path escaped review")
    return path


def load_sources(root):
    root = Path(root)
    manifest = verify(root)
    original = verify(root / "original_sources")
    source = verify(root / "source")
    scope, claim = read(root / "ACQUISITION_CLAIM.json"), read(root / "CLAIM.json")
    if scope["scope_id"] != fingerprint({k: v for k, v in scope.items() if k != "scope_id"}):
        raise ValueError("acquisition scope identity differs")
    if (
        claim["scope_id"] != scope["scope_id"]
        or claim["source_package_id"] != original["package_id"]
        or claim["catalogue_sha256"] != digest(root / "CATALOGUE_RESULT.json")
        or sorted(scope["protected_heldout_ids"]) != list(PROTECTED)
    ):
        raise ValueError("review lineage or heldout protection differs")
    for module in (normalization, parser_a, parser_b):
        name = module.__name__.replace(".", "/") + ".py"
        if digest(module.__file__) != source["files"][name]:
            raise ValueError("parser differs from reviewed implementation")
    expected = {(storm, number) for storm in STORMS for number in range(1, 7)}
    selected = scope["selected"]
    if (
        len(selected) != 36
        or {(s["storm_id"], s["advisory_number"]) for s in selected} != expected
        or any(s["split"] != "development" or s["storm_id"] in PROTECTED for s in selected)
    ):
        raise ValueError("fixed development source population differs")
    ids = [s["source_id"] for s in selected]
    if len(set(ids)) != 36:
        raise ValueError("duplicate source identity")
    report = read(root / "REVIEW_RESULT.json")
    inputs = read(root / "compiler_inputs.json")
    records = report["results"]
    if (
        len(records) != 36
        or [r["source_id"] for r in records] != ids
        or len(inputs) != 36
        or [s["source_id"] for s in inputs] != ids
        or report["planned_products"] != 36
        or report["admitted_products"] != 36
        or any(r["status"] != "admitted" for r in records)
    ):
        raise ValueError("complete admitted source denominator differs")
    loaded = []
    for item, entry, record in zip(selected, inputs, records):
        sid = item["source_id"]
        if (
            sid != f"{item['storm_id'].lower()}-fstadv-{item['advisory_number']:03d}"
            or any(entry[k] != v for k, v in item.items())
            or entry["available_at"] is not None
        ):
            raise ValueError("source identity or availability assertion differs")
        paths = {
            "raw_path": f"original_sources/{sid}/raw.html",
            "product_path": f"products/{sid}.json",
            "canonical_path": f"canonical/{sid}.json",
        }
        for key, expected_path in paths.items():
            contained(root, entry[key])
            if entry[key] != expected_path:
                raise ValueError("source file binding differs")
        fetched = read(root / "original_sources" / sid / "result.json")
        raw_path = contained(root, entry["raw_path"])
        raw = raw_path.read_bytes()
        if (
            fetched["http_status"] != 200
            or fetched["body_sha256"] != digest(raw_path)
            or fetched["body_bytes"] != len(raw)
            or fetched["url"] != item["url"]
            or fetched["final_url"] != item["url"]
            or fetched["retrieved_at"] != entry["retrieved_at"]
        ):
            raise ValueError("original acquisition provenance differs")
        first, second = parser_a.parse(raw), parser_b.parse(raw)
        canonical = normalization.normalize(raw)
        if (
            first != second
            or first != read(contained(root, entry["product_path"]))
            or fingerprint(first) != record["product_sha256"]
            or canonical != read(contained(root, entry["canonical_path"]))
            or (first["storm_id"], first["advisory_number"])
            != (item["storm_id"], item["advisory_number"])
        ):
            raise ValueError("independent source reconstruction differs")
        if fetched["status"] != record["legacy_status"]:
            raise ValueError("historical parser failure accounting differs")
        loaded.append(
            {
                "source_id": sid,
                "product": first,
                "canonical": canonical,
                "raw": raw,
                "retrieved_at": entry["retrieved_at"],
                "url": item["url"],
            }
        )
    return loaded, {
        "scope_id": scope["scope_id"],
        "review_package_id": manifest["package_id"],
        "acquisition_package_id": original["package_id"],
        "planned_products": 36,
        "admitted_products": 36,
        "quarantined_products": [],
        "historical_parser_failures": sum(r["legacy_status"] != "admitted" for r in records),
        "protected_heldout_ids": list(PROTECTED),
        "split": "development",
        "historical_availability": "unknown",
        "probability_sample": False,
    }


def compile_bundle(root):
    return compile_sources(*load_sources(root))
