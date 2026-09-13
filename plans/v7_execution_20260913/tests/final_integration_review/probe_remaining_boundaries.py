"""Synthetic integration-edge probes; do not mutate source or frozen inputs."""
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
    paired_scores,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    t = Target("t", "station:A", "temperature", "K", "scalar", "point", 100, 100,
               "future_physical", "native_instant.v1")
    state = ForecastState(t, "base_bound_override")
    state.update_baseline(Forecast(t.contract_hash, "scalar", "K", 270), "b1", 90)
    state.update_baseline(Forecast(t.contract_hash, "scalar", "K", 280), "b2", 101)
    cutoff_rejected = False
    try:
        t.check_cutoff(101)
    except ValueError:
        cutoff_rejected = True
    scores = paired_scores(
        [{"opportunity_id": "o", "target": t.to_dict(), "outcome": 280}],
        {"late_baseline": {"o": state.effective(101).to_dict()}},
    )

    fixture = ROOT / "plans/v7_execution_20260913/tests/test_fixed_contracts.py"
    record = runpy.run_path(str(fixture))["bundle_record"]()
    parent = record["assets"][0]
    child = copy.deepcopy(parent)
    child.update(asset_id="derived", parents=[parent["asset_id"]],
                 available_at=0, observed_at=None, completed_at=85)
    record["assets"].append(child)
    accepted = EvidenceBundle.freeze(record)
    source = ROOT / "disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py"
    result = {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "scope": "synthetic integration counterexamples, not actual benchmark failures",
        "late_baseline_update": {
            "target_check_cutoff_rejected": cutoff_rejected,
            "state_update_baseline_accepted": state.effective(101).value == 280,
            "scorer_accepts_forecast_without_emission_time": scores["arms"]["late_baseline"]["mean_loss"] == 0,
            "required_interpretation": "Scorer/reducer require an external temporal admission guard for baselines"},
        "derived_available_at": {
            "parent_available_at": parent["available_at"], "child_available_at": child["available_at"],
            "child_completed_at": child["completed_at"], "cutoff": record["cutoff"],
            "accepted_bundle_hash": accepted.bundle_hash,
            "future_content_leak_demonstrated": False,
            "required_interpretation": "Visibility completion is guarded, but a derived source can currently declare impossible availability age"},
        "existing_snapshots_modified": False,
    }
    with (HERE / "BOUNDARY_RESULTS.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
