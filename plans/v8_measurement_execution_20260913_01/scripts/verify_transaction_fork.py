"""Compare the old and optimized seal on identical real six-hour sessions."""

import importlib.util
import json
import time
from pathlib import Path

from run_program_calendar import configs, load, save

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.policies import run_session

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/transaction_fork_01"


def main():
    OUT.mkdir(exist_ok=False)
    old_path = ROOT / "validation/before_transaction_fork_01/admission.py"
    spec = importlib.util.spec_from_file_location(
        "disastertrace.monitoring_fixed_v1._before_seal", old_path
    )
    old = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = old
    spec.loader.exec_module(old)
    data = load_session(
        ROOT / "development_dataset_v2", stations=["KSFO", "KOAK", "KSJC"], hours=6, threshold=5000
    )
    bank = load(ROOT / "contracts/BANK.json")
    config = configs(6, "base_bound_override")["P04_risk_shared"]
    optimized = AdmissionEngine._transaction_fork
    reports, elapsed = {}, {}
    for key, method in [("before", old.AdmissionEngine.fork), ("after", optimized)]:
        AdmissionEngine._transaction_fork = method
        tick = time.perf_counter()
        cpu = time.process_time()
        report = run_session(data, bank, config)
        elapsed[key] = {
            "wall_seconds": time.perf_counter() - tick,
            "cpu_seconds": time.process_time() - cpu,
        }
        save(OUT / (key + ".json"), report)
        reports[key] = report
    AdmissionEngine._transaction_fork = optimized
    if reports["before"] != reports["after"]:
        raise ValueError("Optimization changed the real complete session report")
    replay = AdmissionEngine.restore(reports["before"]["event_replay"])
    if replay.export() != reports["after"]["event_replay"]:
        raise ValueError("Optimized replay differs from the original history")
    save(
        OUT / "VALIDATION.json",
        {
            "passed": True,
            "opportunities": len(data["opportunities"]),
            "complete_reports_equal": True,
            "old_history_replays_exactly": True,
            "timing": elapsed,
            "speedup_cpu": elapsed["before"]["cpu_seconds"] / elapsed["after"]["cpu_seconds"],
            "timing_limit": "one ordered descriptive pair on a shared two-core CCI, no statistical performance claim",
            "model_calls": 0,
            "frozen_running_experiments_modified": False,
        },
    )
    print(json.dumps(load(OUT / "VALIDATION.json")))


if __name__ == "__main__":
    main()
