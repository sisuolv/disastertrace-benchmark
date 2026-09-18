---
title: DisasterTrace v9 最新实现复查与 Codex 后续执行计划
plan_version: "v9-post-pause-audit-20260914"
planning_date: "2026-09-14"
language: zh-CN
repository: "sisuolv/disastertrace-benchmark"
branch: "next-phase-v1"
reference_commit: "6f71c8799ff69439a18f645e63b8c966ca21eec4"
reference_parent: "5ed0fb94ae7bf235b37e7528e201b603271edffa"
current_phase: "PAUSED_FOR_USER_REVIEW"
review_scope: "current GitHub source, reports, receipts and tests; no independent private-repo checkout rerun in this review"
default_allow_network: false
default_allow_model_calls: false
default_allow_gpu: false
default_allow_paid_api: false
default_allow_training: false
supersedes:
  - "DisasterTrace_v8_Latest_Audit_and_Codex_Plan_20260914_CN.md"
  - "plans that still treat COPY controls, regional banks, DeepSeek E/F, or temperature full calendar as pending"
---

# DisasterTrace v9 最新实现复查与 Codex 后续执行计划

## 0. 可直接粘贴给 Codex 的首轮指令

```text
仓库：sisuolv/disastertrace-benchmark
分支：next-phase-v1
本计划复查时远端 HEAD：

6f71c8799ff69439a18f645e63b8c966ca21eec4

不要 reset、不要清理脏工作区、不要改写冻结结果。开始时先读取实际 HEAD；
如果分支已继续前进，先做差异审计，将本计划应用到真实最新状态。

必须先读：

1. disastertrace-starter/AGENTS.md
2. disastertrace-starter/CURRENT_PHASE.md
3. LATEST_PROGRESS_20260914_CN.md
4. plans/v9_followup_execution_20260914_01/README_CN.md
5. plans/v9_followup_execution_20260914_01/RUN_REPORT_CN.md
6. plans/v9_followup_execution_20260914_01/PAUSED_SUMMARY_CN.md
7. plans/v9_followup_execution_20260914_01/PAUSED_RESULT.json
8. plans/v9_followup_execution_20260914_01/BATCH_RESULT.json
9. plans/v9_followup_execution_20260914_01/EXECUTION_STATUS.json
10. plans/v9_followup_roadmap_20260914_01/RESEARCH_ROADMAP_CN.md
11. plans/v9_followup_execution_20260914_01/reports/api_forecast_audit_01/VALIDATION.json
12. plans/v9_followup_execution_20260914_01/reports/api_rare_forecast_audit_01/VALIDATION.json
13. plans/v9_followup_execution_20260914_01/reports/e_error_mechanisms_01/REPORT_CN.md
14. plans/v9_followup_execution_20260914_01/reports/regional_baselines_01/SUMMARY.json
15. plans/v9_followup_execution_20260914_01/reports/process_manifest_02/COVERAGE_REPORT_CN.md
16. plans/v9_followup_execution_20260914_01/reports/temperature_fullcalendar_audit_01/REPORT_CN.md
17. 本文件

首轮只执行 CPU/offline 工作：

V9R-00 统一机器可读最终状态、CURRENT_PHASE 和调用计数；
V9R-01 建立独立审计基线并重跑当前相关测试；
V9R-02 强化 API capture/ledger 的不可变事务与失败保全；
V9R-03 强制正式结果使用 provider-specific OutcomeResolutionPolicy；
V9R-04 强制正式执行使用 production-bound identity；
V9R-05 修正 branch intervention 的明确事件优先级；
V9R-06 将 forecast 数值来源归因升级为正式版本化 evaluator；
V9E-07 实现“模型逐槽判断＋程序确定性汇总”的 E pipeline 和离线重评分；
V9F-08 冻结 persistent/adoption 因子实验的 CPU/program preflight；
V9DATA-09 生成独立天气过程候选、purge 审计和 confirmation protocol 草案；
完成后停止。

首轮禁止：

- 网络请求；
- DeepSeek/API 调用；
- GPU；
- 训练；
- 打开 Bay 2025-02-17 至 02-23 的预留确认周；
- 重跑 E01、E02、F pilot、rare pilot；
- 修改任何原始 response、score、journal、checkpoint、budget 或 frozen source；
- 将 Denver 2025-01-09 outcome-selected 诊断并入普通总体结果；
- 将 persistent old-value 的收益写成新概率信息；
- 将 temperature program 结果写成 LLM 或 C1 跨过程收益；
- 将合成 D 写成真实防灾收益；
- 将 616 tests 写成整个历史仓库所有测试。

每个修复必须：

1. 先写在当前代码上失败的 red test；
2. 保存命令、退出码、JUnit、stdout/stderr 和 SHA256；
3. 保持历史冻结目录不变；
4. 更新 IMPLEMENTATION_STATUS / DECISIONS / BLOCKERS / CURRENT_PHASE；
5. 生成显式 STOP_RECEIPT，确认新模型调用=0、GPU=0、网络=0。
```

---

# 1. 本次复查的最新真实起点

## 1.1 当前分支与执行状态

当前 `next-phase-v1` 已进入 v9 暂停点，不再是上一轮 v8：

```text
HEAD = 6f71c8799ff69439a18f645e63b8c966ca21eec4
phase = PAUSED_FOR_USER_REVIEW
confirmation_opened = false
gpu_cards_in_use = 0
```

本轮已经实际完成：

- 616 项 monitoring 相关测试；
- 四地区 3,303 个 TAF/METAR 原生请求；
- 分离的 2024-12 fit 与 calibration；
- E02 1,008 个完整 API 回答及独立审计；
- 普通 F pilot 2,304 个 API 回答；
- outcome-selected rare diagnostic 384 个 API 回答；
- 2 个 compatibility calls；
- COPY_CURRENT / COPY_BASELINE 连续程序对照；
- 三地区、两日期、两阈值的 base-bound 连续开发会话；
- 24 个月温度完整日历、192 条程序轨迹、11,644 个机会；
- source / selector / predictor 本地串行跨进程恢复；
- provider-specific outcome policy 的初始实现；
- production-bound execution identity；
- failure continuation policy；
- 逐槽 E 错误分解；
- 预留确认周保持未打开。

## 1.2 本次复查的证据边界

本计划复查了当前 GitHub 源码、运行脚本、保存报告和机器回执，但没有在本对话环境独立
clone 私有仓库、展开所有大型归档并重跑 616 项测试。

因此，下文把发现分为：

- **确定性实现问题**：从当前源码或机器文件可以直接确认；
- **已验证设计边界**：代码有意只支持有限范围，不能扩大声称；
- **研究门槛**：工程正确，但数据/统计不足以支持论文结论；
- **待验证风险**：需要 Codex 新增反例，不能直接宣称旧结果错误。

---

# 2. 总体正确性判断

## 2.1 可以认为基本正确的范围

当前实现已经较可靠地完成：

1. 原生产品先按 issuance 选择当前版本，再判断目标窗口覆盖；
2. baseline、withdrawal、begin、completion、failure、cutoff 使用同一事件时钟；
3. measurement v2 事件批次先在副本执行，再整体提交；
4. 防止 reentrant event clock；
5. COPY_CURRENT 与 COPY_BASELINE 是正式 typed program predictor；
6. source、selector、predictor 分别计费和绑定身份；
7. unknown execution 保留 reservation，不当作免费失败；
8. production spool 绑定冻结源码、模型合同、请求、checkpoint、worker 和 response；
9. pending source/selector/predictor 的单个在途调用可以本地串行恢复；
10. failure continuation 已版本化为 `fail_session_v1` / `skip_failed_call_continue_v1`；
11. proposed、admitted、effective forecast 已分开；
12. typed auto-propose 的自动 OVERRIDE 已披露；
13. canonical outcome 和跨 lead 结果一致性已实现；
14. comparison invariants 与允许 intervention 已实现；
15. E-only 不进入 F 分数；
16. common baseline trace 在 arm 间一致；
17. regional fit/calibration/evaluation 使用时间角色和 purge；
18. raw B、f(B)、f(B,E) 已有静态发展结果；
19. E02 的逐槽参考由两个 reducer 一致核验；
20. Denver outcome-selected 诊断与自然日历分表；
21. temperature persistent 结果已正确解释为旧概率持续，而非新概率；
22. E01 AFS 失败和未决费用被保留，没有选择性替换单个失败。

## 2.2 当前还不能声称的能力

不能升级为以下表述：

- 任意并发 pending；
- 任意远端 exactly-once；
- 真实历史 first-public availability；
- DeepSeek 产生了新的有效 F 信息；
- LLM selector 在普通自然日历稳定优于程序策略；
- 235B、DeepSeek 或更大模型一般性更强；
- 一个地区的数千机会是独立天气过程；
- Denver positive diagnostic 是总体收益；
- f(B,E) 是同预算在线策略；
- temperature 已证明主动取证收益；
- D 已形成 acquisition/prediction/action 完整反馈；
- MRMS/HEFS 已形成合格物理 F；
- X09 已实际运行；
- prospective source capture 等于 prospective forecast evaluation；
- 16 类灾害已完成。

---

# 3. 最新结果应该如何解释

## 3.1 E：逐槽理解已经很强，最终逻辑汇总仍可能失败

E02 是 42 个底层问题生成的相依视图，不是 1,008 个独立事实问题。

关键结果：

```text
DeepSeek Flash
  full/direct:     114/126
  full/slotwise:   125/126
  focused/direct:  109/126
  focused/slotwise:126/126

DeepSeek v4 Pro
  full/direct:      85/126
  full/slotwise:   106/126
  focused/direct:   84/126
  focused/slotwise:101/126
```

进一步分解表明：

- Flash focused/slotwise：全部槽和最终聚合都对；
- Pro focused/slotwise：126/126 槽判断正确，但 25 个最终聚合错误；
- Pro full/slotwise：124/126 槽全对，但 18 个聚合错误。

最重要的机制发现是：

> 模型可能已经正确理解每个可见槽，却在简单的 existential/conflict 汇总规则上失败。

因此下一步不应继续调大模型或加解释长度，而应正式比较：

```text
direct model E
model slotwise + model aggregate
model slotwise + deterministic aggregate
deterministic native reducer
always-unknown
```

离线程序汇总不能回写为原模型分数，但可以成为新的、预登记的 pipeline。

## 3.2 F：普通自然日历没有观察到 LLM predictor 增益

普通 pilot 的 aggregate 结果：

```text
1000m:
  FOLLOW/COPY/DeepSeek batch predictor ≈ 0.003527
  batch program / LLM-selector-program 更差
  positive = 0

5000m:
  FOLLOW/COPY/DeepSeek batch predictor ≈ 0.064305
  batch program / LLM-selector-program 更差
  positive opportunities = 47
```

DeepSeek predictor 大多数概率等于 visible current 或 baseline。部分 v4 Pro 输出存在极小数值差，
但都在 1e-6 内，不产生可辨认 Brier 改善。

因此：

- 不再继续“换一个模型看会不会改概率”；
- 需要 exact value-source taxonomy；
- 需要 persistent/adoption 因子；
- 需要把 E pipeline 与一个明确、可校准的 F mapping 接通；
- 需要独立天气过程，而不是增加调用次数。

## 3.3 Denver positive diagnostic 只能作机制诊断

Denver 2025-01-09 是依据 outcome 已知正例后选择的开发日：

- 1000m：3 positives；
- 5000m：11 positives。

结果中，`LLM selector + program predictor` 与 batch/coverage program 有小幅改善；
LLM batch predictor 仍等于 FOLLOW。

正确结论是：

> 在这个 outcome-selected 暴露日上，某些程序概率映射受资料选择影响，LLM selector
> 选择的资料路径可能改变损失。

不能写成：

- LLM 在严重事件总体上有效；
- LLM predictor 改善 F；
- Denver 是 independent confirmation；
- selector improvement 可迁移到其他过程。

## 3.4 Regional baseline：5km 有发展信号，1km 缺少支持

静态 fixed-evidence 结果显示：

- 5km 的 f(B) 在四地区 development slices 中优于 B；
- f(B,E) 只在 Chicago / Denver 进一步改善；
- Bay / New York 的 f(B,E) 反而变差；
- 1km 在 Bay/NY/Chicago evaluation 为 0 positives，PAV 多数变差；
- Denver 1km 只有 3 positives。

这支持：

- 区域化和 calibration 必须做；
- E 增加不保证 F 改善；
- 不可用 1km Brier 排名作为罕见事件能力证据；
- f(B,E) 是 fixed full legal evidence，不是 same-budget dynamic selector；
- calibration 结果仍是 development，不是 confirmation。

## 3.5 Temperature：第二类型闭环已经形成，但还是 program-only

温度完整日历已经有更实质的正例支持：

- 24 月；
- 192 轨迹；
- 11,644 opportunities；
- 3,645 unique targets；
- frost/hot/ice day 和 3-day spell；
- 0 model calls。

Persistent COPY_CURRENT / first-issue-hold：

- 在 ice spell / ice day 上可改善；
- 在 hot spell / frost / hot day 上可恶化；
- 改变来自旧概率持续，不是产生新概率。

这使 temperature 成为当前最成熟的第二过程候选，但下一步仍需：

- process/month grouping；
- calibration；
- legal supplementary evidence；
- same-budget acquisition；
- model only after strong program controls；
- final extreme definitions；
- independent confirmation。

---

# 4. 发现清单：P0 / P1 / P2

# P0：继续任何新模型/API/确认实验前必须处理

## P0-01：机器可读状态互相矛盾

### 确定性问题

`EXECUTION_STATUS.json` 仍包含：

```text
N4 = ordinary_F_running...
new_model_calls = null
benchmark_model_calls = null
```

但 `PAUSED_RESULT.json` / `BATCH_RESULT.json` 已明确：

```text
all_registered_work_verified = true
ordinary F complete
rare complete
temperature complete
phase = PAUSED_FOR_USER_REVIEW
```

`CURRENT_PHASE.md` 的顶部已经是 v9，但正文仍夹有 “F is running” 和旧温度 64-trajectory 状态。

### 风险

Codex 或状态 watcher 可能：

- 误认为当前批次仍在运行；
- 重启已消费任务；
- 无法计算准确调用总数；
- 选择较旧状态覆盖最终状态。

### 修复

新增一个唯一 canonical finalizer：

```text
CANONICAL_STATUS.json
CANONICAL_STATUS_CN.md
```

字段至少：

```text
reference_commit
phase
registered_tasks
platform_jobs
logical_tasks
http_dispatches
provider_responses
valid_responses
scored_responses
compatibility_calls
pre_dispatch_failures
post_dispatch_unknown
unresolved_reservations
program_trajectories
model_trajectories
confirmation_opened
consumed_launchers
next_allowed_task
```

`CURRENT_PHASE.md` 只引用 canonical status，不再复制易过期的运行文字。

### 测试

- RUNNING 与 all_registered_work_verified 不能同时成立；
- null count 不允许出现在 terminal phase；
- 所有 count 可由 immutable receipts 重算；
- consumed launcher 不可成为 next action。

---

## P0-02：API 费用账本仍依赖共享可变 AFS JSON＋全局文件锁

### 当前事实

E01 的 AFS lock 问题留下：

- 876 settled；
- 49 reserved；
- 13 unknown；
- unresolved reservation 约 1.69 USD。

E02 使用新的完整 namespace 和更长 lock wait 成功，结果可信；但架构仍依赖：

```text
BUDGET.json
+ 一个共享 lock
+ 每次更新整个 JSON
```

### 风险

更大的并发批次仍可能：

- AFS `flock` EAGAIN；
- response 已落盘、billing update 失败；
- unknown 标记也因同一 lock 失败；
- terminal status 不一致；
- 全局 ledger 成为吞吐瓶颈。

### 修复

实现 append-only / per-call immutable API ledger：

```text
api_ledger/
  contract.json
  attempts/<call_id>/reserve.json
  attempts/<call_id>/dispatch.json
  attempts/<call_id>/response.raw
  attempts/<call_id>/response.json
  attempts/<call_id>/billing.json
  attempts/<call_id>/score.json
  attempts/<call_id>/terminal.json
```

最终由 deterministic reducer 汇总预算。

要求：

- 同一 call_id immutable；
- reserve 前先验证 model/input/cap；
- response raw 在 decode 和 billing 前 fsync；
- billing 失败不丢 response；
- HTTP error body 也保存并 redaction；
- pre-dispatch / post-dispatch / response-received / billed / scored 分开；
- E01 只做 reconciliation，不纳入 E02 分数；
- E02/F/rare 历史字节不变。

---

## P0-03：provider-specific outcome policy 仍是可选字段

### 当前实现

`OutcomeRegistry` 只有在 record 含 `resolution_policy` 时才调用 provider validation。

当前正式 H15 pilot 在脚本中主动注入：

```text
resolution_policy = h15_routine_archive.v1
```

但 generic formal scoring 仍可以注册一个没有 provider policy 的真实 outcome。

### 风险

后续 MRMS / temperature / HEFS 可能绕过：

- maturity fields；
- chronology；
- quality codes；
- reference kind；
- physical settlement policy。

### 修复

新增 registry mode：

```text
registry_mode:
  legacy_compatible
  formal_provider_bound
```

formal mode 必须有：

```text
resolution_policy
provider
provider_version
reference_kind
quality_status
availability_basis
```

先完成 H15、DWD daily temperature；MRMS/HEFS 保持 blocked。

非 mature 状态也要有明确规则：

- missing 必须 value=null；
- provisional 不可在另一 lead 伪装 mature；
- transition version 化；
- provider-specific required times；
- quality code allowlist。

---

## P0-04：production-bound 执行仍是 opt-in

### 当前实现

`execution_mode` 默认仍为 legacy；正式 pilot 显式设置 `production_bound_v1`。

### 风险

新脚本遗漏配置时可能退回较弱 callback identity，而未立即失败。

### 修复

建立两个入口：

```text
run_formal_session(...)
run_test_session(...)
```

正式入口强制：

```text
execution_mode = production_bound_v1
pending_timing_policy = lifecycle_wall_v1
provider-bound outcome
frozen source manifest
comparison contract
```

legacy 仅允许：

- historical replay；
- tests；
- synthetic fixtures。

---

## P0-05：forecast “新数值”分类仍存在阈值混淆

当前报告同时使用：

- exact equality；
- within 1e-6；
- within 0.005；
- more_than_0.005；
- new_vs_visible_current_and_baseline。

小数舍入可能被计为 “new_vs” 但不改变损失。

### 修复

新增正式 evaluator `forecast_value_provenance.v2`：

```text
proposal_exact_class:
  exact_current
  exact_latest_baseline
  exact_other_visible_value
  exact_program_mapping
  numerically_distinct

absolute_delta_current
absolute_delta_baseline
ulp_distance
loss_delta
effective_at_cutoff
adoption_source
gain_source:
  new_numeric
  state_persistence
  baseline_update
  adoption
  fallback
  timing
```

0.005 只能作为 sensitivity threshold，不得成为“新信息”的定义。

---

## P0-06：branch intervention 与下一事件的顺序仍应显式化

当前 branch intervention 与 begin 等动作处于相同 phase，实际多依赖 event ID 排序。

### 风险

某些自定义 event ID 下，恢复后的第一项 begin 可能先于 intervention。

### 修复

给 `policy_intervention` 独立 precedence：

```text
baseline/completion/cancel
seal
policy_intervention
selector/acquire/begin/prepare
```

新增任意 event ID、同时间、restore/branch regression。

当前已发布分支若没有该碰撞，不应被改写为失败；这是前瞻健壮性修复。

---

# P1：打开 confirmation 或完成行动反馈前处理

## P1-01：当前依赖块不是独立天气过程

`process_components` 使用：

```text
完整输入/结果时间包络
+ 72h gap
+ shared native version union
```

这是保守 dependence block；连续日历常被合并成一个 block。

因此当前每地区 development/calibration/evaluation 基本只有一个块，无法估计：

- process-level variance；
- confidence interval；
- effective sample size；
- cross-process stability。

### 后续

新增 externally grounded process manifest：

```text
synoptic_process_id
front/cyclone/event source
start/end
region
stations
input lookback
outcome window
purge
manual rule version
automatic source
```

若无法可靠识别天气系统，至少使用预注册的 week/block unit，并做：

- 72h；
- 7d；
- region-week；
- leave-one-process-out sensitivity。

不能用 opportunity bootstrap 作为主不确定性。

---

## P1-02：regional baseline split 的核心实现合理，但需更强的不可泄漏审计

当前优点：

- fit/calibration/evaluation 的完整 footprint 必须落在一个 role；
- native TAF version 不允许跨 role；
- fit 与 calibration IDs 分离；
- confirmation 周被显式排除。

仍应补：

- target contract overlap；
- query/result asset overlap；
- source raw SHA overlap；
- station-time window overlap；
- neighbor report reuse；
- calibration/evaluation bank hash freeze；
- script hash freeze；
- post-result bank selection prohibition。

生成：

```text
SPLIT_NONLEAKAGE_AUDIT.json
BANK_FREEZE.json
```

---

## P1-03：E 的最佳下一步是“逐槽模型＋程序汇总”，不是更多 direct prompts

### 新 pipeline

```text
E0 always_unknown
E1 native deterministic reducer
E2 model direct
E3 model slotwise + model aggregate
E4 model slotwise + deterministic aggregate
E5 model slotwise + deterministic aggregate + calibrated confidence
```

公平条件：

- 同一原生输入；
- 同一 query universe；
- 同一 slot definition；
- same max total output tokens；
- all invalid/missing retained；
- no evaluator reference in prompt；
- 42 underlying problems / process units separately reported。

### 主要研究问题

1. 模型是否能逐槽读懂原生报告？
2. 错误来自 perception、slot judgment 还是 logical aggregation？
3. 程序汇总是否稳定提高 E？
4. 更正确的 E 是否能改变 f(B,E) 或行动，而不是只提高事实分数？

---

## P1-04：普通 F pilot 只有 base-bound，必须补 persistent/adoption 因子

当前 COPY_CURRENT 在 base-bound 下与 FOLLOW 等价是预期结果。

下一轮 CPU/program 先做：

```text
protocol:
  base_bound_override
  persistent_override

candidate:
  copy_current
  copy_baseline
  first_issue_hold
  f(B)
  f(B,E)

adoption:
  auto_override
  follow
  threshold_adopt
  loss-limited_adopt
```

先不要调用模型。

目的：

- 区分候选数值价值；
- 区分旧值持续；
- 区分 adoption；
- 防止把 persistent gain 归因给 predictor。

模型 adoption 只有在 program baselines 成熟后再加。

---

## P1-05：当前只支持一个 pending invocation

当前对 H15 串行恢复足够，但无法研究：

- 查询与准备并行；
- 多 source 并行；
- source + processor；
- 多目标异步工具。

行动实验前实现有界 `session_inflight_set.v6`：

```text
pending_attempts[]
dependency_edges
resource_reservations
completion_order
max_concurrency
cutoff visibility
```

首版只支持：

- source + preparation；
- two independent sources；
- source + deterministic processor。

不必立即支持任意模型并发。

---

## P1-06：API HTTP error 原文和 post-response 状态应更完整保留

当前 success raw body 先于 billing 保存，这是正确的。

仍需：

- HTTPError body 写入 immutable raw file，而不只 hash；
- redaction 后 failure view；
- billing update failure 单列；
- response exists but score absent 单列；
- orphan capture directory audit；
- budget settlement after response 的 deterministic recovery。

---

# P2：研究与论文门槛

1. E02 只有 42 underlying opportunities；
2. 多 representation/condition/reasoning 是依赖视图；
3. ordinary F 的 1km 多数区域 0 positives；
4. ordinary F 只有三地区 × 两日期；
5. Denver rare diagnostic outcome-selected；
6. regional calibration 仍是 development；
7. B 是 research frequency map，不是官方概率；
8. f(B,E) 是 full fixed evidence，不是 same-budget dynamic policy；
9. DeepSeek provider exact weights/compute unknown；
10. API timing 是 client delivery，不是 provider compute；
11. current F model primarily copies visible probability；
12. typed_auto_propose 自动 adoption；
13. temperature program-only；
14. synthetic D 不是真实损失；
15. source-only shadow 不是 forecast shadow；
16. confirmation unopened；
17. full 16-hazard release incomplete。

---

# 5. 结果驱动后的研究主线

当前最可信的主线不是：

> LLM 主动取证能够提高天气预测。

而是：

> DisasterTrace 提供一个可审计的持续监测环境，能够分离证据获取、原生产品理解、逻辑汇总、
> 概率转换、状态持续和采纳协议。真实开发实验发现：模型常能读懂逐槽资料，却可能在汇总时
> 出错；即使 E 更确定，也不必改善 F；模型预测器又常复制当前可见概率。

下一阶段需要把这条负结果推进为三个可检验问题：

1. `slotwise model + deterministic aggregate` 能否稳定解决 E？
2. 修复后的 E 是否能通过一个明确的 f(B,E) 改善独立过程 F？
3. 即使 F 改善有限，这些资料是否能在准备窗口尚未关闭时改善行动？

最终 novelty 仍应收敛到：

- 真实持续监测任务；
- 同状态、真实路径分支归因；
- 行动需要决定信息价值；
- 第二物理过程与独立确认。

---

# 6. Codex 详细工作包

## V9R-00：最终状态单一事实源

### 修改

- 重写 `CURRENT_PHASE.md` 为短 pointer；
- 生成 canonical status；
- 将旧 running 状态归档；
- 统一调用口径。

### 调用计数必须拆分

```text
registered_logical_tasks
capture_attempts
pre_dispatch_failures
http_requests_sent
provider_responses_received
valid_json_responses
scored_responses
compatibility_calls
unknown_after_dispatch
unresolved_reservations
```

不要再使用一个含义不清的 `new_model_calls`。

### 验收

所有字段可从 immutable files 重算；机器状态无矛盾。

---

## V9R-01：独立测试基线

### 运行

- 当前 monitoring suite；
- v9 plan-specific tests；
- portable replay；
- regional split audit；
- E02/F/rare offline audit；
- temperature audit；
- lint/type。

### 输出

```text
POSTREVIEW_TEST_MATRIX.json
POSTREVIEW_TEST_MATRIX_CN.md
```

明确：

- 616 的组成；
- 新增测试；
- 不重复累加历史 test runs；
- skips；
- fixture availability。

---

## V9R-02：不可变 API ledger

### 新模块建议

```text
monitoring_v1/api_ledger.py
monitoring_v1/api_capture_v2.py
```

### 状态

```text
REGISTERED
RESERVED
DISPATCHED
RESPONSE_PERSISTED
DECODED
BILLED
SCORED
FAILED_PRE_DISPATCH
FAILED_POST_DISPATCH
UNKNOWN
RECONCILED
```

### 压力测试

- AFS lock unavailable；
- response before billing failure；
- HTTP 429/500 body；
- invalid UTF-8；
- JSON invalid；
- process killed after response fsync；
- duplicate reducer；
- budget overrun；
- same call ID different request；
- E01 import/reconciliation。

---

## V9R-03：formal provider-bound outcomes

### 新接口

```text
OutcomeRegistry(mode="formal_provider_bound")
```

### H15

要求：

- routine/native report identity；
- physical slot；
- valid source SHA；
- mature quality allowlist；
- publication/fetched/resolved policy；
- missing/provisional rules。

### Temperature

要求：

- DWD daily product identity；
- 00–24 UTC support；
- mx2t6/mn2t6 candidate lineage；
- complete future day；
- day0 exclusion；
- outside-reference status；
- member-trajectory duration event。

---

## V9R-04：正式执行入口

新增：

```text
formal_session.py
```

强制：

- production-bound identity；
- lifecycle wall timing；
- frozen files；
- provider outcome policy；
- comparison contract；
- budget contract；
- no hidden outcomes；
- STOP receipt。

---

## V9R-05：branch ordering

将 intervention phase 独立，新增：

- arbitrary event IDs；
- same timestamp；
- branch before selector；
- branch before predictor begin；
- parent hash；
- no free budget/cache reset。

---

## V9R-06：forecast value provenance v2

### 输出每个 opportunity

```text
dispatch_current
dispatch_baseline
proposal
admitted
effective_at_cutoff
exact_class
delta_current
delta_baseline
loss_follow
loss_method
gain_source
```

### 汇总

```text
novel_numeric_count
copy_current_count
copy_baseline_count
persistence_only_gain
adoption_only_gain
baseline_update_gain
timing_gain
fallback_gain
```

所有 aggregate 可回溯到完整机会。

---

## V9E-07：逐槽 E＋程序汇总

### 阶段 A：离线复用 E02

- 不调用模型；
- 用已保存 slot outputs；
- 程序 aggregate；
- 产生 derived pipeline score；
- 清楚标注不是原模型分数。

### 阶段 B：新开发冻结

只有 A 通过后，冻结一个小型新开发批次：

- direct；
- slotwise-model-aggregate；
- slotwise-program-aggregate；
- native reducer；
- always unknown；
- equal total output budget。

### 阶段 C：接入 F

把 E4 的程序汇总作为结构化特征输入同一个 frozen f(B,E)：

```text
F0 B
F1 f(B)
F2 f(B, native E)
F3 f(B, model-slotwise-program-aggregate E)
```

先 program，后模型。

---

## V9F-08：persistent × adoption CPU factorial

### 数据

使用已暴露 development calendars，不打开 confirmation。

### Arms

```text
FOLLOW
COPY_CURRENT
COPY_BASELINE
FIRST_ISSUE_HOLD
f(B)
f(B,E)
```

×：

```text
base_bound
persistent
```

×：

```text
auto_override
threshold_adopt
loss_limited_adopt
```

### 报告

- full calendar；
- positive strata；
- exact value provenance；
- help/harm；
- churn；
- stale override duration；
- effective lead time；
- costs。

---

## V9DATA-09：process units 与 confirmation protocol

### process units

建立两层：

1. conservative temporal/asset block；
2. externally defined meteorological process。

无法自动识别时，使用预注册 region-week unit，不声称 synoptic independence。

### confirmation protocol

生成但暂不打开数据：

```text
CONFIRMATION_PROTOCOL.json
CONFIRMATION_PROTOCOL_CN.md
CONFIRMATION_FREEZE_MANIFEST.json
```

冻结：

- code commit；
- banks；
- models；
- prompts；
- E pipeline；
- F mapping；
- protocols；
- adoption；
- budgets；
- process unit；
- purge；
- metrics；
- missingness；
- stop rule；
- retry policy；
- call cap。

---

## V9CONF-10：一个有界独立确认

仅在 V9R-00 至 V9DATA-09 通过后执行。

优先使用未打开的 Bay 2025-02-17–23，但在打开前确认：

- 与 fit/cal/eval 完整 footprint 不重叠；
- native/source/query SHA 不共享；
- process unit 足够；
- positive support 预期不作为选日依据；
- underpowered 也停止，不追加 outcome-selected 日期。

模型矩阵只保留：

```text
strong program
one frozen small model
one frozen larger model（仅在研究问题需要）
```

不再做 scale sweep。

---

## V9TEMP-11：温度 program 基线与 evidence value

### 先做 CPU

```text
B ensemble frequency
f(B) calibrated
COPY controls
persistent/adoption
```

### 补充证据

只选择与决策时点合法相关的来源，例如：

- 近期观测；
- 新一轮集合起报；
- station QC/product revision；
- 不使用未来 daily outcome。

### 分组

按月份、冷/暖过程或预注册 week block；多 lead 共享 outcome。

### 模型 Go 条件

只有 program `f(B,E)` 在多个 development blocks 有可解释价值，才加入一个模型。

---

## V9ACTION-12：最小行动环境

这一步直接落实“行动需要决定信息价值”。

### Scenario card

必须写清：

```text
user
asset/facility
weather target
preparation duration
capacity
cost
cleanup/cancel cost
reversibility
decision deadline
research assumptions
operationally sourced rules
```

第一版用机场低能见度或 temperature facility protection 做工程验证，不称真实业务规则。

### 三组件隔离

```text
Weather F:
  不接收 miss penalty / action cost / preference

Acquisition policy:
  可看到剩余准备可行性和 DecisionSpec

D policy:
  读取 admitted F + preparation state + DecisionSpec
```

### 配对

同天气、同资料、同 F，只改变：

- duration；
- capacity；
- cost；
- cleanup；
- miss penalty；
- deadline。

检查 F hash/output 不因 preference 改变。

---

## V9ACTION-13：action-aware acquisition 与多 pending

先实现有界并发：

```text
source + preparation
two independent sources
source + deterministic processor
```

然后比较：

```text
all-read
fixed schedule
event trigger
decision-aware one-step
decision-aware two-step
LLM selector
```

目标：

- 已来不及改变的目标停止昂贵查询；
- 长准备目标更早行动；
- 短准备目标可等待；
- 查询与准备可并行；
- 资源紧张时优先减少会改变分配的不确定性。

只报告固定 DecisionSpec 下的 synthetic loss。

---

## V9X09-14：联合目标同预算

低于 confirmation、temperature 和 action 优先级。

新冻结必须有两种条件：

```text
same per-request output cap
same per-group total output budget
```

并加入：

- copy-current；
- deterministic per-target；
- model slotwise + program aggregation；
- invalid group response retains all targets；
- per-target cost；
- group wall time。

---

## V9MM-15：MRMS / HEFS 物理准入

### MRMS

先证明：

- accumulation start/end；
- valid/issue/available time；
- missing/no coverage；
- grid support；
- matched forecast/outcome；
- first-seen policy。

之后比较同一 raw asset 的：

- numerical product；
- professional nowcast；
- structured feature；
- image/VLM。

### HEFS

免费完整专业 forecast 是 common information，不计 acquisition gain。

核准：

- QINE member；
- instant/hourly average；
- regulation；
- cross-section；
- units；
- flow/stage；
- threshold；
- outcome reference；
- availability。

---

## V9SHADOW-16：prospective forecast shadow

现有 source-only capture 保留。

下一步先运行：

- FOLLOW；
- f(B)；
- f(B,E) program；
- copy controls。

要求预测先提交、结果后成熟。程序稳定后再加入一个 frozen model。

不向公众发布，不控制设备。

---

# 7. Go / No-Go

## 新 API/模型调用 No-Go，直到

- canonical status 自洽；
- API ledger v2 通过故障测试；
- formal provider outcome 强制；
- exact value provenance 完成；
- slotwise+program aggregate 离线结果完成；
- persistent/adoption preflight 完成；
- confirmation protocol 冻结；
- consumed launches 全部锁定。

## Confirmation Go

- 未打开数据的 hash/URL/time range 已冻结；
- process unit 与 purge 完成；
- primary metrics 和 stop rule 完成；
- banks/prompts/models frozen；
- no outcome-based extension；
- underpowered 也按规则停止。

## Action model Go

- F preference-blind tests 通过；
- scenario card 审核；
- exact optimizer/program baselines；
- source+preparation concurrency 通过；
- synthetic scope 明确。

---

# 8. 建议的近期优先级

```text
1. V9R-00 状态一致性
2. V9R-02 API immutable ledger
3. V9R-03/04 formal outcome + formal execution
4. V9R-06 exact forecast provenance
5. V9E-07 slotwise + program aggregate
6. V9F-08 persistent/adoption factorial
7. V9DATA-09 process units + confirmation freeze
8. V9CONF-10 one bounded confirmation
9. V9TEMP-11 temperature evidence value
10. V9ACTION-12/13 action-aware information value
11. V9X09-14
12. V9MM-15
13. V9SHADOW-16
```

---

# 9. 当前论文故事的准确版本

## 当前已经有证据支持

> DisasterTrace 建立了一个可审计的持续监测测量环境，能够把原生证据获取、事实支持、
> 逻辑汇总、概率转换、状态持续和采纳协议分开。开发实验发现，模型即使能正确理解逐槽资料，
> 也可能在最终汇总时失败；更多可判定证据不保证更好的未来概率；模型 predictor 又常直接
> 复制当前可见概率。

## 仍需完成后才能成为主贡献

> 当逐槽事实被可靠汇总、强 program baseline 和 independent process 都固定后，主动取证是否
> 能真正改善未来 F；以及在准备时间、共享资源和撤销成本存在时，行动需要是否会改变一份
> 信息的价值，而不污染天气概率判断。

## 不应使用的表述

- “LLM 已经提升极端天气预报”；
- “Denver 证明 selector 有一般收益”；
- “616 tests 证明 scientific novelty”；
- “f(B,E) 是在线 Agent 上界”；
- “temperature 已经验证跨灾种 C1”；
- “合成 D 等于真实防灾效果”；
- “16 类已经完成”。

---

# 10. Codex 任务完成模板

```markdown
# <TASK_ID> Completion

## Frozen Scope
- starting HEAD:
- remote HEAD:
- dirty/index state:
- consumed launches:
- allowed:
- prohibited:

## Changes
- source files:
- schemas:
- migration:
- historical frozen bytes:

## Red Tests
- nodes:
- commands:
- exits:
- receipts:
- hashes:

## Green Tests
- targeted:
- monitoring suite:
- plan-specific:
- portable replay:
- lint/type:
- skips:

## Data/Model Actions
- network:
- model calls:
- API calls:
- GPU:
- training:
- confirmation opened:

## Findings
- fixed:
- remaining engineering:
- remaining scientific:
- claims changed:

## Gate
- GO / NO-GO:
- next task:
```

---

# 11. 第一批完成定义

首轮 CPU/offline 批次完成时必须交付：

1. canonical final status；
2. current pointer；
3. exact call-accounting report；
4. API ledger v2 red/green tests；
5. HTTP error body preservation；
6. provider-bound outcome formal mode；
7. formal production entrypoint；
8. branch ordering fix；
9. forecast provenance v2；
10. E02 slotwise+program aggregate derived report；
11. persistent/adoption freeze；
12. split nonleakage audit；
13. confirmation protocol draft；
14. updated status/decisions/blockers；
15. STOP_RECEIPT with zero new external actions。

完成这些仍不表示：

- independent confirmation；
- LLM F gain；
- real action benefit；
- MM/Hydro completion；
- 16-hazard release。
