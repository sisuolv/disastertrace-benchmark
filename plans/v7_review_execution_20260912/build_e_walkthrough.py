"""Render declared illustrative E errors directly from frozen public products."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main():
    cases_path = BASE / "e_diagnostic_analysis_01/CASES.json"
    inputs_path = BASE / "gpu_e_diagnostic_01/environment.json"
    cases = json.loads(cases_path.read_text())
    inputs = {c["case_id"]: c for c in json.loads(inputs_path.read_text())["cases"]}
    selected = [
        next(c for c in cases if c["expected_e"] == "supported" and c["predictions"]["qwen3_8b"]["E_only"] != "supported"),
        next(c for c in cases if c["expected_e"] == "undetermined" and all(v["E_fact_table"] != "undetermined" for v in c["predictions"].values())),
        next(c for c in cases if c["expected_e"] == "refuted" and c["predictions"]["qwen3_8b"]["joint_F_E"] != "refuted"),
    ]
    lines = ["# 用三个真实案例解释 C2 测量什么", "",
             "这些例子按预先声明的错误类型取排序后的第一例，用于说明合同，不代表错误率或总体样本。",
             "全部统计仍以 96 案例报告及完整 F 日历为准。下列结论来自公开产品和固定逻辑，不使用人工标签或 LLM 评委。", "",
             "E 命题是：登记的两个邻站报告槽位中，是否至少有一个报告的能见度严格低于 1000m。",
             "任一合法已读槽位确定低于阈值即可 supported；所有登记槽位均合法已读且不低于阈值才 refuted；否则 undetermined。", ""]
    for number, record in enumerate(selected, 1):
        data = inputs[record["case_id"]]
        public = data["requests"]["E_only"]
        lines += [f"## 例 {number}：{record['expected_e']}", "", f"案例 ID：`{record['case_id']}`。", "",
                  "登记槽位：" + "；".join("`" + q + "`" for q in public["registered_query_ids"]) + "。", "",
                  "| 已读来源 | 原生能见度支持区间（米） | 原始报告 |", "| --- | --- | --- |"]
        for asset in public["read_evidence"]:
            product = asset["content"]
            for report in product["reports"]:
                interval = report.get("visibility")
                if interval is None:
                    value = "missing"
                else:
                    value = ("[" if interval["lower_closed"] else "(") + str(interval["lower"]) + ", " + str(interval["upper"]) + ("]" if interval["upper_closed"] else ")")
                lines.append(f"| {product['query_id']} | {value} | `{report['raw']}` |")
        lines += ["", "未读槽位：" + ("；".join(public["unread_queries"]) or "无") + "。", "",
                  "| 模型 | 联合 F/E | E-only | E 加规则例子 | E 事实表 |", "| --- | --- | --- | --- | --- |"]
        for model, predictions in record["predictions"].items():
            lines.append(f"| {model} | " + " | ".join(str(predictions[k]) for k in ("joint_F_E", "E_only", "E_examples", "E_fact_table")) + " |")
        lines += ["", {"supported": "合法已读报告中已有一个上界严格低于 1000m 的区间，因此存在命题确定成立；另一个邻站能见度高不改变这个结论。",
                        "undetermined": "当前没有已读报告确定低于阈值，并且仍有未读登记槽位。不能由已读槽位的高能见度推导所有登记槽位均无低能见度。",
                        "refuted": "两个登记槽位都已取得合法报告，并且可见支持均不低于阈值，因此当前存在命题被反驳。"}[record["expected_e"]], ""]
        target = data["requests"]["joint_F_E"]["target"]
        lines += [f"同链 F 仍是 `{target['target_id']}` 的未来报告。当前邻站事实的 supported/refuted 不是该未来目标的确定结果，不能据此自动把 F 概率设为 1/0。", ""]
    lines += ["## 怎样解释这些错误", "",
              "这些输出能定位模型回答与合法可见支持之间的不一致，但不能单凭输出断定模型内部究竟混淆了单位、存在量词、槽位、来源还是提示字段。",
              "事实表由同一已读产品确定性转换而来，属于公开标明的辅助条件；没有把隐藏未来结果交给模型。它不是原生图像得到的精确物理真值。",
              "顺序复核保留这些消息，改变条件/案例执行排列；结果以新批次实测为准，不修改本轮原始回答。", ""]
    (BASE / "E_CASE_WALKTHROUGH_CN.md").write_text("\n".join(lines))
    (BASE / "E_CASE_WALKTHROUGH_BINDINGS.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "illustrative_selection": "First stable case for three explicitly selected error categories; not prevalence estimation",
        "case_ids": [c["case_id"] for c in selected],
        "source_sha256": {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (cases_path, inputs_path)},
        "new_model_calls": 0,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
