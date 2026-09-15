---
title: DisasterTrace v11 最新实现复查与 Codex 后续执行计划
plan_version: "v11-post-snapshot-audit-20260915"
planning_date: "2026-09-15"
language: zh-CN
repository: "sisuolv/disastertrace-benchmark"
branch: "next-phase-v1"
reference_commit: "889620a4fc4ee6ad70757dd3e832a40c7509126a"
reference_parent: "1fd6821fef15b26898a57c74d4715714f33ea779"
published_snapshot_at: "2026-09-15T12:06:47.602706+00:00"
review_scope: "current GitHub source, v11 in-progress snapshot, registered plans, saved receipts, tests and reports; no independent checkout rerun in this review"
current_phase: "v11 code gates completed; full-week and annual CPU/data work in progress in the published snapshot; confirmation unopened"
default_allow_network: false
default_allow_model_calls: false
default_allow_gpu: false
default_allow_paid_api: false
default_allow_training: false
supersedes:
  - "DisasterTrace_v10_Latest_Implementation_Audit_and_Codex_Plan_20260914_CN.md"
  - "plans that still treat formal run provenance, API final dispatch permission, or same-call replay deduplication as wholly unimplemented"
---

# DisasterTrace v11 最新实现复查与 Codex 后续执行计划

## 0. 可直接交给 Codex 的首轮指令

```text
仓库：sisuolv/disastertrace-benchmark
分支：next-phase-v1

本计划复查时远端 HEAD：

889620a4fc4ee6ad70757dd3e832a40c7509126a

该提交是 v11 的“代码修复、预检和进行中状态快照”，不是本批全部实验完成提交。

开始时必须重新读取真实远端 HEAD：
- 若仍为 889620a4...，按本计划执行；
- 若已前进，先生成从 889620a4... 到真实 HEAD 的差异审计；
- 不得 reset、覆盖或重启 v8/v9/v10/v11 已消费的 launcher；
- 不得把 GitHub 中的 2026-09-15T12:06:47Z 快照当作实时云平台状态。

先读：

1. disastertrace-starter/AGENTS.md
2. disastertrace-starter/CURRENT_PHASE.md
3. LATEST_PROGRESS_V11_CN.md
4. publication/v11_inprogress_20260915/PROGRESS_SNAPSHOT.json
5. publication/v11_inprogress_20260915/REVIEW_FOR_CHATGPT_PRO_CN.md
6. plans/v11_execution_20260915_01/README_CN.md
7. plans/v11_planning_20260915_01/OVERALL_PLAN_CN.md
8. plans/v11_planning_20260915_01/NEXT_BATCH_EXECUTION_CN.md
9. plans/v11_execution_20260915_01/c2_design_01/DESIGN.json
10. disastertrace-starter/IMPLEMENTATION_STATUS.md
11. disastertrace-starter/DECISIONS.md
12. disastertrace-starter/BLOCKERS.md
13. 本文件

第一批任务只允许 CPU/offline 和只读状态核验：

V11R-00 读取真实 HEAD、工作树、云任务和已有产物，建立 post-snapshot canonical status；
V11R-01 修正 CURRENT_PHASE，使其指向 v11，而不是继续显示 v10 为当前阶段；
V11T-02 修复温度目标、模型提示、产品可用时间和成员 lineage 的统一合同；
V11A-03 修复 API attempt 创建的 mkdir→reserve 崩溃窗口，并验证 dispatch/STOP 语义；
V11F-04 将正式评分与 legacy replay 的输出资格彻底分开，补全正式输入角色 manifest；
V11B-05 强化 calibration bank 合法性校验；
V11D-06 修复年度样例失败分支的重复结果计数，并登记单一缺片恢复 generation；
V11W-07 修正 fullweek 分组标签和配对矩阵，不重跑已完成轨迹；
V11Q-08 重跑实际唯一测试、当前源 capsule 和数值等价审计；
完成后停止，等待本轮已注册 CPU/数据任务自然终止或已有终态。

第一批禁止：

- 新 API 请求；
- 新 LLM 调用；
- GPU；
- 训练；
- 打开 Bay 2025-02-17 至 23；
- 读取任何新 confirmation outcome；
- 重新提交 v11 当前 fullweek shard；
- 覆盖芝加哥 2023-01 的原 429/timeout 失败；
- 修改 v10/v11 原始回答、journal、score、费用或失败；
- 将 71/72 地区月写成全年完成；
- 将 840 轨迹写成已完成，除非真实最终审计存在；
- 将 C2 的 72 prefixes 写成已完成分支实验：当前 branch_runs=0；
- 将 temperature 的等长 member arrays 写成已证明同一成员 lineage；
- 将 program/EMOS/ECC 写成 LLM 收益；
- 将 historical holdout 写成 prospective first-seen；
- 将任何研究性准备任务写成已证明减少真实灾害损失。

每个修复必须：

1. 先写在当前源码上失败的 red test；
2. 保存精确 nodeid、命令、退出码、JUnit、stdout/stderr 和 SHA256；
3. 保持旧 schema 只读可复算；
4. 不修改历史冻结目录；
5. 新输出使用新 generation/目录；
6. 更新 CURRENT_PHASE、IMPLEMENTATION_STATUS、DECISIONS、BLOCKERS；
7. 生成 STOP_RECEIPT，确认新模型/API/GPU/训练均为 0。
```

---

# 1. 当前真实起点

## 1.1 Git 状态

```text
branch = next-phase-v1
HEAD   = 889620a4fc4ee6ad70757dd3e832a40c7509126a
parent = 1fd6821fef15b26898a57c74d4715714f33ea779
message = Publish v11 code fixes, verified preflights and in-progress data status
```

v11 相对 v10 主要增加：

- FormalSession v2 运行来源绑定；
- formal journal/report/STOP 合同链；
- API 最后本地 dispatch permission；
- bounded-response hash scope；
- `_score_replayed`，单次评分中不重复加载同一 journal；
- temperature support validator；
- 当前源 fullweek/annual/C2 注册与运行材料；
- 进行中状态快照。

## 1.2 发布快照边界

当前 GitHub 发布的是：

```text
release_kind = in_progress_code_and_status_snapshot
all_work_complete = false
snapshot_at = 2026-09-15T12:06:47.602706Z
```

因此必须区分：

```text
COMPLETED CODE GATES
RUNNING/TERMINAL CPU JOBS
REGISTERED BUT NOT RUN
BLOCKED
NOT STARTED
```

不能用提交标题或计划文档替代真实 RESULT。

## 1.3 发布快照中的已完成内容

- 750 个唯一测试通过；
- 0 failures；
- 0 skips；
- 五组真实 preflight 完成；
- 360 条方法记录通过正式 replay 和独立算术审计；
- 九方法评分完整 replay 从 19 次降到 9 次；
- 同一 profile score hash 保持一致；
- 年度闰月三地区目录样例完成；
- C2 的 72 prefixes / 144 native E tasks 完成构建；
- 0 个新 benchmark model calls；
- Bay confirmation 未打开。

## 1.4 发布快照中的未完成内容

- fullweek 840 trajectories 当时仍在运行；
- fullweek final audit 尚未完成；
- annual catalog 71/72；
- Chicago 2023-01 失败；
- annual native sample 0/3 complete；
- full-year native data 未完成；
- annual fit 未完成；
- C2 branch runs = 0；
- C2 F scoring 未完成；
- temperature lineage 尚未完整绑定；
- 新 LLM selector 未注册执行；
- independent confirmation 未打开；
- action、H07/H08、prospective model 未开始。

---

# 2. 总体正确性判断

## 2.1 当前可以认可的部分

### FormalSession v2

当前正式运行已经能绑定：

- data canonical hash；
- bank canonical hash；
- source/code manifest；
- comparison contract；
- provider policy；
- report；
- STOP；
- journal；
- event replay；
- original run directory。

`score_formal` 默认要求 run references；旧日志只有显式 `legacy=True` 才能复算。

这是对 v10 正式 provenance 缺口的真实修复。

### API 最后发送门槛

当前 API 路径在短临界区内：

1. 检查原 reservation；
2. 检查 request identity；
3. 检查 deadline；
4. 检查 STOP；
5. 持久化 dispatch intent；
6. 释放临界区；
7. 执行 HTTP。

成功/错误 body、截断范围、费用和未决 reservation 分开保存。

### 单次评分 replay 去重

当前逻辑：

```text
score_admitted(paths)
  -> load engines once
  -> _score_replayed(engines)
```

formal scorer 也复用同一组已 replay engines。

单个真实 profile：

```text
from_journal calls: 19 -> 9
wall time: 1256.0s -> 554.6s
score hash: identical
```

只能称单案例实测，不能称全局 2.26×。

### fullweek 设计

第一轨使用：

```text
FOLLOW
F_COMMON
F_BASE_ONLY
B11_BATCH
B11_COVERAGE
```

并保留：

- 12 region-weeks；
- 7 天；
- 两阈值；
- 逐日独立 session；
- 48 queries/day；
- complete denominator；
- missing outcome sensitivity；
- positive/negative contribution；
- no hourly bootstrap claim。

方向正确。

### C2 状态分支设计

当前 DESIGN 已绑定：

- same clock；
- spent/reserved budget；
- authorization；
- cache；
- pending；
- current baseline；
- current override；
- source versions；
- failure continuation policy。

并明确：

```text
hindsight path = diagnostic only
unavailable branch = not evaluable
pending original invocation = finish/poll, never duplicate
```

设计正确，但目前没有执行真实 branch。

## 2.2 当前不能认定为已完成的能力

- exact temperature target contract；
- temperature member lineage；
- formal temperature result policy；
- atomic claim creation；
- arbitrary distributed STOP/dispatch transaction；
- portable formal path remapping；
- fullweek scientific result；
- full-year bank；
- C2 F attribution；
- independent weather-process inference；
- LLM selector gain；
- action-aware information value；
- prospective forecast evaluation；
- 16-hazard complete release。

---

# 3. 确定性问题与残余风险

# P0：继续新模型/API/确认前必须处理

## P0-01：`CURRENT_PHASE.md` 仍把 v10 写成当前阶段

### 证据

最新提交已经是 v11，但：

```text
# Current phase: v10 experiments closed, 2026-09-14
```

仍位于 `CURRENT_PHASE.md` 顶部。

### 风险

仓库要求 Codex 优先读取 CURRENT_PHASE。它可能：

- 忽略 v11；
- 读取旧的 720 tests；
- 误认新实验仍关闭；
- 选择 v10 next plan；
- 错误处理当前 running jobs。

### 修复

将 CURRENT_PHASE 改为短 pointer：

```text
Current published phase:
  v11 in-progress snapshot at <timestamp>

Current Git commit:
  <sha>

Canonical published status:
  publication/v11.../PROGRESS_SNAPSHOT.json

Live status:
  must be re-observed; published snapshot does not auto-update

Consumed/closed:
  v8/v9/v10 and v11 registered launch IDs

Current next action:
  finish/audit registered CPU scope; no automatic LLM/API/confirmation
```

历史长文移动到 archive pointer，不删除。

---

## P0-02：温度模型提示与新目标合同不一致

### 当前源码

`TEMPERATURE_SYSTEM` 仍硬编码：

```text
3-day hot: all daily maxima >= 30C
3-day ice: all daily maxima < 0C
```

而 v11 新路径试图由 target row/contract 定义具体变量、窗口、operator 和 threshold。

### 风险

新模型任务如果复用该 prompt：

```text
registered target != model instruction
```

模型即使按提示正确回答，也可能被目标 evaluator 判错。

### 修复

不要保留一个硬编码阈值的通用 prompt。

新增：

```python
def render_temperature_prompt(contract: TemperatureTargetContract) -> str:
    ...
```

必须从冻结 contract 渲染：

- variable；
- aggregation；
- exact UTC support；
- operator；
- threshold；
- day count；
- day0 policy；
- member-joint rule；
- target hash。

旧 v10 prompt 保留为：

```text
temperature_prompt.legacy_v10
```

不得回写原 capture。

### 测试

- prompt threshold/operator 与 target 一致；
- prompt target hash 与 registry 一致；
- 任意 target change 改变 prompt hash；
- old captured task remains legacy；
- no hard-coded 30/0 in new dynamic path。

---

## P0-03：`temperature_contract.py` 仍不是“精确目标合同”

当前 validator 只要求：

- Celsius；
- UTC midnight；
- allowed variable name；
- one/three-day duration；
- `ge/lt`；
- finite threshold；
- unique target dates；
- positive day index；
- complete member arrays；
- equal member counts。

它没有绑定：

- 每种 event 的允许 operator；
- 每种 event 的 frozen threshold；
- product issue identity；
- available_at <= cutoff；
- same forecast issue；
- member IDs/order；
- ensemble configuration；
- result product policy；
- source revision。

### 影响

一个错误 target 如：

```text
daily max < arbitrary threshold
```

仍能通过。

等长数组也不能证明三天的第 i 个值属于同一个 member。

### 修复

实现版本化 schema：

```text
TemperatureTargetContract.v2
TemperatureProductContract.v2
TemperatureMemberLineage.v1
```

字段：

```text
target_id
event_family
variable
daily_extreme_kind
aggregation
operator
threshold
units
physical_start/end
utc_day_count
cutoff
forecast_issue_id
forecast_issue_time
available_at
ensemble_id
member_ids
provider
provider_version
result_policy
```

验证：

```text
available_at <= cutoff < physical_start
same issue across event days
same ordered member_ids across days
member vector length == len(member_ids)
daily product date exactly covers target
no extra/missing day
```

### 旧结果影响

先做只读 impact scan：

```text
UNCHANGED
AFFECTED
UNAVAILABLE_TO_VERIFY
```

没有证据违反 lineage 时，不宣称旧结果错误；但也不升级为正式 lineage-qualified。

---

## P0-04：两个 temperature probability 入口对 max-only packet 的资格不一致

当前：

- `temperature_ensemble_probability()` 可对只含 max 的合法 target 工作；
- `temperature_postprocess.event_probability()` 又调用 `validate_products()`，
  后者强制同时存在 min 和 max。

### 选择一种明确语义

方案 A：

```text
Raw event probability:
  only require consumed field

ECC/EMOS joint min-max processing:
  require both min and max
```

方案 B：

```text
All formal product packets always require both
```

推荐方案 A，因为最小输入原则更清楚。

为 raw、EMOS、ECC 分开 schema，不让辅助 helper 隐式提高 formal 要求。

---

## P0-05：DWD outcome policy 仍未绑定具体温度变量和事件构造

`dwd_daily_archive.v1` 主要检查：

- Celsius；
- interval；
- future physical；
- reference kind；
- quality；
- publication/fetch chronology。

没有精确绑定：

- tmax / tmin；
- daily event；
- duration event；
- UTC-day aggregation；
- threshold；
- result construction。

### 修复

拆成：

```text
dwd_daily_tmax_archive.v2
dwd_daily_tmin_archive.v2
dwd_daily_event_archive.v2
dwd_duration_event_archive.v2
```

只有最后两项可以结算 event probability target。

---

## P0-06：API claim 仍有 mkdir→reserve 崩溃窗口

当前：

```python
attempt_dir.mkdir(exist_ok=False)
write reserve.json
```

若进程在两步之间终止：

- 目录存在；
- reserve 不存在；
- 同 call ID 无法重新 claim；
- reducer 将目录计为 claimed/unresolved；
- 没有版本化 `CLAIM_INCOMPLETE`。

### 修复

推荐 staging + rename：

```text
attempts/.claiming/<nonce>/
  claim.json
  reserve.json
fsync
rename -> attempts/<call_hash>/
fsync parent
```

或者首先原子发布：

```text
claims/<call_hash>.json
```

再建立 attempt。

### 必须注入的 kill points

```text
before claim
after staging mkdir
after claim receipt
after reserve
after request
after dispatch intent
before HTTP
after response.raw
after wire
after billing
before terminal
```

每个状态都必须：

- 可解释；
- 不免费重发；
- 不释放未知费用；
- 不永久伪装为成功；
- reducer 可稳定重算。

---

## P0-07：dispatch gate 仍依赖共享 `fcntl.flock`

短临界区比旧共享费用 JSON 安全得多，但仍应明确：

```text
local/AFS observed gate
!=
general distributed transaction
```

在真实部署路径做：

- same-node stress；
- two-node shared-AFS stress；
- process kill while holding lock；
- STOP/permit race；
- lock timeout；
- stale file handle。

若跨节点 flock 语义无法可靠证明，改为：

- single dispatch owner；
- atomic permission generation；
- transactional local queue；
- provider idempotency key。

本批没有新 API，不用为验证重开旧任务。

---

## P0-08：formal 与 legacy score 的结果本身未携带清楚资格

当前：

```python
score_formal(..., legacy=True)
```

可以显式复算旧日志，但返回结果 schema 与正式 provenance score 没有足够明显的资格差异。

### 修复

拆开公开入口：

```text
score_formal_runs(...)
score_legacy_replay(...)
```

结果必须包含：

```text
qualification:
  formal_bound
  legacy_replay
run_reference_hash
provider_policy
provenance_complete
```

publication validator 禁止把 legacy_replay 填入 formal 主表。

---

## P0-09：正式终态没有显式要求 `done/completed`

`_verify_run_reference` 验证 STOP、report、contract、journal hash，
但没有显式要求：

```text
STOP.done == true
STOP.reason == completed
```

`_score_replayed` 最终会要求完整 snapshots，所以大多数 partial run 会被拒绝，
但终态语义仍不够自解释。

### 修复

支持三种正式终态：

```text
COMPLETED
FAILED_WITH_REGISTERED_FALLBACK
INCOMPLETE_NOT_COMPARABLE
```

只有前两种可进入完整比较；后一种保留分母但阻止完整排名。

---

## P0-10：年度样例失败时重复拼接 sample rows

当前：

```python
results = sample + (
    list(pool.map(...)) if sample_ok else sample
)
```

sample 失败时得到：

```text
sample + sample
```

虽然 `passed` 仍为 false、not_attempted 基本可识别，但：

- completed count 可能重复；
- failure rows 重复；
- machine summary 不再一任务一行。

### 修复

```python
results = sample
if sample_ok:
    results += list(...)
```

增加：

```text
unique unit IDs
exact 72-unit roster
no duplicate result rows
completed + failed + not_attempted == expected
```

---

## P0-11：fullweek PLAN 的 group label 错把 FOLLOW 放入 same_values_bank

当前 PLAN metadata：

```text
same_values_bank:
  FOLLOW
  F_BASE_ONLY
  B11_BATCH
  B11_COVERAGE
```

FOLLOW 不使用 values feature bank。

### 正确分层

```text
professional_baseline:
  FOLLOW

common_backend:
  F_COMMON

same_values_backend:
  F_BASE_ONLY
  B11_BATCH
  B11_COVERAGE
```

分析脚本当前没有依赖该 group 做主分数，因此不要求重跑轨迹；
修正 metadata、审计和报告即可。

---

## P0-12：fullweek pair table 缺少最关键的 base-only vs batch

当前 PAIRS 包含：

```text
F_BASE_ONLY vs B11_COVERAGE
B11_BATCH vs B11_COVERAGE
```

但缺：

```text
F_BASE_ONLY vs B11_BATCH
```

这正是同 values 后端下“全读证据是否有价值”的强对照。

### 建议完整 paired decomposition

```text
FOLLOW vs F_COMMON
FOLLOW vs F_BASE_ONLY
F_COMMON vs F_BASE_ONLY         # different bank, clearly labeled
F_BASE_ONLY vs B11_BATCH        # same backend, full evidence effect
F_BASE_ONLY vs B11_COVERAGE     # same backend, active evidence effect
B11_BATCH vs B11_COVERAGE       # selection vs all-read
```

所有 pair 需要：

- all；
- week；
- region；
- region-week；
- region-day；
- positive/negative contribution；
- missing sensitivity；
- changed predictions。

---

## P0-13：calibration bank validator 可接受非法第一块概率

当前 monotone bank validation：

```python
previous = -1.0
previous <= block["value"] <= 1
```

因此第一块 value 可为负数。

还没有验证：

- lower/upper 按序；
- block 不重叠；
- 完整覆盖或外推规则；
- value >= 0；
- finite probability output。

### 修复

```text
0 <= value <= 1
0 <= lower <= upper <= 1
lower/upper sorted
non-overlap
documented gaps/tail policy
apply output in [0,1]
```

对现有 banks 做只读 audit；生成器正常不代表 validator 可省略。

---

# 4. 已披露但仍未关闭的科学门槛

## 4.1 fullweek 尚无最终科学结果

发布快照只说明运行中。

不得把：

```text
expected trajectories = 840
```

写成：

```text
completed trajectories = 840
```

退出需要：

- exact case roster；
- exact arm roster；
- 60,480 method rows；
- complete journals；
- common settlement masks；
- independent arithmetic；
- final resource state；
- seasonal/positive/negative decomposition。

## 4.2 annual 只有目录，不是全年原文和 fit

当前：

```text
71/72 region-month catalogs
one failed
native sample incomplete
fit incomplete
```

目录成功不等于：

- raw TAF fetched；
- task joined；
- result qualified；
- footprint purged；
- model fitted；
- calibration complete。

## 4.3 C2 当前没有分支结果

当前：

```text
registered_prefixes = 72
native E tasks = 144
branch_runs = 0
F_scored = false
```

而且 72 coverage tasks 全是 full。

当前只能说：

> task construction and development protocol registration pass.

不能说：

- branch attribution 完成；
- partial evidence difficulty 成立；
- E improves F；
- LLM selector improves anything。

## 4.4 2023/2024/2025 分期仍属于 adaptive development lineage

推荐角色：

```text
2023 = fit + internal selection
2024 = final calibration
2025 exposed = development
unread data = confirmation
```

但 no-year feature family、合同澄清等方向已经受 2025 exposed findings 启发。

因此：

- 2023/2024 可用于构建下一版 frozen system；
- 不能写成一开始完全预注册；
- 2025 仍是 exposed development；
- 最终主张必须来自新冻结 confirmation。

## 4.5 region-week 不是独立天气过程

当前只有四个 global weeks。

需要两级依赖单位：

```text
mechanical dependency block
meteorological/process grouping
```

无法可靠识别 process 时，使用保守 region-week/global-week 并做多种 sensitivity，
不能用 12 region-weeks 自动声称 12 independent processes。

---

# 5. 第一阶段：立即修复与当前运行收尾

## V11R-00：真实状态基线

### 任务

- fetch remote HEAD；
- git status/index/dirty；
- 读取平台真实 job state；
- 核对 published snapshot 与 live observation；
- 不从快照推断当前仍运行；
- 不从平台 SUCCEEDED 推断 scientific pass。

### 输出

```text
POST_SNAPSHOT_BASELINE.json
LIVE_PLATFORM_OBSERVATION.json
PROTECTION_MANIFEST.json
CONSUMED_LAUNCHERS.json
```

## V11R-01：状态导航修复

- CURRENT_PHASE 指向 v11；
- 保存 snapshot timestamp；
- 区分 published / live / terminal；
- 历史 v10 内容移为 archive section；
- root README 与 current pointer 一致。

## V11T-02：temperature contract v2

交付：

```text
temperature_contract_v2.py
temperature_prompt_v2.py
temperature_product_schema_v2.json
temperature_lineage_audit.py
TEMPERATURE_IMPACT_REPORT.json
TEMPERATURE_IMPACT_REPORT_CN.md
```

先不重跑模型。

## V11A-03：API atomic claim

交付：

```text
api_ledger.v3
claim state machine
kill-point tests
two-node AFS gate test
legacy v2 reader
API_IMPACT_REPORT.json
```

新 schema 不修改旧 receipts。

## V11F-04：formal qualification v3

交付：

```text
FormalInputManifest
FormalRunReference
score_formal_runs
score_legacy_replay
formal qualification field
portable content-address mapping
```

旧 formal v2 保持复算。

## V11B-05：bank validation

修复 calibration blocks，并只读审计所有现有 bank。

## V11D-06：annual script repair and recovery registration

- 修复 duplicated sample rows；
- 保留 Chicago 2023-01 原失败；
- 创建独立 recovery generation；
- 仅登记缺失 request；
- 同 URL/source/time scope；
- 不因内容或 outcome 选择；
- merge manifest 引用原失败和新 recovery。

## V11W-07：fullweek analysis correction

- 修 group metadata；
- 补 pair matrix；
- 不修改 trajectory；
- final audit 使用 revised analysis source hash；
- old analysis attempt 若已运行则保留。

## V11Q-08：回归

运行：

```text
actual current monitoring suite
new P0 tests
formal forged-run tests
API kill-point tests
temperature target/prompt/lineage tests
annual roster tests
fullweek pair-analysis tests
portable capsule current-source migration
Ruff/type/static checks
```

报告 actual unique node IDs，不预填 750/787 等固定数。

---

# 6. 第二阶段：完成当前已注册 CPU/数据范围

## V11C-09：只读收尾 fullweek

不得重启已有 shard。

最终状态：

```text
completed
failed
not_attempted
unknown platform
```

任何缺片：

- 保留；
- 不选择性补模型；
- CPU deterministic missing shard 只有在预登记恢复规则允许且原 request identity 明确时，
  才建立新 generation；
- 原失败不覆盖。

## V11C-10：fullweek final science report

主表：

```text
threshold
arm
registered
settled
missing
positive
negative
Brier
calibration
changed predictions
source queries
declared latency
actual CPU runtime
```

分层：

```text
global week
region
region-week
region-day
positive/negative contribution
worst block
missing sensitivity
```

重要判断：

- BATCH vs BASE_ONLY 是否显示证据内容价值；
- COVERAGE vs BASE_ONLY 是否显示预算内价值；
- COVERAGE vs BATCH 是否显示选择价值；
- FOLLOW vs research backend 是综合差值，不是纯 acquisition。

## V11C-11：annual catalog recovery and native sample

- 完成一份 exact 72-unit status；
- recovery generation 单列；
- native sample 三个月逐原文；
- parser failures retained；
- no fit until exact dependency audit passes。

---

# 7. 第三阶段：全年强后端

## V11B-12：角色和 purge

### 角色

```text
2023:
  fit + internal blocked CV

2024:
  final calibration only

2025:
  permanently exposed development

confirmation:
  unread continuous windows
```

### 完整 footprint

每个 target 使用：

```text
TAF issue/effective window
METAR lookback
result support
derived parent assets
shared source assets
state persistence
calibration target
```

跨角色有任何 footprint overlap：

```text
drop or isolate
```

不只按年份或 24h buffer。

## V11B-13：candidate limits

首批只允许：

```text
FOLLOW research mapping
f_common(B)
f_mask_age(B,E)
f_values(B,E)
f_values_no_year(B,E)
one common-anchored residual candidate
```

不要扩展成无界 feature search。

## V11B-14：训练所有部署模式

fit/calibration 分布必须覆盖：

```text
no evidence
one slot
two slots
missing report
censored visibility
stale evidence
conflict
failed query
late evidence
```

每种模式有：

- target count；
- positive count；
- process/block count；
- fit/cal/eval role；
- out-of-distribution diagnostics。

## V11B-15：calibration discipline

- feature/regularization selection only in 2023 internal CV；
- 2024 only maps selected frozen candidates；
- no candidate ranking by 2024 final calibration score；
- raw probability primary；
- PAV/CDF secondary；
- no policy-specific post-selection calibration unless separately registered。

## V11B-16：independent arithmetic audit

另一实现重建：

- features；
- coefficients；
- raw probabilities；
- calibration；
- nested threshold coherence；
- outcomes；
- Brier；
- missing masks。

---

# 8. 第四阶段：C2 真实同状态分支

## V11C2-17：输入状态 census

在完整 exposed calendar 上，按 input state 分类，不按 outcome：

```text
TAF full coverage
partial coverage
withdrawn/current unavailable
same-issue conflict
version replacement
one valid neighbor
two valid neighbors
missing
censored
stale
```

主自然日历全部保留。

为机制开发可取固定每 strata 上限，但：

- 规则先冻结；
- selection source only；
- 不读 F outcome；
- 报告 strata prevalence；
- 不能并入自然 prevalence。

## V11C2-18：actual branches

对每个 prefix：

```text
B0 no further query
B1 first legal slot
B2 second legal slot
B3 all remaining legal slots
B4 deterministic process-only transform, if registered
```

继承：

```text
clock
spent/reserved
quotas
authorization
cache
pending
baseline
override
failure policy
```

保存：

```text
PARENT_STATE.json
BRANCH_INTERVENTION.json
BRANCH_JOURNAL
BRANCH_SCORE.json
```

## V11C2-19：因果链

逐 opportunity 输出：

```text
native field changed?
feature vector changed?
probability changed?
candidate admitted?
effective before cutoff?
loss changed?
cost changed?
```

分类：

```text
no new field
field changed but feature-insensitive
feature changed but mapping-insensitive
probability changed but not admitted
admitted too late
effective and helpful
effective and harmful
```

## V11C2-20：selector regret

比较：

```text
no-query
batch
round-robin
risk
coverage
one-step expected loss program
two-step finite lookahead
LLM selector later
hindsight finite oracle diagnostic
```

分解：

```text
acquisition regret
extraction regret
aggregation regret
mapping regret
adoption regret
timing regret
```

oracle 不进入 deployable ranking。

---

# 9. 第五阶段：有界模型实验

## Go 条件

只有同时满足：

1. fullweek final audit 完成；
2. annual backend frozen；
3. C2 branches 实际运行；
4. BATCH/active evidence 能改变 prediction；
5. source/action universe nontrivial；
6. all P0 closed；
7. no confirmation opened。

## V11M-21：单一 235B selector

建议上限：

```text
12 exposed development sessions
24 decisions/session
288 benchmark requests
<=2 compatibility calls
```

固定：

```text
backend
query universe
budget
forecast schedule
prompt
output schema
adoption
failure policy
```

强对照：

```text
batch
round-robin
risk
coverage
one-step program
two-step program
```

不做：

- multiple model scale sweep；
- predictor+selector simultaneously changed；
- post-result prompt fix；
- selective retry；
- API fallback counted as model answer。

## V11M-22：输出

报告：

```text
legal selection
field acquisition
F loss
event/background
process blocks
source queries
model tokens
generation batches
actual delivery
missed cutoffs
fallbacks
cost
```

无收益是有效结论。

---

# 10. 第六阶段：冻结确认

## V11X-23：confirmation protocol

在读取 outcome 前冻结：

```text
code commit
source/data manifest
banks
models
prompts
selectors
predictors
protocol
adoption
budgets
process units
metrics
multiplicity
missingness
retry policy
stop rule
max calendar
```

## V11X-24：Bay role

Bay 2025-02-17..23：

- 只能承担窄的冬季/地区确认；
- 不能承担全年、跨地区和第二过程；
- 未读不代表模型预训练未见；
- 若无正例，报告 underpowered；
- 不追加 outcome-selected dates。

建议另预登记：

```text
one or more continuous unseen seasonal windows
```

不可按 outcome 挑选。

## V11X-25：最小确认矩阵

```text
FOLLOW
best frozen common backend
best frozen full-evidence backend
best simple active program
strong batch
one frozen model pipeline
```

不再做规模 sweep。

---

# 11. 第七阶段：行动需要决定信息价值

这是后续最值得押注的 novelty，但第一版必须程序化、可审计。

## V11D-26：Scenario Card

每个任务写清：

```text
user
asset/facility
weather target
decision horizon
preparation actions
duration
capacity
resource units
cancel/cleanup
reversibility
deadline
rule source
research assumptions
```

写不清不运行模型。

## V11D-27：三头隔离

```text
Weather Forecast Head
  sees weather evidence only
  cannot see action cost/miss penalty/user preference

Acquisition Policy
  sees current F, feasible actions, remaining time and DecisionSpec

Decision Policy
  sees admitted F, preparation state and DecisionSpec
```

必须有 guard：

```text
same weather/evidence/predictor
different DecisionSpec
=> identical F request hash and F output
```

## V11D-28：同一天气，不同准备要求

固定天气和 evidence，只改变：

```text
preparation duration
capacity
start deadline
action cost
cleanup cost
miss penalty
reversibility
```

检查：

- long-duration target 是否更早行动；
- short-duration target 是否允许等待；
- resource scarcity 是否改变 query priority；
- impossible-to-change target 是否停止昂贵查询；
- weather probability 是否保持 preference-blind。

## V11D-29：程序基线

```text
no action
fixed threshold
earliest-deadline-first
fixed schedule
event trigger
all-read
rolling two-step
exact small optimizer
```

LLM 最后加入。

## V11D-30：分开评分

### Forecast

```text
Brier
calibration
continuous/distribution score where applicable
```

### Action

```text
preparation completed in time
required target missed
wasted resource time
invalid cancellation
capacity violation
action churn
```

### Operation

```text
source bytes
processing
model calls
actual completion
waiting
late information
```

不把三项强行压成一个未审查权重总分。

---

# 12. 第二物理过程与多模态

## Temperature

先保持 F-only：

- exact target/product/lineage；
- EMOS/ECC；
- process/season stability；
- persistent/adoption；
- research preparation task。

没有 qualified historical evidence 时不做 temperature C1。

## H07 MRMS

先关闭：

```text
accumulation start/end
valid/issue/available time
units
QC
grid support
missing/no coverage
matched forecast
matched outcome
first-seen
```

同一 raw asset 比较：

```text
official numeric
pysteps/professional nowcast
structured features
regional image/VLM
local high-cost processing
```

## H08 HEFS

先证明：

```text
QINE semantics
member identity
instantaneous/hourly mean
regulated state
cross-section
flow/stage
units
threshold
availability
matched outcome
```

完整专业 forecast 是 common，不计 charged evidence gain。

## MM

首个目标不是 VLM score，而是：

```text
an image actually enters one qualified future-target loop
```

原图、专业产品、结构化处理和 VLM 必须同资产对照。

---

# 13. Prospective shadow

## V11P-31：program first

提前提交：

```text
FOLLOW
f(B)
f(B,E)
COPY controls
best simple acquisition
```

结果后成熟。

## V11P-32：one frozen model

program 稳定后加入一个模型。

只记录，不发布预警、不控制设备。

保存：

```text
first-seen
network failure
actual duration
missing
version updates
before-outcome seal
post-outcome settlement
```

---

# 14. Go / No-Go

## 新 API No-Go

直到：

- atomic claim；
- two-node dispatch/STOP test；
- explicit incomplete state；
- legacy receipts preserved；
- fixed call cap；
- no unknown-fee recycling。

## 新 LLM No-Go

直到：

- fullweek result；
- annual backend；
- C2 actual branches；
- nontrivial information value；
- dynamic target prompt；
- strong program baselines；
- exact model roster。

## Confirmation No-Go

直到：

- process groups；
- freeze manifest；
- methods fixed；
- metrics fixed；
- no prompt/backend tuning；
- max continuous calendar fixed；
- underpowered stop rule。

## Action LLM No-Go

直到：

- Scenario Card；
- preference-blind F；
- program/optimizer baselines；
- nontrivial resource conflict；
- action state transitions；
- bounded concurrency if required。

---

# 15. 论文主张

## 当前可主张

> DisasterTrace 已建立可审计的持续天气监测与回放框架，能够区分共同专业信息、
> 补充资料获取、原生字段提取、逻辑归约、概率映射、状态持续和采用规则。
> 现有开发实验发现，大模型预测常复制可见基线；提取更准确也不必改善未来预测；
> 补证价值又依赖后端、季节和天气块。

## 当前不可主张

- LLM 提高了 H15/temperature F；
- active selector 跨过程优于 batch/program；
- fullweek v11 已完成；
- annual fit 已完成；
- C2 branch attribution 已完成；
- temperature member lineage 已正式验证；
- heldout/prospective 已完成；
- action 减少真实损失；
- 16 hazards 已完成同深度闭环。

## 最值得争取的最终贡献

1. **真实监测任务**  
   多目标、异步资料、时间/预算/处理选择和预测更新。

2. **可验证失败归因**  
   从同一状态实际重跑资料、处理、预测和采用路径。

3. **行动条件下的信息价值**  
   同一天气、不同准备要求，检查获取策略变化且 F 不被偏好污染。

4. **跨物理过程与前瞻验证**  
   至少两条完整链、独立过程、提前提交。

---

# 16. 推荐执行优先级

```text
1. CURRENT_PHASE / canonical status
2. temperature prompt + exact contract + lineage
3. API atomic claim
4. formal vs legacy qualification
5. annual roster bug + recovery generation
6. fullweek grouping/pair analysis
7. actual regression/capsule
8. finish and audit current registered CPU scope
9. annual strong backend
10. fullweek scientific interpretation
11. C2 actual state branches
12. program selector regret
13. one bounded 235B selector
14. frozen confirmation
15. minimal action environment
16. temperature decision track
17. MRMS/HEFS/MM
18. prospective shadow
```

---

# 17. Codex completion template

```markdown
# <TASK_ID> Completion

## Frozen Starting Point
- remote HEAD:
- local HEAD:
- dirty/index:
- published snapshot:
- live platform observation:
- consumed launchers:
- protected artifacts:

## Scope
- allowed:
- prohibited:
- network:
- API:
- model:
- GPU:
- training:
- confirmation:

## Red Tests
- node IDs:
- commands:
- exits:
- receipts:
- hashes:

## Changes
- source:
- schema:
- migration:
- legacy reader:
- frozen artifacts unchanged:

## Green Tests
- targeted:
- full unique suite:
- capsule:
- arithmetic:
- lint/type:
- skips:

## Data/Execution
- registered:
- completed:
- failed:
- not_attempted:
- unresolved:
- no duplicate IDs:
- resource terminal:

## Scientific Impact
- unchanged:
- affected:
- unavailable to verify:
- claims strengthened:
- claims weakened:
- still blocked:

## Gate
- GO / NO-GO:
- next exact task:
```

---

# 18. 第一批完成定义

首轮 CPU/offline 结束必须交付：

1. updated CURRENT_PHASE；
2. post-snapshot canonical status；
3. protected/consumed launcher manifest；
4. dynamic temperature prompt；
5. exact temperature target/product/member schema；
6. historical temperature impact scan；
7. atomic API claim；
8. claim kill-point matrix；
9. dispatch/STOP two-node test；
10. formal vs legacy qualification output；
11. role-aware portable formal manifest；
12. stronger DWD policies；
13. calibration validator fix；
14. annual sample duplicate fix；
15. missing-month recovery registration；
16. fullweek metadata correction；
17. complete fullweek pair matrix；
18. actual unique regression result；
19. capsule/current-source migration result；
20. STOP_RECEIPT with zero new external actions。

完成这些仍不表示：

- fullweek scientific result；
- annual bank；
- C2 branch result；
- LLM gain；
- independent confirmation；
- action value；
- temperature C1；
- H07/H08 formal task；
- complete 16-hazard release。
