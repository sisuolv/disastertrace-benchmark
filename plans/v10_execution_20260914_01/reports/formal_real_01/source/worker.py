"""Small real H15 replay through the mandatory v10 formal entry."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from collections import defaultdict

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, experiment_spec
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.formal_session import FormalSession, required_source_files, score_formal
from disastertrace.monitoring_v1.source_execution import bind_source
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def execute(out):
    data, bank, configs = (read(out / n) for n in ("DATA.json", "BANK.json", "CONFIGS.json"))
    c = read(out / "COMPARISON.json")["payload"]
    comparison = ComparisonContract(c["invariants"], c["allowed_interventions"])
    files = {str(p): digest(p) for p in required_source_files()}
    files.update({str(out / n): digest(out / n) for n in ("DATA.json", "BANK.json", "CONFIGS.json")})
    journals = {}
    for name, config in configs.items():
        session = FormalSession(data, bank, config, comparison=comparison,
                                bound_files=files, directory=out / name)
        report = session.finish(max_steps=80)
        publish(out / name / "REPORT.json", report)
        journals[name] = out / name / "admission.jsonl"
        AdmissionEngine.restore(report["event_replay"]).write_journal(journals[name])
    scores = score_formal(read(out / "OUTCOMES.json"), journals, comparison=comparison)
    publish(out / "SCORES.json", scores)
    publish(out / "RESULT.json", {"passed": True, "arms": list(journals),
        "opportunities": len(data["opportunities"]), "model_calls": 0,
        "scope": "real native H15 archive, provider-bound formal program entry and full journal replay",
        "timing": "declared program latency; lifecycle contract bound; not provider compute measurement",
        "semantics": "measurement.v3", "confirmation_opened": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    out = args.out.absolute()
    if args.execute:
        execute(out)
        return
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    old = root / "plans/v9_followup_execution_20260914_01/api_pilot_01/new_york__2025-01-06__1000"
    data, bank = read(old / "DATA.json"), read(old / "BANK.json")
    first = min(r["cutoff"] for r in data["opportunities"])
    data["opportunities"] = [r for r in data["opportunities"] if r["cutoff"] < first + 6*3600_000_000]
    tids, oids = ({r[k] for r in data["opportunities"]} for k in ("target_id", "opportunity_id"))
    for name in ("targets", "baseline_candidates", "baseline_withdrawals"):
        data[name] = [r for r in data[name] if r["target_id"] in tids]
    data["e_f_pairs"] = [r for r in data["e_f_pairs"] if r["opportunity_id"] in oids]
    base = read(old / "CONFIGS.json")["batch_program"]
    base.update(admission_semantics="measurement.v3", formal_resolution_policy="h15_routine_archive.v1")
    configs, allowed, invariants = {}, defaultdict(list), None
    for protocol in ("base_bound_override", "persistent_override"):
        for arm in ("follow", "batch_program"):
            config = bind_source(bind_execution(dict(base, protocol=protocol,
                acquire=arm != "follow", predict=arm != "follow"), None), None)
            configs[protocol + "__" + arm] = config
            spec = experiment_spec(data, bank, config)
            invariants = invariants or spec["invariants"]
            assert invariants == spec["invariants"]
            for k, v in spec["interventions"].items():
                if v not in allowed[k]:
                    allowed[k].append(v)
    for n, value in (("DATA", data), ("BANK", bank), ("CONFIGS", configs)):
        publish(out / (n + ".json"), value)
    publish(out / "COMPARISON.json", ComparisonContract(invariants, allowed).export())
    publish(out / "OUTCOMES.json", [{**r, "provider": "IEM", "provider_version": "native_h15_snapshot.v1"}
        for r in read(old / "OUTCOMES.json") if r["opportunity_id"] in oids])
    package = root / "disastertrace-starter/src/disastertrace"
    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(package / module, out / "source/disastertrace" / module,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (out / "source/disastertrace/__init__.py").write_text('"""Frozen formal preflight."""\n')
    shutil.copyfile(__file__, out / "source/worker.py")
    publish(out / "FREEZE.json", {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()})
    result = subprocess.run([sys.executable, str(out / "source/worker.py"), "--out", str(out), "--execute"],
        env=dict(os.environ, PYTHONPATH=str(out / "source"), PYTHONDONTWRITEBYTECODE="1"))
    publish(out / "EXIT.json", {"exit_code": result.returncode})
    print(json.dumps({"exit_code": result.returncode, "out": str(out)}))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
