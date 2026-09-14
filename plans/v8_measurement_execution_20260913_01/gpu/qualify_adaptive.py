"""Bind passed offline gates to this new development-only inference freeze."""

import datetime
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from index_preservation import verify_index

HERE = Path(__file__).resolve().parents[1]
BATCH = HERE / "gpu/adaptive_large_02"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = read(BATCH / "PLAN.json")
    program = HERE / "reports/program_calendar_optimized_audit_01/BATCH_COMPLETE.json"
    rehearsal = HERE / "gpu/adaptive_rehearsal_02/audit_01/VALIDATION.json"
    role_rehearsal = HERE / "gpu/adaptive_rehearsal_03/audit_01/VALIDATION.json"
    regression = HERE / "validation/full_roles_and_decision_14.xml"
    context = HERE / "gpu/adaptive_context_preflight_03/REPORT.json"
    assert read(program)["all_passed"] and read(program)["program_arm_runs"] == 40
    assert (
        read(rehearsal)["all_sessions_qualified"]
        and read(rehearsal)["registered_sessions"] == 52
    )
    assert (
        read(role_rehearsal)["all_sessions_qualified"]
        and read(role_rehearsal)["registered_sessions"] == 8
    )
    suites = ET.parse(regression).getroot().iter("testsuite")
    tests = errors = failures = skipped = 0
    for suite in suites:
        tests += int(suite.attrib["tests"])
        errors += int(suite.attrib["errors"])
        failures += int(suite.attrib["failures"])
        skipped += int(suite.attrib["skipped"])
    assert tests == 439 and errors == failures == skipped == 0
    sizing = read(context)
    assert (
        len(sizing["rows"]) == 240
        and sizing["opportunities"] == 216
        and sizing["actual_model_calls"] == 0
    )
    assert sizing["passed"] and len(sizing["program_selector_variants"]) == 24
    assert sizing["current_plan_sha256"] == sha(BATCH / "PLAN.json")
    assert sizing["max_input_tokens"] <= plan["input_token_cap"]
    baseline = read(HERE / "BASELINE.json")
    index_check = verify_index()
    evidence = [program, rehearsal, role_rehearsal, regression, context]
    for name in (
        "real_committed_predictor_01",
        "real_committed_selector_01",
        "real_committed_source_01",
    ):
        file = HERE / "reports" / name / "VALIDATION.json"
        assert read(file)["passed"], file
        evidence.append(file)
    residual = HERE / "reports/residual_c2_01/SUMMARY.json"
    assert read(residual)["all_replayed"]
    evidence.append(residual)
    evidence.append(HERE / "reports/large_model_diagnostic_01/VALIDATION.json")
    for rel, expected in plan["files"].items():
        assert sha(BATCH / rel) == expected, rel
    tested = HERE / "gpu/adaptive_rehearsal_03"
    for rel, expected in read(tested / "PLAN.json")["files"].items():
        if rel.startswith("source/"):
            assert sha(BATCH / rel) == expected, rel
    row = {
        "passed": True,
        "plan_sha256": sha(BATCH / "PLAN.json"),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "evidence_files": {str(p): sha(p) for p in evidence},
        "related_tests": tests,
        "program_sessions": 40,
        "rehearsal_sessions": 52,
        "additional_current_source_selector_role_rehearsals": 8,
        "expected_live_sessions": 52,
        "opportunities_per_live_session": 216,
        "max_live_model_calls": 5376,
        "context_sizing": {
            "max_measured_tokens": sizing["max_input_tokens"],
            "registered_input_cap": plan["input_token_cap"],
            "scope": sizing["scope"],
        },
        "qualification": "W12 adaptive development diagnostic with existing R-track frozen probability map, serial controllers, actual model transport and explicit program/source timing scenarios.",
        "W08_scope": "Committed original source/selector/predictor across local processes; no general concurrent in-flight or physical external exactly-once guarantee.",
        "W11_scope": "Longer natural calendars and information controls acquired; regional calibration, independent weather-process groups and confirmatory power remain unqualified.",
        "not_claimed": [
            "Independent confirmation",
            "Operational cost-efficiency",
            "LLM superiority",
            "X09 joint-target reasoning",
            "D/MM or16-hazard completion",
        ],
        "preserved_original_index_snapshot": baseline["index_sha256"],
        "current_index_content_verification": index_check,
        "new_model_calls_at_freeze": 0,
    }
    with (BATCH / "CPU_PREFLIGHT.json").open("x") as handle:
        json.dump(row, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"passed": True, "tests": tests, "live_model_call_ceiling": 5376}))


if __name__ == "__main__":
    main()
