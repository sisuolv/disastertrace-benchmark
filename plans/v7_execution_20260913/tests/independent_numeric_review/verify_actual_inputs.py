"""Independent actual-data separation and numerical score checks, without inference."""
import hashlib
import json
import statistics
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CYCLE = ROOT / "plans/v7_execution_20260913"


def load(path):
    return json.loads(path.read_text())


def forbid_hidden_keys(value):
    if isinstance(value, dict):
        assert not set(value) & {"outcome", "evaluator_only", "gold", "gold_mask", "expected_e"}
        for item in value.values():
            forbid_hidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            forbid_hidden_keys(item)


def main():
    matrix = CYCLE / "evidence_bundle/matrix_01"
    manifest = load(matrix / "MANIFEST.json")
    asset_count = 0
    for row in manifest:
        envelope = load(matrix / "policy" / (row["call_id"] + ".json"))
        bundle = EvidenceBundle.restore(envelope)
        assert bundle.bundle_hash == row["bundle_hash"]
        visible = bundle.policy_view()
        forbid_hidden_keys(visible)
        target_id = visible["target"]["target_id"]
        for asset in visible["assets"]:
            assert asset["entitlements"] == [target_id]
            assert asset["completed_at"] <= visible["cutoff"]
            for report in asset["content"].get("reports", []):
                assert report["observation_time"] <= visible["cutoff"]
            asset_count += 1
    numeric = CYCLE / "evidence_bundle/numerical_01"
    input_file = CYCLE / "sources_numerical/paired_records.json"
    source = load(input_file)
    output = load(numeric / "REPORT.json")
    assert output["input_sha256"] == hashlib.sha256(input_file.read_bytes()).hexdigest()
    originals = {r["record_id"]: r for r in source["records"] if r["lead_hours"] > 0}
    labels = load(numeric / "evaluator/OUTCOMES.json")
    predictions = load(numeric / "PREDICTIONS.json")
    assert {r["opportunity_id"] for r in labels} == set(originals)
    mae = {}
    for name, reducer in [("ensemble_mean", statistics.mean), ("ensemble_median", statistics.median)]:
        errors = []
        for rid, record in originals.items():
            policy = load(numeric / "policy" / (rid + ".json"))
            forbid_hidden_keys(policy)
            assert record["station_id"] == 460
            assert policy["forecast_members"] == record["model_visible"]["forecast_members"]
            assert policy["target"]["support_kind"] == "point"
            assert policy["target"]["physical_start"] == policy["target"]["physical_end"]
            expected = reducer(record["model_visible"]["forecast_members"])
            assert predictions[name][rid]["value"] == expected
            assert policy["publication_time"] is None
            errors.append(abs(expected - record["evaluator_only"]["observation"]))
        mae[name] = statistics.mean(errors)
        assert abs(mae[name] - output["scores"]["arms"][name]["mean_loss"]) < 1e-12
    assert not output["active_monitoring_qualified"]
    assert not output["historical_online_availability_verified"]
    result = {"frozen_aviation_bundles_checked": len(manifest), "lawful_private_assets_checked": asset_count,
              "numerical_positive_lead_pairs_checked": len(originals), "numerical_mae_K_independently_recomputed": mae,
              "observed_hidden_key_or_future_observation_leak": False,
              "source_and_report_admission_gates_overstated": False,
              "new_model_calls": 0, "modified_frozen_modules": False}
    (HERE / "ACTUAL_INPUT_RESULTS.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
