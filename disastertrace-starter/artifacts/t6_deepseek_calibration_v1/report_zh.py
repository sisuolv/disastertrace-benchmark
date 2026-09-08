"""Render the completed T6 report in Chinese without sending model requests."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def ratio(metric):
    value = metric["value"]
    suffix = "NA" if value is None else f"{100 * value:.2f}%"
    return f"{metric['numerator']}/{metric['denominator']} ({suffix})"


def percentage(value):
    return "NA" if value is None else f"{100 * value:.2f}%"


def main():
    runtime = HERE / "runtime"
    completion = json.loads((runtime / "completion.json").read_text())
    result = json.loads((runtime / "report/report.json").read_text())
    if (
        completion["diagnostic"] is not False
        or result["mode"] != "urllib_http"
        or completion["audit"]["audit_id"] != result["audit_id"]
        or completion["report"]["attempted"] != result["attempted"]
        or completion["report"]["complete"] != result["complete"]
    ):
        raise ValueError("matching final live audit/report required")
    destination = runtime / "REPORT_ZH.md"
    if destination.exists():
        raise ValueError("Chinese report already exists; preserve the original")
    counts = {row["cell_id"]: row for row in result["cell_counts"]}
    cap = result["selected_output_tokens"]
    conclusion = (
        f"共同输出上限选择为 **{cap} tokens**。这是本轮开发筛选结果，供 P2 设置起点使用。"
        if result["live_recommendation"]
        else "本轮结论为 **no_selection**，尚不能根据既定门槛选择共同输出上限。"
    )
    text = [
        "# T6：DeepSeek 输出说明与 token 上限校准结果",
        "",
        conclusion,
        "",
        f"完成时间（UTC）：{completion['ended_at']}。本轮计划 270 个响应机会，"
        f"发送意图 {result['attempted']} 次，收到完整 HTTP 200 响应 {result['received']} 个，"
        f"未发送 {result['unsubmitted']} 个。矩阵完整：{result['complete']}；"
        f"停止原因：{result['stop_reason'] or '无'}。发送意图数是审计到的尝试数，"
        "不能独立证明每次都被服务端处理或收费。",
        "",
        "## 条件和方法结果",
        "",
        "| 条件 / 方法 | 收到 / 30 | Schema 成功 / 30 | Length | "
        "已知字段值正确 | 已知字段及来源正确 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, cell in result["cells"].items():
        count, metrics = counts[name], cell["metrics"]
        text.append(
            f"| {name} | {count['received']} | {count['schema_valid']} | "
            f"{count['length_failures']} | {ratio(metrics['known_value_accuracy'])} | "
            f"{ratio(metrics['known_grounded_accuracy'])} |"
        )
    text += [
        "",
        "每个条件/方法使用同样的 30 个检查点。失败和未发送机会保留在计划分母中；"
        "length、empty 和 schema failure 可重叠，不能相加为独立失败总数。"
        "共同 cap 要求完整矩阵通过审计，且该 explicit 档下每方法 schema ≥29/30、length ≤1/30。",
        "",
        "## 按风暴报告",
        "",
        "| 条件 / 方法 | 风暴组 | Schema | 已知字段及来源正确 | 必要更新成功 | 未变字段保留 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for name, cell in result["cells"].items():
        for event in cell["per_event"]:
            metrics = event["metrics"]
            text.append(
                f"| {name} | {event['group_id']} | {ratio(metrics['schema_success'])} | "
                f"{ratio(metrics['known_grounded_accuracy'])} | "
                f"{ratio(metrics['gold_transition_success'])} | "
                f"{ratio(metrics['gold_preservation_grounded'])} |"
            )
    text += [
        "",
        "| 条件 / 方法 | 等权风暴平均：已知字段及来源正确 | 有定义风暴数 |",
        "| --- | ---: | ---: |",
    ]
    for name, cell in result["cells"].items():
        macro = cell["event_macro"]["known_grounded_accuracy"]
        text.append(
            f"| {name} | {percentage(macro['value'])} | "
            f"{macro['n_events_defined']}/{macro['n_events_total']} |"
        )
    text += [
        "",
        "## 预定条件对比",
        "",
        "下表为每个风暴内配对的差值，单位为百分点。对比包括输出说明/上限改变后，"
        "前序回答及后续载体随之改变的影响；它不单独识别模型内部记忆或纯单轮格式效应。",
        "",
        "| 后条件 − 前条件 | 方法 | 风暴 | Schema 差值 | 已知字段及来源正确差值 |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for comparison in result["arm_comparisons"]:
        for event in comparison["per_event"]:
            delta = event["after_minus_before"]
            changes = [
                "NA" if delta[key] is None else f"{100 * delta[key]:+.2f}"
                for key in ("schema_success", "known_grounded_accuracy")
            ]
            text.append(
                f"| {comparison['later_arm']} − {comparison['earlier_arm']} | "
                f"{comparison['method']} | {event['group_id']} | {changes[0]} | {changes[1]} |"
            )
    operations = result["operations"]
    cost, usage, latency = (
        operations[name] for name in ("cost_estimate", "usage", "latency_seconds")
    )
    text += [
        "",
        "## Usage、时延与费用",
        "",
        f"可核验 usage 响应数：{usage['verified_responses']}。"
        f"输入 tokens：{usage['prompt_tokens']}；"
        f"输出 tokens：{usage['completion_tokens']}；合计：{usage['total_tokens']}。"
        "推理 tokens 已包含在输出统计中，不重复收费计算。",
        "",
        f"峰值/缓存未命中的保守结算账：USD {operations['settled_conservative_usd']}。"
        f"未结算预留：USD {operations['unsettled_reservation_usd']}，"
        f"其中明确未知预留：USD {operations['unknown_reservation_usd']}。",
        "",
        f"在缓存计数和本地 UTC 价格窗口可核验的 {cost['covered_attempts']} 个尝试上，"
        f"保存价格下的费用估计小计为 USD {cost['subtotal_usd']}。"
        f"覆盖全部尝试：{cost['all_attempts_covered']}。这些是条件估计，"
        "不是账户扣款或账单；跨价格时段或缺少缓存计数的请求不强行估算。",
        "",
        f"网络时延统计（秒，{latency['count']} 个捕获）：平均 {latency['mean']}，"
        f"中位数 {latency['median']}，最近秩 P95 {latency['p95_nearest_rank']}，"
        f"最大值 {latency['max']}。网络时延不包含磁盘持久化时间。",
        "",
        "## 解释边界与后续工作",
        "",
        "本轮只有一个模型、三个开发风暴和一次重复；字段、分支和检查点不构成新增独立风暴。"
        "历史 P1 不替代本轮新鲜 legacy 对照；其原 attempt 79 未知收费仍单独保留。"
        "模型服务别名及文档版本标识不保证权重长期不变。",
        "",
        "下一阶段使用 P2 的部分更新、同窗口纠正和支持恢复任务。P2 的真实采集/来源审计"
        "仍须接入，并冻结独立的模型范围及预算。NHC 的共同 cap 不自动证明 P2 或第二模型"
        "具有相同格式可靠性；七个留出风暴尚未进入本次推理。",
        "",
        "原始数据和机器可读结果见 `report/report.json`、逐条件/方法的 actual_views、"
        "scoring_projection、V1/V2 分数，以及 `completion.json` 的独立审计摘要。",
        "",
        f"执行身份：`{result['execution_id']}`。审计身份：`{result['audit_id']}`。",
        "",
    ]
    destination.write_text("\n".join(text), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
