"""Build a bounded V7 code/document export without changing Git state."""

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PUBLICATION = HERE.relative_to(REPO)
PLAN = Path("plans/v7_0912_overall_research")
SOURCE_ROOTS = (
    Path("plans/user_authorized_sources_20260912"),
    Path("plans/v7_0912_monitoring_optimization"),
    PLAN,
    PUBLICATION,
)
OMIT_DIRS = {
    "parser_libs", "extracted", "extracted_inputs", "__pycache__",
    ".pytest_cache", ".ruff_cache", "raw", "native", ".download_locks",
}
ALLOWED = {".py", ".md", ".json", ".csv", ".yaml", ".yml", ".toml", ".sh", ".txt"}
OMIT_NAMES = {"EXPORT_MANIFEST.json", "EXCLUDED_ASSETS.json", "PUBLISH_RESULT.json"}
ZIP_NAME = "chatgpt_pro_v7_overall_review_20260912.zip"
INTRO = """## 最新：v7 整体研究方案与数据验证（2026-09-12）

请先阅读 [v7 整体研究主计划](plans/v7_0912_overall_research/OVERALL_PLAN_CN.md)、
[16 类灾害数据合同](plans/v7_0912_overall_research/HAZARD_DATA_PLAN_CN.md) 和
[近邻工作与 novelty 对照](plans/v7_0912_overall_research/RELATED_WORK_MATRIX_CN.md)。
整体路线包含 10 组实验、8 个阶段；既有下一步计划作为实施附录保留。

最新 97 个来源/产品条目中 86 有解析内容、7 为目录、2 待授权、2 缺原生目标内容。
本轮加入 [EM-DAT/CMA/xBD 的实际审计与代码](plans/user_authorized_sources_20260912/README_CN.md)。
下载可读不等于任务准入；CMA 字段语义与 xBD 配准仍有门槛。
新的 monitoring_v1 尚未实现，本次没有新增模型或 GPU 评测，也未证明主动取证正收益。

用于进一步复查的 [ChatGPT Pro 任务书](publication/v7_overall_review_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md)
与 [阅读附件](publication/v7_overall_review_20260912/chatgpt_pro_v7_overall_review_20260912.zip)
一并提供。原始大数据、模型权重及环境保留本地。

以下为既有阶段记录，其数字按对应版本解释。

"""


def screen(path, data):
    patterns = (
        rb"sk-[A-Za-z0-9_-]{25,}",
        rb"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
        rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
        rb"[?&](?:Signature|Key-Pair-Id)=",
        rb"(?im)^\s*[\"']?(?:key|api_key|access_token)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{25,}",
    )
    if any(re.search(pattern, data) for pattern in patterns):
        raise ValueError("Potential sensitive value in selected file: " + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    selected, omitted = {}, []

    def write(relative, data):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe export path")
        if len(data) > 8 * 1024**2:
            raise ValueError("Unexpected large reading file: " + str(relative))
        screen(relative, data)
        if relative.suffix == ".py":
            ast.parse(data.decode(), filename=str(relative))
        output = args.output / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        selected[str(relative)] = {
            "path": str(relative), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def add(relative):
        source = REPO / relative
        if source.is_symlink():
            raise ValueError("Symlink outside export scope")
        write(relative, source.read_bytes())

    for prefix in SOURCE_ROOTS:
        for folder, dirs, names in os.walk(REPO / prefix):
            dirs[:] = sorted(d for d in dirs if d not in OMIT_DIRS)
            for name in sorted(names):
                source = Path(folder) / name
                relative = source.relative_to(REPO)
                if name in OMIT_NAMES or name == ZIP_NAME:
                    continue
                public_reference = relative.is_relative_to(PLAN / "literature")
                if source.suffix not in ALLOWED and not (
                    public_reference and name == "response.body"
                ):
                    omitted.append({"path": str(relative), "reason": "raw_or_binary_asset"})
                    continue
                add(relative)

    bindings = json.loads((REPO / PLAN / "INPUT_BINDINGS.json").read_text())
    for binding in bindings["repo_relative_bindings"]:
        relative = binding["path"]
        add(relative)
        if selected[relative]["sha256"] != binding["sha256"]:
            raise ValueError("Bound input changed: " + relative)

    with tempfile.TemporaryDirectory(prefix="disastertrace-export-git-") as temporary:
        config = Path(temporary) / "gitconfig"
        config.write_text("[safe]\n\tdirectory = " + str(REPO) + "\n")
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config))

        def git(*arguments):
            return subprocess.run(
                ["git", *arguments], cwd=REPO, env=env,
                capture_output=True, check=True,
            ).stdout

        base = git("rev-parse", args.base).decode().strip()
        for name in ("README.md", "LATEST_PROGRESS_20260912_CN.md"):
            original = git("show", base + ":" + name).decode()
            title, _, body = original.partition("\n")
            write(name, (title + "\n\n" + INTRO + body.lstrip("\n")).encode())

    exclusions = {
        "scope": "Code, planning documents and audit/reference evidence; not full scientific replay",
        "omitted_directory_names": sorted(OMIT_DIRS),
        "omitted_assets": omitted,
        "also_not_selected": [
            "credential files", "model weights and environments",
            "EM-DAT workbook and CMA source archive", "large xBD/raw scientific arrays",
            "running hydro worker's evolving captures", "unrelated local staged changes",
        ],
    }
    write(PUBLICATION / "EXCLUDED_ASSETS.json", (json.dumps(exclusions, indent=2) + "\n").encode())
    manifest = {
        "schema": "disastertrace.v7.publication_manifest.v1",
        "base_commit": base, "files": sorted(selected.values(), key=lambda row: row["path"]),
        "file_count": len(selected), "bytes": sum(row["bytes"] for row in selected.values()),
        "scope": exclusions["scope"],
        "local_head_and_index_not_changed_by_export": True,
    }
    manifest_relative = PUBLICATION / "EXPORT_MANIFEST.json"
    manifest_data = (json.dumps(manifest, indent=2) + "\n").encode()
    (args.output / manifest_relative).write_bytes(manifest_data)

    archive_path = args.output / PUBLICATION / ZIP_NAME
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(selected):
            archive.write(args.output / relative, relative)
        archive.writestr(str(manifest_relative), manifest_data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Reading archive CRC failure")
        for relative, record in selected.items():
            if hashlib.sha256(archive.read(relative)).hexdigest() != record["sha256"]:
                raise ValueError("Archive hash mismatch: " + relative)
    print(json.dumps({
        "base": base, "files": len(selected), "bytes": manifest["bytes"],
        "zip_bytes": archive_path.stat().st_size, "zip_crc_and_hashes_passed": True,
        "potential_sensitive_patterns_found": 0,
    }))


if __name__ == "__main__":
    main()
