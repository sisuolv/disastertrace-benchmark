"""Read-only, bounded baseline for the approved offline A00-A06 batch."""

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = REPO / "plans/v12_execution_20260915_01"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def write(name, value):
    with (ROOT / name).open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def main():
    now = dt.datetime.now(dt.timezone.utc)
    gitdir = Path((REPO / ".git").read_text().strip().split(": ", 1)[1])
    index = sha(gitdir / "index")
    def git(*args):
        return subprocess.check_output(
            ["git", "--git-dir=" + str(gitdir), "--work-tree=" + str(REPO), *args],
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}, text=True,
        ).strip()
    write("EXECUTION_AUTHORIZATION.json", {
        "at": now.isoformat(), "user_instruction": "Execute the reviewed plan in order",
        "scope": [f"A0{i}" for i in range(7)], "stop_after": "A06",
        "time_budget_end": (now + dt.timedelta(hours=10)).isoformat(),
        "new_weather_http": 0, "new_model_calls": 0, "gpu": 0,
        "new_fits": 0, "new_scientific_branches": 0, "confirmation_payload_access": False,
        "git_push": False, "automatic_next_phase": False,
    })
    write("BASELINE.json", {
        "at": now.isoformat(), "development_head": git("rev-parse", "HEAD"),
        "published_reference": "1eba36dd272c72573d1309c78d45dbe97dd8af12",
        "tracked_status": git("status", "--porcelain", "--untracked-files=no").splitlines(),
        "index_sha256": index, "confirmation_opened": False,
        "consumed_runs": ["v12 C2 24 branches", "v12 Stage C 288 calls", "v12 compatibility 2 calls"],
        "historical_scope": "bounded implementation, reports, captures and registered identities; not all raw weather bytes",
    })
    before = ROOT / "before"
    for directory in ["disastertrace-starter/src", "disastertrace-starter/tests"]:
        for path in (REPO / directory).rglob("*.py"):
            target = before / path.relative_to(REPO)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    current = {str(p.relative_to(before)): sha(p) for p in before.rglob("*.py")}
    for name in ["CURRENT_PHASE.md", "IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md"]:
        p = REPO / "disastertrace-starter" / name
        target = before / p.relative_to(REPO)
        shutil.copyfile(p, target)
        current[str(p.relative_to(REPO))] = sha(p)
    protected = set(p for p in OLD.iterdir() if p.is_file() and p.suffix in {".py", ".md", ".json"})
    for directory in ["branch_source", "stage_c_source", "stage_c_source_02", "audit_source", "tests", "api_compatibility_01", "api_compatibility_02", "parents", "branches", "stage_C"]:
        for p in (OLD / directory).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".json", ".xml", ".md"} and "__pycache__" not in p.parts:
                protected.add(p)
    for p in (OLD / "annual_stage_B/fit").glob("*.json"):
        protected.add(p)
    write("PROTECTION_MANIFEST.json", {
        "historical_files": {str(p.relative_to(REPO)): sha(p) for p in sorted(protected)},
        "current_before": current, "raw_weather_universal_preservation_claim": False,
        "index_sha256": index,
    })
    write("EDIT_SCOPE.json", {
        "new_modules": ["analysis_integrity.py", "comparison_fingerprint.py", "selector_contract_v2.py", "api_transport_v2.py"],
        "current_module_allowlist": ["production.py", "policies.py", "residual_query_plan.py"],
        "new_tests": "tests/test_monitoring_v13_*.py",
        "mutable_navigation": ["CURRENT_PHASE.md", "IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md"],
        "frozen_batch_scripts_modified": False,
    })
    old11 = REPO / "plans/v11_execution_20260915_01"
    expected = {"v11": ["FULL_02.xml", "SUPPLEMENTAL.xml"], "v12": json.loads((OLD / "RESULT_SUMMARY.json").read_text())["tests"]["files"]}
    sets, receipts = {}, {}
    for version, names in expected.items():
        source = old11 if version == "v11" else OLD / "tests"
        ids, paths = set(), []
        for name in names:
            matches = list(source.rglob(name))
            if len(matches) != 1:
                paths.append({"name": name, "status": "missing_or_ambiguous", "count": len(matches)})
                continue
            p = matches[0]
            root = ET.parse(p).getroot()
            nodes = {c.attrib.get("classname", "") + "::" + c.attrib["name"] for c in root.iter("testcase")}
            ids |= nodes
            paths.append({"path": str(p.relative_to(REPO)), "sha256": sha(p), "unique_nodes": len(nodes)})
        sets[version] = ids
        receipts[version] = paths
    write("TEST_SCOPE_DIFF.json", {
        "source_receipts": receipts, "v11_unique": len(sets["v11"]), "v12_unique": len(sets["v12"]),
        "common": sorted(sets["v11"] & sets["v12"]),
        "v11_only": sorted(sets["v11"] - sets["v12"]), "v12_only": sorted(sets["v12"] - sets["v11"]),
        "identity_basis": "JUnit classname::name; historical observations, no new test execution",
        "rename_or_removal_inferred": False,
    })
    assert sha(gitdir / "index") == index
    write("A00_RESULT.json", {"passed": True, "protected_historical_files": len(protected),
        "current_python_files_snapshotted": len(current), "test_counts": {k: len(v) for k,v in sets.items()}})
    print(json.dumps(json.loads((ROOT / "A00_RESULT.json").read_text())), flush=True)


if __name__ == "__main__":
    main()
