"""Build an allowlisted local code/results review archive without models or secrets."""

import argparse
import datetime
import hashlib
import json
import re
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    assert re.fullmatch(r"[a-z0-9_]+", args.name)
    output = HERE / args.name
    output.mkdir(exist_ok=False)
    files = set()

    def add(path):
        if path.is_file():
            assert path.resolve().is_relative_to(REPO)
            files.add(path)

    add(REPO / "README_V8_MEASUREMENT_EXECUTION_CN.md")
    for name in ("IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md"):
        add(REPO / "disastertrace-starter" / name)
    for pattern in ("*.md", "*.json"):
        for path in HERE.glob(pattern):
            if path.name != "BASELINE.json":
                add(path)
    for folder in ("scripts", "gpu"):
        for path in (HERE / folder).glob("*.py"):
            add(path)
    for folder in ("monitoring_v1", "monitoring_fixed_v1"):
        for path in (REPO / "disastertrace-starter/src/disastertrace" / folder).rglob(
            "*.py"
        ):
            add(path)
    command = json.loads(
        (HERE / "validation/full_joint_targets_24.command.json").read_text()
    )["command"]
    for token in command:
        if token.endswith(".py") and not token.startswith("-"):
            add(REPO / token)
    for name in (
        "test_monitoring_joint_launch_bounds.py",
        "test_monitoring_joint_analysis.py",
        "test_monitoring_visible_forecast_values.py",
    ):
        add(REPO / "disastertrace-starter/tests" / name)
    for pattern in ("*.xml", "*.exit.json", "*.command.json", "*red*.log"):
        for path in (HERE / "validation").glob(pattern):
            add(path)
    for folder in ("validation/orchestration_guard_27", "finalization_pipeline_01"):
        for pattern in ("*.json", "*.log"):
            for path in (HERE / folder).glob(pattern):
                add(path)
    for folder in (
        "data_governance_01",
        "data_dependence_audit_01",
        "preparation_controls_01",
        "portable_replay_01",
    ):
        for path in (HERE / folder).rglob("*"):
            if path.is_file() and path.suffix in {
                ".py",
                ".json",
                ".jsonl",
                ".md",
                ".csv",
            }:
                add(path)
    for name in ("VALIDATION.json", "COMMAND.json", "EXIT.json", "replay.log"):
        add(HERE / "portable_relocation_01" / name)
    reports = [
        "large_model_diagnostic_01",
        "large_model_analysis_01",
        "program_calendar_optimized_audit_01",
        "program_calendar_analysis_01",
        "residual_c2_01",
        "real_committed_predictor_01",
        "real_committed_selector_01",
        "real_committed_source_01",
        "history_impact_01",
        "original_scorer_comparison_01",
        "original_scorer_comparison_02",
        "original_scorer_comparison_03",
        "adaptive_analysis_rehearsal_01",
        "adaptive_analysis_rehearsal_02",
        "adaptive_large_analysis_01",
        "adaptive_consolidated_analysis_01",
        "adaptive_audit_agreement_01",
        "real_preparation_recovery_01",
        "real_preparation_recovery_02",
        "real_preparation_recovery_03",
        "real_preparation_recovery_summary_01",
        "evidence_witnesses_01",
        "admitted_decisions_01",
        "joint_unlaunched_audit_01",
        "joint_unlaunched_analysis_01",
        "joint_large_analysis_01",
        "forecast_attribution_rehearsal_01",
        "forecast_attribution_rehearsal_02",
        "forecast_attribution_01",
        "visible_forecast_values_01",
        "visible_forecast_values_consolidated_01",
        "forecast_attribution_consolidated_01",
    ]
    for name in reports:
        for path in (HERE / "reports" / name).rglob("*"):
            if any(
                part in {"source", "spool", "worker", "controllers"}
                for part in path.relative_to(HERE / "reports" / name).parts
            ):
                continue
            if (
                path.is_file()
                and path.suffix in {".json", ".csv", ".png", ".pdf", ".md"}
                and path.stat().st_size < 8 * 1024 * 1024
            ):
                add(path)
    for folder in (
        "temperature_extension_01",
        "h07_extension_01/semantic_contract_01",
        "hydro_e_extension_01",
        "regional_calendar_extension_01",
        "shadow_decode_prefix_01",
        "shadow_decode_complete_02",
        "h07_extension_01/endpoint_review_01",
        "temperature_daily_reference_01",
        "temperature_daily_reference_01/qualification_01",
        "temperature_daily_reference_01/sample_support_comparison_01",
        "temperature_daily_reference_01/production_support_01",
    ):
        for path in (HERE / folder).glob("*.json"):
            add(path)
    for path in (HERE / "temperature_extension_01/admission_01").glob("*.json"):
        add(path)
    for path in (HERE / "temperature_daily_forecast_01").rglob("*"):
        if "source" in path.relative_to(HERE / "temperature_daily_forecast_01").parts:
            continue
        if (
            path.is_file()
            and path.suffix in {".json", ".jsonl", ".txt", ".py", ".md", ".zmetadata"}
            and path.stat().st_size < 8 * 1024 * 1024
            and path.name not in {"OUTCOME_REFERENCES.json", "DAILY_FORECASTS.json"}
        ):
            add(path)
    for path in (HERE / "temperature_extension_01/figures_01").glob("*"):
        add(path)
    add(HERE / "temperature_daily_reference_01/EXECUTED_ACQUISITION_SOURCE.py")
    for folder in ("qualification_01", "sample_support_comparison_01", "production_support_01"):
        add(HERE / "temperature_daily_reference_01" / folder / "EXECUTED_SOURCE.py")
    add(HERE / "calendar_extension_01/METADATA_AMENDMENT_01.json")
    for name in (
        "PLAN.json",
        "CPU_PREFLIGHT.json",
        "HARDWARE.json",
        "MODEL_READY.json",
        "COMPLETE.json",
        "WORKER_FAILED.json",
        "TIME_LIMIT.json",
    ):
        add(HERE / "gpu/adaptive_large_02" / name)
    for folder in ("audit_01", "audit_consolidated_01", "audit_parallel_scores_01", "audit_parallel_recovery_01", "audit_parallel_merged_01", "observer_01"):
        for path in (HERE / "gpu/adaptive_large_02" / folder).glob("*.json"):
            add(path)
    for folder in ("audit_01", "audit_consolidated_01", "audit_parallel_merged_01"):
        for name in ("REPORT.json", "VALIDATION.json", "RECEIPTS.json"):
            for path in (HERE / "gpu/adaptive_large_02" / folder).glob("*/" + name):
                add(path)
    for folder in ("audit_parallel_scores_01", "audit_parallel_recovery_01"):
        for path in (HERE / "gpu/adaptive_large_02" / folder).glob("*/*.json"):
            add(path)
    for path in (HERE / "gpu/adaptive_large_02/audit_incremental_01").glob("*.import_from_original.json"):
        add(path)
    for folder in ("joint_targets_candidate_01", "joint_targets_live_01"):
        base = HERE / "gpu" / folder
        for pattern in ("*.json", "*.log", "*.exit.txt"):
            for path in base.glob(pattern):
                add(path)
        for subdir in ("cpu_preflight_01", "submission_01", "audit_01", "qwen235b_fp8"):
            for path in (base / subdir).glob("*.json"):
                if subdir == "qwen235b_fp8" and path.name not in {
                    "STARTED.json",
                    "HARDWARE.json",
                    "COMPLETE.json",
                    "TIME_LIMIT.json",
                    "WORKER_FAILED.json",
                    "SMOKE_REQUEST.json",
                    "SMOKE_RESPONSE.json",
                }:
                    continue
                add(path)
    for path in (HERE / "gpu/joint_evaluation_protocol_01").glob("*.py"):
        add(path)
    for batch in ("large_diagnostic_02", "adaptive_large_02", "joint_targets_live_01"):
        for path in (HERE / "gpu" / batch / "source").rglob("*.py"):
            add(path)
    for name in ("PLAN.json", "VALIDATION.json", "COMPLETE.json"):
        add(HERE / "gpu/large_diagnostic_02" / name)
    for path in (REPO / "plans/v8_integrated_20260913").glob("*.md"):
        add(path)
    add(REPO / "plans/v8_integrated_20260913/WORK_PACKAGES.json")
    archive = output / "DisasterTrace_v8_code_and_progress.zip"
    manifest = []
    secret = re.compile(
        rb"(?:sk-[A-Za-z0-9]{24,}|eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|Signature=[A-Za-z0-9~_-]{30,}|-----BEGIN (?:OPENSSH|RSA|EC) PRIVATE KEY-----)"
    )
    with zipfile.ZipFile(
        archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as bundle:
        for path in sorted(files):
            payload = path.read_bytes()
            if path.suffix in {
                ".py",
                ".json",
                ".jsonl",
                ".md",
                ".log",
                ".txt",
            } and secret.search(payload):
                raise ValueError(
                    "Sensitive credential pattern in allowlisted file: "
                    + str(path.relative_to(REPO))
                )
            rel = str(path.relative_to(REPO))
            bundle.writestr(rel, payload)
            manifest.append(
                {
                    "path": rel,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        bundle.writestr(
            "REVIEW_MANIFEST.json",
            json.dumps(
                {
                    "files": manifest,
                    "created_at": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    "scope": "Allowlisted local code, tests and result summaries with a portable real-journal subset. No model weights, full native data rebuild or blanket raw-token reproduction is included.",
                },
                indent=2,
            ),
        )
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for row in manifest:
            assert hashlib.sha256(bundle.read(row["path"])).hexdigest() == row["sha256"]
    receipt = {
        "passed": True,
        "archive": archive.name,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_bytes": archive.stat().st_size,
        "files": len(manifest),
        "crc_and_every_member_hash_verified": True,
        "published_to_github": False,
    }
    with (output / "VALIDATION.json").open("x") as handle:
        json.dump(receipt, handle, indent=2)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
