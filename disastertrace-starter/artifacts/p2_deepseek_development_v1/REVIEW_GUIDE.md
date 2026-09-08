# 交给 ChatGPT Pro 的复核入口

请先读项目入口 `README_P2_DEEPSEEK_V1.md`、本目录的最终 `FINDINGS.md` 和 `NEXT_PHASE_PLAN.md`，再结合 `runtime/report/report.json`、自动错误清单与冻结源码检查。`diagnostic/` 内是程序预演，不能作为模型成绩。

建议复核以下问题：

1. **任务与主张是否一致。** 所有方法都看到累计公开证据；当前比较的是显式回答载体的附加效果。能否避免把结果解释成内部记忆机制、真实天气预报能力或应急行动最优性？
2. **失败是否完整计入。** 每方法固定 90 个检查点、282 个已知字段、78 个未知字段。格式失败、未发送和未知发送是否保留为不同类别？value 和 current-version grounding 是否分开？
3. **格式门槛是否提前固定且被遵守。** 每任务族 × 方法固定 30 个机会，schema 至少 29、length 最多 1，整轮审计完整。门槛失败后是否仍保留原成绩，后续改动是否形成新版本？
4. **Gold 与输入隔离是否可信。** 检查 frozen implementation 中的 compiler、public oracle、renderer、adapter、collector 和 audit；证据时间、实体/窗口作用域、合法 supersedes 链是否与文档一致？
5. **来源、版本与案例是否混淆。** 初值来自 NHC，后续记录是生成数据；Ida/Florence 为 primary，Dorian 为 secondary。不要把模板情形差异当作单纯来源差异，或把相关分支/检查点当独立事件。
6. **下一步改动是否有明确可测目标。** 可解析 JSON 缺少规定字段，是否首先需要共同输出结构约束？JSON 模式是否被错误视为严格 schema 保证？单臂复测是否被过度解释为因果实验？

关键机器文件：

- `execution/execution.json`：请求矩阵、参数、预算、执行身份、来源和环境。
- `launch_manifest.json`：启动前冻结文件清单和原生产 registry。
- `authorization.json`、`price_attestation.json`、`docs/acquisition.json`：实际范围和价格证据。
- `runtime/report/audit.json`：独立重建的请求、响应、载体、usage 与账目。
- `runtime/report/actual_trace.jsonl`：实际模型提交的答案和传递状态。
- `runtime/report/report.json` 与 `runtime/report/scores/`：固定分母的成绩、格式门槛和运行观察。
- `runtime/analysis/analysis.json`：自动字段/行动错误清单和描述性方法配对比较。
- `runtime/schema_inventory.json`：结构错误类型、缺失/额外根字段及 finish_reason。
- `validation/`：真实执行命令、exit code、日志和历史保护检查。

原始 HTTP 捕获在运行 journal 和 audit 中，使用有界字节记录与 base64 保存，可离线还原；请求凭据不会写入这些文件。无需运行模型 API 就能检查评分与错误清单。`runner.py launch` 已经使用，不能作为复核命令重新执行。

复核代码与研究设计不等于为每道题增加人工标签。本 benchmark 的计分仍由冻结的自动规则确定，复核意见不直接修改当前 Gold 或成绩。
