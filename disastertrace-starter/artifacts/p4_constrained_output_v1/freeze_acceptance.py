"""Bind completed acceptance evidence before the one-use GPU launch."""

from pathlib import Path

from disastertrace.constrained_eval import execution
from disastertrace.local_eval.storage import digest, inventory, now, read, write

HERE = Path(__file__).resolve().parent
REQUIRED = (
    "tests_revised",
    "old_regression",
    "launcher_tests",
    "grammar_controls",
    "freeze_offline",
    "freeze_live",
    "gpu_preflight",
    "diagnostic_offline",
    "report_offline",
    "verify_offline_report",
    "diagnostic_live_freeze",
    "report_live_diagnostic",
    "grammar_diagnostic",
    "portable_diagnostic",
    "preservation_before_launch",
    "lint_all_final",
)


def main():
    live, _, _ = execution.verify(HERE / "execution_live")
    offline, _, _ = execution.verify(HERE / "execution_offline")
    evidence = {}
    for name in REQUIRED:
        result = read(HERE / "validation" / name / "result.json")
        if result["exit_code"] != 0:
            raise ValueError("required acceptance command did not pass: " + name)
        directory = HERE / "validation" / name
        if digest(directory / "stdout.log") != result["log_sha256"]:
            raise ValueError("validation log changed: " + name)
        for path in directory.iterdir():
            evidence[str(path.relative_to(HERE))] = digest(path)
    for directory in (
        "execution_live",
        "execution_offline",
        "diagnostic",
        "diagnostic_report",
        "diagnostic_offline",
        "diagnostic_offline_report",
        "grammar_controls",
        "grammar_diagnostic",
    ):
        evidence.update(
            {directory + "/" + name: value for name, value in inventory(HERE / directory).items()}
        )
    for path in HERE.glob("*.py"):
        evidence[path.name] = digest(path)
    for name in (
        "SCOPE.json",
        "SCOPE_EXTENSION.json",
        "gpu_preflight.json",
        "preservation_before_launch.json",
    ):
        evidence[name] = digest(HERE / name)
    diagnostic = read(HERE / "diagnostic_report/report.json")
    if (
        diagnostic["execution_id"] != live["execution_id"]
        or not diagnostic["complete"]
        or diagnostic["local_model_calls"] != 0
    ):
        raise ValueError("live-freeze diagnostic does not match acceptance")
    if read(HERE / "grammar_controls/report.json")["counts"] != {
        "sequences": 5580,
        "accepted": 5472,
        "rejected_expected": 108,
    }:
        raise ValueError("incomplete Gold/control coverage")
    write(
        HERE / "frozen_acceptance.json",
        {
            "status": "passed",
            "frozen_at": now(),
            "execution_id": live["execution_id"],
            "offline_execution_id": offline["execution_id"],
            "evidence_files": evidence,
            "additional_model_calls": 0,
            "required_commands": list(REQUIRED),
            "preserved_failed_validations": ["lint_initial", "tests_initial", "official_sources"],
        },
    )
    print(
        {"status": "passed", "execution_id": live["execution_id"], "evidence_files": len(evidence)}
    )


if __name__ == "__main__":
    main()
