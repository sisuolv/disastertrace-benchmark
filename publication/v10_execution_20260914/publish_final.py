"""Publish a closed v10 snapshot through isolated Git objects and verify readback."""

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUN = REPO / "plans/v10_execution_20260914_01"
REMOTE = "ssh://git@ssh.github.com:443/sisuolv/disastertrace-benchmark.git"
BRANCH = "next-phase-v1"
BASE = "6f71c8799ff69439a18f645e63b8c966ca21eec4"
DEV_GIT = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/github_review/disastertrace-benchmark/.git/worktrees/disastertrace-next"
)
PUB = HERE.relative_to(REPO)


def utility():
    path = HERE / "publication_helpers.py"
    spec = importlib.util.spec_from_file_location("v10_publication_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_new(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def development_identity():
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    reply = subprocess.run(
        ["git", "--git-dir=" + str(DEV_GIT), "rev-parse", "HEAD"],
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    return {"head": reply.stdout.strip(), "index_sha256": digest(DEV_GIT / "index")}


def selection():
    paths, omissions = set(), []

    def add(path, limit=8 * 1024 * 1024):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            return
        if path.is_symlink():
            raise ValueError("Publication symlink: " + str(path.relative_to(REPO)))
        if path.stat().st_size > limit:
            omissions.append(
                {
                    "path": str(path.relative_to(REPO)),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                    "reason": "large local reconstruction input",
                }
            )
            return
        paths.add(path)

    for module in ["monitoring_v1", "monitoring_fixed_v1", "forecast_task"]:
        for path in (REPO / "disastertrace-starter/src/disastertrace" / module).rglob(
            "*.py"
        ):
            add(path)
    for path in (REPO / "disastertrace-starter/tests").glob("test_monitoring*.py"):
        add(path)
    for name in [
        "plans/v7_execution_20260913/tests",
        "plans/v9_followup_execution_20260914_01/tests",
        "plans/v9_integration_execution_20260914_01/tests",
    ]:
        for path in (REPO / name).glob("test_*.py"):
            add(path)
    for name in [
        "CURRENT_PHASE.md",
        "IMPLEMENTATION_STATUS.md",
        "DECISIONS.md",
        "BLOCKERS.md",
        "pyproject.toml",
    ]:
        add(REPO / "disastertrace-starter" / name)
    for folder in [HERE, RUN, RUN / "scripts", RUN / "contracts"]:
        for path in folder.iterdir():
            if path.suffix in {".py", ".md", ".json"}:
                add(path)
    for folder in [RUN / "validation", RUN / "reports"]:
        for path in folder.rglob("*"):
            if path.name.startswith("pt-"):
                continue
            if path.suffix in {".json", ".jsonl", ".md", ".xml", ".log", ".py"}:
                add(path)
    for name in ["portable_capsule_01", "portable_model_capsule_01"]:
        for path in (RUN / name).rglob("*"):
            add(path, limit=90 * 1024 * 1024 - 1)
        capsule = RUN / name
        manifest = json.loads((capsule / "MANIFEST.json").read_text())
        if any(capsule / rel not in paths for rel in manifest["files"]):
            raise ValueError("A complete replay capsule would lose a required member")
    for name in [
        "fixed_packet_01",
        "feature_temperature_trial_02",
        "large_feature_trial_01",
        "clarified_feature_trial_01",
    ]:
        batch = RUN / name
        plan = json.loads((batch / "PLAN.json").read_text())
        for rel in plan["files"]:
            add(batch / rel)
        for path in batch.glob("*.json"):
            add(path)
        for path in (batch / "gpu").glob("*.json"):
            add(path)
        for sub in [
            "api",
            "final_audit_01",
            "gpu/worker_0",
            "gpu/worker_1",
            "gpu/worker_2",
            "gpu/worker_3",
        ]:
            for path in (batch / sub).rglob("*"):
                if path.suffix in {".json", ".jsonl", ".raw", ".body", ".log"}:
                    add(path)
    for name in [
        "native_feature_bank_01",
        "temperature_postprocess_01",
        "formal_recovery_01",
        "native_residual_01",
        "native_residual_02",
        "multicutoff_01",
        "query_controls_01",
        "native_feature_sessions_01",
        "selector_trial_01",
        "seasonal_development_01",
        "seasonal_completion_02",
        "seasonal_evaluation_01",
        "calendar_feature_ablation_01",
        "seasonal_controls_01",
    ]:
        batch = RUN / name
        for path in batch.glob("*.json"):
            add(path)
        for path in (batch / "source").rglob("*.py"):
            add(path)
        for pattern in [
            "*/RESULT.json",
            "*/FAILED.json",
            "*/CALENDAR.json",
            "*/METRICS.json",
            "*/COMPLETE.json",
            "*/SCORES.json",
            "*/COMPARISON.json",
            "*/CONFIGS.json",
            "*/CONFIG.json",
            "*/CONTROL_INPUTS.json",
            "*/SOURCE_BINDINGS.json",
            "*/DATA.json",
            "*/BANK.json",
            "*/OUTCOMES.json",
            "*/*/SCORES.json",
            "*/*/COMPLETE.json",
        ]:
            for path in batch.glob(pattern):
                add(path)
        for path in (batch / "banks").glob("*.json"):
            add(path)
    for path in (RUN / "selector_trial_01").glob("*/spool/*.json"):
        add(path)
    for folder in [
        RUN / "calendar_feature_ablation_01/evaluation_01",
        RUN / "calendar_feature_ablation_01/independent_audit_01",
    ]:
        for path in folder.glob("*.json"):
            add(path)
        for path in (folder / "source").rglob("*.py"):
            add(path)
        for path in (folder / "banks").glob("*.json"):
            add(path)
        for pattern in ["*/RESULT.json", "*/METRICS.json", "*/SOURCE_AUDIT.json"]:
            for path in folder.glob(pattern):
                add(path)
    for pattern in ["*/paired_preflight*/*", "*/scorer_preflight/*"]:
        for path in RUN.glob(pattern):
            if path.suffix in {".py", ".json", ".log"}:
                add(path)
    for path in (RUN / "runtime").glob("*.json"):
        add(path)
    for path in (RUN / "runtime").glob("*/*.json"):
        if path.name not in {"PLATFORM_STATUS.json", "STATUS.json"}:
            add(path)
    for path in (RUN / "runtime").glob("*/*.py"):
        add(path)
    for pattern in ["*/gpu/submission_*/*.json", "*/submission_*/*.json"]:
        for path in RUN.glob(pattern):
            add(path)
    return sorted(paths), omissions


def prepare(work):
    final = json.loads((RUN / "FINAL_RESULT.json").read_text())
    if not final.get("all_registered_work_closed") or final.get("confirmation_opened"):
        raise ValueError("Closed registered work and unopened confirmation required")
    baseline = json.loads((RUN / "BASELINE.json").read_text())
    identity = development_identity()
    if identity != {
        "head": baseline["development_head"],
        "index_sha256": baseline["index_sha256"],
    }:
        raise ValueError("Development HEAD/index changed outside this publication")
    work.mkdir(parents=True, exist_ok=False)
    snapshot, bare = work / "snapshot", work / "publication.git"
    snapshot.mkdir()
    helpers = utility()
    git = helpers.git_runner(bare)
    git("init", "--bare", str(bare))
    git("remote", "add", "origin", REMOTE)
    git("config", "remote.origin.promisor", "true")
    git("config", "remote.origin.partialclonefilter", "blob:none")
    git("fetch", "--depth=1", "--filter=blob:none", "origin", "refs/heads/" + BRANCH)
    base = git("rev-parse", "FETCH_HEAD").decode().strip()
    if base != BASE:
        raise ValueError(
            "Remote tip differs from the reviewed parent; no forced update"
        )
    private = helpers.KEY_FILE.read_bytes().strip()
    entries = []

    def save(name, data):
        helpers.inspect_payload(name, data, [private])
        path = snapshot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
        entries.append(
            {
                "path": name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    paths, omissions = selection()
    for path in paths:
        save(str(path.relative_to(REPO)), path.read_bytes())
    exported = {row["path"]: row for row in entries}
    capsule_exports = {}
    for name in ["portable_capsule_01", "portable_model_capsule_01"]:
        prefix = RUN.relative_to(REPO) / name
        manifest = json.loads((snapshot / prefix / "MANIFEST.json").read_text())
        for rel, expected in manifest["files"].items():
            actual = exported.get(str(prefix / rel), {})
            if (
                actual.get("sha256") != expected["sha256"]
                or actual.get("bytes") != expected["bytes"]
            ):
                raise ValueError("Exported replay capsule member differs: " + rel)
        capsule_exports[name] = {
            "all_manifest_members_exported": True,
            "verified_members": len(manifest["files"]),
            "manifest_sha256": digest(snapshot / prefix / "MANIFEST.json"),
        }
    save("LATEST_PROGRESS_V10_CN.md", (RUN / "FINAL_REPORT_CN.md").read_bytes())
    banner = (
        "# Latest: v10 experiments and review materials\n\n"
        "Start with [the final Chinese report](LATEST_PROGRESS_V10_CN.md), "
        "[the overall plan](plans/v10_execution_20260914_01/OVERALL_PLAN_UPDATED_CN.md), "
        "and [review instructions](publication/v10_execution_20260914/REVIEW_FOR_CHATGPT_PRO_CN.md). "
        "Completed engineering checks, negative model results and remaining data gates are reported separately.\n\n"
        "The two scoped CPU replay capsules are documented in "
        "[publication scope](publication/v10_execution_20260914/README_CN.md). "
        "Earlier entries below remain historical.\n\n---\n\n"
    )
    save("README.md", (banner + git("show", base + ":README.md").decode()).encode())
    manifest = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "base_commit": base,
        "files": entries,
        "omitted_large_files": omissions,
        "omitted_categories": [
            "model weights and environments",
            "credentials",
            "full native training archives",
            "most session checkpoints and full active journals",
            "unopened confirmation data",
        ],
        "reading_bundle_is_full_reconstruction": False,
        "complete_scoped_replay_capsules": [
            "portable_capsule_01",
            "portable_model_capsule_01",
        ],
        "capsule_exports": capsule_exports,
        "original_development_identity": identity,
        "new_model_calls": 0,
    }
    manifest_name = str(PUB / "EXPORT_MANIFEST.json")
    write_new(snapshot / manifest_name, manifest)
    helpers.inspect_payload(
        manifest_name, (snapshot / manifest_name).read_bytes(), [private]
    )
    archive_name = str(PUB / "DisasterTrace_v10_code_and_results.zip")
    archive_path = snapshot / archive_name
    with zipfile.ZipFile(
        archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for row in entries:
            archive.write(snapshot / row["path"], row["path"])
        archive.write(snapshot / manifest_name, manifest_name)
    if archive_path.stat().st_size >= 90 * 1024 * 1024:
        raise ValueError("Reading archive exceeds the Git file ceiling")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Reading archive CRC mismatch")
        for row in entries:
            value = archive.read(row["path"])
            helpers.inspect_payload(row["path"], value, [private])
            if hashlib.sha256(value).hexdigest() != row["sha256"]:
                raise ValueError("Reading archive member differs")
    names = sorted([row["path"] for row in entries] + [manifest_name, archive_name])
    if len(names) != len(set(names)):
        raise ValueError("Duplicate publication paths")
    git("read-tree", base)
    blobs = (
        git(
            "hash-object",
            "-w",
            "--no-filters",
            "--stdin-paths",
            data="".join(str(snapshot / name) + "\n" for name in names).encode(),
        )
        .decode()
        .splitlines()
    )
    updates = b"".join(
        ("100644 " + sha + "\t" + name + "\0").encode()
        for name, sha in zip(names, blobs, strict=True)
    )
    git("update-index", "-z", "--index-info", data=updates)
    tree = git("write-tree").decode().strip()
    if git(
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "--diff-filter=D",
        "-r",
        base,
        tree,
    ):
        raise ValueError("Publication would delete remote paths")
    commit = (
        git(
            "commit-tree",
            tree,
            "-p",
            base,
            data=b"Publish v10 benchmark controls, model diagnostics and scoped replay capsules\n",
        )
        .decode()
        .strip()
    )
    if development_identity() != identity:
        raise ValueError("Development index or HEAD changed while packaging")
    prepared = {
        "base": base,
        "commit": commit,
        "tree": tree,
        "branch": BRANCH,
        "snapshot": str(snapshot),
        "files": names,
        "blobs": blobs,
        "manifest": manifest_name,
        "archive": archive_name,
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": digest(archive_path),
        "identity": identity,
        "force_push": False,
    }
    write_new(work / "PREPARED.json", prepared)
    print(
        json.dumps(
            {
                "prepared": True,
                "commit": commit,
                "files": len(names),
                "zip_bytes": prepared["archive_bytes"],
            }
        ),
        flush=True,
    )


def publish(work):
    prepared = json.loads((work / "PREPARED.json").read_text())
    if development_identity() != prepared["identity"]:
        raise ValueError("Development identity changed since preparation")
    snapshot = Path(prepared["snapshot"])
    manifest = json.loads((snapshot / prepared["manifest"]).read_text())
    for row in manifest["files"]:
        if digest(snapshot / row["path"]) != row["sha256"]:
            raise ValueError("Prepared publication bytes changed")
    if digest(snapshot / prepared["archive"]) != prepared["archive_sha256"]:
        raise ValueError("Prepared archive changed")
    helpers = utility()
    git = helpers.git_runner(work / "publication.git")
    remote = git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0]
    if remote != prepared["base"]:
        raise ValueError("Remote branch advanced; no forced update")
    write_new(
        work / "PUSH_INTENT.json",
        {
            "commit": prepared["commit"],
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )
    git("push", "origin", prepared["commit"] + ":refs/heads/" + BRANCH, timeout=1800)
    if (
        git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0]
        != prepared["commit"]
    ):
        raise ValueError("Remote tip not confirmed")
    other = helpers.git_runner(work / "readback.git")
    other("init", "--bare", str(work / "readback.git"))
    other("remote", "add", "origin", REMOTE)
    other("config", "remote.origin.promisor", "true")
    other("config", "remote.origin.partialclonefilter", "blob:none")
    other("fetch", "--depth=1", "--filter=blob:none", "origin", "refs/heads/" + BRANCH)
    if other("rev-parse", "FETCH_HEAD").decode().strip() != prepared["commit"]:
        raise ValueError("Independent fetch does not match publication")
    remote_tree = {}
    for row in other("ls-tree", "-r", "-z", prepared["commit"]).split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            remote_tree[name.decode()] = meta.decode().split()
    for name, blob in zip(prepared["files"], prepared["blobs"], strict=True):
        if remote_tree.get(name) != ["100644", "blob", blob]:
            raise ValueError("Remote tree differs: " + name)
    reads = [
        "README.md",
        "LATEST_PROGRESS_V10_CN.md",
        prepared["manifest"],
        prepared["archive"],
        "plans/v10_execution_20260914_01/FINAL_RESULT.json",
        "disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py",
        "disastertrace-starter/src/disastertrace/monitoring_v1/api_ledger.py",
    ]
    for name in reads:
        if hashlib.sha256(
            other("show", prepared["commit"] + ":" + name)
        ).hexdigest() != digest(snapshot / name):
            raise ValueError("Independent remote blob readback differs: " + name)
    if development_identity() != prepared["identity"]:
        raise ValueError("Development identity changed during publication")
    result = {
        "passed": True,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commit": prepared["commit"],
        "branch": BRANCH,
        "base": prepared["base"],
        "verified_tree_files": len(prepared["files"]),
        "independent_readback_files": reads,
        "development_identity_preserved": True,
        "force_push": False,
        "visibility_changed": False,
        "archive_bytes": prepared["archive_bytes"],
        "archive_sha256": prepared["archive_sha256"],
        "url": "https://github.com/sisuolv/disastertrace-benchmark/tree/next-phase-v1",
    }
    write_new(work / "PUBLISHED.json", result)
    write_new(RUN / "GITHUB_UPLOAD.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("action", choices=["prepare", "publish"])
    args = parser.parse_args()
    (prepare if args.action == "prepare" else publish)(args.work.absolute())
