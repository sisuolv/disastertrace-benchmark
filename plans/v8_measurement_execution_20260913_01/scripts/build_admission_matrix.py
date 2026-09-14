"""Render existing source receipts and hazard contracts without upgrading admission."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]


def read(path):
    return json.loads(path.read_text())


def clean(value):
    return str(value).replace("|", "/").replace("\n", " ")


def main():
    registry_path = (
        REPO / "plans/user_authorized_sources_20260912/usage_01/USAGE_REGISTRY.json"
    )
    contract_path = (
        REPO / "plans/v7_0912_overall_research/OVERALL_HAZARD_CONTRACTS.json"
    )
    registry = read(registry_path)
    delta = read(HERE / "data_governance_01/CANDIDATE_SOURCE_DELTA.json")
    hazards = read(contract_path)["hazards"]
    assert (
        hashlib.sha256(registry_path.read_bytes()).hexdigest()
        == delta["prior_registry"]["sha256"]
    )
    sources = {r["source_id"]: r for r in registry["sources"]}
    assert len(sources) == delta["inherited_source_count"] == 97
    assert len(hazards) == 16
    states = {
        "decoded_sample": "已有特定样本解码",
        "catalog_records_only": "仅目录/元数据",
        "no_decoded_target_sample": "尚无目标样本解码",
        "authorization_pending": "历史记录仍待授权",
    }
    lines = [
        "# v8 数据源与任务准入对照",
        "",
        "本表依据已保存的原始验证回执和合同生成。它不发出新下载请求，也不把历史样本可读升级为全版本可下载或完整 benchmark 已完成。",
        "",
        "继承登记的 97 个产品/数据集项中，86 项有特定样本解码记录，7 项仅有目录/元数据，2 项尚无目标样本解码，2 项仍保留历史授权待办。镜像、产品别名、站点数和重复提前量不等于独立来源或天气过程。EUPP/DWD 点温度扩展单列，没有悄悄并入这 97 项。",
        "",
        "## 本轮新增的实际任务证据",
        "",
        "| 资料链 | 已实际完成 | 尚不能据此宣称 |",
        "| --- | --- | --- |",
        "| H15 TAF + METAR / IEM | 5 份自然日历、12,528 个 cutoff 机会；Bay 有 E/F 自动结算和模型开发评测；其余三区域完成原生获取解析 | 所有机会独立、所有低能见度都是浓雾、各地区都已有合格概率映射 |",
        "| H10/H11 EUPPBench + DWD Berus | 2017-2018 两年、51 成员、14,600 个正时效点温度机会，14,430 可结算，170 缺测保留；960 次标量回放 | 热浪、寒潮、霜冻损失或独立极端过程验证 |",
        "| H07 MRMS QPE Pass2 | 连续 12 小时网格解码；官方产品表证明 mm、1h 标称累计时长及 -1/-3 质量含义 | 累计区间端点和历史首发时间已证明，或匹配未来 F / 原生 MM 完成 |",
        "| H08 CNRFC / HEFS | 两个预报循环，43 个 QINE 列，697 个共同有效时刻，2,788 个版本 E 状态 | 43 列成员身份、调蓄关系、流量/水位/空间淹没等价已证明；完整共同 HEFS 的事实不能额外收费 |",
        "| AWC 当前来源采集 | 保存真实 HTTP 接收和原生 TAF/METAR 版本；具体完成范围见 shadow 独立报告 | 实时模型预测或未来结果结算已经完成 |",
        "",
        "模型批次完成状态及分数以 [执行报告](RUN_REPORT_CN.md) 和 [执行状态](EXECUTION_STATUS.json) 为准。本表的来源可用性与模型胜负是两件事。",
        "",
        "## 16 类灾害及其合同候选来源",
        "",
        "以下是来源角色规划，不是 16 条全部准入的声明。各灾种优先完成一个定义严格的子目标；河洪、山洪和内涝也必须分别验证。",
        "",
        "| ID / 灾害 | 主要预报来源 | 结果参考 | 目标定义 | 后续准入门槛 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for hazard in hazards:
        roles = hazard["source_ids"]
        names = lambda key, roles=roles: "; ".join(
            f"{sid}: {sources[sid]['name']}" for sid in roles.get(key, [])
        )
        lines.append(
            "| "
            + " | ".join(
                map(
                    clean,
                    (
                        hazard["id"] + " " + hazard["name_cn"],
                        names("professional_forecast"),
                        names("outcome_reference"),
                        hazard["target_contract"],
                        hazard["overall_plan"]["next_admission_gate_cn"],
                    ),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 97 项逐来源实际证据",
            "",
            "“样本检查”来自继承记录；“本轮补充”链接到新增结果。历史门槛仍保留原文供追溯，若本轮已有更细资格，以新增回执的具体字段为准。未填写新增回执的来源，本轮没有重新宣称其全部端点可用。",
            "",
            "| ID / 来源 | 已有获取级别 | 已实际检查的内容 | 本轮补充 | 继承的未完成门槛 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in delta["sources"]:
        source = sources[item["source_id"]]
        links = "; ".join(f"[{path}]({path})" for path in item["new_evidence"])
        lines.append(
            "| "
            + " | ".join(
                map(
                    clean,
                    (
                        source["source_id"] + " " + source["name"],
                        states[source["state"]],
                        source["current_summary_cn"],
                        links or "继承已有记录",
                        source["remaining_gates_cn"],
                    ),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 这些数据怎样支撑 novelty",
            "",
            "C1 需要同一个共同专业基线、合法资料菜单、共享预算和时间限制，比较补充取证的分配方式。仅下载更多数据或共享缓存不能单独证明 LLM 的贡献。",
            "",
            "C2 需要可计算的证据支持、原生缺测/删失/版本规则，以及同预算下单目标与联合可达性参照。评估器有隐藏标签不代表模型已读懂影像；事实充分不等于未来预测有收益。",
            "",
            "C3 需要上述机制在不同、独立的真实过程和资料类型中复现。当前数据基础足够继续开发，但样本下载清单不能替代同目标预报配对、独立过程实验和强对照。",
            "",
            "后续顺序见 [v8 后续计划](NEXT_PHASE_PLAN_CN.md)：先完成冻结的大模型自适应结算，再补 H15 独立过程与区域概率映射，以及第二灾种的原生物理时间合同。",
            "",
        ]
    )
    output = HERE / "DATA_ADMISSION_MATRIX_CN.md"
    with output.open("x") as handle:
        handle.write("\n".join(lines))
    print(
        json.dumps(
            {
                "path": str(output),
                "source_rows": len(sources),
                "hazard_rows": len(hazards),
                "new_downloads": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
