"""One-use offline preparation: preservation, public tasks, automatic references."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
sys.path.insert(0, str(PROJECT / "src"))

from disastertrace.multimodal_atomic_v1.audit import validate_plan
from disastertrace.multimodal_atomic_v1.references import control, reference
from disastertrace.multimodal_atomic_v1.scoring import parsed, score
from disastertrace.multimodal_atomic_v1.tasks import build
from disastertrace.multimodal_v1.storage import canonical, digest, now, read, write


def main():
    write(ROOT / "PREPARATION_CLAIM.json", {"at": now(), "generations": 0})
    suites = ET.parse(ROOT / "TESTS_02.xml").getroot()
    supplement = ET.parse(ROOT / "TESTS_CONTRACT_03.xml").getroot()
    nodes = {}
    for report in (suites, supplement):
        for case in report.iter("testcase"):
            identity = (case.attrib["classname"], case.attrib["name"])
            if case.find("failure") is not None or case.find("error") is not None:
                raise ValueError("offline test gate failed")
            nodes[identity] = nodes.get(identity, False) or case.find("skipped") is None
    if len(nodes) != 96 or not all(nodes.values()):
        raise ValueError("every required test node must have a passing execution")
    if (ROOT / "LINT_02.log").read_text().strip() != "All checks passed!":
        raise ValueError("lint gate failed")
    preserved = {}
    versions = [("mm0_2_20260909", "files_sha256", "self"),
                ("mm3_20260909", "local_files_sha256", "parent"),
                ("mm3_contract_v2_live_20260909", "local_files_sha256", "self")]
    for name, field, relative in versions:
        old = ROOT.parent / name
        acceptance = read(old / "COMPLETED.json")
        base = old if relative == "self" else ROOT.parent
        for path, expected in acceptance[field].items():
            actual = base / path
            if digest(actual.read_bytes()) != expected:
                raise ValueError("prior evidence changed: " + str(actual))
            preserved[str(actual.relative_to(PROJECT))] = expected
        preserved[str((old / "COMPLETED.json").relative_to(PROJECT))] = digest((old / "COMPLETED.json").read_bytes())
    write(ROOT / "PRIOR_BINDINGS.json", preserved)
    write(ROOT / "PRESERVATION_BEFORE.json", {"at": now(), "status": "passed", "files": len(preserved)})
    seed = ROOT.parent / "mm0_2_20260909/build_02"
    shutil.copytree(seed / "public", ROOT / "seed/public")
    (ROOT / "seed/private").mkdir()
    shutil.copyfile(seed / "private/geometry_lineage.json", ROOT / "seed/private/geometry_lineage.json")
    plan = build(ROOT / "seed/public/requests")
    validate_plan(plan)
    geometries = {g["artifact_id"]: g for g in read(ROOT / "seed/private/geometry_lineage.json")}
    refs, controls = {}, []
    for task in plan["tasks"]:
        tid = task["task_id"]
        refs[tid] = reference(task, geometries)
        actual = control(task)
        if actual != refs[tid]:
            raise ValueError("independent automatic checks disagree: " + tid)
        result = score(task, refs[tid], parsed(canonical(actual), task["family"]), "eos")
        if not result["strict_correct"]:
            raise ValueError("automatic answer does not pass the contract")
        controls.append({"task_id": tid, "reference_equals_public_control": True, "result": result})
    write(ROOT / "REQUEST_PLAN.json", plan)
    write(ROOT / "references.json", refs)
    write(ROOT / "AUTOMATIC_CONTROLS.json", {"origin": "offline_program_diagnostic", "generations": 0,
          "controls": controls, "note": "program controls are not model scores"})
    source = ROOT / "source"
    shutil.copytree(ROOT.parent / "mm3_contract_v2_live_20260909/source", source,
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(PROJECT / "src/disastertrace/multimodal_atomic_v1",
                    source / "src/disastertrace/multimodal_atomic_v1",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(PROJECT / "tests/test_multimodal_atomic_v1.py", source / "tests/test_multimodal_atomic_v1.py")
    for name in ("RUNTIME_BINDINGS.json", "runtime-resolved.txt"):
        shutil.copyfile(ROOT.parent / "mm3_contract_v2_live_20260909" / name, ROOT / name)
    (ROOT / "model_acquisition").mkdir()
    shutil.copyfile(ROOT.parent / "mm3_contract_v2_live_20260909/model_acquisition/plan.json",
                    ROOT / "model_acquisition/plan.json")
    write(ROOT / "OFFLINE_ACCEPTANCE.json", {"at": now(), "status": "passed", "model_calls": 0,
          "test_nodes": len(nodes), "first_run": "56 passed, 40 skipped",
          "contract_supplement": "41 passed; one node overlaps first run",
          "task_count": len(plan["tasks"]), "prior_files_verified": len(preserved),
          "plan_sha256": digest((ROOT / "REQUEST_PLAN.json").read_bytes()),
          "reference_sha256": digest((ROOT / "references.json").read_bytes()),
          "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in source.rglob("*.py")}})
    print(json.dumps({"offline": "passed", "tasks": len(plan["tasks"]), "preserved": len(preserved)}))


if __name__ == "__main__":
    main()
