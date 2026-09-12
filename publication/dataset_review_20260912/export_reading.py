"""Create a small review export while preserving the existing remote documents."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PUBLICATION = HERE.relative_to(REPO)
SOURCE_ROOTS = [
    "plans/all_dataset_utilization_20260912",
    "plans/all_candidate_data_validation_20260912",
    "plans/advisor_review_20260912",
    "plans/task_chain_feasibility_20260912",
    str(PUBLICATION),
]
OMIT_DIRS = {
    "parser_libs",
    "extracted_inputs",
    "__pycache__",
    ".download_locks",
    ".ruff_cache",
}
ALLOWED = {".py", ".md", ".json", ".csv", ".yaml", ".yml", ".toml", ".sh", ".log"}
OMIT_NAMES = {
    "EXPORT_MANIFEST.json",
    "EXCLUDED_ASSETS.json",
    "PUBLISH_RESULT.json",
    "CHECKOUT_VERIFY.json",
}
INTRO = """## 最新：全部候选数据补缺与使用清单（2026-09-12）

当前 97 个来源/产品入口中，84 项有已解析样例、6 项可作事件目录，7 项仍有获取或授权缺口。
本轮实际补齐 TCIR、CAMELSH、CEMS、FloodNet、CrisisMMD、UrbanSARFloods、SenForFlood、GWIS、EFFIS。
完整 [数据报告](plans/all_dataset_utilization_20260912/README_CN.md)、[97 项清单](plans/all_dataset_utilization_20260912/usage_02/USAGE_REGISTRY_CN.md)
和 [16 灾种组合](plans/all_dataset_utilization_20260912/usage_02/HAZARD_CHAINS_CN.md) 已更新。

请将 [ChatGPT Pro 复查任务](publication/dataset_review_20260912/REVIEW_FOR_CHATGPT_PRO_CN.md)
或 [精选阅读 ZIP](publication/dataset_review_20260912/chatgpt_pro_dataset_review_20260912.zip) 交给审阅者。
93 次实际数据请求、约 975 MB 正文和 1,081 个文件的本机独立核验已有记录。
源码、回执和审计结果随仓库提供；新原始大数组与环境保留本地。
样本可读不代表 16 类预警链全部建成；本轮没有新模型调用，既有主动取证未显示收益的结果保留。

"""


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, check=True
    ).stdout


def screen(path, data):
    patterns = [
        rb"sk-[A-Za-z0-9_-]{25,}",
        rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
        rb"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
    ]
    if any(re.search(p, data) for p in patterns):
        raise ValueError("Potential credential in selected text: " + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", default="origin/next-phase-v1")
    args = parser.parse_args()
    base = git("rev-parse", args.base).decode().strip()
    args.output.mkdir(parents=True, exist_ok=False)
    selected, excluded = {}, []

    def write(relative, data):
        relative = str(relative)
        screen(relative, data)
        p = args.output / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        selected[relative] = {
            "path": relative,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    for name in SOURCE_ROOTS:
        for directory, dirs, files in os.walk(REPO / name):
            for d in dirs:
                if d in OMIT_DIRS:
                    excluded.append(
                        {
                            "path": str((Path(directory) / d).relative_to(REPO)),
                            "reason": "local_environment_or_large_extracted_inputs",
                            "directory": True,
                        }
                    )
            dirs[:] = sorted(d for d in dirs if d not in OMIT_DIRS)
            for name in sorted(files):
                p = Path(directory) / name
                rel = p.relative_to(REPO)
                if p.is_symlink():
                    raise ValueError("Unexpected symlink: " + str(rel))
                if (
                    name in OMIT_NAMES
                    or name == "chatgpt_pro_dataset_review_20260912.zip"
                ):
                    continue
                if p.suffix not in ALLOWED and name != ".gitignore":
                    excluded.append(
                        {
                            "path": str(rel),
                            "bytes": p.stat().st_size,
                            "reason": "raw_asset_or_nontext_dependency",
                        }
                    )
                    continue
                if p.stat().st_size > 8 * 1024**2:
                    raise ValueError("Unexpected large review file: " + str(rel))
                write(rel, p.read_bytes())
    for name in ["README.md", "LATEST_PROGRESS_20260912_CN.md"]:
        original = git("show", base + ":" + name).decode()
        title, _, rest = original.partition("\n")
        write(name, (title + "\n\n" + INTRO + rest.lstrip("\n")).encode())
    for name in ["IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md"]:
        rel = "disastertrace-starter/" + name
        remote = git("show", base + ":" + rel).decode()
        local = (REPO / rel).read_text()
        section = local[local.index("## ") :]
        section = section.split("\n## ", 1)[0].rstrip() + "\n\n"
        title, _, rest = remote.partition("\n")
        write(rel, (title + "\n\n" + section + rest.lstrip("\n")).encode())
    exclusion_report = {
        "reason": "Review-only export. Full scientific replay needs local raw files and dependencies.",
        "omitted": excluded,
    }
    write(
        PUBLICATION / "EXCLUDED_ASSETS.json",
        (json.dumps(exclusion_report, indent=2) + "\n").encode(),
    )
    manifest = {
        "base_commit": base,
        "files": sorted(selected.values(), key=lambda x: x["path"]),
        "file_count": len(selected),
        "bytes": sum(x["bytes"] for x in selected.values()),
        "scope": "Selected new code/reports; does not certify omitted raw arrays or complete scientific replay.",
    }
    path = args.output / PUBLICATION / "EXPORT_MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy2(path, HERE / path.name)
    shutil.copy2(
        args.output / PUBLICATION / "EXCLUDED_ASSETS.json",
        HERE / "EXCLUDED_ASSETS.json",
    )
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}))


if __name__ == "__main__":
    main()
