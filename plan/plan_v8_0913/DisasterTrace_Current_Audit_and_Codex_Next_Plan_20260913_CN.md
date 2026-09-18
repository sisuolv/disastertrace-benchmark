---
title: DisasterTrace 当前实现复查与 Codex 后续执行计划
plan_version: "2.0-current-audit"
planning_date: "2026-09-13"
language: zh-CN
repository: "sisuolv/disastertrace-benchmark"
reference_branch: "next-phase-v1"
reference_commit: "6c7c7e81ad88e1d3a553727607e24c858136899d"
supersedes: "DisasterTrace_Monitoring_Mission_Codex_Plan_20260913_CN.md based on 60ebd057"
audit_type: "source_and_receipt_review; independent full test rerun pending"
immediate_execution_scope: "DT-AUDIT-00 through DT-CP04B-03; CPU/offline only"
default_allow_network: false
default_allow_model_calls: false
default_allow_gpu: false
default_allow_training: false
default_allow_paid_api: false
---

# DisasterTrace 当前实现复查与 Codex 后续执行计划

## 0. 直接交给 Codex 的首轮执行指令

```text
你正在处理私有仓库 sisuolv/disastertrace-benchmark，目标分支 next-phase-v1。
本计划复查时的远端提交为：

6c7c7e81ad88e1d3a553727607e24c858136899d

开始前必须：

1. 读取并遵守 disastertrace-starter/AGENTS.md。
2. 读取仓库根 README.md、LATEST_PROGRESS_20260913_CN.md。
3. 读取：
   - plans/v7_adaptive_execution_20260913/FINAL_REPORT_CN.md
   - plans/v7_adaptive_execution_20260913/NEXT_EXECUTION_CN.md
   - plans/v7_adaptive_execution_20260913/VALIDATION.json
   - plans/v7_next_20260913_2/OVERALL_PLAN_CN.md
   - disastertrace-starter/IMPLEMENTATION_STATUS.md
   - disastertrace-starter/DECISIONS.md
   - disastertrace-starter/BLOCKERS.md
   - disastertrace-starter/CURRENT_PHASE.md
   - 本文件
4. 记录实际 HEAD、工作区状态和上述文件 SHA256。若 HEAD 已前进，不要 reset；
   先比较差异，将本计划应用到真实最新状态。
5. 不重新运行任何已经消费的 GPU/API 目录，不替换历史失败回答，不修改冻结结果。
6. 首轮禁止联网下载、模型调用、GPU、训练、付费 API 和人工逐题标注。

首轮只执行：

- DT-AUDIT-00：修正当前事实入口，建立机器可读审计清单；
- DT-AUDIT-01：为本计划列出的确定性风险先写失败回归测试；
- DT-CP04B-01：定义在途查询/模型调用/资源预留的版本化状态合同；
- DT-CP04B-02：实现异常安全、可恢复的资源预约—执行—持久化—提交事务；
- DT-CP04B-03：绑定模型/执行器合同，并区分“相同策略恢复”和“显式干预分支”。

不要新建第二套 session clock，不要重写 monitoring_v1、monitoring_fixed_v1 的历史语义，
不要立即创建一个平行的 monitoring_mission_v1 调度引擎。继续使用现有 SessionCoordinator、
run_clock、AdmissionEngine、BudgetLedger 和 PreparationReducer，以版本化扩展实现所需能力。

执行规则：

- 每个修复必须先有能够在当前代码上失败的非平凡测试。
- 保存 red/green 命令、退出码、JUnit、stdout/stderr 和源码哈希。
- 异常、超限、超时、取消、重复完成和进程中断都必须生成持久化 attempt 记录；
  不得因 Python 异常留下不可解释的 reservation。
- 恢复同一策略时必须验证 backend contract hash；故意切换模型或策略必须记录为
  branch intervention，不能冒充 uninterrupted continuation。
- 继承缓存和获取费用只结算一次；重复完成、重复提交和恢复重放必须幂等。
- 完成 DT-CP04B-03 后运行已有相关回归和完整可承受测试，生成验收报告，然后停止。
  不自动进入新数据下载、432 机会模型矩阵、LLM selector 或 D-sim 模型运行。
```

---

## 1. 本次复查范围、证据与结论边界

### 1.1 复查对象

本计划以 `next-phase-v1` 的提交
`6c7c7e81ad88e1d3a553727607e24c858136899d` 为参考，重点检查：

- `monitoring_v1/event_loop.py`
- `monitoring_v1/policies.py`
- `monitoring_v1/resources.py`
- `monitoring_v1/session_checkpoint.py`
- `monitoring_v1/preparation.py`
- `monitoring_v1/support.py`
- `monitoring_v1/reachability.py`
- `monitoring_v1/views.py`
- `monitoring_fixed_v1/contracts.py`
- `monitoring_fixed_v1/admission.py`
- `monitoring_fixed_v1/adaptive.py`
- `monitoring_fixed_v1/heads.py`
- `monitoring_fixed_v1/representations.py`
- `monitoring_fixed_v1/support_bridge.py`
- `monitoring_fixed_v1/taf_tasks.py`
- `monitoring_v1/providers/aviation.py`
- 最新执行报告、验证回执、阻塞和决策记录。

### 1.2 已有验证证据

仓库保存的 `VALIDATION.json` 声明：

- 313 项相关测试通过；
- 0 errors、0 failures、0 skips；
- Ruff 通过；
- 网络禁用的 portable replay 通过；
- 36 份类型化日志、8 条控制器分支、252 次新捕获和 108 次旧捕获可重放；
- 没有新推理、没有模型权重依赖；
- 97 次新来源请求全部成功；
- 3 个 GPU 作业完成；
- 仍无独立确认，也没有新增完整灾种准入。

本次复查读取了 GitHub 当前源代码和上述回执，但没有在本对话运行环境中独立解包并重跑
完整 313 项套件。因此，本文属于**代码级静态审查＋保存回执复核**；Codex 的第一项任务
仍应在实际开发环境中重跑基线，并把新的独立命令记录下来。

### 1.3 总体判断

当前实现可以被判断为：

> **对于 H15 航空低能见度的有界开发实验，类型化输入、合法证据、截止封存、完整机会分母、
> 静止点跨进程恢复和离线重放基本正确；但它还不是完整的异步、多目标、跨灾种监测执行器。**

现有工程结果没有被本次复查发现的缺陷推翻：

- E-only 不会偷偷提交 F；
- 模型开始、完成、持久化和截止没有被压成同一时间；
- 晚到回答不会修改已经封存的机会；
- 获取证据需绑定实际已结算的 receipt 和 entitlement；
- 相同机会集合和共同结果掩膜被强制保留；
- 产品事实 E 与未来物理天气 F 被分开；
- TAF 覆盖和版本任务没有被当作未来天气预测；
- 负结果被保留。

但是，下列能力仍不能声称已经完成：

- 在途查询和模型任务的恢复；
- 异常、超时、崩溃后的事务一致性；
- 完整 D/preparation 状态分支；
- 执行器/模型身份绑定的同策略恢复；
- 获取与预测预算完全解耦；
- 通用跨灾种 provider；
- 独立天气过程确认；
- 真实主动 LLM selector 的正向增益；
- 完整 16 类准入。

---

## 2. 当前真实进度

### 2.1 已完成

| 部分 | 当前证据 | 正确解释 |
|---|---|---|
| 类型化自适应接入 | `TypedAviationRuntime` 被原 `SessionCoordinator` 调用 | 已接通 H15；不是新建第二套策略时钟 |
| 时间与封存 | baseline、withdrawal、begin、completion、cutoff 使用同一 `run_clock` | 可验证截止前有效状态 |
| 证据费用与权限 | bundle 从 session ledger 已结算 receipt 和 entitlement 构建 | 静态“假定已读”不等于动态已付费 |
| 静止点恢复 | 两个真实 27-opportunity session，多条跨进程续跑 | 仅 quiescent checkpoint |
| 新数据 | 97/97 请求成功，288 METAR，91 TAF，432 opportunities | 432 不是 432 个独立事件 |
| 模型诊断 | 252 次新 Qwen3-8B 调用，无重试、无缺失、无解析失败 | 固定输入诊断，不是自适应 selector 获益实验 |
| E 表示实验 | E-only 24/36 → 33/36；joint E 30/36 → 32/36 | 同一开发材料上的表示效应 |
| F 结果 | 144 个含 F 的回答全部保留共同基线 | 没有观察到预测增益 |
| TAF E | coverage 6/18；revision 16/18 | 产品合同理解，不是物理天气预测 |
| 程序对照 | 旧日期补证改善；新 2025 日期补证恶化 | 主动取证没有稳定优势 |
| 测试/复现 | 保存的 313-test 与 portable replay 通过 | 工程通过不等于科学 novelty 通过 |

### 2.2 当前数据限制

新 24 小时日历中：

- 1 km：0/216 正例机会；
- 5 km：2/216 正例机会；
- 同一天的站点、阈值和 lead time 不是独立天气过程；
- 历史 availability 使用声明的 archive latency，不是 2025 年真实 first-seen；
- Dec 2023 calibration bank 被迁移到 2025，没有按新结果重拟合。

因此，当前日历适合：

- 完整分母工程检查；
- 负结果保留；
- 时间与表示诊断；
- 程序对照；
- 恢复和记账测试。

它不适合单独支撑：

- 稀有浓雾预测能力；
- LLM F 优势；
- 独立过程统计结论；
- 业务预警效果。

---

## 3. 实现正确性：按严重性排列的发现

下表区分：

- **缺陷**：代码在某类合法失败路径上会留下错误或不完整状态；
- **设计局限**：当前冻结实验有意不支持，不能扩大声称；
- **研究门槛**：工程可运行，但不足以支撑科学结论。

### 3.1 P0：扩大实验前必须修复

#### F-01：资源预约后的异常路径不是 failure-atomic

**类型：实现缺陷。**

当前 `policies.py` 中至少存在三类路径：

1. selector 已 `ledger.reserve()`，随后 backend 抛出异常；
2. source 已预约，随后实际序列化字节超过 2048，直接抛错；
3. forecaster 已预约，随后 backend/adapter 抛出异常。

这些路径可能在进程终止前留下未结算 reservation，且没有统一的 durable attempt/disposition。
现有成功批次没有触发该问题，所以不改变已报告结果；但它会阻塞 CP04b、重试、超时和恢复。

**修复原则：**

```text
PREPARED -> DISPATCHED -> RETURNED -> PERSISTED -> COMMITTED
                      \-> FAILED / TIMED_OUT / CANCELED
```

每一步必须：

- 有持久化 attempt ID；
- 有幂等转换；
- 有 reservation disposition；
- 支持 crash 后恢复；
- 不把 backend exception 当作“此调用从未发生”。

**验收反例：**

- backend 在发送前、发送后无返回、返回后持久化前分别崩溃；
- source 返回超 byte cap；
- actual cost 超 reservation；
- duplicate completion；
- cancel 与 completion 同时到达；
- settle 成功但 admission event 尚未 commit 时进程退出。

#### F-02：checkpoint 只支持静止点

**类型：明确设计局限，当前报告已诚实披露。**

`capture_session()` 明确拒绝：

- ledger 有 reserved resource；
- runtime 有未完成 call；
- tick 中间状态；
- D/preparation 的完整在途状态。

因此，当前“跨进程恢复”只能表述为：

> 在完整 policy tick 结束、无在途任务的静止边界恢复。

不能表述为完整异步会话恢复。

**下一步：**

新增版本化 `session_inflight.v1`，保存：

- pending source request；
- pending selector call；
- pending forecast call；
- frozen input/bundle hash；
- request-time selected upstream revision；
- started/completed/persisted/committed 四类时间；
- remaining declared latency；
- reservation upper bound、payer、actual/disposition；
- idempotency/attempt key；
- unread completed result；
- preparation running/cleaning 状态；
- scheduler cursor；
- archive continuation manifest。

旧 `session_quiescent.v1` 保持可读，不覆盖历史。

#### F-03：当前阶段入口错位

**类型：文档/执行治理缺陷。**

`IMPLEMENTATION_STATUS.md` 顶部已经是 v7 typed adaptive，而
`disastertrace-starter/CURRENT_PHASE.md` 仍把 MM-4 atomic diagnostics 写成 current phase。

Codex 被要求读取这些文件时，可能误回到已经消费的 MM-5A 路线，或错误恢复旧 GPU 工作。

**必须修复：**

- 将 `CURRENT_PHASE.md` 改为短的 mutable pointer；
- 顶部只指向最新 commit、当前报告、当前 next plan 和本审计；
- 历史 MM/P 阶段保留为归档链接，不删除；
- 加测试验证 pointer 指向的文件存在，且最新日期/commit 与 `IMPLEMENTATION_STATUS.md` 一致。

#### F-04：相同策略恢复没有强绑定 backend contract

**类型：恢复语义缺陷/设计缺口。**

checkpoint 绑定了 data、bank、config 和 RNG，但 `SessionCoordinator.restore(..., backend=...)`
仍可由调用者传入另一个 backend 对象。若 config/executor 文本不变，恢复流程自身未证明：

- 模型权重相同；
- tokenizer 相同；
- prompt 实现相同；
- generation 参数相同；
- adapter 代码相同。

这对“故意换模型的分支实验”是允许的，但对“不间断等价恢复”不够严格。

**新增 `ExecutionContract`：**

```text
executor_id
backend_family
model_id
model_revision_or_weights_sha256
tokenizer_sha256
prompt_contract_hash
adapter_source_sha256
generation_parameters
output_schema_hash
runtime_image_or_environment_hash
```

- uninterrupted continuation：必须完全相等；
- branch intervention：必须显式声明 changed fields、parent checkpoint hash 和 intervention ID；
- 不允许静默切换 backend。

#### F-05：获取动作被预测调用上限耦合

**类型：设计局限，会影响 C1/D 扩展。**

当前 source acquisition 外层条件同时要求：

- `calls < total_calls_cap`
- `calls + selector_records < model_call_budget`

这意味着预测预算耗尽时，即使获取资料是为了：

- 下一 tick；
- 多目标共享；
- D/preparation；
- 后续专业工具；
- 只做 E 支持；

也不会继续获取。

这适合“获取后立即预测”的当前有界实验，但不适合完整 monitoring mission。

**修改方式：**

显式分开：

```text
source_request_budget
source_byte_budget
selector_call_budget
predictor_call_budget
processing_compute_budget
wall_clock_deadline
preparation_resource_budget
```

获取策略不得隐式依赖预测调用数；是否允许只获取不预测应由 action contract 决定。

---

### 3.2 P1：下一轮科学实验前完成

#### F-06：资源语义仍是部分统一

当前 `Cost` 有 `requests/bytes/tokens/compute_ms`，但实际调用中：

- source request 计入 requests/bytes；
- model 调用主要计 tokens/compute_ms；
- selector 与 predictor 的 persistence/timing 模型不完全对称；
- 模型调用次数另由 cap 管理；
- wall-clock 是 session clock，而不是 `Cost` 字段。

这并非当前结果的错误，但“统一资源预算”需要更精确表述。

建议二选一：

**方案 A：多账本。**

- source ledger；
- model ledger；
- processing ledger；
- preparation ledger；
- 最上层统一 feasibility 检查。

**方案 B：扩展 resource vector。**

```text
source_requests
model_calls
bytes_in
bytes_out
input_tokens
output_tokens
compute_ms
wall_clock_us
preparation_units
```

不要继续用同名 `requests` 混合不同资源，而报告中又靠另一个 cap 补充。

#### F-07：正式 OutcomeRecord 缺少完整时间证明

`score_admitted()` 当前能绑定：

- opportunity ID；
- target contract hash；
- mature/provisional/missing；
- outcome value；
- source revision。

但还需要正式绑定：

```text
valid_start / valid_end
observed_at
available_at
captured_at
maturity_decided_at
quality_flags
provider_version
source_sha256
result_policy
```

否则：

- 数学评分正确；
- 但“这个结果是否在何时成熟、是否与目标物理窗口完全一致”仍在 scorer 外部。

新增 `OutcomeRecord.v1`，由 evaluator-only settlement 使用；policy 端绝不能读取。

#### F-08：full vs focused 表示比较仍有混杂

当前 focused view 的改进是真实观察，但它同时改变了：

- JSON 层级；
- 字段数量；
- 上下文长度；
- slot 顺序；
- 时间表达密度；
- E-only 是否携带与 F 有关的目标/基线/state。

因此不能把 24/36 → 33/36 解释为某个单一因素。

下一轮仅做离线/新冻结对照：

1. full bundle + microseconds；
2. full bundle + ISO shadow fields；
3. focused slots + microseconds；
4. focused slots + ISO；
5. order-only shuffle；
6. token-matched irrelevant metadata control；
7. same source text, no evaluator answer；
8. E-only 与 F/joint 真实独立调用。

报告：

- coverage / comparison / version-selection 三类错误；
- exact boundary error；
- current vs superseded confusion；
- unknown/refuted confusion；
- token/context sensitivity。

#### F-09：`taf_coverage()` 的 fallback 空候选路径不稳健

`support_bridge.taf_coverage()` 在 `try` 之前读取
`candidate["source_id"]`。当 baseline 是 fallback、`native_taf is None` 时会抛出异常，
而不是返回声明的 `unsupported` 结果。

这不一定被当前 18 个真实 TAF 任务触发，但属于确定性健壮性缺口。

要求：

- 先写 `native_taf=None` red test；
- 返回 `status="unsupported"`、明确 reason；
- 不制造 source_revision；
- 不把 fallback 当作 TAF coverage 证据。

#### F-10：candidate `expires_at` 应受注册合同上界约束

`AdmissionEngine` 会检查候选在完成时是否合法，并由 target cutoff 约束是否可生效；
适配器也将 `expires_at` 设为该 target 的最大注册 cutoff。

通用接口仍应显式验证：

```text
expires_at <= registered_target_horizon
expires_at <= declared_candidate_lifetime
```

不能完全信任调用方提供任意远期 `expires_at`。

#### F-11：per-call `decision` 文本可能与最终 admission 不一致

`TypedAviationRuntime.execute()` 对所有有 F forecast 的记录写
`decision="override"`，即使最终状态可能是：

- late；
- stale_base；
- expired_lifetime；
- invalid_response；
- closed_target。

最终 snapshot 是正确的，但 call-level 表容易被误读。

拆分字段：

```text
proposed_action
admission_status
effective_action
effective_forecast_at_cutoff
```

分析时禁止用 `proposed_action` 代替生效状态。

---

### 3.3 P2：研究门槛，不是当前代码 bug

1. 252 次固定输入调用不是 adaptive LLM selector 对照。
2. 432 opportunities 的正例极少，不能支持稀有事件表现。
3. 新日期补证程序比 FOLLOW 更差，必须保留。
4. E 正确率提高没有带来 F 修订。
5. TAF coverage 仍为 6/18。
6. availability 是声明情景，不是历史 first-seen。
7. H07、H08、temperature、D、MM 仍各有独立准入门槛。
8. 多 station/threshold/lead 不增加独立天气过程数。
9. 当前没有完整 16 类科学准入。
10. 没有理由在工程硬化前扩大 GPU 矩阵。

---

## 4. 架构决策：不要立即建设第二套 Mission 时钟

旧版、基于 `60ebd057` 的计划建议新建完整 `monitoring_mission_v1` 内核。
当前提交已经实现：

- 单一 `run_clock`；
- `SessionCoordinator`；
- typed adapter；
- typed admission；
- resource ledger；
- support/reachability；
- preparation reducer；
- quiescent checkpoint。

因此，当前正确路线是：

```text
SessionCoordinator / run_clock
├── TypedAviationRuntime / AdmissionEngine
├── BudgetLedger / EvidenceStore
├── public_support / solve_joint
├── PreparationReducer
└── versioned checkpoint + branch intervention
```

而不是：

```text
现有时钟
+
新的 monitoring_mission_v1 时钟
+
新的 action scheduler
```

### 4.1 可以新增的上层命名空间

只有当 CP04b 完成后，才允许增加一个**组合层**：

```text
monitoring_mission_v1/
├── contracts.py       # mission/decision/action catalog，引用现有 Target/Cost
├── manifests.py       # opportunity→cutoff→effective prediction→outcome
├── branches.py        # 显式 intervention 描述，不自己推进时钟
├── reports.py         # Forecast/E/D/Runtime 分表
└── adapters/
```

它不得拥有第二个独立 clock，也不得复制：

- `Target`
- `Forecast`
- `Cost`
- `BudgetLedger`
- `ForecastState`
- `PreparationReducer`

### 4.2 D-sim 继续扩展现有 `PreparationReducer`

当前 reducer 已支持：

- duration；
- capacity；
- budget；
- cleanup duration/cost；
- cancellation；
- ready/expired；
- missing outcome bounds；
- 明确标注 research assumption。

后续扩展应增加：

- in-flight checkpoint；
- partial progress（仅在研究问题需要时）；
- resource classes；
- preemption policy；
- paired DecisionSpec；
- weather belief 与 preference 隔离。

不要另起一套行动状态机。

---

## 5. Codex 详细工作包

# Phase 0：建立可信起点

## DT-AUDIT-00：修复当前事实入口

### 目标

确保 Codex、研究者和复查者从同一最新入口开始。

### 修改

1. 更新 `disastertrace-starter/CURRENT_PHASE.md`：
   - 当前 commit；
   - `FINAL_REPORT_CN.md`；
   - `NEXT_EXECUTION_CN.md`；
   - 本审计计划；
   - 当前禁止重启的 GPU 目录。
2. 保留旧 MM/P 历史为归档链接。
3. 新增：
   - `plans/current_audit_20260913/AUDIT_FINDINGS_CN.md`
   - `plans/current_audit_20260913/AUDIT_FINDINGS.json`
   - `plans/current_audit_20260913/BASELINE.json`
4. `BASELINE.json` 至少保存：
   - git HEAD；
   - dirty paths；
   - Python/package versions；
   - key source SHA256；
   - latest report/validation hashes；
   - baseline test command/result。

### 测试

- pointer 中的路径都存在；
- CURRENT_PHASE 的 reference commit 与 baseline 一致；
- 不允许 current pointer 指向日期更旧且未标 archive 的阶段；
- 冻结历史文件哈希不变。

### 出口

- 机器可读状态明确；
- 不运行网络、模型或 GPU；
- 记录基线测试是否与 313-test receipt 一致。

---

## DT-AUDIT-01：确定性 red-test 包

为以下问题先写失败测试：

1. selector backend exception after reserve；
2. predictor backend exception after reserve；
3. source payload over byte cap after reserve；
4. crash after settle but before admission commit；
5. duplicate completion after restore；
6. same checkpoint restored with different backend contract；
7. `taf_coverage()` with `native_taf=None`；
8. arbitrary overlong candidate expires_at；
9. proposed override but late/closed → effective action not override；
10. stale `CURRENT_PHASE` pointer；
11. outcome valid window/source maturity mismatch；
12. acquire-only action when predictor budget is zero。

每个 red test 保存：

- test node；
- expected invariant；
- current failure/exception；
- log SHA256；
- planned fix ID。

不得通过删除、xfail 或缩小断言“解决”。

---

# Phase 1：CP04b 异步事务与恢复

## DT-CP04B-01：在途状态合同

### 新 schema

```text
disastertrace.session_inflight.v1
disastertrace.execution_attempt.v1
disastertrace.execution_contract.v1
```

### `ExecutionAttempt`

```text
attempt_id
logical_call_id
kind                        # source / selector / predictor / processor
owner
state                       # prepared/dispatched/returned/persisted/committed/...
reserved_cost
actual_cost | null
started_at
expected_complete_at
returned_at | null
persisted_at | null
committed_at | null
frozen_input_hash
selected_source_revision | null
raw_response_sha256 | null
error_class | null
disposition | null
idempotency_key
parent_checkpoint_hash
```

### checkpoint 必须保存

- ledger spent/reserved/entries；
- pending attempts；
- unread completed payload；
- remaining declared latency；
- store 与 entitlement；
- model call begin bundle；
- baseline/context hash；
- scheduler/tick cursor；
- preparation states；
- journal append position；
- external archive manifest；
- execution contract hash。

### 验收

在 query、selector、predictor、persistence 各阶段截断进程，恢复结果必须：

- 不重复外部调用；
- 不重复扣费；
- 不丢失已返回 payload；
- 不让晚到回答修改已封存 cutoff；
- uninterrupted report 与不中断运行 byte-identical；
- intentional branch 有新的 intervention ID。

---

## DT-CP04B-02：failure-atomic 资源事务

### 实现

新增统一执行包装器，伪代码：

```python
attempt = journal.prepare(...)
ledger.reserve(...)
try:
    journal.mark_dispatched(...)
    result = invoke(...)
    journal.mark_returned(...)
    persisted = persist(result)
    journal.mark_persisted(...)
    ledger.settle(actual, outcome="completed")
    admission.commit(...)
    journal.mark_committed(...)
except Timeout:
    ledger.settle(actual_or_zero, outcome="timed_out")
    journal.finalize("timed_out")
except Cancellation:
    ledger.settle(actual_or_zero, outcome="canceled")
    journal.finalize("canceled")
except Exception as exc:
    ledger.settle(actual_or_zero, outcome="failed")
    journal.finalize("failed", error=...)
```

实际实现需解决 `settle` 与 `admission.commit` 之间的崩溃：

- 使用 write-ahead journal；
- 或可重放的 deterministic commit；
- 不要求真正数据库事务；
- 但恢复必须能从 journal 判断是否需要重放 commit，而不是重新调用 backend。

### 错误分类

至少：

```text
pre_dispatch_failure
transport_failure_unknown_charge
timeout
provider_returned_error
invalid_response
output_limit
persistence_failure
resource_overrun
canceled
late_completion
duplicate_completion
commit_replay
```

### 验收

- 每个 reservation 最终恰好一个 disposition；
- `spent + reserved` 与 entries 重算一致；
- unknown charge 不被默认为零；
- 所有错误保留机会和回退；
- 完整 denominator 不因失败缩小。

---

## DT-CP04B-03：执行身份与分支合同

### 同策略恢复

必须绑定 `ExecutionContract`，包括：

- model ID/revision；
- weights hash（本地模型可记录 manifest hash）；
- tokenizer hash；
- prompt version/hash；
- adapter source hash；
- generation config；
- schema hash；
- runtime/environment manifest；
- public schedule / actual clock mode。

### 显式干预分支

新增：

```text
BranchIntervention:
  branch_id
  parent_checkpoint_hash
  changed_fields
  reason
  allowed_change_class
  created_before_outcome_access
  evaluator_only
```

允许的类别：

- acquisition policy；
- processing method；
- predictor；
- adoption rule；
- authorization mode；
- resource allocation；
- DecisionSpec；
- declared latency stress test。

禁止：

- 修改历史天气 outcome；
- 免费重置预算；
- 删除 inherited failure；
- 让每个目标分别获得完整 global budget 再相加；
- 事后选择获胜日期冒充确认。

### 验收

- 相同策略恢复时 backend contract mismatch 必须拒绝；
- 故意换 backend 时必须创建 intervention；
- parent prefix hash、spent/reserved/cache/state 完全相同；
- 分支差异报告只归因于声明字段。

---

# Phase 2：正式评分和资源合同

## DT-RESOURCE-04：解耦获取、处理、选择与预测预算

### 修改

将当前外层条件拆为独立 action admission：

```text
can_acquire
can_process
can_select
can_predict
can_prepare
```

获取可服务未来 tick、多个目标、E 或 D，而不要求当前仍有 predictor calls。

### 必须保留的对照

- `acquire=False, predict=True`
- `acquire=True, predict=False`
- acquire now, predict later
- shared acquire, multiple later forecasts
- predict cap exhausted but E/D acquisition remains legal
- source budget exhausted but cached processing remains legal

### 出口

可以构造：

- 纯证据支持任务；
- 处理方式选择；
- D-sim；
- 真正的两步策略；

而不受“立即预测”假设限制。

---

## DT-OUTCOME-05：OutcomeRecord 与有效预测 manifest

### 新建

```text
OutcomeRecord.v1
EffectiveForecastManifest.v1
```

### 正式链

```text
registered opportunity
-> lawful cutoff
-> journal prefix replay
-> effective forecast at cutoff
-> typed target match
-> mature/provisional/missing outcome
-> common mask
-> score
```

`EffectiveForecastManifest` 必须列出：

- begin/completed/persisted/admitted times；
- proposal action；
- admission status；
- effective action；
- effective forecast；
- fallback reason；
- baseline revision；
- source/attempt IDs；
- prefix hash。

### 出口

数学评分和及时提交资格在一个可复放合同中，不再靠外部表格隐含连接。

---

## DT-HARDEN-06：边界修复

包含：

- `taf_coverage(None)`；
- generic expires_at horizon；
- cancel completed call；
- unknown job ID 的显式错误；
- proposed/effective action 分离；
- selector persistence timing；
- model request/byte accounting命名；
- outcome maturity/QC；
- duplicate receipt/attempt identity。

---

# Phase 3：H15 诊断和完整程序基线

## DT-TAF-07：TAF 时间与表示误差分解

### 目标

解释 6/18 coverage，而不是直接换 prompt 重跑大矩阵。

### 对照

- UTC microseconds；
- ISO-8601 shadow；
- 两者同时；
- slot-sorted vs original order；
- raw-only vs raw+strict parser fields；
- full bundle vs focused；
- token-matched metadata；
- current/superseded-only；
- exact boundary cases；
- NIL/CNL；
- same-issued mirror/conflict。

所有模型输入不得包含：

- reference answer；
- evaluator sufficiency；
- outcome；
- coverage fraction gold；
- hidden latest label。

### 结果

按字段报告：

- version selection；
- time decoding；
- interval containment；
- status；
- source IDs；
- unsupported/conflict。

现有 6/18 和 16/18 必须保留为原结果，不重写。

---

## DT-H15-08：432 机会完整程序控制

先不调用 LLM，完成全 24 小时：

- FOLLOW；
- frozen statistical map；
- one-read；
- all-read；
- batch-complete；
- risk heuristic；
- coverage heuristic；
- fixed quota/global budget × private/shared；
- acquire-only / delayed predict；
- no-acquire；
- missingness bounds。

报告：

- 所有 432 opportunities；
- settled/missing；
- Brier；
- positive/negative counts；
- source requests/bytes；
- compute；
- wall-clock scenario；
- change/preservation；
- improve/worsen/no-change；
- process-block bootstrap 仅作为敏感性，不把机会当 IID。

### 放行条件

只有在程序控制、记账、结果 manifest 完成后，才冻结更长日期块或 LLM selector。

---

## DT-H15-09：更长开发块与独立确认块

### 冻结规则

- 日期和站点在 outcome/模型结果前登记；
- 保留普通、近阈值和极端过程；
- 不按现有模型错误挑样本；
- 按 parent weather process / conservative block 分组；
- development 与 confirmation 不重叠；
- purge 覆盖输入 lookback、lead 和 outcome window；
- 记录 calibration bank 的训练支持和正例数。

现有零/少正例日历保留，不删除。

---

# Phase 4：C1/C2 公平机制实验

## DT-C2-10：将实际 receipt 图接入联合可达性

`compile_recipes()` 只生成 evaluator-only hindsight recipe；
下一步将实际会话映射为：

```text
Query:
  query_id
  release
  duration
  valid_until
  dependencies
  actual/declared cost
  shared entitlement

Goal:
  target_id
  deadline
  support alternatives
```

调用 `solve_joint()` 获得：

- exact/lower/upper bound；
- one-session joint witness；
- individual relaxation；
- witness replay；
- truncation status。

必须禁止：

- 每个目标各自使用一次完整 global budget；
- 将不兼容单目标最优路径相加；
- 用 evaluator recipe 提示在线 selector；
- 把 E reachability 当 F accuracy。

---

## DT-C1-11：公平 2×2 与强基线

第一层固定同一 selector：

```text
fixed_quota / global_budget
×
target_private / session_shared
```

第二层固定 global/shared：

```text
round_robin
risk
coverage
batch_complete
one-step program
two-step finite lookahead
LLM selector
```

所有方法必须相同：

- target set；
- source catalog；
- permissions；
- query/processing tools；
- baseline；
- predictor；
- clock；
- budgets；
- missingness；
- outcome mask。

便宜批量接口继续作为强对手，不人为拆贵。

---

## DT-ATTR-12：selector × predictor 因子实验

当前 252 次固定输入诊断不能回答 selector 是否有用。正式矩阵：

| Selector | Predictor | 回答的问题 |
|---|---|---|
| fixed | statistical/program | 无 LLM 强基线 |
| LLM | same statistical/program | 只测资料/目标选择 |
| fixed | LLM F-only | 只测预测器 |
| LLM | LLM F-only | 端到端组合 |
| batch/all-read | strongest program | 可获得上界型强对手 |

Joint head 单列，不代替 F-only。

额外固定：

- candidate 与 effective forecast 分开；
- selector call 也计预算；
- E-only 不进 F denominator；
- invalid/late 保留；
- 不要求模型必须修改概率。

---

## DT-BRANCH-13：完整状态分支归因

从同一 checkpoint 分别执行：

1. no additional action；
2. one legal source；
3. full legal batch；
4. same raw asset, different processor；
5. same evidence, different predictor；
6. same candidate, different adoption rule；
7. same output, different completion time；
8. same weather, different DecisionSpec。

分项归因：

```text
acquisition effect
processing effect
prediction effect
adoption effect
timing effect
decision effect
```

hindsight-best 只作为 evaluator diagnostic，不称为可部署策略。

---

# Phase 5：D-sim 与“行动需要决定信息价值”

## DT-D-14：扩展现有 PreparationReducer

在 CP04b 完成后，将 reducer 状态纳入 checkpoint。

第一版动作：

- observe；
- start preparation；
- cancel/cleanup；
- reprioritize（可通过明确 cancel+start 实现）；
- request human review。

第一版不要做开放式疏散文本。

### 三 head 隔离

**Weather F head：**

- 只能看天气证据；
- 不看 miss penalty、人员、准备成本；
- 输出概率/连续量。

**Acquisition head：**

- 可看 DecisionSpec；
- 决定信息是否仍能改变安排。

**Decision head：**

- 接收冻结 F 与 DecisionSpec；
- 决定准备状态。

### 核心配对

保持天气、证据和预测器相同，只改变：

- preparation duration；
- capacity；
- cost；
- cleanup cost；
- reversibility；
- deadline。

检查：

- F 是否不受偏好污染；
- 获取与行动是否合理改变；
- 已来不及改变的目标是否停止昂贵搜索；
- 相同风险、不同准备时间是否产生不同合法动作。

所有收益写为：

> 在固定研究性 DecisionSpec 下的准备损失。

不得写成真实损失、伤亡或业务效果。

---

# Phase 6：第二物理过程

## DT-H07-15：区域短时强降水

优先完成数据合同，不先跑 VLM：

- rain rate vs accumulation；
- accumulation window；
- grid/projection；
- issue/available/valid times；
- radar/NWP lineage；
- QC、negative code、missing；
- outcome reference；
- spatial aggregation；
- license；
- continuous sequences；
- process grouping。

强基线：

- latest professional/NWP；
- persistence；
- optical-flow/专业 nowcast；
- full batch；
- fixed trigger；
- same raw asset with different processing depth。

只有出现真实 coverage-depth 取舍后，才比较 VLM/LLM 工具选择。

## DT-H08-16：水文

必须核准：

- QINE 是瞬时还是小时平均；
- regulated/unregulated；
- ensemble member identity；
- gauge/cross-section；
- forecast/observation support；
- historical availability；
- datum/QC；
- stage vs flow；
- official threshold 或预注册 statistical task；
- NLDI/河网关系。

无法核准时保留工程配对，不评分、不冒充 flood warning。

---

# Phase 7：C3 独立确认与发布

## DT-C3-17：冻结确认

冻结：

- predictor；
- selector；
- prompt；
- processing；
- DecisionSpec；
- calibration；
- dates/regions/processes；
- analysis；
- missingness policy。

按独立过程/时空块评估，不按 calls 计样本量。

## DT-SHADOW-18：前瞻影子运行

- 先提交预测和动作建议；
- 后结算；
- 不对公众发布；
- 不控制设备；
- 保存 first-seen、失败、延迟和版本；
- 与历史 replay 分表。

## DT-PUBLISH-19：分级发布

**工程版：**

- 类型化合同；
- replay；
- 负结果；
- 程序基线；
- 回执和失败。

**机制版：**

- 公平 C1/C2；
- 完整分支；
- independent processes；
- 强对照。

**完整 v7：**

- 16 类逐项 admission；
- E/F/D/MM 分级；
- 第二物理过程；
- confirmation；
- license/data cards。

---

## 6. 实验主表

### 6.1 Forecast

- Brier；
- reliability/resolution；
- MAE/CRPS/quantile loss（适用时）；
- gain over latest lawful professional baseline；
- improve/worsen/no-change；
- complete calendar；
- common result mask；
- process-block uncertainty。

### 6.2 E / Support

- supported/refuted/undetermined/inconsistent；
- coverage/current revision；
- sufficient recipe size；
- individual vs joint reachability；
- parser unsupported；
- source conflict；
- provenance validity。

### 6.3 Alert/Review

- time to first correct flag；
- false/missed review；
- review churn；
- risk coverage under review capacity；
- whether flag arrived while action remained feasible。

### 6.4 D-sim

- ready by deadline；
- missed demanded jobs；
- wasted preparation；
- cleanup/cancel cost；
- capacity violation；
- total cost bounds under missing outcomes。

### 6.5 Runtime

- source requests/bytes；
- selector/predictor calls；
- tokens；
- compute；
- wall clock；
- persistence；
- late/canceled/failed；
- cache reuse；
- inherited vs new charges。

### 6.6 Branch Attribution

- paired loss difference；
- evaluable fraction；
- unavailable-counterfactual reason；
- hindsight oracle gap；
- acquisition/processing/prediction/adoption/timing decomposition。

不要在首版把不同单位压成一个任意总分。

---

## 7. Go / No-Go 门槛

### Gate A：允许新模型调用前

必须全部满足：

- P0 red tests 已修复；
- in-flight recovery 通过；
- no reservation leaks；
- backend contract 绑定；
- outcome manifest 完成；
- full 432 program controls 完成；
- experiment freeze 完成；
- no consumed run reused。

否则：**No-Go for GPU/model calls。**

### Gate B：允许声称 C1 机制结果前

必须：

- strong batch/all-read baseline；
- same permissions/tools/budget；
- selector/predictor 因子分离；
- actual receipt/time graph；
- joint witness；
- complete denominator；
- independent process/block analysis。

否则只能写开发诊断。

### Gate C：允许 D 应用价值表述前

必须：

- DecisionSpec 清楚；
- F 与偏好隔离；
- preparation state 可恢复；
- simple optimizer/program baselines；
- same-weather paired tasks；
- user/operational rules 有来源或明确标 research assumption。

否则只称 synthetic preparation engineering。

### Gate D：允许第二场景论文结果前

必须：

- 完整 target/time/QC/outcome/availability/license；
- nontrivial sequence；
- strong professional/program baseline；
- process-level split；
- no data postselection。

### Gate E：允许“独立确认”前

- development 完全冻结；
- confirmation 未被 prompt/data tuning 看过；
- no selective retry/replacement；
- missing/failures retained；
- process-level unit reported。

---

## 8. Codex 每个任务的交付模板

```markdown
# Task <ID> Completion

## Scope
- reference commit:
- actual starting HEAD:
- allowed operations:
- prohibited operations:

## Changes
- files:
- schemas:
- migration/compatibility:

## Red Tests
- command:
- exit:
- failed nodes:
- log hashes:

## Green Tests
- targeted:
- related:
- full:
- lint/type:
- skips:

## Runtime/External Actions
- network:
- model calls:
- GPU jobs:
- paid API:
- training:

## Preservation
- historical files checked:
- hashes:
- consumed launches untouched:

## Findings
- fixed:
- still blocked:
- scientific implications:

## Next Gate
- GO / NO-GO:
- next task:
```

---

## 9. 首轮建议的实际完成定义

Codex 完成首轮后，应交付：

1. 最新 CURRENT_PHASE pointer；
2. 审计 JSON/Markdown；
3. 12 类 red regressions；
4. `ExecutionAttempt.v1`；
5. `ExecutionContract.v1`；
6. `session_inflight.v1` 最小实现；
7. failure-atomic ledger wrapper；
8. same-backend restore 检查；
9. explicit branch intervention；
10. source/selector/predictor exception recovery；
11. targeted + related tests；
12. CPU replay；
13. 更新 status/decisions/blockers；
14. 明确停止，不启动新模型实验。

首轮成功不代表：

- C1/C2 已科学验证；
- D-sim 已完成；
- H07/H08 已准入；
- LLM 有预测优势；
- 16 类完成。

---

## 10. 建议的最终论文主线

在现有工程基础上，最有辨识度的方向仍然是：

> **面对持续更新的专业预报和多个共享资源的风险目标，DisasterTrace 评测智能体能否在截止前选择值得获取和处理的信息，形成有效预测与研究性准备；并从同一完整状态重跑真实替代路径，验证价值或失败发生在获取、处理、预测、采用还是行动阶段。**

但这条主线应通过当前单一时钟、typed admission、resource ledger、support/reachability 和
preparation reducer 逐步实现，而不是再增加一套平行框架。

近期优先级固定为：

```text
事实入口
→ failure-atomic + in-flight restore
→ backend/outcome/resource contract
→ 432 程序基线
→ 公平 C1/C2
→ D-sim 配对
→ H07/H08
→ independent confirmation / shadow
```

任何新 GPU 批次都应排在前四项之后。
