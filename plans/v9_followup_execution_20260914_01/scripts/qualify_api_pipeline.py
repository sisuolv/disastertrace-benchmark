"""No-generation checks of real inputs, frozen dispatch and direct program replay."""

import importlib.util
import json
from pathlib import Path
import shutil
import sys

from disastertrace.monitoring_fixed_v1.aviation import AviationProvider
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

from evidence_diagnostic import independent_reference, messages

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
V8 = ROOT.parent / "v8_measurement_execution_20260913_01"
OUT = ROOT / "reports/api_qualification_01"
TRUTH = {"supported": "true", "refuted": "false", "undetermined": "unknown", "inconsistent": "conflict"}


def main():
    OUT.mkdir(exist_ok=False)
    path = ROOT / "scripts/run_api_pilot.py"
    spec = importlib.util.spec_from_file_location("qualification_pilot", path)
    pilot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pilot)
    pilot.OUT = OUT
    for module in ["monitoring_v1", "monitoring_fixed_v1"]:
        shutil.copytree(REPO / "disastertrace-starter/src/disastertrace" / module,
                        OUT / "source/disastertrace" / module, ignore=shutil.ignore_patterns("__pycache__"))
    (OUT / "source/disastertrace/__init__.py").write_text('"""Offline qualification."""\n')
    shutil.copyfile(path, OUT / "source/run_api_pilot.py")
    shutil.copyfile(V8 / "scripts/run_program_calendar.py", OUT / "source/program_reference.py")
    shutil.copyfile(ROOT / "model_catalog/probe_01/deepseek_pricing.body", OUT / "PRICING.html")
    old_bank = V8 / "contracts/BANK.json"
    case, _ = pilot.prepare_case("new_york", "2025-01-06", 5000, bank_path=old_bank)
    dispatch = []
    for arm in ["deepseek-flash__batch_predictor", "deepseek-v4-pro__llm_selector_program"]:
        backend = pilot.backend_for(case, arm)
        config = read(case / "CONFIGS.json")[arm]
        session = SessionCoordinator(read(case / "DATA.json"), read(case / "BANK.json"), config, backend=backend)
        session.step()
        session.persist(case / arm / "checkpoints/dispatch.json")
        requests = list((case / arm / "spool").glob("*.request.json"))
        assert len(requests) == 1
        request = read(requests[0])
        input_upper = sum(len(m["content"].encode()) for m in request["messages"]) + 4096
        assert input_upper <= 32768
        dispatch.append({"arm": arm, "input_byte_allowance": input_upper,
                         "request_sha256": digest(requests[0]), "http_calls": 0,
                         "scope": "unserviced local spool dispatch; no provider request"})
    publish(OUT / "DISPATCH.json", dispatch)
    comparisons = []
    previous = ROOT / "reports/api_program_preflight_01" / case.name
    for arm in ["copy_current", "batch_program"]:
        config = read(case / "CONFIGS.json")[arm]
        report = run_session(read(case / "DATA.json"), read(case / "BANK.json"), config)
        original = read(previous / arm / "REPORT.json")
        for field in ["snapshots", "calls", "resource_spent", "resource_reserved", "actual_model_calls"]:
            assert report[field] == original[field], "Direct/coordinator mismatch: " + field
        publish(OUT / (arm + "_DIRECT_REPORT.json"), report)
        comparisons.append({"arm": arm, "snapshots": len(report["snapshots"]), "equivalent": True})
    publish(OUT / "DIRECT_EQUIVALENCE.json", comparisons)
    references = []
    for region in ["bay", "new_york", "chicago", "denver"]:
        dataset = V8 / "calendar_extension_01/dataset_v2_complete_02" if region == "bay" else V8 / "regional_calendar_extension_01" / region / "dataset_v2"
        provider = AviationProvider(dataset, read(old_bank))
        checked = 0
        max_upper = 0
        for opportunity in provider.opportunities.values():
            if opportunity["lead_hours"] != 1:
                continue
            for condition in ["common_only", "fixed_one", "all_registered"]:
                bundle = provider.freeze(opportunity["opportunity_id"], condition,
                                         as_of=opportunity["cutoff"] - 600_000_000)
                independent = independent_reference(bundle.policy_view())
                native = native_slot_support(bundle)
                assert independent["fact_truth"] == TRUTH[native["status"]]
                assert independent["slots"] == {s["query_id"]: TRUTH[s["status"]] for s in native["slots"]}
                msg = messages(bundle.policy_view(), "full_bundle", "slotwise")
                upper = sum(len(m["content"].encode()) for m in msg) + 4096
                assert upper <= 32768
                max_upper = max(max_upper, upper)
                checked += 1
        row = {"region": region, "native_E_references": checked, "max_input_byte_allowance": max_upper}
        references.append(row)
        print(json.dumps(row), flush=True)
    publish(OUT / "VALIDATION.json", {"passed": True, "reference_checks": references,
        "dispatch": dispatch, "direct_equivalence": comparisons, "model_calls": 0,
        "bank_scope": "old Bay bank borrowed only for engineering qualification"})


if __name__ == "__main__":
    main()
