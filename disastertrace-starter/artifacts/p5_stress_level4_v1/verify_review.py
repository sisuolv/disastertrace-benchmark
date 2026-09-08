"""Rebuild P4/P5 reports and postprocessing in a relocated CPU-only project."""

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copy", type=Path, required=True)
    parser.add_argument("--original-project", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    args = parser.parse_args()
    copy = args.copy.resolve()
    blocked = (args.original_project.resolve(), args.model_directory.resolve())

    def guard(event, fields):
        if event == "open" and isinstance(fields[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(fields[0])).resolve()
            if not path.is_relative_to(copy) and any(path.is_relative_to(root) for root in blocked):
                raise RuntimeError("CPU review attempted original data/weight access")
        if event == "socket.connect":
            raise RuntimeError("CPU review attempted network access")

    sys.addaudithook(guard)
    assert importlib.util.find_spec("torch") is None
    assert importlib.util.find_spec("vllm") is None
    bundle = copy / "artifacts/p5_stress_level4_v1"
    sys.path.insert(0, str(bundle))
    import analyze_p5
    import compare_stress

    from disastertrace.constrained_eval import audit as base_audit
    from disastertrace.local_eval.storage import now, read, write
    from disastertrace.stress_eval import audit

    base = copy / "artifacts/p4_constrained_output_v1"
    base_run = copy / "work/p4-qwen3-constrained-v1"
    before = base_audit.report(
        base / "execution_live", base_run, base / "model_report", require_model=True, verify=True
    )
    units, runs = {}, {}
    for factor in compare_stress.FACTORS:
        unit = bundle / "units" / factor
        run = copy / "work" / ("p5-qwen3-" + factor.replace("_", "-") + "-v1")
        units[factor] = audit.report(
            unit / "execution_live", run, unit / "model_report", require_model=True, verify=True
        )
        runs[factor] = run
    comparison = compare_stress.generate(base_run, runs)
    if comparison != read(bundle / "stress_comparison/comparison.json"):
        raise ValueError("relocated comparison differs")
    analysis, tables = analyze_p5.generate(copy / "work")
    if (
        analysis != read(bundle / "analysis/analysis.json")
        or tables != (bundle / "analysis/RESULT_TABLES.md").read_text()
    ):
        raise ValueError("relocated analysis differs")
    result = {
        "status": "passed",
        "at": now(),
        "base": before,
        "units": units,
        "analysis_id": analysis["analysis_id"],
        "comparison_id": comparison["comparison_id"],
        "relocated": True,
        "original_data_and_weights_blocked": True,
        "network_blocked": True,
        "torch_and_vllm_absent": True,
        "additional_model_calls": 0,
    }
    write(copy / "verification_result.json", result)
    print(result)


if __name__ == "__main__":
    main()
