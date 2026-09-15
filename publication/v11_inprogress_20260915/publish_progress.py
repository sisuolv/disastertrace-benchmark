"""Publish a bounded in-progress snapshot without touching the development index."""

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

import publication_helpers as helpers

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUN = REPO / "plans/v11_execution_20260915_01"
PLANNING = REPO / "plans/v11_planning_20260915_01"
PUB = HERE.relative_to(REPO)
BASE = "1fd6821fef15b26898a57c74d4715714f33ea779"
BRANCH = "next-phase-v1"
REMOTE = "ssh://git@ssh.github.com:443/sisuolv/disastertrace-benchmark.git"
DEV_GIT = Path("/mnt/afs/260010168/extreme_weather_benchmark/github_review/disastertrace-benchmark/.git/worktrees/disastertrace-next")


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def identity():
    result = subprocess.run(["git", "--git-dir=" + str(DEV_GIT), "rev-parse", "HEAD"],
        env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), capture_output=True, check=True, text=True)
    return {"head": result.stdout.strip(), "index_sha256": digest(DEV_GIT / "index")}


def overlay_tree(git, names, blobs):
    # Preserve remote entries without read-tree's eager hydration of historical blobs.
    root = {}
    for name, blob in zip(names, blobs, strict=True):
        parts, node = name.split("/"), root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = blob

    def build(parent, changes):
        entries = {}
        if parent:
            for row in git("ls-tree", "-z", parent).split(b"\0"):
                if row:
                    meta, name = row.split(b"\t", 1)
                    entries[name.decode()] = meta.decode().split()
        for name, value in changes.items():
            previous = entries.get(name)
            if isinstance(value, dict):
                if previous and previous[1] != "tree":
                    raise ValueError("Publication directory conflicts with an existing file")
                entries[name] = ("040000", "tree", build(previous[2] if previous else None, value))
            else:
                if previous and previous[1] == "tree":
                    raise ValueError("Publication file conflicts with an existing directory")
                entries[name] = ("100644", "blob", value)
        records = [f"{mode} {kind} {blob}\t{name}\0".encode()
                   for name, (mode, kind, blob) in sorted(entries.items())]
        return git("mktree", "-z", "--missing", data=b"".join(records)).decode().strip()

    return build(BASE, root)


def progress():
    units = [read(p) for p in sorted((RUN / "annual_catalog_01").glob("*/RESULT.json"))]
    jobs = []
    for p in sorted((RUN / "runtime").glob("*/JOB.json")):
        exit_path = p.parent / "EXIT.json"
        records = []
        log = p.parent / "worker.log"
        if log.exists() and p.parent.name.startswith("fullweek02_shard"):
            for line in log.read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "finished" in row and "expected" in row:
                    records.append(row)
        jobs.append({**read(p), "runtime": p.parent.name,
            "worker_exit": read(exit_path).get("exit_code") if exit_path.exists() else None,
            "last_reported_progress": records[-1] if records else None})
    data = {"snapshot_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "release_kind": "in_progress_code_and_status_snapshot", "all_work_complete": False,
        "regression": read(RUN / "REGRESSION_RESULT_02.json"),
        "real_preflight": read(RUN / "real_pilot_02/RESULT.json"),
        "profile": read(RUN / "profile_01/RESULT.json"),
        "fullweek_status": read(RUN / "STATUS_03.json"),
        "fullweek_expected": {"daily_cases": 168, "trajectories": 840, "opportunities": 12096},
        "fullweek_audit_complete": (RUN / "fullweek_02/RESULT.json").exists(),
        "annual_catalog": {"expected_region_months": 72, "expected_logical_slices": 432,
            "completed_region_months": sum(r["complete"] for r in units),
            "failed_region_months": [r for r in units if not r["complete"]],
            "pending_region_months": 72-len(units)},
        "native_sample": {"registered_native_originals": 2470, "expected_regions": 3,
            "completed_regions": sum(read(p)["complete"] for p in (RUN / "annual_native_sample_01").glob("*/RESULT.json")),
            "full_year_native_complete": False, "annual_fit_complete": False},
        "c2": read(RUN / "c2_design_01/RESULT.json"), "jobs": jobs,
        "new_benchmark_model_calls": 0, "codex_development_token_usage": "not measured; not zero by inference",
        "confirmation_opened": False, "publication_freezes_observation_only": True}
    write(HERE / "PROGRESS_SNAPSHOT.json", data)
    return data


def selection():
    paths = set()

    def add(path):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            if path.is_symlink():
                raise ValueError("Symlink is outside this publication scope")
            paths.add(path)

    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        for p in (REPO / "disastertrace-starter/src/disastertrace" / module).rglob("*.py"):
            add(p)
    for p in (REPO / "disastertrace-starter/tests").glob("test_monitoring*.py"):
        add(p)
    for name in ("IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md", "pyproject.toml"):
        add(REPO / "disastertrace-starter" / name)
    for directory in (HERE, PLANNING):
        for p in directory.rglob("*"):
            if p.suffix in {".md", ".json", ".py", ".log", ".xml"}:
                add(p)
    for p in RUN.iterdir():
        if p.suffix in {".py", ".md", ".xml", ".log"}:
            add(p)
    for name in ("BASELINE.json", "REGRESSION_RESULT.json", "REGRESSION_RESULT_02.json",
                 "PREFLIGHT_AMENDMENT_02.json", "QUOTA_AMENDMENT_03.json", "PRESERVATION_01.json",
                 "ANALYSIS_PREFLIGHT.json", "ANNUAL_PREPARATION_CHECK.json",
                 "ADVANCE_RESULT.json", "ADVANCE_RESULT_02.json", "FINISH_INTERRUPTION_01.json"):
        add(RUN / name)
    for directory in ("before", "impact_01", "impact_02", "hydro_closure_01", "c2_design_01",
                      "real_pilot_01", "real_pilot_02", "profile_01"):
        for p in (RUN / directory).rglob("*"):
            if p.suffix in {".json", ".jsonl", ".py", ".md", ".log", ".txt"}:
                add(p)
    for directory in ("fullweek_01", "fullweek_02", "annual_catalog_01", "annual_native_sample_01"):
        folder = RUN / directory
        for p in (folder / "source").rglob("*.py"):
            add(p)
        for name in ("PLAN.json", "REGISTRATION.json", "DATA_CARD.json", "LOGICAL_SLICES.json", "SAMPLE_RESULT.json"):
            add(folder / name)
    return sorted(paths)


def report(data):
    annual = data["annual_catalog"]
    failed = len(annual["failed_region_months"])
    return f"""# v11 最新代码与实验进度

快照时间：{data['snapshot_at']}。**这是进行中快照，后台计算继续，本页不会自动更新。**
详细任务/作业身份见 [PROGRESS_SNAPSHOT.json](publication/v11_inprogress_20260915/PROGRESS_SNAPSHOT.json)。

## 已完成

| 工作 | 已有证据 |
|---|---|
| 当前回归 | 585 个 monitoring 测试与 165 个不同补充测试，共750个通过，零失败/跳过 |
| 代码修复 | 温度支持/数值边界、正式运行来源绑定、API最后本地发送门槛、common银行适配 |
| 历史影响扫描 | 252条特征回答、256条温度回答、256次温度输入检查及11644条温度政策记录无已知变化 |
| 真实五组预检 | 五组完成，360条方法记录通过正式重放与独立算术审计 |
| 评分性能 | 相同九方法日志19→9次重放，1256.0→554.6秒，评分文件哈希相同 |
| 年度月样例 | 2024年2月三地区18个目录/站报分片通过，枚举2470份原生TAF |
| C2登记 | 72个目标前缀、144个真实TAF E任务；72个覆盖任务全部为full |

性能数值来自同节点的单个profile案例，未控制文件缓存；不能承诺所有任务都快2.26倍。
本批没有新增被测LLM调用。开发中编写代码、阅读日志和分析结果会使用Codex，token用量未测量。

## 正在执行

完整季节周固定168个日会话条件、五组、840条轨迹、12096个机会，使用原有三地区九站、
四个季节周及1km/5km阈值。当前调度状态：`{data['fullweek_status']['state']}`。
CPU配额曾拒绝一个16核申请；第三片改为8核，第四片按配额释放接续。科学条件未改变。
最终全量审计和损失分层结果尚未纳入本次发布。

全年登记72个地区月、432个逻辑分片；当前 **{annual['completed_region_months']} 个地区月完成、
{failed} 个失败、{annual['pending_region_months']} 个尚无终态**。芝加哥2023年1月KORD曾出现429及重试超时，
原失败保留。目录完成不等于原文、任务连接或拟合完成。
三个闰月地区的2470份原生TAF下载和完整月构建仍属于独立进行中任务。

## 研究结论与未完成项

C1/C2/C3和16灾种总体方向保持。当前主要推进低能见度与温度；尚不能据此声称16灾种已完成。
v10已有的大模型负结果继续保留，本批没有证明新增模型收益。

C2目前证明真实任务能构建，但覆盖样本全部full，尚未证明难度、同状态分支效果或E→F收益。
后续按固定完整日历普查非平凡覆盖、版本、删失和缺报，同时保留普通样本。
需要记录字段→特征→概率→及时采用→F损失，不能把E归约更准直接解释为预测更好。

下一顺序：完整周强对照与分层报告 → 全年来源/角色剔除/强后端 → C2实际同状态分支 →
一次有限大模型选择器实验 → 固定方法后的未读历史确认。Bay确认集仍封闭。
更完整的成员lineage、部分DWD资格、全部prompt/数据卡绑定和当前源capsule迁移验证仍未完成。

## 复查入口

- [给ChatGPT Pro的复查说明](publication/v11_inprogress_20260915/REVIEW_FOR_CHATGPT_PRO_CN.md)
- [整体计划](plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md)
- [本批执行说明](plans/v11_execution_20260915_01/README_CN.md)
- [本次代码与材料ZIP](publication/v11_inprogress_20260915/DisasterTrace_v11_progress_and_code.zip)
- [导出范围](publication/v11_inprogress_20260915/README_CN.md)

ZIP是当前更新的阅读包，未包含所有原始数据、权重和运行中检查点，不是全部实验的完整复现包。
先前v10的有限CPU复算包及历史发布继续保留。
"""


def prepare(work):
    original = identity()
    baseline = read(RUN / "BASELINE.json")
    if (DEV_GIT / "HEAD").read_text().strip() != baseline["head"] or original["index_sha256"] != baseline["index_sha256"]:
        raise ValueError("Development identity changed")
    git = helpers.git_runner(work / "publication.git")
    if git("rev-parse", "FETCH_HEAD").decode().strip() != BASE:
        raise ValueError("Remote base differs from the prior publication")
    snapshot = work / "snapshot"
    snapshot.mkdir(exist_ok=False)
    data = progress()
    private = [helpers.KEY_FILE.read_bytes().strip()] if helpers.KEY_FILE.exists() else []
    entries, omitted = [], []

    def save(name, content):
        helpers.inspect_payload(name, content, private)
        path = snapshot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
        entries.append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})

    for path in selection():
        if path.stat().st_size >= 80 * 1024 * 1024:
            omitted.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size,
                            "sha256": digest(path), "reason": "large local artifact"})
            continue
        save(str(path.relative_to(REPO)), path.read_bytes())
    save("LATEST_PROGRESS_V11_CN.md", report(data).encode())
    banner = ("# Latest: v11 code and in-progress experiments\n\n"
        "Start with [the current Chinese progress report](LATEST_PROGRESS_V11_CN.md) and "
        "[ChatGPT Pro review instructions](publication/v11_inprogress_20260915/REVIEW_FOR_CHATGPT_PRO_CN.md). "
        "This is a timestamped snapshot: full-calendar execution and annual data acquisition continue. "
        "Earlier entries below describe historical releases.\n\n---\n\n")
    save("README.md", banner.encode() + git("show", BASE + ":README.md"))
    manifest_name = str(PUB / "EXPORT_MANIFEST.json")
    manifest = {"snapshot_at": data["snapshot_at"], "base_commit": BASE, "files": list(entries),
        "omitted_files": omitted, "omitted_categories": ["credentials", "model weights", "environments",
            "full annual raw captures", "running session journals and checkpoints", "unopened confirmation data"],
        "standalone_full_reproduction": False, "all_work_complete": False, "development_identity": original}
    save(manifest_name, (json.dumps(manifest, indent=2) + "\n").encode())
    archive_name = str(PUB / "DisasterTrace_v11_progress_and_code.zip")
    archive_path = snapshot / archive_name
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in entries:
            archive.write(snapshot / row["path"], row["path"])
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Review ZIP CRC failed")
        for row in entries:
            content = archive.read(row["path"])
            helpers.inspect_payload(row["path"], content, private)
            if hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise ValueError("Review ZIP member differs")
    if archive_path.stat().st_size >= 90 * 1024 * 1024:
        raise ValueError("Review archive too large for this publication")
    names = sorted([row["path"] for row in entries] + [archive_name])
    blobs = git("hash-object", "-w", "--no-filters", "--stdin-paths",
        data="".join(str(snapshot / name) + "\n" for name in names).encode()).decode().splitlines()
    tree = overlay_tree(git, names, blobs)
    if git("diff-tree", "--no-commit-id", "--name-only", "--diff-filter=D", "-r", BASE, tree):
        raise ValueError("Publication would remove remote history")
    commit = git("commit-tree", tree, "-p", BASE,
        data=b"Publish v11 code fixes, verified preflights and in-progress data status\n").decode().strip()
    if identity() != original:
        raise ValueError("Development identity changed during packaging")
    prepared = {"base": BASE, "commit": commit, "tree": tree, "branch": BRANCH,
        "snapshot": str(snapshot), "manifest": manifest_name, "archive": archive_name,
        "archive_bytes": archive_path.stat().st_size, "archive_sha256": digest(archive_path),
        "files": names, "blobs": blobs, "identity": original, "snapshot_at": data["snapshot_at"]}
    write(work / "PREPARED.json", prepared)
    print(json.dumps({k: v for k, v in prepared.items() if k not in {"files", "blobs"}}), flush=True)


def publish(work):
    prepared = read(work / "PREPARED.json")
    if identity() != prepared["identity"]:
        raise ValueError("Development identity changed before push")
    snapshot = Path(prepared["snapshot"])
    manifest = read(snapshot / prepared["manifest"])
    for row in manifest["files"]:
        if digest(snapshot / row["path"]) != row["sha256"]:
            raise ValueError("Snapshot member changed")
    if digest(snapshot / prepared["archive"]) != prepared["archive_sha256"]:
        raise ValueError("ZIP changed")
    git = helpers.git_runner(work / "publication.git")
    if git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().split()[0] != BASE:
        raise ValueError("Remote advanced; do not overwrite")
    write(work / "PUSH_INTENT.json", {"commit": prepared["commit"], "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    git("push", "origin", prepared["commit"] + ":refs/heads/" + BRANCH, timeout=1800)
    other = helpers.git_runner(work / "readback.git")
    other("init", "--bare", str(work / "readback.git"))
    other("remote", "add", "origin", REMOTE)
    other("config", "remote.origin.promisor", "true")
    other("config", "remote.origin.partialclonefilter", "blob:none")
    other("fetch", "--depth=1", "--filter=blob:none", "origin", "refs/heads/" + BRANCH)
    if other("rev-parse", "FETCH_HEAD").decode().strip() != prepared["commit"]:
        raise ValueError("Independent remote readback differs")
    tree = {}
    for row in other("ls-tree", "-r", "-z", prepared["commit"]).split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            tree[name.decode()] = meta.decode().split()
    for name, blob in zip(prepared["files"], prepared["blobs"], strict=True):
        if tree.get(name) != ["100644", "blob", blob]:
            raise ValueError("Remote tree member mismatch: " + name)
    readbacks = ["README.md", "LATEST_PROGRESS_V11_CN.md", str(PUB / "PROGRESS_SNAPSHOT.json"),
        prepared["manifest"], prepared["archive"],
        "disastertrace-starter/src/disastertrace/monitoring_v1/formal_session.py",
        "disastertrace-starter/src/disastertrace/monitoring_v1/temperature_contract.py"]
    for name in readbacks:
        content = other("show", prepared["commit"] + ":" + name)
        if hashlib.sha256(content).hexdigest() != digest(snapshot / name):
            raise ValueError("Remote file readback mismatch: " + name)
    if identity() != prepared["identity"]:
        raise ValueError("Development identity changed during push")
    result = {"passed": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commit": prepared["commit"], "branch": BRANCH, "base": BASE,
        "snapshot_at": prepared["snapshot_at"], "verified_tree_files": len(prepared["files"]),
        "independent_readback_files": readbacks, "archive_bytes": prepared["archive_bytes"],
        "archive_sha256": prepared["archive_sha256"], "development_identity_preserved": True,
        "force_push": False, "visibility_changed": False, "release_kind": "in_progress_snapshot",
        "url": "https://github.com/sisuolv/disastertrace-benchmark/tree/next-phase-v1"}
    write(work / "PUBLISHED.json", result)
    write(RUN / "GITHUB_UPLOAD.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "publish"))
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.action == "prepare" else publish)(args.work.absolute())
