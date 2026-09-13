"""Check current reducer fixes; preserve all original frozen review artifacts."""
import ast
import hashlib
import json
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Forecast,
    ForecastState,
    Target,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CYCLE = ROOT / "plans/v7_execution_20260913"


def target(semantics, support, start, end, release=None):
    return Target("test", "station:test", "temperature", "K", "scalar", support,
                  start, end, semantics, "test_product.v1", release_event_at=release)


def check_boundary(t, base_at, at):
    state = ForecastState(t, "base_bound_override")
    state.update_baseline(Forecast(t.contract_hash, "scalar", "K", 270), "b1", base_at)
    before = state.effective(base_at).to_dict()
    status = state.propose(Forecast(t.contract_hash, "scalar", "K", 280), "b1", at, at + 10)
    assert status == "invalid_target_time"
    assert state.effective(at).to_dict() == before
    replay = ForecastState.restore(state.to_dict())
    assert replay.events[-1]["status"] == status
    assert replay.effective(at).to_dict() == before
    return {"semantics": t.temporal_semantics, "at": at, "status": status,
            "baseline_preserved": True, "durable_replay_verified": True}


def main():
    results = [check_boundary(target("future_physical", "point", 100, 100), 90, 100),
               check_boundary(target("future_product_release", "interval", 10, 20, 30), 25, 30),
               check_boundary(target("partial_window_nowcast", "interval", 10, 20), 12, 20)]
    t = target("future_physical", "point", 100, 100)
    state = ForecastState(t, "base_bound_override")
    state.update_baseline(Forecast(t.contract_hash, "scalar", "K", 270), "same_id", 80)
    original = state.to_dict()
    try:
        state.update_baseline(Forecast(t.contract_hash, "scalar", "K", 280), "same_id", 90)
    except ValueError:
        pass
    else:
        raise AssertionError("Same baseline identity changed its value")
    assert state.to_dict() == original and state.now == 80

    gpu = CYCLE / "gpu"
    parser_path = gpu / "verify_fact_truth.py"
    tree = ast.parse(parser_path.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "parse_fact_response")
    mapping_tree = ast.parse((gpu / "fact_truth_probe.py").read_text())
    mapping_assignment = next(node for node in mapping_tree.body if isinstance(node, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == "TRUTH_TO_SUPPORT" for t in node.targets))
    mapping = ast.literal_eval(mapping_assignment.value)
    assert mapping == {"true": "supported", "false": "refuted", "unknown": "undetermined", "conflict": "inconsistent"}
    namespace = {"json": json, "Forecast": Forecast, "TRUTH_TO_SUPPORT": mapping}
    # Run only the reviewed parser AST, avoiding a GPU-runtime import during this CPU check.
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(parser_path), "exec"), namespace)  # noqa: S102
    parser = namespace["parse_fact_response"]
    policy_file = min((CYCLE / "evidence_bundle/matrix_01/policy").glob("*.json"))
    bundle = EvidenceBundle.restore(json.loads(policy_file.read_text()))
    parser_checks = 0
    for truth, support in mapping.items():
        for variant in ["explicit_truth_E_only", "explicit_truth_joint_EF"]:
            response = {"fact_truth": truth}
            if variant.endswith("joint_EF"):
                response["probability"] = 0.25
            _, result = parser(json.dumps(response), bundle, variant)
            assert result == support
            parser_checks += 1
    for value in [True, False, 1, None]:
        try:
            parser(json.dumps({"fact_truth": value}), bundle, "explicit_truth_E_only")
        except ValueError:
            parser_checks += 1
        else:
            raise AssertionError("Non-string fact truth accepted")
    rows = json.loads((gpu / "fact_truth_verification_01/ROWS.json").read_text())
    report = json.loads((gpu / "fact_truth_verification_01/REPORT.json").read_text())
    e_only = [r for r in rows if r["prompt_variant"] == "explicit_truth_E_only"]
    assert len(e_only) == 144
    assert all(r["model"] is None and r["model_gain"] is None and r["forecast_submitted"] is False for r in e_only)
    assert all(not r["mean_brier"] and not r["mean_gain"] for key, r in report["summary"].items() if "/explicit_truth_E_only/" in key)
    counts = {}
    for variant in {r["prompt_variant"] for r in rows}:
        group = [r for r in rows if r["prompt_variant"] == variant]
        assert all(r["e_correct"] == (r["model_e"] == r["expected_e"]) for r in group)
        counts[variant] = {"rows": len(group), "E_correct": sum(r["e_correct"] for r in group)}
    source_paths = [ROOT / "disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py",
                    parser_path, gpu / "fact_truth_probe.py",
                    gpu / "fact_truth_probe_01/source/fact_truth_probe.py"]
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    assert source_paths[2].read_bytes() == source_paths[3].read_bytes()
    output = {"boundary_cases": results, "same_base_identity_change_rejected_without_state_mutation": True,
              "fact_truth_parser_cases_passed": parser_checks, "E_only_F_omission_verified_rows": len(e_only),
              "fact_truth_E_counts_independently_recomputed": counts,
              "current_fact_truth_mapping_matches_frozen_capture_source": True,
              "sources": sources, "old_review_artifacts_overwritten": False, "new_model_calls": 0}
    with (HERE / "RESULTS_VERIFIED.json").open("x") as stream:
        json.dump(output, stream, indent=2)
        stream.write("\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
