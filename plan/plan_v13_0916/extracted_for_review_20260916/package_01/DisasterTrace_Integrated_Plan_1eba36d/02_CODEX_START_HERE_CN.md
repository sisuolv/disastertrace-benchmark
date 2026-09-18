# 交给 Codex 的第一批执行指令

本段是待用户交给执行器的指令。本次整合评审没有运行这些工单，也没有授权后续 API、训练或确认实验。

```text
项目：sisuolv/disastertrace-benchmark
分支：next-phase-v1
本次评审参考 SHA：1eba36dd272c72573d1309c78d45dbe97dd8af12
任务：只执行整合计划的第一批 A00—A06，完成后停止，不自动推进 B/C/D 或旁路任务。

先读：
1. disastertrace-starter/AGENTS.md
2. LATEST_PROGRESS_V12_CN.md
3. plans/v12_execution_20260915_01/FINDINGS_AND_NEXT_GATES_CN.md
4. plans/v12_execution_20260915_01/RESULT_SUMMARY.json
5. plans/v12_execution_20260915_01/FINAL_VERIFICATION_01.json
6. plans/v12_execution_20260915_01/FULLWEEK_FINDINGS_CN.md
7. plans/v12_execution_20260915_01/C2_ENGINEERING_REPORT_CN.md
8. plans/v12_execution_20260915_01/stage_C/REPORT_CN.md
9. disastertrace-starter/CURRENT_PHASE.md、IMPLEMENTATION_STATUS.md、DECISIONS.md、BLOCKERS.md
10. 本整合包的 01_MASTER_PLAN_CN.md、03_WORK_PACKAGES.json、04_PLAN_MERGE_MATRIX_CN.md。

A00：记录实际本地 HEAD、dirty/index、已有远端跟踪引用及其新鲜度。
首批离线，不执行 git fetch/ls-remote；附件中的远端 SHA 只是带审查时点的参照。
若本地继续前进，比较 reference→actual 的本地差异；不要 reset。
若必要版本对象或本地工件不存在，记录 BLOCKED，不联网补齐。
建立当前实现允许修改清单和历史不可变保护清单，二者分开。
不得改写旧模型回复、capture、journal、STOP、checkpoint、费用、预测、结果或冻结实现快照。
不要把 72 个月、840 条轨迹、24 C2 分支、288 请求当成未运行工作。
按真实 node IDs 对账历史 750 与 628；不得直接相减或相加。

A01：先在当前代码写 red test，验证 C2 缺报告/缺必要 trace/重复或错绑定不能仍通过。
新派生分析必须核对注册父×分支×机会集合；零特征变化不构成失败。
用新模块/新报告身份修复，保持已消费 v12 批次脚本和冻结结果可复算。
补 formal_bound/legacy_replay/engineering_diagnostic 资格与终态区分。

A02：以 mock HTTP 和故障注入修复最终 dispatch permit、STOP/截止和一次性发送。
同时修 capture 字节/截断/脱敏哈希，以及原 capture 恢复后被 failure 标记永久阻断的问题。
保留 failure，追加 reconciliation receipt；不得删除失败、重发原请求、重复结算或回填及时性。
明确单节点/共享文件系统的验证范围。多节点锁未验证时限制单一 dispatch authority。
无法判断 provider 是否处理过的 attempt 保留 UNKNOWN，不自动重试。

A03：实现 query-only v2，唯一动作字段 query_order。
prompt、输入说明、逻辑 schema、provider schema 和 parser 同一契约生成。
先离线测试，不调用真实 provider；旧自由输出仍按旧契约解释，不事后转换字段。
不以模型是否产生严格子集或重排作为接口资格。

A04：新增 residual_query_plan.v2 的 none/first_new/second_new/all_new。
按真实私有/共享权益排除 cached/requested/unavailable，保留 disposition。
配对身份记录 consumer/bank/calibration/clock/adoption 等实际因子，不仅判断 F_COMMON 名称。

A05：只读普查既有资料/回执的时钟、合法输入、subset、动作异质性及历史影响。
可以进行离线特征/算术诊断，不重拟合，不注册或执行新的真实天气分支/完整周实验。
无本地支持的分析项标记 BLOCKED，不依据未来标签挑日期或父状态。
已有 LLM 动作的离线观察只标记 posthoc diagnostic，不覆盖旧正式表。

A06：执行当前去重回归集合、上述 red→green 测试及本地可得的旧 capsule；
保存命令、node IDs、退出码、JUnit（适用时）、stdout/stderr、实现/结果哈希。
缺 fixture/dependency 时逐项声明未运行，不下载、不跳过后仍称全部通过。
输出旧结果影响扫描和第一批完成/阻塞报告，更新当前状态入口并停止。

输出目录：新建 plans/v12_integrated_followup_01/；如已存在，用新后缀，禁止覆盖。
交付至少：BASELINE、PROTECTION_MANIFEST、NODEID_DIFF、TEST_RECEIPTS、
HISTORICAL_IMPACT、CLOCK_ACTION_CENSUS、NEXT_GATE_DECISION、STOP_RECEIPT。

必须保持：
network_downloads=0；remote_api=0；new_model_calls=0；gpu=0；training=0；
confirmation_outcomes_opened=false；historical_outputs_rewritten=false。
不打开 Bay 2025-02-17—23；不启动新288-call；不重消费旧兼容性名额。
不自动启动完整日历桥接、新 bank、C2 扩展、温度、多模态或行动实验。

完成汇报分为：实际修改、测试证据、历史影响、仍未证明的科研结论、下一批需要的具体授权。
不能把“离线探针观察复现/实现通过”写成“模型有增益/独立确认完成”。
```

## 第一批后真正要回答的问题

不是“还有多少个 bug”，而是：现有数据上的信息差异是否真实、是否可由公开状态利用、是否值得进入新的 CPU 科学比较。下一批 B00/B01/B02 必须预登记具体日历、分支和预算；B03 仅在必要且获准时训练。
