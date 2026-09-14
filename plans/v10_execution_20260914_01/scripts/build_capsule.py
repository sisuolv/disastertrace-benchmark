"""Build a small complete replay subset, preserving the original artifact bytes."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    old = root / "plans/v9_followup_execution_20260914_01"
    origins = {}

    def copy(src, rel):
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        origins[rel] = str(src)

    f_units = []
    for source, case_name, model in [
        ("api_pilot_01", "new_york__2025-01-06__5000", "deepseek-flash"),
        ("api_rare_pilot_01", "denver__2025-01-09__1000", "deepseek-v4-pro"),
    ]:
        case = old / source / case_name
        prefix = "F/" + case_name
        arms = ["follow", model + "__batch_predictor"]
        for name in ("DATA.json", "BANK.json", "OUTCOMES.json", "COMPARISON.json"):
            copy(case / name, prefix + "/" + name)
        for arm in arms:
            for name in (
                "REPORT.json",
                "SCORES.json",
                "admission.jsonl",
                "COMPLETE.json",
            ):
                copy(case / arm / name, prefix + "/" + arm + "/" + name)
            for p in (case / arm / "captures").rglob("*"):
                if p.is_file():
                    copy(
                        p,
                        prefix
                        + "/"
                        + arm
                        + "/captures/"
                        + str(p.relative_to(case / arm / "captures")),
                    )
        f_units.append(
            {
                "path": prefix,
                "arms": arms,
                "scope": "ordinary development"
                if source == "api_pilot_01"
                else "known-outcome Denver diagnostic",
            }
        )
    temp = old / "temperature_fullcalendar_01/2017-01"
    temp_arms = [
        "copy_current__base_bound_override",
        "copy_current__persistent_override",
    ]
    for name in ("POLICY.json", "OUTCOMES.json", "SCORES.json"):
        copy(temp / name, "temperature/" + name)
    for arm in temp_arms:
        for name in (
            "admission.jsonl",
            "SNAPSHOTS.json",
            "COMPLETE.json",
            "DECISIONS.json",
        ):
            copy(temp / arm / name, "temperature/" + arm + "/" + name)
    e = old / "api_evidence_02"
    plan, refs = (
        json.loads((e / n).read_text())
        for n in ("PLAN.json", "evaluator/REFERENCES.json")
    )
    selected = None
    for task in sorted(plan["tasks"], key=lambda t: t["call_id"]):
        if task["reasoning"] != "slotwise":
            continue
        score = json.loads(
            (
                e / "captures/deepseek-v4-pro" / (task["call_id"] + ".score.json")
            ).read_text()
        )
        answer = score.get("answer", {})
        if (
            answer.get("slots") == refs[task["call_id"]]["slots"]
            and answer.get("fact_truth") != refs[task["call_id"]]["fact_truth"]
        ):
            selected = task["opportunity_id"]
            break
    if selected is None:
        raise ValueError("Expected original E02 aggregation counterexample absent")
    tasks = [t for t in plan["tasks"] if t["opportunity_id"] == selected]
    for task in tasks:
        cid = task["call_id"]
        copy(e / "policy" / (cid + ".json"), "E02/policy/" + cid + ".json")
        for model in plan["models"]:
            for name in (
                "REQUEST.json",
                "RESPONSE.body",
                "RESPONSE.json",
                "WIRE_RECEIPT.json",
            ):
                copy(
                    e / "captures" / model / cid / name,
                    "E02/captures/" + model + "/" + cid + "/" + name,
                )
            copy(
                e / "captures" / model / (cid + ".score.json"),
                "E02/captures/" + model + "/" + cid + "/ORIGINAL_SCORE.json",
            )
    (out / "E02/UNIT.json").write_text(
        json.dumps(
            {
                "tasks": tasks,
                "models": plan["models"],
                "selection": "hash-first original Pro correct-slots/wrong-aggregate example; illustrative, not a performance sample",
            },
            indent=2,
        )
        + "\n"
    )
    copy(old / "scripts/evidence_diagnostic.py", "helpers/evidence_diagnostic.py")
    package = root / "disastertrace-starter/src/disastertrace"
    for module in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        for p in (package / module).rglob("*.py"):
            copy(p, "source/disastertrace/" + str(p.relative_to(package)))
    (out / "source/disastertrace/__init__.py").write_text(
        '"""Portable frozen compatible replay source."""\n'
    )
    copy(Path(__file__).parent / "verify_capsule.py", "verify.py")
    (out / "UNITS.json").write_text(
        json.dumps({"F_units": f_units, "temperature": {"arms": temp_arms}}, indent=2)
        + "\n"
    )
    (out / "README_CN.md").write_text(
        "# DisasterTrace v10 小型完整重建包\n\n"
        "本包按预先指定的普通 F／Denver 诊断／2017-01 温度和一个 E02 错误实例抽取。"
        "它是完整日志重放子集，不代表所有实验、独立天气过程或新模型调用。\n\n"
        "运行：`python verify.py --capsule . --result /tmp/disastertrace-capsule-result.json`。"
        "只需 Python 3.10+；不需要 API、GPU、模型权重或原始仓库。"
        "验证器阻止网络以及对原工作区的额外读取，核对字节清单、完整事件日志、原计分、"
        "独立 Brier 算术、原模型响应及两个 E 归约器。\n\n"
        "数据来自 NOAA/NWS 经 Iowa Environmental Mesonet 归档的原生 TAF/METAR，"
        "以及先前已解析的 EUPPBench 集合预报和 DWD 站点日产品。"
        "保留原结果来源与完整原始文件哈希；归档情景延迟不代表已证明的历史首次公开时间。"
        "E02 示例按错误选取，仅解释程序汇总，不用于估计总体收益。"
        "温度为完整一个月的两条 COPY 程序轨，尚非温度 LLM 或补证 C1 结果。\n\n"
        "原始路径仅作为来源标识保留于 MANIFEST.json，不应在重建时访问。"
        "上游资料的使用条款继续适用；本包供项目私有研究复核。\n",
        encoding="utf-8",
    )
    manifest = {
        str(p.relative_to(out)): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
            "original": origins.get(str(p.relative_to(out))),
        }
        for p in out.rglob("*")
        if p.is_file()
    }
    (out / "MANIFEST.json").write_text(
        json.dumps(
            {"schema": "disastertrace.portable_replay_subset.v1", "files": manifest},
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "files": len(manifest),
                "bytes": sum(r["bytes"] for r in manifest.values()),
                "E_answers": len(tasks) * len(plan["models"]),
            }
        )
    )


if __name__ == "__main__":
    main()
