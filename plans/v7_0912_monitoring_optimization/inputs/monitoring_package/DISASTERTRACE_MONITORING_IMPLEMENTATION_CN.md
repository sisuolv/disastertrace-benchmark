# DisasterTrace：共享预算多目标监测与选择性预测修订实施计划

日期：2026-09-12  
已核对仓库：`sisuolv/disastertrace-benchmark`，分支 `next-phase-v1`  
固定阅读提交：`ae69453ff15bc3def6c513fafbfd8758437a8587`  
地位：供 Codex 执行的研究与工程计划；未修改远端仓库，未实施新监测内核，未运行新模型、科学数据下载或完整项目测试。

## 0. 必须保持的范围

保留 DisasterTrace 名称、已有16类灾害数据索引、历史结果及负结果。实现一次明确升级：从“每题独立预算”，变成“同一真实时段内的一组固定未来目标，共享信息获取和模型计算资源”。不要再另起多Agent、网页模拟或全球天气模型训练项目。

核心产物：`MonitorSession`、受控证据代理、共享成本账本、选择性预测状态、原生多模态预测适配器、独立评分与回放。下面新模块名和命令均是拟实现接口，并非仓库已有能力。

主问题：在共同最新合法专业预报下，系统如何选择目标与证据、复用信息、保持或修改预测？其收益和损害是否超过廉价程序、批量处理与简单统计方法？主动策略不必须胜出。协议不得依据测试结果削弱基线、提高费用或调整截止。

边界：不新增逐题人工Gold、不用LLM judge决定真值；可以继承已有专家标注并标明来源。只读研究型监测，不执行现实撤离、航班处置或水库调度。保留E证据、F未来预测、D研究情景的区别；首版优先E/F，D后置。

## 1. 实际代码基础与迁移决定

| 现有路径 | 本轮阅读到的实现 | 复用方式 | 不可直接照搬的部分 |
|---|---|---|---|
| `active_warning_v1/schema.py` | Artifact/Episode/Outcome严格分离；目标时间、变量、单位约束；当前只支持气旋/流量和非负值 | 继承强合同思路与旧数据只读桥接 | 所有证据同entity/variable/unit，两个family，非负限制，单个deadline |
| `active_warning_v1/environment.py` | 请求时固定版本；query/completed/read分离；预算、并发、引用与追加日志 | 提取等价的新session状态机行为，保留旧回放测试 | 为每个目标新建Environment会重置预算与缓存；canonical合并键不是通用产品谱系；fact仅数值 |
| `active_warning_v1/scoring.py` | 私有结果匹配；轨迹复算；最新业务参考、MAE、缺提交回退、组平均 | 借结算分离、固定分母与复算方法 | 初始值回退不等于动态FOLLOW_BASELINE；概率0/1回退不是校准基线；不能直接混合多单位 |
| `multimodal_v1/runner.py` | request/intent/raw/outcome封存；prepare先于dispatch；每轨迹自己的carrier；未知请求不自动重发 | 复用持久化协议和故障恢复 | 文件头明确是offline adapter，并不自身提供真实模型传输；不得共享不同策略的carrier |
| `multimodal_live_v1/adapter.py` | 真PNG进入processor；input_ids、image_grid_thw、visual tokens、张量哈希、原始输出记录 | 新backend包装其图像核验和运行捕获方式 | 旧提示是状态维护；只允许full_evidence、最多两图；新任务需独立白名单及配置 |
| `hydro_shadow_v1/pipeline.py` | 有限前瞻注册、真实落盘收据、监督超时、固定采集与结果版本 | 复用采集与提交持久化；写session适配，不复制旧作业 | 当前是程序基线、固定站点/轮次；不能当作已完成在线VLM或自然区域多目标共享 |
| `plans/task_chain_feasibility_20260912/` | 历史温度/TAF/流量配对、原生语义回归、程序对照（前序复查记录） | 将批准复用的解析逻辑放入新适配器并做差分测试 | 保留旧输出；不能直接修改旧解析器再覆盖冻结结果；完整TAF/趋势边界先修 |
| `plans/all_dataset_utilization_20260912/` | 来源登记、获取与解析证据（前序复查记录） | 作已存资产发现及角色准入入口 | `decoded_sample`不自动提升为正式session合格 |

阅读方式：本轮实际通过连接读取上表前六项关键源码。数据构建及97项语义陷阱同时沿用当前对话中此前固定提交复查，执行前须再核对实际本地文件与全部适用AGENTS.md。不得根据本计划重置未提交修改。

建议只新增一个顶层包：

```text
disastertrace-starter/src/disastertrace/monitoring_v1/
  contracts.py          # session/target/evidence/baseline/action/receipt/outcome
  state.py              # FOLLOW/OVERRIDE/closed + 纯事件归约器
  evidence.py           # 版本、表示、来源关系、合法视图与隔离
  budget.py             # 多维预算预留、记账与缓存费用
  scheduler.py          # 确定性事件队列与受控时钟
  baseline.py           # 完整业务基线与固定概率映射
  runner.py             # selector/predictor解耦、请求/结果持久化
  scoring.py            # 全目标E/F、损益、覆盖、成本
  replay.py             # 不再生成回答的独立重放
  cli.py
  adapters/
    legacy.py           # 原Episode只读导入
    aviation.py         # TAF/METAR合同、站点与时间
    satellite.py        # Satpy配置化解码与渲染
    radar.py            # 可选Py-ART读取
    hydro.py            # 第二任务族
    vlm.py              # 真实图像请求及processor捕获
    live.py             # 有界前瞻采集/真实提交收据
```

这是职责地图，不要求第一轮创建每个空文件。优先实现contracts/state/budget及一个窄入口，确有职责才新增模块。不引入Kafka、图数据库、Kubernetes或完整网页UI作为首版前提。JSONL为审计权威记录，SQLite可作可重建索引，大数组仍留现有持久资产目录。

## 2. 冻结首个研究对象

### 2.1 首选区域机场；水文作为第二路线

首条真实session从同一区域、同一真实时段的4–6个机场起步；工程上先验证2个机场的最小链，再扩。一个8–12小时监测片段、每机场若干固定未来报告目标只是工程规划，不是已找到样本或足够统计量。目标按报告计划、预先定义时段或输入目录选择，不按结果/模型表现选择。

公开初始与共同更新：完整适用TAF及固定基线表示。辅助：此前METAR序列、区域ABI观测/配置化物理图件、适用的雷达资料。结果：固定目标时刻/预注册选择规则下的原生能见度报告与QC。第一版可定义“未来例行报告的低能见度”，不要无条件称为整个时间窗内从未出现危险，更不要把低能见度统称为浓雾。

必须先做 `REGIONAL_JOIN_AUDIT.json`：

- 站点身份与经纬度能核验；同一真实监测时段。
- 每个目标有合法共同基线；同一资产可几何覆盖多个目标，且变量/时刻可能相关。
- 原始资料中观测/创建/发行/抓取/处理时间分开；历史availability未证明就使用受控轨。
- 原始TAF保留INITIAL/FM/TEMPO及适用操作符；未知操作符不能默默忽略。
- 当前METAR主体与BECMG/TEMPO趋势分离；缺当前能见度不得向趋势寻找替代；原生站号和时间与索引一致。
- P/M、9999、0000等删失规则保存为区间，不强转精确数字；质量与缺测保持。
- 相邻站点、同天气过程、相邻日与重叠图像的泄漏分组先确定。
- 本地旧KSFO与KDEN不同日期只能分别作解析fixture，不可拼成同时发生的自然session。

如果4–6个站点暂无完整TAF/影像/结果，保留已验证的2站试点或明确受限，不能删掉不方便的目标后仍声称原固定分母已满足。

### 2.2 TAF概率基线的放行条件

TEMPO不是某个精确时刻固定概率；prevailing-only可以保留为弱诊断，不可称完整专业预报。官方点值或条件段不自动具有唯一概率映射。

先建立完整TAF事实/条件解析，并冻结一种可审计任务表示。需要Brier/校准主分时，在独立开发过程上建立并锁定规则/简单统计概率映射；保留原始预报与校准器身份，称“业务资料派生概率基线”，而非官方发布概率。样本不足时先完成E和合适的非概率目标，不用唯一正例拟合校准后自测。

模型可看与基线转换相同的完整信息；不能让VLM读取TEMPO，而让专业基线永远丢弃。主获取比较中的预测器和输出类型固定。

### 2.3 第二条水文及16类扩展

水文使用真实相关流域内多站NWPS/HEFS、此前USGS及相关降雨/流域几何。既有多州站点说明接口可用，不自动构成一张图覆盖的自然共享场景。缺适用水位/流量阈值时先做相应连续量；只允许有依据的垂直基准转换。

NWPS常规服务不是完整历史预报档案；HEFS实验服务在本次官方说明中保留最近10天，产品还可能暂缺。因此近期有界前瞻采集可并行，长期回放不能假定接口能补全部版本。[R7]

16类索引继续保存；先同灾种多地点，后相近时间尺度的多灾种。分钟级对流与周级干旱不强行使用同一时钟。洪水/野火现成影像可先作E/物理演化诊断，只有真实截止前输入与后续参考匹配时进入F。每类发布完成的合同、独立过程和失败，不以统一题数凑覆盖。

## 3. 数据合同：目标、证据、行为三者分离

| 对象 | 必需字段和语义 |
|---|---|
| `MonitorSession` | session_id、真实区域/时段、全部target IDs、availability mode、成本规则、候选池快照、父事件组/划分、代码/配置哈希 |
| `TargetContract` | 实体、变量、单位/基准、有效点或区间、聚合、阈值比较符、域约束、deadline、权重、结果O/P/R身份 |
| `BaselineRevision` | 目标ID、业务原产品与版本、原文/数组绑定、合法交付时刻、完整表示、派生预测/校准器版本；先确保启动基线存在 |
| `EvidenceProduct` | 上游产品、提供方、实体/覆盖、变量/单位、观测与适用支持、版本链、创建/发布/首次捕获等时间、QA/许可/私有角色 |
| `EvidenceView` | 内容哈希、原产品集合、波段/投影/分辨率/裁剪/色标/掩膜、实际显示范围、展示时间、视图格式；不能带隐藏答案 |
| `Relation` | identity_duplicate/representation_of/derived_from/supersedes/shared_upstream/unknown；关联参考依据；metadata overlap不等于确证预测价值 |
| `Action/Receipt` | strategy/session/action ID、前置公开快照、工具/视图/目标集、预算预留、开始/完成/交付时刻、实际开销、失败/重试状态 |
| `ForecastCommit` | target ID、点/概率/分布类型、值、引用回执、as_of baseline版本、模式、命令ID、真实或逻辑提交收据；历史不能覆写 |
| `OutcomeRevision` | 固定目标、O/P/R、值/删失/QC、结果版本/捕获时间、pending/provisional/final/unscorable、统一结算规则 |

重要约束：

1. 结果必须严格匹配Target；输入不要求与Target同变量，只要求关联规则真实且范围合法。
2. 物理域由变量定义，允许负摄氏度、负距平或合适基准下负水位；禁止所有float一律非负。
3. 统一内部时区，原始时区/日界线也保存。数值可用Decimal或明确精度表示；不做未声明舍入。
4. 新产品身份与新URL、渠道身份不同。缓存按产品版本和内容哈希，不只按URL。
5. 全候选资产与输出私有区不挂给模型；公开metadata只能包含当时已发布字段，不能含从未读数组或标签计算出的“有用/无用”。
6. 目标集和权重在结果前冻结；新增/取消目标需协议支持并记录，首版不允许任意删目标。

## 4. 选择性修订状态机：首先消除KEEP歧义

### 4.1 状态而不是一次性值

每个目标维护以下模式：

- `FOLLOW_BASELINE`：默认的持续委托策略；在目标截止前跟随共同基线的合法更新。
- `OVERRIDE`：模型显式提交自己的预测及其使用的基线版本；保持至后续显式修改/回归基线或目标关闭。
- `CLOSED`：到目标自身deadline封存最终生效预测，后续任何新资料或预测不回写。

另记录 `explicit_action`、`default_delegation`、`invalid_submission`、`baseline_auto_update`，不能全部计为模型成功提交。

### 4.2 最小动作集合

| 动作 | 含义 |
|---|---|
| `READ(product/view/query_spec)` | 选择当前合法资料；底层分获取、处理和交付，产生回执 |
| `PREDICT(target_ids, view_receipt_ids)` | 调用固定预测器，只为所选目标推理，实际消息/token/图像全部记账 |
| `REVISE(target_id, forecast, citations, baseline_revision_id)` | 提交新预测，切换OVERRIDE |
| `FOLLOW_BASELINE(target_ids)` | 显式撤销自有覆盖，重新跟随共同最新基线 |
| `NO_CHANGE` | 不做新修改，保持现有模式；不是自动跟随新基线 |
| `WAIT(until or public_event)` | 让环境推进，不能获得未来隐私事件时间作为提示 |
| `FINISH_ACQUISITION` | 不再做主动获取/推理，但环境仍按已声明模式推进到所有目标关闭 |

`PREDICT`是实验runner的接口；若端到端策略直接生成预测，也必须经过相同提交合同和费用记录。为了隔离调度效果，首版建议selector输出资料/目标选择，再由同一个固定predictor执行预测，不让不同策略偷偷换预测器。

### 4.3 必须通过的例子

- A初始基线0.20，默认FOLLOW。基线变为0.35且A未被选择：生效值0.35，标记为委托更新，不算新模型预测。
- B在0.20基线上提交0.60，进入OVERRIDE。新基线变0.35但没有新动作：B仍为0.60；不能自动变成0.35、0.75或选择后来分数更好的值。
- B显式FOLLOW后恢复0.35并跟随后续合法更新。
- A截止后基线再更新：A保持截止时的值，后续目标仍可继续运行。
- 同批提交中A已过期、B尚合法：按每目标独立校验/收据处理；原批次和每项拒收保留，不因A失败丢失B，也不替A追溯补交。
- 模型基于b_v1推理时b_v2到达：输入快照保持b_v1；完成时提交若仍在截止前，可按预定政策接受并标明based_on_stale_baseline，不能暗中移植增量。首版采用“接受合法快照、报告版本年龄”；其他政策单独做实验。

这是一种明确的研究协议，不保证模型绝不会损害基线。若选择覆盖过期或TTL策略，要在运行前另行冻结，禁止事后因坏结果自动重置。

## 5. 共享证据：三层缓存与三条权限边界

### 5.1 缓存分层

1. **研究原始资产缓存**：实验构建者可以一次获取许多公共文件，供多策略物理复用；成本在研究账本报告。这里文件存在不意味着策略已获访问权。
2. **策略session获取/渲染缓存**：某策略首次合法取得某产品版本后可为多个目标复用。新裁剪/分辨率/通道形成新视图，依实际处理计成本。
3. **模型上下文/表示缓存**：每次实际送入模型仍计算token/图像和处理费用；只有真实实现并验证的KV缓存/特征缓存才能计为复用，不能凭“以前看过图”宣称本次零费用。

缓存key建议：产品稳定ID + 版本 + 内容哈希；渲染key追加波段/投影/尺度/裁剪/QA/代码版本。相同bytes不同来源仍保留来源身份，不等同于独立信息。每个策略session隔离授权、预算、外部记忆和预测；可共享不可变公共原文件，不共享其他策略的回答或私有未来参考。

### 5.2 花一次成本帮助多目标的准确含义

“网络取得同一产品版本一次”可以共享；为每机场做新的高分辨率裁剪仍有处理成本；把同一图连续发送给预测器仍有视觉输入成本。共享推理一次输出多目标可能节约总成本，但会改变预测器行为，应作为后续联合推理因素，而不是与调度策略混在一个对比中。

若一次区域视图便宜地覆盖全部站点，批量全读可能就是最优强基线。不能人为增加每站网络费用使Agent获胜。AWC官方提供批量缓存并建议大查询使用它们。[R6]

### 5.3 公开信息边界

未读资产可以公开原产品本来提供的时间、波段、名义覆盖、文件大小与费用预估。不能公开：未来总版本数、私有正例位置、从未读像元算出的事件强度、隐藏质量分或“值得获取”标记。几何名义覆盖可以用于metadata greedy；有效像元覆盖只有原产品已公开或经付费读取后才属于策略知识。

## 6. 全局成本账本

至少分别记录研究端和策略端，策略端再分：网络请求/字节、解码/重投影/渲染时间、文本输入token、视觉token或像素、输出token、selector调用、predictor调用、CPU/GPU实耗、墙钟。

主报告给各资源的原始量及质量—预算曲线，不强迫不同单位相加成一个“真实费用”。为了可重复压力测试，可以定义标准化访问/推理配额，但名称、标定和与真实费用的差异必须公开。

并发执行需要先原子预留：

```text
validate action
  → compute public quote / reserve bounded resource
  → durable intent
  → dispatch
  → actual receipt
  → settle reservation vs actual cost
```

不能两个并发操作都看见剩余额度，分别开始后一起超预算。输入token、图片token和输出上限在prepare时核验；未知费用用有界上限，超限请求明确拒收/停止。失败下载也计实际消耗，无自动无限重试。成本预估只能使用公开元数据或开发期标定，不能偷看测试Gold。

冷/热缓存条件、模型加载预热是否计入、并行上限预先声明。不同策略物理运行顺序不能影响逻辑收费；真实测时交错顺序并报告硬件争用。保持不取证程序、廉价校准和批量程序作为对手。

## 7. 单时钟session调度，而不是循环运行N个Episode

首版使用单写者事件归约器，异步IO可以并发；不需要分布式队列。

事件类型：`BASELINE_DELIVERED`、`EVIDENCE_DISCOVERED`、`READ_REQUESTED`、`VIEW_READY`、`MODEL_STARTED`、`MODEL_FINISHED`、`COMMIT_RECEIVED`、`CHECKPOINT`、`TARGET_CLOSED`、`OUTCOME_ARRIVED`。

推荐两个运行层级：

- **受控固定机会版先做**：公共检查点供selector决策，所有目标共享预算/缓存；研究目标选择/复用即可，不同时引入自由唤醒难题。
- **事件驱动等待版后做**：策略可WAIT并选择唤醒条件；环境真实到达和截止推进。必须禁止零时延无穷循环，事件/动作数有上限。

### 7.1 replay与live

`replay`用明确的虚拟时间、已封存资料时间线和开发期冻结服务/计算费用模型，不因为本次GPU快慢改变控制条件。另记录实耗用于效率分析。严格历史时点无法证明时标archive_controlled，不能冒充verified_historical。

`live`用服务端UTC收据判断合法时间，用monotonic计实际耗时。获取完成、渲染完成、处理器输入快照、推理完成与落盘提交分别记录。目标deadline每条独立。所有同刻事件使用确定的 `(time, priority, sequence)` 规则；例如先处理此前可交付的公共信息，再收截止前完成的commit，最后关闭目标。live最终以真实持久化收据是否超过deadline判定，不能通过优先级给迟到答案回填。

不要直接把SentinelBench的speed_factor搬成“把12小时压到3分钟”，却继续把不变推理时长当真实预警性能。其源码在加载时缩放事件、保留固定墙钟反应窗口；这属于其自己的实验协议。[R1]

### 7.2 简化伪代码（待实现，不是现有接口）

```python
session = compile_registered_session(...)
engine = SessionEngine(session, evidence_backend, budget_policy)
for event in engine.events_until_session_closed():
    engine.apply_public_event(event)
    engine.close_due_targets_using_durable_commits()
    if not engine.is_public_decision_opportunity(event):
        continue
    view = engine.public_view()  # 不含隐藏内容、结果和未来目录
    proposal = selector.act(view)  # 调度开销也计入
    for action in engine.validate_and_reserve(proposal):
        engine.dispatch(action)   # 锁定请求/图像/基线版本快照
    engine.journal_and_checkpoint()
# 在独立进程中加载Outcomes，按固定分母与版本规则评分
```

需要明确的调度测试包括：推理途中新产品出现、某目标截止而其他目标未截止、重启恢复后不二次扣费/生成、inflight结果在截止后返回只存raw不生效、结果成熟不泄露给仍在运行的预测器。

一个早期目标的结果后来可能作为真实公开观测，合法服务另一个更晚目标；应由原始provider观察流及其时间规则决定。不能把grader的分数或私有最终修订值直接注入模型。

## 8. 原生多模态的实现与开放代码复用

### 8.1 图像管线

原始文件 → 物理解码/校准 → 固定投影与空间视图 → 通道与时间拼图（明确标签） → QA与nodata呈现 → 真实图像消息 → processor张量 → 原始回答。

可复用Satpy的ABI L1b reader和Scene/load/resample/save流程；其公开代码文档提供NetCDF/xarray读取及红外亮温校准。[R4] NEXRAD可用Py-ART读取和绘制，并保留扫描层、变量与质量，不自己猜二进制定标。[R5]

不使用未来图像做逐scene自动色阶/标准化，不用隐藏掩膜绘制“参考边界”。固定的多通道物理合成可以是正式视觉输入，但需要单独标识派生图而不是原始自然彩照。夜间不可见光照条件与传感器遮挡不填成无灾；不能因一张图有云就断言站点地面可见度。

GOES资料中存在2018—2024再处理数据，重新计算的辐射/几何与运行时版本不同。[R8] 对历史业务轨必须区分operational与reprocessed；后者可以做受控研究，但不能写成原时刻已公开版本。卫星平台/通道按所选年份真实匹配。

### 8.2 复用已有VLM适配器，但重新定义request

保留 `multimodal_live_v1/adapter.py` 的这些核验：

- 实际图像而不是路径/base64文本占位进入模型；
- PNG身份与维度、图片计数、image_grid_thw和视觉token一致；
- context reservation在持久化dispatch之前；
- 实际输入token、图像哈希、处理器张量哈希、输出token与finish reason记录。

新request含session、active targets、合法baseline、授权view receipts和策略自己的状态。旧 `access_track=full_evidence` 与2图限制不能简单删掉；以版本化图像/token上限替代，并有fail-fast/预算内用户可见降级规则，不偷偷降分辨率。

第一版固定同一VLM与同一单目标forecast prompt，只让调度器选择何时为哪些目标调用它。这样不会因联合输出、多目标上下文、额外变量等同时变化失去可比性。联合多目标推理作为独立后续因素。

`PREDICT`只读该策略已获授权的view。selector如果需要看图也要计视觉输入。不能让它在后台免费阅读所有图片，再给predictor只计被选图片。

### 8.3 开源借用清单与边界

| 来源 | 本轮核对层次 | 建议使用 | 明确限制 |
|---|---|---|---|
| Sentinel `server/timing.py` | 真实源码 | 事件生命周期、有限运行与等待测时思想 | 不是天气虚拟时钟的直接替代；不移植10套模拟网页 |
| AFABench `afabench/core/types.py` | 真实源码 | act/predict分离、合法动作mask、预算与stop对照 | API允许oracle方法传label，普通策略适配强制无label；默认单位费用不能冒充真实服务费用 |
| EWB data model | 官方实现文档 | ForecastBase/TargetBase、init/lead/valid、变量映射与惰性读取 | 数据可能是固定历史文件；单位转换不能做两次；目标支持与质量仍自己核验 |
| Satpy ABI reader | 官方reader文档 | NetCDF/物理校准、重投影和固定合成 | 不代表自动知道地面雾或给出Gold |
| Py-ART | 官方文档 | NEXRAD读取、扫描/栅格处理与图像 | 不自动替代雷达QC、任务标签或物理归因 |

仓库代码使用前再锁整个commit/release、依赖版本与许可证。本次记录的Git blob SHA仅证明所读文件版本，不等于整个外部仓库commit。详见source_reuse_registry.json。LEAP可作后续固定证据融合对照，但未审计的外部finalizer不能算完整复现；本轮不引入它阻塞首版。

## 9. 基线与实验：先拆因素，再扩大

### 9.1 必须保留的对手

1. 永久FOLLOW最新完整业务基线，无额外LLM。
2. 同资料下的持续性/气候态/开发期冻结校准与简单融合。
3. 均匀周期分配、最早截止优先、经合法校准的近阈值优先、公开覆盖/时效贪心。
4. 批量获取/并行全读；同预算可行就进入主表，超预算则额外资源上界单列。
5. 固定同预测器的主动selector。
6. 独立逐目标策略，但享有合理批量缓存和相同总资源，不故意重复下载削弱它。

没有可靠概率时不能用距0.5随意排名；阈值优先可用量纲规范化的预测裕度，并在开发期冻结尺度。coverage greedy只看已公开覆盖元数据，不用隐藏参考选择最危险目标。

### 9.2 先进行2×2机制对照

| 条件 | 分配 | 授权证据/渲染共享 |
|---|---|---|
| B00 | 逐目标固定分额 | 目标独立，记录真实批量底座成本 |
| B01 | 逐目标固定分额 | session可复用已获得共享产品 |
| B10 | 全局动态分配 | 目标读取范围隔离 |
| B11 | 全局动态分配 | session共享 |

主对照还要有廉价的“独立预测+合理共享缓存”基线，避免把去掉重复IO的普通工程收益称为智能调度收益。B00等禁共享条件是明示机制消融，不是唯一竞争对手。初轮predictor调用仍逐目标同构；联合多目标预测另加因子，避免同时改变预测器。

先单独验证selector有可辨识机会：小开发集枚举有限可行路径，事后最佳仅诊断，不选测试题、不作为部署方法。若完整全读也不能利用信息，检查感知/融合与参考，不宣称信息论无价值。

### 9.3 选择性修改与局部传播

比较全部重写、规则触发、模型选择REVISE、一直FOLLOW。记录改好/改坏/保持次数及幅度、实际修订率、deadline违约、信息使用与被忽略目标。自动baseline变化不算模型修订。

同源等价表示/旧版/新观测/受控时延按固定原始事件创建分支。相同底层未来结果不变；E按分支已合法交付证据核验。未来概率对某个地区证据变化也可能有合法相关响应，不能用简单几何“不重叠”就强制所有F预测不变。确定性局部不变性主要用于适用范围明确的E事实或严格等内容对照；F响应看proper score、校准和配对统计。

来源依赖实验先核验同地点、变量、有效时刻、版本与内容。GWIS/EFFIS共享后端但不同地点的现有两个请求，不是等信息副本。

## 10. 评分与统计

### 10.1 有效预测

每个目标deadline用明确模式解析出的合法预测。FOLLOW使用deadline前最后合法基线；OVERRIDE使用deadline前最后合法模型提交。漏交/非法行为按协议保留其生效旧状态，另计失败，不能自动挑结果更好的预测。

所有预登记目标都出现；不查询不删目标。初始无可用基线则在任务准入前记录失败；运行中的基线更新缺失按冻结政策沿用最后合法值并报告过期，不悄悄切换参考。

### 10.2 分数

- E：可验证的单位、时间、来源、版本、地理适用范围与图像定位；引用存在不等于语义正确。
- F：连续量MAE/合格分布CRPS、二元Brier/校准。区间不能确定标签就按既定规则留未结算；不转阴性。
- 成本：独立报告各资源与预算档，不任意混单位造总分。
- 修订：净收益、改善幅度和恶化幅度、修订覆盖率、极端/近阈值表现、最长目标未处理时间等预注册诊断。
- D：只有公开成本/准备耗时/截止作用定义后单列。等待无成本时保留等待至deadline基线。

同一尺度目标可定义：`d_j = loss(b_j,y_j) - loss(p_j,y_j)`，session内先归一化预登记权重，再按session及独立父过程汇总。`sum(max(d_j,0)) - sum(max(-d_j,0))`是损失差的算术分解，不是获取/感知/状态的因果可加分解。不同单位连续量分开，不能直接平均风速和水位误差。

session数不等于独立事件数。地点/时间/父天气过程/重叠图像构成聚类；多个seed、deadline、阈值和图像裁剪不增加独立N。确认集在策略冻结后使用；不因低能见度未出现或Agent未胜出而删窗口。

自然固定监测队列与事件富集诊断队列分开。普通窗口用于虚警与自然发生率校准；未知采样率的富集集不能外推业务收益。

### 10.3 独立结算与复算

grader和agent运行进程的挂载、凭据与网络隔离；getter只开放按规则授权的当前视图。结果本体与私有标签不随run包发送。HTTP内容/业务文字视为数据而不是执行指令；首版无任意shell工具。

保存命令、input_snapshot、intent、raw response、processor记录、receipt、commit、cost events。重放使用原始回答重新解析，不重新生成更好的答案。哈希链提供变更可检测性，若可重写全部链并不能单独提供可信时间戳；live以独立/受控服务的持久化收据封存。

结果pending/provisional/final/unscorable按固定成熟规则追加，不按预测误差挑最佳观测版本。所有策略使用同一结果快照与结算mask；分别报告结算覆盖和模型行为失败。

## 11. 工作包、依赖和首轮范围

全部工作包的机器可读定义见 `specs/work_packages.json`；测试验收见 `specs/acceptance_tests.json`。其中test只是拟实施规格，不是已经通过的测试。

| 编号 | 工作 | 主要依赖 | 验收产物 |
|---|---|---|---|
| M00 | 工作区盘点、冻结保护、复用映射 | 无 | 基线manifest、实际AGENTS/HEAD/dirty状态、本地测试命令与边界 |
| M01 | 目标/证据/session合同与FOLLOW/OVERRIDE状态 | M00 | 强类型合同、纯归约器、负值/删失/目标deadline/模式测试 |
| M02 | 数据语义适配与完整业务基线 | M00 | 原生解析、完整条件段、拒收账本、独立基线映射策略 |
| M03 | 证据代理、缓存授权、成本预留 | M01 | 版本化store、每策略隔离、原子预算、fake IO测试 |
| M04 | session调度与提交日志 | M01,M03 | 单时钟多deadline、重启无重复执行、run/resume/replay命令 |
| M05 | 区域资料配对与真实多模态编译 | M02,M03 | REGIONAL_JOIN_AUDIT、公开/私有分包、原生图像及渲染manifest |
| M06 | 强基线、selector/predictor及共同更新 | M02,M04,M05 | 批量/周期/截止/覆盖/FOLLOW对照、共同基线一致性 |
| M07 | 独立评分、分母与机制测试 | M01,M04,M05 | 不调用模型的独立replay和grader、不可解/缺测状态、损益表 |
| M08 | 接通真实VLM、预算与故障记录 | M04,M05,M06,M07 | processor回执、限定模型小批、已读权限与图像/token成本 |
| M09 | 机制试点、独立确认设计 | M06,M07,M08 | 共享/分配2×2、选择性修订与图像对照、负结果、样本量规划 |
| M10 | 有限前瞻、打包与发布 | M04,M05,M06,M07（模型前瞻另需M08） | 预登记新目标、真实收据、后续结算、复现包、覆盖/许可说明 |

推荐首轮交给Codex：M00、M01、M03、M04与M07的合成离线部分，并行M02已有资产语义核查。不要先跑M09的大模型矩阵。M05先列真实候选和预算，获准后有界取样；M10前瞻只运行新有限范围，不接管或重启旧作业。

阶段门槛：

- G0：2–3虚构目标纯协议fixture通过（只证明工程语义）。
- G1：一个真实2站多模态session可由程序完成；没有真实配对则明确阻塞。
- G2：4–6站session，真实共享资产/成本记录和全部目标结算；仍不证明统计充分。
- G3：若干独立开发过程用于定位机会和估计方差；规模由数据与成本决定，不预写主动提升。
- G4：新地区/时段确认集＋有限前瞻；16类按同一合同逐渐扩展。

## 12. 必須能够否定主张的结果

- 如果独立逐目标+合理共享缓存与全局调度没有区别，应降低多目标创新主张，不强加无意义资源紧张。
- 如果批量程序便宜又准确，应如实推荐程序，不制造昂贵API。
- 如果图像没有进入processor，多模态闭环未完成；如仅文字已经泄露全部答案，应修输入。
- 如果只在削弱TAF、特定人为延迟或少数已暴露事件获胜，不宣称稳健增益。
- 如果强基线无法利用新增资料，继续分离感知/融合/输入/结果问题，不直接判定自然证据无价值。
- 如果没有基线概率校准资料，暂停该类概率主分，不用LLM填Gold或用一例自校准。

## 13. 成功交付的最小定义

一条真正的共享资源任务必须能够展示：

`同区域同时间多个目标 → 共同最新完整业务资料 → 同一原生图像合法取得 → 为多个目标复用但实际处理计费 → 只为选择的目标推理 → FOLLOW/OVERRIDE明确生效 → 各目标截止冻结 → 全目标独立结算 → 同日志复算`。

计划执行时以这一链路为核心，而非新增几十个接口、更多空文档、模型调用数或格式有效率。保持原始负结果与所有缺失。

## 14. 依据与访问入口

下列URL用于定位源码/官方文档；这次“读到文档/源码”不代表已克隆、安装或完整复现。

- [R0] 用户仓库：`https://github.com/sisuolv/disastertrace-benchmark/tree/ae69453ff15bc3def6c513fafbfd8758437a8587`
- [R1] Sentinel源文件：`https://github.com/microsoft/sentinel_environments/blob/main/server/timing.py`；本轮blob `2b847f51f873f32bbea22f884efe79f67a0a6f06`。
- [R2] AFA接口：`https://github.com/Linusaronsson/AFA-Benchmark/blob/main/afabench/core/types.py`；本轮blob `8245bf49c8e41f358dfcce5a35a713c40dffeecf`。
- [R3] EWB：`https://extremeweatherbench.readthedocs.io/en/latest/data/`
- [R4] Satpy：`https://satpy.readthedocs.io/en/stable/api/satpy.readers.abi_l1b.html`
- [R5] Py-ART：`https://arm-doe.github.io/pyart/`
- [R6] AWC官方：`https://aviationweather.gov/data/api/`；包括OpenAPI和current批量缓存。
- [R7] NWPS/HEFS：`https://api.water.noaa.gov/about/api`
- [R8] GOES数据目录：`https://registry.opendata.aws/noaa-goes/`

本轮已读取的本仓库源码blob及外部复用范围另见 `specs/source_reuse_registry.json`。本文未执行新科学下载、图像构建、模型推理或完整项目测试；附件结构核查也不能当作上述实现已经完成。
