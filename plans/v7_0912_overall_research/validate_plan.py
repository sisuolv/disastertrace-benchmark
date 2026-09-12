"""Validate planning references and contracts, without scientific evaluation."""

import ast
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(name):
    return json.loads((ROOT / name).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def indexed(rows):
    result = {row["id"]: row for row in rows}
    require(len(result) == len(rows), "Duplicate contract ID")
    return result


def check_dag(items):
    visiting, done = set(), set()

    def visit(key):
        require(key in items, "Unknown dependency: " + key)
        require(key not in visiting, "Dependency cycle at " + key)
        if key in done:
            return
        visiting.add(key)
        for parent in items[key]["depends_on"]:
            visit(parent)
        visiting.remove(key)
        done.add(key)

    for key in items:
        visit(key)


def main():
    parsed = 0
    for path in sorted(ROOT.rglob("*.json")):
        if "validation" not in path.relative_to(ROOT).parts:
            json.loads(path.read_text())
            parsed += 1

    hazard_doc = read("OVERALL_HAZARD_CONTRACTS.json")
    hazards = indexed(hazard_doc["hazards"])
    require(set(hazards) == {f"H{i:02d}" for i in range(1, 17)}, "Hazard scope")
    require({h["group"] for h in hazards.values()} == set("ABCDEF"), "Group scope")
    sources = read("SOURCE_USAGE_MAP.json")
    source_ids = {s["source_id"] for s in sources["sources"]}
    require(len(source_ids) == len(sources["sources"]) == 97, "Source count")
    require(
        dict(Counter(s["state"] for s in sources["sources"])) == sources["state_counts"],
        "Source state counts differ",
    )
    for hazard in hazards.values():
        roles = list(hazard["source_ids"].values()) + [
            hazard.get(name, [])
            for name in (
                "index_sources",
                "conditional_outcome_sources",
                "native_diagnostic_sources_with_unresolved_spatial_gates",
            )
        ]
        for ids in roles:
            require(set(ids) <= source_ids, "Unknown source in " + hazard["id"])
        admission = hazard["overall_plan"]["current_new_monitoring_admission"]
        require(not any(admission.values()), "Planning cannot imply new admission")

    novelty = read("NOVELTY_CONTRACT.json")
    requirements = indexed(novelty["requirements"])
    contributions = indexed(novelty["contributions"])
    hypotheses = indexed(novelty["hypotheses"])
    experiments = indexed(read("EXPERIMENT_MATRIX.json")["experiments"])
    phases = indexed(read("MASTER_MILESTONES.json")["milestones"])
    review = indexed(read("literature/REVIEW_INDEX.json")["reviews"])
    require(len(requirements) == 8 and len(contributions) == 3, "Novelty scope")
    require(len(hypotheses) == 6 and len(experiments) == 10, "Experiment scope")
    require(len(phases) == 8, "Milestone count")
    check_dag(phases)
    old_tasks = indexed(
        json.loads(
            (ROOT.parent / "v7_0912_monitoring_optimization/IMPLEMENTATION_BACKLOG.json")
            .read_text()
        )["tasks"]
    )
    for contribution in contributions.values():
        require(set(contribution["requirement_ids"]) <= set(requirements), "Unknown R")
        require(set(contribution["experiment_ids"]) <= set(experiments), "Unknown X")
        require(set(contribution["nearest_neighbors"]) <= set(review), "Unknown paper")
    for hypothesis in hypotheses.values():
        require(set(hypothesis["experiment_ids"]) <= set(experiments), "Unknown HYP X")
    for experiment in experiments.values():
        require(
            set(experiment["milestone_ids"] + experiment["prerequisite_milestone_ids"])
            <= set(phases),
            "Unknown experiment milestone",
        )
        require(experiment["execution_status"] == "not_started", "False run status")
    for phase in phases.values():
        require(set(phase["existing_work_package_ids"]) <= set(old_tasks), "Unknown WP")

    bindings = read("INPUT_BINDINGS.json")
    for binding in bindings["repo_relative_bindings"]:
        path = REPO / binding["path"]
        require(digest(path) == binding["sha256"], "Input changed: " + binding["path"])
        require(path.stat().st_size == binding["bytes"], "Input byte count changed")

    # Reference failures remain valid audit records, not successful downloads.
    receipts = 0
    complete, partial, missing = 0, 0, 0
    for path in sorted((ROOT / "literature").glob("captures_*/*/RECEIPT.json")):
        receipt = json.loads(path.read_text())
        body = path.parent / "response.body"
        data = body.read_bytes() if body.exists() else b""
        require(hashlib.sha256(data).hexdigest() == receipt["sha256"], "Reference hash")
        require(len(data) == receipt["bytes"], "Reference byte count")
        receipts += 1
        if receipt["curl_exit"] == 0 and receipt["http_status"] == 200:
            complete += 1
        elif data:
            partial += 1
        else:
            missing += 1
    for item in review.values():
        for evidence in item["evidence"]:
            require(digest(ROOT / evidence["path"]) == evidence["sha256"], "Review hash")
    for section in read("literature/REVIEWED_SECTIONS.json"):
        require(digest(ROOT / section["source_path"]) == section["source_sha256"], "Section hash")

    checked_links = 0
    for path in sorted(ROOT.glob("*.md")):
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
            if target.startswith(("https://", "http://", "#", "mailto:")):
                continue
            local = target.split("#", 1)[0]
            if (path.parent / local).resolve() == ROOT / "validation/PLAN_VALIDATION.json":
                continue
            require((path.parent / local).is_file(), "Missing document link: " + target)
            checked_links += 1
    python_files = []
    for path in sorted(ROOT.glob("*.py")):
        ast.parse(path.read_text(), filename=str(path))
        python_files.append(path.name)

    report = {
        "schema": "disastertrace.v7.plan_validation.v1",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "scope": "Planning structure, hashes, local links and Python syntax only",
        "json_files_parsed": parsed,
        "hazards": len(hazards),
        "sources": len(source_ids),
        "contributions": len(contributions),
        "hypotheses": len(hypotheses),
        "experiments": len(experiments),
        "acyclic_milestones": len(phases),
        "reviewed_works": len(review),
        "repo_input_hashes_verified": len(bindings["repo_relative_bindings"]),
        "reference_receipts_verified": receipts,
        "reference_transfers": {"complete": complete, "partial": partial, "no_body": missing},
        "local_document_links_checked": checked_links,
        "python_syntax_checked": python_files,
        "new_monitoring_engine_tests_run": False,
        "new_dataset_tasks_admitted": False,
        "model_gain_demonstrated": False,
        "novelty_certified": False,
    }
    output = ROOT / "validation/PLAN_VALIDATION.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
