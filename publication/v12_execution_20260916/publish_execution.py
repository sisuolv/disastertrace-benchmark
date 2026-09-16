"""Publish bounded code/results via isolated Git, preserving experimental inputs."""
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
RUN = REPO / "plans/v12_execution_20260915_01"
PUB = HERE.relative_to(REPO)
BASE = "808ca1912c7065ff6c774004626867676118a9cf"
BRANCH = "next-phase-v1"
REMOTE = "ssh://git@ssh.github.com:443/sisuolv/disastertrace-benchmark.git"
OBJECTS = Path("/mnt/afs/260010168/extreme_weather_benchmark/publication/v12_planning_20260915_01/publication.git/objects")
PRIOR = REPO / "publication/v11_inprogress_20260915"
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


def init_git(path, alternate=False):
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
    output = {}
    for row in git("ls-tree", "-r", "-z", revision).split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            output[name.decode()] = meta.decode().split()
    return output


def selection():
    paths = set()
    for folder in (REPO / "disastertrace-starter/src", REPO / "disastertrace-starter/tests"):
        paths.update(folder.rglob("*.py"))
    for name in ("IMPLEMENTATION_STATUS.md", "BLOCKERS.md", "DECISIONS.md", "pyproject.toml",
                 "requirements-verified.txt", "requirements-mm-cpu-v1.txt"):
        paths.add(REPO / "disastertrace-starter" / name)
    amendment = REPO / "plans/v12_review_amendment_20260915_01"
    for folder in (RUN, HERE, amendment):
        paths.update(p for p in folder.iterdir() if p.is_file() and p.suffix in {".py", ".md", ".json"}
                     and p.name not in {"ANNUAL_NATIVE_OBJECTS.json", "GITHUB_UPLOAD.json"})
    for directory in ("branch_source", "stage_c_source_02"):
        paths.update((RUN / directory).rglob("*.py"))
    for directory in ("tests", "annual_stage_B/fit", "stage_C", "stage_C_audit_handoff_01",
                      "api_compatibility_01", "api_compatibility_02"):
        paths.update(p for p in (RUN / directory).iterdir()
                     if p.is_file() and p.suffix in {".json", ".md", ".xml"})
    for name in ("DATA_QUALITY_REPORT.json", "DATA_QUALITY_REPORT_CN.md", "DOWNLOAD_STATUS.json",
                 "PREPARATION_RESULT.json", "TAIL_RESULT.json", "joins/RESULT.json"):
        paths.add(RUN / "annual_stage_B" / name)
    for folder in (RUN / "stage_C", RUN / "stage_C_audit_handoff_01/scores"):
        paths.update(folder.glob("*/SCORE_*.json"))
    for folder in (RUN / "runtime").iterdir():
        for name in ("JOB.json", "EXIT.json", "LAUNCH_CLAIM.json"):
            if (folder / name).exists():
                paths.add(folder / name)
    return sorted(p for p in paths if p.is_file() and "__pycache__" not in p.parts)


def prepare(work):
    work.mkdir(exist_ok=False)
    identity = prior.identity()
    if not read(RUN / "FINAL_VERIFICATION_01.json")["passed"]:
        raise ValueError("Execution lacks final verification")
    git = init_git(work / "publication.git", alternate=True)
    if git("rev-parse", "FETCH_HEAD").decode().strip() != BASE:
        raise ValueError("Remote advanced; preserve it and review the new base")
    snapshot = work / "snapshot"
    snapshot.mkdir()
    exported = []
    private = [helpers.KEY_FILE.read_bytes().strip()] if helpers.KEY_FILE.exists() else []
    credential = Path("/mnt/afs/260010168/.config/disastertrace/credentials/siliconflow.json")
    if credential.exists():
        private.append(read(credential)["api_key"].encode())

    def save(name, content):
        helpers.inspect_payload(name, content, private)
        dest = snapshot / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(content)
        exported.append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})

    for path in selection():
        if path.is_symlink():
            raise ValueError("Symlink excluded: " + str(path))
        save(path.relative_to(REPO).as_posix(), path.read_bytes())
    latest = """# v12 最新进展：已完成执行与结果核验

批次于 2026-09-15 22:34 UTC 收尾，最新代码与结果于 2026-09-16 发布。

- 72/72 个地区月份原生数据构建完成，补齐 52,548 个原文；年度预测器已冻结。
- 六父重建、六次原策略续跑、24 个 C2 取证分支完成；父会话同日且无正例。
- DeepSeek-V4-Flash 的 288 次正式请求完成，108 个方法运行和 24 个评分组核验通过。
- 仅 71/288 个回复符合原输出契约。861 个可结算机会中的 16 个正例集中在芝加哥同一天。
- 当前没有模型优于强覆盖率/批量共享规则的证据。模型只选择资料，概率由冻结程序输出。
- 628 个历史测试节点通过，完整 16 类和独立过程确认尚未完成。

## 阅读入口

- [实际结果与下一轮门槛](plans/v12_execution_20260915_01/FINDINGS_AND_NEXT_GATES_CN.md)
- [完整执行报告](plans/v12_execution_20260915_01/FINAL_REPORT_CN.md)
- [模型结果表与解释](plans/v12_execution_20260915_01/stage_C/REPORT_CN.md)
- [年度数据质量](plans/v12_execution_20260915_01/annual_stage_B/DATA_QUALITY_REPORT_CN.md)
- [复查说明](publication/v12_execution_20260916/REVIEW_FOR_CHATGPT_PRO_CN.md)
- [代码与结果阅读 ZIP](publication/v12_execution_20260916/DisasterTrace_v12_execution_review.zip)
- [导出范围与重现边界](publication/v12_execution_20260916/README_CN.md)

下一步优先修复真实天气接口、验证取证信息作用并覆盖多个独立过程。旧自由输出的失败保留，确认集仍关闭。
历史文档中的“未启动”“运行中”和“未上传”描述其各自记录时点，以本页和本次发布回执为当前入口。
"""
    save("LATEST_PROGRESS_V12_CN.md", latest.encode())
    banner = ("# Latest: v12 execution completed (2026-09-16 publication)\n\n"
              "Start with [current code, results and next gates](LATEST_PROGRESS_V12_CN.md) or "
              "[ChatGPT Pro review instructions](publication/v12_execution_20260916/REVIEW_FOR_CHATGPT_PRO_CN.md). "
              "The 72-month source chain and bounded model comparison are complete; LLM gains and "
              "independent confirmation remain unproved. Earlier entries below are historical.\n\n---\n\n")
    save("README.md", banner.encode() + git("show", BASE + ":README.md"))
    manifest_name = str(PUB / "EXPORT_MANIFEST.json")
    manifest = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "base_commit": BASE,
                "release_kind": "completed_development_code_and_results", "files": list(exported),
                "full_experiment_reproduction_included": False,
                "excluded": ["credentials", "raw annual source cache", "full journals/checkpoints", "model weights", "confirmation data"],
                "historical_execution_record_unchanged": True, "github_CI_run_claim": False}
    save(manifest_name, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    archive_name = str(PUB / "DisasterTrace_v12_execution_review.zip")
    archive_path = snapshot / archive_name
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in exported:
            archive.write(snapshot / row["path"], row["path"])
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for row in exported:
            if hashlib.sha256(archive.read(row["path"])).hexdigest() != row["sha256"]:
                raise ValueError("ZIP member mismatch")
    if archive_path.stat().st_size > 45 * 1024 * 1024:
        raise ValueError("Review ZIP exceeds bounded publication size")
    names = sorted([row["path"] for row in exported] + [archive_name])
    blobs = git("hash-object", "-w", "--no-filters", "--stdin-paths",
                data="".join(str(snapshot / name) + "\n" for name in names).encode()).decode().splitlines()
    tree = prior.overlay_tree(git, names, blobs)
    before, after = entries(git, BASE), entries(git, tree)
    if set(before) - set(after) or any(before[n] != after[n] for n in set(before) - set(names)):
        raise ValueError("Unselected remote content changed")
    commit = git("commit-tree", tree, "-p", BASE,
                 data=b"Publish completed v12 source, annual data audit and model evaluation results\n").decode().strip()
    if prior.identity() != identity:
        raise ValueError("Development identity changed during snapshot preparation")
    write(work / "PRE_PUSH_AUDIT.json", {"passed": True, "added": len(set(after) - set(before)),
        "modified": [n for n in before if before[n] != after[n]], "removed": 0,
        "unselected_unchanged": True, "payloads_checked": len(exported), "zip_verified": True})
    write(work / "PREPARED.json", {"base": BASE, "commit": commit, "tree": tree, "files": names,
        "blobs": blobs, "identity": identity, "archive": archive_name, "manifest": manifest_name,
        "archive_sha256": digest(archive_path), "archive_bytes": archive_path.stat().st_size})
    print(json.dumps({"prepared": True, "commit": commit, "files": len(names), "zip_bytes": archive_path.stat().st_size}), flush=True)


def publish(work):
    prepared = read(work / "PREPARED.json")
    if not read(work / "EXPORT_VALIDATION.json")["passed"]:
        raise ValueError("Export validation must pass before push")
    if prior.identity() != prepared["identity"]:
        raise ValueError("Development identity changed before publication")
    snapshot = work / "snapshot"
    for row in read(snapshot / prepared["manifest"])["files"]:
        if digest(snapshot / row["path"]) != row["sha256"]:
            raise ValueError("Prepared file changed")
    if digest(snapshot / prepared["archive"]) != prepared["archive_sha256"]:
        raise ValueError("Prepared ZIP changed")
    git = helpers.git_runner(work / "publication.git")
    if git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0] != BASE:
        raise ValueError("Remote advanced; no force push")
    write(work / "PUSH_INTENT.json", {"commit": prepared["commit"], "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    git("push", "origin", prepared["commit"] + ":refs/heads/" + BRANCH)
    other = init_git(work / "readback.git")
    if other("rev-parse", "FETCH_HEAD").decode().strip() != prepared["commit"]:
        raise ValueError("Independent remote commit mismatch")
    remote_tree = entries(other, prepared["commit"])
    for name, blob in zip(prepared["files"], prepared["blobs"], strict=True):
        if remote_tree.get(name) != ["100644", "blob", blob]:
            raise ValueError("Remote tree mismatch: " + name)
    readbacks = ["README.md", "LATEST_PROGRESS_V12_CN.md", str(PUB / "REVIEW_FOR_CHATGPT_PRO_CN.md"),
                 "plans/v12_execution_20260915_01/RESULT_SUMMARY.json",
                 "disastertrace-starter/src/disastertrace/monitoring_v1/residual_query_plan.py",
                 prepared["manifest"], prepared["archive"]]
    for name in readbacks:
        if hashlib.sha256(other("show", prepared["commit"] + ":" + name)).hexdigest() != digest(snapshot / name):
            raise ValueError("Remote file bytes mismatch: " + name)
    if prior.identity() != prepared["identity"]:
        raise ValueError("Development identity changed during publication")
    result = {"passed": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commit": prepared["commit"], "base": BASE, "branch": BRANCH,
        "verified_tree_files": len(prepared["files"]), "readback_files": readbacks,
        "archive_bytes": prepared["archive_bytes"], "archive_sha256": prepared["archive_sha256"],
        "force_push": False, "development_identity_preserved_since_prepare": True,
        "release_kind": "completed_development_code_and_results"}
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
