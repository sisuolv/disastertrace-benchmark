"""Reproduce development-only diagnostic program comparisons without model calls."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import (
    file_hash,
    fingerprint,
    read_jsonl,
    write_json,
    write_jsonl,
)
from disastertrace.automated.dynamic import run_episode, score_dynamic
from disastertrace.automated.evidence_support import build_evidence_index
from disastertrace.automated.scoring_v2 import score_dynamic_v2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()
    source_root = Path(
        __import__("disastertrace.automated.dynamic", fromlist=["__file__"]).__file__
    ).parent
    modules = [
        "__init__.py",
        "common.py",
        "dynamic.py",
        "methods.py",
        "evidence_support.py",
        "scoring_v2.py",
    ]
    source_hashes = {name: file_hash(source_root / name) for name in modules}
    for name in modules:
        target = output / "implementation_source" / "automated" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / name, target)
    shutil.copyfile(__file__, output / "run_diagnostics.py")
    manifest_path = args.build / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    episode_path = args.build / "episodes" / "dynamic_episodes.jsonl"
    assert file_hash(episode_path) == manifest["files"]["episodes/dynamic_episodes.jsonl"]
    assert (
        fingerprint({key: value for key, value in manifest.items() if key != "build_id"})
        == manifest["build_id"]
    )
    # Only the declared development episodes are evaluated or copied into this package.
    episodes = [
        episode for episode in read_jsonl(episode_path) if episode["split"] == "development"
    ]
    assert len(episodes) == 6
    assert len({episode["group_id"] for episode in episodes}) == 3
    assert sum(len(episode["checkpoints"]) for episode in episodes) == 30
    for name in ("common.py", "dynamic.py", "methods.py"):
        assert source_hashes[name] == manifest["files"][f"implementation_source/automated/{name}"]
    write_jsonl(output / "development_episodes.jsonl", episodes)
    index = build_evidence_index(episodes)
    write_json(output / "evidence_index.json", index)
    write_json(
        output / "input_identity.json",
        {
            "schema_version": "p0_development_diagnostic_inputs_v1",
            "build_id": manifest["build_id"],
            "build_manifest_sha256": file_hash(manifest_path),
            "frozen_episodes_file_sha256": file_hash(episode_path),
            "selected_development_episodes_fingerprint": fingerprint(episodes),
            "selected_episode_ids": [episode["episode_id"] for episode in episodes],
            "source_hashes": source_hashes,
            "evidence_index_fingerprint": fingerprint(index),
            "script_sha256": file_hash(Path(__file__)),
            "python_version": sys.version,
            "model_kind": "diagnostic_program",
            "eligible_for_llm_leaderboard": False,
            "source_origin": "official_record",
            "schedule_origin": "controlled_release",
            "heldout_evaluated": False,
        },
    )
    rows = []
    methods = ("structured_state", "snapshot", "answer_history")
    backends = ("rule", "last-arrival", "no-update")
    for method in methods:
        for backend in backends:
            name = f"{method}__{backend}"
            traces = [
                row
                for episode in episodes
                for row in run_episode(
                    episode, backend, max_queries=len(episode["checkpoints"]), method=method
                )
            ]
            assert len(traces) == 30
            assert {row["model_kind"] for row in traces} == {"diagnostic_program"}
            assert all(not row["eligible_for_llm_leaderboard"] for row in traces)
            assert sum(row["provider_requests"] for row in traces) == 0
            v1, v2 = score_dynamic(episodes, traces), score_dynamic_v2(episodes, traces)
            assert v2["evidence_index_fingerprint"] == fingerprint(index)
            assert v1["metrics"]["grounded_state"] == v2["metrics"]["grounded_state"]
            expected_known = {"rule": 96, "last-arrival": 72, "no-update": 0}[backend]
            assert v2["metrics"]["known_grounded_accuracy"]["numerator"] == expected_known
            assert v2["metrics"]["known_grounded_accuracy"]["denominator"] == 96
            assert v2["metrics"]["unknown_accuracy"]["numerator"] == 54
            assert v2["metrics"]["unknown_accuracy"]["denominator"] == 54
            assert v2["metrics"]["schema_success"]["value"] == 1
            (output / name).mkdir()
            write_jsonl(output / name / "traces.jsonl", traces)
            write_json(output / name / "score_v1.json", v1)
            write_json(output / name / "score_v2.json", v2)
            slot_reasons = Counter(
                slot["reason"] for row in v2["per_checkpoint"] for slot in row["slots"].values()
            )
            citation_reasons = Counter(
                check["reason"]
                for row in v2["per_checkpoint"]
                for slot in row["slots"].values()
                for check in slot["citation_checks"]
            )
            if backend == "last-arrival":
                assert citation_reasons["stale_report"] == 24
            rows.append(
                {
                    "configuration": name,
                    "method": method,
                    "backend": backend,
                    "model_kind": "diagnostic_program",
                    "eligible_for_llm_leaderboard": False,
                    "provider_requests": 0,
                    "logical_queries": sum(row["logical_queries"] for row in traces),
                    "metrics": v2["metrics"],
                    "event_macro": v2["event_macro"],
                    "slot_reasons": dict(sorted(slot_reasons.items())),
                    "citation_reasons": dict(sorted(citation_reasons.items())),
                }
            )
    fixed_names = [
        name for name in rows[0]["metrics"] if not name.startswith("self_error_recovery")
    ]
    fixed_denominators = {name: rows[0]["metrics"][name]["denominator"] for name in fixed_names}
    assert all(
        {name: row["metrics"][name]["denominator"] for name in fixed_names} == fixed_denominators
        for row in rows
    )
    assert (
        fixed_denominators["gold_transition_success"] + fixed_denominators["gold_preservation"]
        == 120
    )
    assert all(file_hash(source_root / name) == digest for name, digest in source_hashes.items())
    result = {
        "schema_version": "p0_development_diagnostic_matrix_v1",
        "configurations": rows,
        "configuration_count": len(rows),
        "independent_events": 3,
        "episode_count": 6,
        "checkpoints_per_configuration": 30,
        "diagnostic_responses": 270,
        "provider_requests": 0,
        "model_kind": "diagnostic_program",
        "eligible_for_llm_leaderboard": False,
        "fixed_denominators_identical": True,
        "fixed_denominators": fixed_denominators,
        "source_hashes_unchanged_during_execution": True,
        "started_at": timestamp,
        "elapsed_seconds": time.monotonic() - started,
        "interpretation": "Offline diagnostic programs, not LLM responses. Shared real development events and dependent branches are not new independent samples.",
    }
    write_json(output / "matrix_summary.json", result)
    lines = [
        "# Development diagnostic matrix",
        "",
        "This is zero-API verification of diagnostic programs, not an LLM evaluation.",
        "Three existing development storms, six controlled branches and 30 checkpoints are replayed per configuration.",
        "All three methods receive cumulative delivered evidence. No heldout episode is evaluated.",
        "",
        "| Method | Diagnostic backend | Known grounded | Overall grounded | Semantic changes | Stable semantics | Source refresh |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:

        def ratio(name, metrics=row["metrics"]):
            value = metrics[name]
            return f"{value['numerator']}/{value['denominator']}"

        lines.append(
            "| "
            + " | ".join(
                [
                    row["method"],
                    row["backend"],
                    ratio("known_grounded_accuracy"),
                    ratio("grounded_state"),
                    ratio("gold_transition_success"),
                    ratio("gold_preservation"),
                    ratio("provenance_refresh"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "All nine configurations have identical fixed Gold denominators, including unsuccessful/correctness-independent opportunities.",
            "The rule parser supports all 96 known slots. Last-arrival gets 72/96 known slots grounded and exposes 24 stale citations.",
            "No-update gets 0/96 known slots grounded; its 54 correctly unknown slots do not conceal that failure in known-only metrics.",
            "These controls test scorer behavior and method wiring. They do not establish differences or equivalence between LLM methods.",
            "",
            "Saved files include exact traces, v1/v2 scores, selected source episodes, the evidence index, source snapshots and hashes.",
            "The script refuses an existing output directory. To reproduce, run the same command with a fresh output path; timestamps and elapsed time will differ.",
        ]
    )
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
    write_json(
        output / "manifest.json",
        {
            "schema_version": "p0_development_diagnostic_artifacts_v1",
            "files": {
                str(path.relative_to(output)): file_hash(path)
                for path in sorted(output.rglob("*"))
                if path.is_file()
            },
        },
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "configurations": len(rows),
                "diagnostic_responses": 270,
                "provider_requests": 0,
                "fixed_denominators": fixed_denominators,
            }
        )
    )


if __name__ == "__main__":
    main()
