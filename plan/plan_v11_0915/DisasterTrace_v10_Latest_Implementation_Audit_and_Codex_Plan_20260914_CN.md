---
title: DisasterTrace v10 最新实现复查与 Codex 后续执行计划
plan_version: "v10-post-closure-audit-20260914"
planning_date: "2026-09-14"
language: zh-CN
repository: "sisuolv/disastertrace-benchmark"
branch: "next-phase-v1"
reference_commit: "1fd6821fef15b26898a57c74d4715714f33ea779"
reference_parent: "6f71c8799ff69439a18f645e63b8c966ca21eec4"
review_scope: "current GitHub source, contracts, saved receipts, reports and tests; no independent full private-repository checkout rerun in this review"
current_phase: "v10 experiments closed; confirmation unopened"
default_allow_network: false
default_allow_model_calls: false
default_allow_gpu: false
default_allow_paid_api: false
default_allow_training: false
supersedes:
  - "DisasterTrace_v9_Latest_Implementation_Audit_and_Codex_Plan_20260914_CN.md"
  - "plans that still treat COPY controls, immutable API ledger, provider outcome policy, formal session, seasonal data or temperature postprocessing as unimplemented"
---

# DisasterTrace v10 最新实现复查与 Codex 后续执行计划

## 0. 可直接交给 Codex 的首轮指令

```text
仓库：sisuolv/disastertrace-benchmark
分支：next-phase-v1
本计划复查时远端 HEAD：

1fd6821fef15b26898a57c74d4715714f33ea779

不要 reset 到该提交；先读取实际 HEAD。若分支已经前进，先生成从上述提交到实际 HEAD
的差异审计，再将本计划应用于真实最新状态。

不得重启或替换任何 v8/v9/v10 已消费任务，不得因结果不理想而重跑模型，不得打开
尚未使用的确认资料。

开始前依次读取：

1. disastertrace-starter/AGENTS.md
2. disastertrace-starter/CURRENT_PHASE.md
3. LATEST_PROGRESS_V10_CN.md
4. plans/v10_execution_20260914_01/CANONICAL_STATUS.json
5. plans/v10_execution_20260914_01/FINAL_RESULT.json
6. plans/v10_execution_20260914_01/FINAL_REPORT_CN.md
7. plans/v10_execution_20260914_01/REVIEW_RESOLUTION_CN.md
8. plans/v10_execution_20260914_01/NEXT_PHASE_PLAN_CN.md
9. plans/v10_execution_20260914_01/OVERALL_PLAN_UPDATED_CN.md
10. disastertrace-starter/IMPLEMENTATION_STATUS.md
11. disastertrace-starter/DECISIONS.md
12. disastertrace-starter/BLOCKERS.md
13. 本计划

首轮仅允许 CPU/offline 工作：

- V10A-00：建立 post-closure 审计基线与保护清单；
- V10A-01：关闭正式评分的 FormalSession provenance 旁路；
- V10A-02：关闭 API ledger claim 的崩溃窗口并加强 failure recovery；
- V10A-03：强化 provider-specific outcome policy，尤其 DWD target binding；
- V10A-04：实现预加载 engine 的正式评分与 journal replay cache；
- V10A-05：运行完整相关回归、portable capsules 和独立等价性检查；
- V10B-00：冻结下一批全年数据、process unit、模型和确认协议草案；
- 完成后停止。

首轮禁止：

- 网络下载；
- 模型/API 调用；
- GPU；
- 训练；
- 打开 Bay 2025-02-17 至 23；
- 读取任何新 confirmation outcome；
- 修改 v10 原始响应、journal、模型分数或失败；
- 将 clarification 后的同题结果替换原成绩；
- 将 12 region-weeks 写成 12 个独立天气过程；
- 将 Denver/outcome-selected 诊断并入自然日历；
- 将 persistent old-value 收益写成新预测信息；
- 将 temperature program/EMOS 结果写成主动取证或 LLM 收益。

所有代码修复必须：

1. 先写当前代码上可失败的 red test；
2. 保存命令、退出码、JUnit、stdout/stderr 和 SHA256；
3. 保留旧 schema 的只读 replay；
4. 不修改历史冻结目录；
5. 更新 IMPLEMENTATION_STATUS、DECISIONS、BLOCKERS、CURRENT_PHASE；
6. 写 STOP_RECEIPT，确认 network/model/API/GPU/training 全部为 0。
```

---

# 1. 本次复查起点与证据边界

## 1.1 当前真实状态

本计划以：

```text
next-phase-v1
1fd6821fef15b26898a57c74d4715714f33ea779
```

为参考。

v10 已经完成并关闭的主要工作包括：

- 720 项 monitoring 回归；
- 23 个云任务全部终止；
- 正式 `FormalSession`；
- `measurement.v3` 干预顺序；
- provider-specific H15/DWD outcome policy；
- per-call immutable API escrow；
- COPY_CURRENT / COPY_BASELINE；
- 多截止和 adoption 程序对照；
- 12 个 seasonal region-weeks；
- 12,096 个 seasonal opportunities；
- 216 条季节性预算控制轨迹；
- feature bank、校准和消融；
- 27B/235B fixed feature/temperature；
- 235B selector；
- clarified feature diagnostic；
- 24 个月 temperature postprocessing；
- 两个可搬迁评分 capsule；
- confirmation 未打开。

## 1.2 复查方式

本次复查直接读取了：

- 当前 GitHub 源码；
- v10 canonical/final reports；
- 关键测试；
- FormalSession、API ledger、outcome、admission、feature backend；
- 当前 next plan。

没有在本对话运行环境独立 clone 私有仓库、恢复全部大型 fixture 并重跑 720 tests。
所以发现分为：

- **确定性源码问题**：代码即可确认；
- **残余资格风险**：当前结果未必受影响，但后续正式实验可被旁路；
- **已披露设计边界**：不属于 bug；
- **科学门槛**：工程成功不等于研究结论。

Codex 首轮仍须在真实工作区重跑基线。

---

# 2. 总体正确性判断

## 2.1 当前注册范围内基本正确

当前实现已经可靠完成：

1. 当前原生产品选择与固定目标覆盖分离；
2. 单一事件时钟；
3. 非法批次整体拒绝；
4. measurement-v3 transaction fork；
5. cutoff seal；
6. intervention 在 begin 前；
7. typed Forecast / EvidenceBundle；
8. source/selector/predictor 资源分离；
9. request/executor binding；
10. unknown reservation 保留；
11. single-pending serial recovery；
12. COPY controls；
13. formal provider outcomes；
14. complete opportunity denominator；
15. common baseline trace；
16. comparison invariants/interventions；
17. exact proposal/current/baseline attribution；
18. slotwise E 与 program composition；
19. threshold-coherent 1km/5km feature backend；
20. fit/calibration/evaluation purge；
21. seasonal natural-calendar development；
22. temperature EMOS/ECC；
23. immutable captured-answer scoring；
24. historical failures and negative results preserved。

未发现能够直接推翻 v10 主表的确定性错误。

## 2.2 当前不能扩大声称

仍不能声称：

- formal score 无法被任意直接 journal 构造旁路；
- API attempt claim 在任意进程崩溃下原子；
- arbitrary distributed exactly-once；
- multiple concurrent pending；
- 历史 first-seen 已证明；
- 12 region-weeks = 12 independent weather systems；
- 235B/27B 提供稳定新增 F；
- 235B selector 优于强程序；
- clarified prompt 已独立泛化；
- f(B,E) 是 same-budget active agent 成绩；
- temperature 已验证 C1；
- D 已验证实际业务价值；
- MRMS/HEFS 物理 F 已准入；
- 16 类均完成同等正式评测。

---

# 3. 当前进度与结果的研究解释

## 3.1 模型规模与调用成功不等于 F 价值

v10 的主要模型发现是：

- fixed packet 有效 F 几乎全部复制可见 baseline；
- 27B/235B 温度预测没有稳定超过共同 baseline；
- 235B 改动更多，但损失更高；
- clarified feature 大幅提高字段准确率，固定后端 F 没有改善；
- 235B selector 的 5km Brier 明显差于 FOLLOW。

因此下一阶段不再进行模型规模 sweep。

## 3.2 E 已经可以分解为 perception、slot judgment 和 aggregation

当前已经证明：

- 逐槽字段可以正确；
- 最终 existential/conflict aggregation 仍可错；
- 程序 composition 可以消除 aggregation error；
- 但 E 更准不保证 F 更好。

下一步重点不是重新实现 E composition，而是把现有 composed E 接入：

```text
同一 calibrated backend
同一 active acquisition
同一 process units
同一 confirmation
```

## 3.3 当前真正有开发价值的是 backend 与 evidence 的分离

四季结果表明：

```text
FOLLOW
common backend
values backend without evidence
values backend with full evidence
```

必须分开。

5km 下：

- common backend 已改善；
- full evidence 在部分设置进一步改善；
- 1km 不存在统一收益；
- active budget subset 的总体小改善主要来自无正例块；
- 12 月有正例块反而退化。

所以：

> active acquisition 不能由 aggregate Brier 宣称有效，必须按自然过程、正例支持、后端与证据分别归因。

## 3.4 Selector 的下一步是 regret decomposition，不是再跑更多 LLM

当前 selector：

- 输出合法；
- 查询数符合预算；
- 部分 E 判断正确；
- 最终 5km 明显差于 FOLLOW。

需要回答：

```text
选错资料？
后端不适合？
资料处理错？
概率转换错？
adoption 错？
等待/迟到？
```

这正适合使用同状态 branch replay。

## 3.5 Temperature 是成熟的 F-only 第二链

已完成：

- 原生集合；
- DWD daily outcomes；
- 多起报；
- 同成员 duration event；
- EMOS/ECC；
- 24 月完整日历。

未完成：

- 合法 historical supplementary evidence；
- active acquisition；
- action-aware value；
- independent model gain。

所以 temperature 可承担 C3 F-only 和 D 更新协议实验，暂不能承担温度 C1。

---

# 4. P0 发现：下一次正式实验前修复

## P0-01：`score_formal` 未强制验证对应的 FormalSession contract

### 现状

`FormalSession` 构造和恢复会验证：

- source manifest；
- bound files；
- comparison；
- config；
- formal checkpoint；
- STOP boundary。

但 `score_formal(outcomes, arms, comparison=...)` 接收的是 journal paths。
它检查 journal 内：

- measurement.v3；
- formal_resolution_policy；
- production_bound；
- lifecycle timing。

它没有要求：

- `CONTRACT.json`；
- formal checkpoint marker；
- STOP.json；
- formal contract hash；
- bound file manifest；
- report hash。

理论上，一个直接调用普通 `run_session`、但配置字段伪装成 formal 的 journal
可以通过 `score_formal` 的初筛。

### 影响

这是**资格 provenance 旁路**。

没有证据表明 v10 正式结果使用了伪造 journal；当前发布脚本有额外冻结和审计。
但后续正式成绩不应只靠调用纪律保证。

### 修复

改变 formal scorer 输入：

```text
arm_name -> FormalRunReference:
  journal_path
  formal_directory
  contract_path
  stop_path
  final_checkpoint_or_report
```

验证：

```text
CONTRACT schema
CONTRACT hash
STOP reason == completed
STOP contract hash
STOP report hash
journal experiment formal_contract_sha256
source manifest hash
data hash
bank hash
comparison hash
provider policy
```

在 FormalSession 创建时，把：

```text
formal_contract_sha256
formal_source_manifest_sha256
```

写入 experiment invariants / admission contract。

### 测试

1. ordinary run_session + formal-looking config 必须拒绝；
2. CONTRACT 缺失；
3. STOP 缺失；
4. STOP failed；
5. changed source file；
6. journal from another formal directory；
7. changed comparison；
8. correct formal run passes。

---

## P0-02：generic `score_admitted` 仍可使用 legacy outcome validation

### 现状

`score_formal` 会先经过 formal `OutcomeRegistry`。

但是 generic `score_admitted` 在 outcome 含 resolution version 时，内部重新建立的是
legacy-compatible `OutcomeRegistry`。

如果正式脚本绕过 `score_formal`，provider-specific policy 不一定强制执行。

### 修复

新增：

```text
score_admitted_engines(...)
score_formal_runs(...)
```

- formal scorer canonicalize outcomes 一次；
- generic scorer 不再重新降低 validation mode；
- formal engine 带 `formal_required=True`；
- formal journal 禁止进入 generic public scorer；
- legacy replay 保持显式入口。

---

## P0-03：API attempt claim 有 mkdir→reserve 的崩溃窗口

### 现状

`ApiLedger.claim()`：

```text
mkdir attempt directory
write reserve.json
```

若进程在两者之间终止：

- attempt directory 已存在；
- reserve receipt 不存在；
- 同一 call 不能重新 claim；
- reducer 会把目录计为 claimed/unresolved；
- 没有显式 claim-incomplete recovery。

### 修复方案

推荐：

```text
attempts/.claiming/<uuid>/
  claim.json
  reserve.json
fsync
atomic rename -> attempts/<call_hash>/
```

或：

```text
exclusive claim.json as first atomic artifact
attempt directory only after claim receipt exists
```

新增状态：

```text
CLAIM_INCOMPLETE
CLAIMED
DISPATCHED
RESPONSE_PERSISTED
BILLED
FAILED_PRE_DISPATCH
FAILED_POST_DISPATCH
RECONCILED
```

### 测试

在以下位置强制 kill/fault：

1. before mkdir；
2. after mkdir；
3. after reserve；
4. after request；
5. after dispatch；
6. after response.raw；
7. after wire；
8. after billing；
9. before terminal。

每一状态必须可重算、不可免费重试、不会永久不可解释。

---

## P0-04：超限 response 的 hash 命名不精确

当前 HTTP success path 最多读取 4,000,001 bytes。

当服务端 body 更长时：

- 保存的是 bounded prefix；
- `original_body_sha256` 实际是该 captured prefix 的 hash；
- 不是完整 provider body hash。

### 修复

改名并新增：

```text
captured_body_sha256
capture_limit_bytes
capture_truncated
full_body_sha256 = null
```

不得将 bounded capture hash 描述为完整 wire body hash。

历史 schema 保持 replay 兼容。

---

## P0-05：DWD provider policy 对 target 语义绑定仍偏宽

H15 policy 显式绑定：

```text
variable == visibility
report_policy == iem_routine_unique_hour.v1
```

DWD policy 目前主要绑定：

```text
interval
units C
future_physical
reference kind
quality
times
```

它尚未同等强制：

- target variable；
- daily max/min/event kind；
- UTC-day aggregation；
- DWD product identity；
- duration-event member/time contract。

### 修复

拆分：

```text
dwd_daily_tmax_archive.v2
dwd_daily_tmin_archive.v2
dwd_daily_event_archive.v2
dwd_duration_event_archive.v2
```

每项绑定：

```text
variable
aggregation
support interval
unit
reference product
quality
result policy
duration construction
```

---

## P0-06：formal bound files 的 data provenance 需要机器要求

FormalSession 会绑定所有 Python 源码，并通过 experiment hash 绑定内存 data/bank。

但接口只强制 source files 的路径清单；它没有强制 bound_files 中必须列出：

- DATA.json；
- BANK.json；
- target registry；
- query catalog；
- source index；
- comparison contract；
- provider outcome policy artifact。

### 修复

新增 `FormalInputManifest`：

```text
source_code
data
bank
target_registry
query_catalog
source_index
comparison
provider_policy
prompt
execution_contract
```

每项保存：

```text
role
path or content-address
sha256
schema
```

formal contract 必须绑定其整体 hash。

---

# 5. P1 工程工作：性能与并发

## P1-01：正式评分重复 replay

当前九方法正常评分路径会执行约 19 次完整 `from_journal`：

```text
score_formal first engine
score_formal validate each arm
score_admitted load each arm again
```

### 修复

新增：

```python
def load_verified_engines(arms, replay_cache=None): ...
def score_admitted_engines(outcomes, engines, comparison=None): ...
def score_formal_runs(outcomes, formal_runs, comparison=None): ...
```

cache key：

```text
journal file sha256
formal contract sha256
scorer version
```

### 等价验收

- output JSON byte-identical；
- all admission statuses identical；
- common baseline trace identical；
- formal provenance checks retained；
- corrupted journal never served from cache；
- 720 tests + new performance tests；
- relocated capsule replay。

### 剖析

分别记录：

```text
read bytes
journal parse
hash-chain verify
event replay
snapshot seal
baseline trace
outcome validation
paired scoring
report serialization
```

不要只报告总加速。

---

## P1-02：有界 multi-pending

当前 single-pending serial recovery 是合格边界，不是 bug。

在行动与 MM 前增加：

```text
session_inflight_set.v6
```

首版只支持：

```text
two independent sources
source + deterministic processor
source + preparation
```

需要：

- dependency DAG；
- reservations；
- independent completion order；
- cutoff visibility；
- duplicate remote receipt；
- one unknown does not block unrelated work；
- no free inherited work on branch。

暂不支持任意模型 fan-out。

---

# 6. 下一批数据与基线：修订当前计划

## P2-00：先冻结全年数据注册，而不是固定“必须多少天”

当前 next plan提出 2023 fit、2024 calibration、2025 exposed development。
这是合理的最小路线，但日期规模不应仅写成 50/100/150 天。

### 注册应由以下目标驱动

```text
每地区/季节的 target count
1km/5km positive target count
positive process/block count
missing/QC distribution
TAF coverage state
evidence availability state
expected interval precision
```

### 推荐两级方案

**最低可执行方案**

```text
2023 full year fit
2024 full year calibration
2025 exposed development
unopened confirmation separate
```

**稳健性方案**

```text
rolling-origin:
  fit <= year Y-2
  calibrate year Y-1
  evaluate year Y
```

至少增加一组 year-role sensitivity，避免“2023/2024 年差异”被误认为“fit/calibration 效果”。

---

## P2-01：训练所有部署缺证模式

当前正式部署可能出现：

```text
common only
none read
one slot read
all read
missing report
censored visibility
conflict
stale version
late evidence
```

新 bank 必须在 fit/calibration 中覆盖将要部署的模式。

不能：

```text
只在 all-read 训练
→ 对 partial/missing 直接当同分布预测
```

### 保留的 bank families

```text
B: common research baseline
f_common(B)
f_mask_age(B,E)
f_values(B,E)
f_values_no_year(B,E)
season-shrinkage sensitivity
```

raw probability 是 primary；PAV/CDF 是 secondary sensitivity。

---

## P2-02：对 feature selection 使用 nested development

v10 去除 `year_sin/year_cos` 的消融是在看到四季结果后提出的，所以只能是 development。

下一批：

1. 在 fit/calibration 内选择 feature family；
2. selection criterion 预先冻结；
3. 2025 exposed 只做 development validation；
4. confirmation 不再变更；
5. 保留原 winter bank、full-feature bank、no-year bank。

---

# 7. 自然过程、统计单位与确认

## P3-00：两级依赖单位

当前 global time/asset block 过于保守，可能把不同地区同一周全部合并；
但把 region-week 当独立天气系统又过于乐观。

新增：

### Level A：机械 dependence block

```text
input/output footprint overlap
shared native version
purge gap
```

### Level B：外部/预注册 process unit

```text
region
synoptic/event catalog if available
start/end
affected stations
weather regime
source/rule version
```

如果无法可靠识别 synoptic system，则 primary unit 使用：

```text
pre-registered region-week
```

并做：

```text
72h block
7d block
global week
leave-one-region-week-out
```

敏感性分析。

---

## P3-01：主结果与极端诊断分开

### Natural calendar

- 全部普通机会；
- 完整 missing；
- Brier / calibration；
- cost；
- process-level uncertainty。

### Extreme diagnostic

- selection rule 在 outcome 前冻结；
- 完整过程窗口；
- 邻近正常窗口；
- 事件比例不代表自然 prevalence；
- 不并入总体均值。

Denver 类型结果继续单列。

---

## P3-02：confirmation freeze

在读取任何 confirmation outcome 之前写：

```text
CONFIRMATION_PROTOCOL.json
CONFIRMATION_FREEZE_MANIFEST.json
CONFIRMATION_STOP_RULE.json
```

冻结：

- commit；
- source code；
- data/source URLs；
- models；
- prompts；
- execution contracts；
- bank families；
- E composition；
- selector；
- predictor；
- adoption；
- protocol；
- budgets；
- process units；
- metrics；
- missingness；
- retries；
- call cap；
- stop rule。

Bay heldout week只能承担一个窄确认，不承担全年/跨区结论。

建议额外预注册一组：

```text
continuous cross-season historical windows
or
prospective 2026 shadow windows
```

但不能根据 outcome 选择。

---

# 8. C2：用现有结果做真正的 branch attribution

## P4-00：Selector regret decomposition

冻结同一：

```text
state
backend
budget
clock
query universe
adoption
outcomes
```

比较：

```text
no query
all legal batch
round-robin
risk
coverage
LLM selector
one-step expected loss program
two-step finite lookahead
hindsight archive oracle (diagnostic only)
```

### 分解

```text
acquisition regret
evidence extraction regret
aggregation regret
probability mapping regret
adoption regret
timing regret
```

### 关键规则

- oracle 不进入可部署排名；
- branch 继承已花预算、cache、pending 和当前 override；
- unavailable counterfactual 标记不可评估；
- 不用 outcome 选择在线动作。

---

## P4-01：从 E composition 连接到 F

现有 `e_composition.py` 已完成严格 program aggregate。
下一步不是重做 E，而是新建 pipeline：

```text
E0 native deterministic
E1 model direct
E2 model slotwise + model aggregate
E3 model slotwise + program aggregate
```

然后固定同一个概率后端：

```text
F0 f(B)
F1 f(B,E0)
F2 f(B,E1)
F3 f(B,E2)
F4 f(B,E3)
```

分别报告：

- E correctness；
- F Brier；
- forecast changes；
- help/harm；
- cost；
- invalid fallback；
- process blocks。

同一个底层问题的多 representation 不作为独立样本。

---

## P4-02：same-information / same-total-budget

当前 selector 和 predictor 比较仍需两层公平性：

```text
same source-query budget
same total compute/token/wall-clock envelope
```

来源请求相同，不代表模型计算相同。

需要声称“更值得采用”时，必须有第二层资源合同。

---

# 9. Adoption 与状态持续

## P5-00：program-only factorial

在 exposed development 上先运行：

```text
candidate:
  FOLLOW
  COPY_CURRENT
  COPY_BASELINE
  FIRST_ISSUE_HOLD
  f(B)
  f(B,E)

protocol:
  base_bound
  persistent

adoption:
  always
  never
  change_epsilon
  robust_pointwise_harm_limit
```

不要调用模型。

### 输出

```text
proposal value
effective value
stale duration
override age
baseline revisions missed
help/harm
churn
lead time
gain source
```

### 目标

精确区分：

```text
candidate value
old-value persistence
adoption
baseline update
```

---

## P5-01：模型 adoption 后置

只有 program factorial 证明 adoption task 非平凡后，才增加一个模型 adoption arm。

固定：

- candidate；
- completion time；
- evidence；
- action universe。

模型只选择：

```text
FOLLOW
ADOPT
KEEP
```

不允许同时产生新概率，否则无法归因。

---

# 10. Independent confirmation

## P6-00：首轮确认矩阵保持最小

推荐：

```text
FOLLOW
best frozen common backend
best frozen full-evidence backend
best frozen simple active program
strong batch
one frozen model pipeline
```

模型 pipeline 只选一个研究角色：

- feature extraction + program aggregate；
- 或 selector + fixed program backend；
- 不同时更换所有组件。

### 不以开发正收益作为放行条件

模型即使开发负收益，也可以作为冻结对照进入一次确认；
但不再增加模型数量寻找赢家。

### 停止规则

- 按注册窗口执行；
- 失败保留；
- 无正例也结束并报告 underpowered；
- 不追加 outcome-selected 日期；
- 不重新调 prompt；
- 不选择性重试。

---

# 11. Temperature 第二主链

## P7-00：先做 process stability

对 2017 fit / 2018 development：

- month/season；
- warm/cold episode；
- station/region；
- lead；
- event duration；
- member trajectory；

进行分层。

保留：

- hot-day EMOS 退化；
- ice/frost 改善；
- repeated leads sharing outcome。

## P7-01：合法 evidence gate

当前 DWD final archive 不能恢复历史 revision availability。

合法选择：

1. prospective first-seen capture；
2. 具有 version/publication archive 的新产品；
3. 不做 active evidence，只保留 F-only。

禁止给 final archive 人工加固定时延后称 historical evidence。

## P7-02：temperature action task

即使没有 C1 evidence，temperature 仍可测试：

```text
连续 forecast updates
preparation deadline
resource capacity
persistent/adoption
```

但必须称：

```text
forecast-update decision task
```

不是 active evidence acquisition。

---

# 12. D：行动需要决定信息价值

## P8-00：Scenario Card

每个行动任务先写一页：

```text
user
asset/facility
weather target
forecast horizon
preparation action
duration
capacity
cost
cancel/cleanup
reversibility
decision deadline
rule source
research assumptions
```

写不清则不运行模型。

## P8-01：三组件隔离

```text
Weather Forecast Head
  weather evidence only
  no action cost / miss penalty / user preference

Acquisition Policy
  may see remaining feasible actions and DecisionSpec

Decision Policy
  sees admitted F + preparation state + DecisionSpec
```

增加 guard：

```text
same weather/evidence/predictor
different DecisionSpec
=> same F request hash and output
```

## P8-02：配对实验

同一天气、同一资料、同一 F，只改变：

- preparation duration；
- capacity；
- start deadline；
- action cost；
- cleanup cost；
- miss penalty；
- reversibility。

检查：

- F 不被 preference 污染；
- acquisition 合理变化；
- action 合理变化；
- 已不可改变目标停止昂贵搜索；
- 查询与准备可并行。

## P8-03：强程序基线

```text
no action
fixed threshold
earliest-deadline-first
rolling two-step
exact small optimizer
all-read
fixed schedule
event trigger
```

LLM 最后加入。

只报告 fixed DecisionSpec 下的 synthetic loss。

---

# 13. H07/H08 与 MM

## P9-00：MRMS

先关闭：

```text
accumulation start/end
issue/valid/available time
unit
quality flags
missing/no coverage
grid/spatial support
matched forecast
matched outcome
first-seen policy
```

之后比较同一原始资产：

```text
official numeric product
professional nowcast
structured features
regional image/VLM
local high-cost processing
```

## P9-01：HEFS

先证明：

```text
QINE meaning
member identity
instant/hourly average
regulated/unregulated
cross-section/station
units
flow/stage
threshold
availability
matched outcome
```

完整专业 forecast 是 common information，不能计为 charged acquisition gain。

---

# 14. Prospective shadow

## P10-00：program first

先运行：

```text
FOLLOW
f(B)
f(B,E)
COPY controls
best simple acquisition
```

预测必须在 outcome 前提交。

## P10-01：one frozen model

program 稳定后加入一个冻结模型，不向公众发布，不控制设备。

报告：

- true first-seen；
- network failures；
- actual duration；
- missing；
- version changes；
- before-outcome seal；
- post-outcome settlement。

---

# 15. Go / No-Go

## 新数据下载 Go

必须有：

- DATA_REGISTRATION；
- process-unit rule；
- fit/cal/eval/confirm roles；
- download cap；
- license；
- stop rule；
- no outcome-based selection。

## 新模型 Go

必须有：

- P0 fixes；
- replay optimization verified；
- strong backend frozen；
- E/F role fixed；
- copy/batch/program controls；
- exact call cap；
- no prompt tuning on confirmation；
- consumed launchers locked。

## Confirmation Go

必须有：

- formal provenance closure；
- provider outcomes；
- full manifest；
- process units；
- primary metrics；
- underpowered stop rule；
- frozen models/prompts/banks；
- no selective retry。

## Action model Go

必须有：

- Scenario Card；
- preference-blind F guard；
- exact/program baselines；
- nontrivial tradeoff；
- bounded multi-pending；
- synthetic scope disclosure。

---

# 16. 建议执行顺序

```text
V10A-00 post-closure baseline
→ V10A-01 formal provenance
→ V10A-02 API claim atomicity
→ V10A-03 provider policies
→ V10A-04 scorer/replay optimization
→ V10A-05 full regressions/capsules
→ V10B-00 data/process/confirmation registration
→ V10B-01 full-year acquisition
→ V10B-02 nested backend fit/calibration
→ V10B-03 process units
→ V10C-00 selector branch attribution
→ V10C-01 E composition to F
→ V10C-02 protocol/adoption factorial
→ V10D-00 bounded confirmation
→ V10E-00 temperature stability
→ V10F-00 action environment
→ V10G-00 MRMS/HEFS
→ V10H-00 prospective shadow
```

---

# 17. 首轮完成定义

CPU/offline 首轮结束时必须有：

1. `POST_V10_BASELINE.json`
2. `FORMAL_PROVENANCE_V2.md/json`
3. forged-journal red test
4. FormalRunReference scorer
5. formal contract hash in experiment invariants
6. atomic API claim
7. claim-incomplete recovery
8. truncated-body schema
9. strengthened DWD policies
10. preloaded-engine scorer
11. journal replay cache
12. performance profile
13. byte-identical score validation
14. 720+new tests
15. both capsules replay
16. next data registration draft
17. confirmation protocol draft
18. STOP_RECEIPT with zero external actions

这不表示：

- 独立确认完成；
- LLM 有 F 增益；
- action 有真实收益；
- temperature 有 C1；
- MRMS/HEFS 已准入；
- 16 类已完成。
