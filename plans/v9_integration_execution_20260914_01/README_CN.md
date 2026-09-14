# v9 审查整合：当前阅读入口

本批已完成工程修复、28 条全日程序对照、Qwen3.8-27B 的 4 卡证据诊断，以及 H15/DWD 结果合同验证。它是开发阶段的可复查结果，不是 16 灾种全量 benchmark 的最终发布。

| 想了解什么 | 文件 |
| --- | --- |
| 这次做了什么、结果和限制 | [RUN_REPORT_CN.md](RUN_REPORT_CN.md) |
| 依据结果调整的下一步及整体路线 | [NEXT_PHASE_PLAN_CN.md](NEXT_PHASE_PLAN_CN.md) |
| 最初如何整合提供的审查包 | [OVERALL_AND_IMMEDIATE_PLAN_CN.md](OVERALL_AND_IMMEDIATE_PLAN_CN.md) |
| 机器可读的完成状态 | [EXECUTION_STATUS.json](EXECUTION_STATUS.json) |
| Qwen3.8 四种输入/回答条件的原始评分 | [RESULTS_CN.md](reports/qwen38_evidence_results_01/RESULTS_CN.md) |
| 程序对照完整分数、采用状态与资源 | [COPY_CONTROLS_SUMMARY.json](reports/COPY_CONTROLS_SUMMARY.json) |
| 模型输入、EOS、响应绑定和时间的复查 | [COMPLETED_CAPTURE_AUDIT.json](reports/COMPLETED_CAPTURE_AUDIT.json) |
| 真实结果合同资格 | [VALIDATION.json](reports/outcome_policy_01/VALIDATION.json) |
| 原始代码保全和旧轨迹影响范围 | [BASELINE_PRESERVATION.json](reports/BASELINE_PRESERVATION.json)、[HISTORICAL_TRACE_IMPACT.json](reports/HISTORICAL_TRACE_IMPACT.json) |
| 最终相关回归测试 | [full_04.xml](validation/full_04.xml)、[full_04.command.json](validation/full_04.command.json) |

Qwen3.8 正式 144 次、兼容性 4 次调用已全部完成。`pt-xn7x9vev` 已为 `SUCCEEDED`，四个 worker 退出码均为 0。正式调用来自 12 个原问题的 36 个证据视图，不能按 144 个独立天气过程统计。

原两小时窗口为 2026-09-14 04:33:23 至 06:33:23 UTC。GPU 最后一条回复在 05:41:43 UTC，程序轨迹和原始评分在 06:03:39 UTC 完成；独立 CPU 分析、最终回归和文档在窗口之后完成。所有一次性 launcher 已消费，不得直接重启。复核只需读取冻结数据/源码/捕获，不需要重新运行模型。

当前新增源代码位于 `../../disastertrace-starter/src/disastertrace/monitoring_v1/` 和 `monitoring_fixed_v1/`。实验实际使用的源码保存在各自 `source/`；它们与后续修复后的当前源码不是同一个快照。`BASELINE.json` 中的 0 次调用是开始时的状态，最终调用数以 `EXECUTION_STATUS.json` 和原始响应为准。

本批未打开 2025-02-17 至 23 日保留确认周。旧 v8 的 6,118 次调用与当前 148 次分别归档。本批交付在本地，尚未新建 GitHub 发布快照。
