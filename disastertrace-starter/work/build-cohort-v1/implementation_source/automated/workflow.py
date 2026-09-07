from __future__ import annotations

import copy
import platform
from collections import Counter
from pathlib import Path
from typing import Any

from .common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    safe_child,
    strict_json,
    write_json,
    write_jsonl,
)
from .disasterbench import build_disasterbench, score_disasterbench
from .dynamic import build_episodes, reference_at, run_episode, score_dynamic
from .sources import parse_nhc, profile_cyportqa


def _fresh_directory(path: Path) -> None:
    if path.exists():
        raise ValueError(f"output already exists; choose a new path to preserve history: {path}")
    path.mkdir(parents=True)


def _read(path: Path) -> Any:
    return strict_json(path.read_text(encoding="utf-8-sig"))


def implementation_snapshot() -> dict:
    files = {path.name: file_hash(path) for path in sorted(Path(__file__).parent.glob("*.py"))}
    snapshot = {"schema_version": "automated_implementation_v1", "files": files}
    return {**snapshot, "implementation_id": fingerprint(snapshot)}


def _require_implementation(build_path: Path) -> dict:
    recorded = _read(build_path / "implementation.json")
    current = implementation_snapshot()
    if recorded != current:
        raise ValueError(
            "implementation changed since build; create a new build to preserve history"
        )
    return current


def build(references: Path, output: Path, *, nhc_snapshot: Path | None = None) -> dict:
    _fresh_directory(output)
    write_json(output / "implementation.json", implementation_snapshot())
    source_copy = output / "implementation_source/automated"
    source_copy.mkdir(parents=True)
    for path in sorted(Path(__file__).parent.glob("*.py")):
        (source_copy / path.name).write_bytes(path.read_bytes())
    inventory = []
    snapshot = references / "no_manual_review_2026-09-06/weather_qa_sources"
    manifest = _read(snapshot / "MANIFEST.json")
    selected = {}
    for item in manifest:
        if item["repo"] != "TamuChen18/DisasterBench_Open":
            continue
        path = safe_child(snapshot, item["local_path"])
        if file_hash(path) != item["sha256"]:
            raise ValueError(f"upstream snapshot checksum mismatch: {path}")
        selected[item["path"]] = path
        inventory.append(
            {
                "source": "DisasterBench_Open",
                "url": item["url"],
                "commit": item["commit"],
                "sha256": item["sha256"],
            }
        )
    disasterbench = build_disasterbench(
        selected["data/benchmark.jsonl"], selected["interfaces/tools/tools_manifest.json"]
    )
    write_jsonl(output / "public/disasterbench_tasks.jsonl", disasterbench["public_tasks"])
    write_jsonl(
        output / "private/disasterbench_references.jsonl", disasterbench["private_references"]
    )
    write_json(output / "profiles/disasterbench.json", disasterbench["profile"])

    audit_root = references / "opensource_audit_2026-09-06"
    audit = _read(audit_root / "AUDIT.json")
    repository = next(
        item
        for item in audit["repositories"]
        if item["repository"] == "ChenchenMobility/MLLM-Bench-CyPortQA"
    )
    template = next(
        item
        for item in repository["source_files"]
        if item["upstream_path"] == "source_data/CyPortQA_template.json"
    )
    template_path = safe_child(audit_root, template["path"])
    if file_hash(template_path) != template["sha256"]:
        raise ValueError("CyPortQA template snapshot checksum mismatch")
    profile = profile_cyportqa(template_path)
    inventory.append(
        {
            "source": "CyPortQA_templates",
            "url": template["url"],
            "commit": repository["resolved_commit"],
            "sha256": template["sha256"],
        }
    )
    write_json(output / "profiles/cyportqa_templates.json", profile)

    nhc_root = nhc_snapshot or references / "implementation_sources"
    nhc_manifest = _read(nhc_root / "MANIFEST.json")
    catalogue = nhc_manifest.get("catalogue")
    if nhc_snapshot is not None and catalogue is None:
        raise ValueError("cohort snapshot requires a frozen catalogue")
    if catalogue is not None:
        catalogue_file = safe_child(nhc_root, nhc_manifest["catalogue_path"])
        if file_hash(catalogue_file) != nhc_manifest["catalogue_sha256"]:
            raise ValueError("cohort catalogue checksum mismatch")
        if _read(catalogue_file) != catalogue:
            raise ValueError("embedded cohort catalogue differs from frozen file")
        write_json(output / "sources/nhc_acquisition.json", nhc_manifest)
        write_json(output / "sources/cohort_catalogue.json", catalogue)
    records, admission = [], []
    source_ids = set()
    for item in nhc_manifest["files"]:
        if item["source_id"] in source_ids:
            raise ValueError("duplicate NHC snapshot source ID")
        source_ids.add(item["source_id"])
        html, text_path = (
            safe_child(nhc_root, item["html_path"]),
            safe_child(nhc_root, item["text_path"]),
        )
        if file_hash(html) != item["html_sha256"] or file_hash(text_path) != item["text_sha256"]:
            raise ValueError("NHC snapshot checksum mismatch")
        text = text_path.read_bytes().decode("utf-8")
        result = parse_nhc(
            text,
            source_id=item["source_id"],
            source_url=item["source_url"],
            source_sha256=item["text_sha256"],
        )
        admission.append(
            {
                "source_id": item["source_id"],
                "admitted": result["admitted"],
                "rejection_reasons": result["rejection_reasons"],
            }
        )
        if result["admitted"]:
            records.append(result["record"])
        inventory.append({"source": "NHC", **item, "extraction": nhc_manifest["extraction"]})
    cohort = None
    if catalogue is not None:
        from .cohort import build_cohort

        planned_ids = [
            source_id for event in catalogue["events"] for source_id in event["source_ids"]
        ]
        acquired_ids = [item["source_id"] for item in nhc_manifest["records"]]
        if len(set(acquired_ids)) != len(acquired_ids) or set(acquired_ids) != set(planned_ids):
            raise ValueError("acquisition records do not cover the frozen source catalogue exactly")
        if not source_ids <= set(planned_ids):
            raise ValueError("unplanned source file in NHC snapshot")
        for item in nhc_manifest["records"]:
            if item["source_id"] not in source_ids:
                admission.append(
                    {
                        "source_id": item["source_id"],
                        "admitted": False,
                        "rejection_reasons": [{"code": "ACQUISITION_FAILED", "detail": item}],
                    }
                )
        cohort = build_cohort(records, catalogue)
        episodes = cohort["episodes"]
        write_json(output / "profiles/cohort.json", cohort["profile"])
        write_json(output / "splits/event_groups.json", cohort["split_manifest"])
    else:
        episodes = build_episodes(records) if len(records) == 3 else []
    write_jsonl(output / "records/nhc_records.jsonl", records)
    write_jsonl(output / "episodes/dynamic_episodes.jsonl", episodes)
    write_jsonl(
        output / "private/dynamic_references.jsonl",
        [
            {
                "episode_id": episode["episode_id"],
                "checkpoint_id": checkpoint["checkpoint_id"],
                "reference": reference_at(episode, checkpoint["checkpoint_id"]),
            }
            for episode in episodes
            for checkpoint in episode["checkpoints"]
        ],
    )
    write_json(
        output / "profiles/nhc_admission.json",
        {
            "scope": "predeclared_pilot_cohort_not_population_admission_rate"
            if cohort
            else "three_selected_ida_advisories_not_population_admission_rate",
            "source_count": len(admission),
            "admitted_count": len(records),
            "quarantined_count": len(admission) - len(records),
            "items": admission,
            "dynamic_status": "ready" if episodes else "insufficient_admitted_records",
        },
    )
    write_json(output / "source_inventory.json", inventory)
    summary = {
        "schema_version": "automated_build_v1",
        "disasterbench_source_tasks": disasterbench["profile"]["source_tasks"],
        "disasterbench_admitted": len(disasterbench["public_tasks"]),
        "disasterbench_quarantined": disasterbench["profile"]["quarantined_tasks"],
        "cyportqa_templates": profile["template_count"],
        "nhc_admitted_records": len(records),
        "dynamic_episodes": len(episodes),
        "dynamic_checkpoints": sum(len(ep["checkpoints"]) for ep in episodes),
        "independent_weather_events": len({ep["group_id"] for ep in episodes}),
        "schedule_origin": "controlled_release",
        "content_edits": False,
        "new_human_reviews": 0,
        "model_calls": 0,
    }
    if catalogue is not None:
        summary.update(
            planned_weather_events=catalogue["planned_event_count"],
            nhc_planned_records=sum(len(event["source_ids"]) for event in catalogue["events"]),
            nhc_downloaded_records=len(nhc_manifest["files"]),
            cohort_id=catalogue["cohort_id"],
            dynamic_used_records=len(
                {record["record_id"] for episode in episodes for record in episode["records"]}
            ),
            weather_event_splits={
                split: len({ep["group_id"] for ep in episodes if ep["split"] == split})
                for split in ("development", "heldout")
            },
        )
        write_json(
            output / "profiles/dynamic_task_coverage.json",
            {
                "selection_frozen_before_model_results": True,
                "advisory_numbers_are_not_aligned_storm_phases": True,
                "policy": episodes[0]["policy"] if episodes else None,
                "by_split": {
                    split: {
                        "reference_action_counts": dict(
                            Counter(
                                reference_at(episode, checkpoint["checkpoint_id"])["action"]
                                for episode in episodes
                                if episode["split"] == split
                                for checkpoint in episode["checkpoints"]
                            )
                        ),
                        "independent_events": summary["weather_event_splits"][split],
                    }
                    for split in ("development", "heldout")
                },
            },
        )
    write_json(output / "summary.json", summary)
    artifacts = {
        str(path.relative_to(output)): file_hash(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    lock = {"schema_version": "automated_build_v1", "files": artifacts}
    lock["build_id"] = fingerprint(lock)
    write_json(output / "manifest.json", lock)
    return {**summary, "build_id": lock["build_id"]}


def verify_build(path: Path) -> dict:
    manifest = _read(path / "manifest.json")
    if manifest["build_id"] != fingerprint(
        {key: value for key, value in manifest.items() if key != "build_id"}
    ):
        raise ValueError("build manifest fingerprint mismatch")
    for name, expected in manifest["files"].items():
        if file_hash(safe_child(path, name)) != expected:
            raise ValueError(f"build artifact changed: {name}")
    return manifest


def selected_episodes(build_path: Path, split: str = "all") -> list[dict]:
    if split not in {"all", "development", "heldout"}:
        raise ValueError("unknown event split")
    episodes = read_jsonl(build_path / "episodes/dynamic_episodes.jsonl")
    selected = [ep for ep in episodes if split == "all" or ep["split"] == split]
    if not selected:
        raise ValueError("no admitted dynamic episodes in the selected split")
    return selected


def run(
    build_path: Path,
    output: Path,
    *,
    track: str,
    backend: str,
    predictions_path: Path | None = None,
    max_queries: int = 20,
    split: str = "all",
) -> dict:
    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    if type(max_queries) is not int or max_queries < 0:
        raise ValueError("max_queries must be a nonnegative integer")
    if backend == "submissions" and predictions_path is None:
        raise ValueError("submissions backend needs --predictions")
    if predictions_path is not None and backend != "submissions":
        raise ValueError("--predictions is only valid with submissions backend")
    if track not in {"dynamic", "disasterbench"}:
        raise ValueError("unknown track")
    if split not in {"all", "development", "heldout"} or (
        track == "disasterbench" and split != "all"
    ):
        raise ValueError("event split selection applies only to the dynamic track")
    allowed = {
        "dynamic": {"rule", "last-arrival", "no-update", "submissions"},
        "disasterbench": {"reference-fixture", "empty-control", "submissions"},
    }
    if backend not in allowed[track]:
        raise ValueError(f"backend {backend} is not available for {track}")
    _fresh_directory(output)
    config = {
        "schema_version": "automated_run_v1",
        "build_id": manifest["build_id"],
        "track": track,
        "backend": backend,
        "split": split,
        "max_queries": max_queries,
        "model_kind": "submitted_unverified"
        if backend == "submissions"
        else ("scorer_fixture" if track == "disasterbench" else "diagnostic_program"),
        "eligible_for_llm_leaderboard": False,
        "live_model_calls": 0,
        "implementation_id": implementation["implementation_id"],
        "python_version": platform.python_version(),
        "prediction_file_sha256": file_hash(predictions_path) if predictions_path else None,
    }
    write_json(output / "run.json", config)
    rows = read_jsonl(predictions_path) if predictions_path else []
    if track == "dynamic":
        episodes = selected_episodes(build_path, split)
        config["selected_episode_ids"] = [ep["episode_id"] for ep in episodes]
        indexed = {}
        expected = {
            (ep["episode_id"], cp["checkpoint_id"]) for ep in episodes for cp in ep["checkpoints"]
        }
        for row in rows:
            if set(row) != {"episode_id", "checkpoint_id", "raw_response"} or not isinstance(
                row["raw_response"], str
            ):
                raise ValueError(
                    "dynamic submission requires episode_id, checkpoint_id, raw_response string"
                )
            if any(
                not isinstance(row[name], str) or not row[name]
                for name in ("episode_id", "checkpoint_id")
            ):
                raise ValueError("dynamic submission identifiers must be nonempty strings")
            key = (row["episode_id"], row["checkpoint_id"])
            if key not in expected or key in indexed:
                raise ValueError("unknown or duplicate submitted checkpoint")
            indexed[key] = row
        remaining, count = max_queries, 0
        trace_path = output / "trace.jsonl"
        with trace_path.open("w", encoding="utf-8") as stream:
            for episode in episodes:
                trace = run_episode(
                    episode,
                    backend,
                    max_queries=remaining,
                    predictions=indexed if backend == "submissions" else None,
                )
                used = sum(row["logical_queries"] for row in trace)
                remaining -= used
                count += len(trace)
                for row in trace:
                    stream.write(canonical(row) + "\n")
                    stream.flush()
        config.update(
            checkpoint_attempts=count,
            logical_queries=max_queries - remaining,
            stop_reason="completed" if max_queries >= count else "budget_exhausted",
        )
    else:
        tasks = read_jsonl(build_path / "public/disasterbench_tasks.jsonl")
        refs = read_jsonl(build_path / "private/disasterbench_references.jsonl")
        if backend == "reference-fixture":
            rows = [
                {
                    "task_id": ref["task_id"],
                    "structured_plan": copy.deepcopy(ref["structured_plan"]),
                }
                for ref in refs[:max_queries]
            ]
        elif backend == "empty-control":
            rows = [
                {"task_id": task["task_id"], "structured_plan": []} for task in tasks[:max_queries]
            ]
        elif len(rows) > max_queries:
            raise ValueError(
                "submitted response count exceeds max_queries; raise the explicit limit"
            )
        # Validate identifiers and structures before saving, but do not feed scores into requests.
        score_disasterbench(tasks, refs, rows)
        write_jsonl(output / "predictions.jsonl", rows)
        predictions_by_id = {row["task_id"]: row for row in rows}
        with (output / "trace.jsonl").open("w", encoding="utf-8") as stream:
            for task in tasks:
                response = predictions_by_id.get(task["task_id"])
                stream.write(
                    canonical(
                        {
                            "task_id": task["task_id"],
                            "request": task,
                            "request_hash": fingerprint(task),
                            "raw_response": canonical(response) if response is not None else None,
                            "model_kind": config["model_kind"],
                            "fixture_reads_private_reference": backend == "reference-fixture",
                            "eligible_for_llm_leaderboard": False,
                        }
                    )
                    + "\n"
                )
        config.update(
            expected_tasks=len(tasks),
            logical_queries=len(rows),
            stop_reason="completed" if len(rows) == len(tasks) else "partial_submission",
        )
    config["trace_sha256"] = file_hash(output / "trace.jsonl")
    if (output / "predictions.jsonl").exists():
        config["predictions_sha256"] = file_hash(output / "predictions.jsonl")
    write_json(output / "run.json", config)
    return config


def score(build_path: Path, run_path: Path, output: Path) -> dict:
    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    config = _read(run_path / "run.json")
    if config["build_id"] != manifest["build_id"]:
        raise ValueError("run/build identity mismatch")
    if config["implementation_id"] != implementation["implementation_id"]:
        raise ValueError("run/implementation identity mismatch")
    budget, used = config["max_queries"], config["logical_queries"]
    if type(budget) is not int or type(used) is not int or not 0 <= used <= budget:
        raise ValueError("invalid run query budget/accounting")
    if config["trace_sha256"] != file_hash(run_path / "trace.jsonl"):
        raise ValueError("trace checksum mismatch")
    traces = read_jsonl(run_path / "trace.jsonl")
    if config["track"] == "dynamic":
        episodes = selected_episodes(build_path, config["split"])
        if config["selected_episode_ids"] != [ep["episode_id"] for ep in episodes]:
            raise ValueError("run split/episode selection mismatch")
        expected = [
            (episode["episode_id"], checkpoint["checkpoint_id"])
            for episode in episodes
            for checkpoint in episode["checkpoints"]
        ]
        indexed = {(row["episode_id"], row["checkpoint_id"]): row for row in traces}
        if len(indexed) != len(traces) or set(indexed) != set(expected):
            raise ValueError("invalid dynamic trace checkpoint set")
        if config["checkpoint_attempts"] != len(expected) or used != min(budget, len(expected)):
            raise ValueError("run query accounting does not match expected attempts")
        for index, key in enumerate(expected):
            row = indexed[key]
            if row["logical_queries"] != int(index < budget):
                raise ValueError("trace query accounting does not match run budget")
            if (row["status"] == "budget_exhausted") != (index >= budget):
                raise ValueError("trace exhaustion does not match run budget")
        result = score_dynamic(episodes, traces)
        if (build_path / "profiles/cohort.json").is_file():
            from .cohort import summarize_events

            result["event_summary"] = summarize_events(
                episodes,
                traces,
                expected_split=config["split"] if config["split"] != "all" else None,
            )
    elif config["track"] == "disasterbench":
        if config["split"] != "all":
            raise ValueError("DisasterBench run cannot claim an event split")
        if config["predictions_sha256"] != file_hash(run_path / "predictions.jsonl"):
            raise ValueError("prediction checksum mismatch")
        tasks = read_jsonl(build_path / "public/disasterbench_tasks.jsonl")
        refs = read_jsonl(build_path / "private/disasterbench_references.jsonl")
        predictions = read_jsonl(run_path / "predictions.jsonl")
        if used != len(predictions) or config["expected_tasks"] != len(tasks):
            raise ValueError("run query accounting does not match submitted predictions")
        by_id = {row["task_id"]: row for row in traces}
        if len(by_id) != len(traces) or set(by_id) != {task["task_id"] for task in tasks}:
            raise ValueError("invalid DisasterBench trace task set")
        pred_map = {row["task_id"]: row for row in predictions}
        for task in tasks:
            row = by_id[task["task_id"]]
            expected_response = (
                canonical(pred_map[task["task_id"]]) if task["task_id"] in pred_map else None
            )
            if (
                row["request"] != task
                or row["request_hash"] != fingerprint(task)
                or row["raw_response"] != expected_response
            ):
                raise ValueError("DisasterBench trace does not match task/prediction")
        result = score_disasterbench(tasks, refs, predictions)
    else:
        raise ValueError("unknown run track")
    result.update(build_id=manifest["build_id"], run=config, eligible_for_llm_leaderboard=False)
    if output.exists():
        raise ValueError("score output exists; use a new path")
    write_json(output, result)
    return result


def report(build_path: Path, scores: list[Path], output: Path) -> str:
    lock = verify_build(build_path)
    summary = _read(build_path / "summary.json")
    profile = _read(build_path / "profiles/disasterbench.json")
    lines = [
        "# Automated weather evaluation report",
        "",
        "Diagnostic programs are not LLM benchmark results. Imported responses retain unverified external provenance; no certified leaderboard is produced.",
        "",
        f"Build: {lock['build_id']}",
        "",
        "## Source admission",
        "",
        f"- DisasterBench: {summary['disasterbench_admitted']}/{summary['disasterbench_source_tasks']} tasks admitted; {summary['disasterbench_quarantined']} quarantined without label repair.",
        f"- CyPortQA: {summary['cyportqa_templates']} template declarations inventoried; no claim of complete QA admission.",
        f"- NHC: {summary['nhc_admitted_records']} selected official reports parsed; {summary['independent_weather_events']} independent storm groups.",
        f"- Dynamic example: {summary['dynamic_episodes']} controlled schedules, {summary['dynamic_checkpoints']} checkpoint attempts; original report content unchanged.",
        "- Gold is inherited for planning and generated from admitted source facts plus the explicit replay specification for dynamic tasks.",
        "",
        "## Automatic quarantine",
        "",
    ]
    for row in profile["quarantine"]:
        lines.append(f"- {row['task_id']}: {'; '.join(row['issues'])}")
    if "cohort_id" in summary:
        lines.extend(
            [
                "",
                "## Frozen event cohort",
                "",
                f"- Catalogue: {summary['cohort_id']}; {summary['planned_weather_events']} planned storm groups; {summary['nhc_downloaded_records']}/{summary['nhc_planned_records']} records downloaded.",
                f"- Admitted groups by split: {summary['weather_event_splits']}.",
                "- All branches and reports from one storm stay in one split. Ida remains in development because it was used for the first implementation.",
                "- This is a selected Atlantic cyclone pilot, not a representative sample of all extreme weather. Held-out events use the same parser and task template; they are not a hidden contamination-free benchmark.",
                "- Full source/event rejections are in profiles/nhc_admission.json and profiles/cohort.json; split assignments are in splits/event_groups.json.",
            ]
        )
    lines.extend(
        [
            "",
            "## Diagnostic results",
            "",
            "| Track / backend | Model kind | Metric | Result |",
            "| --- | --- | --- | --- |",
        ]
    )
    event_results = []
    for path in scores:
        result = _read(path)
        if result["build_id"] != lock["build_id"]:
            raise ValueError("report cannot combine different builds")
        run_config = result["run"]
        prefix = f"{run_config['track']} / {run_config['backend']} / {run_config['split']}"
        if "event_summary" in result:
            event_results.append((prefix, result["event_summary"]))
        if run_config["track"] == "disasterbench":
            agg = result["aggregate"]
            lines.append(
                f"| {prefix} | {run_config['model_kind']} | Inherited exact agreement | {agg['correct_tasks']}/{agg['expected_tasks']} |"
            )
        else:
            for metric in ("grounded_state", "action_accuracy", "known_answer_coverage"):
                value = result["metrics"][metric]
                lines.append(
                    f"| {prefix} | {run_config['model_kind']} | {metric} | {value['numerator']}/{value['denominator']} |"
                )
    if event_results:
        lines.extend(
            [
                "",
                "## Event-level results",
                "",
                "Each storm contributes one event; branches and checkpoints do not increase the independent event count. Event macro rates and denominators are preserved in score JSON. No confidence interval or population generalization is claimed.",
                "",
            ]
        )
        for prefix, event_summary in event_results:
            lines.append(
                f"- {prefix}: {event_summary['n_events']} storm groups, {event_summary['n_episodes']} branches, {event_summary['n_checkpoints']} checkpoints."
            )
        lines.extend(
            [
                "",
                "| Run / split | Storm | Grounded fields | Correct rule actions |",
                "| --- | --- | --- | --- |",
            ]
        )
        for prefix, event_summary in event_results:
            for event in event_summary["per_event"]:
                fields = event["metrics"]["grounded_state"]
                actions = event["metrics"]["action_accuracy"]
                lines.append(
                    f"| {prefix} | {event['group_id']} | {fields['numerator']}/{fields['denominator']} | {actions['numerator']}/{actions['denominator']} |"
                )
        lines.extend(
            [
                "",
                "| Run / split | Event macro grounded rate | Event macro action rate |",
                "| --- | --- | --- |",
            ]
        )
        for prefix, event_summary in event_results:
            macro = event_summary["overall"]["event_macro"]
            lines.append(
                f"| {prefix} | {macro['grounded_state']['value']:.4f} | {macro['action_accuracy']['value']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Reference-copy predictions are scorer fixtures that intentionally read private labels, not model outputs. Rule/last-arrival/no-update are deterministic diagnostic programs, not LLMs. Submitted outputs have unverified external provenance.",
            "",
            "DisasterBench scores measure agreement with inherited plans, not tool execution or emergency response quality. The new strict admission/response contract is a derived protocol. These tasks cover broad disasters and are not all extreme-weather events.",
            "",
            "The weather sample uses real source text with controlled release and repeated/late arrivals. Selected advisories do not establish a population-wide parser admission rate or historical public availability. The missing reopening field tests evidence insufficiency, not actual port recovery.",
            "",
            "Offline run/score use diagnostics or imported responses. Separate model collection requires an explicitly configured endpoint and model. Monetary caps, cross-provider budgets, automated search, and resumable live execution are not implemented.",
            "",
        ]
    )
    content = "\n".join(lines)
    if output.exists():
        raise ValueError("report output exists; use a new path")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return content
