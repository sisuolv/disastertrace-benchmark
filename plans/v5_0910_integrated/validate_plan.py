"""Read-only consistency checks for a planning package, not benchmark tests."""

import hashlib
import json
import math
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate():
    manifest = read("INPUT_MANIFEST.json")
    source = read("SOURCE_CANDIDATES.json")
    backlog = read("IMPLEMENTATION_BACKLOG.json")
    resources = read("RESOURCE_SCOPES_DRAFT.json")
    baseline = read("BASELINE_SNAPSHOT.json")
    checked_members = 0
    original_rows = {}
    package_counts = {}

    for item in manifest["files"]:
        data = (ROOT / item["copy"]).read_bytes()
        require(len(data) == item["bytes"], "input size: " + item["copy"])
        require(digest(data) == item["sha256"], "input hash: " + item["copy"])
        require(
            digest(Path(item["original_path"]).read_bytes()) == item["sha256"],
            "original input changed: " + item["original_path"],
        )

    for archive in manifest["archives"]:
        with zipfile.ZipFile(ROOT / archive["copy"]) as bundle:
            expected = {m["path"]: m for m in archive["members"]}
            actual = {i.filename: i for i in bundle.infolist() if not i.is_dir()}
            require(set(expected) == set(actual), "archive member inventory")
            for name, info in actual.items():
                path = PurePosixPath(name)
                require(not path.is_absolute() and ".." not in path.parts, "unsafe member")
                require((info.external_attr >> 16) & 0o170000 != 0o120000, "symlink member")
                data = bundle.read(name)
                require(len(data) == expected[name]["bytes"], "member size: " + name)
                require(digest(data) == expected[name]["sha256"], "member hash: " + name)
                checked_members += 1
            rows = json.loads(bundle.read(archive["registry_member"]))[archive["registry_key"]]
            require(len(rows) == archive["candidate_rows"], "registry row count")
            package_counts[archive["plan_id"]] = len(rows)
            for index, row in enumerate(rows):
                ident = next(row[k] for k in ("id", "source_id", "dataset_id") if k in row)
                key = archive["plan_id"] + ":" + ident
                require(key not in original_rows, "duplicate input candidate")
                original_rows[key] = (index, row)

    by_plan = {a["plan_id"]: a for a in manifest["archives"]}
    for duplicate in manifest["duplicates"]:
        archive = by_plan[duplicate["same_as_plan"]]
        with zipfile.ZipFile(ROOT / archive["copy"]) as bundle:
            require(
                (ROOT / duplicate["standalone"]).read_bytes()
                == bundle.read(duplicate["same_as_member"]),
                "standalone duplicate mismatch",
            )

    ids = [row["candidate_id"] for row in source["records"]]
    require(len(ids) == len(set(ids)) == source["candidate_record_count"] == 257, "candidate count")
    require(set(ids) == set(original_rows), "candidate identity coverage")
    require(source["distinct_product_count"] is None, "unverified distinct product count")
    for candidate in source["records"]:
        index, row = original_rows[candidate["candidate_id"]]
        require(candidate["original_record"] == row, "original record altered")
        require(candidate["source_row_index"] == index, "source index altered")
        require(candidate["canonical_product_id"] is None, "unexpected finalized identity")

    tasks = {t["id"]: t for t in backlog["tasks"]}
    require(len(tasks) == len(backlog["tasks"]) == backlog["count"] == 30, "task count")
    visited, visiting, ordered = set(), set(), []

    def visit(ident):
        require(ident in tasks, "missing task dependency: " + ident)
        require(ident not in visiting, "dependency cycle: " + ident)
        if ident in visited:
            return
        visiting.add(ident)
        task = tasks[ident]
        require(task["status"] == "proposed", "task falsely marked implemented")
        require(task["deliverables"] and task["acceptance"], "empty deliverable or gate")
        for dependency in task["depends_on"]:
            visit(dependency)
        visiting.remove(ident)
        visited.add(ident)
        ordered.append(ident)

    for ident in tasks:
        visit(ident)
    for ident in backlog["first_execution_scope"] + backlog["gated_first_week_extensions"]:
        require(ident in tasks, "unknown first-sprint task")

    calls, tokens, gpu_hours = 0, 0, 0
    for scope in resources["model_scopes"]:
        require(math.prod(scope["factors"].values()) == scope["max_model_calls"], "matrix product")
        capacity = scope["max_model_calls"] * scope["max_requested_output_tokens_per_call"]
        require(capacity == scope["max_requested_output_tokens"], "token capacity")
        require(tasks[scope["task_id"]]["model_scope_id"] == scope["id"], "task/scope mapping")
        require(not scope["execution_enabled"] and scope["actual_counts"] is None, "scope status")
        require(scope["model_retries"] == 0 and scope["max_h100_global"] == 4, "scope limits")
        calls += scope["max_model_calls"]
        tokens += capacity
        gpu_hours += scope["proposed_max_reserved_h100_hours"]
    require(calls == resources["combined_max_model_calls"] == 1568, "total calls")
    require(tokens == resources["combined_max_requested_output_tokens"] == 3211264, "total tokens")
    require(gpu_hours == resources["combined_proposed_max_reserved_h100_hours"] == 64, "total GPUh")
    capture = next(s for s in resources["data_scopes"] if s["id"] == "CAPTURE_72H")
    polls = capture["max_wall_seconds"] // capture["minimum_poll_interval_seconds"] * capture["max_providers"]
    require(polls == capture["scheduled_poll_opportunities_max"] == 576, "capture schedule")
    require(polls <= capture["max_http_attempts"] == 768, "capture request budget")
    require(not resources["dispatch_enabled"] and not resources["execution_scope_frozen"], "planning status")

    for item in baseline["baseline_files"]:
        require(digest((ROOT / item["path"]).read_bytes()) == item["sha256"], "baseline changed: " + item["path"])

    checked_links = 0
    for document in ROOT.glob("*.md"):
        text = document.read_text(encoding="utf-8")
        for href in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", text):
            href = href.strip("<>")
            if "://" in href or href.startswith("#"):
                continue
            path = href.split("#", 1)[0]
            require((document.parent / path).exists(), "missing local link: " + path)
            checked_links += 1
    decisions = (ROOT / "PLAN_DECISIONS.md").read_text(encoding="utf-8")
    for ident in re.findall(r"(?:master43|complete45|master52|master58|master59):[A-Za-z0-9_]+", decisions):
        require(ident in original_rows, "unknown source cross-reference: " + ident)

    return {
        "status": "passed",
        "scope": "planning_consistency_only_not_benchmark_acceptance",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "input_files": len(manifest["files"]),
        "archive_members": checked_members,
        "package_candidate_counts": package_counts,
        "standalone_duplicate_pairs": len(manifest["duplicates"]),
        "candidate_rows": len(ids),
        "distinct_product_count": None,
        "backlog_tasks": len(tasks),
        "topological_order": ordered,
        "max_model_calls_proposed": calls,
        "max_requested_output_token_capacity": tokens,
        "max_reserved_h100_hours_proposed": gpu_hours,
        "baseline_files_unchanged": len(baseline["baseline_files"]),
        "local_links_checked": checked_links,
        "external_endpoints_validated": False,
        "benchmark_implementation_tests_run": False,
        "new_model_calls": 0,
        "new_gpu_jobs": 0,
        "new_weather_data_downloads": 0,
        "planning_file_hashes": {
            p.name: digest(p.read_bytes())
            for p in sorted(ROOT.iterdir())
            if p.is_file() and p.name != "PLAN_VALIDATION.json"
        },
    }


if __name__ == "__main__":
    try:
        report = validate()
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps(report, ensure_ascii=False, indent=2))
