"""Independent checks after the integration-edge repair; no new inference."""

import copy
import hashlib
import json
import runpy
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Forecast,
    ForecastState,
    Target,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    rows = []
    for semantics, start, end, release in [
        ("future_physical", 100, 100, None),
        ("future_product_release", 80, 80, 100),
        ("partial_window_nowcast", 80, 100, None),
    ]:
        target = Target(
            "t", "station:A", "temperature", "K", "scalar",
            "point" if start == end else "interval", start, end,
            semantics, "native.v1", release_event_at=release,
        )
        for protocol in ("base_bound_override", "persistent_override"):
            state = ForecastState(target, protocol)
            initial = Forecast(target.contract_hash, "scalar", "K", 270)
            changed = Forecast(target.contract_hash, "scalar", "K", 280)
            assert state.update_baseline(initial, "b1", 70) == "accepted"
            assert state.update_baseline(changed, "b2", 100) == "invalid_target_time"
            assert state.effective(100) == initial
            assert state.events[-1]["kind"] == "base_rejected"
            assert ForecastState.restore(state.to_dict()).to_dict() == state.to_dict()
            rows.append({"semantics": semantics, "protocol": protocol,
                         "late_baseline_rejected_and_replay_preserved": True,
                         "earlier_baseline_retained": True})

    fixture = ROOT / "plans/v7_execution_20260913/tests/test_fixed_contracts.py"
    record = runpy.run_path(str(fixture))["bundle_record"]()
    parent = record["assets"][0]
    child = copy.deepcopy(parent)
    child.update(asset_id="derived", parents=[parent["asset_id"]],
                 available_at=0, observed_at=None, completed_at=85)
    record["assets"].append(child)
    try:
        EvidenceBundle.freeze(record)
    except ValueError as error:
        assert "availability predates parent" in str(error)
    else:
        raise AssertionError("Derived availability regression remains accepted")
    child["available_at"] = parent["available_at"]
    EvidenceBundle.freeze(record)

    matrix = ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01"
    manifest = json.loads((matrix / "MANIFEST.json").read_text())
    asset_count = parent_edges = 0
    for item in manifest:
        frozen = json.loads((matrix / "policy" / (item["call_id"] + ".json")).read_text())
        bundle = EvidenceBundle.restore(frozen)
        assert bundle.bundle_hash == item["bundle_hash"]
        visible = bundle.policy_view()
        target = Target(**visible["target"])
        target.check_cutoff(visible["cutoff"])
        base = visible["baseline"]
        state = ForecastState(target, visible["state"]["protocol"])
        assert state.update_baseline(
            Forecast(**base["forecast"]), base["source_revision"], base["available_at"]
        ) == "accepted"
        assets = {a["asset_id"]: a for a in visible["assets"]}
        for asset in assets.values():
            for pid in asset["parents"]:
                assert assets[pid]["available_at"] <= asset["available_at"]
                parent_edges += 1
            asset_count += 1
    source = ROOT / "disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py"
    result = {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "scope": "independent synthetic repair checks and existing real-input compatibility",
        "baseline_checks": rows,
        "derived_availability_regression_rejected": True,
        "same_parent_available_at_accepted": True,
        "actual_bundles_checked": len(manifest),
        "actual_assets_checked": asset_count,
        "actual_derived_edges": parent_edges,
        "actual_baselines_accepted": len(manifest),
        "actual_bundle_hashes_unchanged": True,
        "new_model_calls": 0,
        "frozen_inputs_modified": False,
    }
    with (HERE / "REPAIRED_BOUNDARY_RESULTS.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
