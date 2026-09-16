# v12 实际执行入口

用户已授权本轮从 2026-09-15 15:24:27 UTC 起自主执行至 2026-09-16 01:24:27 UTC，并在科学门槛满足后使用额外 CPU、最多四卡 H100 或模型 API。授权与相对原阶段 A 提案的扩展见 `EXECUTION_AUTHORIZATION.json`。

本批已于 2026-09-15 22:34:09 UTC 收尾，耗时约 7 小时 10 分钟。优先阅读 [结果与下一轮门槛](FINDINGS_AND_NEXT_GATES_CN.md)、[完整执行报告](FINAL_REPORT_CN.md) 和 `RESULT_SUMMARY.json`。

72/72 月原生构建、24 条 C2 分支、108/108 个方法运行及 24/24 个正式评分组完成；628 个去重测试通过。模型合法回复 71/288，当前没有 LLM 优于强程序的证据。861 个可结算机会中的 16 个正例集中在一个地区日会话，不能当作 16 个独立过程。

末尾评分通过 [有记录的并行交接](stage_C_audit_handoff_01/README_CN.md) 完成。平台回读为 7 个作业成功、1 个原串行尾部已停止，无本批运行中作业。`CLOSED_WITH_CONTROLLED_AUDIT_HANDOFF` 保留原停止与未知进程退出码，不伪称原 worker 正常结束。

## 工作流与主要产物

| 阶段 | 内容 | 证据入口 |
|---|---|---|
| A | E/年度摘要与 bank 守卫修复，来源普查，六父重建及原策略续跑，24 条有限取证分支 | `C2_ENGINEERING_REPORT_CN.md`、`C2_ENGINEERING_RESULT.json`、`tests/` |
| A 原结果消费 | 既有 840 条轨迹正式审计与完整十配对、正负例及缺失分解 | `FULLWEEK_FINDINGS_CN.md`、`FULLWEEK_PAIRED_DECOMPOSITION.json` |
| B 获取 | 72 个地区月份目录、58,221 个唯一原文身份；复用 5,673 个缓存并补 52,548 个原文 | `annual_stage_B/PREPARATION_RESULT.json`、`DOWNLOAD_STATUS.json`、`DOWNLOAD_RESULTS.json` |
| B 构建/拟合 | 严格 72 月原生构建，2023 拟合、2024 年 1—11 月校准，先冻结再评测 | `annual_stage_B/joins/RESULT.json`、`annual_stage_B/fit/RESULT.json` |
| C | 12 个已暴露日会话，9 条件；一个 DeepSeek 查询选择器，最多 288 个 HTTP 请求意图 | `stage_C/INTENT.json`、`RESULT.json`、`ANALYSIS.json`、`REPORT_CN.md` |
| 收尾 | 测试去重、保护核验、API 与资源账本、完整终态 | `PRESERVATION_AFTER.json`、`RESULT_SUMMARY.json`、`FINAL_REPORT_CN.md` |

当前新增研究仅涉及 H15 航空能见度。模型选择补充查询，冻结程序输出未来目标的概率；不把程序概率声称为 LLM 直接生成的天气预报。全体 16 类计划、跨过程确认、真实 TAF 干预和原生影像实验仍各有自己的门槛。

## 主要解释限制

- 六个 C2 工程父会话同日、正例数均为零。概率与损失变化证明消费链运行，不证明极端事件检出能力。
- 72 个 TAF 覆盖任务均为 full；来源普查中存在其他窗口冲突和不支持报文，但没有把它们计作已完成的真实 TAF 干预。
- API 兼容性 HTTP/JSON 成功、合成题的一查询要求失败；保留失败且未重试。正式 selector 允许排名列表，真实表现单独统计。
- 第二个兼容性名额的 strict JSON schema 合成检查通过；它是开发诊断，不替代 288 条正式回复。后续接口建议见 [SELECTOR_INTERFACE_V2_PROPOSAL_CN.md](SELECTOR_INTERFACE_V2_PROPOSAL_CN.md)。
- CCI 的 editable 包影响了初始快照导入测试；ACP 原分支合同实际绑定冻结源码。下一阶段使用完整 `stage_c_source_02`，记录和保留两次导入方案。
- 所有样例为已暴露开发资料。小时、站点和处理分支不等于独立天气过程；不能保证 novelty 或模型收益。

## 运行与用量

数据遍历、下载、解析、hash、拟合与统计由后台程序完成，不逐条使用 Codex。watcher 每分钟读取短状态与阶段回执，在完成/失败/截止节点触发后续动作。被测模型的 token 由供应方响应记录；Codex 本身 token 无精确可用接口；CPU/GPU/网络用量另列，三者不混合。

所有 runtime 的 `LAUNCH_CLAIM.json`、`JOB.json`、`EXIT.json` 和日志保留。不要重新执行已消费的 launcher、父状态重建、续跑或处理分支；失败修复使用新的明确身份。模型任务达到门槛才真正派发；未达到不换样本或另选模型补结果。用户凭据在仓库外保存，本目录不含凭据值。
