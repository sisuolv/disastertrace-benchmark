# 给 ChatGPT Pro 的 v12 复查说明

请复查这次已经完成的开发实验，重点判断代码、数据证据和研究结论是否一致。不要把旧的“待复核/运行中”文档误认为当前终态。最新入口为 `LATEST_PROGRESS_V12_CN.md`。

## 建议阅读顺序

1. `plans/v12_execution_20260915_01/FINDINGS_AND_NEXT_GATES_CN.md`：结果和解释边界。
2. 同目录的 `RESULT_SUMMARY.json`、`FINAL_VERIFICATION_01.json`、`FINAL_REPORT_CN.md`：实际完成情况。
3. `stage_C/ANALYSIS.json`、`ANALYSIS_ROWS.json`、`REPORT_CN.md` 与 `SELECTOR_BEHAVIOR_DIAGNOSTIC.json`：完整分母、配对、缺失敏感性和真实模型行为。
4. `C2_ENGINEERING_REPORT_CN.md`、`C2_FIELD_TO_LOSS.json`、`PLANNED_EXECUTED_ACTIONS.json`：有限取证分支的实际作用链。
5. `annual_stage_B/DATA_QUALITY_REPORT.json` 与 `fit/REGISTRATION.json`、`ROLE_ADMISSION.json`、`BANK_FREEZE.json`：原生数据可用性和拟合/校准角色。
6. `disastertrace-starter/src/disastertrace/monitoring_v1/`、`monitoring_fixed_v1/` 和对应测试；本轮脚本位于 `plans/v12_execution_20260915_01/`。
7. `SELECTOR_INTERFACE_V2_PROPOSAL_CN.md` 与 `plans/v12_review_amendment_20260915_01/OVERALL_PLAN_CN.md`：后续计划。

## 本轮事实

- H15 航空低能见度是本轮新增实验灾种，不能称 16 类全部完成。
- 72/72 个地区月份构建完成，缺少的 52,548 个原文全部获取；传输成功不代表每条原文均可解析。
- 2023 拟合、2024 年 1—11 月校准；2025 会话属于已暴露开发资料，确认集仍关闭。
- 六个 C2 父会话同日且正例数为零；24 个分支、36 个配对出现特征和有效概率变化。
- DeepSeek-V4-Flash 只负责查询选择，概率由冻结程序产生。288 个正式请求全部 HTTP 200，但仅 71 个合法回复，192 个结构错误、25 个非纯 JSON。
- 71 个合法回复中，58 个不查询、13 个选全部三个候选，没有合法的严格子集选择或重排。
- 每方法 864 个机会，861 个可结算、16 个正例、3 个缺失；16 个正例全部集中在芝加哥 2025-12-01。
- 模型 Brier 为 0.0085666，覆盖率规则为 0.0077496，F_COMMON 为 0.0072363；F_COMMON 的 bank 不同。模型相对 F_BASE_ONLY 的微小改善全部来自负例，缺失敏感性界跨零。
- 两个兼容性名额已用完。第二次 strict schema 的合成题通过属于事后开发诊断，没有替换正式回复，也未证明完整天气接口修复。
- 原串行评分尾部已被有记录地停止；复用 3 个评分组，21 组使用相同冻结 scorer 并行完成。停止状态和未知原进程退出码保留。24 组评分和 108 个方法会话的派生损失核对通过。

## 请优先回答

1. 支持集合、来源时间、父状态恢复及实际消费链有没有泄漏、混淆或不成立的推断？
2. 格式失败与选择空间有限分别限制了什么结论？下一轮 strict schema 的实际天气验证应设哪些最小门槛？
3. 共同信息 bank、values bank 与 FOLLOW 的差异是否被正确解释？拟合与应用时点差异有多大风险？
4. 单日 16 个正例、同日零正例 C2 分支和缺失结果，允许哪些结论、禁止哪些结论？
5. 目前 C1/C2/C3 哪些已有可复查证据，哪些仍只有工程资格？请给出最小、可执行的下一批建议，避免扩展核心概念或无依据增加模型数量。
6. 并行评分交接是否保留了完整审计依据，发布材料是否足以支持这里的表述？

请按严重性列出具体文件/函数/证据与修复建议，并区分“实际发现的实现问题”“未验证的风险”和“数据覆盖不足”。本 ZIP 是代码与结果阅读包，缺少完整原文、journal 和 checkpoint，不能据此声称独立重跑了完整大型实验。
