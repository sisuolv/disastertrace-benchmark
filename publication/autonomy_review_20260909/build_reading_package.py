"""Create a bounded reading attachment, explicitly excluding full raw reconstruction."""

import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROJECT = REPO / "disastertrace-starter"
PHASES = (
    "p6_offline_v1", "p6_live_v1", "p7_forecast_task_v1", "p7_forecast_live_v1",
    "p8_carrier_representation_v1", "p9_forecast_model_v1", "p10_forecast_cohort_v1",
    "p11_cohort_live_v1", "p12_compact_grammar_v1", "p13_prompt_role_v1", "p14_qwen_prompt_role_v1",
)


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()


def main():
    archive, receipt = HERE / "chatgpt_pro_p6_p14_reading.zip", HERE / "reading_manifest.json"
    if archive.exists() or receipt.exists():
        raise FileExistsError("the reading package already exists")
    selected = set()

    def add(path):
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(REPO):
            raise ValueError("missing or nonregular reading input: " + str(path))
        if path.stat().st_size >= 32 * 1024 * 1024:
            raise ValueError("large evidence belongs in the full archive: " + str(path))
        selected.add(path)

    for name in ("RESULTS_20260909.md", "SOURCE_REVIEW.md", "REFERENCE_BUNDLE.md"):
        add(REPO / name)
    for name in ("REVIEW_FOR_CHATGPT_PRO_P6_PLUS.md", "CURRENT_PHASE.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml"):
        add(PROJECT / name)
    for root, pattern in ((PROJECT / "src", "**/*.py"), (PROJECT / "tests", "**/*.py"),
                          (REPO / "plans", "**/*.md"), (PROJECT / "docs", "**/*.md"),
                          (PROJECT, "README_P[6-9]*.md"), (PROJECT, "README_P1[0-4]*.md"),
                          (HERE, "*.md"), (HERE, "*.py"), (HERE / "licenses", "*"),
                          (HERE / "result_tables_v1", "*")):
        for path in root.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                add(path)
    for phase in PHASES:
        bundle = PROJECT / "artifacts" / phase
        for pattern in ("*.md", "*.py", "PREREGISTRATION.json", "TEST_GATES.json", "*ACCEPTANCE*.json",
                        "FINAL_STATUS.json", "finalization*/FINAL_STATUS.json", "analysis*.json"):
            for path in bundle.glob(pattern):
                if path.is_file():
                    add(path)
    autonomy = PROJECT / "artifacts/autonomy_10h_v1"
    for pattern in ("*.md", "*.py", "cohort_stops_01/*.json", "cohort_reviews_01/*.json", "role_reviews_01/*.json",
                    "reviews_continuation_v2/*.json", "*GATES.json",
                    "p11_examples_v1/*.json", "p11_examples_v1/*.md",
                    "p11_review_addendum_v1/*.json",
                    "program_role_prompts_01.json", "CUMULATIVE_EVIDENCE_CHECK_01.json",
                    "COMPLETED_SUPPLEMENT.json", "dispatch_deadlines_v3.json", "context_censoring_v1.json",
                    "DISPATCH_V2_TEST_GATE.json", "DISPATCH_V3_TEST_GATE.json", "PUBLICATION_COPY_V2_TEST_GATE.json",
                    "PUBLICATION_COPY_V2_FINAL_TEST_GATE.json",
                    "CPU_PUBLICATION_INTERRUPTION_02.json", "publication_reconstruction_02/*.json",
                    "global_seal_recovery_03/*.json", "global_seal_recovery_03/*.log",
                    "validation/global_supplement*.json", "validation/global_supplement*.log",
                    "validation/dispatch*.json", "validation/dispatch*.log",
                    "validation/publication_copy*.json", "validation/publication_copy*.log",
                    "pair_coverage_v1.json",
                    "context_diagnostics_late_v1/*.json", "gpu_snapshots_01/final_accounting_01.json"):
        for path in autonomy.glob(pattern):
            if path.is_file():
                add(path)
    content = {path.relative_to(REPO).as_posix(): path.read_bytes() for path in sorted(selected)}
    notes = {
        "schema_version": "autonomy_reading_attachment_contents_v1",
        "purpose": "code_design_and_summary_review_not_full_reconstruction",
        "excluded": ["full_raw_model_runs", "full_program_diagnostic_runs", "model_weights", "tokenizers",
                     "installed_environments", "most_status_polling_logs", "many_historical_artifacts"],
        "full_reconstruction_requires": "the accepted evidence volumes and compatible CPU dependencies",
        "files_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in content.items()},
    }
    content["READING_CONTENTS.json"] = encoded(notes)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for name, data in sorted(content.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            stream.writestr(info, data)
    with zipfile.ZipFile(archive) as stream:
        if len(stream.namelist()) != len(content) or stream.testzip() is not None:
            raise ValueError("reading archive member count or CRC differs")
        for name, expected in content.items():
            if stream.read(name) != expected:
                raise ValueError("reading member bytes differ: " + name)
    record = {
        "schema_version": "autonomy_reading_attachment_v1", "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_bytes": archive.stat().st_size, "members_verified": len(content),
        "reading_files": len(selected), "full_reconstruction_package": False,
        "model_calls": 0, "scientific_bytes_modified": False,
    }
    with receipt.open("xb") as stream:
        stream.write(encoded(record))
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
