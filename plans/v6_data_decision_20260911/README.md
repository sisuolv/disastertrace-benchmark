# DisasterTrace：整体灾种与数据方案

日期：2026-09-11。本目录回答整个 benchmark 的灾种范围、数据来源、处理规则及评测设计。

首读 [OVERALL_BENCHMARK_DATA_PLAN_CN.md](OVERALL_BENCHMARK_DATA_PLAN_CN.md)。方案包含 16 个灾种族，按证据理解、未来风险和准备决定组织任务，并区分观测、产品和报告标签的结果含义。

| 文件 | 用途 |
| --- | --- |
| [整体方案](OVERALL_BENCHMARK_DATA_PLAN_CN.md) | 灾种选型、整体数据处理、研究问题与完成交付物 |
| [逐灾种来源矩阵](HAZARD_SOURCE_MATRIX.md) | 16 类的主源、预报、已有 benchmark、处理与当前证据 |
| [矩阵 JSON](HAZARD_SOURCE_MATRIX.json) / [CSV](HAZARD_SOURCE_MATRIX.csv) | 可程序读取的来源角色、状态与灾种映射 |
| [处理合同](DATA_PROCESSING_CONTRACT.json) | 身份、时间、QC、目标、结果、切分及公开输入规则 |
| [数值子集选择](SOURCE_SELECTION.json) | 仅 NHC / 水文数值链的深入选型，整体范围以总方案为准 |
| [NHC 审计](nhc_audit_01/AUDIT.json) / [处理器](audit_nhc_data.py) | 继承原始资料重核、预报到事后分析的独立匹配 |
| [水文审计](hydro_audit_01/AUDIT.json) / [匹配表](hydro_audit_01/JOIN_TABLE.csv) / [处理器](audit_hydro_data.py) | 两站预报、观测与集合数组的实际配对 |
| [请求汇总](PROBE_SUMMARY.json) | 30 次有界请求的成功、空响应、错误、截断及哈希 |
| [校验报告](VERIFY_REPORT.json) | 本目录内容、链接、原始响应及既有输入保护的离线检查 |

已选定的总体路线不等于所有来源已正式准入。本次新增正式未来预警任务为 0，模型调用为 0；既有模型结果保持原范围。`private` 文件名表示数据角色，本目录尚不是实现了访问隔离的正式评测运行环境。

既有来源登记与论文代码审查分别见 [数据准入报告](../v6_0911_dataset_selection/DATA_READINESS_REVIEW_CN.md) 和 [研究审查](../v6_active_warning_review_20260911/RESEARCH_PLAN_CN.md)。
