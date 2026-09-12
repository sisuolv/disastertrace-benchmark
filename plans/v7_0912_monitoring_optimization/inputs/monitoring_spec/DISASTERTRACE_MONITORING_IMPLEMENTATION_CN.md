# DisasterTrace：持续监测、共享取证与选择性预测修订实施规格

审阅日期：2026-09-12  
用户仓库：`sisuolv/disastertrace-benchmark`  
审阅基线：`next-phase-v1@ae69453ff15bc3def6c513fafbfd8758437a8587`  
文件性质：建议实施规格，不是已实现功能或已通过验收的声明。

本次读取了现有源码、历史任务链和公开框架的代码/官方文档；未修改远端仓库，未重跑本机全部原始科学数组、GPU实验或上一轮Range测试。本包中的YAML、JSON和命令是待实现的接口约定，不是现有CLI的使用说明。代码实现应先检查实际HEAD，记录相对本基线的变化，再决定迁移。

## 0. 要交付什么，不做什么

交付一个独立版本的 `monitoring_v1`：将现有单目标结果验证能力保留在内层，在外层新增多地点监测会话、共享查询预算、资料到达队列、证据复用和选择性预测修订。

核心问题：在共同最新专业预报条件下，系统能否把额外取证资源用于值得复核的目标；实际修订带来多少改善、多少破坏、多少成本？

首版范围：

- 主任务：美国机场群低能见度报告预测；数值迁移任务：区域站点温度。
- 条件扩展：多河站连续流量或水位，二者分开；原生多模态至少完成一条与主任务同期、同空间关系的链。
- 保留16类灾害蓝图，逐类发布E（产品事实）、F（未来预测）、D（声明决定情景）的完成状态。
- 历史冻结回放是主实验；前瞻first-seen是独立的补充实验。
- 不训练新的全球天气模型；不构建物理灾害世界模拟器；不自动发撤公众预警；不把请求人工复核当免费答案工具。
- 本规格不授权启动GPU/API调用、长时下载或常驻采集。实现先通过离线合成夹具和现有开发样本，再按明确的资源批准执行。
- 不新增逐题人工Gold，不使用LLM judge作为主评分。复用既有标签仍需核验数据定义、质量与上游来源。
- 不以主动策略取得正增益为样本准入条件；负结果和缺测保留。

## 1. 已有代码怎样复用

| 已有路径 | 可复用部分 | 必须保持或改变的边界 |
|---|---|---|
| `disastertrace-starter/src/disastertrace/active_forecast/` | 精确数值、严格JSON、UTC、来源选择器、有限产品事实证书 | 八卡上限和有限池语义保留；只给E层用，不把证书当未来概率真值 |
| `.../active_warning_v1/schema.py` | 输入/结果分离、目标与时间不变量 | 新合同独立实现；不能直接套非负值、两种family、同实体同变量限制 |
| `.../active_warning_v1/environment.py` | 请求时刻版本冻结、query/read分离、回执、追加日志 | 单目标预算改为session预算；查询须按product、entity、variable、support索引；不得按kind全池取最新 |
| `.../active_warning_v1/policies.py` | 获取与预测两阶段后端接口、原始回复记录 | 预置两轮改为事件驱动；WAIT、停止与多目标选择由新协议明确 |
| `.../active_warning_v1/scoring.py` | 运行后独立评分、检查点前最后提交、分组报告 | 首版新系统以完整机会表左连接；未处理默认跟随共同基线，不沿用旧版初始预报回退语义 |
| `plans/task_chain_feasibility_20260912/build_chains.py` | GFS/HEFS/站报的受限解析与样例 | 抽取成无全局状态的provider adapters；补TAF部分字段继承、操作符、区间与COR处理 |
| 同目录 `verify_chains.py` / `test_contracts.py` | 已有数值复核和语义回归 | 不改原冻结结果；新增测试结果另目录保存 |
| `.../hydro_shadow_v1/` | 有界前瞻抓取、真实收据、注册/结算版本 | 不重新启动旧任务；通过captured artifact事件接入新会话；历史回放和真实时钟分开 |
| `plans/all_dataset_utilization_20260912/` | source binding、请求回执、可用性清单、Range下载 | 来源样例状态不自动等于任务准入；先回归此前提出的预算越界与缺少版本标识反例 |
| 旧 `multimodal_v1` / 表示模块 | 经核验适用的图文渲染、交付元数据 | 不默认旧气旋特定字段或标签可直接用于新灾种 |

旧版本作为冻结回归目标。不要通过扩大Literal、删掉所有值域/配对校验来强行兼容新任务；应改成“物理变量约束+证据角色约束”。

## 2. 首版实验合同：先固定这些决定

### 2.1 会话、目标、评分机会三个身份

- `session_id`：同一区域站点集合的一段连续监测时间，拥有共享预算和会话内缓存。
- `target_id`：一个固定的物理/报告结果对象，例如“机场A在[T,T+1h)的例行报告能见度统计”，不随预测改变。
- `opportunity_id`：某个target在某个公共检查点的评分机会。同一target可在不同提前量被多次评分，但不是多个独立天气事件。

必须先生成完整 `opportunities.parquet`，再连接资料和结果。所有方法使用同一个表。模型不能选择评分分母。

目标创建按日历、站点和任务规范，不能按未来天气、资料异常值、标签正负或结果是否齐全创建。扩展正式测试前固定站点清单和时间块；缺数据站点保留缺口报告，不在看完成绩后替换。

### 2.2 v1公开信息与免费基线

主轨 `shared_baseline`：所有方法在相同公开交付时刻取得完整合法专业预报内容、标准投影/校准结果及版本号。基线查询配额为0，但任何模型读取它产生的输入token仍记账。各方法拥有同一份免费资料范围。

补充观测的实际值、质量结果、影像裁剪和派生统计必须通过工具取得，除非它们明确属于所有方法共同拥有的初始信息。公共目录只给固定能力、已合法公开的产品元数据与成本，不给未读数据的趋势/异常提示。

监测目标可以预知；不得预先给出来自未来事件摘要的危险地区或峰值提示。

另轨 `end_to_end` 把专业预报也纳入查询成本，使用不同protocol_id，不能与主轨混榜。

### 2.3 未处理、无效、超时如何形成系统输出

系统默认存在一个冻结的 `BaselineProvider`。没有合法修订时，输出当前共同基线，而不是删除目标或保持空预测。baseline也没有时，使用开发期冻结的缺基线回退（例如气候态/持久性组合）；其身份必须是 `baseline_missing_fallback`，不得称为官方预报。

无效/超时仍记入failure ledger，即使系统预测采用回退也不能算作模型合法完成。系统级分数与Agent协议完成率分开。

### 2.4 修订的版本作用域：明确选择，不留隐式规则

建议主协议使用 `base_bound_override`：

- 每次修订绑定target、基线内容版本、提交时间、固定有效期限和已读引用。
- 有效期内可跨多个检查点复用同一target修订，不要求重复调用模型；每个检查点仍计分。
- 当影响该target的共同基线内容版本改变、目标合同失效或达到expires_at，该修订转入历史状态，自动跟随新共同基线。
- 只有传输渠道或文件打包改变、规范基线事实完全相同，不算基线内容修订，避免重复推送引发无意义失效。
- 不把旧修正量自动加到新版预报。需要这种能力时另建 `residual_carry` 敏感性轨。
- `FOLLOW_BASELINE`表示撤销当前覆盖，继续随该target之后的基线变化；`KEEP_LAST`与之不同，v1不开放以免混淆。

这是所有方法共用的实验性保护规则，不是给某个模型的优势。另做持久覆盖敏感性实验，公开自动回退对结果的贡献。

### 2.5 会话记忆与学习

允许会话内证据和预测记忆。不同测试会话、不同策略、不同情景的动态缓存不互相共享；共享磁盘原始字节不代表共享已读证据权限。冻结训练得到的参数或公开背景资料可复用。

v1不在测试会话中用评分器Gold训练或更新门控。过去目标的真实观测若在当前已经合法发布，可以作为正常观测查询；它不同于暴露评分器的终版标签、误差或全部结果。在线学习若研究，另设结果成熟延迟和更新协议。

## 3. 数据建设：从离散事件样例到连续监测小包

### 3.1 建议开发规模（不是统计充分性或已下载声明）

`smoke`：3个机场、72h、每小时公共检查点、3个提前量。先用合成夹具，再用实际连续资料。若每小时每机场生成3个机会且无其他掩膜，名义机会数为3×72×3=648；648不是648个独立事件。

`pilot`：2个区域、每区6个机场或站点、每区14天。训练校准数据和测试块分开；扩展之前先做索引和字节预算估计。

确认性规模根据独立session/父事件上的效应与方差确定。不要预先承诺“若干万题足够发表”。

下载覆盖应包括初始回看与结果尾窗：`[session_start-lookback, session_end+max_lead+outcome_window+settlement_allowance]`。会话结束不等于所有目标结果已经到达；尾窗只由独立评分流程使用，不在模型的最后输入中提前开放。72小时示例若最后检查点还生成+6h目标，不能只下载72小时观测。

### 3.2 机场能见度主线

原始预报：NWS TAF通过IEM历史原文与元数据；观测：同机场原生METAR，SPECI作为额外及时证据可单列。不能根据SPECI触发时刻才生成目标，否则目标密度与风险相关。

推荐目标：未来固定小时窗内，按已登记例行报告槽位得到的能见度结果是否低于研究阈值。默认阈值1000m仅为研究配置，不是机场通用运营决策规则。另行保留实际雾现象标签，不把SN导致的低能见度称为FG。

目标支持与结果选择：

1. 在开发侧冻结站点例行报告时隙/支持窗口，按规则取routine METAR，不把空小时移动到最近有利报文。
2. 原生SM分数、P/M删失、米制9999/0000、CAVOK等按官方定义解析成区间，分别保留上下界和开闭性。
3. 一小时聚合若用多个槽位，使用固定统计量（如例行报告最小值），不是连续物理最小值。
4. 对不完整窗口采用相同、预先固定的覆盖要求，不因为看见正例就临时放松其他条件；不满足则unresolved。
5. COR报文与修订必须保存observation_time和revision_received时间。用最终修订作结果可以，但不能倒填成历史输入。
6. 区间完全在阈值某一侧才生成确定二元标签；跨阈值或无法解释则不可用作该二元主分。

TAF修正：当前仅INITIAL/FM/TEMPO有界支持并不等于完整TAF解析。新增状态继承，支持在许可地区范围内的PROB、PROB TEMPO、BECMG、AMD/COR、CNL/NIL；不支持的输入进入quarantine且报告选择偏差，不能静默忽略。TEMPO仅描述临时条件，不机械赋某点概率0.5。

基线层至少分成：

- `taf_prevailing_projection`：保留旧诊断，不当强专业基线；
- `taf_full_rules`：完整适用条件的规则参考，报告其目标映射约定；
- `taf_full_calibrated`：开发期拟合并冻结的概率映射，使用完整TAF、时效和允许静态特征，不偷用额外付费观测；
- `persistence_calibrated`及简单站报增强：作为额外资料对照，站报访问成本必须公平。

若校准集缺乏事件或时空代表性，只发布当前能够可靠计算的分类/区间诊断；不声称已完成概率主榜。

### 3.3 温度迁移任务

先复用GFS精确valid_time与NCEI历史观测链，当前获取主线再按适用版本使用GHCNh。允许负温度。首版6/12/24h等时效必须兼容真实产品的valid_time网格，不伪造小时预报。

格点到站点的最近点/插值政策在开发侧冻结；不使用未来标签选择邻格。若需要时间重采样，必须同时声明参考支持和预测转换，所有模型共同采用；优先不插值的精确配对起步。

点温度MAE先完成；热浪、寒潮的多年基准、持续性另建target规范，不从一次高温/低温样例外推整类已完成。

### 3.4 水文条件线

HEFS流量与USGS00060匹配；NWPS水位与同基准水位匹配。CAMELSH/Caravan是观测与背景资产，不是业务预报归档。

先建立 `forecast_archive_coverage.parquet`：provider/product/station/issue/created/valid/window/receipt/版本数量。多事件版本不足时，不以retrospective模拟代替真实业务预报，而是标为受控模型产品或转前瞻补充。

流量阈值不存在时只发布连续流量；禁止套用水位阈值。不同站量级分开或按开发期尺度正规化，不能用目标所在测试窗口的均值/标准差作归一化参数。

### 3.5 原生多模态链

首条建议机场群＋同期GOES ABI序列，或温度/水文＋经空间关系核验的雷达/卫星。具体产品变量（辐亮度、亮温、反射率）需要各自适配；C01不能无条件解释成可反演物理变量，夜间可见光不可用是正常质量条件。

查询裁剪锚定预登记机场/流域与固定尺度集合，不由未来分割标签选ROI。保留投影、分辨率、nodata/DQF、渲染变换、合法时间、像素支持。无数据与清晰无灾害不能混同。

三种视图分轨：原生标准渲染；同资产的固定数值特征；同事实不同表达。数值特征需由已读资产计算，其算力/新操作计费；不是免费的特权Gold。

影像特征对预测的简单强基线：用相同合法影像资产生成固定空间/时序特征，交由冻结的轻量融合器；不要只有VLM加图和纯文本两个不公平条件。

## 4. 建议新增目录

```text
disastertrace-starter/src/disastertrace/monitoring_v1/
  contracts.py          # 类型、值域、角色、时间与身份约束
  catalog.py            # 提供者/产品/支持查询与可见性
  compiler.py           # session/target/opportunity/event构建
  clock.py              # heapq事件队列与同刻顺序
  environment.py        # reset/step/public_view，不导入Gold
  receipts.py           # 费用预留、实际结算、事务与幂等
  baseline.py           # 共同基线版本与冻结校准器
  ledger.py             # 产品/表示/交付/已读权限
  dependencies.py       # 数据与计算依赖，不是LLM生成天气因果图
  predictions.py        # FOLLOW/OVERRIDE/失效和封存
  actions.py            # 受限工具/动作JSON合同
  runners.py            # mock/program/text/VLM后端
  replay.py             # 从日志重建，不重采样模型回复
  scoring.py            # 独立评估入口，物理层面隔离
  cli.py                # 待实现命令
  adapters/
    taf_metar.py
    station_temperature.py
    hydro.py
    satellite.py
  policies/
    follow.py
    fixed.py
    risk_first.py
    statistical_gate.py
    agent.py
    lineage_aware.py
  diagnostics/
    paired_histories.py
    selective_revision.py
    monitoring_alerts.py
```

脚本编排建议放 `plans/monitoring_v1/`，不要继续把核心逻辑藏在只执行一次的日期目录中。冻结的旧日期产物不搬动、不覆盖。

源绑定与标准化表可用Parquet；原生数组沿用NetCDF/GeoTIFF或分块存储；配置和有限trace用严格JSON/YAML。原始大文件不进入Git。v1不需要Neo4j、向量库、Kafka或多Agent框架。

## 5. 数据对象与隐私边界

| 对象 | 必需字段摘要 |
|---|---|
| SessionSpec | id、cohort、start/end、opportunity_rule、budget、baseline/latency/override/feedback政策、协议hash |
| TargetSpec | id、实体、变量、单位、空间支持、目标时刻/窗、结果统计量、阈值与版本、允许输出类型 |
| Opportunity | target_id、cutoff、horizon、共同权重、状态；与result按固定键连接 |
| Artifact | product_family/product_id/content_revision/representation_id、provider、support、issue/valid/release/capture、quality、private_storage_ref |
| Fact | fact_id、来自哪些已读artifact、精确/区间/派生结果、单位、时空支持、推导政策 |
| Receipt | query_id、accepted/request/complete/read时刻、产品快照、成本预留/结算、失败、payload hash |
| Override | target_id、base_revision、value/probability、commit_time、expiry、citation_receipts、可选agent声明事实依赖 |
| Outcome | target_id、O/P/R参考身份、value/interval/class、QC、成熟度、版本、结算时刻与reason |

结果由单独worker读取，模型worker不挂载结果表或未裁剪的全时段原始文件。opaque artifact ID不能编码未来事件名称、标签或split。源哈希与原始URL可在私有审计层保留；对模型只暴露必要的产品身份与可用元数据。

公共summary若显示未读站报趋势、satellite异常分数或影响站列表，就已经传递了证据信息；应成为所有方法的共同免费产品或通过付费工具交付，不能藏在“只是元数据”中。

结果表中某目标的物理观测，在更晚时刻可以经合法provider artifact接口被用于更晚目标。授权按记录/版本/as-of执行，不按“这个文件叫outcomes所以永远不能读取同一个物理事实”执行；但评估器派生标签不直接给模型。

## 6. 事件驱动时钟与动作

### 6.1 推荐v1时钟

CPU主进程使用整数UTC微秒与 `heapq`，键为 `(event_time, priority, monotonic_sequence)`。无需真的等历史6小时，只处理事件后跳转。

事件包括：TargetOpened、BaselinePublished、ProviderArtifactReleased（内部）、QueryCompleted、InferenceCompleted、OverrideExpired、PublicTick、CutoffClosed、SessionEnded。

不要把每次内部资料更新都通知模型；只有共同专业产品更新、公共tick或自己请求的完成才按公开政策唤醒。否则“隐藏源是否有更新”会通过唤醒信号泄漏。

同刻政策建议：提供者/基线发布→已经在途的工具及推理完成→因基线变化失效处理→截止封存→恰好在本刻到期的覆盖清理→公开唤醒。覆盖在 commit_time <= c <= valid_until 的端点内有效；valid_until恰等于cutoff时，先封存该检查点再清理，不能将合法最后提交提前清空。对不确定的同刻可得性采取声明的保守边界。定义commit_time<=cutoff可接受，但cutoff之后才开始的调用不能回溯算在cutoff前；每个有实质动作有非零计时时长或明确事件序号，不允许同刻无限循环。

按每个事件实际时间处理，不在一次大跨度wait之后把所有中间事件都记成最终时间。

### 6.2 推理期间如何处理新信息

调用开始时冻结model_view与evidence_bundle_hash。模型返回内容只对应该快照。

在 `archive_costed` 主协议中，服务延迟/推理计时时间来自事先冻结的计时策略（或批准的校准配置），真实耗时单独记录；推理完成事件之前继续处理外部时间事件，但新内容不悄悄塞入在途请求。baseline版本已变则旧覆盖按协议拒收或标过期。

另设 `wall_clock_shadow` 使用实际收到/落盘时间，资源争用与超时原样记录。可以有 `logical_only` 工程轨，但不得称为真实耗时/时限性能结果。

同一个模型对应所有策略必须采用相同计时规则，不能给全读加人为惩罚。v1一个Agent会话只允许一个在途推理调用，工具可以有界并发；多Agent另轨。

### 6.3 动作建议

- `query(tool, entity_or_region, variable, valid_window, revision_policy)`：预留成本，冻结该时刻可用的具体产品。
- `read(receipt_id)`：仅允许完成且具有该run权限的请求；payload首次进入可见视图。
- `derive(operation, receipts, parameters)`：仅对已读证据做白名单计算，计处理资源。
- `override(target_id, base_revision, prediction, citations)`：不改目标，仅追加修订。
- `follow(target_id)`：撤销覆盖，跟随共同参考，不删除评分机会。
- `wait(until)`：推进事件队列但不跳过公共检查点，队列时间不作为未读内容提示。
- `stop_acquisition(scope)`：scope为本目标/时段/会话，v1选定且固定；即便不再查询仍处理基线、到期与评分。

预算耗尽不终止会话评分。非法调用、解析失败、超时分别记账；无效尝试不能通过无限免费重试获取额外算力。

## 7. 成本、缓存、失败与幂等

至少分四本账：

1. 上游查询/交付次数；
2. 传输字节与已读唯一资产数；
3. 确定性解析/派生操作；
4. 模型输入/输出token、调用数、图像像素或视觉token、运行时间。

离线下载的总体数据量与Agent运行时的逻辑访问成本分开。不要把回放本地读文件耗时称为卫星重访或网络服务延迟。

缓存键包含产品版本、变量、空间裁剪、时间支持、分辨率、单位转换和质量政策，不只用URL或文件哈希。

同一run已获得且已读的资产用于新目标，可免第二次上游费用，但重新放入模型上下文的token仍计费。一个run命中物理磁盘缓存，若其尚无访问权限，仍走相同逻辑费用/延迟；其他策略读过不能让该策略提前免费获取。

“同源但不同地点/变量”不合并成同一事实。“同一产品两个镜像”是否仍付网络费用按工具合同说明；不能按结果调整。

每次接受请求先写intent并预留预算，再执行和写回执；原始模型回复落盘后才更新状态。request_id+action_id做幂等；恢复从最后已封存事件重建，未完成在途请求标记为interrupted，不当作没发生后重新抽更好回复。日志损坏的内部行fail closed，只有明确的末尾未提交片段可按恢复协议隔离。

Range代码修复加入P0：累计字节加本次实际Range（含预读）必须先检查；没有版本标识不能把(None,None)当对象稳定证明，需可靠条件请求或独立可信哈希路径。现有字节未因此被判坏。本轮未重跑这些旧测试。

## 8. 基线与参考系统

### 8.1 最小基线集合

B0 FollowLatest：不额外查询，始终共同参考。
B1 StatisticalPostprocess：只使用同一免费信息的冻结校准/偏差修正。
B2 RoundRobin：共享总预算下固定轮询；接相同预测后端。
B3 RiskDeadlineFirst：由公共基线风险、不确定性、截止和已读数据年龄决定优先级，权重在开发期冻结。
B4 BudgetedAllRead：按同样权限、成本与资源限制尽可能全读；超出预算的全读另表。
B5 ActiveRaw：固定LLM/VLM负责选择与预测，无特权状态修复。
B6 ActiveLineage：同后端、同预算，使用从合法已读资料生成的结构化证据状态与来源关系。

固定流程、随机或贪心可以作为增补；不必一次把所有AFA方法全复现。任何借鉴算法需要相应训练数据，不能把论文算法名贴在简单启发式上。

### 8.2 获取、感知、预测、门控分离

`AcquisitionPolicy`只读公开视图；`EvidenceInterpreter`只读已授权资料；`Forecaster`根据相同格式证据输出；`RevisionGate`决定提交或follow。不同模块可以使用同一个模型，但接口与日志必须分开。

先做固定获取×主动获取与数值后端×LLM后端的交叉比较。VLM原生输入与数值提取是不同representation轨，不在取证因果对照里一起改变。

v1不学习一个复杂策略。先实现Follow、固定轮询、风险/截止启发式与LLM工具策略。若简单启发式已强，保留其结果再讨论是否需要训练门控。

### 8.3 轻量预测器范例（待训练并冻结，不是保证有效）

温度：官方点预报+在过去观测上计算的历史预报残差/趋势特征，岭回归或明确固定融合；不得使用目标时刻未来观测生成修正特征。

能见度：完整TAF结构和开发期标签拟合概率参考；付费站报增强在另一predictor中加入近期湿度/风/能见度/趋势等允许信息，计其数据访问。

图像：固定提取器或已冻结编码器生成空间和变化特征，与数值后端融合。图像信息只有通过查询后才可访问。

## 9. 配对实验、选择性修订与依赖

记录四种不同关系：产品谱系（副本/派生/共享上游/未知）；事实出处；目标相关性（预登记几何/变量关系）；Agent声明的预测依赖。不能把后者当自然界真实因果关系。

两个主实验层：

- 完整session重跑：相同目标/结果/共同基线，改变数据访问或表示。允许策略后续选择变化，测系统效果。
- 固定前缀分叉：冻结相同已读前缀和模型输入，限定修复一个可验证事实/状态，测该干预的恢复；不得偷看未来结果选择正确答案。

情景：clean、exact_duplicate、lossless_reexpression、stale_redelivery、source_outage、delayed_delivery、additional_complementary_source。

情景选择、时间和强度在开发侧固定；自然事故和人工注入分开。近未来信息晚到不是“天气反事实”。来源outage若基于更丰富未来内容触发则属于特定诊断，不冒充自然监测分布。

副本对照必须确定同变量、同地点、同时间窗、同起报版本。现有GWIS(-4,40)与EFFIS(-7,42)只支持共享上游，不是同一事实副本。

局部状态修复只认证可机械确定的字段/计算依赖。两个站点不同不等于天气独立；不对一般概率要求无关目标逐字不变。显示同一已读图像的数值提取属于有成本/声明的诊断，不是免费真值。

## 10. 评分与统计

### 10.1 按完整机会表评分

评分器以opportunities为左表，按cutoff解析最后合法有效覆盖或共同baseline。结果资格掩膜对所有策略相同；unresolved在总机会数中保留并报告。可结算样本的误差报告必须同时给出数据覆盖与缺失分层，不能假设缺测随机。

连续变量：MAE作为基础；分布预测采用合格的proper score。能见度删失主线用可确定的二元事件，不把上界6SM写成精确连续数值。每个时距、灾种分层。

若某Agent未提供概率，系统回退到冻结的共同概率基线并标记probability_fallback，而不是暗中把点值转成0/1充当完整概率预测。

### 10.2 净收益、改善与破坏

对同一机会集合与相同权重w：

`Delta = sum(w * (loss_base - loss_system)) / sum(w)`

`G_plus = sum(w * max(loss_base-loss_system,0)) / sum(w)`

`G_minus = sum(w * max(loss_system-loss_base,0)) / sum(w)`

验收 `Delta == G_plus-G_minus`（浮点容差事先固定）。报告修改率、合法提交率、fallback率、数据缺失率、资源成本。不能只在Agent修改的子集上报主分。

同单位也不自动允许跨流域裸MAE平均。先按站/区域时间块报告，必要的尺度参数从开发集冻结，禁止从测试结果拟合。

### 10.3 提醒与决定独立于预测主分

提醒由公开决策规则从系统概率/预测派生，动作词不影响主预测评分。event_id关联按结果侧固定分组，告警合并/cooldown/解除规则预注册；一个真实事件不能因重复消息多得命中。报告POD、false alarm ratio、false positive rate时给公式和分母，避免简称混淆。

首次提前检出按预定义事件起点和合法提交计算；一小时routine METAR目标不等于连续能见度首次跨线时刻。窗口稀疏时只报其可支持的提前量区间或报告定义。

决定损失可用公开成本—损失情景，不能直接解释成现实减少损失。截止前等待免费且动作效果相同时，不人为奖励更早同样动作。

### 10.4 划分与不确定性

开发、校准、选择、确认数据分开。按父天气过程/区域时间块切分后再生成表示/预算变体。同一母风暴造成的多灾种、同站相邻窗口、重叠影像不能跨split泄漏。边界purge至少考虑最大输入回看+最大预测时距+标签持续规则，具体数值在任务合同冻结。

自然监测队列与极端富集诊断队列分开。按session/父事件做paired block bootstrap；缺少独立块时只报描述结果。随机种子不增加独立天气样本。测试集不能依据Agent错误或增益反向筛选。

## 11. 资源与实验矩阵

先CPU/mock通过，再批准模型实验。延续不超过4张H100作为方案上限，不意味着必须用满。

首轮模型建议两个后端即可：已有Qwen3-8B用于文本回归；一个本地完成加载/图像输入/结构输出smoke的开源VLM。固定权重revision、tokenizer、chat template、dtype、解码配置与推理框架；不把模型名称相同视为运行配置相同。

先跑clean与一个关键扰动，不一次扩全部情景。程序基线可以先覆盖全部组合。确认主要假设后再增后端、区域和预算敏感性。

成本估算使用：`sessions × public_wakeups × calls_per_wakeup × policies × seeds × conditions`，不能把stations×targets直接等同LLM调用数。例：3机场×72h×3时距=648机会，若每小时最多2次模型调用则每策略每情景上限144次；若另允许completion唤醒，需计入单独上限，不能仍报144。实际token由dry-run的上下文序列化统计，不凭空承诺GPU时间。

同一session在单个逻辑owner顺序运行；并行的是独立session/条件/后端，不在一个session内部让多个进程竞写账本。原始数组可由所有worker只读缓存，但各run权限和逻辑成本独立。

AFS存放不可变原始资产、检查点、已封存分片和最终结果。活跃SQLite（尤其WAL）放执行节点本地；不要让不同CCI在网络文件系统上共同写一个WAL数据库。允许单writer写追加trace并定期以不可变小段同步，需验证原子发布和恢复行为。

实际CPU采集器与GPU推理器分开。数据工作使用已批准网络入口；不把GEE或任何代理作为绕过站点授权的途径。运行模型时不开放自由互联网和全AFS挂载；模型服务只接收公开视图，评分进程单独读Gold。

## 12. 8个可独立审阅的实施提交

| 编号 | 主要改动 | 必交付 | 放行条件 |
|---|---|---|---|
| PR0 | 冻结基线、依赖与下载器回归 | BASELINE_PIN、源码/环境锁、旧测试结果、Range修复测试 | 不改旧结果；边界反例拒绝；无凭据进入Git |
| PR1 | 新contracts、opportunity、override政策 | schema、合成session、协议例子 | 有符号/区间/跨变量/身份校验；策略不改变机会分母 |
| PR2 | 无网络离散事件引擎、账本和恢复 | reset/step、完整trace、mock策略 | 时间不回退、deadline race、缓存隔离、预算、重放、崩溃幂等通过 |
| PR3 | 连续TAF/METAR数据编译与完整基线 | 原生语义报告、固定连续小包、coverage/Gold表 | 条件段不丢、删失/QC/COR处理、预报与输入时间隔离 |
| PR4 | 数值/统计/固定取证基线与温度迁移 | 全机会scores、G+/G-、风险/成本曲线 | 不使用LLM也能端到端，负温度与缺测成立，强基线公平 |
| PR5 | 模型后端、固定/主动/来源状态策略 | 原始输入输出、消费计数、加载smoke | 输出结构、合法引用、资源上限、同输入重放核验 |
| PR6 | 同期多模态及配对情景 | 一条原生视图链、已读前缀分叉、消融 | 相同target/Gold、无特权未来标签，互补与重复分开 |
| PR7 | 独立会话确认、影子模式适配与发布 | 冻结确认协议、结果区间、data/model cards、轻量复现包 | 报全部缺口/失败，权限/许可审查，影子不触发现实行动 |

阶段依赖为PR0→PR1→PR2；数据PR3可在合同稳定后并行；PR4依赖PR2/3；模型PR5须经单独资源批准；PR6依赖已有任务闭环；PR7只在所有主要比较冻结后运行。不要用日历工期代替放行标准。

## 13. 必须覆盖的验收测试

详细机器可读清单见 `acceptance_checks.json`。至少覆盖：

- Empty/follow策略对所有有共同基线机会产生同样输出，主损失差严格为0；预算为0仍保留全部机会。
- 基线更新自动失效旧base-bound修订；同内容镜像不导致虚假失效；未来目标变化不能复用旧值。
- 请求快照不变；在途推理不获得新资料；完成时间晚于cutoff不能生效；同刻优先序确定。
- 已读内容在同run跨目标复用，不跨run泄漏；隐藏副本索引和私有缓存命中不泄漏未来信息。
- `available_at`控制当时访问；修订版历史观测不可倒签；模型绝不读取未裁剪多日全文件。
- 负温度合法；1000m严格边界、P/M/9999/CAVOK和区间开闭性按官方定义；TAF未重复字段正确继承；不支持操作符隔离。
- 不提供概率时有明确回退，不把点预报当校准概率；未结算不是负例。
- 同目标累计窗/站点/基准不一致拒收；query不同variable不从kind全池误选。
- 同站点未来结果在之后可合法作新目标输入，但永远不能改变过去提交；首版不反馈私有评分。
- 任意seed/故障组合中spent+reserved不超预算；未知动作和长输出受计算/次数限制。
- 重启恢复结果一致；已保存模型回复不重新采样；内部损坏日志不静默跳过。
- Gold改变不应改变固定运行阶段输入/trace；可见切换之前的隐藏未来文件名/内容变化不影响公开视图。
- G+−G−=Delta；仅修改子集不是主分；所有策略使用同一结果资格mask。
- 共享预算与每目标独立预算分轨；干预变体与同母事件不可跨split。

合成夹具只证明工程语义，永远不计真实天气结果或科学性能。

## 14. 外部代码如何借用

- EWB：`src/extremeweatherbench/inputs.py` 的变量映射与forecast/target组织，`evaluate.py`/`metrics.py`供后续选定函数核查；本次没有复现其全套指标或下载整库。采用局部适配器，不把其依赖树无条件搬入核心。
- FutureSim：`environment/replay.py`的动作日志重建与状态恢复组织。本次看到其读日志会跳过JSON错误；DisasterTrace确认评测不能照搬这种容错，应fail closed且保留损坏记录。也不复用自由文本answer matcher作Gold。
- AFABench：成本/策略/预测器分离与固定、贪心、序列基线组织。公开说明主要分类任务，连续变量需独立适配，不能宣称现成支持。
- SimPy：借鉴时间事件稳定排序设计；v1选标准库heapq即可，避免同时引入两个调度器。
- vLLM：结构输出功能可降低格式噪声，JSON约束不认证科学语义；按安装版本验证，不从旧文档硬写guided_json参数。主比较所有策略使用相同约束。
- SQLite：本地索引或单writer状态可使用，网络共享写WAL不采用。

每个真正导入的外部代码记录repo、commit、blob、许可证、被修改路径、测试以及与原方法的差异。当前源blob仅表示阅读的文本版本，不声称已运行或完整复现对应方法。

## 15. 待实现CLI与推荐首轮交付

下面命令是目标接口，必须先实现对应入口后才能运行：

```bash
python -m disastertrace.monitoring_v1.cli validate-config configs/monitoring/dev_airports.yaml
python -m disastertrace.monitoring_v1.cli compile --config configs/monitoring/dev_airports.yaml --offline --out artifacts/monitoring/build_001
python -m disastertrace.monitoring_v1.cli run --bundle artifacts/monitoring/build_001 --policy follow --backend program --out artifacts/monitoring/run_follow_001
python -m disastertrace.monitoring_v1.cli verify --run artifacts/monitoring/run_follow_001
python -m disastertrace.monitoring_v1.cli score --run artifacts/monitoring/run_follow_001 --out artifacts/monitoring/score_follow_001
```

输出目录必须新建，不能覆盖旧run；评分入口在独立权限进程调用。`compile --offline`缺本地源即报告，不自动联网补齐。缺真实站点/日期/模型许可/资源批准时校验拒绝运行。

第一轮实际目标不是“完整16灾种benchmark”，而是：一个连续监测小包、一个完整专业基线、一个Follow和固定策略、一个可重放环境、一个不依赖LLM judge的全机会评分器。拿到这一套之后再批准模型和多模态阶段。

## 16. 来源与本次核查范围

用户代码固定提交：`ae69453ff15bc3def6c513fafbfd8758437a8587`。

| 编号 | 来源（公开/私有） | 用途 |
|---|---|---|
| R1 | 用户仓库 `active_warning_v1/schema.py`，blob `6088acb1c20e74e3704769dd23e322b1a5892e1a` | 值域、任务族与时间限制 |
| R2 | `active_warning_v1/environment.py`，blob `1e1000517524d0370a0271be930e9d1a5f8d8596` | 请求快照、读取与规范视图 |
| R3 | `active_warning_v1/policies.py`，blob `f7bebb6a148e7adc0d9daf5d69fb6daea1626426` | 两轮编排与轨迹重放 |
| R4 | `active_warning_v1/scoring.py`，blob `9cc5d7575a6b223c5fdbb17c859dd4e0bc04e625` | 原检查点评分与回退 |
| R5 | `task_chain_feasibility_20260912/build_chains.py`，blob `f2bc1315af6b657c1d5cb80674721c51e596825a` | TAF/METAR与HEFS解析 |
| R6 | `task_chain_feasibility_20260912/README_CN.md`，blob `1ae60b5debb08ad8f799388673c3f7411f905d3f` | 真实任务链和未决条件 |
| R7 | `active_forecast/README.md`，blob `945efe401912e278944f8320216b187d76115cee` | 精确核、八卡和证书边界 |
| R8 | EWB `inputs.py`，blob `968861779e548b80545e61ed1bf2cc63d2d5d4bc` | 变量映射与适配层参考 |
| R9 | FutureSim `environment/replay.py`，blob `79c70b8b6ae21fbc4d7193651fa9279368a264c2` | 日志重建机制与不可照搬的跳错策略 |

官方说明/开源入口（2026-09-12读取，实际部署前冻结适用版本）：

```text
https://aviationweather.gov/help/data/
https://mesonet.agron.iastate.edu/request/taf.php
https://api.water.noaa.gov/about/api
https://extremeweatherbench.readthedocs.io/en/latest/data/
https://github.com/brightbandtech/ExtremeWeatherBench
https://github.com/OpenForecaster/futuresim
https://github.com/Linusaronsson/AFA-Benchmark
https://simpy.readthedocs.io/en/latest/topical_guides/time_and_scheduling.html
https://docs.vllm.ai/en/latest/features/structured_outputs/
https://www.sqlite.org/wal.html
```

本规格中的session规模、预算、选择性覆盖规则、事件优先序、PR分解和CLI是设计建议，不是上述论文或仓库已经实现的事实。未获得的同事件资料、校准集和未见测试不能用合成内容冒充。
