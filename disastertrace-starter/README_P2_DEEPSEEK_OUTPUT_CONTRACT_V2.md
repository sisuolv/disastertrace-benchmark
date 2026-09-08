# P2 DeepSeek 输出契约 v2 开发筛选

当前阶段：**270/270 个真实响应已完成，独立审计与离线重建通过，九个格式单元全部通过。**
工作进程于 2026-09-07 16:11:26 UTC 写入完成记录，后续保全核验于 18:02:02 UTC 结束。
启动器及最终离线核验进程的退出码均为 0；工作进程自身记录 intended exit 0，
但其 OS 退出码没有被独立观察到。此次启动范围已经消耗。
实验范围是 18 个 development episode × 3 种方法 × 5 个 checkpoint，
共 54 条独立载体轨迹、一次重复；使用 `deepseek-v4-flash`、统一 v2 输出契约、
8192 输出上限、high reasoning 和 thinking enabled。独立 USD 3 为条件预算。

本轮用于测量共同格式说明能否达到预先固定的九单元门槛。每个任务族 × 方法
单元有 30 个机会，要求至少 29 个格式有效、最多一次 length，且全轮审计完整。
任何失败都保留在原分母中；原始响应由确定性规则评分，不需要逐题人工标注或 LLM judge。

实际授权、当前官方价格证据、冻结执行和专用启动器位于
`artifacts/p2_deepseek_output_contract_v2/`。此前的离线候选及旧模型响应保留不变。
启动前 13 项专用测试、静态检查以及完整 270 槽位离线演练均已通过。
三种方法在本轮全部正确，结果如下：

| 方法 | 格式有效 | 已知值及当前引用正确 | 未知状态正确 | checkpoint 全对 |
| --- | --- | --- | --- | --- |
| snapshot | 90/90 | 282/282 | 78/78 | 90/90 |
| structured_state | 90/90 | 282/282 | 78/78 | 90/90 |
| answer_history | 90/90 | 282/282 | 78/78 | 90/90 |

没有 length、空内容、格式、值或引用失败。使用 609,487 prompt tokens 和
283,699 completion tokens；费用估计 USD 0.267236704，保守结算 USD 0.64265696，
未结算/未知预留均为 0。这些是本轮记录中的估计与账目，不是供应商账单。

本轮另外通过 6 项历史对照测试。两轮报告分别用各自冻结源码重建，321 个指标
分母和 270 个 checkpoint 机会相同，3,116 个历史/源码文件未变化。首轮离线
收尾会话未完成文件保全结束记录，已在独立目录复核复用产物并补齐，过程保留。

详细入口：

- [主要发现](artifacts/p2_deepseek_output_contract_v2/FINDINGS.md)：成绩、历史对照、费用及限制。
- [完整结果表](artifacts/p2_deepseek_output_contract_v2/runtime/RESULT_TABLES.md)：按任务族、来源组和方法列分子/分母。
- [后续计划](artifacts/p2_deepseek_output_contract_v2/NEXT_PHASE_PLAN.md)：跨模型离线准备、平衡版本与区分度设计。
- [ChatGPT Pro 复查说明](artifacts/p2_deepseek_output_contract_v2/REVIEW_GUIDE.md)及[无 API 复现](artifacts/p2_deepseek_output_contract_v2/REPRODUCE.md)。
- [本地复查包](artifacts/p2_deepseek_output_contract_v2/p2_deepseek_output_contract_v2_review.tar.gz)及[包校验记录](artifacts/p2_deepseek_output_contract_v2/archive_verification.json)。

只读进度命令，在本项目目录执行：

```bash
.venv/bin/python artifacts/p2_deepseek_output_contract_v2/runner.py status
```

真实采集目录为 `work/p2-deepseek-output-contract-v2`。启动采用独立后台进程；
出现 runtime 目录或生产 claim 后不能再次启动。本轮进程已经完成独立审计、
报告及重建验证。查看结果和重新核验均不需要凭据或新模型调用。

当前 v2 与历史 v1 的比较仅用于开发诊断，两次采样时间不同，不能将差值全部
归因于提示变化。当前三方法全部满分，说明这个小矩阵不足以区分方法能力。
下一步优先准备第二模型接口及来源/情形平衡版本，另行冻结后再进行新的实测；
格式通过不表示已完成跨模型或留出集评测。
