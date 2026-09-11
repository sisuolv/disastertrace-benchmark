"""Publish a bounded reading copy into a clean checkout of the remote branch."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
PUB = Path("publication/blueprint_review_20260911")
PLAN = Path("plans/v6_blueprint_sample_validation_20260911")
PARENT = "a08486dca0cb08c481a44ebaf6d289520857f4fd"


def bind(path, base):
    data = path.read_bytes()
    return {"path": str(path.relative_to(base)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    dest = args.destination.resolve()
    assert dest != SOURCE.resolve()
    env = {**os.environ, "SUDO_UID": "11329"}
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dest, env=env, text=True).strip() == PARENT
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=dest, env=env, text=True).strip()
    selected = []
    omitted = []
    folders = [PLAN, Path("plans/v6_data_decision_20260911"), Path("plans/v6_active_warning_review_20260911"), PUB]
    for folder in folders:
        for path in sorted((SOURCE / folder).rglob("*")):
            if not path.is_file() or {"parser_libs", "__pycache__"}.intersection(path.relative_to(SOURCE).parts):
                continue
            rel = path.relative_to(SOURCE)
            include = path.suffix in {".md", ".py", ".json", ".csv", ".log"} or path.name in {".gitignore", "GHCNH_DOCUMENTATION_TEXT.txt"}
            if include:
                out = dest / rel
                assert not out.exists(), str(rel)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, out)
                selected.append(rel)
            else:
                omitted.append({"path": str(rel), "bytes": path.stat().st_size, "reason": "raw_payload_image_or_nonreading_asset_retained_in_data_workspace"})
    bindings = json.loads((SOURCE / PLAN / "INPUT_BINDINGS.json").read_text())
    inputs = []
    for index, item in enumerate(bindings["inputs"][:2], 1):
        source = Path(item["path"])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item["sha256"]
        rel = PUB / "inputs" / f"overall_blueprint_{index:02}_CN.md"
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, out)
        selected.append(rel)
        inputs.append({"published_path": str(rel), "source_path": item["path"], "sha256": item["sha256"]})
    note = {
        "scope": "selected plans, code, request receipts and audits; no raw-array reconstruction",
        "raw_payloads_published": False, "inputs": inputs, "omitted_files": omitted,
        "source_data_workspace_verification": json.loads((SOURCE / PLAN / "VERIFY_REPORT.json").read_text()),
    }
    rel = PUB / "PUBLICATION_SCOPE.json"
    (dest / rel).write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n")
    selected.append(rel)
    block = """## 最新：16 类灾害整体方案与真实样例验证（2026-09-11）

请先读 [完善后的整体方案](plans/v6_blueprint_sample_validation_20260911/OVERALL_PLAN_REFINED_CN.md)、
[逐灾种数据合同](plans/v6_blueprint_sample_validation_20260911/HAZARD_SOURCE_MATRIX.md) 和
[逐来源样例清单](plans/v6_blueprint_sample_validation_20260911/SOURCE_SAMPLE_INVENTORY.md)。
本次整合两份整体蓝图，并实际执行 125 次有界请求；最终科学审计含 31 条科学内容解析
和 2 条渲染地图记录。97 项登记包含不同产品、继承和条件候选，不是独立数据集数量。
GHCNh、未来业务预报、冻雨/沙尘站报、雷达卫星及海岸/干旱产品均有实际样例证据；
权限、单位、时空支持、正例和配对缺口分别披露。新正式评测任务和模型调用为 0。

研究主线进一步确定为：在相同专业预报、资料预算和准备截止下，测量主动获取证据
对固定未来风险预测与决定的增量，并区分来源、表示、版本和状态造成的失效。
历史产品事实评测继续保留为 E 面板；F/D 的完整未来结果闭环仍待构建。

[本次发布与复查入口](publication/blueprint_review_20260911/README.md) 包含 ChatGPT Pro
复查问题、阅读 ZIP 和副本校验命令。原始数组和解析环境保留在数据工作区；GitHub
副本提供代码、方案、回执与审计记录，不能据此声称已独立重跑全部科学解码。

以下保留此前各阶段的进展与结果，历史“当前/最新”字样应按对应阶段理解。

"""
    for rel in [Path("README.md"), Path("LATEST_PROGRESS_20260911_CN.md")]:
        path = dest / rel
        old = path.read_text()
        first, rest = old.split("\n", 1)
        path.write_text(first + "\n\n" + block + rest.lstrip("\n"))
        selected.append(rel)
    # Keep every included file in the archive byte-identical to the reading copy.
    zip_rel = PUB / "disastertrace_blueprint_review.zip"
    with zipfile.ZipFile(dest / zip_rel, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel in sorted(selected):
            archive.write(dest / rel, str(rel))
        archive.writestr("READING_SCOPE.json", json.dumps({"raw_arrays_included": False, "source_parent_commit": PARENT, "files": [bind(dest / rel, dest) for rel in sorted(selected)]}, ensure_ascii=False, indent=2) + "\n")
    selected.append(zip_rel)
    manifest = {
        "schema": "disastertrace.blueprint_publication.v1", "parent_commit": PARENT,
        "target_repository": "sisuolv/disastertrace-benchmark", "target_branch": "next-phase-v1",
        "files": [bind(dest / rel, dest) for rel in sorted(selected)],
        "excluded_self_referential_files": [str(PUB / "PUBLICATION_FILES.json"), str(PUB / "PUBLICATION_VALIDATION.json")],
    }
    (dest / PUB / "PUBLICATION_FILES.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"selected_files": len(selected), "selected_bytes": sum(x["bytes"] for x in manifest["files"]), "zip_bytes": (dest / zip_rel).stat().st_size, "omitted_assets": len(omitted)}))


if __name__ == "__main__":
    main()
