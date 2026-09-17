"""Publish completed v13 results, preserving original runs and Git index."""

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PUB = HERE.relative_to(REPO)
BASE = "013c64feb1f1307497f7769e0939363154e89f83"
BRANCH = "next-phase-v1"
spec = importlib.util.spec_from_file_location("v12_publisher", REPO / "publication/v12_execution_20260916/publish_execution.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
legacy.prior.BASE = BASE
legacy.OBJECTS = Path("/mnt/afs/260010168/extreme_weather_benchmark/publication/v13_inprogress_20260916_02/publication.git/objects")
helpers = legacy.helpers
GROUPS = {"plan": "v13_planning_20260916_01", "A": "v13_execution_20260916_01",
          "B": "v13_followup_20260916_01", "S": "v13_strong_baselines_20260916_01",
          "R": "v13_revision_readiness_20260916_01", "M": "v13_selector_execution_20260916_01"}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def development_identity():
    head = subprocess.check_output(["git", "-c", "safe.directory=" + str(REPO),
        "--git-dir=" + str(legacy.prior.DEV_GIT), "rev-parse", "HEAD"],
        env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), text=True).strip()
    return {"head": head, "index_sha256": digest(legacy.prior.DEV_GIT / "index")}


legacy.prior.identity = development_identity


def selection():
    paths = set()
    suffixes = {".py", ".json", ".md", ".xml", ".yaml", ".yml", ".toml", ".txt",
                ".sh", ".log", ".stdout", ".stderr"}
    def add(path):
        if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts:
            if path.is_symlink():
                raise ValueError("Symlink excluded: " + str(path))
            paths.add(path)
    for name in ("src", "tests"):
        for path in (REPO / "disastertrace-starter" / name).rglob("*"):
            add(path)
    for name in ("CURRENT_PHASE.md", "IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md",
                 "AGENTS.md", "pyproject.toml", "requirements-verified.txt", "requirements-mm-cpu-v1.txt"):
        add(REPO / "disastertrace-starter" / name)
    fixture = REPO / "plans/v7_review_execution_20260912/regional_01"
    for name in ("public/TARGETS.json", "public/OPPORTUNITIES.json", "public/QUERY_CATALOG.json",
                 "public/E_F_PAIRS.json", "environment/NATIVE_PRODUCT_INDEX.json",
                 "environment/QUERY_RESULTS.json", "environment/BASELINE_CANDIDATES.json"):
        add(fixture / name)
    for folder in [HERE] + [REPO / "plans" / name for name in GROUPS.values()]:
        for path in folder.iterdir():
            if path.name != "GITHUB_UPLOAD.json":
                add(path)
    for group, folders in {"A": ["tests", "regression", "regression_02"],
                           "S": ["regression"], "B": ["B00", "C00", "M00", "SOURCE_STRATA"]}.items():
        root = REPO / "plans" / GROUPS[group]
        for name in folders:
            folder = root / name
            for path in folder.iterdir():
                add(path)
            for path in (folder / "xml").glob("*.xml"):
                add(path)
    for group, folder in [("A", "regression_02/source"), ("B", "source"), ("S", "source")]:
        for path in (REPO / "plans" / GROUPS[group] / folder).rglob("*.py"):
            add(path)
    # Completion receipts are selected once; no unfinished journal or spool is copied.
    root = REPO / "plans" / GROUPS["B"]
    for pattern in ("B00/*/RESULT.json", "C00/*/C00_RESULT.json", "M00/*/RESULT.json"):
        for path in root.glob(pattern):
            add(path)
    for group in ("B", "S", "M"):
        root = REPO / "plans" / GROUPS[group]
        for pattern in ("runtime/*/JOB.json", "runtime/*/EXIT.json", "runtime/*/CREATE_ARGUMENTS.json",
                        "runtime/*/LAUNCH_FREEZE.json", "runtime/*/bounded.sh"):
            for path in root.glob(pattern):
                add(path)
    root = REPO / "plans" / GROUPS["M"]
    for pattern in ("cases/*/RESULT.json", "cases/*/API_AUDIT.json", "cases/*/CONSUMER_AUDIT.json",
                    "cases/*/EXECUTION.json", "cases/*/SCORE.json", "cases/*/ROWS.json"):
        for path in root.glob(pattern):
            add(path)
    for path in (REPO / "plans" / GROUPS["S"] / "B02").glob("*/*_RESULT.json"):
        add(path)
    for path in (root / "runtime").iterdir():
        add(path)
    for path in (root / "runtime/submission_wait").iterdir():
        add(path)
    return sorted(paths)


def stable_bytes(path):
    for _ in range(5):
        first = path.read_bytes()
        if first == path.read_bytes():
            try:
                if path.suffix == ".json":
                    json.loads(first)
            except json.JSONDecodeError:
                time.sleep(0.1)
                continue
            return first
        time.sleep(0.1)
    raise ValueError("File did not reach a readable observation: " + str(path))


def summarize(snapshot, started):
    def load(group, name):
        path = snapshot / "plans" / GROUPS[group] / name
        return read(path) if path.exists() else None
    b00 = list((snapshot / "plans" / GROUPS["B"] / "B00").glob("*/RESULT.json"))
    c00 = list((snapshot / "plans" / GROUPS["B"] / "C00").glob("*/C00_RESULT.json"))
    return {"observation_started_at": started, "observation_finished_at": now(),
        "release_kind": "completed_development_results", "registered_batch_execution_complete": True,
        "overall_research_plan_complete": False,
        "observation_is_cross_process_atomic": False,
        "A00_A06": load("A", "FINAL_RESULT.json"), "B00_C00_M00_status": load("B", "STATUS.json"),
        "copied_B00_case_receipts": {"count": len(b00), "passed": sum(read(p)["passed"] for p in b00)},
        "copied_C00_parent_receipts": {"count": len(c00), "passed": sum(read(p)["passed"] for p in c00)},
        "M00": {k: v for k, v in load("B", "M00/RESULT.json").items() if k != "results"},
        "B02_status": load("S", "STATUS.json"), "B02_regression": load("S", "regression/RESULT.json"),
        "M01_status": load("M", "STATUS.json"), "M01_job": load("M", "runtime/JOB.json"),
        "M01_submission_wait": load("M", "runtime/submission_wait/STATUS.json"),
        "M01_pre_handoff": load("M", "PRE_HANDOFF_CHECK.json"),
        "B00_final": load("B", "B00/RESULT.json"), "C00_final": load("B", "C00/RESULT.json"),
        "B02_final": load("S", "FINAL_RESULT.json"), "M01_final": load("M", "FINAL_RESULT.json"),
        "source_strata": load("B", "SOURCE_STRATA/RESULT.json"),
        "preservation": load("B", "PRESERVATION.json"),
        "publication_result_validation": read(HERE / "RESULT_VALIDATION.json"),
        "new_model_calls_caused_by_publication": 0, "new_weather_downloads": 0,
        "confirmation_opened": False, "full_scientific_reproduction_included": False,
        "codex_token_usage_for_publication": "not measured; ordinary scripts do not call Codex"}


def report(status):
    return (HERE / "RESULTS_CN.md").read_text() + "\n发布观察时间：" + status["observation_finished_at"] + "\n"


def prepare(work):
    work.mkdir(exist_ok=False)
    if not read(HERE / "RESULT_VALIDATION.json")["passed"]:
        raise ValueError("Result audit must pass before export")
    identity = legacy.prior.identity()
    git = legacy.init_git(work / "publication.git", alternate=True)
    if git("rev-parse", "FETCH_HEAD").decode().strip() != BASE:
        raise ValueError("Remote advanced; review new base without force push")
    snapshot = work / "snapshot"
    snapshot.mkdir()
    private = [helpers.KEY_FILE.read_bytes().strip()] if helpers.KEY_FILE.exists() else []
    credential = Path("/mnt/afs/260010168/.config/disastertrace/credentials/siliconflow.json")
    if credential.exists():
        private.append(read(credential)["api_key"].encode())
    exported = []
    def save(name, content):
        helpers.inspect_payload(name, content, private)
        dest = snapshot / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(content)
        exported.append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                         "observed_at": now()})
    started = now()
    for path in selection():
        save(path.relative_to(REPO).as_posix(), stable_bytes(path))
    status = summarize(snapshot, started)
    save(str(PUB / "RESULTS_SNAPSHOT.json"), (json.dumps(status, ensure_ascii=False, indent=2) + "\n").encode())
    save("LATEST_PROGRESS_V13_CN.md", report(status).encode())
    banner = ("# Latest: v13 completed experiments and results (2026-09-17)\n\n"
              "Start with [current progress](LATEST_PROGRESS_V13_CN.md), "
              "[review instructions](publication/v13_completed_20260917/REVIEW_FOR_CHATGPT_PRO_CN.md), "
              "or [the code and evidence ZIP](publication/v13_completed_20260917/DisasterTrace_v13_completed_results.zip). "
              "B00, C00, B02 and M01 are complete. Model gains over all strong programs are not established. "
              "Earlier entries below retain their historical scope.\n\n---\n\n")
    save("README.md", banner.encode() + git("show", BASE + ":README.md"))
    manifest_name = str(PUB / "EXPORT_MANIFEST.json")
    manifest = {"at": now(), "base_commit": BASE, "release_kind": status["release_kind"],
                "development_identity": identity, "files": list(exported),
                "full_experiment_reproduction_included": False, "github_CI_run_claim": False,
                "excluded": ["credentials", "raw annual source cache", "full journals/checkpoints/spools",
                             "model weights", "confirmation payloads", "unfinished per-case results"]}
    save(manifest_name, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    archive_name = str(PUB / "DisasterTrace_v13_completed_results.zip")
    archive_path = snapshot / archive_name
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in exported:
            archive.write(snapshot / row["path"], row["path"])
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        for row in exported:
            if hashlib.sha256(archive.read(row["path"])).hexdigest() != row["sha256"]:
                raise ValueError("ZIP bytes differ")
    if archive_path.stat().st_size > 45 * 1024 * 1024:
        raise ValueError("Reading ZIP exceeds publication bound")
    names = sorted([row["path"] for row in exported] + [archive_name])
    blobs = git("hash-object", "-w", "--no-filters", "--stdin-paths",
                data="".join(str(snapshot / name) + "\n" for name in names).encode()).decode().splitlines()
    tree = legacy.prior.overlay_tree(git, names, blobs)
    before, after = legacy.entries(git, BASE), legacy.entries(git, tree)
    if set(before) - set(after) or any(before[n] != after[n] for n in set(before) - set(names)):
        raise ValueError("Unselected remote content changed")
    commit = git("commit-tree", tree, "-p", BASE,
                 data=b"Publish completed v13 baseline, intervention and model evaluation results\n").decode().strip()
    if legacy.prior.identity() != identity:
        raise ValueError("Development HEAD/index changed")
    write(work / "PRE_PUSH_AUDIT.json", {"passed": True, "added": len(set(after) - set(before)),
        "modified": [n for n in before if before[n] != after[n]], "removed": 0,
        "unselected_unchanged": True, "payloads_checked": len(exported), "zip_verified": True})
    write(work / "PREPARED.json", {"base": BASE, "commit": commit, "tree": tree, "files": names,
        "blobs": blobs, "identity": identity, "archive": archive_name, "manifest": manifest_name,
        "archive_sha256": digest(archive_path), "archive_bytes": archive_path.stat().st_size})
    print(json.dumps({"prepared": True, "commit": commit, "files": len(names),
                      "zip_bytes": archive_path.stat().st_size, "snapshot_at": status["observation_finished_at"]}), flush=True)


def publish(work):
    prepared = read(work / "PREPARED.json")
    if not read(work / "EXPORT_VALIDATION.json")["passed"]:
        raise ValueError("Export validation must pass")
    if legacy.prior.identity() != prepared["identity"]:
        raise ValueError("Development identity changed")
    snapshot = work / "snapshot"
    for row in read(snapshot / prepared["manifest"])["files"]:
        if digest(snapshot / row["path"]) != row["sha256"]:
            raise ValueError("Prepared bytes changed")
    if digest(snapshot / prepared["archive"]) != prepared["archive_sha256"]:
        raise ValueError("Reading ZIP changed")
    git = helpers.git_runner(work / "publication.git")
    if git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0] != BASE:
        raise ValueError("Remote advanced; do not force push")
    write(work / "PUSH_INTENT.json", {"at": now(), "commit": prepared["commit"]})
    git("push", "origin", prepared["commit"] + ":refs/heads/" + BRANCH)
    other = legacy.init_git(work / "readback.git")
    if other("rev-parse", "FETCH_HEAD").decode().strip() != prepared["commit"]:
        raise ValueError("Independent remote commit mismatch")
    remote_tree = legacy.entries(other, prepared["commit"])
    for name, blob in zip(prepared["files"], prepared["blobs"], strict=True):
        if remote_tree.get(name) != ["100644", "blob", blob]:
            raise ValueError("Remote tree mismatch")
    readbacks = ["README.md", "LATEST_PROGRESS_V13_CN.md", str(PUB / "REVIEW_FOR_CHATGPT_PRO_CN.md"),
                 "disastertrace-starter/src/disastertrace/monitoring_v1/public_query_selectors.py",
                 "plans/v13_selector_execution_20260916_01/FINAL_RESULT.json",
                 "plans/v13_selector_execution_20260916_01/COMPARISONS.json",
                 str(PUB / "RESULT_VALIDATION.json"), prepared["manifest"], prepared["archive"]]
    for name in readbacks:
        if hashlib.sha256(other("show", prepared["commit"] + ":" + name)).hexdigest() != digest(snapshot / name):
            raise ValueError("Remote readback bytes differ")
    if legacy.prior.identity() != prepared["identity"]:
        raise ValueError("Development identity changed during publication")
    result = {"passed": True, "at": now(), "commit": prepared["commit"], "base": BASE,
              "branch": BRANCH, "verified_tree_files": len(prepared["files"]), "readback_files": readbacks,
              "archive_bytes": prepared["archive_bytes"], "archive_sha256": prepared["archive_sha256"],
              "release_kind": "completed_development_results", "force_push": False,
              "development_identity_preserved_since_prepare": True, "new_experiments_by_publication": 0,
              "export_validation": read(work / "EXPORT_VALIDATION.json")}
    write(work / "PUBLISHED.json", result)
    write(HERE / "GITHUB_UPLOAD.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "publish"))
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.action == "prepare" else publish)(args.work.absolute())
