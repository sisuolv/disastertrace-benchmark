---
title: DisasterTrace v8 最新实现复查与 Codex 后续执行计划
plan_version: "v8-result-driven-20260914"
planning_date: "2026-09-14 UTC / 2026-09-13 America-New_York"
language: zh-CN
repository: "sisuolv/disastertrace-benchmark"
branch: "next-phase-v1"
reference_commit: "5ed0fb94ae7bf235b37e7528e201b603271edffa"
supersedes:
  - "DisasterTrace_Current_Audit_and_Codex_Next_Plan_20260913_CN.md"
  - "any execution priority based on 6c7c7e81 or earlier"
review_scope: "GitHub current source + saved test/audit receipts; no independent full checkout rerun in this review"
default_allow_network: false
default_allow_model_calls: false
default_allow_gpu: false
default_allow_paid_api: false
default_allow_training: false
---

# DisasterTrace v8 最新实现复查与 Codex 后续执行计划

## 0. 给 Codex 的首轮直接指令

```text
仓库：sisuolv/disastertrace-benchmark
分支：next-phase-v1
本计划审查时远端提交：

5ed0fb94ae7bf235b37e7528e201b603271edffa

不要 reset 到本提交；先读取实际 HEAD。若分支已前进，生成差异审计后再应用本计划。
不得重启或复用任何已消费模型/GPU 任务，尤其不得重跑到出现正收益。

开始前依次读取：

1. disastertrace-starter/AGENTS.md
2. LATEST_PROGRESS_20260914_CN.md
3. plans/v8_measurement_execution_20260913_01/README_CN.md
4. plans/v8_measurement_execution_20260913_01/RUN_REPORT_CN.md
5. plans/v8_measurement_execution_20260913_01/ADAPTIVE_SCORECARD_CN.md
6. plans/v8_measurement_execution_20260913_01/NEXT_PHASE_PLAN_CN.md
7. plans/v8_measurement_execution_20260913_01/EXECUTION_STATUS.json
8. plans/v8_measurement_execution_20260913_01/WORK_PACKAGE_PROGRESS_02.json
9. plans/v8_measurement_execution_20260913_01/REGRESSION_MATRIX_07.json
10. plans/v8_measurement_execution_20260913_01/REVIEW_REQUEST_CN.md
11. disastertrace-starter/IMPLEMENTATION_STATUS.md
12. disastertrace-starter/DECISIONS.md
13. disastertrace-starter/BLOCKERS.md
14. disastertrace-starter/CURRENT_PHASE.md
15. 本文件

首轮执行范围固定为 CPU/offline：

- V8-AUDIT-00：修复 CURRENT_PHASE 指针并建立最新审计基线；
- V8-HARDEN-01：版本化“执行失败后是否继续后续机会”的策略；
- V8-HARDEN-02：加强 OutcomeRegistry 的状态与提供方时间合同；
- V8-HARDEN-03：生产模式强制 declared execution/source contract；
- V8-COPY-04：实现并验证 visible-current / latest-baseline 的强复制程序基线；
- V8-ATTR-05：把可见数值来源、采纳协议和有效预测归因纳入正式报告；
- V8-TEST-06：运行相关完整回归、portable replay 和新 red/green tests；
- 完成后停止，不下载新确认数据、不调用模型、不申请 GPU、不打开预留确认周。

首轮不得：

- 修改或替换已有 6,118 次模型调用；
- 改写 adaptive_large_02、large-model fixed-input 或原 GPU 冻结源码；
- 将 pt-ug2dg5ln 的平台 FAILED 改为 SUCCEEDED；
- 将补充审计写成原自动审计完整成功；
- 把 11,232 方法机会写成独立天气样本；
- 把 persistent override 的旧值收益称为模型产生新概率；
- 把 D-sim 写成真实防灾收益；
- 把温度、MRMS、HEFS 的窄资格升级成完整灾害任务；
- 启动旧 X09 launcher 或修改其原最晚启动界限。
```

---

# 1. 本次复查的真实起点

## 1.1 最新分支状态

本计划以 `next-phase-v1` 的提交 `5ed0fb94...` 为参考。相较上一轮 v7，该提交已经完成：

- v8 235B/8B 固定输入实验；
- 52 个 235B 自适应全日会话；
- source / selector / predictor 执行身份和在途恢复；
- 原子事件事务；
- OutcomeRegistry 和 ComparisonContract；
- 40 条全日程序轨迹；
- 可见概率来源归因；
- 温度日/多日闭环；
- 合成 D 与当前 admitted F 条件回放；
- X09 离线协议；
- 4 小时 source-only 前瞻采集；
- 502 项不同相关测试和本地复查包。

因此，早期“先实现基础类型化 admission、单一时钟、在途恢复和执行合同”的任务已不再是主缺口。

## 1.2 复查证据边界

本次复查读取当前 GitHub 源码、测试矩阵、执行状态、完整报告和结果表，但没有在本对话运行环境中独立 clone 私有仓库并重跑 502 项测试。

因此本文结论分为：

- **代码直接确认**：从当前源码可以确定的行为；
- **保存回执支持**：仓库中的测试、审计和模型回执所支持的事实；
- **待验证风险**：需要 Codex 新增回归或运行反例，不能直接声称当前实验已错。

首轮 Codex 必须重新记录实际 HEAD、环境和测试命令。

---

# 2. 当前实现是否正确：总体结论

## 2.1 可以认为正确的范围

当前实现对以下有界范围基本正确：

1. H15 原生 TAF/METAR 的 typed target、baseline、evidence 和 cutoff；
2. 先选择当前原生版本，再检查固定目标覆盖；
3. 同刻事件排序、非法批次整体拒绝和防重入；
4. typed admission 的事务副本与提交；
5. source/selector/predictor 请求、执行身份和费用绑定；
6. 未知费用保留，不把失败调用免费释放；
7. source/selector/predictor 单个在途调用的本地串行跨进程恢复；
8. committed spool 中 checkpoint 先持久化、worker 后 claim；
9. proposed / admitted / effective forecast 的区分；
10. E-only 不进入 F 分母；
11. canonical target outcome 和跨 lead 一致性；
12. comparison invariants 与显式 interventions；
13. 完整机会分母、共同 baseline trace、共同结果版本；
14. 当前可见事实 E 与未来预测 F 分开；
15. synthetic D 与真实天气 F 分开；
16. 保存负结果、旧错误、timeout 和未完成原自动审计。

这些支持“测量链在当前注册范围内可信”，不支持“任意异步系统、远端 exactly-once、跨灾种通用任务已经完成”。

## 2.2 不能认为已经完成的范围

仍未完成：

- 一个 session 内多个并发 pending source/model/tool；
- 任意远端基础设施 exactly-once；
- 执行失败后的通用继续/降级策略；
- 当前概率复制强基线的正式闭环轨迹；
- H15 区域独立概率映射和校准；
- 独立天气过程确认；
- X09 实际模型运行和相同总输出预算对照；
- H07 MRMS 的确切物理积累端点与 matched F/MM；
- H08 流量/水位/调蓄/断面物理 F；
- 温度连续 adaptive session；
- D 与 acquisition/predictor 的完整反馈；
- 真实防灾决策收益；
- 实时模型预测提交和成熟结果结算；
- 完整 16 灾种研究级发布。

---

# 3. 当前进度与结果的正确解释

## 3.1 工程进度

| 工作 | 当前状态 | 正确边界 |
|---|---|---|
| W00-W07 | 当前 H15 注册范围内基本完成 | 单日/开发数据不是独立确认 |
| W08 | 单个 pending 的本地串行 source/selector/predictor 恢复通过 | 非通用并发、非远端 exactly-once |
| W09 | 小型真实残余图与联合见证 | 大图、跨过程机制未确认 |
| W10 | 235B/8B 固定输入诊断完成 | 暴露开发集 |
| W11 | 连续自然日历和区域数据阶段推进 | 区域映射与过程分组未完成 |
| W12 | 52 自适应会话和 5,108 次调用完成 | X09 未运行，单日少正例 |
| W13 | 温度日/多日候选、结果和 snapshots | 非连续主动会话、未校准 |
| W14 | MRMS 单位/QC/标称时长 | 物理端点、F/MM 未完成 |
| W15 | HEFS 版本 E 和免费共同信息对照 | 物理 F 未完成 |
| W16 | 合成 D、admitted-F 条件 D、串行恢复 | 无完整反馈、无真实收益 |
| W17 | 暴露与依赖审计 | 预留确认集未打开 |
| W18 | source-only 4h capture | 无实时模型 F |
| W19 | 97-source/16-hazard 治理 | 16 类完整发布未完成 |

## 3.2 固定输入结果

### E

235B：

- common-only E-only：43/48；
- one-read E-only：2/48；
- all-read E-only：47/48。

这不是“235B 越大越好”，而是发现：

> 235B 在部分证据时经常把一个已读槽位推广成整个注册集合的确定结论。

8B 在部分输入上较高的正确率又常接近 always-unknown。

因此以后 E 必须同时报告：

```text
accuracy
always-unknown baseline
unjustified certainty
unnecessary unknown
conflict handling
conditional confusion by evidence completeness
```

### F

235B 固定输入的 288 个 F 全部保持 dispatch baseline；8B 只改 3 个，其中一项恶化。

结论只能是：

- 当前模型没有展示新预测信息；
- 不应要求模型为了“有贡献”必须修改概率；
- 下一步要加入更强的 deterministic copy controls，而不是换更大模型继续试。

### TAF

coverage 仍约 5–6/18，version 约 16–18/18。ISO/epoch 没有稳定改变 coverage。

这说明错误不只是时间显示格式，需继续拆：

- 当前版本选择；
- DDHH/validity 解码；
- interval containment；
- partial/full/none 分类；
- current/superseded source IDs。

## 3.3 自适应结果

关键事实：

```text
4,916 predictor replies
4,915 == visible current state probability
1 == visible latest baseline probability
0 differs from both
```

所以：

- 数值可由“直接重发当前可见状态”的程序复现；
- 1,054 个值虽不同于最新 baseline，却仍等于旧 override/current state；
- persistent override 的正/负差异主要来自旧值持续，而不是模型创造新概率；
- typed_auto_propose 自动提出 OVERRIDE，模型没有选择 FOLLOW/OVERRIDE。

当前最强科学发现不是预测增益，而是：

1. 模型会复制当前可见概率；
2. 部分证据会导致无依据确定性；
3. 更多 E 可判定不保证 F 改善；
4. 共享证据可增加 E coverage，却可能让 F 变差；
5. adoption/protocol 可以制造表面 gain/loss，必须与新预测信息分开。

## 3.4 程序与共享结果

5km 的 2×2 显示：

- shared 显著提高 E 可判定；
- Follow Brier 仍优于多种补证程序；
- help 的机会可能更多，但 harm 幅度更大。

因此：

- all-read 不是 F upper bound；
- E sufficiency 不是 F accuracy upper bound；
- shared cache benefit、selector benefit、predictor benefit 必须分开。

## 3.5 平台 FAILED 的正确解释

`pt-ug2dg5ln`：

- platform state = FAILED；
- inference worker exit = 0；
- 52 controllers exit = 0；
- 原自动 audit 未在外层时限内完成；
- supplement audit 最终核完 52 cases。

必须同时保留以上事实。后续应改进 orchestration，但不重跑本批。

---

# 4. 代码审查发现：P0 / P1 / P2

# P0：下一次任何新实验前处理

## P0-01：CURRENT_PHASE 仍指向 MM-4

### 类型

确定性文档/执行治理缺陷。

### 位置

`disastertrace-starter/CURRENT_PHASE.md`

### 影响

Codex 按 AGENTS 要求读取该文件时，可能误回已消费 MM-4/MM-5A 路线，忽略 v8 当前入口。

### 最小修复

把它改成短 mutable pointer：

```text
current commit
latest report
scorecard
next plan
review request
consumed jobs
current no-go gates
```

历史内容移入 archive 链接，不删除。

### 回归

- pointer 路径存在；
- pointer 日期不早于 IMPLEMENTATION_STATUS 首段；
- current commit 与 baseline audit 一致；
- 不允许 “Next” 指向已消费 launcher。

---

## P0-02：缺少正式的 visible-current copy 闭环基线

### 类型

研究归因缺口，不是旧结果实现 bug。

### 证据

几乎所有 predictor 输出都可由读取 visible current state 复现。

### 必须新增的程序 arms

```text
C00_follow_latest_baseline
C01_copy_visible_current_state
C02_copy_dispatch_latest_baseline
C03_hold_last_override
C04_frozen_frequency_B
C05_f_B
C06_f_B_E
```

### 两种证据

1. **静态归因**：对已有捕获分类，不产生新调用；
2. **新连续轨迹**：按自身程序成本从头运行，不能修改旧 LLM 时间戳冒充新轨迹。

### 正式报告字段

```text
proposal_source:
  novel_numeric
  copied_visible_current
  copied_latest_baseline
  copied_other_visible_value
  invalid_or_missing

delta_to_current
delta_to_baseline
effective_gain_due_to:
  numeric_proposal
  persistence
  baseline_update
  adoption
  fallback
```

### 放行门槛

没有 C01/C02 新连续程序轨迹，不再运行新的 predictor 模型比较。

---

## P0-03：执行失败后隐式“永久停机”

### 类型

确定性控制策略缺口。

### 位置

`monitoring_v1/policies.py`

当前逻辑在任意已有 predictor `execution_status` 或 selector `execution_status` 后，抑制后续独立时刻调用。

### 问题

“不重试原调用”不等于“之后所有不同机会都不能运行”。

当前成功批次基本没有触发，因此不影响当前分数；前瞻/故障实验会被严重影响。

### 新合同

```text
failure_continuation_policy:
  fail_session_v1
  skip_failed_call_continue_v1
  fallback_selector_continue_v1
  pause_until_reconcile_v1
```

冻结到 experiment invariants/interventions。

### 必须测试

- t1 predictor unknown，原 call 不重发；
- t2 新 opportunity 在 continue 策略下可运行；
- unknown reservation 保留并继续占预算；
- selector failure 可按预注册 fixed fallback 继续；
- fail_session 保持旧行为；
- 不允许事后按结果选择 continuation policy。

---

## P0-04：生产执行身份仍允许弱绑定 Python callback

### 类型

生产硬化风险。

### 位置

`monitoring_v1/execution.py`

undeclared Python callback 的 identity 绑定 bytecode、defaults 和有限 closure；不能完整绑定外部 globals、模型目录内容或可变对象内部状态。

### 当前结果影响

实际模型已有 declared contract 的证据；不能据此说当前 235B 批次错。

### 最小修复

新增：

```text
execution_identity_mode:
  test_callback
  declared_production
```

任何实际模型/source/shadow：

- 必须 `declared_production`；
- 必须 model/weights/tokenizer/adapter/generation/runtime；
- source 必须 source contract；
- callback fallback 仅用于 tests/program fixtures。

### 回归

- 改模型路径/权重 manifest/tokenizer/prompt/runtime 必须 identity 改变；
- 修改全局变量但不更新 declared contract 必须拒绝生产启动；
- 历史 frozen execution contract 仍可读取。

---

## P0-05：OutcomeRegistry 需要提供方状态机，而非只有通用字段

### 类型

验证缺口；没有证据表明当前 outcome 表已经错误。

### 位置

`monitoring_fixed_v1/outcomes.py`

当前已绑定 target、物理支持、单位、hash、quality、observed/published/fetched/resolved，但通用 schema 仍允许一些语义模糊组合，例如：

- mature 但某些关键时间为空；
- missing 带非空 value；
- published/observed/fetched/resolved 的提供方顺序没有完整约束；
- provisional 与 mature 的转换规则未版本化；
- quality_status 是任意非空字符串。

### 修复方式

不要写一个过度通用的错误顺序；新增 provider-specific resolution policy：

```text
OutcomeResolutionPolicy:
  policy_id
  allowed_statuses
  required_fields_by_status
  chronology_rules
  maturity_transition
  allowed_quality_codes
  result_identity_rule
```

H15、temperature、MRMS、HEFS 分别实现。

### red tests

- missing + non-null outcome；
- mature 缺 required source/times；
- impossible provider chronology；
- provisional 被另一 lead 当 mature；
- same target/resolution 不同 quality；
- result version silently changed。

---

## P0-06：平台推理与 audit 生命周期应分离

### 类型

运行编排缺口。

### 问题

当前外层时限使平台 job FAILED，尽管 inference/controllers 完成；最终依赖 supplemental audit。

### 修复

以后冻结三个独立状态：

```text
inference_state
controller_state
audit_state
platform_state
```

- 推理结束先封存 captures；
- audit 独立 CPU/finalizer；
- 预留 audit wall-time；
- 外层 deadline 前生成 completion checkpoint；
- 不因 audit 未完成重新调用模型。

---

# P1：独立确认或跨过程扩展前处理

## P1-01：一个 session 只支持一个 pending invocation

### 类型

明确设计局限。

当前 checkpoint 只允许 pending source / selector / predictor 三者之一。

### 下一版本

```text
session_inflight_set.v6:
  pending_attempts[]
  concurrency_limit
  dependency_edges
  completion_order
  reservation bindings
```

### 测试

- 两 source 并行，逆序完成；
- source + predictor 合法重叠；
- query 与 preparation 并行；
- cutoff 与两个 completion 同刻；
- duplicate remote receipt；
- 一个 unknown 不阻塞无依赖的另一个；
- inherited reservations 不重复支付。

不要在 H15 confirmation 前强制完成所有通用并发；但 D/MM 的“查资料与准备并行”实验前必须完成。

---

## P1-02：本地 spool 不能升级成远端 exactly-once

当前 hardlink/fsync/claim 对测试文件系统有效。下一步需：

- 写明支持的 filesystem contract；
- 启动时探测 hardlink、fsync、atomic publish；
- 远端队列使用 provider idempotency key 或 reconciliation；
- 没有能力时保持 unknown，不自动 retry；
- 文档继续写 local committed outbox，不写 universal exactly-once。

---

## P1-03：branch intervention 应有明确事件优先级

当前 restore 会把 policy intervention 注册为后续 event。为了避免依赖 event ID 字典序：

- 为 `policy_intervention` 指定独立 phase/precedence；
- 保证它发生在恢复后的第一个 selector/begin 之前；
- parent checkpoint hash 和 changed fields 进入 snapshot/report；
- 测试任意 event ID 不改变顺序。

这属于稳健性修复，不证明当前分支结果错误。

---

## P1-04：neighbor E 合同中的站点数量检查需明确

`load_session()` 的错误消息称需要至少两个 sites，但实现只检查 query list 非空。

Codex 必须决定合同：

- “至少一个邻站槽位”；
- 或“至少两个不同站点”。

然后让验证、提示和错误文本一致，添加单站/重复站测试。

---

## P1-05：action/adoption 仍由系统自动完成

当前 adaptive 使用 `typed_auto_propose.v1`：

- 模型输出 E/F；
- 系统自动将合法 F 提议为 OVERRIDE；
- 模型没有选择 FOLLOW/OVERRIDE。

因此 current results 不能支持“模型会选择是否采用修订”。

后续如果研究 adoption，新增独立条件：

```text
fixed candidate + fixed completion time
×
follow
threshold_adopt
risk_limited_adopt
llm_adopt
```

候选数值、完成时间和输入保持相同，只改变采用规则。

---

# P2：研究设计门槛

1. 11,232 方法机会来自同一开发日，不是独立过程。
2. 1km 没有正例，5km 只有两个正目标。
3. 235B/8B 结构、训练、量化不同，不能归因参数量。
4. regional calendars 没有区域 probability map。
5. all exposed calendars 不能再当 confirmation。
6. reserved week 未打开，但未自动保证独立。
7. temperature 仍无 continuous adaptive information value。
8. MRMS 物理 endpoint 未核准。
9. HEFS common product E 免费已知，不是 C1 acquisition gain。
10. D outcomes 仍是 synthetic demand。
11. X09 只有离线协议，且现有 per-request output budget 不等总组预算。
12. source-only shadow 不是 prospective forecast evaluation。

---

# 5. 结果驱动的后续优先级

```text
P0 correctness/governance
→ visible-copy baselines and attribution
→ partial-evidence E failure isolation
→ strong H15 B/f(B)/f(B,E) and regional calibration
→ process grouping + external extreme diagnostic
→ freeze unopened confirmation
→ one bounded confirmation
→ temperature continuous session
→ D action-aware information value
→ X09 equal-budget run
→ MRMS/HEFS/MM
→ prospective forecast shadow
```

不建议：

- 继续比较更多模型尺寸；
- 在同一 Bay day 上继续堆调用；
- 为获得正 gain 调 prompt；
- 用 persistent old-state gain 宣称 F innovation；
- 直接把 16 类全部接 D；
- 在 MRMS/HEFS 物理合同未过关时做多模态故事。

---

# 6. Codex 工作包

## V8-AUDIT-00：最新入口与保全

### 交付

```text
plans/v8_postreview_20260914/
  BASELINE.json
  AUDIT_FINDINGS_CN.md
  AUDIT_FINDINGS.json
  SOURCE_HASHES.json
  TEST_BASELINE.json
```

更新 `CURRENT_PHASE.md`。

### 验收

- 实际 HEAD、remote HEAD、dirty/index 状态；
- 关键源和报告 hashes；
- consumed jobs/launchers；
- 485 core + supplementary tests 的来源分开；
- 不把历史 test receipts 累加；
- 不运行外部动作。

---

## V8-HARDEN-01：失败继续策略

### 修改

- config/schema；
- experiment_spec；
- selector/predictor loop；
- report fields；
- checkpoint compatibility；
- tests。

### 默认

历史 v8 冻结保持 `fail_session_v1` 解释不变；新开发推荐
`skip_failed_call_continue_v1`，但必须预注册。

### 结果字段

```text
failed_logical_call_id
failure_disposition
continuation_policy
later_calls_attempted
reservation_retained
fallback_used
```

---

## V8-HARDEN-02：OutcomeResolutionPolicy

### 文件建议

```text
monitoring_fixed_v1/outcome_policies.py
monitoring_fixed_v1/outcomes.py
tests/test_monitoring_outcome_policies.py
```

先实现 H15 和 temperature；MRMS/HEFS 继续 blocked。

---

## V8-HARDEN-03：production execution contracts

### 文件

```text
monitoring_v1/execution.py
monitoring_v1/source_execution.py
monitoring_v1/session_checkpoint.py
```

### 接口

```text
config["execution_identity_mode"] = "declared_production"
config["source_identity_mode"] = "declared_production"
```

测试 callback 继续显式 `test_callback`。

---

## V8-COPY-04：visible-value 强基线

### 新 predictor kinds

```text
copy_current_state
copy_latest_baseline
hold_last_override
frequency_mapping
calibrated_baseline
calibrated_with_evidence
llm
```

### 实现要求

- typed program predictor；
- 独立 execution identity；
- 程序 compute cost；
- 全新 continuous trajectories；
- old capture attribution separate；
- same selectors/budgets/clock；
- all 432 opportunities。

### 主要实验

```text
selector fixed:
  copy-current vs copy-baseline vs frequency vs LLM

predictor fixed:
  round-robin/risk/coverage/batch/LLM selector
```

### 出口

正式 scorecard 可以区分：

- 新数值预测；
- 可见旧值复制；
- protocol persistence；
- baseline update；
- adoption。

---

## V8-ATTR-05：正式数值来源归因

将现有 posthoc visible-value attribution 变成版本化 evaluator：

```text
forecast_value_attribution.v1
```

每个 call 和 cutoff 输出：

```text
dispatch_current
dispatch_latest_baseline
proposal
effective_at_cutoff
exact_source_class
help_harm_no_change
gain_component
```

保留 exact equality，同时增加十进制规范化和 delta 报告；不得用宽 epsilon 把真正小修订吞掉。

---

## V8-EVIDENCE-06：部分证据错误套件

### Baselines

```text
always_unknown
deterministic_visible_support
slotwise_program_aggregate
llm_direct
llm_slotwise_then_aggregate
```

### 因子

- common-only；
- one-read；
- all-read；
- missing；
- censored interval；
- positive witness；
- all-refuting complete set；
- conflicting same-slot；
- current/superseded；
- raw vs structured slot list。

### 指标

```text
accuracy
unjustified_certainty_rate
unnecessary_unknown_rate
positive_witness_recall
complete_refutation_accuracy
conflict_accuracy
format_validity
tokens/time
```

### 重要边界

deterministic visible support 只使用模型已见产品，不使用未来 outcome。

---

## V8-H15-07：强 baseline 和 regional calibration

### 冻结比较

```text
B        = latest lawful common research baseline
f(B)     = calibration/postprocessing using independent train/calibration period
f(B,E)   = same method + lawful supplementary evidence
P        = persistence/current-state controls
```

### 要求

- per-region bank；
- train/calibration/evaluation dates；
- positive support；
- station/process grouping；
- bank hash；
- mapping metadata；
- no fit on exposed evaluation;
- calibration and discrimination separately；
- Bay cross-year transfer separately disclosed。

### New York / Chicago / Denver

仅在 regional banks 通过后评分，不直接套 Bay map 后声称 cross-region skill。

---

## V8-DATA-08：自然集、极端诊断集和依赖单元

### 自然连续集

保留全部平静和缺失时段，主 Brier/MAE。

### 外部规则极端集

- selection rule before model；
- complete process window；
- adjacent normal controls；
- all registered sites；
- quality failures retained；
- separate prevalence and metrics；
- 不用于总体校准结论。

### Grouping

```text
parent_weather_process
region_block
station_time_window
target_contract
lead_family
input_lookback
outcome_window
purge_interval
```

开发数据估计块间变异；不得以 calls 数量计算样本量。

---

## V8-CONFIRM-09：打开确认集前冻结

先写：

```text
CONFIRMATION_PROTOCOL.json
CONFIRMATION_PROTOCOL_CN.md
```

必须冻结：

- commit/source hashes；
- model/execution contract；
- prompt；
- direct-copy/program baselines；
- predictor/selector arms；
- budgets；
- adoption policy；
- calibration banks；
- outcomes and maturity；
- primary/secondary metrics；
- process grouping/purge；
- missing/failure rules；
- sample/stop rule；
- no selective retry；
- no extension based on who wins。

只有独立审计通过才允许下载/打开 Bay 2025-02-17–23。

若正例不足，报告 underpowered，不追加挑选获胜日期。

---

## V8-TEMP-10：温度连续 typed session

### 第一阶段 CPU/program

将现有：

- mx2t6/mn2t6；
- daily target；
- three-day duration event；
- canonical outcomes；
- 480 snapshots；

接入同一 SessionCoordinator。

### 必须新增

- full common forecast；
- lawful supplementary evidence；
- query catalog；
- availability policy；
- multi-cutoff session；
- current/baseline copy controls；
- calibrated and uncalibrated labels；
- independent process grouping。

### 不允许

- 把瞬时 t2m 当日极值；
- 乘三日边际概率；
- 把 day0 当完整未来日；
- 称 heatwave/coldwave，除非 final definition 冻结。

温度是优先第二过程候选，因为其物理闭环比 MRMS/HEFS 更成熟。

---

## V8-D-11：行动需要决定信息价值

该任务直接落实当前最值得押注的 novelty。

### 三层隔离

```text
F head:
  weather evidence only
  no DecisionSpec/preferences

Acquisition head:
  may see remaining preparation feasibility and DecisionSpec

D policy:
  sees frozen/admitted F + preparation state + DecisionSpec
```

### Pair design

天气、原始证据、target 和 F predictor 固定，只改变：

- preparation duration；
- capacity；
- start deadline；
- action cost；
- cleanup/cancel cost；
- reversibility；
- miss penalty。

### 必须验证

1. fixed evidence 条件下，DecisionSpec 不改变 F request/hash/output；
2. D action 随准备条件合理变化；
3. action-aware acquisition 可以变化；
4. 如果 acquisition 导致合法 evidence 不同，最终 F 可以不同，但必须归因；
5. 已无法改变的任务不继续昂贵查询；
6. query 和 preparation 可以并行——这需要 multi-pending 资格。

### 基线

- no preparation；
- fixed threshold；
- EDF；
- rolling two-step；
- exact small optimizer；
- LLM D 最后加入。

只报告 synthetic DecisionSpec loss，不报告真实防灾收益。

---

## V8-CONCURRENCY-12：多 pending

在 D/MM 前实现：

```text
session_inflight_set.v6
```

先支持：

- multiple source；
- source + processing；
- source + preparation；
- optional predictor overlap。

不必立即支持所有任意并发。

---

## V8-X09-13：联合目标同预算实验

现有协议保留，不重开旧 launcher。

新的 fresh freeze 同时报告两种公平性：

1. 相同 per-request output cap；
2. 相同 per-three-target-group total output budget。

所有 single/multi calls 看相同 shared context。

指标：

- per-target E/F；
- group validity；
- all-target failure；
- total tokens；
- batch wall time；
- per-target normalized cost；
- copy-current attribution。

先运行小型 interface pilot；若没有独立价值，不优先大 235B 矩阵。

---

## V8-MRMS-14：物理时间合同

先解决：

- accumulation start/end；
- issue/available time；
- valid time；
- missing/no coverage；
- spatial support；
- matched forecast/outcome；
- source lineage。

然后建立：

```text
same raw asset
× numeric product
× professional nowcast
× structured features
× native image/VLM
```

评估器 mask 不可免费进入模型。

---

## V8-HEFS-15：水文物理 F

免费完整 HEFS 继续作为 common baseline，不计 charged acquisition gain。

必须核准：

- QINE identity；
- 43/member semantics；
- instantaneous/hourly average；
- regulation；
- station/cross-section；
- unit；
- USGS target equivalence；
- flow vs stage；
- threshold；
- availability。

未核准时只做 E/version/transport diagnostic。

---

## V8-SHADOW-16：source-only 到 prospective F

现有 AWC 4h capture 是 source qualification。

下一步先冻结：

- stations；
- target windows；
- cutoffs；
- baseline/predictor；
- submission format；
- first-seen rule；
- maturity；
- network failure policy；
- no public action。

先提交 program baselines，再考虑一个冻结模型；结果成熟后自动结算。

---

## V8-FINALIZE-17：运行编排和发布

### 分状态

```text
platform_state
worker_state
controller_state
capture_state
audit_state
score_state
publication_state
```

### 规则

- audit 不完成不重跑 inference；
- supplement import 有 provenance；
- original incomplete audit preserved；
- separate CPU finalizer；
- no result replacement；
- frozen source vs current source clearly separated。

---

# 7. 首轮 CPU 工作的具体测试清单

## Governance

- stale CURRENT_PHASE fails；
- consumed launcher cannot be current next；
- current report/scorecard paths exist。

## Failure continuation

- failed predictor + continue policy；
- failed predictor + fail-session；
- failed selector + fixed fallback；
- unknown reservation retained；
- same logical call never retried；
- later distinct call allowed；
- checkpoint/restore keeps policy。

## Execution identity

- production rejects undeclared callback；
- changed declared weights/tokenizer/prompt/runtime rejected；
- test callback explicitly allowed；
- pending resolver identity unchanged。

## Outcome policy

- missing + value rejected；
- mature missing required provider fields rejected；
- bad chronology rejected；
- quality code not allowed rejected；
- same target/version conflict rejected；
- lead-time resolution mismatch rejected。

## Copy baselines

- static 4,916 attribution reconstructs saved counts；
- copy-current program emits state value exactly；
- copy-baseline emits latest baseline；
- continuous trajectory has own costs/times；
- persistent gains attributed correctly；
- no new model calls.

## Regression

- current 485 core；
- launch-bound；
- joint-analysis；
- visible-attribution；
- portable replay；
- lint；
- no skipped tests unless separately justified.

---

# 8. GPU / model Go-No-Go

## No-Go

禁止新模型调用，直到：

- current pointer fixed；
- copy-current continuous arm complete；
- failure policy explicit；
- outcome policies pass；
- H15 banks/process grouping frozen；
- confirmation protocol signed and hashed；
- old jobs marked consumed；
- exact new scope/call cap exists。

## First allowed model work

优先顺序：

1. unopened confirmation with one frozen model and strong program controls；
2. only after that, bounded X09 interface or D model pilot；
3. no new scale sweep；
4. no prompt search on confirmation；
5. no selective retries/replacements。

---

# 9. 论文主线应如何更新

当前最可信的论文故事不是：

> 大模型通过主动取证提高天气预测。

而是：

> DisasterTrace 构建了一个可审计的持续监测测量框架，能够把合法证据、共享预算、异步完成、预测数值来源和采纳协议分开；真实开发实验揭示，大模型会在部分证据下产生无依据确定性，并大量复制当前可见概率，且更多可判定证据不必然改善未来预测。

下一阶段需要证明：

1. copy controls 后是否仍有 predictor value；
2. active acquisition 能否减少部分证据错误；
3. 这些变化是否在独立过程成立；
4. action requirements 是否改变 information value，而不污染 weather belief；
5. 第二物理过程是否复现相同或不同规律。

这与“真实值班任务 + 实际分支对照 + 资料和处理联合选择”的方向一致，但必须以强基线和独立确认完成，而不是靠功能数量。

---

# 10. 每个 Codex 任务的完成模板

```markdown
# <TASK_ID> Completion

## Frozen Scope
- starting HEAD:
- reference remote:
- allowed operations:
- prohibited operations:
- consumed jobs protected:

## Source Changes
- files:
- schemas:
- backward compatibility:
- historical bytes unchanged:

## Red Evidence
- test nodes:
- commands:
- exits:
- logs:
- hashes:

## Green Evidence
- targeted:
- core:
- supplemental:
- portable replay:
- lint/type:
- skips:

## External Actions
- network:
- model calls:
- GPU:
- API:
- training:

## Result Boundaries
- supported claims:
- unsupported claims:
- negative results retained:

## Gate
- GO / NO-GO:
- next task:
```

---

# 11. 近期完成定义

首轮完成后，仓库应新增：

1. 最新 CURRENT_PHASE；
2. post-review audit bundle；
3. explicit failure continuation contract；
4. provider outcome policies；
5. production execution identity mode；
6. copy-current/copy-baseline predictors；
7. continuous copy control runs；
8. formal forecast value attribution；
9. updated scorecard with copy controls；
10. all tests and portable replay；
11. updated status/decisions/blockers；
12. explicit stop receipt showing zero model/GPU calls。

这仍不表示：

- LLM F gain；
- independent confirmation；
- D real benefit；
- X09 complete；
- MM complete；
- 16 hazard complete。

---

# 12. 最终推荐顺序

```text
V8-AUDIT-00
→ V8-HARDEN-01/02/03
→ V8-COPY-04 + V8-ATTR-05
→ V8-EVIDENCE-06
→ V8-H15-07 + V8-DATA-08
→ V8-CONFIRM-09
→ V8-TEMP-10
→ V8-D-11 + V8-CONCURRENCY-12
→ V8-X09-13
→ V8-MRMS-14 / V8-HEFS-15
→ V8-SHADOW-16
→ V8-FINALIZE-17
```

核心原则：

> 新模型调用不再用于寻找“会不会突然改对概率”，而只用于预先冻结、强基线无法替代、能够回答明确研究问题的实验。
