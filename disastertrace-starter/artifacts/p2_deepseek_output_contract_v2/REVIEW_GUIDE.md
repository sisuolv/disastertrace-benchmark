# 交给 ChatGPT Pro 的复查入口

请先读项目入口 `README_P2_DEEPSEEK_OUTPUT_CONTRACT_V2.md`、本目录的
`FINDINGS.md` 和 `NEXT_PHASE_PLAN.md`。结果文件须以本轮完成后的实际文件为准；
`diagnostic/` 是程序演练，不能作为 LLM 成绩。

本轮执行同一份 18 episode × 3 方法 × 5 checkpoint 的开发矩阵。
统一输出契约 v2 更明确地说明 state/action 结构及 record_id/ASSERT 引用方式。
任务证据、自动 Gold、严格解析器、评分规则、累计证据输入和载体策略保持不变。

建议重点复查这些问题：

1. **实验身份是否一致。** `execution/execution.json`、`launch_manifest.json`、
   实际授权、每次准备好的请求和最终 report 是否绑定同一 v2 版本和 system hash？
   旧版默认请求是否仍保留原字节？
2. **输入是否泄漏答案。** 模型只接收公开记录及声明的载体；Gold、未来证据、
   来源组、任务族和分支标签不应成为输入。标准答案来自事件结构，独立 oracle
   从公开文本重建，两个路径是否一致？
3. **格式筛选是否守住原门槛。** 九个 family × method 单元各 30 个机会，
   schema 至少 29、length 最多 1，并要求完整审计。错误项、未发送和未知发送
   是否全部保留？是否错误地把格式通过解释为所有能力通过？
4. **事实与引用是否分开。** 每方法固定 90 个 checkpoint、282 个已知字段、
   78 个未知字段。值正确但引用旧版本或错误行号，应与值错误分开报告。
   合法 JSON 也可能不满足严格结构；不得修补后覆盖原分数。
5. **历史比较是否过度归因。** 两轮采集时间不同、每个条件一次采样。
   实际载体也会随前轮回答变化。`historical_comparison.json` 是描述性对照，
   不能据此识别提示词改动的因果效应或宣称显著的方法优势。
6. **测量范围是否清楚。** 三方法都看到累计公开证据。本任务评估的是证据更新、
   保留、作用域及来源追踪；不直接测量内部记忆、天气预报精度或实际应急行动质量。
   初值源于 NHC，后续修订、实体和时间窗口是明确标识的受控生成数据。
7. **样本与后续设计是否合理。** Ida/Florence 使用 primary，Dorian 使用 secondary，
   来源与情形存在混淆。分支和 checkpoint 相互依赖；不能把 270 次调用当作
   270 个独立天气事件。第二模型、平衡设计和留出评测需要单独冻结。

主要文件对应关系：

| 文件 | 用途 |
| --- | --- |
| `authorization.json`、`authorization_context.json` | 本轮实际批准范围 |
| `docs/acquisition.json`、`price_attestation.json` | 新获取的官方价格和参数依据 |
| `execution/` | 数据、执行计划、冻结实现源码及原始未批准模板 |
| `runtime/report/audit.json` | 独立重建的请求、响应、载体及账目 |
| `runtime/report/actual_trace.jsonl` | 原样提交的答案和实际传递状态 |
| `runtime/report/report.json`、`runtime/report/scores/` | 完整分母评分、九单元筛选及资源消耗 |
| `runtime/analysis/analysis.json` | 自动字段/行动错误及方法配对描述 |
| `runtime/schema_inventory.json` | 格式错误、finish_reason 和原始结构 |
| `runtime/historical_comparison.json` | 分别验证两轮报告后的描述性比较 |
| `validation/` | 实际命令、退出码、测试日志及历史保护检查 |

原始 HTTP 捕获保存在运行 journal 和 audit 中，可由有界字节记录离线还原。
本轮凭据通过隐藏输入传入工作进程，没有写入运行文件。复查无需再次调用 API。
`runner.py launch` 已被使用，不能当作复现命令重新执行。

审计还绑定原始绝对运行/registry 路径和软件环境。压缩包可以在任意位置做静态
复查及文件哈希核验；若要重新执行严格审计，需要重建记录中的环境和原始路径。
不得通过编辑旧 claim 或 manifest 来绕过此约束。具体命令见 `REPRODUCE.md`。

代码和研究设计复查不等于为每道题增加人工标签。现有分数仍由冻结的自动规则
确定；复查意见应进入后续版本，不能直接改写本轮标准答案或模型成绩。
