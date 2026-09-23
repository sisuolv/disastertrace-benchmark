# 给 ChatGPT Pro 的 v18 代码审查 Prompt

请审查这个 DisasterTrace benchmark 的最新代码是否真正执行了原始计划，并判断计划目标完成到什么程度。

请同时阅读：

1. 原始计划：`disastertrace-starter/docs/plans/PLAN_V18_ORIGINAL_CN.md`
2. 代码：`disastertrace-starter/src/`、`disastertrace-starter/scripts/`、`disastertrace-starter/tests/`
3. v18 修复审查记录：`disastertrace-starter/review/v18_execution_20260923/`

如果你运行在原始工作区，也可以将上述两个副本分别与
`/mnt/afs/260010168/extreme_weather_benchmark/plan/plan_v18_0922/DisasterTrace_v17_Benchmark_Optimization_Recommendations_CN.md`
和 `/mnt/afs/260010168/extreme_weather_benchmark/plan/plan_v18_0922/v18_execution_20260922/`
交叉核对。

请按原计划的每个目标逐项建立“计划要求 → 实际实现 → 证据 → 缺口 → 结论”表格。重点检查：

- 真实天气证据、TAF 单位、时间可用性和 TEMPO/PROB 语义是否正确；
- complete-grid denominator、carry-forward、checkpoint 权重、缺失 Y bounds 和 target-level outcome 是否满足定义；
- Natural Track 的 action、clock、deadline、source identity 和 terminal 状态；
- API 请求模型、provider 返回模型、HTTP 状态、response schema 和 run identity 是否可审计；
- evidence stream 的 chronology、duplicate/revision/conflict 处理；
- 测试是否验证了真实行为，还是只验证了 fixture；
- 哪些结论是 empirical，哪些只有 synthetic 或 source-only 证据；
- 当前实现是否足以支持 forecast gain、calibration、ranking、live-agent 或 paper-ready claim。

请直接阅读代码和测试，不能只复述 README 或 status 文档。每个关键判断给出文件路径、行号和测试名称；发现问题时给出最小可复现反例、严重级别（P0/P1/P2）和具体修复建议。特别区分 Codex/平台生成代码所用模型与 benchmark runner 实际请求的 provider model。最后给出：

1. 当前计划完成率（按目标而不是按文件数量）；
2. 可以立即接受的部分；
3. 阻止真实实验或论文结论的部分；
4. 下一轮最小执行顺序。

审查完成后，请生成一个可下载的 `disastertrace_v18_followup_plan.zip`，供我交给 Codex 继续执行。zip 内至少包含：

- `FOLLOWUP_PLAN_CN.md`：按优先级和依赖关系排列的后续计划；
- `TASKS.json`：每个任务的 ID、目标、输入文件、预计改动文件、验证命令、完成标准、风险和是否需要真实 API；
- `EVIDENCE_MATRIX.csv`：计划要求、代码位置、证据、当前状态、缺口和结论；
- `CODEX_HANDOFF.md`：给 Codex 的执行顺序、禁止事项、需要保留的历史产物和最终交付物；
- `README.md`：说明如何解压、如何从第一个任务开始执行，以及 zip 生成时使用的审查日期和代码版本。

计划必须把“代码修复”“离线 synthetic 验证”“真实 provider run”“outcome 结算”“holdout 分析”和“论文结论”分成不同阶段，并为每个阶段写清楚前置条件。不要把 synthetic 结果写成 empirical 结果，不要建议重试已经关闭的 API run，不要读取 holdout 或保护窗口数据，也不要在任何文件中写入 API key。若 ChatGPT Pro 环境不能直接附加 zip，请输出完整的文件树和每个文件的内容，并给出一条可复制的本地打包命令。

不要修改仓库，不要调用真实 API，不要读取 holdout 或保护窗口数据。
