# DisasterTrace v7：基于当前工作的 Codex 实施总计划

- 制定日期：2026-09-13。
- 本次实际核对的远端：`sisuolv/disastertrace-benchmark`，`next-phase-v1@60ebd05723f9483590611976d379da2e4edd85b0`。
- 性质：供 Codex 执行的设计与工作包，不是已经实施的代码或实验报告。
- 保留：v7、C1/C2/C3、X00—X09、六组16类灾害、全部历史冻结输入和负结果。
- 输入：用户新增的“区域值班、资料与处理选择、真实分支对照”建议 A，以及“有准备时间、资源占用、撤销成本的准备任务”建议 B。原始文件及 SHA256 见 `SOURCES_AND_BASELINE.json`。
- 本次核查范围：当前分支元数据、最新 NEXT_PLAN／执行报告、固定类型状态与评分、独立 heads、旧 EventJournal，以及列出的官方文档与论文摘要。没有重跑仓库测试、恢复完整原始大数组、运行模型或修改远端。

## 0. 给实施代理的首要指令

这是在已有项目上做集成与有限扩展，不是新建第三套 benchmark。先读当前工作树及最新报告，再按任务依赖实现。若本地 HEAD、暂存区或工作副本与本计划不同，登记差异并保留已有内容；不要回退到本文提交来覆盖进度。

本计划不构成新的 GPU、模型训练、付费接口、长期采集、批量下载、仓库推送或实际应急操作授权。默认可以进行本地只读核查、隔离的代码实现和 CPU 测试。需要外部资源的工作包列明端点、对象、时窗、数量和上限，在有当前有效授权时执行；没有授权就保存 BLOCKED 原因并继续不依赖它的本地工作，不伪造样本或反复等待。

禁止 `git reset --hard`、`git clean`、覆盖用户暂存、改写历史输出、复用已消费 GPU launch ID、自动 push。不得把 token、密钥或临时带凭据下载地址写入发布材料。

**第一批默认实施 C00—C05；C08 的合成准备状态测试可按依赖并行。不要默认执行全部20个工作包。** 首批必须交付代码、测试、实际回执和未完成项，而不只是再生成一份计划。C06—C07 尽量复用已有本地真实资产；模型工作包 C12/C16 另受授权与科学前置条件约束。

## 1. 两份 novelty 建议的取舍与最终对象

### 1.1 共同主问题

在持续更新的共同专业预报上，一个系统如何为多个固定未来目标选择资料、处理工具与处理深度，并在时间和共享资源约束下形成值得采用的预测和研究性准备安排？哪些作用能由同前缀重跑验证？

### 1.2 不能静默混合的两份建议

建议 A 强调资料与计算的监测分配，主交付为预测、可追溯提醒及相同状态的替代路径。建议 B 实质增加了可改变后续状态的准备动作：它有时长、占用和撤销成本。B 不是给 A 多加一个字符串字段，也不是仅将成本损失公式换名。

采用分层实施：

| 层 | 计划位置 | 参考与解释 |
|---|---|---|
| E：证据支持 | 保留、接通现有 C2，并增加与预测输入直接相关的合同 | 认证有限合法产品事实，不认证未来概率或行动安全 |
| F：未来预测 | 继续为主轨；固定时刻/窗口、完整机会、合法提交 | 合格观测或明示的产品/报告参考 |
| D0：提醒与旧截止决定 | 保留旧版本；结构化提醒清单只作日志/辅助界面 | 发出提醒不等于完成准备，不等于已帮助真实值班人员 |
| D1：研究性准备 | 本计划新增；少数合格场景、公开假设、可执行状态机 | 真实天气结果 + 研究准备模型，二者分开报告 |
| D2：联合风险/复合后果 | 条件扩展 C18，不能阻塞第一版 | 需要匹配的联合结果与真正依赖相关性的损失 |

不模拟人群疏散、不控制水库、机场或道路，不自动通知公众，不把研究损失换算成已减少的真实财产损失或伤亡。业务规则/典型案例的专家审查是后续应用验证，不要求新增逐题人工标签，也不是当前自动评测的硬前置。

### 1.3 候选贡献保持 C1/C2/C3

- C1：共同预报持续变化时，资料选择、处理选择与研究准备的相互作用是否带来及时、资源可承受的增量。没有正增量同样可发布。
- C2：从相同完整监测状态重跑真实可执行路径，分开数据、感知/处理、预测、修订与动作调度的影响。不是模型自述错误原因，不把相互作用分解成相加100%的原因占比。
- C3：同一协议在不同物理过程、不同信息条件与独立时段中是否成立，并最终满足原六组16类分级发布要求。

动态监测、信息获取、固定材料比较、专家路由、成本损失、排程各自已有研究。新意必须落在可检验的交互与跨过程证据，不能声明“首次”或预先保证排名反转。增加准备层是候选研究增量，不能掩盖当前 F 无稳定收益。

## 2. 当前基线：不重复开发，不误报完成

以本次读取报告为准，以下为仓库报告的既有事实，不是本计划重新执行的结果。

| 资产 | 当前已有 | 仍缺 |
|---|---|---|
| `monitoring_v1` | 事件状态、费用账本、两种覆盖、支持集合、联合可达、原始日志与回放 | 与新 typed bundle 和新 scalar 的通用桥接 |
| `monitoring_fixed_v1/contracts.py` | 不可变 EvidenceBundle、point/interval、概率/标量、ForecastState、Brier/MAE | `paired_scores` 自身不验证预测产生时刻；小 reducer 不是完整共享监测引擎 |
| `heads.py` | 明确 E-only/F-only/joint、无填值示例、严格输出验证 | F-only 的真实模型调用尚未执行；当前 heads 限定航空目标 |
| 本轮模型 | 720次真实调用，48个已暴露机会、3种证据条件、5类提示/任务 | 不是720个天气过程；其中只有两个正例机会；没有 F 预测增益证据 |
| 校准 | 两年 Front matched/expanded 与 Bay 对照 | 2024改善、2026恶化；全读登记邻站不稳定，稀有条件支持不足 |
| EUPP/DWD | 63条核对、60正时效、28有效目标，点温度 MAE | 连续任务、as-of依据、非平凡补证、监测会话；不是热浪 |
| CNRFC/HEFS | 两个2024小时QINE版本与USGS时间连接 | 物理时间支持/调蓄/成员身份等；未授正式流量 F 资格 |
| LAV/LAMP | 历史类别及当前原生15分钟概率读取 | 原生阈值/窗口匹配、高频结果、历史可用性 |
| SEEPS4ALL | 预报、观测和气候数组读取 | 实际日界、尾部QC与缺失原因/发布范围 |

旧27,216次预测器调用只有146次概率不同、10次显式覆盖，说明不能再主要怪 wrapper。填值示例复制与指令歧义相容；修好格式不是天气方法创新。

本计划不重审所有97个来源，不重新创建相互竞争的来源注册表。沿用现有来源身份与 A0—A5/E/F/D/MM 资格，增加关联状态，不把 A5 模糊改名为本计划的完成门槛。

## 3. 架构：单一会话时钟、typed bridge、两个新职责

### 3.1 架构决定

保留旧 `monitoring_v1` 的冻结实验；复用它的 EventJournal、BudgetLedger、权限与可达接口。`monitoring_fixed_v1` 是输入/输出类型与固定证据比较层，不独立拥有另一套现实时间。

在现有命名空间加薄的适配/扩展，不建立第三个通用引擎。新 typed reducer 通过唯一 SessionRuntime 的事件更新。概率分支用旧/新 reducer 作影子差分测试，但一次正式运行只能有一个生效状态的权威来源。连续量不能塞进旧概率字段，也不能让两个 reducer 各自推时钟。

建议职责路径（尚未实现，Codex需检查冲突后确定具体落点）：

```text
disastertrace-starter/src/disastertrace/
  monitoring_v1/
    typed_bridge.py            # 接 typed Target/Forecast/Bundle 与唯一会话调度
    effective_commits.py       # 合法提交与检查点生效清单
    snapshot_bridge.py         # 完整可信状态导出/恢复/派生分支
    processing_actions.py      # 取得资料与处理资料分别建动作
    branch_diagnostics.py      # 固定证据/完整状态/固定候选三种回放
    preparedness.py            # D1 准备状态、占用与不可抹除动作账
    planning_baselines.py      # 规则/优化器；不读取私有结果
    decision_experiments.py    # 参数配对与概率—偏好隔离
  monitoring_fixed_v1/
    [原有 contracts/aviation/heads 保留]
    [按provider注册新增head，不把航空prompt套到所有连续量]
configs/...                    # 复用原有配置体系，不另立注册表
plans/[本轮唯一run目录]/        # 不覆盖旧冻结报告
```

### 3.2 研究主体与显示材料分离

ModelView 只包含当前合法、必要的科学资料和操作元数据；完整审计 envelope 不必逐字都塞给模型。若精简模型视图，登记 representation_version 并对所有方法一致提供；不得一边去掉他人必需信息，一边把自身解析器输出当作免费特权。

`ForecastView` 不含准备成本、人员容量或撤销代价；`DecisionView` 可以读取合法预测与准备状态；端到端 Agent 可以看到两者，但应另做预测受偏好影响诊断。E问题、F目标、D偏好三者拥有独立身份。

## 4. C00—C03：在新增任务前必须接通的接口

### 4.1 实际工作树与授权核对

只读记录 `git rev-parse HEAD`、`git status --porcelain=v1`、当前分支、暂存/未暂存修改及已冻结输入哈希。不自动fetch/reset覆盖任何文件。若已有新模块或新结果，先做 delta map，将已完成工作包置为 verified/deferred，而不是重复执行。

记录模型、环境、数据、协议、prompt、评分器各自版本。新增数据、安装依赖、GPU和训练分别设授权项；旧窗口已过期不得沿用。

### 4.2 Target 与 DecisionSpec 分离

`Target` 保持物理对象、变量、单位、空间支持、完整有效窗、事件条件、结果政策。`DecisionSpec` 单独记录准备时长、deadline依据、资源、取消规则、成本和假设来源。

改变成本/容量/准备时长不能改变 F target hash；改变天气目标或阈值则必须改变 target hash。用于 D 的实验身份可以组合 `forecast_target_hash + decision_spec_hash`，不能把二者混成一个天气语义。

### 4.3 三种哈希

- `bundle_hash`：实际输入字节/规范表示及审计 envelope 校验。
- `product_revision_id`：上游版本身份。
- `target_base_context_hash`：该 F 目标依赖的基线语义、适用性、校准器身份与必要生命周期。

当前 EvidenceBundle 的完整 baseline hash 可能包含 E_question、查询列表、原始revision等。它不应未经投影直接充当“是否让旧预测失效”的 F 语义指纹。E问题变化、无损重排、镜像副本不应无故触发回退；概率相同但相关条件/支持变了则需识别。

### 4.4 有效预测清单

保留纯数学 `paired_scores`，另加正式入口：

```text
CommittedForecast:
  opportunity_id, target_hash, cutoff
  input_snapshot_hash, bundle_hash, forecast_view_hash
  call_id, started_at, completed_at, persisted_at
  target_base_context_at_start, protocol, typed_forecast
  status: accepted|follow|fallback|late|invalid|stale
  source_receipt_ids, state_journal_prefix_hash
  runtime/code/model/prompt/score versions
```

以持久化完成规则决定能否在 cutoff 生效；不能根据作业结束后的文件生成时间倒填。模型调用的逻辑完成时刻和实测完成耗时分字段。失败原回复先保存，缺答按所有方法共同 fallback；所有机会继续计分。

数学离线配对、受控历史回放、有证明历史as-of、前瞻预测分别命名。不要求自然首次发布时间未知的数据被删除，但不能升级成已证明的历史在线输入。

### 4.5 通用 C2 bridge

provider转换必须明确：事实对象、单位、区间端点、scope、时窗、版本链、误差政策、可见授权。新 `bounded_error` 不是简单改名为旧 `bounded_measurement`；原图、模型估计不因字段存在而成为精确事实。

首批在真实航空上保留存在命题，并加入完整TAF条件段是否覆盖目标、原生区间是否决定阈值、新旧产品是否同目标等。H07用累计缺槽与上下界；无有限上界时保留无穷。不能让冲突空集通过 vacuous truth 被同时判真/假。

将 provider 生成的有限动作图接到已有联合求解器。单目标分别可达不代表共享预算下可共同完成。搜索达到上限时返回 feasible lower bound / declared optimistic upper bound，不标最优。完整见证包含同一条路径的费用和完成时间。

## 5. 完整状态分支：本计划的核心新增能力

### 5.1 三种对照必须分开命名

| 模式 | 固定什么 | 可以解释什么 |
|---|---|---|
| fixed_bundle | 输入资料、表示、目标、快照时刻 | 资料与预测器的直接响应，不是完整自适应策略 |
| fixed_candidate | 候选、完成时间、原始选择轨迹 | wrapper/门控的受控直接作用 |
| full_state_branch | 相同完整前缀、剩余资源、外部时间线、continuation policy | 下一动作改变后，在声明环境中的系统路径效应 |

只复制一个 EvidenceBundle 不构成 full_state_branch。

### 5.2 可信 SessionSnapshot 必須包含

```text
session/target/opportunity registry + scenario hash
clock + deterministic same-time phase + processed-event cursor
current baselines + typed explicit forecasts + calibrator identity
spent/reserved budgets + quotas + concurrency slots
cache entries + authorization + parent lineage + already paid costs
running query/processing/model jobs + frozen views + planned completions
completed/read/disclosed asset sets
preparation job state + occupancy + accrued cost + pending cleanup
alert/review log + forecast/action commits + immutable event prefix
policy private memory if permitted + RNG state + continuation policy/version
trusted external archive cursor (sealed evaluator-side, never model-visible)
```

snapshot 分为可见投影与可信封装。私有结果和未来档案即使被可信重放器持有，也不得通过 snapshot、目录、错误或queue metadata暴露。

### 5.3 分支协议

1. 选择前缀规则仅使用冻结日历、公开状态或开发诊断规则；确认集不按未来损失改善挑前缀。
2. 复制同一可信前缀到新命名空间；保存 parent snapshot hash 与分支定义。
3. 主动测试少量真实可执行替代：不追加；查合法站报；处理已可得雷达；运行专业工具；换预测器；不同覆盖规则。
4. 所有分支的外部天气与真实产品内容不变；查询不能改变天气。未归档替代返回 unavailable_to_evaluate，不能让 LLM 编造返回。
5. 前缀费用每个分支继承一次。分支之后不共享新缓存、不共享私有结果、不重置已花/已保留资源。
6. 在途请求按原请求时选版与回执继续，不可以分支时免费跳到新版本。
7. 复制 RNG 状态；不同动作消耗的随机数不同要记录。可按逻辑operation_id生成成对随机流，不能预设不同模型输出必然一致。
8. continuation policy固定；完整自适应实验允许之后基于不同合法状态产生不同动作。
9. 紧凑输出包含 F损失、D研究损失、费用、截止与未结算状态。只能称声明环境/策略下的受控干预差异。

后验最佳分支只供评估器诊断，不能用它选择当前测试动作、学习测试选择器或宣称真实期望信息价值。按已看到的case结果选最好的分支训练时，只能用开发组并交叉拟合、冻结后去新组测试。

### 5.4 改变准备条件的实验与分支实验不同

同一 DecisionSpec 内改变下一动作可以从任意合法前缀fork。改变准备时长/容量/成本时，从无准备动作的共同起点或可证明兼容的前缀开始；不能给已做一半的长工序换成短工序并保留不一致进度，也不能复制原容量下的非法占用。

## 6. 资料与处理方式：建立有限操作目录

### 6.1 动作分层

| 动作 | 语义 |
|---|---|
| QUERY | 按公开产品/地点/变量/时窗请求，锁定合法版本 |
| PROCESS | 对已合法取得的父资产运行解析、裁剪、数值处理或原生VLM |
| RUN_FORECAST_TOOL | 运行冻结专业/研究预测器，输出model_estimate与版本 |
| SUBMIT_FORECAST | 提交固定未来目标概率/标量，不能改旧记录 |
| WAIT_UNTIL | 等待公开可知事件/允许时刻，不跳到私有“最有用”资料 |
| STOP_ACQUISITION | 停止新的付费获取，不删除评分机会或暂停正在执行的准备 |
| PREPARE / CANCEL / REPRIORITIZE | D1动作，见下一节 |

目录只描述能力与公开范围，不提前泄漏未来候选数、实际质量、暴露未知值或结果决定的优先级。

### 6.2 ProcessingSpec / Receipt

包含输入变量、native support、单位、CRS、规则采样间隔、缺测政策、依赖/授权、方法与参数版本、随机种子、输出身份、实测和声明成本、失败/重试/缓存规则。

处理费用与获取费用分开。一次区域计算实际覆盖多个目标时，允许共享已授权产物；再次裁剪或再次进模型的推理仍按实际规则收费。缓存键至少绑定原始资产版本、处理器/参数、ROI/CRS、表示、seed；不能让同名字的旧产品成为新资料的缓存命中。

所有普通基线同样可用解析器、pysteps、优化器、批量服务和并发；不得只有Agent享有工具。

### 6.3 时间协议

继续保留机制回放与实测成本轨。机制轨使用冻结、声明的服务/处理延迟；实测轨按相同硬件与资源政策记录合法完成。共享集群排队不能无说明当成模型自身推理延迟。

单一事件队列同时推进资料发布、查询完成、推理完成和准备完成；程序在等待模型时不能冻结外部世界或准备工作。新事件顺序显式版本化，旧轨不改。准备占用按 `[start,end)`；规定 `end <= ready_deadline` 才算及时。旧F的同刻完成/封存顺序保持旧协议，新增动作不得获得cutoff后回填特权。

## 7. D1：有状态的研究性准备任务

### 7.1 最小任务而非完整应急模拟

先选H15的已登记站点目标做研究性保障准备，不模拟航班取消、机场关闭或疏散。第一版每个目标对应一个准备工作包，使用一种 renewable crew 资源；不要同时加入路线、车辆交通和物资补货。

天气与观测记录保持真实；duration/capacity/cost 在没有业务文档时明确 `research_assumption`，以公开配置冻结。工程fixture数值不是现实单位估计。专家以后可审核规则和典型案例，不用逐题人工判分。

### 7.2 DecisionSpec 最小字段

```text
decision_id / target_hash / scenario_version
purpose: research_readiness_only
ready_deadline_basis: fixed_target_support_start
ready_deadline
job_duration / crew_demand / crew_capacity
start_cost / work_cost_rate / cancel_cost / miss_penalty
cancel_policy / cleanup_duration / progress_after_cancel
readiness_expiry / one_job_per_target
parameter_basis: research_assumption|documented|expert_reviewed
outcome_dependency / unresolved_rule
```

第一版 `ready_deadline = target.physical_start` 或外部预登记更早时刻，启动最晚时间为 `ready_deadline-duration`。不使用事后真实首次越阈时刻倒推deadline。只有存在合格高频结果与预先注册定义时，另做发生时刻相关的及时性轨。

天气目标、预测评分检查点和准备deadline三者不同；不能因为第一份F机会封存就结束目标全部活动。

### 7.3 状态机

```text
UNSTARTED -> QUEUED -> IN_PROGRESS -> READY
QUEUED -> CANCELLED
IN_PROGRESS -> CANCEL_REQUESTED -> CLEANUP -> CANCELLED
READY -> EXPIRED (仅在配置了有效期时)
```

第一实现可省去显式 QUEUED，把 pending request 交给规划器；但实际开始、已占用、取消与清理状态不能省。

- PREPARE 原子检查资源再预留；非法动作拒绝、记录，不超配；不能偷偷自动修复成最优动作。
- 剩余工时由执行器计算，不由模型声明百分比。
- 默认不支持任意暂停/恢复；取消后已用工时沉没，需清理则清理结束后才释放。再次开始是新job，不恢复未定义的进度。
- 已经完成的准备不能从历史日志中删除。撤销预测不能撤销准备费用或已完成工作。
- REPRIORITIZE 只重排未开始任务；运行中工作不可瞬移到另一个站。
- START与CANCEL幂等，重放不重收或漏收费用；失败不重置账户。
- 稀缺设备若以后添加，单列非renewable/驻留占用，不默认crew完成后设备也免费释放。
- 所有结果为仿真内部状态，不向外界发出真实预警或调度。

### 7.4 评分

先分别报及时完成率、实际工时、无事件工时、漏准备、取消次数/沉没工时、资源违规和完整原始F分数。需要一个研究损失时使用冻结配置：

`J_theta = sum_jobs(start_cost * I(actual_started) + work_cost_rate * actual_work
                    + cancel_cost * I(cancellation_charged))
         + sum_targets L_i * y_i * (1 - eta_i * ready_i_by_deadline)`。

首版可取声明的二元 `eta=1`，表示该研究损失项被完全避免，不代表现实防护100%有效。`actual_work`包含取消前工时与明确清理工时；start_cost只在实际开始时收取，cancel_cost仅在声明的取消事件发生时收取，未开始排队任务的取消费单独配置。取消成本不得再重复算同一工时。费用用研究单位，不与token/秒/人民币直接相加。若加总运行成本，另设有依据的转换敏感性轨。

y未知时保留已知操作成本与未知结果罚分的界，采用共同结果政策，不删掉高成本失败会话。对同一目标的多个F时距不能重复收三次miss损失，D按决策任务身份结算。

REV只适用于独立二元保护的特定简化子轨；不能拿其最大阈值扫描结果当测试期可部署政策，也不能替代排程总损失。所有阈值开发集冻结。

### 7.5 无LLM强对手

1. 不准备、可行范围内总准备、预登记deadline规则。
2. 最新共同预报 + 固定阈值/公开优先级。
3. 最新共同预报 + 滚动优化器；正在运行的工作作为硬承诺输入。
4. 廉价全读 + 同一专业预测器 + 同一优化器。
5. 事件触发规则 + 同等工具和预算。

最小实例用独立枚举器验排程与损失；规模扩大后用 OR-Tools 的 interval/no-overlap/cumulative 结构。优化目标是当前合法概率下的声明期望损失，不是通用job-shop示例的makespan，也不是已经看到的真实y。

报告 solver时间、可行性、最优性/界；time-limit内只有可行解不能称最优。OR-Tools只做基线与约束验证，不作为LLM专享工具。

## 8. 两项最值得优先的新实验

### 8.1 固定天气与证据，改变准备要求

将duration/capacity/cost作为单独因素，预先冻结小网格。先单因素，再选定组合，不默认全笛卡尔积。

- 固定 evidence/forecast backend/compute 时：改变准备参数，F输入规范字节和统计预测必须相同，D动作允许变化。
- 随机LLM比较用配对seed与输出分布，不要求所有自然语言重复调用逐字相同。
- 端到端策略可以因不同目的选择不同证据，之后F不同是合法的，不能误判为概率受偏好污染。
- 在cost-aware统一Agent上追加诊断可测概率偏移；模块化强基线通过独立F视图保障隔离。架构隔离通过不等于LLM自己掌握了不变性。
- 任务截止、变量、阈值不随成本改变；改变阈值就是另一F目标，不属于偏好隔离测试。

### 8.2 固定真实前缀，重跑取得/处理/采用/准备路径

保持物理结果与外部资料不变，比较当前无追加、单条观测、区域处理、工具调用、固定候选门控及提前准备。完整分支继承运行中的准备与查询，不能免费清空重来。

固定预测比较planner；固定planner比较预测；固定预测器比较资料；固定资料比较处理器。不同对照效果不相加。只有修改指定条件且其他条件按声明保持，才称该评测环境内的受控作用。

**这两项分别对应用户材料中的“行动需要决定信息价值”和“可实际重跑的失败分析”。** 不以频繁改变动作、更早报警或更多调用作为奖励。

## 9. 联合风险：保留，但先证明它对损失是必要的

第一版 D1 的确定性可行排程若有逐目标可加损失，对固定排程a：

`E[sum_i L_i(a_i,Y_i)] = sum_i E[L_i(a_i,Y_i)]`。

因此共享crew约束本身不自动意味着必须预测完整联合分布；边际概率可能已足够做这一基线。不要为了制造难度强加“所有准备任务都需要joint概率”。这是一项对附件建议的实现限定，不是否定其共同风险方向。

C18 只有在引入明确的非可加/随机共同需求目标时启用，例如固定窗口“至少两个站点越阈”或同时需求超过容量的损失。相同边际0.5/0.5下：完全同步时共同发生概率0.5；互斥时0，差异才直接影响该目标。

要求：同周期成员场保持空间身份、完整目标窗、共同结果覆盖；不能独立随机打散站点成员再称保留相关性，也不能把不相干事件的最坏片段拼成真实复合灾害。缺联合依据时，独立乘积只能作明示假设基线，或报告Fréchet界，不生成伪Gold。

当前CNRFC历史列身份未确认，不能直接赋予跨周期或跨站成员对齐资格。D1可继续，不让该问题阻塞基础准备任务。

## 10. 数据与场景路线：完整16类保留，少数场景先闭环

### 10.1 H15 航空回归与首个研究准备任务

使用现有TAF/METAR合法样例联调，旧48机会标为exposed开发。确认用完整预登记新日历，不按正例、LLM获胜或E错误选择。

当前R映射与原始TAF概率身份保持；LAV类别不直接变为官方概率。LAMP 15分钟最低值和英里阈值另立子目标，不替换原小时1km/5km问题。只有完整匹配结果才评分。

### 10.2 H07 区域短时强降水：提高研究优先级，先核验再接工具

目标是同一真实区域、同一连续过程中的区域概览/局地处理/短临计算选择。优先检查已登记MRMS/站点/HRRR或其他实际可得预报的时空交集；不要以“相关库支持”代替实际产品值。

准入字段：原始降水率/累计变量、单位、连续帧时间、像元尺度、投影、质量、缺测/遮挡、输入时间与合法版本、模型预测目标与观测聚合窗口。

pysteps STEPS需要规则间隔降水场与运动场、时间步和像元尺度。不能将SEVIR VIL或彩色截图直接作为毫米雨量；没有合格QPE转换就拒绝工具调用。集合输出是新预测，不是真值。

强对手包含持久性/平流、pysteps或合格专业短临、NWP/融合、批量读取加同样工具。共同专业预报都可用，补充处理成本才进入相应选择实验。空间裁剪依据登记目标，不使用未来最强雨区找最有利ROI。

结果优先独立雨量站；若用雷达产品作为未来参考，明确为产品目标并披露与输入/融合的依赖。模型调用未来观测不允许。

SEEPS4ALL是日尺度路线，不能替代本场景的短时累计。短时合格源未齐，输出join审计并让温度或已通过水文接口继续，不伪造降水—流量映射。

### 10.3 H08 水文并行：先物理支持，再水网共享

复用已捕获2024 CNRFC/QINE，核准瞬时/小时平均、调蓄/还原、站点断面、单位和适用版本。核准前只做产品版本E，不给正式流量F。

官方阈值缺失时，已合格的连续流量或独立历史统计阈值R轨可先推进，不冒充官方洪水警戒。NLDI可辅助水网上下游关系；保存实际导航结果和映射，不把地理最近站视为上游，也不把水网拓扑自动等同传播时间或预测因果。

专业多站ZIP本就进入共同基线时，其文件共享不能再算成补证智能增益。只有真正额外的已授权观测/处理具有共享关系时才作C1试验。

### 10.4 H10/H11 温度：低成本数值迁移

EUPPBench/DWD继续区分forecast与reforecast。正时效不是as-of证明；日最高/最低、instant温度与热浪不同。先接连续任务、typed forecasts和真实补证；不因为60配对可评分就标热浪/寒潮完成。

### 10.5 其余12类与发布角色

| 组 | 灾类 | 后续门槛 |
|---|---|---|
| 气旋/风暴 | H01、H02 | 保留风暴/站点语义、风平均时长、预报目标与结果 |
| 对流 | H03—H06 | SPC完整原生窗口、报告/物理参考、雷电R轨、雷达输入支持 |
| 水灾 | H09 | 总水位/增水/淹没、潮位基准与适用产品 |
| 冬季 | H12 | 降雪/雪深/SWE/冻雨分别准入 |
| 陆表/成分 | H13、H14、H16 | 干旱产品发布与未来物理分开；沙尘成因；火险与蔓延分轨 |

这里没有降低完整16类F发布目标；只是不要求每一类都做完整D1或联合D2。逐类同时记录 source_parsed / E / F_offline / F_monitoring / D_research / native_MM / independent_confirmed，不能一栏0/16遮盖进度，也不能一项通过代表全类。

## 11. 方法、基线与实验：不建大型Agent群

### 11.1 最小候选方法

公共事件触发 -> 廉价检查资料年龄/基线分歧/剩余准备时间 -> 选择资料与处理级别 -> 冻结预测器 -> 门控或FOLLOW -> 有约束planner。

触发不读取未来值。若用LLM选择器，全部元推理、失败和重试计入同资源账。保留纯程序与全读策略。候选无需每tick调用大模型。

一至两步前瞻先做有限可执行动作。需要预测尚未取得资料的效果时，只能使用独立开发数据拟合的风险模型、声明的概率模型或冻结启发式；不能查询评估器真实未读值。BRiG-AFA是可借鉴的研究思想，不是已适配的本项目算法；拟合/训练仍需授权。

### 11.2 与X00—X09对应

| 原实验 | 本计划增强，不新增第11个核心实验 |
|---|---|
| X00 | 强共同基线、源角色、明确heads、全日历预测与研究D基线 |
| X01 | 固定selector的资源分配×共享2×2；相同权限下策略比较 |
| X02 | 原候选/门控/覆盖差分；D动作不被FOLLOW清空 |
| X03 | 同一完整前缀的资料/版本/处理分支 |
| X04 | 真实provider到C2、联合可达和非平凡预测输入事实 |
| X05 | 同原始资产不同处理、真实MM；有损摘要不称等信息 |
| X06 | 不同物理过程、同目标参考与分组迁移 |
| X07 | duration/capacity/cost配对；实际时间/声明时间；并行准备 |
| X08 | 有界影子验证、first-seen区间和结果成熟度 |
| X09 | 联合资料+工具/预测器选择；可选联合风险，不阻塞核心 |

### 11.3 不同因果问题用不同对照

- 固定信息与F模型，比较资料策略。
- 固定证据包，比较F预测器。
- 固定F轨迹，比较D planner。
- 固定D规则，比较F来源。
- 固定候选和完成时刻，比较wrapper。
- 固定完整前缀与continuation policy，比较下一可执行动作。
- 固定天气证据与计算条件，改变DecisionSpec，检查F不变与D响应。

同资源效率是主对照；匹配预测调用数可以单列选择质量诊断，不免费删除selector成本。联合输出与分头输出的总成本不同，分别报告。

### 11.4 初批模型规模

C12独立head诊断先一个冻结文本后端，确认实际F-only调用入口。不要用一个joint回答拆成两次调用。无填值答案样例；预登记有限提示候选、明确停止规则，冻结后换新数据。

C16端到端先一个文本后端、一个已有合格VLM/专业工具，4—6种强策略，两个资源档加不紧对照，三个单因素D设置。不是全部笛卡尔积，主要比较先登记。不要求触发override、更早准备或排名反转才能放行。

## 12. 统计、缺失与应用证据

主队列由地区/站点/日历/阈值预登记生成，包括普通、边界、正例与缺失。机制富集另表，不代替自然事件率。旧48机会、两个正例、重复head及多提前量不当独立N。

训练、校准、门控/选择器开发与确认过程分组隔离。purge覆盖回看、目标窗及共享派生输入；资源会话72h不是天气独立过程。对新参数和多比较预登记主对比、曲线或多重检验政策。

用开发组的配对差异方差与最小关心效应决定确认规模。可用 `n≈((z_alpha+z_power)*sd_group/delta)^2` 作初步独立组近似，但罕见事件与相关块需模拟检查；不把估计值当保证，不以增加调用补样本。

F保留Brier/适用MAE、尾部或多阈值补充、可靠性与排序分开。多阈值单调、原始删失和单位严格，不能把不同灾种MAE直接平均。

D报告冻结研究损失及每项组成。无结果会话仍计资源与失败，未知结果损失可给保守界；共同mask公平不保证总体无偏。不能从单次 realized gain推出概率理性或真实VOI。

影子运行不作论文核心的阻塞；仅在明确授权窗口中采集、先提交后结算，不常驻、不发布公众预警。专家规则审查作为潜在应用层级，不让其变成自动主榜逐题Judge。

## 13. 开源复用与来源边界

| 资源 | 本次核查/可复用部分 | 实施限制 |
|---|---|---|
| OR-Tools | 官方排程文档：interval、precedence、no-overlap | 本项目要最小化当前预测下的准备损失，不直接复制makespan；固定版本/许可/最优性与耗时 |
| pysteps | 官方STEPS与blending接口：连续降水场/运动/分辨率/时步 | 实际合法QPE与NWP支持需通过；库输出非Gold；不偷偷下载数据/训练 |
| USGS NLDI | 官方上下游导航 | 只提供经读取的连接证据，不提供完整水文预测等价性 |
| scores | REV及其二元成本损失限制 | 仅对兼容简化轨使用；不能测试期扫阈值后充作可部署效用 |
| BRiG-AFA | 论文摘要描述预算相关Bellman终局风险，监督路线 | 需另审代码/版本/成本；不声称已完整复现，不把未读值给策略 |
| Expert-Conditioned Advice | 论文摘要：专家与额外信息选择耦合 | 不用其理论否定为归因而拆接口；算法复用需独立适配 |
| SentinelBench/FutureSim | 官方/作者资料显示监测与动态预测已有 | 不主张首次；不要整体移植浏览器、私有反馈和合成时间设置 |
| EWB/AFA/LEAP | 继承附件建议的有限适配用途 | 本轮未重新读其完整源码；Codex先固定真实代码版本、许可和缺失后端 |

本轮没有穷尽两附件所有论文全文。附件列出的 DORA/TerraBench/LastMileBench 等不能因未重新阅读就推断有或无某功能；可保留为待定向审阅项，不将其弱存在性作为新颖性保证。

## 14. 里程碑与工作包

精确依赖、前置、输出、测试与停止条件见 `CODEX_BACKLOG.json`，共20个工作包，C18/C19为条件扩展。

| 阶段 | 工作包 | 必须实际交付 |
|---|---|---|
| M0 当前基线与任务 | C00—C01 | 现状差异、权限和一页研究任务；不重复旧审计 |
| M1 集成与分支 | C02—C05 | 有效提交、typed/C2、完整快照、处理目录 |
| M2 强基线与固定对照 | C06—C07、C12 | 程序闭环、固定证据矩阵、真实分头结果（授权后） |
| M3 研究准备层 | C08—C10 | 状态机、可重算planner、偏好配对；可与M2并行做CPU |
| M4 方法与第二过程 | C11、C13—C14 | 事件触发/有限前瞻、H07条件接入、H08/温度迁移 |
| M5 确认与发布 | C15—C17 | 新分组冻结、有限端到端矩阵、分级证据包 |
| 条件扩展 | C18—C19 | 真正联合风险、有界影子/规则应用验证 |

首轮默认 C00—C05；C08 的单元测试可在C01/C02后并行，不能不等集成就将模拟分数称为真实监测结果。新增模式默认关闭，已有模式应保持输出一致。

## 15. 必须执行的反例/验收类别

1. 截止前请求、截止后返回；截止相等；early completion未持久化；全部保留失败与fallback。
2. 只改D成本不改F目标/视图；有意识改变证据后F允许不同。
3. 目标语义相同的镜像/重排不误失效；相同p但相关分布/条件变化能识别。
4. 同完整前缀不采取额外动作的分支，与原继续运行逐条一致。
5. 分支不得获得新免费预算、共享另分支私有缓存或丢失pending任务。
6. 迟到资料不能通过派生图、摘要、缓存绕过父时间/权限。
7. typed支持的删失、负值、冲突、无穷上界、版本和单位；同一路径联合见证。
8. 一名crew不能同时服务两个任务；完成边界释放合法；取消有沉没代价且幂等。
9. 查询与准备并行：WAIT不暂停已开始准备，模型计算不冻结外部世界。
10. FOLLOW/基线更新不能删除已准备/取消历史。
11. duration=0且资源不紧的兼容子轨可退化到原截止规则；非零duration下最后启动点以前后有真实后果。
12. 未发生事件、全零风险和全部准备等条件不过度奖励动作频繁。
13. 同成本/输入的强程序与LLM享有同工具/批处理/优化器。
14. 固定可加排程下只改相关结构不改期望损失；非可加joint目标可区别同步/互斥情形。
15. 原生LAMP、QINE/SQME、日雨量和VIL等错误支持自动拒绝，不能fallback猜数后继续当合格。
16. 移址恢复从冻结输入到同分；原始ETL重建与模型token回放分开声明。

这些是待新增/复用的测试类别，不是已运行的16项测试，更不是16场真实灾害。

## 16. 最终汇报要求

每个工作包输出 `status, dependencies, actual_changes, commands, source_hashes, tests, real_data_checks, model_calls, cost, scientific_claims_supported, blocked_reasons`。

`implemented`、`unit_verified`、`real_data_verified`、`model_executed`、`independent_confirmed` 是不同状态。原始失败、提示复制、负结果、缺失、请求短包、被拒绝动作保留。

最后必须给出：
- 本轮真正新增了什么、复用了什么、哪些只是计划；
- F、E、D与资源结果的独立表；
- 每灾种各层资格与source索引；
- 下一轮最小可执行任务；
- 不覆盖旧文件的复现命令与证据哈希。

不要以代码行数、测试数、token或下载量作为主要科学完成标准。成功是得到了可信、可解释、可被否定的比较，不是预先写好的Agent胜出结论。

## 17. 来源定位与本次实际阅读边界

两份新用户建议完整保留其任务含义：A=区域监测/资料和处理选择/完整前缀分支，B=准备时间/占用/撤销/目的条件配对。本文对分层实施、可加损失下联合风险是否必要等所作限定属于本次设计推理，不冒充附件原结论。

- [plans/v7_execution_20260913/NEXT_PLAN_CN.md](https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/plans/v7_execution_20260913/NEXT_PLAN_CN.md)：最新工作与阻塞；读取返回在末尾截断，未据此推断未见后文。
- [plans/v7_execution_20260913/FINAL_REPORT_CN.md](https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/plans/v7_execution_20260913/FINAL_REPORT_CN.md)：本轮重新读取前90行；其他细节来自已有会话材料，未重跑。
- [disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py](https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_fixed_v1/contracts.py)：本轮读取330—580行，核对状态和paired_scores。
- [disastertrace-starter/src/disastertrace/monitoring_fixed_v1/heads.py](https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_fixed_v1/heads.py)：本轮读取1—145行，核对独立head与航空限制。
- [disastertrace-starter/src/disastertrace/monitoring_v1/journal.py](https://github.com/sisuolv/disastertrace-benchmark/blob/60ebd05723f9483590611976d379da2e4edd85b0/disastertrace-starter/src/disastertrace/monitoring_v1/journal.py)：本轮读取完整文件，哈希链/持久化/恢复。

本轮核查的外部资料：

- [OR-Tools job-shop](https://developers.google.com/optimization/scheduling/job_shop)：官方文档已读取；提供区间、precedence、no-overlap示例；非本项目期望损失完整实现。
- [pysteps STEPS](https://pysteps.readthedocs.io/en/stable/generated/pysteps.nowcasts.steps.forecast.html)：官方接口已读取；未执行库。
- [pysteps blending](https://pysteps.readthedocs.io/en/stable/generated/pysteps.blending.steps.forecast.html)：官方接口页面已读取；未执行库。
- [USGS NLDI navigation](https://api.water.usgs.gov/docs/nldi/navigation/)：官方说明已读取；未调用实际站点导航。
- [scores REV](https://scores.readthedocs.io/en/latest/tutorials/Relative_Economic_Value_Score.html)：官方说明已读取，包含二元成本损失和适用限制；未执行库。
- [BRiG-AFA](https://arxiv.org/abs/2608.02305)：作者论文摘要核查；未复现训练或冻结新代码版本。
- [Expert-Conditioned Advice](https://arxiv.org/abs/2603.14324)：作者论文摘要核查；未复现算法。
- [SentinelBench](https://www.microsoft.com/en-us/research/publication/sentinelbench-a-benchmark-for-long-running-monitoring-agents/)：官方研究页面已读取。
- [SentinelBench official article](https://www.microsoft.com/en-us/research/articles/sentinelbench-a-benchmark-for-long-running-monitoring-agents/)：官方详细说明已读取；不移植其人工时间或任务终止语义。
- [FutureSim](https://arxiv.org/abs/2605.15188)：作者摘要核查；不穷尽其全部实现。
- [EarthVerse](https://arxiv.org/abs/2608.23525)：作者摘要核查；详细近邻叙述按附件范围归因。

实际代码/包依赖版本在Codex执行C00/C05时再固定；本包的外部implementation_pin为null不是已锁定实现。没有访问到的论文或库不能被宣布“不支持某功能”。
