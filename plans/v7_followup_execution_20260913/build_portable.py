"""Build a review subset with no model weights or generation entry point."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main(output):
    output.mkdir(exist_ok=False, parents=True)
    package = output / "source/disastertrace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        '"""Isolated offline replay package without optional app dependencies."""\n'
    )
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            ROOT / "disastertrace-starter/src/disastertrace" / module,
            package / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    for name in (
        "admission_02",
        "model_smoke_02",
        "support_01",
        "branch_01",
        "preparation_01",
        "scalar_admission_01",
    ):
        shutil.copytree(HERE / "reports" / name, output / "reports" / name)
    shutil.copytree(
        ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01/policy",
        output / "fixed_inputs",
    )
    for name in (
        "FINAL_REPORT_CN.md",
        "NEXT_EXECUTION_CN.md",
        "ARCHITECTURE_DECISION_CN.md",
        "MISSION_SPEC.json",
        "HEAD_CONTRACTS.json",
        "verify_portable.py",
    ):
        shutil.copyfile(HERE / name, output / name)
    (output / "README_CN.md").write_text(
        "# v7 第一批执行复查包\n\n"
        "运行 `python3 -B verify_portable.py` 可离线复放；需要 Python 3.10 及以上，仅使用标准库。\n\n"
        "本包包括当前源码、合法输入、评估侧结果、日志与报告；没有模型权重，不会发起模型调用。\n"
        "目录可整体移动。不要将评估侧结果或完整会话快照作为模型输入。\n\n"
        "完整原始 GPU token/请求/回答及 SHA 绑定留在执行目录 gpu/heads_smoke_01。\n"
        "本包用于重算封存与分数；原始 token 解码与 GPU 作业身份由主执行目录中的实测审计记录支持。\n"
    )
    files = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    (output / "MANIFEST.json").write_text(
        json.dumps(
            {"schema": "disastertrace.portable_followup.v1", "files": files}, indent=2
        )
        + "\n"
    )
    print(
        json.dumps(
            {"directory": str(output), "bound_files": len(files), "new_model_calls": 0}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
