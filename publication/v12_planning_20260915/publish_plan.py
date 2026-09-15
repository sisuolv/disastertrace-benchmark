"""Publish the reviewed plan files using isolated Git and verify remote bytes."""

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLAN = REPO / "plans/v12_planning_20260915_01"
PUB = HERE.relative_to(REPO)
BASE = "889620a4fc4ee6ad70757dd3e832a40c7509126a"
BRANCH = "next-phase-v1"
REMOTE = "ssh://git@ssh.github.com:443/sisuolv/disastertrace-benchmark.git"
PRIOR = REPO / "publication/v11_inprogress_20260915"
OBJECTS = Path("/mnt/afs/260010168/extreme_weather_benchmark/publication/v11_inprogress_20260915_02/publication.git/objects")
sys.path.insert(0, str(PRIOR))
import publication_helpers as helpers

spec = importlib.util.spec_from_file_location("prior_publication", PRIOR / "publish_progress.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.BASE = BASE


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def init_git(path, *, alternate=False):
    git = helpers.git_runner(path)
    git("init", "--bare", str(path))
    git("remote", "add", "origin", REMOTE)
    git("config", "remote.origin.promisor", "true")
    git("config", "remote.origin.partialclonefilter", "blob:none")
    if alternate:
        (path / "objects/info/alternates").write_text(str(OBJECTS) + "\n")
    git("fetch", "--depth=1", "--filter=blob:none", "origin", "refs/heads/" + BRANCH)
    return git


def entries(git, revision):
    result = {}
    for row in git("ls-tree", "-r", "-z", revision).split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            result[name.decode()] = meta.decode().split()
    return result


def prepare(work):
    work.mkdir(exist_ok=False)
    identity = prior.identity()
    baseline = read(PLAN / "CURRENT_STATE_01.json")
    if identity != {k: baseline["development_git"][k] for k in ("head", "index_sha256")}:
        raise ValueError("Development identity changed")
    for name, sha in baseline["source_bindings"].items():
        if digest(REPO / name) != sha:
            raise ValueError("Protected production source changed: " + name)
    if read(PLAN / "WORK_PACKAGES.json")["execution_authorized"]:
        raise ValueError("Expected a review-only plan")
    git = init_git(work / "publication.git", alternate=True)
    if git("rev-parse", "FETCH_HEAD").decode().strip() != BASE:
        raise ValueError("Remote advanced; preserve it and stop")
    snapshot = work / "snapshot"
    snapshot.mkdir()
    exported = []
    private = [helpers.KEY_FILE.read_bytes().strip()] if helpers.KEY_FILE.exists() else []

    def save(name, data):
        helpers.inspect_payload(name, data, private)
        path = snapshot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        exported.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    for directory in (PLAN, HERE):
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.is_symlink():
                raise ValueError("Symlink excluded")
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            save(str(path.relative_to(REPO)), path.read_bytes())
    inputs = read(PLAN / "REVIEW_INPUTS.json")["inputs"]
    originals = []
    for item in inputs:
        path = Path(item["source_path"])
        if digest(path) != item["sha256"]:
            raise ValueError("Review source changed")
        name = str(PLAN.relative_to(REPO) / "original_inputs" / path.name)
        save(name, path.read_bytes())
        originals.append({"original_name": path.name, "export_path": name, "sha256": item["sha256"]})
        for member in item["members"]:
            if digest(PLAN / member["path"]) != member["sha256"]:
                raise ValueError("Extracted source changed")
    save(str(PUB / "ORIGINAL_INPUTS.json"), (json.dumps(originals, ensure_ascii=False, indent=2) + "\n").encode())
    latest = """# v12 整体计划：待执行前复核

本次更新发布整体计划与首批执行规格，新增执行尚未启动。
此前登记的 v11 任务保持原流程；规划中的状态是 2026-09-15 13:28—13:29 UTC 观察，不是实时看板。

- [整体计划](plans/v12_planning_20260915_01/OVERALL_PLAN_CN.md)
- [下一批执行规格](plans/v12_planning_20260915_01/NEXT_BATCH_EXECUTION_CN.md)
- [七份审查意见取舍与源码核对](plans/v12_planning_20260915_01/REVIEW_DECISIONS_CN.md)
- [给 ChatGPT Pro 的复核说明](publication/v12_planning_20260915/REVIEW_FOR_CHATGPT_PRO_CN.md)
- [完整阅读 ZIP](publication/v12_planning_20260915/DisasterTrace_v12_planning_review.zip)
- [导出范围与状态边界](publication/v12_planning_20260915/README_CN.md)

建议先复核阶段 A：整周派生分析、C2 完整来源与字段依赖、最多六个父状态和24个程序分支、
年度缺片/原文清单。新模型/API/GPU、全年拟合和确认均不在已执行范围。
生产代码基准仍为本次提交的父版本889620a4；本次不修改benchmark实现或历史结果。
"""
    save("LATEST_PLAN_V12_CN.md", latest.encode())
    banner = ("# Latest: v12 plan awaiting review\n\n"
        "Start with [the integrated plan and next batch](LATEST_PLAN_V12_CN.md) or "
        "[ChatGPT Pro review instructions](publication/v12_planning_20260915/REVIEW_FOR_CHATGPT_PRO_CN.md). "
        "This update publishes planning materials; no new benchmark execution is authorized or launched. "
        "Earlier entries below are historical snapshots.\n\n---\n\n")
    save("README.md", banner.encode() + git("show", BASE + ":README.md"))
    manifest_name = str(PUB / "EXPORT_MANIFEST.json")
    manifest = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "base_commit": BASE,
        "release_kind": "plan_for_review", "execution_authorized": False,
        "source_observation_at": baseline["observed_at"], "files": list(exported),
        "production_code_changes": False, "standalone_benchmark_reproduction": False}
    save(manifest_name, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    archive_name = str(PUB / "DisasterTrace_v12_planning_review.zip")
    archive_path = snapshot / archive_name
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in exported:
            archive.write(snapshot / row["path"], row["path"])
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        for row in exported:
            if hashlib.sha256(archive.read(row["path"])).hexdigest() != row["sha256"]:
                raise ValueError("ZIP member mismatch")
    names = sorted([row["path"] for row in exported] + [archive_name])
    blobs = git("hash-object", "-w", "--no-filters", "--stdin-paths",
        data="".join(str(snapshot / name) + "\n" for name in names).encode()).decode().splitlines()
    tree = prior.overlay_tree(git, names, blobs)
    before, after = entries(git, BASE), entries(git, tree)
    if set(before) - set(after):
        raise ValueError("Unexpected deletions")
    if any(before[n] != after[n] for n in set(before) - set(names)):
        raise ValueError("Unselected remote content changed")
    changed = [n for n in before if before[n] != after[n]]
    if changed != ["README.md"]:
        raise ValueError("Unexpected existing-file changes")
    commit = git("commit-tree", tree, "-p", BASE,
        data=b"Publish v12 integrated research plan and pre-execution review bundle\n").decode().strip()
    if prior.identity() != identity:
        raise ValueError("Development identity changed during preparation")
    write(work / "PRE_PUSH_AUDIT.json", {"passed": True, "added": len(set(after)-set(before)),
        "modified": changed, "removed": 0, "unselected_unchanged": True,
        "payloads_checked": len(exported), "zip_verified": True})
    prepared = {"base": BASE, "commit": commit, "tree": tree, "files": names, "blobs": blobs,
        "identity": identity, "archive": archive_name, "manifest": manifest_name,
        "archive_sha256": digest(archive_path), "archive_bytes": archive_path.stat().st_size}
    write(work / "PREPARED.json", prepared)
    print(json.dumps({k: v for k, v in prepared.items() if k not in {"files", "blobs"}}), flush=True)


def publish(work):
    prepared = read(work / "PREPARED.json")
    if prior.identity() != prepared["identity"]:
        raise ValueError("Development identity changed before push")
    snapshot = work / "snapshot"
    manifest = read(snapshot / prepared["manifest"])
    for row in manifest["files"]:
        if digest(snapshot / row["path"]) != row["sha256"]:
            raise ValueError("Prepared snapshot changed")
    if digest(snapshot / prepared["archive"]) != prepared["archive_sha256"]:
        raise ValueError("Archive changed")
    git = helpers.git_runner(work / "publication.git")
    if git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0] != BASE:
        raise ValueError("Remote advanced; no overwrite")
    write(work / "PUSH_INTENT.json", {"commit": prepared["commit"], "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    git("push", "origin", prepared["commit"] + ":refs/heads/" + BRANCH, timeout=600)
    other = init_git(work / "readback.git")
    if other("rev-parse", "FETCH_HEAD").decode().strip() != prepared["commit"]:
        raise ValueError("Independent remote commit mismatch")
    remote_tree = entries(other, prepared["commit"])
    for name, blob in zip(prepared["files"], prepared["blobs"], strict=True):
        if remote_tree.get(name) != ["100644", "blob", blob]:
            raise ValueError("Remote tree mismatch: " + name)
    readbacks = ["README.md", "LATEST_PLAN_V12_CN.md", str(PLAN.relative_to(REPO) / "OVERALL_PLAN_CN.md"),
        str(PLAN.relative_to(REPO) / "NEXT_BATCH_EXECUTION_CN.md"), str(PUB / "REVIEW_FOR_CHATGPT_PRO_CN.md"),
        prepared["manifest"], prepared["archive"]]
    for name in readbacks:
        if hashlib.sha256(other("show", prepared["commit"] + ":" + name)).hexdigest() != digest(snapshot / name):
            raise ValueError("Remote file bytes mismatch: " + name)
    if prior.identity() != prepared["identity"]:
        raise ValueError("Development identity changed during push")
    result = {"passed": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(), "commit": prepared["commit"],
        "base": BASE, "branch": BRANCH, "verified_tree_files": len(prepared["files"]),
        "readback_files": readbacks, "archive_bytes": prepared["archive_bytes"],
        "archive_sha256": prepared["archive_sha256"], "release_kind": "plan_for_review",
        "execution_authorized": False, "force_push": False, "development_identity_preserved": True}
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
