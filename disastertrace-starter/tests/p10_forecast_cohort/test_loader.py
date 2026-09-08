import shutil
from pathlib import Path

import pytest

from disastertrace.forecast_cohort.loader import STORMS, compile_bundle, contained, load_sources
from disastertrace.forecast_cohort.protocol import schedule
from disastertrace.forecast_task.common import canonical, fingerprint, inventory, read
from disastertrace.forecast_task.diagnostics import collect_program
from disastertrace.forecast_task.scoring import summarize

ROOT = Path(__file__).resolve().parents[2] / "artifacts/p10_source_catalog_v1/review_v2"


@pytest.fixture(scope="module")
def compiled():
    return compile_bundle(ROOT)


def test_all_original_sources_and_parser_failures_accounted():
    sources, identity = load_sources(ROOT)
    assert len(sources) == 36
    assert identity["historical_parser_failures"] == 10
    assert {s["product"]["storm_id"] for s in sources} == set(STORMS)


@pytest.mark.parametrize("name", ["../secret", "/tmp/secret", "a/../../secret"])
def test_external_source_path_rejected(tmp_path, name):
    with pytest.raises(ValueError, match="relative and contained"):
        contained(tmp_path, name)


def test_public_only_resolver_covers_every_expanded_query(compiled):
    public = compiled["public"]
    slots = schedule(public)
    assert len(slots) == 3 * len(public["opportunities"])
    assert {s["repeat"] for s in slots} == {0}
    captures, _ = collect_program(public, slots, "latest_explicit")
    score = summarize(slots, captures, public, compiled["private_reference"])
    assert score["counts"]["all_correct"] == len(slots)


def test_future_cutoff_and_controlled_availability_are_retained(compiled):
    private = compiled["private_reference"]
    for item in compiled["candidates"]:
        assert item["included"] == (item["query"]["valid_at"] > item["forecast_reference_at"])
    assert all(s["available_at"] is None for s in private["sources"].values())
    assert all(s["initialization_at"] is None for s in private["sources"].values())
    assert compiled["dataset"]["counts"]["source_revision_pairs"] == 138


@pytest.mark.parametrize(
    "mutation", ["missing_input", "availability", "traversal", "product", "old_failure"]
)
def test_resealed_forged_review_cannot_replace_original_semantics(tmp_path, mutation):
    root = tmp_path / "review"
    shutil.copytree(ROOT, root)
    inputs = read(root / "compiler_inputs.json")
    if mutation == "missing_input":
        inputs.pop()
    elif mutation == "availability":
        inputs[0]["available_at"] = inputs[0]["retrieved_at"]
    elif mutation == "traversal":
        inputs[0]["raw_path"] = "../raw.html"
    elif mutation == "product":
        path = root / inputs[0]["product_path"]
        product = read(path)
        product["forecasts"][0]["max_sustained_wind_kt"] += 1
        path.write_text(canonical(product))
    else:
        path = root / "REVIEW_RESULT.json"
        report = read(path)
        report["results"][0]["legacy_status"] = "failed"
        path.write_text(canonical(report))
    (root / "compiler_inputs.json").write_text(canonical(inputs))
    manifest = {
        "schema_version": "forecast_task_package_v1",
        "files": inventory(root, ("manifest.json",)),
    }
    manifest["package_id"] = fingerprint(manifest)
    (root / "manifest.json").write_text(canonical(manifest))
    with pytest.raises(ValueError):
        load_sources(root)
