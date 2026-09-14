"""Publish the closed batch from an isolated Git database after its pause receipt."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PUBLICATION = HERE.relative_to(REPO)
BATCH = REPO / "plans/v9_followup_execution_20260914_01"
RUNTIME = BATCH / "runtime/github_after_pause_01"
REMOTE = "ssh://git@ssh.github.com:443/sisuolv/disastertrace-benchmark.git"
BRANCH = "next-phase-v1"
SSH = (
    "ssh -i /mnt/afs/260010168/.ssh/github_ed25519 -o IdentitiesOnly=yes "
    "-o BatchMode=yes -o StrictHostKeyChecking=yes "
    "-o UserKnownHostsFile=/mnt/afs/260010168/.ssh/github_review_known_hosts -o ConnectTimeout=15"
)
REVIEW = "DisasterTrace_v9_code_and_results.zip"
KEY_FILE = Path("/mnt/afs/260010168/.config/disastertrace/deepseek_followup_20260914.key")
SENSITIVE = {
    "api_token": re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer_value": re.compile(rb"(?i)Bearer\s+[A-Za-z0-9._~+/-]{24,}"),
    "signed_url": re.compile(rb"(?i)[?&](?:X-Amz-Signature|Signature|Key-Pair-Id|GoogleAccessId)="),
    "jwt": re.compile(rb"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{40,}"),
}


def read(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_once(path, value):
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, path)
    temporary.unlink()


def status(phase, **fields):
    row = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": phase, **fields}
    with (RUNTIME / "EVENTS.jsonl").open("a") as stream:
        stream.write(json.dumps(row) + "\n")
    temporary = RUNTIME / "STATUS.next"
    temporary.write_text(json.dumps(row, indent=2) + "\n")
    temporary.replace(RUNTIME / "STATUS.json")


def code_files():
    paths = []
    for module in ["monitoring_v1", "monitoring_fixed_v1"]:
        paths += list((REPO / "disastertrace-starter/src/disastertrace" / module).rglob("*.py"))
    paths += list((REPO / "disastertrace-starter/tests").glob("test_monitoring*.py"))
    paths += list((BATCH / "scripts").glob("*.py"))
    paths += list(HERE.glob("*.py"))
    return sorted(set(paths))


def selected_files():
    paths = set(code_files())
    omissions = []

    def add(path, limit=8 * 1024 * 1024):
        if not path.is_file():
            return
        if path.is_symlink():
            raise ValueError("Symlink in publication selection: " + str(path.relative_to(REPO)))
        if path.stat().st_size > limit:
            omissions.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size,
                              "reason": "Large reconstruction input omitted from this reading/code publication"})
        else:
            paths.add(path)

    for name in ["CURRENT_PHASE.md", "IMPLEMENTATION_STATUS.md", "BLOCKERS.md", "DECISIONS.md", "pyproject.toml"]:
        add(REPO / "disastertrace-starter" / name)
    for folder in [BATCH, REPO / "plans/v9_followup_roadmap_20260914_01",
                   REPO / "plans/v9_integration_execution_20260914_01"]:
        for p in folder.iterdir():
            if p.suffix in {".md", ".json"}:
                add(p)
    for p in (BATCH / "validation").iterdir():
        if p.suffix in {".json", ".xml", ".log"}:
            add(p)
    report_names = {"VALIDATION.json", "SUMMARY.json", "COVERAGE.json", "SPLITS.json",
                    "AFS_INCIDENT_REPORT.json", "N1_VALIDATION.json", "TEMPERATURE_POSITIVE_COVERAGE.json",
                    "BANK.json", "BANK_RAW.json", "DIRECT_EQUIVALENCE.json", "RESULT.json"}
    for folder in [BATCH / "reports", REPO / "plans/v9_integration_execution_20260914_01/reports"]:
        for p in folder.rglob("*"):
            if p.suffix == ".md" or p.name in report_names or p.name.endswith("__CANONICAL_SCORES.json"):
                add(p)
    add(BATCH / "reports/process_manifest_02/DATA_PROCESS_MANIFEST.json")
    # Preserve the failed original as a collection result, without copying raw data archives.
    for name in ["BUDGET.json", "COMPLETE.json", "RESULTS.json"]:
        add(BATCH / "api_evidence_01" / name)
    for p in (BATCH / "api_evidence_02").rglob("*"):
        if p.suffix in {".json", ".py", ".body"}:
            add(p)
    for pilot in ["api_pilot_01", "api_rare_pilot_01"]:
        root = BATCH / pilot
        for name in ["PREREGISTRATION.json", "BUDGET.json", "PROGRAM_COMPLETE.json", "COMPLETE.json"]:
            add(root / name)
        for pattern in ["*/CONFIGS.json", "*/COMPARISON.json", "*/FREEZE.json", "*/OUTCOMES.json",
                        "*/*/COMPLETE.json", "*/*/EXIT.json", "*/*/SCORES.json",
                        "*/*/captures/*/REQUEST.json", "*/*/captures/*/RESPONSE.json",
                        "*/*/captures/*/WIRE_RECEIPT.json", "*/*/captures/*/RESPONSE.body",
                        "*/*/captures/*/FAILURE.json"]:
            for p in root.glob(pattern):
                add(p)
    for name in ["temperature_stream_02", "temperature_fullcalendar_01"]:
        root = BATCH / name
        for pattern in ["*.json", "*/SCORES.json", "*/*/COMPLETE.json"]:
            for p in root.glob(pattern):
                add(p)
    for region in ["bay", "new_york", "chicago", "denver"]:
        for name in ["RESULT.json", "SOURCE_NATIVE_PLAN.json"]:
            add(BATCH / "regional_training_02" / region / name)
    for p in (BATCH / "runtime").glob("*.json"):
        add(p)
    for folder in ["cpu_handoff_01", "temperature_fullcalendar_01", "pause_after_batch_01"]:
        for p in (BATCH / "runtime" / folder).glob("*.json"):
            if p.name not in {"PLATFORM_STATUS.json", "STATUS.json", "JOB_STATUS_01.json"}:
                add(p)
    add(HERE / "README_CN.md")
    add(HERE / "AUTHORIZATION.json")
    for p in RUNTIME.glob("tests_*.xml"):
        add(p)
    for p in RUNTIME.glob("tests_*.command.json"):
        add(p)
    return sorted(paths), omissions


def inspect_payload(name, content, private_values=()):
    path = Path(name)
    if (path.is_absolute() or ".." in path.parts or any(c in name for c in "\n\r\t\0")
            or any(part in {".git", ".ssh", ".config", ".venv", "__pycache__"} for part in path.parts)
            or path.suffix in {".key", ".pem"} or path.name.startswith(".env")):
        raise ValueError("Excluded publication path: " + name)
    if len(content) >= 90 * 1024 * 1024:
        raise ValueError("Publication file exceeds size ceiling: " + name)
    for label, pattern in SENSITIVE.items():
        if pattern.search(content):
            raise ValueError("Credential or signed-URL pattern " + label + " in " + name)
    if any(value and value in content for value in private_values):
        raise ValueError("Known private credential found in " + name)


def git_runner(bare):
    env = dict(os.environ, GIT_SSH_COMMAND=SSH, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Codex", GIT_AUTHOR_EMAIL="codex@localhost",
               GIT_COMMITTER_NAME="Codex", GIT_COMMITTER_EMAIL="codex@localhost")
    for name in ["GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_QUARANTINE_PATH"]:
        env.pop(name, None)

    def git(*args, data=None, timeout=600):
        reply = subprocess.run(["git", "-c", "safe.directory=" + str(bare), "--git-dir=" + str(bare), *args], env=env,
                               input=data, capture_output=True, timeout=timeout, check=False)
        if reply.returncode:
            # No remote credentials or environment are printed on failure.
            raise RuntimeError("Git operation failed: " + args[0] + "; exit=" + str(reply.returncode))
        return reply.stdout

    return git


def publish():
    authorization = read(HERE / "AUTHORIZATION.json")
    paused = read(BATCH / "PAUSED_RESULT.json")
    done = read(BATCH / "runtime/pause_after_batch_01/COMPLETE.json")
    if not done or not done.get("paused") or not paused or paused.get("phase") != "PAUSED_FOR_USER_REVIEW":
        raise ValueError("Final pause receipt required before publication")
    if {str(p.relative_to(REPO)) for p in code_files()} != set(authorization["fixed_code"]):
        raise ValueError("Code inventory changed after publication preparation")
    for name, sha in authorization["fixed_code"].items():
        if digest(REPO / name) != sha:
            raise ValueError("Code changed after publication preparation: " + name)
    status("BUILDING_FINAL_PUBLICATION", scientific_batch_passed=paused["all_registered_work_verified"])
    work = REPO / "review-outputs/v9_followup_publication_20260914_01"
    work.mkdir(parents=True, exist_ok=False)
    bare, snapshot = work / "publication.git", work / "snapshot"
    snapshot.mkdir()
    git = git_runner(bare)
    git("init", "--bare", str(bare))
    git("remote", "add", "origin", REMOTE)
    git("config", "remote.origin.promisor", "true")
    git("config", "remote.origin.partialclonefilter", "blob:none")
    git("fetch", "--depth=1", "--filter=blob:none", "origin", "refs/heads/" + BRANCH)
    base = git("rev-parse", "FETCH_HEAD").decode().strip()
    if base != authorization.get("remote_tip", base):
        raise ValueError("Remote branch changed after authorization snapshot; review before publication")
    old_readme = git("show", base + ":README.md").decode()
    files, omissions = selected_files()
    private = KEY_FILE.read_bytes().strip()
    entries = []

    def save(name, data):
        inspect_payload(name, data, [private])
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        entries.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    for p in files:
        if p.is_symlink():
            raise ValueError("Symlink in selected files")
        name = str(p.relative_to(REPO))
        content = p.read_bytes()
        expected = authorization["fixed_code"].get(name)
        if expected is not None and hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Code changed during snapshot construction: " + name)
        save(name, content)
    summary = (BATCH / "PAUSED_SUMMARY_CN.md").read_text()
    save("LATEST_PROGRESS_20260914_CN.md", summary.encode())
    banner = ("# Latest: v9 follow-up paused for review\n\n"
              "The current computation and audits have ended; scientific failures, if any, remain explicit. "
              "Start with [the final Chinese results](LATEST_PROGRESS_20260914_CN.md), "
              "[publication scope](publication/v9_followup_20260914/README_CN.md), and "
              "[review questions](publication/v9_followup_20260914/REVIEW_FOR_CHATGPT_PRO_CN.md).\n\n"
              "Older progress notes below are historical and do not supersede the final pause record.\n\n---\n\n")
    save("README.md", (banner + old_readme).encode())
    questions = """# ChatGPT Pro 复查入口

先读根目录 LATEST_PROGRESS_20260914_CN.md，再检查本目录 EXPORT_MANIFEST.json 与 review ZIP。代码与结果来自本轮已结束的任务；通过验证和未通过的部分必须分别评价。

重点复查：

1. E02 的 42 个底层问题与 1,008 次相依视图调用是否被正确区分？Pro 的逐槽正确、最终汇总错误是否有原始回答支持？
2. 连续 F 是否在相同机会与结果掩膜下比较 FOLLOW、COPY、强程序基线和模型？概率数值变化是否被误当作新预测信息？
3. 普通日历与按已知正例选定的 Denver 诊断是否分开？跨阈值、站点、相邻日期的依赖是否限制结论？
4. 四区域独立时期拟合/校准、未知费用预留、AFS 采集修复与时间语义是否可核对？是否有评估侧标签流入模型输入？
5. 温度扩展是否正确处理同成员三日事件、多个起报版本、原生 DWD 日极值和未来完整日？注意其仍是程序轨，没有温度 LLM 成绩。
6. C1/C2 的现有证据支持到什么程度，哪些只是开发现象？哪些门槛应在独立确认、持久修订或跨灾种模型评价前补齐？

原始大体积原生数据、完整运行检查点和 F 事件日志未完整附带，因此这是一份代码与审查材料发布包，不是全量重建包。报告中的本机审计结果不等于你已独立重跑。请勿运行历史模型启动器：其请求范围与启动标记均已消耗。
"""
    save(str(PUBLICATION / "REVIEW_FOR_CHATGPT_PRO_CN.md"), questions.encode())
    manifest = {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(), "base_commit": base,
                "branch": BRANCH, "files": entries, "omitted_large_files": omissions,
                "scope": "Current monitoring code/tests, v9 plans, completed summaries, E02 responses and disclosed inputs, F captures and score exports; not complete raw-data/checkpoint reconstruction",
                "omitted_categories": ["model weights and installed environments", "credentials",
                    "large native-data archives", "full F event journals and controller checkpoints",
                    "bulk qualification inputs and large process manifests"],
                "all_registered_work_verified": paused["all_registered_work_verified"],
                "new_model_calls_from_publication": 0, "visibility_change": False}
    manifest_path = snapshot / PUBLICATION / "EXPORT_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    inspect_payload(str(PUBLICATION / "EXPORT_MANIFEST.json"), manifest_path.read_bytes(), [private])
    archive_path = snapshot / PUBLICATION / REVIEW
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in entries:
            archive.write(snapshot / row["path"], row["path"])
        archive.write(manifest_path, str(PUBLICATION / "EXPORT_MANIFEST.json"))
    if archive_path.stat().st_size >= 90 * 1024 * 1024:
        raise ValueError("Reading ZIP exceeds the Git file ceiling")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Reading ZIP CRC failure")
        for row in entries:
            raw = archive.read(row["path"])
            inspect_payload(row["path"], raw, [private])
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("Reading ZIP member hash differs")
    extra = [str(PUBLICATION / "EXPORT_MANIFEST.json"), str(PUBLICATION / REVIEW)]
    names = sorted([r["path"] for r in entries] + extra)
    if len(names) != len(set(names)):
        raise ValueError("Duplicate export path")
    write_once(work / "PAYLOAD_VALIDATION.json", {
        "passed": True, "files": len(names), "reading_zip_bytes": archive_path.stat().st_size,
        "credential_patterns_and_known_private_value_checked": True,
        "all_zip_members_crc_and_sha256_checked": True,
    })
    git("read-tree", base)
    blobs = git("hash-object", "-w", "--no-filters", "--stdin-paths",
                data="".join(str(snapshot / n) + "\n" for n in names).encode()).decode().splitlines()
    if len(blobs) != len(names):
        raise ValueError("Blob count differs")
    updates = b"".join(("100644 " + sha + "\t" + name + "\0").encode()
                       for name, sha in zip(names, blobs, strict=True))
    git("update-index", "-z", "--index-info", data=updates)
    tree = git("write-tree").decode().strip()
    if git("diff-tree", "--no-commit-id", "--name-only", "--diff-filter=D", "-r", base, tree):
        raise ValueError("Publication would delete existing remote paths")
    if git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0] != base:
        raise ValueError("Remote branch advanced during packaging; no forced update")
    message = ("Publish v9 follow-up code and paused benchmark results\n\n"
               "Include regional calibration, corrected DeepSeek evidence captures, "
               "continuous forecast comparisons, temperature control results and final "
               "audit boundaries. Preserve original collection failures and unfinished gates.\n")
    commit = git("commit-tree", tree, "-p", base, data=message.encode()).decode().strip()
    prepared = {"base": base, "commit": commit, "tree": tree, "branch": BRANCH,
                "selected_files": len(names), "manifest_sha256": digest(manifest_path),
                "reading_zip_sha256": digest(archive_path), "snapshot": str(snapshot),
                "original_project_git_index_or_refs_modified": False, "force_push": False}
    write_once(work / "PREPARED.json", prepared)
    status("PUSHING_CHECKED_COMMIT", commit=commit, selected_files=len(names))
    git("push", "origin", commit + ":refs/heads/" + BRANCH, timeout=1800)
    if git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0] != commit:
        raise ValueError("Remote tip not confirmed after push")
    # Re-fetch tree and selected contents from GitHub in an independent object store.
    readback = work / "readback.git"
    other = git_runner(readback)
    other("init", "--bare", str(readback))
    other("remote", "add", "origin", REMOTE)
    other("config", "remote.origin.promisor", "true")
    other("config", "remote.origin.partialclonefilter", "blob:none")
    other("fetch", "--depth=1", "--filter=blob:none", "origin", "refs/heads/" + BRANCH)
    if other("rev-parse", "FETCH_HEAD").decode().strip() != commit:
        raise ValueError("Independent remote fetch differs")
    remote_entries = {}
    for row in other("ls-tree", "-r", "-z", commit).split(b"\0"):
        if row:
            metadata, name = row.split(b"\t", 1)
            remote_entries[name.decode()] = metadata.decode().split()
    for name, blob in zip(names, blobs, strict=True):
        if remote_entries.get(name) != ["100644", "blob", blob]:
            raise ValueError("Fetched tree does not match selected blob: " + name)
    read_names = ["README.md", "LATEST_PROGRESS_20260914_CN.md",
                  str(PUBLICATION / "EXPORT_MANIFEST.json"), str(PUBLICATION / REVIEW),
                  "disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py",
                  "disastertrace-starter/src/disastertrace/monitoring_v1/session_checkpoint.py",
                  str((BATCH / "PAUSED_RESULT.json").relative_to(REPO))]
    for name in read_names:
        if hashlib.sha256(other("show", commit + ":" + name)).hexdigest() != digest(snapshot / name):
            raise ValueError("Remote readback hash mismatch: " + name)
    prepared.update(passed=True, at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    remote_ref_matches=True, independently_verified_tree_files=len(names),
                    independently_read_back=read_names,
                    url="https://github.com/sisuolv/disastertrace-benchmark/tree/next-phase-v1",
                    batch_remains_paused=True)
    write_once(work / "PUBLISHED.json", prepared)
    write_once(BATCH / "GITHUB_UPLOAD_AFTER_PAUSE.json", prepared)
    status("PUBLISHED_AND_PAUSED", commit=commit, remote_verified=True)


def wait_and_publish():
    write_once(RUNTIME / "CLAIM.json", {"pid": os.getpid(), "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    status("WAITING_FOR_FINAL_PAUSE")
    deadline = time.monotonic() + 12 * 3600
    while time.monotonic() < deadline:
        done = read(BATCH / "runtime/pause_after_batch_01/COMPLETE.json")
        if done and done.get("paused"):
            publish()
            return
        time.sleep(30)
    status("WAIT_LIMIT_REACHED", published=False, no_automatic_retry=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    options = parser.parse_args()
    try:
        wait_and_publish() if options.wait else publish()
    except Exception as exc:
        status("STOPPED_AT_PUBLICATION_GATE", error_type=type(exc).__name__, reason=str(exc),
               no_automatic_retry=True)
        raise
