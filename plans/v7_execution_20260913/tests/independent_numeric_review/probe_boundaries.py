"""Independent, non-mutating boundary probes of the frozen typed reducer."""
import hashlib
import json
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import Forecast, ForecastState, Target

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def target(semantics, support, start, end, release=None):
    return Target("test", "station:test", "temperature", "K", "scalar", support,
                  start, end, semantics, "test_product.v1", release_event_at=release)


def boundary_probe(t, base_at, proposal_at):
    base = Forecast(t.contract_hash, "scalar", "K", 270)
    candidate = Forecast(t.contract_hash, "scalar", "K", 280)
    state = ForecastState(t, "base_bound_override")
    state.update_baseline(base, "b1", base_at)
    rejected_by_target = False
    try:
        t.check_cutoff(proposal_at)
    except ValueError:
        rejected_by_target = True
    status = state.propose(candidate, "b1", proposal_at, proposal_at + 10)
    return {"temporal_semantics": t.temporal_semantics, "proposal_at": proposal_at,
            "target_check_cutoff_rejected": rejected_by_target, "state_propose_status": status,
            "effective_value": state.effective(proposal_at).value,
            "replay_preserves_late_acceptance": ForecastState.restore(state.to_dict()).effective(proposal_at).value == candidate.value}


def main():
    source = ROOT / "disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py"
    probes = [boundary_probe(target("future_physical", "point", 100, 100), 90, 100),
              boundary_probe(target("future_product_release", "interval", 10, 20, 30), 25, 30),
              boundary_probe(target("partial_window_nowcast", "interval", 10, 20), 12, 20)]
    report = {"module_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "kind": "synthetic_contract_boundary_counterexamples_not_GPU_failures",
              "finding": "ForecastState.propose does not enforce Target.check_cutoff; callers currently must do so",
              "cases": probes, "existing_frozen_inputs_mutated": False}
    (HERE / "BOUNDARY_RESULTS.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
