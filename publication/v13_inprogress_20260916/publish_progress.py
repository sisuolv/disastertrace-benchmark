"""Publish a bounded v13 snapshot without mutating active runs or Git index."""

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import time
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PUB = HERE.relative_to(REPO)
BASE = "1eba36dd272c72573d1309c78d45dbe97dd8af12"
BRANCH = "next-phase-v1"
spec = importlib.util.spec_from_file_location("v12_publisher", REPO / "publication/v12_execution_20260916/publish_execution.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
legacy.prior.BASE = BASE
legacy.OBJECTS = Path("/mnt/afs/260010168/extreme_weather_benchmark/publication/v12_execution_20260916_01/publication.git/objects")
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
        "release_kind": "in_progress_code_and_status_snapshot", "all_work_complete": False,
        "observation_is_cross_process_atomic": False,
        "A00_A06": load("A", "FINAL_RESULT.json"), "B00_C00_M00_status": load("B", "STATUS.json"),
        "copied_B00_case_receipts": {"count": len(b00), "passed": sum(read(p)["passed"] for p in b00)},
        "copied_C00_parent_receipts": {"count": len(c00), "passed": sum(read(p)["passed"] for p in c00)},
        "M00": {k: v for k, v in load("B", "M00/RESULT.json").items() if k != "results"},
        "B02_status": load("S", "STATUS.json"), "B02_regression": load("S", "regression/RESULT.json"),
        "M01_status": load("M", "STATUS.json"), "M01_job": load("M", "runtime/JOB.json"),
        "M01_submission_wait": load("M", "runtime/submission_wait/STATUS.json"),
        "M01_pre_handoff": load("M", "PRE_HANDOFF_CHECK.json"),
        "new_model_calls_caused_by_publication": 0, "new_weather_downloads": 0,
        "confirmation_opened": False, "full_scientific_reproduction_included": False,
        "codex_token_usage_for_publication": "not measured; ordinary scripts do not call Codex"}


def report(status):
    b = status["B00_C00_M00_status"]["B00"]
    c = status["copied_C00_parent_receipts"]
    s = status["B02_status"]
    m = status["M01_status"]["M01"]
    job = status["M01_job"]
    job_text = ("平台已接受作业 `" + job["job_id"] + "`") if job else "首次提交被 CPU 配额拒绝，自动脚本等待资源释放"
    return f"""# DisasterTrace v13：最新代码与执行进度

观察区间：{status['observation_started_at']} 至 {status['observation_finished_at']}。
**这是进行中快照，服务器后台任务继续；此 GitHub 页面不会自动更新。**

| 工作 | 本次实际观察 |
|---|---|
| A00-A06 核心修复 | 已完成；最终 880 个回归节点通过，历史原始回复和评分保留 |
| B00 同年度银行完整日历 | {b['verified_cases']}/168 个单元核验通过，失败 {b['failed_cases']}；轨迹终态文件 {b['terminal_arm_files']}/840，不等于全部已评分 |
| C00 同父状态 GET-v2 | 已导出 {c['count']}/12 个父案例完成回执，其中 {c['passed']} 个通过；全批尚待完整验收 |
| M00 真实接口小试 | 12/12 次合法且消费核验通过，28,880 provider tokens，零重试；不是 12 个完整模型天气日 |
| B02 强程序对照 | 新增 {s['B02_passed_method_days']}/72 个方法日通过；门槛打开状态为 {s['B02_gates_open']} |
| M01 完整模型对照 | {m['completed_days']}/12 天完成，HTTP 意图 {m['HTTP_intents']}/288；{job_text} |
| 新预测提前量 | 现有年度 bank 只获 1 小时目标支持，3/6 小时 C01 尚未运行 |

状态文件与逐案例回执可能相差一次观察周期，完整读数见
[PROGRESS_SNAPSHOT.json](publication/v13_inprogress_20260916/PROGRESS_SNAPSHOT.json)。

## 这一轮实际改变

- 查询选择器 v2 统一 prompt/schema/parser，只输出 query_order；执行器保留实际可执行前缀和尾部原因。
- API v2 将发送许可、持久捕获、独立发布核验和生产消费连通；未知远端执行不自动重发。
- GET-v2 区分新获取、缓存授权与 pending，保留旧 v1 的身份和结果。
- 新增真正轮转、公开风险/发布时间、固定哈希三个程序选择器，并补固定 coverage 的预算与共享 2×2。
- 当前合并回归为 912 个唯一节点，包含先前 880 个，不能相加。M01 执行器和资源调度另有 14+14 项离线检查通过。
- 已核验一个真实日的 72 次程序概率与实际证据消费；这证明重算一致，不证明取证或模型取得正收益。

## 正在回答的研究问题

同一专业资料流、预测器、日历、预算和评分分母下，查询选择能否改善未来站报风险？
M01 固定 12 个 metadata/hash 选定天气日、864 个机会和一个 DeepSeek-V4-Flash 路由，
最多 288 次请求。模型选择查询，概率由固定程序生成。负收益允许正常完成，
非法响应、网络失败、实际延迟与缺失结果保留。尚无本轮模型优于强程序的新结论。

整体仍保留 C1/C2/C3 与 16 灾种路线；当前深链集中于低能见度。
同目标多截止修订、PROCESS/TIMING、独立过程确认及其他灾种主动链仍有未完成项。
未读 Bay 确认周没有打开。已有 Git index stat-cache 字节差异继续如实记录，
不能将其与科学源文件的完整性检查混为一个结论。

## 阅读入口

- [复查任务](publication/v13_inprogress_20260916/REVIEW_FOR_CHATGPT_PRO_CN.md)
- [整体计划](plans/v13_planning_20260916_01/OVERALL_PLAN_CN.md)
- [工程完成及历史影响](plans/v13_execution_20260916_01/IMPACT_SUMMARY_CN.md)
- [当前真实实验](plans/v13_followup_20260916_01/README_CN.md)
- [强程序对照](plans/v13_strong_baselines_20260916_01/README_CN.md)
- [模型执行与门槛](plans/v13_selector_execution_20260916_01/README_CN.md)
- [代码与证据阅读 ZIP](publication/v13_inprogress_20260916/DisasterTrace_v13_progress_and_code.zip)
- [导出范围与复现边界](publication/v13_inprogress_20260916/README_CN.md)

历史文件中的停止/未启动措辞对应其原批次，后续授权与状态单独记录。
本次发布不触发新实验；GitHub 的历史内容保留，原始年度数据和完整 journal 留在服务器。
"""


def prepare(work):
    work.mkdir(exist_ok=False)
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
    save(str(PUB / "PROGRESS_SNAPSHOT.json"), (json.dumps(status, ensure_ascii=False, indent=2) + "\n").encode())
    save("LATEST_PROGRESS_V13_CN.md", report(status).encode())
    banner = ("# Latest: v13 code and in-progress experiments (2026-09-16)\n\n"
              "Start with [current progress](LATEST_PROGRESS_V13_CN.md), "
              "[review instructions](publication/v13_inprogress_20260916/REVIEW_FOR_CHATGPT_PRO_CN.md), "
              "or [the code and evidence ZIP](publication/v13_inprogress_20260916/DisasterTrace_v13_progress_and_code.zip). "
              "This is a timestamped snapshot; background experiments continue. "
              "Earlier entries below retain their historical scope.\n\n---\n\n")
    save("README.md", banner.encode() + git("show", BASE + ":README.md"))
    manifest_name = str(PUB / "EXPORT_MANIFEST.json")
    manifest = {"at": now(), "base_commit": BASE, "release_kind": status["release_kind"],
                "development_identity": identity, "files": list(exported),
                "full_experiment_reproduction_included": False, "github_CI_run_claim": False,
                "excluded": ["credentials", "raw annual source cache", "full journals/checkpoints/spools",
                             "model weights", "confirmation payloads", "unfinished per-case results"]}
    save(manifest_name, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    archive_name = str(PUB / "DisasterTrace_v13_progress_and_code.zip")
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
                 data=b"Publish v13 implementation, gated model evaluation and live progress snapshot\n").decode().strip()
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
                 "plans/v13_selector_execution_20260916_01/model_run.py", prepared["manifest"], prepared["archive"]]
    for name in readbacks:
        if hashlib.sha256(other("show", prepared["commit"] + ":" + name)).hexdigest() != digest(snapshot / name):
            raise ValueError("Remote readback bytes differ")
    if legacy.prior.identity() != prepared["identity"]:
        raise ValueError("Development identity changed during publication")
    result = {"passed": True, "at": now(), "commit": prepared["commit"], "base": BASE,
              "branch": BRANCH, "verified_tree_files": len(prepared["files"]), "readback_files": readbacks,
              "archive_bytes": prepared["archive_bytes"], "archive_sha256": prepared["archive_sha256"],
              "release_kind": "in_progress_code_and_status_snapshot", "force_push": False,
              "development_identity_preserved_since_prepare": True, "new_experiments_by_publication": 0,
              "offline_export_tests_passed": read(work / "EXPORT_VALIDATION.json")["offline_export_tests_passed"]}
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
